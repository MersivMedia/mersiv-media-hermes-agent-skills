# remake_analyze.py — Phase 0: understand the reference before building anything.
# Usage: python3 remake_analyze.py [--fps 24] [--width 1920]
#   reads  ref/reference.mp4
#   writes ref/full/fNNNN.jpg (every frame, 0-based, conformed to --fps and --width x 16:9 height of the source aspect)
#          ref/audio.wav, ref/cuts.json {fps, n, w, h, cuts, diff}, ref/sheet/sheet_K.jpg (every 6th frame, labelled, CUT marked)
# Then: read the sheets and write SPEC.md (shot table). Most "cuts" in modern launch films are continuous camera/morph
# moves, so expect only ~10-15 hard cuts, and expect SPEC boundaries to be a few frames off (build agents fix them).
# Adapted from howseen-ai/claude-motion-design remake_analyze.py (MIT).
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

a = sys.argv[1:]
opt = lambda k, d: a[a.index(k) + 1] if k in a else d
FPS, WID = int(opt("--fps", "24")), int(opt("--width", "1920"))
H = Path.cwd()
ref = H / "ref/reference.mp4"
if not ref.exists():
    sys.exit("put the reference at ref/reference.mp4 (user-supplied: this box can't download from YouTube)")
full = H / "ref/full"
full.mkdir(parents=True, exist_ok=True)
if not any(full.iterdir()):
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(ref), "-vf", f"fps={FPS},scale={WID}:-2", "-start_number", "0",
                    "-q:v", "3", str(full / "f%04d.jpg")], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(ref), "-vn", "-ac", "2", "-ar", "48000", str(H / "ref/audio.wav")])
frames = sorted(full.glob("f*.jpg"))
w, h = Image.open(frames[0]).size
print(f"frames {len(frames)} @ {FPS} fps, {w}x{h}, {len(frames) / FPS:.2f}s")

small = [np.asarray(Image.open(f).convert("L").resize((192, 108)), dtype=np.float32) for f in frames]
d = np.array([0.0] + [np.abs(small[i] - small[i - 1]).mean() for i in range(1, len(small))])
cuts = []
for i in range(1, len(d)):                      # spike = diff much larger than its local median
    lo, hi = max(1, i - 6), min(len(d), i + 7)
    loc = np.median(np.concatenate([d[lo:i], d[i + 1:hi]])) if hi - lo > 1 else 0
    if d[i] > 6 and d[i] > 3.5 * (loc + 0.5):
        cuts.append(i)
print("hard cuts at frames:", cuts)
json.dump({"fps": FPS, "n": len(frames), "w": w, "h": h, "cuts": cuts, "diff": [round(float(x), 2) for x in d]},
          open(H / "ref/cuts.json", "w"))

sheet_dir = H / "ref/sheet"
sheet_dir.mkdir(exist_ok=True)
thumbs = [(i, Image.open(frames[i]).resize((256, int(256 * h / w)))) for i in range(0, len(frames), 6)]
cols, th = 10, int(256 * h / w) + 16
for page in range(0, len(thumbs), 80):
    chunk = thumbs[page:page + 80]
    rows = (len(chunk) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 256, rows * th), "white")
    dr = ImageDraw.Draw(sheet)
    for k, (i, im) in enumerate(chunk):
        x, y = (k % cols) * 256, (k // cols) * th
        sheet.paste(im, (x, y))
        near = any(abs(i - c) < 6 for c in cuts)
        dr.text((x + 4, y + th - 14), f"f{i}" + (" CUT" if near else ""), fill="red")
    sheet.save(sheet_dir / f"sheet_{page // 80}.jpg", quality=80)
print(f"sheets -> {sheet_dir} ({(len(thumbs) + 79) // 80})")
print("next: read the sheets, write SPEC.md (copy SPEC_TEMPLATE.md), then python3 remake_stub.py")
