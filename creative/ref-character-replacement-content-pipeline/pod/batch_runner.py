#!/usr/bin/env python3
"""Batch runner (runs ON THE POD, one per batch, in tmux).

  batch_runner.py /workspace/batches/<batch> [--host http://127.0.0.1:8189]
                  [--tag A] [--only J01,J02] [--force]

For each manifest row: trim + stage inputs, set every per-job override on the
API graph, render, copy the output to renders/<stem>.mp4, write the sidecar,
append results.csv, and drop one upscale ticket per requested target height.
Rows whose sidecar already says ok are skipped unless --force.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comfy_api import Comfy, median_step_seconds  # noqa: E402

# Paths default to the pod layout; env overrides exist only for offline tests.
COMFY = Path(os.environ.get("REFSWAP_COMFY", "/workspace/ComfyUI"))
RUNDIR = Path(os.environ.get("REFSWAP_RUNDIR", "/root"))
WORKFLOW = Path(os.environ.get("REFSWAP_WORKFLOW",
                               str(COMFY / "user/default/workflows/H3 Ref Character Replacement.json")))
STATE = RUNDIR / "refswap_state.json"           # written by bootstrap: gpu, rate, layout, sage
GPU_LOG = RUNDIR / "gpu.csv"
H3_MAX_AREA = 768 * 1344
UPSCALE_LABEL = {1080: "1080p", 1440: "2k", 2160: "4k"}


def sh(*cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw).stdout


def probe(path):
    d = json.loads(sh("ffprobe", "-v", "error", "-show_entries",
                      "stream=codec_type,width,height,r_frame_rate:format=duration",
                      "-of", "json", str(path)))
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    return {"w": int(v["width"]), "h": int(v["height"]),
            "dur": float(d["format"]["duration"]),
            "audio": any(s["codec_type"] == "audio" for s in d["streams"])}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def h3_dims(w, h, res):
    """Short edge = res, long edge from source aspect, both /32, area-capped at H3's max."""
    if w >= h:
        H, W = res, round(res * w / h / 32) * 32
        while W * H > H3_MAX_AREA:
            W -= 32
    else:
        W, H = res, round(res * h / w / 32) * 32
        while W * H > H3_MAX_AREA:
            H -= 32
    return W, H


def slug(p):
    return re.sub(r"^(src|ref)_", "", Path(p).stem)


def peak_vram(t0, t1):
    """Peak memory.used (MiB) per GPU index between two epochs, from gpu_log.py."""
    peak = {}
    if not GPU_LOG.exists():
        return peak
    for line in GPU_LOG.read_text().splitlines():
        try:
            ts, idx, util, mem = line.split(",")
            ts = float(ts)
        except ValueError:
            continue
        if t0 <= ts <= t1:
            peak[idx] = max(peak.get(idx, 0), int(float(mem)))
    return peak


def find(api, ui_nodes, cls, title_part=None):
    for nid, n in api.items():
        if n["class_type"] != cls:
            continue
        if title_part is None or title_part.lower() in ui_nodes[nid].get("title", "").lower():
            return nid
    raise SystemExit(f"workflow has no {cls} node titled like {title_part!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batch")
    ap.add_argument("--host", default="http://127.0.0.1:8189")
    ap.add_argument("--tag", default="")
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    B = Path(a.batch)
    for d in ("renders", "upscaled", "sidecars", "upscale_queue", "staged"):
        (B / d).mkdir(exist_ok=True)
    rows = list(csv.DictReader(open(B / "manifest.csv")))
    only = {j.strip() for j in a.only.split(",") if j.strip()}
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    rate = float(state.get("gpu_rate_per_hr", 0))
    comfy = Comfy(a.host)
    ui = json.load(open(WORKFLOW))
    ui_nodes = {str(n["id"]): n for n in ui["nodes"]}
    info = comfy.get("/object_info", timeout=180)
    base_api = comfy.ui_to_api(ui, info)
    (RUNDIR / "batch_session").touch()          # tells autostop a batch ran this session

    ids = {
        "director": find(base_api, ui_nodes, "H3PromptDirector"),
        "checkbox": find(base_api, ui_nodes, "PrimitiveBoolean", "background"),
        "turbo": find(base_api, ui_nodes, "PrimitiveBoolean", "Lightning"),
        "duration": find(base_api, ui_nodes, "PrimitiveFloat", "Duration"),
        "steps_full": find(base_api, ui_nodes, "PrimitiveInt", "Full"),
        "steps_turbo": find(base_api, ui_nodes, "PrimitiveInt", "Lightning"),
        "h3": find(base_api, ui_nodes, "MiniMaxH3ReferenceToVideo"),
        "noise": find(base_api, ui_nodes, "RandomNoise"),
        "audio": find(base_api, ui_nodes, "H3AudioRoute"),
        "video": find(base_api, ui_nodes, "VHS_LoadVideo"),
        "char": find(base_api, ui_nodes, "LoadImage", "Character"),
        "save": find(base_api, ui_nodes, "SaveVideo"),
        "sampler": find(base_api, ui_nodes, "SamplerCustomAdvanced"),
        "dec_audio": find(base_api, ui_nodes, "VAEDecodeAudio"),
    }
    results_csv = B / "results.csv"
    new_file = not results_csv.exists()
    fields = ["job", "stem", "tag", "status", "res", "w", "h", "steps", "turbo", "audio",
              "replace_bg", "sage", "layout", "gpu", "exec_s", "median_step_s", "cost_usd",
              "peak_vram_mib", "error"]

    for r in rows:
        job = r["job"]
        if only and job not in only:
            continue
        src, ref = B / "sources" / r["source"], B / "refs" / r["reference"]
        res = int(r.get("res") or 768)
        replace_bg = r.get("replace_bg", "0") == "1"
        turbo = (r.get("turbo") or "1") == "1"
        steps = int(r["steps"]) if r.get("steps") else (4 if turbo else 20)
        audio = r.get("audio") or "source"
        seed = int(r.get("seed") or 4242)
        stem = f"{job}_{slug(src)}__{slug(ref)}_{'bg' if replace_bg else 'char'}_{res}p"
        side = B / "sidecars" / f"{stem}.json"
        if side.exists() and not a.force and json.loads(side.read_text()).get("status") == "ok":
            print(f"[{job}] already done, skipping", flush=True)
            continue

        pi = probe(src)
        duration = min(float(r.get("duration") or 15), pi["dur"], 15.0)
        if audio == "source" and not pi["audio"]:
            audio = "generated"                     # nothing to keep; fall back
        W, H = h3_dims(pi["w"], pi["h"], res)

        # trim to exact duration (H3 conditions on the whole ref clip) + stage
        staged_src = f"rs_{B.name}_{stem}_src.mp4"
        staged_ref = f"rs_{B.name}_{Path(r['reference']).name}"
        sh("ffmpeg", "-v", "error", "-y", "-i", str(src), "-t", f"{duration:.3f}",
           "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p",
           *(["-c:a", "aac", "-b:a", "192k"] if pi["audio"] else ["-an"]),
           str(COMFY / "input" / staged_src))
        shutil.copyfile(ref, COMFY / "input" / staged_ref)

        api = json.loads(json.dumps(base_api))
        g = lambda k: api[ids[k]]["inputs"]  # noqa: E731
        g("director")["instruction"] = r.get("instruction") or \
            "Replace the performer with the character in the reference image. Keep the exact motion and timing."
        if not isinstance(g("director").get("replace_background"), list):
            g("director")["replace_background"] = replace_bg
        g("checkbox")["value"] = replace_bg
        g("turbo")["value"] = turbo
        g("duration")["value"] = duration
        g("steps_turbo" if turbo else "steps_full")["value"] = steps
        g("h3")["width"], g("h3")["height"] = W, H
        g("noise")["noise_seed"] = seed
        g("audio")["mode"] = audio
        g("video")["video"] = staged_src
        g("char")["image"] = staged_ref
        g("save")["filename_prefix"] = f"refswap/{B.name}/{stem}"

        print(f"[{job}] {stem}  {W}x{H} {duration:.2f}s steps={steps} audio={audio}", flush=True)
        out = comfy.run(api, timeout=5400)
        exec_s = out.get("exec_seconds") or out["seconds"]
        peak = peak_vram(out.get("exec_start_epoch", time.time() - exec_s),
                         out.get("exec_end_epoch", time.time()))
        render_path = None
        if out["status"] == "ok":
            vids = [o for o in out["outputs"] if str(o.get("filename", "")).endswith(".mp4")]
            if vids:
                o = vids[-1]
                p = COMFY / "output" / o.get("subfolder", "") / o["filename"]
                render_path = B / "renders" / f"{stem}.mp4"
                shutil.copyfile(p, render_path)
            else:
                out["status"], out["error"] = "error", "no mp4 in outputs"

        sc = {
            "job": job, "stem": stem, "batch": B.name, "tag": a.tag, "status": out["status"],
            "error": out["error"],
            "params": {"source": r["source"], "reference": r["reference"], "replace_bg": replace_bg,
                       "audio": audio, "duration": duration, "turbo": turbo, "steps": steps,
                       "res": res, "w": W, "h": H, "seed": seed,
                       "instruction": g("director")["instruction"],
                       "upscale": r.get("upscale", "")},
            "inputs_sha256": {"source": sha256(src), "reference": sha256(ref)},
            "prompt": "\n".join(out.get("text") or []),
            "timing": {"exec_s": exec_s, "wall_s": out["seconds"],
                       "median_step_s": median_step_seconds(out["step_times"], ids["sampler"]),
                       "audio_decode_s": out["node_seconds"].get(ids["dec_audio"], {}).get("seconds"),
                       "node_seconds": out["node_seconds"], "cached": out["cached"]},
            "gpu": state.get("gpu"), "gpu_rate_per_hr": rate,
            "cost_usd": round(exec_s * rate / 3600, 3),
            "peak_vram_mib": peak, "sage": state.get("sage"), "layout": state.get("layout"),
            "render": str(render_path) if render_path else None,
            "finished": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        side.write_text(json.dumps(sc, indent=1))
        with open(results_csv, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            if new_file:
                w.writeheader(); new_file = False
            w.writerow({"job": job, "stem": stem, "tag": a.tag, "status": out["status"], "res": res,
                        "w": W, "h": H, "steps": steps, "turbo": int(turbo), "audio": audio,
                        "replace_bg": int(replace_bg), "sage": state.get("sage"),
                        "layout": state.get("layout"), "gpu": state.get("gpu"), "exec_s": exec_s,
                        "median_step_s": sc["timing"]["median_step_s"], "cost_usd": sc["cost_usd"],
                        "peak_vram_mib": max(peak.values()) if peak else "",
                        "error": (out["error"] or "")[:300]})
        print(f"[{job}] {out['status']} exec={exec_s}s step={sc['timing']['median_step_s']}s "
              f"cost=${sc['cost_usd']} peak={peak} {out['error'] or ''}", flush=True)

        if render_path:
            for t in [x for x in (r.get("upscale") or "").split(";") if x.strip()]:
                th = int(t)
                ticket = {"batch": str(B), "stem": stem, "src": str(render_path), "src_res": res,
                          "target_h": th, "label": UPSCALE_LABEL.get(th, f"{th}p"),
                          "out": str(B / "upscaled" / f"{stem}_{UPSCALE_LABEL.get(th, f'{th}p')}.mp4"),
                          "tag": a.tag, "created": time.time()}
                (B / "upscale_queue" / f"{stem}__{th}.json").write_text(json.dumps(ticket))
                print(f"[{job}] ticket -> upscale {th}p", flush=True)
    print("RUNNER_DONE", flush=True)


if __name__ == "__main__":
    main()
