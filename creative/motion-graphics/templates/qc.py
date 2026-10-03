# qc.py — numeric QC on a rendered film (pair it with qc.sh's images; numbers find, eyes judge).
# Usage: python qc.py out/final.mp4 [--fps 60] [--loop] [--cuts 3.2,7.5]
#   pops     frame-diff spikes > 3x both neighbours (intentional hard cuts show up too: say so, don't hide them)
#   flashes  one-frame flashes: frame n differs from both neighbours while n-1 ~ n+1
#   frozen   runs of identical frames longer than 1 s (nothing should be still except the final hold)
#   loop     (--loop) seam check in POSITION (last vs first) and VELOCITY (motion into vs out of frame 0)
# Exit code 1 if anything unexplained is found. Adapted from howseen-ai/claude-motion-design render_template.py (MIT).
import subprocess
import sys

import numpy as np

a = sys.argv[1:]
path = a[0]
opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                        "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip()
num, den = (probe.split("/") + ["1"])[:2]
FPS = float(opt("--fps") or float(num) / float(den))
CUTS = [float(c) for c in opt("--cuts", "").split(",") if c]
S = 180
raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", path, "-vf", f"scale={S}:{S},format=gray", "-f", "rawvideo", "-"],
                     capture_output=True, check=True).stdout
fr = np.frombuffer(raw, np.uint8).reshape(-1, S, S).astype(np.float32)
d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))           # d[i] = change from frame i to i+1
bad = 0
near_cut = lambda t: any(abs(t - c) < 1.5 / FPS for c in CUTS)

pops = []
for i in range(1, len(d) - 1):
    nb = max(d[i - 1], d[i + 1], 0.3)
    if d[i] > 3 * nb and d[i] > 2.0:
        pops.append((i + 1, (i + 1) / FPS, d[i], nb))
print(f"frames {len(fr)} @ {FPS:g} fps, median step {np.median(d):.2f}")
print(f"pops: {len(pops)}")
for f, t, v, nb in pops:
    tag = "hard cut (declared)" if near_cut(t) else "UNEXPLAINED"
    bad += tag == "UNEXPLAINED"
    print(f"  frame {f:5d}  t {t:7.3f}  diff {v:6.2f}  neighbours {nb:5.2f}  {tag}")

flashes = []
for n in range(1, len(fr) - 1):
    x, y = d[n - 1], d[n]
    skip = np.abs(fr[n + 1] - fr[n - 1]).mean()
    if min(x, y) > 2.0 and skip < 0.35 * min(x, y):
        flashes.append((n, n / FPS, min(x, y), skip))
print(f"one-frame flashes: {len(flashes)}")
for n, t, v, s in flashes:
    bad += 1
    print(f"  frame {n:5d}  t {t:7.3f}  diff {v:6.2f}  n-1 vs n+1 {s:5.2f}")

runs, start = [], None
for i, v in enumerate(list(d) + [99]):
    if v < 0.02 and start is None:
        start = i
    elif v >= 0.02 and start is not None:
        if (i - start) / FPS > 1.0:
            runs.append((start / FPS, i / FPS))
        start = None
print(f"frozen runs > 1 s: {len(runs)}")
for s, e in runs:
    last = e >= (len(fr) - 2) / FPS
    print(f"  {s:7.2f}s -> {e:7.2f}s  {'(final hold: OK)' if last else 'DEAD: keep a micro drift alive'}")
    bad += not last

if "--loop" in a:
    med = float(np.median(d)) or 0.3
    seam = np.abs(fr[-1] - fr[0]).mean()
    vin, vout = np.abs(fr[-1] - fr[-2]).mean(), np.abs(fr[1] - fr[0]).mean()
    pos_ok = seam <= 2 * med
    vel_ok = abs(vin - vout) <= max(1.0, 0.5 * max(vin, vout))
    print(f"loop position: seam {seam:.2f} vs median step {med:.2f} -> {'OK' if pos_ok else 'JUMP: fix positions at t=0/T'}")
    print(f"loop velocity: in {vin:.2f} / out {vout:.2f} -> {'OK' if vel_ok else 'SPEED BREAK: use loopTrack() (spring tails of previous cycles)'}")
    bad += (not pos_ok) + (not vel_ok)

print("QC:", "PASS" if bad == 0 else f"{bad} issue(s) to fix or explain")
sys.exit(1 if bad else 0)
