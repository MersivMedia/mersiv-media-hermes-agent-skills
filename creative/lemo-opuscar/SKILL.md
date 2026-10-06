---
name: lemo-opuscar
description: "Use when making a styled short film in code."
version: 1.0.0
author: Hermes Agent (wraps lemomo-ai/lemo-opuscar, MIT © 2026 LemoLab)
license: MIT
platforms: [linux, macos]
prerequisites:
  commands: [node, ffmpeg, git, python3]
metadata:
  hermes:
    tags: [video, film, motion-graphics, animation, art-style, canvas, webgl, storytelling]
    related_skills: [motion-graphics, motion-remake, manim-video, elevenlabs-narrator-revoice, generated-asset-verification]
---

# Lemo-Opuscar: styled short films in code

## When to Use

Use this when the film needs a **specific artistic look**: watercolor, ink wash, impasto oil, woodcut, risograph, 80s cel anime, rubber-hose cartoon, pixel RPG, HD-2D, stained glass, art deco, spy titles, silent film, blueprint, hologram HUD, data storytelling and others. It also fits narrative or explainer shorts with voice and score, where the look carries the story.

Other skills fit better in these cases:
- **Product launch films, showreels, kinetic type, UI morphs, beat-synced ads:** `motion-graphics`. Its harness, beat tools and QC are the stronger fit.
- **1:1 remake of an existing video:** `motion-remake`.
- **Math explainers:** `manim-video`.

The two combine well. Opuscar supplies the style grammar (STYLE.md) and its toolkit; motion-graphics' `qc.py` / `qc.sh` and its 8+ critique loop still apply to the output.

## What it is

[Lemo-Opuscar](https://github.com/lemomo-ai/lemo-opuscar) is a library of **43 film styles**. Each has a `STYLE.md` style prompt covering essence, materials, colour, type, motion, camera, sound, native moves and pitfalls. Each also comes with a demo film made entirely in code. Everything sits on a shared toolkit:
- `core/render`: still / video / events / readcheck / contact sheet / srt / mux
- `core/tts`: Kokoro offline, edge-tts, Whisper check
- `core/audio`: sampler, pluck, procedural SFX

The styles were tuned with Claude Opus 5.5, so other models may not reproduce them.

**Library location:** `LIB=~/.hermes/data/motion-graphics/opuscar`. It's a sparse clone: guides, core tools and every STYLE.md, with no demo sources or big images. Core dependencies are installed (npm `playwright-core` + `three`, chromium-headless-shell, `.venv` with numpy/scipy/soundfile/soxr/pillow).

## Steps

1. **Refresh the library:**
   `bash ~/.hermes/skills/creative/lemo-opuscar/scripts/opuscar.sh` prints `LIB=<path>`. Then run `... opuscar.sh deps` (core). Only if the film needs them, add `deps voice` (Kokoro, about 300 MB with the model) or `deps music` (numba). Sample instruments: `cd $LIB && sh tools/fetch.sh instruments <lib>`.
2. **Read and follow `$LIB/AGENTS.md`.** It covers finding the style (`$LIB/styles/README.md` maps English/Chinese names to folders), the **one** round of questions, `TREATMENT.md`, look frames, produce, and the self-check. `DIRECTOR.md` covers craft and delivery (§11 is the delivery list). `TECHNIQUE.md` covers the build. `core/README.md` is the command reference.
3. **Project folder:** `~/.hermes/data/motion-graphics/projects/<name>/` (lowercase, digits, hyphens), never `/tmp`. Wherever the guides say `films/<name>/`, read this folder.
4. **Run tools from `$LIB` with the project's absolute path:**
   `cd "$LIB" && node core/render/still.mjs "<project>" 1.5 3`. Pages load library files by absolute URL (`/core/lib.js`, `/node_modules/three/...`); the project is served at `/@film/`. `build.sh` sets `LIB=<path>` at the top and never uses `../..`.
5. **Demo source, for reference only, after `TREATMENT.md` exists:** `... opuscar.sh demo <slug>`. Read its techniques. Don't render it.
6. **Look before claiming done.** Open the stills and contact sheet with vision. Run `readcheck.mjs` for text timing. Optionally run motion-graphics' `qc.py` for pops, flashes and frozen runs.

## Page contract (from core/README.md)

```js
window.DUR = 54.2;               // seconds
window.render = t => { ... };    // pure, deterministic frame at time t
window.READY = true;             // after fonts/images load
window.EV = [{t, type, ...}];    // optional sound/cue events
window.TEXTS = t => [{id, text, x0, y0, x1, y1}];   // optional, for readcheck
```

This is the same idea as motion-graphics' `seek(t)`, under different names. Seed randomness with `mulberry` from `/core/lib.js`; never use `Date.now()` or unseeded `Math.random()`. The default frame is 1920×1080; for vertical, pass `--size 1080x1920` to every tool.

## Hermes rules on top of the library's

- **Voice:** for branded work, use the brand's locked ElevenLabs narrator (`elevenlabs-narrator-revoice`) instead of Kokoro/edge-tts. Kokoro is fine for drafts and unbranded films.
- **Editor hand-off:** if the user finishes in an editor (CapCut, Premiere), deliver clean elements, not auto-composited wordmarks or outros.
- **Copyright:** follow `DIRECTOR.md` §12. Styles are grammar only; never copy a referenced work's characters or frames.
- **Credits:** sampled instruments are CC BY (Salamander, MuldjordKit and others). Keep the credit lines `sampler.py` prints in the delivery notes.

## Pitfalls

- **Stock demos don't render as cloned.** Their fonts and audio aren't in git (404s, then `[pageerror] A network error occurred`). The demo is meant to be read, not run. Test the toolkit with your own page.
- **The renderer stops on any page error or HTTP error** for a script or module. A missing optional font only warns.
- **Each parallel render needs its own `--out`,** or the moov atom gets corrupted (the same rule as motion-graphics).
- **Grain:** add it in `mux.sh` (`grain=2`), never in the page. Page grain makes every frame incompressible and slow.
- **The setup script installs its own chromium-headless-shell** (v1243, about 114 MB in `~/.cache/ms-playwright`), separate from motion-graphics' runtime.
- **Don't edit `core/` or `styles/` for a user's film.** `opuscar.sh` hard-resets the managed clone to upstream `main` on every refresh.

## Verification

Smoke film: `~/.hermes/data/motion-graphics/opuscar-smoke/film/index.html` (4 s, page contract only).
- `cd $LIB && node core/render/still.mjs <film> 1 3.5`
- `node core/render/video.mjs <film> --fps 24 --workers 2 --out <film>/out/video.mp4`

Expect 96 frames at 1920×1080 and a duration of 4.0 s.

Last run on this 2-core box on 2026-10-04: stills about 0.1 s each; 96 frames in 11 s with 2 workers (simple 2D scene; painterly styles cost much more per frame).
