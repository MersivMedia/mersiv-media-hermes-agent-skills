---
name: motion-graphics
description: "Use when making motion graphics videos rendered from code."
version: 2.0.0
author: Hermes Agent (workflow from @0xMovez's course + Raphaël Aubry's claude-motion-design, MIT)
license: MIT
platforms: [linux, macos]
prerequisites:
  commands: [node, ffmpeg, ffprobe, python3]
metadata:
  hermes:
    tags: [motion-graphics, video, animation, canvas, showreel, launch-video, ui-morph, ffmpeg, playwright]
    related_skills: [motion-remake, seedance-video, elevenlabs-narrator-revoice, generated-asset-verification, p5js, manim-video, social-launch-assets]
---

# Motion graphics (code-rendered video)

## When to Use

Use this for showreels, product launch films, animated explainers, motion ads, kinetic type and looping UI morphs. It also covers "make a video like this viral one".

Other skills fit better in these cases:
- **Frame-locked 1:1 remake of an existing video:** `motion-remake`.
- **Photoreal footage or characters:** `seedance-video`.
- **Math or algorithm explainers:** `manim-video`.

## How it works

The model can't output an MP4. It writes a **program**: one `window.seek(t)` function that paints the exact frame for any time `t`. A headless browser calls it for every frame, averages subframes for motion blur, and ffmpeg encodes the result. Nothing depends on timers, so the same time always gives the same pixels. A fix is a code edit plus a re-render of only the seconds that changed.

**The prompt is 10% of the video and the harness is 90%.** Both sources independently say the same thing.
- **A one-liner gives "mid":** a centered title on a gradient, everything fading in, music and picture living separate lives.
- **What fixes it:**
  - a reference to borrow grammar from
  - a director's brief with timed states
  - a beat map with the drop on the key visual
  - stills before renders
  - springs instead of curves
  - SFX on measured peaks
  - real data or an "Example data" label
  - **watching your own frames until every score is 8+**

Prompt library: `references/prompts.md`. Sources and credits: `references/sources.md`.

## Files

```
templates/index.html       the film: SCENES, FILM {dur, cuts}, seek(t), ?w=&h= sizing, preview HUD (space/←→/shift/R/scrub/?t=)
templates/lib/motion.js    E easings (exact 0/1 ends), P(), spring/springFZ/SPRINGS presets, track/loopTrack, indicator,
                           swapAlpha, cyc, drift, rng (mulberry32), beat helpers, camera (log zoom + beat punches),
                           flood (clears farthest corner), riseWords (masked word rise), fitFont, layout()
templates/render.mjs       --stills / --beats / --draft / master; --sub N over --shutter 0.5, cut-aware, --adaptive,
                           --scale 2 supersample, --capture dom, --from/--to; BT.709 TV range; frame-count check;
                           fails on page errors; machine-wide render lock
templates/chunks.sh        K parallel time chunks + lossless concat (big machines only)
templates/drop.py          real drop by band energy (+ --zoom 20 ms, --drop/--at → beats.json with song offset)
templates/beats.py         librosa beat/onset map (optional; needs a venv)
templates/music.mjs        synthesized on-grid backing bed + beats.json (no track supplied)
templates/mix.py           music offset + SFX on MEASURED PEAK + VO ducking + two-pass loudnorm -14 LUFS → mux
templates/sfx.mjs, mix.sh  older synth-SFX + one-pass mix (kept; mix.py is preferred)
templates/assets.py        Mixkit SFX/music search+download, svgl/simple-icons logos, picsum (Unsplash) photos
templates/qc.py            pops, one-frame flashes, frozen runs > 1 s, loop position AND velocity
templates/qc.sh            contact.png, strip.png, phone.png, poster.png, loop_check.mp4
templates/poster0.sh       burn poster into frame 0 (X/Slack/Discord show frame 0, not the cover)
templates/formats.sh       9:16 / 1:1 / 16:9 / 4:5 from one timeline, one shared mix
templates/BRIEF.md, facts.md, review_log.md, STUDIO_RULES.md   copied into every project (docs/ + root)
scripts/new_project.sh     scaffold;  scripts/smoke_test.sh  end-to-end self-test
```

**Runtime:**
- **playwright-core:** lives in `~/.hermes/data/motion-graphics/runtime`, and render.mjs finds it on its own. Override with `MOTION_RUNTIME`. To reinstall: `mkdir -p ~/.hermes/data/motion-graphics/runtime && cd $_ && npm init -y && PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm i playwright-core`.
- **Chrome:** the cached `chromium_headless_shell`, or set `CHROME_PATH`.
- **Python:** the tools need numpy + ffmpeg only. Use `/usr/bin/python3` (numpy 2.3). `beats.py` alone needs librosa in a venv.

## Workflow

**0. Brief first, no code.**
- **Collect inputs:**
  - product/URL or subject
  - duration
  - formats
  - brand: logo, one accent, fonts
  - a **named reference style** ("Linear launch", "Apple bumper"; never "premium modern") plus reference files
  - music: a file, Mixkit, or synthesize
  - VO or mascot
- **If the user's brief has an `<inputs>` block**, ask for exactly those inputs, recommended defaults first.
- **Fill the documents:** `docs/BRIEF.md` (timed states, layers, sound plan, silent one-sentence test) and `docs/facts.md` (every number with source + date).
- **Wait for OK.** Anything paid (TTS, Seedance base shots) gets a cost estimate first.

**1. Scaffold.**
- Run `bash ~/.hermes/skills/creative/motion-graphics/scripts/new_project.sh <dir>`.
- Work in the user's project, or in `~/.hermes/data/motion-graphics/projects/<name>/`. Never `/tmp`.
- One folder per brand. Reuse the closest earlier film instead of starting from zero.

**2. Assets and reference.**
- **Product:** capture real UI with Playwright into `brand/screenshots/` and list what you found. Never invent screens.
  - **Product films:** rebuild screens in code (pixel-sample one `ui-tokens` set: colours, radii, shadows, spacing) so they animate element by element. Check them side by side with the screenshots.
  - **Paywalled UI:** ask the user for screenshots, or label a recreated UI as illustrative.
- **Reference video:** extract `fps=2` frames and look at them. Write `docs/style_guide.md` (palette hex, type, shot lengths, transitions, camera, text in/out). Take the grammar, never the content.
- **Free assets:** `python3 assets.py sfx whoosh`, `sfx-get <id>`, `music <genre>`, `music-get <id>`, `logo <name>`, `photo <picsum id>`. Contact-sheet every image before using it.

**3. Beat map.**
- **Supplied or Mixkit track:**
  1. `python3 drop.py audio/x.mp3` gives per-bar low-band energy and candidate drops.
  2. `--zoom <t>` pins the drop to 20 ms.
  3. `--drop <t> --at <film_t> --dur <s> > beats.json`.
  4. Put the printed `offset` into `sound.json`.
  **Never trust an automatic grid:** one real track's auto bar was 2 beats off.
- **No track:** `node music.mjs --bpm 120 --dur N` writes `audio/music.wav` and `beats.json`, offset 0.
- **Placement:** every scene starts on a beat, the drop lands on the key visual moment, nothing stays still for more than 1 s.
- **Tempo by mood:** 60-80 BPM regal, 90-110 smooth, 115-123 sophisticated, above 125 hype.

**4. Build `index.html`.**
- One object per shot in `SCENES`, and every hard cut listed in `FILM.cuts`.
- Use `layout()` units throughout. Make shots shared-element handoffs where you can.
- **Motion helpers:** springs and `track()` for motion, `camera()` for the one camera, `flood()` for colour transitions, `riseWords()` for type, `fitFont()` so titles fit the safe width at peak zoom.
- **Seeking:** `rng(seed)`, never `Math.random`. Third-party libs only if they can be seeked (STUDIO_RULES.md).

**5. Stills.**
- Run `node render.mjs --w 540 --h 960 --stills 0.5,2,4.1,...` (one per shot) or `--beats` (one per beat), then **open them with vision**.
- Fix composition before motion. One wrong still costs 2 minutes; the same problem found on a full render costs a full re-render.

**6. Draft plus critique, at least 3 rounds.**
- Run `node render.mjs --w 1080 --h 1920 --draft`. That's a 540-pixel short side, 30 fps, no blur, so you're judging rhythm, not sharpness.
- Then run `bash qc.sh out/draft.mp4 <fast_t>` and **look at** contact, strip and phone sheets.
- **Score 1-10:** hook, phone readability, motion, variety, composition, brand/data accuracy, sound sync.
- Log the scores and the 3 worst problems with timestamps in `docs/review_log.md`.
- **Fix only shots scoring 7 or less**, and don't touch shots at 9+. Re-render only `--from/--to`. Repeat until everything is 8+.
- For anything shipping publicly:
  - run the critic as a **separate read-only sub-agent** (`delegate_task`, default reject)
  - then have a fresh agent restate the message from the frames alone; if it can't, the film fails

**7. Master.**
- **Render:** `node render.mjs --w 1080 --h 1920 --fps 60 --sub 8 --adaptive --out out/silent.mp4`. Use `--scale 2` for type-heavy films.
- **Check:** `python3 qc.py out/silent.mp4` should report 0 unexplained pops, flashes or frozen runs. Add `--loop` for loops.
- **Mix:** fill `sound.json` with cues (name, time, gain 0.04-0.3), then run `python3 mix.py --video out/silent.mp4 --out out/final.mp4`.
- **Other formats:** `FORMATS="9x16 4x5 16x9" bash formats.sh --fps 60 --sub 8 --adaptive`.
- **For X/Slack/Discord:** `bash poster0.sh out/final.mp4 out/poster.png out/final_poster.mp4`.

**8. Deliver.**
- **Files:** the final MP4(s), contact.png and poster.png.
- **Report:** duration, resolution, measured LUFS, final scores, what you'd improve, and a **true** caption: no "one prompt" or "made in 10 minutes" if it wasn't.
- **Telegram:** `MEDIA:/abs/path`.

## Hard rules

- **Render contract:** `seek(t)` is pure. No CSS transitions, timers, rAF (except the preview loop), carried state, Date, or `Math.random`. smoke_test.sh checks this by comparing frame hashes across two renders.
- **Truth on screen:**
  - Numbers only from `docs/facts.md`.
  - Anything illustrative is labelled "Example data".
  - Real integrations only, e.g. "Native: X, Y. Anything else via webhook." Never invent features or imply partnerships with co-marks.
  - Fictional people get generated faces and invented names.
- **Anti-AI-look:**
  - One accent, and one thing moving at a time.
  - One visual system throughout, built from transformations rather than cuts.
  - Springs damped to a ratio of 0.72 or more (the `playful` preset is for mascots only).
  - **Banned:** gradient title cards, fade-everything, corner labels, glow, particles, rainbow, emoji, lorem ipsum, gratuitous 3D flips.
- **Look before claiming done.** Never report a render as good without opening the QC images.
- **Keys** stay in `.env`. If the user finishes in an editor (CapCut, Premiere), deliver clean elements instead of a composited cut.

## Pitfalls

- **Subframes:** 4 ghost on fast moves, so use 8 for slams and whips with `--adaptive`, which keeps static frames at 1 sample. Blur never crosses `FILM.cuts`, so an undeclared cut double-exposes the cut frame.
- **A transition must finish before its hard cut.** A flood still growing at the cut pops from circle to full frame, and qc.py flags it. The template's flood ends 0.13 s before its cut. Also check the frame's corners in a still.
- **Type at peak zoom:** a title sized for zoom 1.0 clips at 1.06. Size titles with `fitFont(width / maxZoom)`. The 9:16 smoke test caught exactly this.
- **Easing ends:** easings solved numerically return about 1e-9 at 0, so `if (e > 0)` guards fire early. Use the `E` easings, which return exact 0 and 1.
- **Loops:** match position AND velocity (`loopTrack`, `qc.py --loop`), with integer cycles per loop (`cyc`).
- **Use HTTP, not `file://`.** ES modules and fetch need HTTP. render.mjs serves the folder; to preview, run `python3 -m http.server`.
- **Fonts:** wait for `document.fonts.ready` via `window.ready`. A missing font silently falls back. Inter is in `~/.fonts`; otherwise self-host the `.woff2`.
- **Headless WebGL renders black:** set `WEBGL=1` (SwiftShader/ANGLE flags).
- **Render cost on this 2-core box:** a 540×960 film at 30 fps took about 23 s for a 6 s draft and about 96 s for an 8-sub adaptive master. A full-HD 60 fps master costs roughly 8× more per second of film. Always draft small. One render at a time is enforced by a lock in `~/.hermes/data/motion-graphics/locks`, and stale locks clear themselves. chunks.sh only pays off on multi-core machines.
- **Concurrent encodes:** need unique `--out` paths, or the moov atom gets corrupted.
- **Python packages:** PEP 668 blocks global pip here. Use `/usr/bin/python3` for the numpy tools, and a venv for librosa.
- **Mixkit's search ignores `?q=`.** assets.py crawls tag and genre pages instead. The SFX preview MP3s are short (around 0.3 s); place them by peak.

## Verification

Run `bash ~/.hermes/skills/creative/motion-graphics/scripts/smoke_test.sh ~/.hermes/data/motion-graphics/smoke`. It exercises:
- scaffold, synthesized music, drop finder, stills and beat stills
- draft, then an adaptive 8-sub master with a declared cut
- peak-placed mix with two-pass loudnorm
- qc.py, qc.sh, poster0
- the determinism check
- 16:9, 1:1 and 4:5 reframes

It should end with `QC: PASS`, `determinism: identical frames`, -14.0 LUFS and `SMOKE OK`.

Last run on this box on 2026-10-02:
- draft 23.7 s
- master 96.4 s, samples {1: 98, 4: 68, 8: 14}
- -14.0 LUFS, 0 pops, 0 flashes
- identical frames
