# BRIEF — build agent [G] (frame-locked remake of [REF VIDEO] for [BRAND])

Workdir (absolute): [WORKDIR] · you own frames [f0]-[f1] · fps [FPS] · stage [W]x[H].
Renderer: `node remake_render.mjs compare out/[G] F1 F2 ...` (serves the folder itself; <= 15 frames per call).

## Acceptance bar
Our render must match REF frame by frame in LAYOUT, SIZES, POSITIONS, TIMING, EASING, CAMERA, CUTS, BLUR, CURSOR PATH and
TYPING CADENCE when shown side by side in sync ("original | copy" split screen). Only content is swapped.
Target: position/size error <= 1-2% of frame, cuts 0 frames off. Differences only where the swap forces them
(e.g. word widths): report each one.

## Swap rules (edit per project)
- [OLD BRAND] -> [BRAND]: `CORE.appIcon` / `CORE.mark`, accent colours -> `CORE.T` tokens (palette filter catches leftovers).
- Partner/co-brand marks: never imply a partnership that doesn't exist (no "OpenAI x [BRAND]"; a true co-mark only).
- No photos of real people from REF: logo tiles, cards or neutral shapes of the same size and motion instead.
- Copy must be TRUE for [BRAND]; no invented numbers (mock UI numbers read as examples).
- Never reuse REF music, voice or images.

## File rules
Write ONLY `shots/[G].js` (IIFE, helpers prefixed `[G]_`, one `SHOT({id, f0, f1, render})` per shot, contiguous range).
Pure function of F (`CORE.rand`, never Math.random/Date/timers). Never edit core.js / index.html / project.json / scripts.
Scratch only in `out/[G]/` and `measure/[G]_*`.

## Method
1. Read SPEC.md + the core.js API (CORE.*).
2. MEASURE with numpy on `ref/full/fNNNN.jpg` (ink bounding boxes, typed char counts per frame, cursor tip, camera
   scale/offset, fade timing) -> drive motion with `CORE.samples(F, f0, measuredArray)` or `CORE.kf` tables.
3. Verify per shot: `node remake_render.mjs compare out/[G] <first, last, keyframes, 2 frames into every transition>`,
   then LOOK at out/[G]/compare_sheet.jpg. Iterate. Never claim a match without viewing REF | OURS.
4. Pitfalls: measure text only after fonts load (`CORE.inkBox`, `CORE.fitFont`); REF's cursor is often not the macOS arrow
   (draw REF's shape); REF whips may be crisp (no blur); seeded bursts; check REF's real cut frames (SPEC boundaries are
   often +/-4 frames off: fix them and report).

## Report back
Table: shot | frames | MATCHES / CLOSE / ROUGH | residual difference | frames that would drift | SPEC errors found.
