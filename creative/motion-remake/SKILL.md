---
name: motion-remake
description: "Use when remaking an existing video frame by frame for a new brand."
version: 1.0.0
author: Hermes Agent (adapted from Raphaël Aubry's claude-motion-design remake mode, MIT)
license: MIT
platforms: [linux, macos]
prerequisites:
  commands: [node, ffmpeg, ffprobe, python3]
metadata:
  hermes:
    tags: [motion-graphics, remake, video, rebrand, split-screen, frame-locked, playwright, ffmpeg]
    related_skills: [motion-graphics, generated-asset-verification, subagent-driven-development]
---

# Motion remake (frame-locked 1:1 copy for another brand)

## When to Use

Use this when someone asks to "remake / recreate this launch video for my brand", or wants the viral split-screen format: **original | code remake**. The result is a code-rendered copy that matches the reference frame by frame in layout, timing, easing, camera, cuts and cursor path, with only the content swapped.

For an original film, use `motion-graphics`. This skill reuses that one's runtime, audio tools (`drop.py`, `mix.py`, `assets.py`) and QC (`qc.py`).

**Proven by the source:** a 65 s, 28-shot launch film remade in about 25 min per build agent, with agents running in parallel. That figure is the author's claim. Here, the pipeline was verified on a synthetic reference (see Verification); no real 60 s remake has been run on this box.

## Hard rules (check before starting)

- **The reference video is user-supplied.** This box's IP is blocked by YouTube, so ask for the file. Put it at `ref/reference.mp4`.
- **Never reuse REF's music, voice, images or people photos.**
  - People become logo tiles, cards or neutral shapes of the same size and motion.
  - Music is a royalty-free track (Mixkit, supplied, or synthesized) fitted to REF's tempo and drop.
  - VO, if any, uses REF's word *timings* only, never the audio.
- **Truth:**
  - Copy must be true for the new brand. Mock UI numbers read as examples.
  - No co-marks implying a partnership that doesn't exist (no "OpenAI × Brand").
  - Credit and tag the original brand in the post.
  - No fake "made in 15 minutes".
- **Brand and trademark:** remaking a *competitor's* film to compete with it is a legal and PR risk. Say so, and suggest an homage to the format instead.
- **Paid parts:** anything paid (TTS VO) gets a cost estimate first.

## Files

```
templates/core.js            seek(F) engine for a DOM #stage: E easings, spring (frames), kf keyframe tables, samples() for
                             measured per-frame arrays, rand, camera, mblurDefs, cursor, typed, words, gtext, mark/appIcon,
                             pixelDissolve, fitFont, inkBox, mixHex, paletteFilter (re-hues leftover old-brand colours)
templates/index.html         loads project.json → fonts → core.js → shots/<G>.js; sets window.ready
templates/project.json       fps, size, brand tokens, mark, fonts, oldHues, oldColorScan, groups {G1:[f0,f1],...}, split labels
templates/remake_analyze.py  Phase 0: every frame (conformed fps/width), audio, hard cuts, labelled 6-frame contact sheets
templates/remake_stub.py     one placeholder shots/<G>.js per group (never overwrites)
templates/remake_render.mjs  stills | compare (REF|OURS tiles + sheet) | full; serves the folder; shared render lock
templates/remake_sync.py     encode (frame-count check, no -shortest) | split (post format, setsar=1) | stacked (QA)
templates/remake_qa.py       per-second REF|OURS sheets, group seams, old-brand colour scan
templates/remake_audio.py    analyse REF (BPM, drop candidates, hard stop, transient hits) | fit a track (≤8% stretch, drop on REF drop)
templates/BRIEF_TEMPLATE.md  build-agent brief (acceptance bar, swap rules, file rules, method, report table)
templates/SPEC_TEMPLATE.md   shot table + swap rules + groups + audio plan
scripts/new_remake.sh        scaffold (copies motion-graphics drop.py, mix.py, assets.py, qc.py too)
scripts/smoke_test.sh        end-to-end self-test on a synthetic reference
```

## Workflow

**Phase 0: analysis, no building.**
1. Run `bash ~/.hermes/skills/creative/motion-remake/scripts/new_remake.sh <dir> <reference.mp4>`. Work in `~/.hermes/data/motion-remake/projects/<name>/` or the user's folder, never `/tmp`.
2. Edit `project.json`:
   - fps (REF's own, usually 24/25/30) and size
   - brand tokens, mark file and fonts
   - `oldHues`: the old brand's hue ranges mapped to the new accent hue
   - `oldColorScan`: thresholds tuned to the old accent
3. Run `python3 remake_analyze.py --fps <fps> --width <w>`, then **read every `ref/sheet/*.jpg`**.
4. Write `SPEC.md` from `SPEC_TEMPLATE.md`:
   - **Shot table:** id, f0-f1, REF content, brand swap.
   - **Swap rules.**
   - **Groups:** contiguous, about equal work, 4 for a 60 s film.

   Expect only about 10-15 real hard cuts, since most "cuts" are continuous camera or morph moves. Expect SPEC boundaries to be a few frames off. **Show SPEC to the user and wait for OK.**

**Phase 1: engine (you, before agents).**
1. Copy the groups into `project.json` and run `python3 remake_stub.py`.
2. Put brand assets in `assets/` and add anything new the shots need to `core.js`. Only you edit `core.js`; agents never do.
3. Smoke-test with `node remake_render.mjs compare out/test 10 600 1200`, then look at the sheet.

**Phase 2: parallel build.**
1. Fill `BRIEF_TEMPLATE.md` once per group.
2. Dispatch build agents with `delegate_task`, at most 3 parallel children here. Each agent:
   - writes **only** `shots/<G>.js`
   - measures REF with numpy (ink boxes, typed char counts, cursor tip, camera scale) and drives motion from the measurements via `CORE.samples` or `CORE.kf`
   - verifies with `compare` sheets it actually looks at
3. If there are 4 groups, run the 4th after one of the first three finishes.
4. **Audio agent**, or you:
   1. `python3 remake_audio.py analyse`. Pick REF's real drop from the candidates by checking the ref sheets.
   2. `python3 assets.py music <genre>` → `music-get <id>`.
   3. `python3 drop.py audio/mixkit-<id>.mp3` to find the track's drop.
   4. `python3 remake_audio.py fit audio/mixkit-<id>.mp3 --track-drop T --ref-drop R`.
   5. Tune the cue names and gains in `sound.json`, then run `python3 mix.py`.

**On this 2-core box:** renders queue on the shared lock, so agents effectively take turns rendering. Planning and measuring still run in parallel. On a bigger machine, set `MOTION_RENDER_SLOTS=3`.

**Phase 3: integrate.**
1. Run `node remake_render.mjs full out/full 0 <N>`. On big machines, split it into 3 ranges with `MOTION_RENDER_SLOTS=3`.
2. Run `python3 remake_sync.py encode`, which checks the frame count and muxes `out/mix.wav`.
3. Run `python3 remake_sync.py stacked` and watch the sync.
4. Run `python3 remake_qa.py`, then read `persec_*.jpg` and `seams.jpg`. Fix any old-brand colour frames it reports.
5. Run `python3 qc.py out/remake_silent.mp4 --cuts <REF cut times>` to catch undeclared pops and flashes.
6. Fix, re-render the affected range, and repeat.
7. Run `python3 remake_sync.py split` for the post.
8. **Deliver:** `split_screen.mp4`, `remake.mp4`, and the per-shot MATCHES/CLOSE/ROUGH table from the agents. Report honestly: name the shots that are ROUGH.

## Pitfalls

- **Use the measurements, not guesses.**
  - Drive motion from per-frame arrays measured on `ref/full/`.
  - Measure text only after fonts load (`CORE.inkBox`, `CORE.fitFont`).
  - REF's cursor is often not the macOS arrow, so draw REF's shape.
  - REF's whips may be crisp, with no blur.
- **Frame indexing:** `remake_analyze.py` conforms REF to `--fps`, so `ref/full/fNNNN.jpg` index N equals our frame F. Changing fps after analysis breaks every comparison, so re-run the analysis.
- **Mix length = film length.** The mix must be as long as the film. A mix cut at REF's audio hard stop, plus `-shortest`, truncated the video in the first smoke run: 3.55 s out of 4 s. `remake_audio.py fit` now sets `dur` to REF's duration, and `encode` cuts to the video length and warns on mismatch.
- **Split screen:** use `setsar=1` on every input and the output, or X stretches the post.
- **Palette filter:** it only re-hues `#rrggbb` hex in the HTML. Colours in images, `rgb()` and named colours slip through, which is what `remake_qa.py`'s colour scan is for. Put the brand's images in `assets/` already in the new colours.
- **Synthetic test refs:** ffmpeg's `drawbox` x/y aren't evaluated per frame, so an animated box silently freezes. Use `overlay=...:eval=frame`.

## Verification

Run `bash ~/.hermes/skills/creative/motion-remake/scripts/smoke_test.sh ~/.hermes/data/motion-remake/smoke`. It builds a synthetic 4 s reference: an orange "OLDCO" card sliding in, a hard cut, then a title. The test then runs:
- analyse (must find the cut at frame 48)
- stub stills, a real G1 shot written from the measured motion, and a compare sheet
- a **frame-lock check**: card edges within 2% of REF at frames 0/12/24/47
- full render, encode, audio analyse + fit, and mix (-14 LUFS)
- a duration check (the remake must not be truncated)
- split, stacked, QA (0 old-brand colour frames, because the palette filter re-hued the deliberately orange card)
- `qc.py` (only the declared cut pops)

It should end with `REMAKE SMOKE OK`.

Last run on this box on 2026-10-02 (smoke2):
- cut found at frame 48
- frame-lock error 0.00%
- full 96-frame 960×540 render in 9.9 s
- remake.mp4 4.000 s (not truncated), mix -14.5 LUFS
- 0 old-brand colour frames, `QC: PASS`
- split screen checked by eye: SAR 1:1, labels legible

The first run (smoke1) caught two real bugs, both now fixed and covered by the test:
- the audio truncated the film
- the synthetic ref froze because of `drawbox`
