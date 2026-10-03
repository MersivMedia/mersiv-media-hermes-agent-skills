# remake_qa.py — QA sheets after a full render:
#   out/qa/persec_K.jpg   REF | OURS one frame per second (33 pairs per page)
#   out/qa/seams.jpg      last 2 / first 2 frames at every group boundary (project.json groups)
#   old-brand colour scan over our frames (thresholds in project.json oldColorScan): frames still showing the old brand's hue
# Read every sheet before claiming a match. Adapted from howseen-ai/claude-motion-design remake_qa.py (MIT).
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

H = Path.cwd()
P = json.loads((H / "project.json").read_text())
Q = H / "out/qa"
Q.mkdir(parents=True, exist_ok=True)
FULL = H / "out/full"
n = len(list(FULL.glob("o_f*.png")))
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
except Exception:
    font = ImageFont.load_default()


def pair(F):
    r = Image.open(H / f"ref/full/f{F:04d}.jpg").convert("RGB").resize((480, 270))
    o = Image.open(FULL / f"o_f{F:04d}.png").convert("RGB").resize((480, 270))
    c = Image.new("RGB", (970, 290), "white")
    c.paste(r, (0, 20))
    c.paste(o, (490, 20))
    ImageDraw.Draw(c).text((4, 2), f"F{F}  REF | OURS", fill="red", font=font)
    return c


def sheet(frames, name, cols=3):
    tiles = [pair(F) for F in frames if F < n]
    if not tiles:
        return
    rows = -(-len(tiles) // cols)
    s = Image.new("RGB", (cols * 970, rows * 290), "white")
    for i, t in enumerate(tiles):
        s.paste(t, ((i % cols) * 970, (i // cols) * 290))
    s.save(Q / name, quality=78)
    print("wrote", Q / name)


secs = list(range(0, n, P["fps"]))
for k in range(0, len(secs), 33):
    sheet(secs[k:k + 33], f"persec_{k // 33 + 1}.jpg")
seams = []
for g, (a, b) in sorted(P["groups"].items(), key=lambda kv: kv[1][0])[1:]:
    seams += [a - 2, a - 1, a, a + 1]
sheet(seams, "seams.jpg", cols=2)

sc = P.get("oldColorScan", {})
bad = []
for F in range(0, n, 4):
    a = np.asarray(Image.open(FULL / f"o_f{F:04d}.png").convert("RGB").resize((480, 270)), dtype=np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    m = (r > sc.get("rMin", 180)) & (r - g > sc.get("rgGap", 60)) & (r - b > sc.get("rbGap", 60)) & (g > sc.get("gMin", 60))
    if m.sum() > sc.get("minPixels", 150):
        bad.append((F, int(m.sum())))
print(f"old-brand-colour frames: {len(bad)}", bad[:40])
