---
name: notebooklm-pdf-slideshow
description: Convert a NotebookLM-exported slideshow PDF into a numbered set of horizontal JPG slides plus AI-generated 2:3 vertical alternates for Reels/Shorts/TikTok. Use when the user hands you a slideshow PDF (typically a NotebookLM output sitting in a [brand] topic folder) and wants it split into per-slide images with vertical social-format counterparts.
version: 1.0.0
author: B3Fr33
license: MIT
metadata:
  hermes:
    tags: [pdf, slideshow, image-generation, brand, social-media]
    related_skills: [replicate-api-generation, google-workspace, notebooklm-brand-edit]
---

# NotebookLM PDF → Slideshow + Vertical Alternates

Turn a slideshow PDF into:
- Numbered horizontal JPGs (`slide-01.jpg`, `slide-02.jpg`, ...) at 1920×1080-ish (rendered from the PDF directly, no AI)
- Numbered vertical 2:3 JPGs (`slide-01-vertical.jpg`, ...) generated via gpt-image-2 image-to-image from each horizontal source

The vertical alternates are designed for Instagram Reels, TikTok, YouTube Shorts, and IG posts where the content needs to be reflowed into a 2:3 (1024×1536) frame in the [brand] brand style.

## When to use

- User uploads a slideshow PDF to a [brand] topic folder on Drive
- User wants "vertical versions for Reels/Shorts" of an existing slide deck
- The deck is roughly 16:9 (NotebookLM standard) and 5-30 pages

## Drive folder convention

Each topic folder gets a `slideshow/` subfolder (sibling to `research/`):

```
<Parent Blogs folder>/
  └── <NN - Topic — Pillar>/
      ├── research/                   # sources.txt, prompt.txt, videoprompt.txt
      └── slideshow/                  # PDF + per-slide JPGs (horizontal + vertical)
          ├── Example_Episode.pdf
          ├── slide-01.jpg
          ├── slide-01-vertical.jpg
          ├── slide-02.jpg
          ├── slide-02-vertical.jpg
          └── ...
```

## Persistent local working directory

```
~/.hermes/data/notebooklm-pdf-slideshow/<topic-slug>/slideshow/
```

Same files mirror locally so re-runs and partial-rerun debugging work without re-downloading the PDF. Override via `BRAND_SLIDESHOW_ROOT` env var.

## Preconditions

```bash
# Google Workspace (Drive) auth
GSETUP="python ${HERMES_HOME:-$HOME/.hermes}/skills/productivity/google-workspace/scripts/setup.py"
$GSETUP --check     # AUTHENTICATED

# Replicate (for gpt-image-2 vertical generation)
echo "$REPLICATE_API_TOKEN" | head -c 8       # should print a key prefix

# Python deps in venv
/tmp/hermes/venv/bin/pip install pymupdf pillow ddgs   # ddgs only needed if used elsewhere
```

## Workflow (one PDF)

The runner `scripts/build_slideshow.py` automates everything:

1. **Inputs:** Drive file ID of the PDF + a topic slug (e.g. `01-pure-play-space-stocks`) OR the topic folder's Drive ID
2. **Create slideshow/ subfolder** under the topic folder if missing
3. **Move the PDF** into slideshow/ if it isn't already there (uses Drive `files.update` with `addParents`/`removeParents`)
4. **Download** the PDF to `~/.hermes/data/notebooklm-pdf-slideshow/<slug>/slideshow/`
5. **Render each page** to `slide-NN.jpg` at 2× zoom (≈2560×1440 for 16:9 PDFs) using PyMuPDF + PIL
6. **For each slide**, send to gpt-image-2 as `input_images` with the vertical-reformat prompt → save `slide-NN-vertical.jpg` (1024×1536)
7. **Upload** all generated JPGs back to the Drive `slideshow/` folder (idempotent — deletes any prior `slide-*.jpg` first)

## Prompt template (vertical reformat)

```
Reformat this 16:9 slide into a 2:3 vertical poster suitable for Instagram Reels and TikTok.
Keep ALL content from the original — every headline, every bullet, every number, every chart.
Reflow the layout so it reads top-to-bottom instead of left-to-right.
Maintain the [brand] brand:
- Background: [brand background color] (default #121212) with subtle parchment-paper texture overlay
- Headlines: [brand accent color] (default #FFC107), slab-serif (Rockwell / Roboto Slab / Arvo)
- Body: [brand text color] (default #F0F0F0), clean sans-serif
- Accents: [brand secondary color] (default #26A69A) for positive/up data, [brand emphasis color] (default #E53935) for warnings/down data
- Numbers: tabular monospace
- Subtle gold rule lines, slight film grain, weathered ship's-log meets terminal-screen mood
- NO mascot inserts, NO logos in the body — the wordmark goes on later in post

If the original has a chart, redraw it cleanly in the brand palette (gold/teal up, red down), tall orientation.
If the original has a comparison table, stack rows vertically with clear hierarchy.
Do NOT add new content. Do NOT change the data values. Do NOT use stock photos.
Output: single image, 1024×1536, no margins, full-bleed.
```

## Cost (rough)

- Horizontal slides: free (local PyMuPDF rendering)
- Vertical alternates: gpt-image-2 medium quality ≈ **$0.05 per slide**
- A 15-slide deck ≈ **$0.75**. High quality (`quality="high"`) ≈ $2.55 per deck — only use if a slide turns out grainy and the user asks for a re-do.

## Calling the runner

```bash
/tmp/hermes/venv/bin/python3 ~/.hermes/skills/creative/notebooklm-pdf-slideshow/scripts/build_slideshow.py \
  --pdf-id <DRIVE_FILE_ID> \
  --topic-slug 01-pure-play-space-stocks \
  --topic-folder-id <DRIVE_FOLDER_ID>
```

Flags:
- `--quality medium|high` — gpt-image-2 quality (default: medium)
- `--skip-vertical` — only do horizontal split (cheap dry run)
- `--vertical-only` — skip the PDF render step (use existing `slide-NN.jpg` files; useful for re-runs of just the AI step)
- `--from N` / `--to N` — only process slides N through N (1-indexed, inclusive). Useful for re-running a few bad ones.

Background it for big decks (>10 slides) — each gpt-image-2 call is 8-15 seconds:

```bash
nohup /tmp/hermes/venv/bin/python3 .../build_slideshow.py ... > /tmp/slideshow.log 2>&1 &
```

## Pitfalls

- **`python` vs `python3` on PATH** — the runner used to hardcode `["python", GAPI_SCRIPT]`, which `FileNotFoundError`s on systems where only `python3` is symlinked (the default on most fresh Ubuntu/Debian and our `/tmp/hermes/venv`). Fixed May 2026 — now uses `sys.executable` then falls back to `shutil.which("python")` / `shutil.which("python3")`. If you ever copy this pattern into another script, do the same fallback dance instead of hardcoding `python`.
- **gpt-image-2 `output_format` must be `jpeg`/`png`/`webp`** — `jpg` is rejected with HTTP 422. The schema enum is strict.
- **gpt-image-2 aspect ratio is restricted** — only `1:1`, `3:2`, `2:3`. Vertical = `2:3` (1024×1536). Not 9:16. Reels/Shorts auto-letterbox 2:3 fine.
- **gpt-image-2 sometimes drops chart precision** — for slides with critical numbers, eyeball the vertical against the horizontal. If a number changed, re-run that slide with `quality=high`.
- **gpt-image-2 content-filter rejections (E005 `flagged as sensitive`) are deterministic per-input** — slides featuring crosshair/reticle imagery, "hunt" + "plunder" + treasure-map language, weapons-adjacent visuals, or strong contrarian framing against named entities can deterministically trip the OpenAI moderation filter even when the content is clearly metaphorical financial analysis. Discovered May 2026 on Ep4 slide 3 ([brand]'s "Treasure Map Framework" slide — crosshair targeting reticles + "hunt for signals" + "plunder" language). **The runner now auto-handles this:** one retry on filter rejection (sometimes nondeterministic), then falls back to a clean PIL letterbox (1024×1536 on `#121212` [brand background color], full content preserved) and marks the slide in the `filter_fallbacks` summary at the end. The deck always completes. If you want an AI-stylized vertical for a fallback slide later, mask the trigger element in the horizontal source first (e.g. blur the crosshair) and rerun with `--from N --to N`.
- **PDF rendering quality** — 2× zoom is enough for most NotebookLM exports (they're already vector-rendered to ~1376×768 internally). Bump to 3× if you see jagged text.
- **PDF that's not 16:9** — the rendering still works but the aspect ratio of `slide-NN.jpg` will match the PDF, not 16:9. The vertical alt will still be 2:3 either way.
- **Drive `files.update` move pattern** — google_api.py CLI has no `move` verb. Use Drive API directly: `files().update(fileId=..., addParents=NEW, removeParents=OLD)`. See `scripts/build_slideshow.py::move_to_folder` for the helper.
- **Idempotent re-runs** — script deletes prior `slide-*.jpg` from the Drive folder before uploading new ones. Won't delete the PDF.
- **`pd` UnboundLocalError when `Prefer: wait=60` returns terminal status immediately** — original `replicate_predict` only defined `pd` inside the polling `while` loop. Fast predictions that came back already-terminal skipped the loop and any post-loop access to `pd.get(...)` blew up. Fixed May 2026 by seeding `pd = resp` before the loop. Pattern applies to any Replicate polling code you copy from here.
- **Don't run vision passes per slide** — earlier attempt; way more expensive and the i2i pass already sees the pixels. Just pass the original slide as `input_images` to gpt-image-2 and let it reflow.

## Verification before declaring done

- `slideshow/` folder exists on Drive under the topic folder
- PDF lives inside `slideshow/`, not the topic folder root
- N horizontal JPGs + N vertical JPGs in `slideshow/` (one of each per PDF page)
- Spot-check 2-3 verticals — content preserved, no hallucinated text, brand colors present
- **Check the runner's tail output for a `filter_fallbacks` NOTE.** If any slides hit the PIL letterbox fallback, surface them to the user explicitly — those slides are letterboxed (full content, smaller scale, solid black margins) instead of AI-reflowed, and the user may want to mask the trigger element in the horizontal and rerun `--from N --to N` for an AI-stylized vertical. AI verticals are typically 230-280KB JPEG; PIL fallback is typically 140-170KB on the same content — file-size deltas are the quick disambiguator if you didn't capture the runner output.
- Local mirror at `~/.hermes/data/notebooklm-pdf-slideshow/<slug>/slideshow/` matches
