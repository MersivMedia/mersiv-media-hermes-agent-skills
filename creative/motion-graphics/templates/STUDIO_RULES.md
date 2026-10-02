# Studio rules (read before every change)

## Render contract
- Every film is a pure function of time: `window.seek(t)` paints frame t.
- No CSS transitions, no setTimeout, no requestAnimationFrame in render mode, no state carried between frames.
- Seeded noise only (`rng()` in lib/motion.js, mulberry32). Never `Math.random`.
- Size comes from `?w=&h=`. Position everything with `layout()` units, never fixed pixels.
- Render with `node render.mjs`. H.264, yuv420p, CRF 16.

## Look
- Banned defaults: centered title on gradient, everything fading in, corner labels and frame borders,
  glow on UI chrome, generic particle bursts, bouncy easing on type.
- One display face, one UI face, one accent color unless the brief says otherwise.
- Something new happens on screen every 2 to 4 seconds. Hook in the first 2.
- Real product UI only (screenshots of the real thing). Never invent screens.
- Motion uses springs from lib/motion.js. A value with more than one target uses `track()`.
  Tiny overshoot on UI, none on type.

## Sound
- Score and SFX are synthesized in code (music.mjs, sfx.mjs) unless a track is supplied (beats.py).
- State changes on beats, big moments on downbeats, SFX on measured hits. Final loudness -14 LUFS.

## Loop before showing anything
1. Render stills (one per beat or per shot) and the QC sheets, then LOOK at them.
2. Score 1-10: hook in first 2s, readability at phone size, motion quality, variety,
   composition, brand accuracy, sound sync.
3. Log scores + the 3 worst problems with timestamps in docs/review_log.md. Fix. Repeat until every score is 8+.
4. Only then do the full render.
