#!/usr/bin/env python3
"""Upscale lane worker (runs ON THE POD in tmux).

Polls /workspace/batches/*/upscale_queue/*.json tickets (dropped by
batch_runner.py as each render lands), claims one atomically by renaming it
to .working, runs upscale_run.py against the upscale ComfyUI (--host), then
moves the output to upscaled/<stem>_<label>.mp4, writes an upscale sidecar,
and appends upscale_results.csv. Exits after --idle-exit seconds with nothing
to do (0 = run forever).
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from batch_runner import peak_vram, STATE, COMFY, RUNDIR  # noqa: E402

UPSCALE = os.environ.get("REFSWAP_UPSCALE", str(RUNDIR / "pod/upscale_run.py"))
COMFY_OUT = COMFY / "output"
BATCHES = os.environ.get("REFSWAP_BATCHES", "/workspace/batches")


def claim():
    for t in sorted(glob.glob(f"{BATCHES}/*/upscale_queue/*.json")):
        w = t + ".working"
        try:
            os.rename(t, w)
            return Path(w)
        except OSError:
            continue
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="http://127.0.0.1:8190")
    ap.add_argument("--seedvr-model", default="seedvr2_7b_sharp_int8_convrot.safetensors")
    ap.add_argument("--steps", type=int, default=6)
    ap.add_argument("--idle-exit", type=int, default=0)
    a = ap.parse_args()
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    rate = float(state.get("gpu_rate_per_hr", 0))
    idle_since = time.time()
    print(f"upscale worker on {a.host}", flush=True)
    while True:
        w = claim()
        if w is None:
            if a.idle_exit and time.time() - idle_since > a.idle_exit:
                print("idle, exiting", flush=True)
                return
            time.sleep(5)
            continue
        tk = json.loads(w.read_text())
        B = Path(tk["batch"])
        name = f"{tk['stem']}_{tk['label']}"
        rj = str(RUNDIR / f"upscale_{name}.json")
        print(f"[{name}] {tk['src_res']}p -> {tk['target_h']}p", flush=True)
        t0 = time.time()
        p = subprocess.run([sys.executable, "-u", UPSCALE, "--host", a.host, "--input", tk["src"],
                            "--engine", "seedvr2", "--seedvr-model", a.seedvr_model,
                            "--target-height", str(tk["target_h"]), "--steps", str(a.steps),
                            "--prefix", f"refswap_up/{B.name}/{name}", "--result-json", rj],
                           capture_output=True, text=True)
        ok = p.returncode == 0 and os.path.exists(rj)
        res = json.loads(Path(rj).read_text()) if ok else {}
        out_path, err = None, None
        if ok:
            vids = [o for o in res.get("outputs", []) if str(o.get("filename", "")).endswith(".mp4")]
            if vids:
                o = vids[-1]
                src = COMFY_OUT / o.get("subfolder", "") / o["filename"]
                out_path = Path(tk["out"])
                shutil.copyfile(src, out_path)
            else:
                ok, err = False, "no mp4 in upscale outputs"
        else:
            err = (p.stdout[-1500:] + "\n" + p.stderr[-1500:]).strip()
        exec_s = res.get("exec_seconds") or round(time.time() - t0, 1)
        peak = peak_vram(res.get("exec_start_epoch") or t0, res.get("exec_end_epoch") or time.time())
        sc = {"stem": tk["stem"], "label": tk["label"], "src_res": tk["src_res"],
              "target_h": tk["target_h"], "target_wh": res.get("target"), "status": "ok" if ok else "error",
              "error": err, "exec_s": exec_s, "wall_s": round(time.time() - t0, 1),
              "cost_usd": round(exec_s * rate / 3600, 3), "peak_vram_mib": peak,
              "seedvr_model": a.seedvr_model, "steps": a.steps, "layout": state.get("layout"),
              "gpu": state.get("gpu"), "tag": tk.get("tag"), "out": str(out_path) if out_path else None}
        (B / "sidecars" / f"{name}.json").write_text(json.dumps(sc, indent=1))
        f = B / "upscale_results.csv"
        new = not f.exists()
        with open(f, "a", newline="") as fh:
            wr = csv.DictWriter(fh, fieldnames=["stem", "label", "src_res", "target_h", "status",
                                                "exec_s", "cost_usd", "peak_vram_mib", "layout",
                                                "gpu", "tag", "error"])
            if new:
                wr.writeheader()
            wr.writerow({k: sc.get(k) for k in wr.fieldnames} |
                        {"peak_vram_mib": max(peak.values()) if peak else "",
                         "error": (err or "")[:300]})
        os.rename(w, str(w).replace(".json.working", ".json.done" if ok else ".json.failed"))
        print(f"[{name}] {'ok' if ok else 'FAILED'} exec={exec_s}s cost=${sc['cost_usd']} "
              f"{(err or '')[:300]}", flush=True)
        idle_since = time.time()


if __name__ == "__main__":
    main()
