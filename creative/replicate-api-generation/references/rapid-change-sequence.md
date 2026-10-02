# Rapid-change sequence: one motion, many looks

**Status (2026-09-29): stage 1 RUN and alignment MEASURED. It works.** The
base (5 s, first/last frame between relay keyframes K3→K4) and 2 look edits
(leather jacket, red gown) all succeeded on `minimax/h3` 2K, $0.65 each.
- **Frame lock:** each look has the same frame count as the base (124 @
  24 fps). The best temporal offset from a −6…+6 frame edge-map sweep is
  **0 frames** for both looks, and the score rises smoothly on either side.
- **Pose lock:** in a same-frame grid (0.5 / 1 / 1.5 / 2.5 / 4 s), pose,
  head angle, hands, umbrella, crane and framing are identical across base,
  L1 and L2. Only the outfit changes, and the face holds.
- **Cuts:** in the 3 s beat-cut preview (0.5 s slices at original timecodes),
  the frames before and after each hard cut show the same body position, so
  it reads as one continuous motion. No cross-dissolve is needed.
- QC tooling is in the sizzle-reel data dir: `qc_stage1.py` (probe, seams,
  offset sweep, preview) and `qc_looks.py` (the same-frame and cut grids).

**BUT the user rejected stage 1 v1: "there's nothing moving in the
background such as rain, people, and cars."** Alignment passing doesn't
make the clip good. Measured with `scripts/bg_motion_check.py`: only
**3.7% of background pixels changed** across the base walk, nearly all of it
the umbrella drip. The looks inherited the same frozen background exactly,
which is expected, since they copy the base. Root causes, all fixable
BEFORE spend:
1. **The bracketing keyframes had the street melted into neon bokeh**, so
   there were no cars or people for H3 to animate. The keyframe prompt must
   say "the busy street stays clearly readable in moderate focus, NOT melted
   into bokeh: cabs with headlights on the road, pedestrians under
   umbrellas, visible rain streaks falling".
2. **The base prompt said "Simple, even, continuous motion"**, which H3
   read as "only the subject moves". Name the background motion
   explicitly: rain streaks fall steadily, cabs drive past behind her left
   to right with lights and wipers, pedestrians walk both ways, puddles
   splash.
3. **The look template must preserve it:** "Keep ALL the background motion
   of `<Video 1>` exactly as it is: the same falling rain, the same cabs and
   pedestrians, at the same moments."

**The fix is MEASURED (v2, 2026-09-29).** Regenerating only the two bracketing
stills (readable cabs, pedestrians and rain; $0.30) plus the base with named
background motion raised background motion from **3.7% → 14.9%** of pixels.
The motion map is bright across the road, sidewalk and top, and a 6-frame grid
shows cabs changing position and pedestrians walking. The pose and the face
stayed clean. The whole redo cost $2.25, matching the estimate.

**Automate the gate inside the generation script, not as a manual step.**
A `walk` stage (`make_videos.py walk --min-bg-pct 10`) runs:
1. Render the base.
2. Compute `pct_bg_pixels_moving`: the share of background pixels that
   change by more than 6 luma levels between frames, with a central subject
   column excluded.
3. Exit 2 **before** submitting any look if the reading is under the
   threshold. That saves $1.30+ per failed base.

10% was the threshold used: v1 at 3.7% failed and v2 at 14.9% passed. Log the
reading to the run log, so the user-facing report can quote it.

**Gate order:** run the background-motion check on the BASE before
submitting any look. A frozen base means every look is wasted, because a
redo of the base forces a redo of all its looks (the v1 base + 2 looks,
$1.95, were written off). Target: a clearly nonzero `pct_bg_pixels_moving`
with motion-map streaks or blobs outside the subject. Also look at the
motion-map PNG.

**Measured so far:**
- A look edit = `reference_video_urls: [<base output URL>]`, the
  `<Video 1>` template prompt, `duration` equal to the base's, `ratio: 16:9`,
  `resolution: 2K`. The replicate.delivery URL of the base output works as
  the reference directly. Wall time was 337–408 s per look, with 2 running in
  parallel.
- Look output sizes (2.6–2.9 MB) were smaller than the base (4.0 MB), a hint
  of less fine detail or motion. Check the frame counts match the base (124
  frames at 24 fps for `duration: 5`) before slicing.
- Gate script shape (a sizzle-reel data dir `qc_stage1.py`): ffprobe each clip;
  compare downscaled luma edge maps per frame of look vs base; search the best
  temporal offset over ±6 frames (a nonzero best offset means the look
  lags or leads, so shift the slice windows by it); build a preview that cuts
  base 0–0.5 | L1 0.5–1.0 | L2 1.0–1.5 … at ORIGINAL timecodes, re-encoded
  to 1920×1080 with `-an`. Show the preview to the user before the other 7
  looks.

The user asked for this technique by name: one subject whose clothes, hair,
style and objects change on every beat, while it still reads as one
continuous video (not a slideshow of stills). It belongs in any sizzle reel or
showcase that needs to show control.

## Method

1. **Base clip.** Generate one 5 s shot with readable subject motion (walking
   toward camera, a turn) and a static or slow camera. Name the BACKGROUND
   motion explicitly too (rain, traffic, crowd). "Simple, even motion" froze it
   in v1. Every later edit inherits this motion, background included.
2. **Edit the FULL base clip once per look.** Pass it as `reference_videos` /
   `reference_video_urls` with a prompt that keeps the person, pose, motion,
   camera and framing and changes exactly one thing ("Only ONE change: ...").
   Looks can be an outfit, hair or a held object. For this user, keep every
   look **photoreal**: they said "keep all the styles highly realistic", so
   drop rendering-style looks such as anime or claymation. A realistic set
   that was approved: leather jacket, red gown, platinum pixie, spacesuit,
   ivory suit, samurai armour, braids, Victorian dress, a bouquet of roses.
   The base look must match the hand-off keyframes, e.g. the trench coat she
   wears in the relay stills.
3. **Slice by beat.** At the music BPM (120 BPM = 0.5 s/beat), take slice
   *k* from look *k*, keeping the **original timecodes**. Slice 1 is
   0.0–0.5 s of look 1, slice 2 is 0.5–1.0 s of look 2, and so on. Because
   every look shares the base timeline, the walk keeps moving forward across
   cuts.
4. **Concatenate** in order with hard cuts on the beat (ffmpeg concat after
   re-encoding every slice to identical fps/size/pixfmt).

## Verified constraints

- **Minimum clip length is ~4 s on H3 and Seedance.** You can't cheaply
  edit only the half-second you show. The cost is N × full-clip edits.
- **Pricing favours H3.** It charges $0.13/s at 2K with or without video
  input. Seedance 2.5 charges **$0.97/s** at 720p when a video goes in.
  Nine looks cost ~$6.50 on H3 2K vs ~$44.70 on Seedance 2.5. See
  `video-model-apis.md` for the price table.
- Editors regenerate. **The pose can drift** between looks and show up as a
  jump at each cut.

## Stage-1 gate (before spending on all looks)

Base + 2 looks (~$1.95 on H3 2K). Then measure alignment against the base.
Per slice boundary, compare subject position with a silhouette/keypoint
centroid, or failing that the frame-difference energy at the cut against
the average within a slice. Also check timing: the edit must have the same
frame count and fps as the base. Show the user the stitched 1 s test before
the remaining looks. If drift is visible, fall back to cross-dissolves of 2–3
frames or to a pose-locked replacement pipeline
(`ref-character-replacement-content-pipeline`, `video-character-replacement`).

## Sizzle-reel context this came from

- Landscape 16:9, 1920×1080, 24 fps, cuts on a 120 BPM bed.
- The user specified the generators: **H3 or Seedance 2.5 only**, with the
  **cost reported and approved before any generation**.
- The user wants the whole reel to flow as one continuous take. The rapid
  change sits inside a match-cut relay as one shot: the base clip is
  first/last-frame generated between two relay keyframes, so it enters and
  exits on shared frames. See `match-cut-relay-transitions.md`.
- In the edit prompt, use H3's label convention: "`<Video 1>` is the source
  video for the target video edit. Keep ... Only ONE change: {change}."
- **Lock time, light and weather in the base and in every look edit.** The
  base prompt says "hold the time, light and weather constant for the whole
  shot: night, steady rain, the same neon bokeh and cool fill". The edit
  template repeats those exact conditions and adds "with the rain wetting the
  new outfit the same way". A look regenerated with slightly different light
  shows up as a flicker at every 0.5 s cut, even when the pose aligns.
- The end card is built in code, not generated. The logo goes on its own
  measured background colour (pure #000000 here), with white tagline text
  matched to the wordmark's thin, wide-tracked geometric sans. Upscale or
  vectorize a small logo file (320 px) rather than stretching it. Send a
  still for approval first.

## Pitfall: a static background (measured 2026-09-29)

The v1 base walk passed seam and alignment checks, but the user noticed that nothing
moved behind her: no rain, cars or people. Only 3.7% of background pixels changed
frame to frame, and that was the umbrella dripping. Every look inherits the base's
background, so the flaw multiplies by the number of looks.

- **Cause:** the first/last keyframes had the street melted into bokeh, so there were
  no cars or people for H3 to animate. The prompt also said "simple, even motion".
- **Fix, both halves needed:** (1) the keyframes show a *readable* background, with
  named moving elements (cabs with headlights, pedestrians with umbrellas, visible
  rain streaks); (2) the base prompt names continuous background motion and its
  direction, and the look template says "keep ALL the background motion of
  <Video 1> exactly".
- **Gate:** `make_videos.py walk` measures background motion on the base (the share
  of pixels outside the central subject column changing >6 levels per frame) and
  refuses to spend on looks below 10%. v2 scored 14.9% (base), 15.2% and 14.8%
  (looks), so the looks keep the motion. Alignment stayed at 0 / -1 frame offset.
- Check this BEFORE rendering looks. v1's looks ($1.30) were wasted.

## Full 9-look run (stage 2, 2026-09-29)

All 9 looks rendered with 0 API failures. 8 of 9 held the lock: best offset
0 or +1 frame, background motion 14.8–16.5%. **One failed silently:** "she
holds a bunch of red roses instead of the crane" came back as a big bouquet
held near the lens. H3 zoomed the camera to feature the new object, which
gave a best offset of -4 and an edge diff of 11.3, against 5–7 for the good
looks.

- **Object-swap looks must pin size, position and camera.** The reroll
  prompt that passed (offset 0, edge diff 3.5): "three small red roses ...
  the same size as the crane and in exactly the same place between her thumb
  and forefinger; the camera distance, framing, her head position and the
  umbrella pole are unchanged, no zoom". Outfit and hair looks don't need
  this; the ones that change a held object do.
- **Auto-flag rule:** best offset beyond ±1 or an edge diff far above its
  siblings means the look is misaligned. Reroll only that look ($0.65); the
  generator skips outputs already on disk.
- **Object-swap looks break the relay's story.** The user watched v1 and
  flagged: "one of the outfit change scenes still has a rose for the crane."
  Swapping out the RELAY object (the thing the whole reel follows) reads as
  an error, even for half a second. In a relay reel, change only clothes,
  hair or style; never replace the relay object. v2 dropped the roses look.
- **Cut order:** bracket the run with the base look (base → L1…L8 → base) so
  both seams into and out of the sequence join the outfit the relay stills
  show. Split the base timeline evenly across the 10 slots (about 12–14
  frames each), at original timecodes.
- **Assembly:** sample the looks from the BASE timeline (look *k* supplies its
  own frames for its slot). The looks share the base's frame count, so indices
  map 1:1. Don't use `templates/relay_assemble.py`'s even-sampling retime;
  see "Assembly" in `match-cut-relay-transitions.md`.
