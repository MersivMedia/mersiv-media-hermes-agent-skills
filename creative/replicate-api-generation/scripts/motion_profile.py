#!/usr/bin/env python3
"""Motion profile of a video clip or a time range of a reel: diagnose "choppy" before re-rendering.

Reports, from 320x180 grayscale frame-to-frame mean-abs-diff (uint8 decode, low RAM):
  - median motion (a world-change / travel shot under ~4 reads as static to this user)
  - motion per second (dips toward ~4 or below between busy seconds = ease-in/ease-out at shot joins,
    which the user perceives as "choppy"; fix with ONE long first/last-frame shot, see
    references/match-cut-relay-transitions.md "Long continuous shots")
  - hard internal cuts: frame i where motion[i] > 2.2 * median(motion[i-3..i+3 excl. i]) + 3
    (H3 sometimes inserts a camera cut inside a long generation; hide it with an 8-frame xfade)
  - near-duplicate frames (motion < 0.15) = visible "pauses"

Usage:
  motion_profile.py CLIP.mp4                  # whole clip
  motion_profile.py REEL.mp4 --from 32.2 --to 42.7
Prints one JSON object.
"""
import argparse, json, subprocess
import numpy as np

W, H = 320, 180

def motion(path, t0=None, t1=None):
    cmd = ["ffmpeg", "-v", "error"]
    if t0 is not None: cmd += ["-ss", str(t0)]
    if t1 is not None: cmd += ["-to", str(t1)]
    cmd += ["-i", path, "-vf", f"scale={W}:{H},format=gray", "-f", "rawvideo", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    prev, m = None, []
    while True:
        b = p.stdout.read(W * H)
        if len(b) < W * H: break
        f = np.frombuffer(b, np.uint8).astype(np.int16)
        if prev is not None: m.append(float(np.abs(f - prev).mean()))
        prev = f
    p.wait()
    return np.array(m, np.float32)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("--from", dest="t0", type=float); ap.add_argument("--to", dest="t1", type=float)
    ap.add_argument("--fps", type=int, default=24)
    a = ap.parse_args()
    m = motion(a.video, a.t0, a.t1)
    if len(m) < 8:
        print(json.dumps({"error": "too few frames", "frames": int(len(m) + 1)})); return
    cuts = [(i + 1, round(float(m[i]), 1)) for i in range(3, len(m) - 3)
            if m[i] > 2.2 * np.median(np.r_[m[i - 3:i], m[i + 1:i + 4]]) + 3]
    dups = [i + 1 for i, v in enumerate(m) if v < 0.15]
    print(json.dumps(dict(
        frames=int(len(m) + 1), secs=round((len(m) + 1) / a.fps, 2),
        median_motion=round(float(np.median(m)), 2),
        motion_per_second=[round(float(np.mean(m[k:k + a.fps])), 1) for k in range(0, len(m), a.fps)],
        hard_internal_cuts=cuts, near_duplicate_frames=len(dups), first_dups=dups[:20])))

if __name__ == "__main__":
    main()
