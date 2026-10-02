#!/usr/bin/env python3
"""Background-motion check for generated video clips.

Catches the "frozen background" failure (the subject moves, but the rain,
traffic and crowd don't) BEFORE spending on dependent edits (e.g.
rapid-change looks that copy the base clip's background).

Usage:
  bg_motion_check.py CLIP.mp4 [CLIP2.mp4 ...] [--out DIR]
    [--subject x0,y0,x1,y1]   # subject box as fractions (default 0.30,0.15,0.70,1.0)

Prints JSON per clip:
  bg_mean               mean abs frame-to-frame luma diff outside the subject box
  subject_mean          same, inside the box
  pct_bg_pixels_moving  % of background pixel-steps with diff > 6 (0-255 scale)
  left/right/top        per-band means
Also writes <clip>_motionmap.png (max diff over time x4; bright = moved).

Reference point (2026-09-29, H3 2K, a neon rainy street walk with the
background melted into bokeh): pct_bg_pixels_moving = 3.7, bg_mean = 1.1,
and it was rejected by the user as "nothing moving". A shot with a real
camera move measured 38%. Always look at the motion map too: rain reads as
streaks, cars as horizontal bands, people as blobs.
Needs ffmpeg, numpy, Pillow.
"""
import json, os, subprocess, sys
import numpy as np
from PIL import Image

W, H = 480, 270

def frames(p):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-vf", f"scale={W}:{H},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.float32)

def main(argv):
    out_dir, box, clips = None, (0.30, 0.15, 0.70, 1.0), []
    it = iter(argv)
    for a in it:
        if a == "--out": out_dir = next(it)
        elif a == "--subject": box = tuple(float(v) for v in next(it).split(","))
        else: clips.append(a)
    res = {}
    for p in clips:
        a = frames(p)
        if len(a) < 2:
            res[p] = {"error": "fewer than 2 frames"}; continue
        d = np.abs(np.diff(a, axis=0))
        bg = np.ones((H, W), bool)
        bg[int(H * box[1]):int(H * box[3]), int(W * box[0]):int(W * box[2])] = False
        res[os.path.basename(p)] = dict(
            frames=len(a),
            bg_mean=round(float(d[:, bg].mean()), 2),
            subject_mean=round(float(d[:, ~bg].mean()), 2),
            left=round(float(d[:, :, :int(W * .25)].mean()), 2),
            right=round(float(d[:, :, int(W * .75):].mean()), 2),
            top=round(float(d[:, :int(H * .2), :].mean()), 2),
            pct_bg_pixels_moving=round(float((d[:, bg] > 6).mean() * 100), 2))
        m = np.clip(d.max(axis=0) * 4, 0, 255).astype(np.uint8)
        od = out_dir or os.path.dirname(os.path.abspath(p))
        Image.fromarray(m).save(os.path.join(od, os.path.splitext(os.path.basename(p))[0] + "_motionmap.png"))
    print(json.dumps(res, indent=1))

if __name__ == "__main__":
    main(sys.argv[1:])
