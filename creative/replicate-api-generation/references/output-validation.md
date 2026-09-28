# Validating Generative Outputs: The A/B Vision-Grid Pattern

When you fix a prompt and regenerate, you need to verify the artifact is actually gone. Asking a vision model "is this artifact present?" on a single grid does NOT work reliably — it compares the output to a perfect physical-sim ideal and reports "still wrong" even after meaningful improvements. The only reliable validation is a labeled OLD vs NEW side-by-side comparison.

Applies to any generative output where you iterate on a prompt and need to confirm the fix landed: video frames, images, audio waveforms, design comps, animated logos.

## When to reach for this

- You changed a `video_prompt`, `prompt`, or `negative_prompt` to remove a visual artifact
- The artifact is subtle (a logo that "feels floaty", a camera that "jitters", a face that "drifts")
- You don't trust your own eyes after staring at the same character for an hour
- You don't want to burn another generation pass on a fix that didn't actually work

## When NOT to use this

- The artifact is obvious on a still frame (extra fingers, missing object, wrong color) — just look
- You only have the NEW output and no OLD reference — solo vision is fine for spot-checks, just don't ask comparative questions
- The change is structural (different aspect ratio, different subject) — A/B doesn't apply

## The recipe

### 1. Sample frames densely during motion peaks

If the artifact only appears during head turns, fast hand gestures, or transitions, low-fps sampling will miss it. Crop to the region of interest at the same time:

```bash
# 8 fps, crop top 45% of frame (e.g. hat region)
ffmpeg -y -i clip.mp4 -vf "fps=8,crop=in_w:in_h*0.45:0:0" frame_%03d.png -loglevel error
```

For full-frame inspection, drop the crop. For audio, render a spectrogram or waveform PNG instead of frames.

### 2. Pick evenly-spaced frames from each clip

8 from OLD, 8 from NEW. Evenly spaced beats random — the artifact has temporal structure you want to see across the runtime.

```python
import glob
frames = sorted(glob.glob('frame_*.png'))
picks = [frames[int(i*len(frames)/8)] for i in range(8)]
```

### 3. Build a labeled grid: OLD on top, NEW on bottom

Two-row layout with text labels. Vision models reliably anchor on labeled regions when you explicitly tell them which row is which.

```python
from PIL import Image, ImageDraw
old_imgs = [Image.open(f) for f in old_picks]
new_imgs = [Image.open(f) for f in new_picks]
w, h = old_imgs[0].size
n = len(old_imgs)

grid = Image.new('RGB', (w*n, h*2 + 40), 'white')
d = ImageDraw.Draw(grid)
for i, im in enumerate(old_imgs):
    grid.paste(im, (i*w, 20))
for i, im in enumerate(new_imgs):
    grid.paste(im, (i*w, h + 40))
d.text((10, 0), "OLD (original)", fill='red')
d.text((10, h + 22), "NEW (after fix)", fill='green')
grid.thumbnail((2000, 2000))
grid.save('ab-compare.png')
```

### 4. Open the grid and ask a COMPARATIVE question

Navigate the browser to the file (`file://...`), then call `browser_vision` with a comparative question, not a binary one.

**Good prompts (comparative):**
- "Top row labeled OLD vs bottom row labeled NEW. Compare the [artifact area]: is it more [desired property] in the NEW row than the OLD row? Be specific about what differs."
- "Does the [thing] appear more integrated/flatter/better attached in the NEW row than the OLD row, or does it look the same, or worse?"

**Bad prompts (binary):**
- "Is the artifact present?" → model says yes for both, comparing to a physical-sim ideal
- "Does the logo float?" → model says yes for both, because the underlying pose image always had a frontal-locked logo
- "Is this fixed?" → vague, model hedges

The comparative phrasing forces the model to anchor judgments to the actual OLD reference instead of an imagined ideal.

### 5. Trust the verdict, ship or iterate

If the model says NEW is clearly better, ship. If it says they look the same, your prompt change probably didn't land — re-read the diff and try a stronger or more specific clause. If it says NEW is worse, revert.

## Why solo-frame vision fails

The vision model has no idea what the "correct" version is supposed to look like. So it compares the artifact to its internal model of how the thing should physically behave: real embroidery has thread shadow, real camera tripods don't drift at all, real lip-sync has perfect phoneme alignment. Almost no generative output meets this bar perfectly, so the model says "still wrong" even when you've moved meaningfully closer to acceptable.

A labeled OLD-vs-NEW comparison gives the model a concrete reference point: NEW only needs to be better than OLD, not perfect.

## Pitfalls

- **Crop matches must be IDENTICAL between OLD and NEW.** Same `crop` filter, same fps, same frame count, same grid cell size. If the NEW row is zoomed in tighter than OLD, the vision model will conflate "better visible" with "actually improved" — flag this in your prompt or fix the crop.
- **Use crisp labels.** PIL's default font is small but readable. If labels are illegible, the model can't tell which row is which and the comparison collapses.
- **Don't ask multi-part questions.** "Is the logo flatter AND does the camera move less AND does the face look more natural?" — pick ONE artifact per A/B grid. Run another grid for the next artifact.
- **Browser vision needs the file actually loaded.** `browser_navigate('file:///path')` first, THEN `browser_vision`. The model can't analyze what's not in the browser window.
- **For audio artifacts, render to PNG first.** Vision models don't ingest WAV/MP3. Use librosa or matplotlib to render a spectrogram or waveform comparison, then A/B grid the PNGs.

## Real-world calibration

This pattern was discovered during [brand] Ep1 regen (May 2026). Solo-frame vision insisted the hat logo was still "frontally locked and floating" on the FIXED clip. The A/B grid immediately surfaced the actual improvement: flatter, embroidered, conforming to hat curvature. Saved a wasted regeneration pass.
