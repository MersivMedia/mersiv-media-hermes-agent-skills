#!/usr/bin/env python3
"""Surgically replace ONE text-colored character/word on a recolored slide.

Use case: NotebookLM misnumbered a slide (e.g. wrote "5" but should be "3"),
or has a typo, and you need to swap it without paying gpt-image-2 ($0.04/call)
and without risking gpt-image-2's framing drift (it reframes 16:9 content to
3:2 even when prompted to preserve composition — unusable for single-glyph
swaps).

How it works:
  1. Build a text-color mask of the image (R/G/B near #F0F0F0).
  2. Connected-component label all text-color regions.
  3. Find the LARGEST component whose centroid lies in the target region
     (default: left 30% of frame — adapt for other glyph positions).
  4. Erase that component's pixels PLUS a dilated halo (catches anti-alias
     edges) by overwriting with brand BG #121212.
  5. Render the replacement glyph in DejaVuSans-Bold (or Liberation Sans
     Bold) at a font size that matches the original bounding box HEIGHT.
     Height-match works better than width-match for NotebookLM's
     tall-narrow display font — the rendered glyph ends up slightly
     wider, which helps cover the erased halo region.
  6. Save.

Caveats:
  - Erases a small rectangular patch of the dark background pattern
    (constellation art) under the original glyph. Usually invisible at
    video distance, but acceptable trade vs. AI reframing.
  - Text-color mask thresholds are tuned for the [brand] palette
    (#F0F0F0). If you ever change brand colors, retune (r,g,b) checks.
  - Requires scipy for ndimage.label + binary_dilation. Install once:
    `/tmp/hermes/venv/bin/pip install scipy`.

Usage:
  /tmp/hermes/venv/bin/python3 surgical_text_swap.py \\
      --src recolored-14.png --dst recolored-14-fixed.png \\
      --glyph 3 --region left
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont
import numpy as np
from scipy import ndimage  # type: ignore

BG = (18, 18, 18)
TEXT_COLOR = (240, 240, 240)

CANDIDATE_FONTS = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]

# Region definitions: (x_min_frac, x_max_frac, y_min_frac, y_max_frac)
REGIONS = {
    "left":   (0.00, 0.30, 0.00, 1.00),
    "right":  (0.70, 1.00, 0.00, 1.00),
    "top":    (0.00, 1.00, 0.00, 0.30),
    "center": (0.30, 0.70, 0.30, 0.70),
    "full":   (0.00, 1.00, 0.00, 1.00),
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", required=True, help="Source PNG (recolored slide)")
    ap.add_argument("--dst", required=True, help="Output PNG path")
    ap.add_argument("--glyph", required=True, help="Replacement text (e.g. '3')")
    ap.add_argument("--region", default="left", choices=list(REGIONS),
                    help="Where to look for the original text-colored glyph")
    ap.add_argument("--min-area", type=int, default=5000,
                    help="Minimum pixel area to qualify as the target glyph")
    ap.add_argument("--halo-px", type=int, default=4,
                    help="Dilation iterations for anti-alias halo erase")
    args = ap.parse_args()

    if not os.path.exists(args.src):
        print(f"ERROR: source not found: {args.src}", file=sys.stderr)
        return 2

    img = Image.open(args.src).convert("RGB")
    w, h = img.size
    arr = np.array(img)

    # Text-color mask
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    mask = (r > 220) & (g > 215) & (b > 200) & (r < 255) & (g < 250) & (b < 240)

    labels, n = ndimage.label(mask)
    print(f"Found {n} text-color components in full frame")

    xmin_f, xmax_f, ymin_f, ymax_f = REGIONS[args.region]
    rx0, rx1 = int(w * xmin_f), int(w * xmax_f)
    ry0, ry1 = int(h * ymin_f), int(h * ymax_f)

    # Pick largest component whose centroid falls inside the target region.
    candidates = []
    for lid in range(1, n + 1):
        ys, xs = np.where(labels == lid)
        if len(xs) == 0:
            continue
        cx = float(xs.mean())
        cy = float(ys.mean())
        if not (rx0 <= cx < rx1 and ry0 <= cy < ry1):
            continue
        area = len(xs)
        if area < args.min_area:
            continue
        x_min, x_max = int(xs.min()), int(xs.max())
        y_min, y_max = int(ys.min()), int(ys.max())
        candidates.append((area, lid, x_min, x_max, y_min, y_max))

    if not candidates:
        print(f"ERROR: no text-color glyph candidate in region '{args.region}' "
              f"(min_area={args.min_area})", file=sys.stderr)
        return 3

    candidates.sort(reverse=True)
    area, lid, x_min, x_max, y_min, y_max = candidates[0]
    bb_w = x_max - x_min
    bb_h = y_max - y_min
    print(f"Target glyph: component {lid} area={area} "
          f"bbox=({x_min},{y_min})-({x_max},{y_max}) {bb_w}x{bb_h}")

    # Erase component + halo
    comp_mask = (labels == lid)
    dilated = ndimage.binary_dilation(comp_mask, iterations=args.halo_px)
    arr_out = arr.copy()
    arr_out[dilated] = BG
    print(f"Erased {int(comp_mask.sum())} core + "
          f"{int((dilated & ~comp_mask).sum())} halo pixels")
    img = Image.fromarray(arr_out)

    # Pick font
    font_path = next((f for f in CANDIDATE_FONTS if os.path.exists(f)), None)
    if not font_path:
        print("ERROR: no usable font found", file=sys.stderr)
        return 4
    print(f"Font: {font_path}")

    # Binary-search font size so rendered HEIGHT matches bb_h.
    # (Height-match outperforms width-match for NotebookLM's tall-narrow display
    #  font: the resulting glyph is slightly wider and helps cover the erased halo.)
    target_h = bb_h
    lo, hi = 50, 1000
    best_size = lo
    for _ in range(20):
        mid = (lo + hi) // 2
        fnt = ImageFont.truetype(font_path, mid)
        bbox = fnt.getbbox(args.glyph)
        gh = bbox[3] - bbox[1]
        if gh < target_h:
            best_size = mid
            lo = mid + 1
        else:
            hi = mid - 1
        if hi - lo < 2:
            break

    fnt = ImageFont.truetype(font_path, best_size)
    bbox = fnt.getbbox(args.glyph)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    print(f"Font size {best_size}: '{args.glyph}' = {text_w}x{text_h}, "
          f"target {bb_w}x{bb_h}")

    # Centre the new glyph on the original bbox centre.
    orig_cx = (x_min + x_max) // 2
    orig_cy = (y_min + y_max) // 2
    draw_x = orig_cx - text_w // 2 - bbox[0]
    draw_y = orig_cy - text_h // 2 - bbox[1]

    draw = ImageDraw.Draw(img)
    draw.text((draw_x, draw_y), args.glyph, font=fnt, fill=TEXT_COLOR)

    img.save(args.dst)
    print(f"Saved: {args.dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
