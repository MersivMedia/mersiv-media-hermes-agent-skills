# Brand Asset Composition with PIL

Reusable Python recipes for compositing brand assets after the AI-generated parts are in hand. Pixel-perfect, deterministic, no model drift.

## Setup

PIL/Pillow doesn't install cleanly with PEP 668 system-managed Python. Use a venv:

```bash
python3 -m venv /tmp/build_venv
/tmp/build_venv/bin/pip install --quiet Pillow
/tmp/build_venv/bin/python3 your_script.py
```

## Transparent background from solid-color image

Drop the brand-background color and replace with alpha=0. Includes a soft-ramp zone for clean edges (no jaggies).

```python
from PIL import Image

HARD_BLACK = 35   # max(rgb) <= this → fully transparent
SOFT_BLACK = 55   # ramp zone

def make_transparent(src_path, dst_path):
    img = Image.open(src_path).convert("RGBA")
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            m = max(r, g, b)
            if m <= HARD_BLACK:
                px[x, y] = (r, g, b, 0)
            elif m <= SOFT_BLACK:
                ratio = (m - HARD_BLACK) / (SOFT_BLACK - HARD_BLACK)
                px[x, y] = (r, g, b, int(ratio * 255))
    img.save(dst_path)
```

## Dark outline around transparent assets

Without a background, bright shapes (white/gold) get lost on light surfaces. Add a thin dark stroke around all visible content. Use brand dark, not pure `#000`.

```python
from PIL import Image, ImageFilter

OUTLINE_COLOR = (18, 18, 18)   # brand dark
OUTLINE_PX = 3

def add_outline(src_path, dst_path):
    img = Image.open(src_path).convert("RGBA")
    w, h = img.size
    alpha = img.split()[-1]
    kernel = 2 * OUTLINE_PX + 1
    dilated = alpha.filter(ImageFilter.MaxFilter(kernel))
    outline = Image.new("RGBA", (w, h), OUTLINE_COLOR + (0,))
    op, dp, ap = outline.load(), dilated.load(), alpha.load()
    for y in range(h):
        for x in range(w):
            d, o = dp[x, y], ap[x, y]
            if d > 0 and o < d:
                op[x, y] = OUTLINE_COLOR + (d - o,)
    Image.alpha_composite(outline, img).save(dst_path)
```

## Unify two backgrounds (different shades of "black")

AI-generated images often have slightly-off near-black backgrounds. When compositing multiple assets together, paint any near-black pixel to the exact brand color so the seams disappear.

```python
def recolor_bg(img_rgba, threshold=40, new_bg=(18, 18, 18)):
    img = img_rgba.convert("RGB")
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if r < threshold and g < threshold and b < threshold:
                px[x, y] = new_bg
    return img.convert("RGBA")
```

## Trim solid-bg padding (bounding box of content)

Before compositing into a lockup, trim each asset to its tight content bbox so spacing math is predictable.

```python
def trim_dark_bg(img, tol=22):
    px = img.convert("RGB").load()
    w, h = img.size
    min_x, min_y, max_x, max_y = w, h, 0, 0
    for y in range(h):
        for x in range(w):
            if max(px[x, y]) > tol:
                min_x = min(min_x, x); min_y = min(min_y, y)
                max_x = max(max_x, x); max_y = max(max_y, y)
    pad = 8
    return img.crop((max(0, min_x - pad), max(0, min_y - pad),
                     min(w, max_x + pad), min(h, max_y + pad)))
```

## Visual-center alignment for asymmetric assets

Bounding-box centering looks wrong when one asset has asymmetric bright content (e.g. wordmark with an off-center glyph). Center on **visual** center of mass instead.

```python
def find_visual_center_x(img_rgba, brightness_tol=40):
    img = img_rgba.convert("RGB")
    px = img.load()
    w, h = img.size
    total_x = total_w = 0.0
    for y in range(h):
        for x in range(w):
            v = max(px[x, y])
            if v > brightness_tol:
                weight = v - brightness_tol
                total_x += x * weight
                total_w += weight
    return total_x / total_w if total_w > 0 else w / 2

# Then place asset so its visual_center_x lands on canvas center_x:
emb_x = int(canvas_cx - find_visual_center_x(emblem))
```

The [brand] vertical lockup needed this — bounding-box centering put the emblem slightly right of the wordmark's optical center.

## Horizontal lockup recipe

Emblem on left, wordmark on right, emblem ~1.6× wordmark height.

```python
target_emblem_h = int(wordmark.height * 1.6)
scale = target_emblem_h / emblem.height
emblem_h = emblem.resize((int(emblem.width * scale), target_emblem_h), Image.LANCZOS)

gap = int(emblem_h.height * 0.10)
side_pad = int(emblem_h.height * 0.20)
top_pad = int(emblem_h.height * 0.20)
canvas_w = emblem_h.width + gap + wordmark.width + 2 * side_pad
canvas_h = max(emblem_h.height, wordmark.height) + 2 * top_pad

horizontal = Image.new("RGBA", (canvas_w, canvas_h), BG)
horizontal.paste(emblem_h, (side_pad, (canvas_h - emblem_h.height) // 2))
horizontal.paste(wordmark, (side_pad + emblem_h.width + gap,
                             (canvas_h - wordmark.height) // 2))
```

## Cover-fit background to target dimensions

Standard "cover" CSS behavior — scale to fill, crop overflow, center.

```python
def cover_fit(img, size):
    bw, bh = img.size
    tw, th = size
    scale = max(tw / bw, th / bh)
    nb = img.resize((int(bw * scale), int(bh * scale)), Image.LANCZOS)
    left = (nb.width - tw) // 2
    top = (nb.height - th) // 2
    return nb.crop((left, top, left + tw, top + th))
```

## Darken background for foreground contrast

When pasting bright logo/text on a busy AI background, add a semi-transparent dark overlay so the foreground reads.

```python
def darken(img, factor=0.45):
    """factor=0..1, lower = darker."""
    overlay = Image.new("RGBA", img.size, (18, 18, 18, int(255 * (1 - factor))))
    return Image.alpha_composite(img, overlay)
```

## Centered text on canvas with brand font

```python
from PIL import ImageDraw, ImageFont

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"

def draw_text_centered(canvas, text, font, fill, y):
    draw = ImageDraw.Draw(canvas)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((canvas.width - tw) // 2 - bbox[0], y - bbox[1]),
              text, font=font, fill=fill)
```

## Favicon: detect icon from full emblem

When the user wants the icon alone (without surrounding elements), don't trust automatic bounding-box detection — surrounding elements bleed into the corners. Detect the icon row-by-row from the visual center outward, stopping at the first dark gap. Or just ask the user to manually crop, then run fragment cleanup:

```python
# Bottom 15% strip, outside the center 30-70% horizontal band → paint over
bottom = int(h * 0.85)
center_l, center_r = int(w * 0.28), int(w * 0.72)
for y in range(bottom, h):
    for x in range(w):
        if center_l <= x <= center_r:
            continue  # skip teeth zone
        if max(px[x, y]) > 35:
            px[x, y] = BG
```

## Multi-size ICO for browser favicons

```python
img.resize((256, 256), Image.LANCZOS).save(
    "favicon.ico",
    sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]
)
```

## Banner sizes cheat sheet

| Platform | Dimensions |
|----------|-----------|
| X / Twitter header | 1500 × 500 |
| YouTube channel art | 2560 × 1440 (mobile safe zone 1546 × 423 centered) |
| Facebook page cover | 820 × 312 |
| LinkedIn company banner | 1128 × 191 |
| Instagram grid square | 1080 × 1080 |
| Instagram story / reel | 1080 × 1920 |
| YouTube end screen | 1920 × 1080 |
| GitHub social preview | 1280 × 640 |
| Discord server banner | 960 × 540 |
| Shopify hero (most themes) | 1920 × 1080 |
