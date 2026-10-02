#!/usr/bin/env python3
"""Upscale lane worker (runs ON THE POD in tmux).

Polls /workspace/batches/*/upscale_queue/*.json tickets (dropped by
batch_runner.py as each render lands), claims one atomically by renaming it
to .working, runs upscale_run.py against the upscale ComfyUI (--host), then
copies the output to upscaled/<stem>_<label>.mp4, writes an upscale sidecar,
and appends upscale_results.csv. Exits after --idle-exit seconds with nothing
to do (0 = run forever).

Hardening after 2026-09-28 (the lane died on one bad ticket, stranding the
rest while the session waited on it):
  - every ticket runs inside try/except: an exception marks THAT ticket
    .failed with the traceback and the worker moves on;
  - a heartbeat file (/root/upworker.alive, epoch seconds) is touched every
    loop, so the local session can tell a dead worker from a slow one;
  - stale .working tickets left by a crashed worker are requeued on start.
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
import traceback
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from batch_runner import peak_vram, STATE, COMFY, RUNDIR  # noqa: E402
from comfy_api import pick_output  # noqa: E402

UPSCALE = os.environ.get("REFSWAP_UPSCALE", str(RUNDIR / "pod/upscale_run.py"))
BATCHES = os.environ.get("REFSWAP_BATCHES", "/workspace/batches")
HEARTBEAT = RUNDIR / "upworker.alive"
UP_TIMEOUT = int(os.environ.get("REFSWAP_UPSCALE_TIMEOUT", "3600"))


def beat():
    HEARTBEAT.write_text(str(int(time.time())))


def requeue_stale():
    for w in glob.glob(f"{BATCHES}/*/upscale_queue/*.json.working"):
        os.rename(w, w[:-len(".working")])
        print(f"requeued stale ticket {os.path.basename(w)}", flush=True)


def claim():
    for t in sorted(glob.glob(f"{BATCHES}/*/upscale_queue/*.json")):
        w = t + ".working"
        try:
            os.rename(t, w)
            return Path(w)
        except OSError:
            continue
    return None


def process(w: Path, a, state: dict, rate: float):
    tk = json.loads(w.read_text())
    B = Path(tk["batch"])
    name = f"{tk['stem']}_{tk['label']}"
    rj = str(RUNDIR / f"upscale_{name}.json")
    prefix = f"refswap_up/{B.name}/{name}"
    print(f"[{name}] {tk['src_res']}p -> {tk['target_h']}p", flush=True)
    t0 = time.time()
    res, out_path, err = {}, None, None
    try:
        # Popen + poll so the heartbeat keeps ticking through a 40-min 4K job.
        proc = subprocess.Popen([sys.executable, "-u", UPSCALE, "--host", a.host, "--input", tk["src"],
                                 "--engine", "seedvr2", "--seedvr-model", a.seedvr_model,
                                 "--target-height", str(tk["target_h"]), "--steps", str(a.steps),
                                 "--prefix", prefix, "--result-json", rj],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        while proc.poll() is None:
            beat(); time.sleep(5)
            if time.time() - t0 > UP_TIMEOUT:
                proc.kill(); raise TimeoutError(f"upscale exceeded {UP_TIMEOUT}s")
        tail = (proc.stdout.read() or "")[-1500:]
        if proc.returncode != 0 or not os.path.exists(rj):
            err = f"upscale_run rc={proc.returncode}: {tail}".strip()
        else:
            res = json.loads(Path(rj).read_text())
            src = pick_output(res.get("outputs", []), COMFY, prefix)
            if src is None:
                err = f"no saved mp4 in upscale outputs: {res.get('outputs')}"[:600]
            else:
                out_path = Path(tk["out"])
                shutil.copyfile(src, out_path)
    except Exception:
        err = traceback.format_exc()[-1500:]
    ok = err is None
    exec_s = res.get("exec_seconds") or round(time.time() - t0, 1)
    peak = peak_vram(res.get("exec_start_epoch") or t0, res.get("exec_end_epoch") or time.time())
    sc = {"stem": tk["stem"], "label": tk["label"], "src_res": tk["src_res"],
          "target_h": tk["target_h"], "target_wh": res.get("target"), "status": "ok" if ok else "error",
          "error": err, "exec_s": exec_s, "wall_s": round(time.time() - t0, 1),
          "cost_usd": round(exec_s * rate / 3600, 3), "peak_vram_mib": peak,
          "seedvr_model": a.seedvr_model, "steps": a.steps, "layout": state.get("layout"),
          "gpu": state.get("gpu"), "tag": tk.get("tag"), "out": str(out_path) if out_path else None}
    try:
        (B / "sidecars").mkdir(exist_ok=True)
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
    finally:
        os.rename(w, str(w).replace(".json.working", ".json.done" if ok else ".json.failed"))
    print(f"[{name}] {'ok' if ok else 'FAILED'} exec={exec_s}s cost=${sc['cost_usd']} "
          f"{(err or '')[:300]}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="http://127.0.0.1:8190")
    ap.add_argument("--seedvr-model", default="seedvr2_7b_sharp_int8_convrot.safetensors")
    ap.add_argument("--steps", type=int, default=6)
    ap.add_argument("--idle-exit", type=int, default=0)
    a = ap.parse_args()
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    rate = float(state.get("gpu_rate_per_hr", 0))
    requeue_stale()
    idle_since = time.time()
    print(f"upscale worker on {a.host}", flush=True)
    while True:
        beat()
        w = claim()
        if w is None:
            if a.idle_exit and time.time() - idle_since > a.idle_exit:
                print("idle, exiting", flush=True)
                HEARTBEAT.unlink(missing_ok=True)
                return
            time.sleep(5)
            continue
        try:
            process(w, a, state, rate)
        except Exception:                         # last line of defence: never die on one ticket
            print(f"[{w.name}] worker error, ticket failed:\n{traceback.format_exc()[-1500:]}", flush=True)
            if w.exists():
                os.rename(w, str(w).replace(".json.working", ".json.failed"))
        idle_since = time.time()


if __name__ == "__main__":
    main()
