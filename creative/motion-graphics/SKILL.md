---
name: motion-graphics
description: "Use when making motion graphics videos rendered from code."
version: 1.0.0
author: Hermes Agent (workflow from @0xMovez's "motion design studio with Opus 5.5" course)
license: MIT
platforms: [linux, macos]
prerequisites:
  commands: [node, ffmpeg, ffprobe, python3]
metadata:
  hermes:
    tags: [motion-graphics, video, animation, canvas, showreel, launch-video, ui-morph, ffmpeg, playwright]
    related_skills: [seedance-video, elevenlabs-narrator-revoice, generated-asset-verification, p5js, manim-video, social-launch-assets]
---

# Motion graphics (code-rendered video)

Covers showreels, product launch reels, animated explainers, UI morph loops and motion ads. The engine is a deterministic `seek(t)` canvas, with springs, a beat grid, synthesized audio, and a mandatory critique loop where you look at your own frames.

The model can't output an MP4. It writes a **program**: one `window.seek(t)` function that paints the exact frame for any time `t`. A headless browser calls it for every frame and ffmpeg encodes the result. Because nothing depends on timers, renders come out identical every time, and any fix is a code edit followed by a re-render.

The source course's thesis: **the prompt is 10% of the video, the harness is 90%.** One-liners give a generic clip: centered text on a gradient, everything fading in, a logo at the end. What separates good output is a reference, a state list, springs, a beat grid, and the habit of **looking at your own rendered frames and fixing them**. Full prompt templates are in `references/prompts.md`; source and repos are in `references/sources.md`.

## Files

```
templates/index.html      the film: SCENES array, window.seek(t), size from ?w=&h=, live preview in a browser
templates/lib/motion.js   spring(), SPRINGS presets, track(), indicator(), swapAlpha(), loopT(), rng(), pulse(), layout()
templates/render.mjs      headless render → ffmpeg. --stills for PNGs, --from/--to for partial re-renders, --sub N motion blur
templates/music.mjs       synthesized on-grid backing track + beats.json (no track supplied)
templates/beats.py        measure a supplied track → beats.json (needs librosa in a venv)
templates/sfx.mjs         synthesized UI SFX from cues.json (click, tick, pop, thump, whoosh, riser, chime)
templates/mix.sh          music + SFX → -14 LUFS AAC, muxed onto the silent render (video stream copied)
templates/qc.sh           contact.png, strip.png, phone.png, poster.png, loop_check.mp4, loop-seam diff
templates/formats.sh      9:16, 1:1, 16:9 from one timeline
templates/STUDIO_RULES.md house rules copied into every project (read before every change)
scripts/new_project.sh    scaffold a project from the templates
scripts/smoke_test.sh     end-to-end self-test of the whole pipeline
```

Runtime: `playwright-core` lives at `~/.hermes/data/motion-graphics/runtime` (render.mjs finds it automatically, or set `MOTION_RUNTIME`). Chrome is the cached Playwright `chromium_headless_shell`, or set `CHROME_PATH`. If the runtime is missing, run: `mkdir -p ~/.hermes/data/motion-graphics/runtime && cd $_ && npm init -y && PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm i playwright-core`.

## Workflow

**0. Plan first, before writing code.** Collect the inputs:
- product + URL, or the subject
- duration
- formats
- brand colors and fonts, one accent color
- a reference (a frame, a video, or an image folder)
- music: a file, or "synthesize"
- voice or mascot, if any

Pick the brief level (L1 one-liner → L4 director's brief, `references/prompts.md`). Write `docs/shotlist.md` on the beat grid: every shot gets its time range, what happens, the type on screen, and the SFX. **Show it to the user and wait for an OK.** Anything paid (ElevenLabs voice, Seedance base shots) gets a cost estimate before it runs.

**1. Scaffold.** `bash ~/.hermes/skills/creative/motion-graphics/scripts/new_project.sh <dir>`. Work in the user's project directory, or in `~/.hermes/data/motion-graphics/projects/<name>/`, never `/tmp`. Keep one folder per brand so later films reuse the pipeline.

**2. Assets and reference.**
- *Product URL:* capture real screenshots, logo, colors and fonts into `./assets` with Playwright (CDP), and list what you found. Never invent product UI.
- *Reference video:* `ffmpeg -i refs/x.mp4 -vf fps=2 refs/frames/%03d.png`. Look at the frames and write `docs/style_guide.md`: palette as hex, type, shot lengths, transitions, camera, texture, how text enters and leaves. Take the reference's grammar, never its content.

**3. Audio grid.**
- *No track:* `node music.mjs --bpm 120 --dur N --key A --mood bright|dark`. This writes `audio/music.wav` and `beats.json`.
- *Supplied track:* `python beats.py audio/track.wav > beats.json` in a venv with librosa. Check by ear that beat 1 lands on a real downbeat.
- Then put state changes on `beats`, big moments on `downbeats`, and SFX on `hits`.

**4. Build `index.html`.** One object per shot in `SCENES`.
- Position everything through `layout()` (`u()` units, `L.portrait/landscape`, `L.safe`) so other formats reframe instead of cropping.
- Use springs from `lib/motion.js` for all motion. Any value with several targets uses `track()`, not a restarted spring.
- Use `rng(seed)`, never `Math.random`.
- Make something new happen every 2–4 s, with a hook in the first 2.

**5. Look at stills before animating everything.** `node render.mjs --w 540 --h 960 --stills 0.5,2,4,...` (one per shot), then **open the PNGs with vision**. Fix composition before motion.

**6. Draft render plus critique loop, at least 3 rounds.**
- Render at preview size: `node render.mjs --w 540 --h 960 --fps 30 --sub 1 --out out/draft.mp4`.
- Run `bash qc.sh out/draft.mp4 <fast_action_t>`, then **look at** `contact.png`, `strip.png` and `phone.png`.
- Score 1–10 on hook, phone readability, motion, variety, composition, brand, and sound sync. Log the scores and the 3 worst problems with timestamps in `docs/review_log.md`.
- Fix them and re-render only the affected range (`--from/--to`). Repeat until every score is 8+. The critique prompt is §6 of `references/prompts.md`.

**7. Final.**
- Video: `node render.mjs --w 1080 --h 1920 --fps 60 --sub 4 --out out/silent.mp4`.
- SFX: `node sfx.mjs cues.json out/sfx.wav --dur N`.
- Mix: `bash mix.sh out/silent.mp4 out/final.mp4`. It reports the integrated loudness, which should be about -14 LUFS.
- More formats: `bash formats.sh` (sequential by default; `PARALLEL=1` only on machines with enough RAM).
- Run `qc.sh` once more on the final file.

**8. Deliver** `final.mp4`, `contact.png` and `poster.png`, plus any other formats. Give the duration, resolution, measured loudness, final review scores, and what you'd improve next. On Telegram, send with `MEDIA:/abs/path`.

## Hard rules

- **Render contract:** no CSS transitions, `setTimeout`, `requestAnimationFrame` (except the preview branch), or state carried between frames. `seek(t)` must give the same pixels whatever order it's called in. smoke_test.sh checks this by rendering the same range twice and comparing frame hashes.
- **Banned looks:** a centered title on a gradient, everything fading in, corner labels and frame borders, glow on UI chrome, generic particle bursts, bouncy easing on type.
- **Real product UI only.** Crop and animate the real thing.
- **Look before claiming done.** Never report a render as good without opening the QC images. Use the `generated-asset-verification` habits.
- **Keys:** API keys stay in `.env` and are referenced by name. Never paste them into prompts or files that get shared.
- **Brand compositing:** for [brand] episodes the user composites in CapCut, so deliver clean elements rather than auto-compositing wordmarks or outros.

## Pitfalls

- **Use HTTP, not `file://`.** ES modules and `fetch('beats.json')` fail over `file://`. render.mjs serves the folder on a local HTTP server; to preview in a browser, run `npx http-server` or `python3 -m http.server`.
- **Wait for fonts.** Canvas text needs loaded fonts: `window.ready` awaits `document.fonts.ready`. Use fonts installed locally (Inter is in `~/.fonts`) or self-host `.woff2` in `assets/` with `@font-face`. A missing font silently falls back and breaks the look.
- **Use `toBlob`, not element screenshots.** render.mjs captures canvas bytes with `toBlob`, which always matches the canvas size exactly. Element screenshots in full Chrome can lose viewport pixels.
- **Render time is CPU-bound.** Render time scales with fps × sub × duration × pixel area. On this 2-core box, a 540×960 render at 30 fps with sub 2 took about 9 s for 6 s of video. A full-HD 60 fps sub-4 final costs roughly 16× that per second of film, so draft small and finish once.
- **Avoid `will-change` and CSS scaling on text.** They make scaled text blurry. Draw text at its final pixel size on canvas.
- **Loop seam:** for loops the last frame must equal the first, cursor velocity included. qc.sh prints a first-vs-last frame difference, which should be near 0 for loops and doesn't matter for non-loops.
- **Concurrent renders need unique `--out` paths.** Two encoders writing one file corrupts the moov atom.
- **PEP 668:** install librosa in a venv (`python3 -m venv .venv && .venv/bin/pip install numpy librosa soundfile`). A global `pip install` silently does nothing here.
- **Brief contagion:** the stock one-liner gives the same reel everyone else got. Use it only to test the setup, and get the idea from a reference, a story or a product.

## Verification

`bash ~/.hermes/skills/creative/motion-graphics/scripts/smoke_test.sh ~/.hermes/data/motion-graphics/smoke` scaffolds a project and runs the whole chain:
- music, SFX, stills, a 6 s render, mix and QC
- the determinism check
- 16:9 and 1:1 reframes

It should end with `determinism: identical frames`, an integrated loudness of about -14 LUFS, and `SMOKE OK`. Last verified on this box 2026-10-02: 540×960 at 30 fps, -14.2 LUFS, identical frames.
