# Validating generative output (talking-heads, slides, verticals)

When you change a generative prompt in this pipeline — `video_prompt` for p-video-avatar, the vertical-reformat prompt in notebooklm-pdf-slideshow, any future image/video prompt — DO NOT trust solo-frame vision to tell you whether the change worked.

## The failure mode

Vision models, when shown a single frame or grid from generative output, compare against a physical-sim ideal. They will say things like "the logo still looks too flat" or "the camera still doesn't move with the head" *even when the new generation is meaningfully better than the old one*. The model is comparing to "a real embroidered patch on real wool" — not to "the previous version of the same generation".

This bit us on Ep1 th5 (May 2026): after fixing the floating-logo artifact with embroidery prompt language, solo-frame vision insisted the logo was "still frontal-locked" and "still pasted on rather than integrated." A direct OLD-vs-NEW grid in the same call immediately reported "clear improvement, flatter, conforming to hat curvature."

## The fix: always run a labeled A/B grid

Three steps, scriptable per validation:

### 1. Extract frames from both versions at the same density

```bash
mkdir -p _ab-debug && cd _ab-debug
# OLD version
ffmpeg -y -i ../old.mp4 -vf "fps=8,crop=in_w:in_h*0.45:0:0" old_%03d.png -loglevel error
# NEW version
ffmpeg -y -i ../new.mp4 -vf "fps=8,crop=in_w:in_h*0.45:0:0" new_%03d.png -loglevel error
```

The `crop=in_w:in_h*0.45:0:0` is for hat/head artifacts on the talking-head clips. Adjust the crop to whatever region of the frame the artifact lives in (logo, hands, background, etc.). Don't grid the whole frame — you'll lose the detail vision needs.

### 2. Build a labeled side-by-side grid (PIL)

```python
from PIL import Image, ImageDraw
import glob

old = sorted(glob.glob('old_*.png'))
new = sorted(glob.glob('new_*.png'))
n = 8  # 8 frames per row is usually right; bump to 16 for longer clips
op = [old[int(i*len(old)/n)] for i in range(n)]
np_ = [new[int(i*len(new)/n)] for i in range(n)]

oi = [Image.open(f) for f in op]
ni = [Image.open(f) for f in np_]
w, h = oi[0].size

grid = Image.new('RGB', (w*n, h*2 + 40), 'white')
d = ImageDraw.Draw(grid)
for i, im in enumerate(oi): grid.paste(im, (i*w, 20))
for i, im in enumerate(ni): grid.paste(im, (i*w, h + 40))
d.text((10, 0),       "OLD (previous prompt)", fill='red')
d.text((10, h + 22),  "NEW (current prompt)",  fill='green')
grid.thumbnail((2000, 2000))
grid.save('ab-compare.png')
```

The text labels are non-negotiable. Without them, vision sometimes flips which row it thinks is which, or hedges.

### 3. Ask vision a COMPARATIVE question

```
browser_navigate file:///.../ab-compare.png
browser_vision "Top row labeled OLD shows the prior version of <ARTIFACT>.
Bottom row labeled NEW shows the regenerated version with <CHANGE>.
COMPARE the two rows: is <ARTIFACT> better/same/worse in NEW vs OLD?
Be specific about what differs between top and bottom."
```

Comparative phrasing is also non-negotiable. "Is the logo flat now?" → false negative. "Is the logo flatter in NEW than OLD?" → reliable signal.

## What this validates well

- Hat-logo embroidery vs floating decal
- Locked camera vs zoom/pan/push-in drift
- Lip-sync intensity changes
- Color palette adherence on the vertical-slide reformat (compare horizontal source row vs vertical-output row, cropped to header strip)
- Any "did the model actually respond to the prompt edit" check

## What this does NOT validate

- Whether the generation is "good" in absolute terms — that's a human call
- Whether the change is the BEST possible fix — only that it's *directionally better*
- Numerical chart accuracy (vision will hallucinate numbers; check those visually yourself)

## Drop-in checklist

Before mass-regenerating a batch after changing a prompt:
1. Generate ONE test clip with the new prompt
2. Build the A/B grid
3. Get vision's comparative verdict
4. If "clear improvement" → proceed with the batch
5. If "same" or "worse" → iterate on the prompt, re-test, don't burn the batch budget

Cost guard: this avoids spending $0.50-$3 regenerating a batch only to find the prompt didn't move the needle.
