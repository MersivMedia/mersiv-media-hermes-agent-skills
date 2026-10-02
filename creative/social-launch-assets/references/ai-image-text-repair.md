# Repairing text in AI-generated infographics

Image models (FLUX 2 Klein via FAL here) get big display text right but
misspell small labels. On the Jermes infographic, 9 of 10 strings were
correct; "context trimming" came back "context trimining". Repair in post
instead of re-rolling: each re-roll changes the whole composition.

## Replace a label

```python
from PIL import Image, ImageDraw, ImageFont
import numpy as np
im = Image.open("raw.png").convert("RGB"); A = np.asarray(im).astype(int)

def ink(x0, x1, y0, y1, thr=360):          # bright-text bounding box + density
    b = A[y0:y1, x0:x1].sum(axis=2) > thr
    ys = np.where(b.any(1))[0]; xs = np.where(b.any(0))[0]
    return xs.min()+x0, xs.max()+x0, ys.min()+y0, ys.max()+y0, \
           b[ys.min():ys.max()+1, xs.min():xs.max()+1].mean()

# 1. Measure a correctly spelled neighbour with the same letter count/shape
#    (ascender+descender both present, e.g. "duplicate skills").
rx0, rx1, ry0, ry1, rd = ink(440, 720, 1515, 1590)
# 2. Paint the bad label with the card's median non-text colour.
ImageDraw.Draw(im).rectangle([112, 1515, 364, 1590], fill=(14, 15, 22))
# 3. Render the text on an L mask, crop to ink, pick the font size whose ink
#    height equals the neighbour's, then resize horizontally to a width close
#    to the neighbour's (<= ~15% squeeze or it reads as compressed).
f = ImageFont.truetype("~/.fonts/Inter-Regular.ttf".replace("~", str(__import__("pathlib").Path.home())), 44)
L = Image.new("L", (600, 120)); ImageDraw.Draw(L).text((10, 10), "context trimming", font=f, fill=255)
L = L.crop(L.getbbox()).resize((256, ry1 - ry0 + 1), Image.LANCZOS)
# 4. Composite centred on the card, top aligned to the neighbour's ink top.
im.paste(Image.new("RGB", L.size, (238, 243, 239)), (238 - L.size[0] // 2, ry0), L)
```

Check the result by cropping the card row and inspecting it with vision
next to its neighbours (size, weight, baseline). Tell the user a label was
hand-repaired.

## 9:16 → 4:5 without visible letterbox bars

A flat dark pad shows because the generated panel is lighter than the pad.
What worked:

1. Scale the image to full height (1350); it spans ~70% of the width.
2. Build a background field: the median colour of the outer ~30px of each
   row, smoothed vertically (moving average, k≈61), repeated across 1080px.
3. Feather the image's left and right edges into the field over ~70px
   (smoothstep alpha).
4. Apply a light horizontal vignette (`1 - 0.18*((x-540)/540)**2`).

Keep the untouched 9:16 original for Stories.
