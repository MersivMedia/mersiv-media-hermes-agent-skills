---
name: notebooklm-brand-edit
description: Re-brand NotebookLM-generated videos with [brand] identity. Detects scene cuts, recolors light-themed scenes to brand dark palette (PIL for simple, gpt-image-2 for complex), strips NotebookLM logo from bottom-right corner throughout, removes their full-screen end cards, overlays [brand] wordmark, and bookends the content with the brand intro/outro video (same file at front and end).
---

# NotebookLM → [brand] Video Re-Brand

Take a raw NotebookLM video, strip Google branding, recolor to the [brand] dark palette, add our wordmark watermark, and bookend it with our brand intro/outro (the same bumper plays at the start AND the end). Output stays at source resolution + frame rate.

## When to use this

- User provides a NotebookLM video (MP4, usually 1280×720 @ 24fps) from a [brand] topic folder
- They want it published as a [brand] asset (YouTube, X, IG Reels)

## Required inputs

1. Source MP4 (Drive ID or local path)
2. Brand assets (already in Drive `brand/` folder):
   - `brand-lockup-horizontal-transparent.png` — watermark
   - `brand-intro-outro.mp4` — appended at end (intro/outro)
3. Tools: `ffmpeg`, `ffprobe`, Python 3 + PIL, `replicate` API token in env

> ⚠ **PIL note** — Hermes' system Python doesn't have PIL. Run the pipeline through the project's local venv:
> `/tmp/hermes/venv/bin/python3 SCRIPT` (or whichever venv has Pillow installed).
> Bootstrap if missing: `python3 -m venv /tmp/hermes/venv && /tmp/hermes/venv/bin/pip install Pillow numpy scipy`.
> `numpy + scipy` are needed by `scripts/surgical_text_swap.py` (connected-component glyph erase).

## Brand palette (use exact hex)

- [brand background color] (default #121212) — backgrounds
- [brand text color] (default #F0F0F0) — primary text
- [brand accent color] (default #FFC107) — accents, highlights
- [brand emphasis color] (default #E53935) — emphasis (rare)
- [brand secondary color] (default #26A69A) — secondary accent
- [brand muted color] (default #6B7280) — body text on dark

## Process

### Step 1: Download + probe
```bash
ffprobe -v error -show_format -show_streams INPUT.mp4
```
Capture: duration, width, height, fps. NotebookLM defaults: 1280×720 @ 24fps.

### Step 2: Detect scene cuts
```bash
ffmpeg -i INPUT.mp4 -filter:v "select='gt(scene,0.25)',showinfo" \
  -vsync vfr -f null - 2>&1 | grep showinfo | grep -oE "pts_time:[0-9.]+"
```
Threshold 0.25 catches NotebookLM's slide transitions cleanly. Scenes = [0, t1, t2, ..., duration].

### Step 3: Extract one frame per scene
For each scene midpoint, dump a PNG to `scenes/scene-NN.png`. Use scene midpoint (not start) to avoid transition blur.

### Step 4: Classify each scene
For each scene image, decide light vs dark:
```python
# Brightness check: mean of all pixels' max(r,g,b)
img = Image.open(path).convert("RGB")
pixels = list(img.getdata())
brightness = sum(max(r,g,b) for r,g,b in pixels) / len(pixels)
is_light = brightness > 140  # NotebookLM's white-ish bg lands ~200+
```

Also classify complexity (decides PIL vs GPT):
- **Text-heavy / simple** = mostly 1-2 colors, large flat regions → PIL recolor
- **Illustration / chart / map** = many distinct colored shapes → GPT-image-2

Heuristic: count unique quantized colors. <50 = text-heavy, >150 = illustration.

### Step 5a: PIL recolor (text-heavy scenes)
```python
# Map: light bg → brand dark; coral/pink accents → [brand accent color]; gray text → [brand text color]
# Use np.where on RGB channels with thresholds.
```
See `scripts/recolor_text_scene.py` for the implementation.

### Step 5b: GPT-image-2 recolor (illustration scenes)
Send each frame to gpt-image-2 with `input_images=[frame]` and prompt:
```
Recolor this image to match the [brand] brand palette while keeping ALL
text, layout, charts, illustrations, and composition EXACTLY THE SAME. Only
change colors. Convert the light/white background to [brand background color] (default #121212).
Convert dark gray text and elements to [brand text color] (default #F0F0F0). Convert
coral/pink/red accent colors to [brand accent color] (default #FFC107). Convert any blue accents
to [brand secondary color] (default #26A69A). Preserve every word of text exactly as written, every
line of every chart, every illustration detail. Output a dark-themed version
of the same slide with identical information.
```
Aspect ratio: `3:2` if source is 16:9 (closest gpt-image-2 supports), then we'll re-crop to original dimensions in PIL.

### Step 6: Strip NotebookLM branding
- **Bottom-right corner badge** (present on EVERY scene): NotebookLM puts a small `◌ NotebookLM` badge at roughly x=1140-1270, y=680-715 on a 1280×720 frame. Cover with a solid `#121212` rectangle, then overlay our wordmark on top.
- **Full-screen NotebookLM end cards**: detected as scenes where mean brightness suddenly jumps and dominant color is white/pastel near the end. Either drop these scenes entirely (preferred) or replace with a solid brand-black frame for their original duration.

Detection for end cards:
```python
# Last few scenes: if scene has high white % AND contains NotebookLM-style logo
# (square pill-shaped accent), flag for removal
```
Simpler check: any scene in the last 10 seconds with brightness >180 → flag as NotebookLM end card, drop.

### Step 7: Overlay [brand] wordmark
Position bottom-right, sized so wordmark height = ~10% of video height, with 2% margin from right and bottom edges.
```bash
ffmpeg -i INPUT.mp4 -i wordmark.png -filter_complex \
  "[1:v]scale=-1:ih*0.10[wm];[0:v][wm]overlay=W-w-W*0.02:H-h-H*0.02" \
  -c:a copy OUT.mp4
```

### Step 8: Assemble final timeline
1. Build concat list of: [brand-intro-outro.mp4 as INTRO] + [recolored scenes (in order, original durations preserved)] + [brand-intro-outro.mp4 as OUTRO]
2. Use ffmpeg concat demuxer for clean stream-copy where possible.

The same `brand-intro-outro.mp4` is used at BOTH ends — it's a symmetric bumper that bookends the content. Encode it once (matched to source FPS/dimensions) and reference it twice in the concat list.

```bash
# concat.txt
file 'brand-intro-outro-matched.mp4'   # intro (front)
file 'recolored-scene-01.mp4'
file 'recolored-scene-02.mp4'
...
file 'brand-intro-outro-matched.mp4'   # outro (end)

ffmpeg -f concat -safe 0 -i concat.txt -c copy OUTPUT.mp4
```

If codecs/resolutions don't match between recolored scenes and intro/outro, re-encode the intro/outro to match source first:
```bash
ffmpeg -i brand-intro-outro.mp4 -vf "scale=SOURCE_W:SOURCE_H" \
  -r SOURCE_FPS -c:v libx264 -pix_fmt yuv420p -c:a aac intro-matched.mp4
```

### Step 9: Upload result
Same Drive parent folder as source, filename = `{original_name_without_ext}-edited.mp4`.

## Pitfalls

- **Wordmark file**: ALWAYS use `brand-lockup-horizontal.png` (solid black background). Do NOT use any `-transparent.png` or `-transparent-outlined.png` variant — those render the letterforms directly over slide artwork and become unreadable / look like typos when slide elements bleed through the negative space inside letters like "I" and "O". The solid-bg version has a black plate that keeps it legible everywhere.
- **NotebookLM uses motion** within each slide (zoom, pan on illustrations). Naive frame replacement loses this — for illustration scenes consider re-rendering only the static text overlay portions rather than the full scene if motion matters. For v1, accepted tradeoff: static recolored slides for the scene duration.
- **GPT-image-2 aspect ratios** limited to 1:1, 3:2, 2:3. For 16:9 source, generate 3:2 then crop to 16:9 — center crop loses top/bottom pixels, so account for content position.
- **Audio preserved verbatim** — never re-encode unless necessary, use `-c:a copy` end-to-end.
- **Concat demuxer resolves `file` paths relative to the LIST file's directory, NOT the process cwd.** If `concat-scenes.txt` lives at `workdir/concat-scenes.txt` and contains `file 'workdir/clip-00.mp4'`, ffmpeg tries to open `workdir/workdir/clip-00.mp4` and dies with `Impossible to open ...` + exit 254. Fix: write only basenames in the concat list when the list and the clips share a directory. Verified bug + patched in `edit_video.py` after Ep07 (May 2026 — subagent worked around it manually but the path was double-prefixed and the recolor failed at the concat step).
- **Concat demuxer** requires all segments share codec/timebase/dimensions. If recolored scenes are PNGs converted to short videos, encode them with the same codec params as source: `-c:v libx264 -pix_fmt yuv420p -r 24 -video_track_timescale 12800`.
- **Concat demuxer fails on mixed stream-copy + re-encode chains** — even when codec/timebase/dimensions match, the demuxer can throw `Invalid NAL unit size` / `h264_mp4toannexb filter failed` when one segment came from `-c copy` and the next from re-encode. For the intro/content/outro merge use the concat FILTER instead (`-filter_complex "[0:v][0:a][1:v][1:a]...concat=n=N:v=1:a=1"`). It decodes everything and re-encodes once, which is slower but immune to NAL/timestamp mismatches. The script does this for the final intro+content+outro merge.
- **Scene cut threshold 0.25** works for NotebookLM. Animated transitions (cross-fades) may need 0.15. Hard cuts can use 0.35.
- **First-slide-dropped bug**: The script builds boundaries as `[0.0] + cuts + [DUR]` and samples each scene at its midpoint. If NotebookLM crossfades from the title card to the next slide (no hard cut), `detect_scene_cuts` misses that first transition entirely. Result: "scene 00" spans 0s → first_detected_cut, but the midframe lands in the SECOND slide, and the title card is silently replaced. Verify after every edit by extracting frame at t=0.5s from source and comparing to `scene-00.png`. Fix options: (a) lower `--scene-threshold` to 0.15 and re-check, (b) manually prepend a fake cut at the title-card duration via a small patch to `boundaries`, or (c) extract the 0→first_cut segment from source as its own clip and prepend it during concat. Audio is fine either way — only the visual gets dropped.
- **Surgical late-stage fixes don't need a full re-run.** The workdir keeps every intermediate: `scene-NN.png` (raw), `recolored-NN.png` (post-recolor + badge-cover), `clip-NN.mp4` (per-scene video). For typo fixes, missing slides, or single-scene edits: edit/replace the `recolored-NN.png` in place, then re-run only Steps 7→12 (make_scene_video → concat → audio mux → wordmark → outro). Don't re-detect scenes, don't re-classify, don't re-call gpt-image-2 for unchanged scenes. See `scripts/rebuild_from_recolored.py` for the cheap-iteration entry point.
- **NotebookLM end card detection** based on brightness is heuristic — manually verify the cut point on first 2-3 videos before trusting it on a batch.
- **REPLICATE_API_TOKEN** must be in env; gpt-image-2 calls cost ~$0.04 per image (high quality). Budget per video: ~$0.20-0.40 if 5-10 illustration scenes need AI recolor.
- **Aspect ratio** must be explicitly set with `-aspect W/H` and `setsar=1` on every encode/concat. ffmpeg drops DAR metadata across `concat` and `-c copy` chains, which makes some players render the video square.
- **Tweaking wordmark size / position** does NOT require re-running the AI recolor. Keep the most expensive pre-outro artifact (`content-with-audio.mp4`) cached in the workdir, then re-overlay the wordmark and re-concat the outro for the cheap iteration loop. Don't pay GPT-image-2 twice for a watermark change.
- **Never send the FULL recolored frame back through gpt-image-2 for a "change one thing" edit.** The model reframes the image (zooms, re-crops to its 3:2 output, drops decorations like wordmarks and ad-pill chips) even with strong instructions. Two viable surgical paths instead: (A) **gpt-image-2 on a CROPPED region** containing only the element to edit (recommended for decorative / stylized glyphs like torn-paper or shattered numbers — see the "Surgical post-edit fixes" section below for the exact recipe and the `surgical_slide_edit.py` script), or (B) **PIL connected-component erase + glyph redraw** via `surgical_text_swap.py` (fallback when no AI token is available, only works on clean solid-color glyphs on solid backgrounds — leaves visible artifacts on decorative glyphs).
- **Text-colored glyph erase leaves a small flat patch** of the dark constellation background where the original character sat. Acceptable trade vs. AI reframing — at video distance and ~3-5s screen time it reads as flat dark. If a still frame is needed for thumbnails, manually inpaint the patch in an image editor.
- **Intro/outro audio MUST fade** — the source `brand-intro-outro-v4.mp4` ends abruptly at its tail with no built-in fade, so a raw concat creates a hard cut directly from music-at-full-volume into content narration (and vice versa at the end). The user hears this as music "continuing into" the content. The pipeline applies 0.5s `afade=out` to the intro at `(duration - 0.5)s` and 0.5s `afade=in` to the outro at `0s` via `reencode_to_match(..., audio_fade=("out"|"in", start, 0.5))`. Don't remove these fades unless the bumper source itself is re-mastered with proper tails. If the user reports "music bleeding into content", verify the fades fired — `ffprobe -af astats` the intro segment of the output and confirm RMS drops to silence at the boundary.
- **Never run two `edit_video.py` invocations against the same `--workdir` in parallel.** Both write `recolored-NN.png` / `clip-NN.mp4` / `content-with-wordmark.mp4` / the final output to the same paths. The result is corrupted MP4s (no moov atom) and silently mixed-source frames. If a background job seems to hang, check `pgrep -af edit_video.py` BEFORE restarting — background completion notifications can fire on the parent shell while a grandchild ffmpeg is still writing. Either wait properly, or kill the stale grandchild explicitly before launching the retry. Same rule for the surgical-fix rebuild script — give each rebuild attempt its own output path until you've confirmed the previous attempt is fully dead.
- **`-vf` is silently ignored when `-filter_complex` is set.** When building the final concat with the concat filter, do not mix the two — put `setsar=1` INSIDE the filtergraph (`[0:v:0]setsar=1[v0]; ...`) rather than as a separate `-vf` flag. ffmpeg will exit with non-zero status when both are present.
- **`scripts/edit_video.py` concat-path bug (still present as of May 2026 — recover, don't re-run).** The script writes `recolor-work/concat-scenes.txt` with entries like `file 'recolor-work/clip-NN.mp4'`, then invokes ffmpeg on it from the parent episode directory. ffmpeg resolves the paths as `recolor-work/recolor-work/clip-NN.mp4` and fails with `Impossible to open ...`. By that point ALL the per-scene `clip-NN.mp4` assets AND any gpt-image-2 recolors have already completed — DO NOT re-run `edit_video.py`, you'll burn the recolor spend again. Recovery (verified Ep07 SpaceX Valuation Tender):
  ```bash
  cd episodes/{slug}/recolor-work
  ls clip-*.mp4 | sort | awk '{print "file \047"$0"\047"}' > concat-fixed.txt
  ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i concat-fixed.txt -c copy silent-recolored.mp4
  cd ..
  ffmpeg -hide_banner -loglevel error -y -i recolor-work/silent-recolored.mp4 \
    -i source-audio.mp3 -c:v copy -c:a aac -shortest recolored-video.mp4
  ```
  Proper fix (not yet landed): patch `scripts/edit_video.py` to either (a) `chdir` into `recolor-work/` before invoking ffmpeg on `concat-scenes.txt`, or (b) write absolute paths into `concat-scenes.txt`. Until that fix ships, the recovery snippet above is the standard play.
- **Wordmark vertical position**: overlay at `H-h-H*0.02` (2% bottom margin), NOT `H-h-H*0.02-25`. The `-25px` lift the original pipeline had pushed the wordmark off the bottom edge into the content area on some slides. The 2% formula alone keeps it bottom-anchored across all resolutions.

## Surgical post-edit fixes (typos, renumbering, single-slide tweaks)

After the full pipeline runs, the user often wants to fix one or two elements (typo in a title, renumber a chapter slide, change a single value). Two approaches, with very different reliability:

### Option A — gpt-image-2 on cropped region (RECOMMENDED)

Send only a NARROW left/right/top region around the element to be edited. The model can't reframe what it can't see, and the rest of the slide stays untouched after compositing.

```bash
/tmp/hermes/venv/bin/python3 ~/.hermes/skills/creative/notebooklm-brand-edit/scripts/surgical_slide_edit.py \
  WORKDIR/recolored-13.png WORKDIR/recolored-13-fixed.png \
  --crop "0,0,380,720" \
  --aspect "2:3" \
  --prompt "Change the large stylized chapter number '5' on the left to '4'. Use the EXACT same font, color, size, position, and visual style (including any torn-paper, shattered, or decorative effects). Keep the background, decorative elements, ticker text, borders, illustrations EXACTLY the same. The ONLY change is the digit 5→4."
```

Pick a crop that:
- Contains the element to edit + some context (so the model knows what it's looking at)
- Stops BEFORE the content card or any other layout element that must not change
- Has an aspect ratio close to one of gpt-image-2's supported ones (1:1, 3:2, 2:3) — a 380x720 left strip is ≈2:3

The script crops, sends to gpt-image-2 with `quality=high`, resizes the result back to the crop dimensions, and pastes back into the original PNG. Cost: ≈$0.04 per edit. Total preservation of everything outside the crop.

### Option B — PIL erase + redraw (FALLBACK, FRAGILE)

Find the digit's bounding box via connected-component analysis, dilate to absorb anti-aliasing, paint the dilated region with brand BG, render the new digit in PIL.

Pitfalls:
- Fails on "torn paper" / shattered / decorative number styles where the digit isn't a solid text-colored shape (the connected-component finder gets a partial mask, the erase leaves halos, the new flat digit clashes against leftover stylization fragments)
- Font selection has to be hand-picked; available system fonts (LiberationSans, DejaVuSans) don't always match the NotebookLM slab-serif
- Only works for clean solid-color digits on solid backgrounds

When Option A is available (Replicate token set), always prefer it. Reserve Option B for offline/no-AI runs.

### Rebuilding the video after surgical fixes

The workdir keeps every intermediate. After replacing `recolored-NN.png` files, only re-run Steps 7-12:

```bash
# For each fixed scene N:
ffmpeg -loop 1 -i WORKDIR/recolored-NN-fixed.png -t DURATION -r FPS \
  -vf "scale=W:H,setsar=1" -aspect W/H \
  -c:v libx264 -pix_fmt yuv420p -preset fast -tune stillimage -an \
  WORKDIR/clip-NN.mp4

# Then concat all clips, mux audio, overlay wordmark, and final concat with intro+outro.
# See scripts/edit_video.py Steps 7-12 for the exact ffmpeg commands.
```

Don't re-run scene detection, classification, or gpt-image-2 for unchanged scenes. Total time for a single-scene fix: ~30s.

## Verification

After edit, manually check:
1. No NotebookLM logo visible at any timestamp
2. Wordmark visible bottom-right throughout content
3. Brand outro plays cleanly at end
4. Audio in sync, no glitches at scene transitions
5. No light-themed frames remain

## Files

- `scripts/edit_video.py` — main pipeline (probe → cuts → classify → recolor → strip → overlay → concat)
- `scripts/surgical_slide_edit.py` — **PRIMARY** surgical-fix tool: crops a region of a recolored slide, sends ONLY that region to gpt-image-2 with a scoped prompt, pastes the result back. Use for typo fixes, chapter-number changes, single-element tweaks. Works on decorative/stylized glyphs that `surgical_text_swap.py` can't handle.
- `scripts/rebuild_from_recolored.py` — cheap-iteration rebuild from cached `recolored-NN.png` frames (typo fixes, missing-slide insertion via `--insert-at`, no AI re-calls)
- `scripts/surgical_text_swap.py` — FALLBACK surgical-fix tool (no-AI). PIL connected-components erase + glyph redraw. Only works for clean solid-color glyphs on solid backgrounds.
- `scripts/recolor_text_scene.py` — PIL-only recolor for text-heavy scenes
- `scripts/recolor_illustration.py` — gpt-image-2 recolor for complex scenes
- `references/brand-palette.md` — exact hex codes + usage notes
