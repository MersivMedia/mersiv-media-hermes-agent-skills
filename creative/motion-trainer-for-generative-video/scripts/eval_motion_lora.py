#!/usr/bin/env python3
"""Sweep motion-LoRA checkpoints x strengths against a fixed-seed baseline.

Submits one generation per (checkpoint, strength) pair to a running ComfyUI
server, plus a no-LoRA baseline at the same seed, so the LoRA's effect can
be judged rather than guessed.

Requires a ComfyUI API-format workflow containing a LoRA loader node.

Usage:
    python3 eval_motion_lora.py \
        --comfy-host http://127.0.0.1:8188 \
        --workflow ./motion_test_api.json \
        --lora-dir ./out --strengths 0.4,0.6,0.8,1.0 \
        --prompt "a person walking through a doorway" \
        --output-dir ./eval
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path


def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def http(method, url, payload=None, timeout=120):
    cmd = ["curl", "-sS", "-X", method, url,
           "-H", "Content-Type: application/json",
           "-w", "\n__STATUS__%{http_code}", "--max-time", str(timeout)]
    if payload is not None:
        cmd += ["-d", json.dumps(payload)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        die(f"curl failed: {r.stderr.strip()}")
    body, _, status = r.stdout.rpartition("\n__STATUS__")
    try:
        return int(status), json.loads(body)
    except (ValueError, json.JSONDecodeError):
        return int(status or 0), body


def find_nodes(wf, class_substr):
    return [nid for nid, n in wf.items()
            if class_substr.lower() in str(n.get("class_type", "")).lower()]


def set_if_present(wf, node_ids, key, value):
    for nid in node_ids:
        if key in wf[nid].get("inputs", {}):
            wf[nid]["inputs"][key] = value
            return True
    return False


def submit_and_wait(host, wf, timeout):
    st, body = http("POST", f"{host}/prompt", {"prompt": wf})
    if st != 200:
        return None, f"submit HTTP {st}: {str(body)[:300]}"
    pid = body.get("prompt_id")
    if not pid:
        return None, f"no prompt_id: {str(body)[:200]}"

    deadline = time.time() + timeout
    while time.time() < deadline:
        st, hist = http("GET", f"{host}/history/{pid}")
        if st == 200 and isinstance(hist, dict) and pid in hist:
            entry = hist[pid]
            status = (entry.get("status") or {}).get("status_str")
            if status == "error":
                return None, "execution error (see ComfyUI log)"
            return entry, None
        time.sleep(3)
    return None, f"timeout after {timeout}s"


def collect_outputs(entry):
    files = []
    for node_out in (entry.get("outputs") or {}).values():
        for key in ("images", "gifs", "videos"):
            for item in node_out.get(key, []) or []:
                if isinstance(item, dict) and item.get("filename"):
                    files.append(item)
    return files


def download(host, item, dest):
    q = urllib.parse.urlencode({
        "filename": item["filename"],
        "subfolder": item.get("subfolder", ""),
        "type": item.get("type", "output"),
    })
    r = subprocess.run(["curl", "-sS", "-o", str(dest), f"{host}/view?{q}"],
                       capture_output=True, text=True)
    return r.returncode == 0 and dest.exists() and dest.stat().st_size > 0


def main():
    ap = argparse.ArgumentParser(description="Motion LoRA eval sweep")
    ap.add_argument("--comfy-host", default="http://127.0.0.1:8188")
    ap.add_argument("--workflow", required=True, help="API-format workflow JSON")
    ap.add_argument("--lora-dir", required=True, help="dir of .safetensors checkpoints")
    ap.add_argument("--strengths", default="0.4,0.6,0.8,1.0")
    ap.add_argument("--prompt", help="override the positive prompt")
    ap.add_argument("--seed", type=int, default=12345,
                    help="fixed seed — same for every cell AND the baseline")
    ap.add_argument("--output-dir", default="./eval")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--no-baseline", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    wf_path = Path(a.workflow).expanduser()
    if not wf_path.is_file():
        die(f"workflow not found: {wf_path}")
    base_wf = json.loads(wf_path.read_text())
    if "nodes" in base_wf and "links" in base_wf:
        die("workflow is editor format — re-export via Workflow -> Export (API)")

    lora_dir = Path(a.lora_dir).expanduser()
    ckpts = sorted(lora_dir.glob("*.safetensors")) if lora_dir.is_dir() else []
    if not ckpts:
        die(f"no .safetensors in {lora_dir}")

    try:
        strengths = [float(s) for s in a.strengths.split(",") if s.strip()]
    except ValueError:
        die("--strengths must be comma-separated numbers")

    lora_nodes = find_nodes(base_wf, "lora")
    if not lora_nodes:
        die("no LoRA loader node in the workflow")
    sampler_nodes = find_nodes(base_wf, "sampler")
    text_nodes = find_nodes(base_wf, "cliptextencode")

    outdir = Path(a.output_dir).expanduser()
    total = len(ckpts) * len(strengths) + (0 if a.no_baseline else 1)
    print(f"checkpoints: {len(ckpts)}  strengths: {len(strengths)}  "
          f"=> {total} generation(s)")
    print(f"fixed seed: {a.seed}\n")

    if a.dry_run:
        for c in ckpts:
            for s in strengths:
                print(f"  would run {c.name} @ {s}")
        if not a.no_baseline:
            print("  would run BASELINE (no LoRA)")
        return

    outdir.mkdir(parents=True, exist_ok=True)
    results = []

    jobs = [(c, s) for c in ckpts for s in strengths]
    if not a.no_baseline:
        jobs.append((None, 0.0))

    for ckpt, strength in jobs:
        label = "BASELINE" if ckpt is None else f"{ckpt.stem}@{strength}"
        print(f"[{label}] ...", flush=True)

        wf = json.loads(json.dumps(base_wf))
        if a.prompt and text_nodes:
            set_if_present(wf, text_nodes, "text", a.prompt)
        set_if_present(wf, sampler_nodes, "seed", a.seed)
        set_if_present(wf, sampler_nodes, "noise_seed", a.seed)

        if ckpt is None:
            # Baseline: neutralize the LoRA rather than rewiring the graph.
            set_if_present(wf, lora_nodes, "strength_model", 0.0)
            set_if_present(wf, lora_nodes, "strength_clip", 0.0)
        else:
            set_if_present(wf, lora_nodes, "lora_name", ckpt.name)
            set_if_present(wf, lora_nodes, "strength_model", strength)
            set_if_present(wf, lora_nodes, "strength_clip", strength)

        t0 = time.time()
        entry, err = submit_and_wait(a.comfy_host, wf, a.timeout)
        elapsed = round(time.time() - t0, 1)

        if err:
            print(f"   FAILED: {err}")
            results.append({"label": label, "status": "failed", "error": err})
            continue

        saved = []
        for i, item in enumerate(collect_outputs(entry)):
            ext = Path(item["filename"]).suffix or ".png"
            dest = outdir / f"{label.replace('@','_s')}_{i}{ext}"
            if download(a.comfy_host, item, dest):
                saved.append(str(dest))

        print(f"   ok {elapsed}s -> {len(saved)} file(s)")
        results.append({"label": label, "status": "ok",
                        "seconds": elapsed, "files": saved})

    (outdir / "results.json").write_text(json.dumps(results, indent=2))
    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"\n{ok}/{len(results)} succeeded -> {outdir}/results.json")
    print("\nJudge three axes SEPARATELY against the baseline:")
    print("  1. motion fidelity   — is the learned movement present?")
    print("  2. prompt adherence  — do action words still change the output?")
    print("  3. identity bleed    — did a specific subject leak in?")
    print("Record the winner in references/run-log.md.")


if __name__ == "__main__":
    main()
