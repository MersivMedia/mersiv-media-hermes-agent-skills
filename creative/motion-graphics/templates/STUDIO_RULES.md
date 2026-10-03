# Studio rules (read before every change)

## Render contract
- Every film is a pure function of time: `window.seek(t)` paints frame t, in any order, identically every run.
- No CSS transitions, no setTimeout, no requestAnimationFrame outside the preview loop, no state carried between
  frames, no Date. Seeded noise only (`rng()` in lib/motion.js). Never `Math.random`.
- Declare every constant before the first `seek()`. `window.ready` resolves after fonts and images load.
- Size comes from `?w=&h=`. Position everything with `layout()` units, never fixed pixels.
- Third-party animation libs only if they can be SEEKED: GSAP `tl.pause(); tl.totalTime(t + 0.001, true); tl.totalTime(t, true)`
  (it skips redraws for the same time), WAAPI `document.getAnimations().forEach(a => { a.pause(); a.currentTime = t * 1000 })`,
  Lottie `goToAndStop(t * 1000)`, anime.js `autoplay: false` + `seek(t * 1000)`, Theatre.js `sequence.position = t`.
  Never live-only runtimes (Spline, Unicorn Studio, framer-motion): they can't be seeked, frames drift.
- Video sources inside a film: pre-extract frames with ffmpeg and draw the right image per t (waiting on `seeked` flakes).

## Look (anti "AI motion")
- Banned: centered title on a gradient, everything fading in, corner labels and frame borders, glow on UI chrome,
  particle bursts, rainbow gradients, emoji, lorem ipsum, gratuitous 3D flips, cartoon bounce on type.
- ONE accent colour. One display face, one UI face. A named reference style ("Linear launch", "Apple bumper"),
  never "premium modern".
- One thing moves at a time (unless one control drives a continuous transform). One shape / visual system from start
  to end: transformations, not cuts. The next shot enters already moving in the previous exit's direction.
- Something new every 2 to 4 s, a hook in the first 2, the music drop on the key visual moment.
- No frozen frame anywhere except the final hold: keep a micro drift/settle alive (`drift()`), also on end cards.
- Text: masked word rises (`riseWords`), shared elements carry their text into the next state; text swapping inside a
  morphing shape gets its own mask. Never scale a blurry copy of text; crossfade only the fill. Measure text with
  canvas `measureText` (never DOM rects under a camera scale). Type big enough for a phone (check phone.png at 360 px).
- Camera: one transform, keys `[t, zoom, x, y]`, zoom interpolated in log space, never in-then-out back-to-back.
- Floods clear the farthest corner (`flood()`), in ~0.3-0.35 s, then contract into the next object.

## Motion
- Springs from lib/motion.js; damping ratio >= 0.72 for anything premium (tiny overshoot on UI, none on type).
  `playful` (0.42) is for mascots/stickers only. A value with more than one target uses `track()`; loops use `loopTrack()`.
- Settles: per-frame law, fastest step first, never in visible 3-frame steps. Exits accelerate (geometric x1.5 per frame).
- Easings, when not a spring: `E.io`, `E.out`, `E.o5`, `E.expo`. Linear motion is cheap: never.
- Loops: integer cycles per loop (`cyc()`), last frame = first frame in position AND velocity.

## Truth on screen
- Every number on screen comes from `docs/facts.md` (value + source + date). No facts.md, no numbers.
- Anything illustrative is labelled on screen: "Example data", "Example answer", "Illustration".
- Real product UI and real integrations only. Never claim a feature that doesn't exist. Logos: "works with" only if true,
  never co-marks that imply a partnership.
- Fictional people in UIs: generated faces with matching invented names, never a real person.
- Captions/posts stay true: no "made in 10 minutes", "one prompt" or "0 tools" unless it is literally true.

## Sound
- Music: supplied track (drop.py finds the real drop by band energy; never trust an auto grid), a free Mixkit track
  (assets.py), or synthesized (music.mjs). Start the song at `drop_in_song - drop_in_film`.
- SFX on their MEASURED PEAK (mix.py), gains 0.04 to 0.3, keystrokes follow the typing rhythm. "Premium" = a handful of
  soft hits; remove anything loud or out of place. Two-pass loudnorm to -14 LUFS, true peak -1 dB.

## Loop before showing anything
1. Stills (one per shot, or `--beats` one per beat) -> LOOK -> fix. Then `--draft` (judge rhythm, not sharpness).
2. Critique as a harsh motion director (ideally a separate read-only sub-agent, default reject): score 1-10 on hook,
   readability at 360 px, motion quality, variety, composition, brand/data accuracy, sound sync.
3. Log scores + the 3 worst problems with timestamps in docs/review_log.md. Fix only shots <= 7; don't touch 9+.
   Repeat until every score is 8+. Then a fresh agent restates the message from the frames alone; if it can't, it fails.
4. Master render, `python qc.py` (pops, flashes, frozen runs, loop), qc.sh sheets, mix, deliver.
