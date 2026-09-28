#!/usr/bin/env python3
"""GPU logger (runs ON THE POD in tmux). Appends epoch,index,util%,memMiB to
/root/gpu.csv every second. batch_runner / upscale_worker read it to report
peak VRAM per job; perf_report uses it for lane-overlap utilisation."""
import subprocess
import time

with open("/root/gpu.csv", "a", buffering=1) as f:
    while True:
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,utilization.gpu,memory.used",
                 "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10).stdout
            now = time.time()
            for line in out.strip().splitlines():
                idx, util, mem = [x.strip() for x in line.split(",")]
                f.write(f"{now:.1f},{idx},{util},{mem}\n")
        except Exception:
            pass
        time.sleep(1)
