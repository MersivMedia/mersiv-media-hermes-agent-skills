# Match-cut relay: many shots that read as one continuous take

**Status (2026-09-29 sizzle reel "Pass It On"): the keyframe chain ran four
rounds for $4.27 on stills: v1 $0.55 (nano-banana, stylized), v2 $0.44
(photoreal prompts), v3 $2.90 (nano-banana-pro 2K), v4 $0.39 (a K1
perspective fix). Video stage 1 has RUN** (S1 + rapid-change base + 2 looks,
$2.73, 0 failures). Both halves are proven: the first/last-frame seams hold, and the
looks are frame-locked to the base (0-frame offset, identical pose). See
`rapid-change-sequence.md`. The user still rejected the v1 walk for a frozen
background (3.7% moving). The v2 redo, with readable street keyframes, named
background motion and an automatic ≥10% gate before the looks, measured 14.9%
and cost $2.25. The metric passing isn't enough: the user judges the clip.

## Measured: H3 first/last-frame video on Replicate (stage 1, 2026-09-29)

- **Long prompts are fine.** Prompts of 500–1,600 chars (shot action +
  time/light/weather sentence + a film-frame style block + negatives) were
  accepted with no truncation error. Don't trim for length.
- **Seams hold.** First frame vs first keyframe: PSNR 30–34 dB. Last frame vs
  last keyframe: 23–32 dB. Visually the same framing and the same relay-object
  position. PSNR is lower on busy nadir city frames because fine detail is
  regenerated; judge the seam from a 4-tile side-by-side (still | first frame
  | last frame | still), not from the number.
- **Output shape:** 2560×1440 h264 at 24 fps with an **AAC audio track
  included** (strip it at assembly; the music bed goes on top). `duration: 6`
  gave 158 frames / 6.58 s and `duration: 5` gave 124 frames / 5.17 s, so
  expect about 0.2–0.6 s more than asked; trim to the timeline in ffmpeg.
- **Wall time:** 275–408 s per clip, and 2 clips in parallel didn't slow each
  other. Submit from a background process with notify, and poll every 10 s up
  to 30 min.
- **Call shape:** `first_frame_image` + `last_frame_image` as files-API URLs,
  `ratio: "adaptive"`, `resolution: "2K"`. A look edit uses
  `reference_video_urls: [base_output_url]` + `ratio: "16:9"`, and the
  replicate.delivery URL of the base output works directly as the reference
  (no re-upload). Start the look edits only after the base succeeds.
- S1 (a rooftop release, tilt straight down, fall between towers) came out
  photoreal with continuous motion: no warping, no duplicate object. The
  base walk kept her face and coat consistent across 5 s.

## Keyframe light sources imply subjects: write them into the shot

The user reviewed the stills and spotted that the whale-shark-throat frame
was lit by what reads as a **scuba diver's torch**, so the shot into it had to
include scuba divers. Any strong motivated light in a keyframe (a torch beam,
headlights, a lantern, a phone screen) implies someone or something holding
it. When you read `STATES` off the images, also list the **implied light
sources**. Then either add the subject to the shot that ends on that frame
(the divers swim in with torches, then peel away so only the beam remains at
the seam) or regenerate the still without the source. Update the frame's
STATE text and the next shot's prompt so both name the same source ("the
diver's cool-white torch beam"), keeping the seam consistent.

## User preferences learned across the review rounds (apply from round 1)

- **"Keep all the styles highly realistic."** No anime, claymation, paper
  worlds or ink wash, even for "abstract/fantastical" beats. The user cut
  those scenes and asked for historical, future, weird-real-creatures and
  nature scenes instead. Fantastical ideas (aliens, a planet) must be shot as
  a real location with practical creature effects.
- **"Need more photorealism"** came even after photoreal prompts on
  nano-banana. Start on **`google/nano-banana-pro` at 2K** ($0.15/image,
  2752×1536). Use a film-frame style suffix on every prompt: a named cinema
  camera and lens, natural or motivated light, skin pores, atmosphere
  (dust/moisture/haze). Add explicit negatives: no oversaturation, no HDR
  glow, no plastic skin, no fantasy lighting, no CGI look.
- **Relay-object scale must be physically plausible for the world.** The user
  flagged the crane as "too large" between skyscrapers and again underwater.
  A 12 cm object is a SPECK in a vertigo shot or a reef. Write an explicit
  size for EVERY keyframe as a percent of frame width, compared against
  things in the scene: "about 3% of the image width, far smaller than the sea
  turtle, the manta ray and even the individual fish". Close-up and hand-held
  frames can be about 8–15%.
- Wardrobe notes (e.g. "the girl in the rain should have a coat on") go into
  every keyframe AND shot prompt where that subject appears.
- Feel free to reorder so opposites sit side by side (ancient Egypt → 2150
  megacity; still rainforest → teeming reef).

## Every shot prompt must describe the time / light / weather CHANGE

User instruction: "Make sure the video prompts for transitions describe the
changes in time, lighting, and weather from the previous frame." When first
and last frames sit in different worlds, an interpolator given only the
content change will cross-fade the light. Naming the change turns it into
something that looks motivated (a time-lapse, a sun climbing, a storm rolling
in, a shadow blotting out the sun).

1. **Read each keyframe's state off the generated IMAGE, not off its prompt.**
   Record time of day, key light (source, direction in frame, warm/cool),
   ambient/fill, weather/atmosphere and palette per keyframe. One vision pass
   over the contact sheet works. Keep these in a `STATES = {"K0": ...}` dict
   in the plan. The images often disagree with the prompt that produced them:
   the K2 storm carried into K3, and the "dusk" megacity came back as midday.
2. **Per shot, add a `tlw` field** giving the from → to summary for the sheet,
   and append a full sentence to the prompt. Start the sentence with "Time,
   light and weather:". Say HOW each property changes and give it a cause:
   "the fall compresses a whole day into seconds like a time-lapse: warm
   morning sun drains through dusk into night, neon and headlights flicker
   on, storm clouds roll over, the first drops hit the lens, then it pours in
   sheets".
3. **Held-constant shots say so explicitly.** The rapid-change base clip and
   every look edit say "hold the time, light and weather constant: night,
   steady rain, the same neon bokeh and cool fill", and the edit template says
   the rain wets the new outfit the same way. Without that, each 0.5 s cut
   flickers.
4. **Sheet:** add a "Time / light / weather change" column. Insert it AFTER
   "Est. cost" so the cost-column index and SUM formula don't move. Still
   rows carry "State: ..." so a redo keeps consistent light.
5. Verify with a script that every video row's prompt contains the sentence,
   that every row matches the header width, and that the sheet read-back
   shows 0 mismatches.

## Perspective must be stated geometrically (vertigo / nadir shots)

"Looking straight down the facade" produced a tilted camera with **sky down
one side**, and the user rejected it ("perspective is off with the sky on the
side"). What worked (2 of 4 candidates were right, on both nano-banana-pro and
flux-2-pro): "Nadir aerial photograph: the camera points exactly straight
down, ninety degrees ... the towers all around lean inward and converge toward
the centre ... every edge of the frame is building facade and rooftop, **no
sky visible anywhere, no horizon**." Apply the same rule to any extreme
angle: give the camera axis in degrees and name what must fill the frame
edges, since a shot name alone isn't enough.

## Measured failures of the edit chain at scale (v2/v3)

- **"Keep EXACTLY the same size" fights any size change.** Editing from a
  large-crane predecessor kept it large (15% width) no matter what the new
  prompt said. What worked, in order:
  1. A **fresh text-to-image generation** for the frame where scale changes.
     This got the vertigo frame from 15% to 4% width.
  2. A **dedicated shrink-only edit** of an existing good frame: "Make the
     crane MUCH smaller: about 3% of the image width ... keep everything
     else exactly as it is". This worked on the reef and the throat frames.
  Don't put a size change and a world change in the same edit.
- **End frame on pure black: the model duplicated the object** (two cranes)
  and added surfaces. Build that frame in code: generate a clean product
  shot, crop the object by a luminance threshold, scale it to about 10–11%
  width, and paste it at the right third on a #000000 canvas. Then check that
  the left two-thirds is exactly 0.
- **Red-mask centroid QC breaks at 2K on real scenes.** It locked onto red
  taxis, signs and clownfish, and reported "NOT FOUND" on dark frames. Treat
  the metric as a hint only. The real gate is a full-size visual check of
  each frame plus the contact sheet. With 2K chains, placement between
  neighbours no longer holds at ≤3%, and that is acceptable: the seam still
  matches because K_i is both the last frame of one shot and the first frame
  of the next.
- Realism upgrades push crimson toward pink/magenta. Say "deep crimson-red
  (saturated red, not pink)" in the object description and in the keep
  clause. Magenta at reef depth is physically correct, so leave it.
- **Budget overrun:** the v3 estimate of $1.95 became $2.90 after scale
  fixes. Plan for about 50% redos on a first photoreal pass, and report the
  overrun and its cause plainly.
- **Candidate-batch pattern:** write a shell script that runs 3–5 parallel
  `redo_one.py` candidates (fresh generation vs edit vs another model) for
  the problem frames, build a labelled mini contact sheet, pick the winners,
  and **move** the rejected frames to `_rejected/vN/` (never delete them).
  Put the file moves in a script, because inline `mv` chains triggered
  approval prompts that timed out.

## Measured: the keyframe chain works

- K0 came from flux-2-pro (1888×1072). K1–K12 came from nano-banana edits,
  each from its predecessor (1344×768, about 10 s and $0.039 each). The
  resolutions differ, so normalise everything to 1920×1080 at assembly.
- The crane's centroid across K0→K5 drifted **0.000–0.026 of frame width**
  between neighbours. The "keep EXACTLY where it is" edit template holds
  placement well.
- **Failure: an edit that only says "keep" can return nearly the same frame.**
  The first K4 ("she releases it toward camera", written as KEEP + small
  delta) came back almost identical to K3, which makes a dead hand-off where
  nothing happens across the shot. Every keyframe prompt must state the NEW
  state positively and concretely: pose, facing, hand shape, object size
  change ("turned to face the camera, palm open and flat, the crane lifting
  off it, clearly larger because nearer the lens"). Keep the placement clause
  only for the relay object.
- **The keyframe chain can change the plan.** The rainstorm from K2 carried
  into K3, so the planned "overcast sidewalk" walk became a neon night street.
  Once keyframes exist, re-read each downstream shot prompt against the actual
  images, then re-sync the sheet.
- **Red-mask centroid QC gives false positives** when the world is also red
  (anime fire: 0.17 "drift" that was really the flames). Treat metric drift
  as "look at this frame", not as a verdict. Always check a contact sheet
  visually as well: 4 columns, 480×270 tiles, id and description labels, and
  a centre crosshair on every tile. Look at flagged frames at full size.
- Crane readability is the real risk on busy frames (fire/ice seam). Put a
  "keep the crane clearly readable against X" clause in that shot's prompt.
- Keep rejected keyframes in `keyframes/_rejected/` and delete the
  `K<n>.png` to regenerate. The generator skips files that already exist, so
  a rerun costs only the replaced frame.

## Runtime planning and creative direction (user preferences)

- The user wanted **60 s** and asked for more shots rather than accepting a
  shorter linked reel. Linked shots eat runtime slowly (5 s shots, 4 s
  bridges), so a 60 s reel needed about 12 shots + 13 keyframes (~$17.30 at
  H3 2K with the buffer). Quote the runtime next to the price.
- **Energy contrast:** alternate CALM / CHAOS (plus FANTASTICAL / TENSION /
  RESOLVE) and give the sheet a colour-coded Energy column and a Timecode
  column. For music, do NOT put cue timecodes in the music prompt: the
  model ignores them. Generate a steady bed plus separate impact and riser
  SFX, and place the hits on the cut times in code (see "Measured: full reel
  assembly" and `audio-models.md`).
- Openers: a scenic, high-vantage establishing shot (e.g. the top of a
  supertall above a sea of cloud) before the chaos.
- A good transition device is a **swallow**: follow the object down a
  creature's throat, and let bioluminescent specks stretch into starlight so
  the throat opens into space. Use one of these per reel.
- Ending: the relay object settles beside the logo. The last keyframe is the
  object at rest on the brand's background colour, in the right third. The
  logo and tagline are composited in code, never generated. **The user
  corrected the placement:** the logo + tagline lockup must be **centred on
  the screen** (both axes, measured about 0.50 × 0.50 in the final frame),
  not placed in the empty left side. Check it doesn't overlap the object;
  move the object further right if it does. The end card holds about 3.5 s.
  Longer reads as dead air.

The user asked for this technique by name. They want a reel where a subject in
one shot passes an object to, or looks toward, the next scene, so the whole
thing plays almost like one continuous shot. The backgrounds can be completely
different. An object ends a shot at one screen position and starts the next
shot at the **same position, same size, same motion**, in a new world.

## Core idea: shared hand-off keyframes

The seam is a **still image**, not a video. For N shots, make N+1 keyframes
K0..KN. Keyframe K_i is BOTH the last frame of shot i and the first frame of
shot i+1. Generate each shot as first-frame → last-frame interpolation (H3
`first_frame_image` + `last_frame_image`, or Seedance `image` +
`last_frame_image`). Every cut then lands on an identical frame, so the eye
reads motion rather than a cut.

```
K0 --S1--> K1 --S2--> K2 --S3--> K3 ...
           ^ last frame of S1 AND first frame of S2
```

## Building the keyframes (the part that makes it work)

1. **K0 from text** (for this user, `google/nano-banana-pro` 2K with the
   film-frame style suffix; flux-2-pro only as a candidate). Give the relay
   object a simple, readable silhouette at a scale that is plausible for the
   scene. A small red paper origami crane is a good relay object: high
   contrast, rigid shape, and plausible in any world.
2. **K_{i+1} = image edit of K_i** (nano-banana-pro `image_input`; plain
   nano-banana and flux-kontext were rejected as not photoreal enough).
   Prompt template:
   > "Keep the <object> EXACTLY where it is in the frame: same pixel position,
   > same size, same angle, same lighting direction on it. Replace everything
   > else with <new world>."
   Editing from the previous keyframe (not generating fresh) is what holds the
   object's placement. Put the object's target SIZE in the edit too, and when
   the size changes a lot, generate fresh or do a separate shrink edit (see
   "Measured failures"). Avoid stylized worlds (anime/claymation) for this
   user unless asked; they want everything photoreal.
3. **Check the stills before spending on video.** Stills cost $0.15 each; a
   bad seam found after the video costs about $0.65. The centroid metric is a
   hint only at 2K (see "Measured failures"). The real gate is the
   self-review checklist below, done at full size. Placement may move WITHIN
   a shot: the seam still matches because K_i is both the last frame of one
   shot and the first frame of the next.

## Self-review checklist before showing stills (what this user catches)

Over four review rounds the user found each of these by eye. Run every one of
them yourself first, frame by frame at full size:
- **Photoreal?** It should read as a film frame, not CGI: no HDR glow,
  plastic skin, oversaturation or game-like creatures.
- **Coherent perspective?** No sky on the side of a nadir shot, and no
  impossible horizon.
- **Plausible object scale** for this world, compared against named things in
  the frame (towers, fish, a hand).
- **Implied light sources** (a torch, headlights) have a subject in the shot
  that ends on this frame.
- **Wardrobe and continuity notes** the user gave are present, e.g. the coat
  in the rain.
- **Dead hand-off:** K_i ≈ K_{i+1}, so nothing happens across the shot.
- **Background life.** Any street, crowd, rain or traffic scene must show
  readable moving elements in BOTH bracketing stills, not melted into
  bokeh. Otherwise the video's background comes out frozen (see
  `rapid-change-sequence.md`, 3.7% measured).
- **Does the relay object TRAVEL?** After rendering, the median motion of
  every world-change shot should be above about 4. Anything lower needs a
  launch, a chase and a boundary crossing (see "Transitions must TRAVEL").
- **Is a single physical journey split across several short shots?** (a fall
  from a rooftop to a street, a dive from reef to throat). That pulses at every
  join and the user calls it "choppy". Plan it as one 8–15 s shot (see "Long
  continuous shots"). Check with `scripts/motion_profile.py` for per-second
  dips toward about 4.
- **Does the background keep moving right up to the last frame?** H3 tends to freeze the scene as it
  converges on `last_frame_image` (the cabs parked for the final 4 s of a 15 s shot). Measure road or
  traffic flow over the final seconds, not just the clip median.
- **Does traffic keep its direction across each seam?** The next shot regenerates the traffic from the
  shared frame and can flip it. Measure the outgoing shot's direction with optical flow and name it in the
  incoming shot's prompt. Flow is confounded while the camera tilts or dives, so confirm by eye on a
  1/6 s frame strip before calling it either way.
- **Real-world insignia or logos** on generated wardrobe (a NASA meatball and
  a US flag appeared on a "NASA-style spacesuit"). Don't prompt for a real
  organisation's style; say "unbranded, no insignia, no flags". Flag any that
  appear before commercial use.
- **Is the object ever drawn OVER a solid surface** (floor, slab, glass, wall) that it should pass beside or
  behind? That reads as passing through it, and the user caught it on two renders my QC had passed. Check a
  1/12 s grid at every place the object crosses an obstacle. Before rendering, also check whether the camera path
  between the first and last frames has to cross a solid object. If it does, fix the endpoints, because H3
  takes the shortest path whatever the prompt says.

## Show every arrival and every transition on screen (user corrections)

The user asked for missing beats twice in one review: "there also needs to
be a transition of the crane flying into her hand from above" and "the
transition from day into night and rain". A shot summary like "she catches
it" or "morning → night" is NOT enough:
- **Arrivals:** when the relay object changes carrier (sky → hand, hand →
  water), the shot must show it arriving: from where, how it moves, what the
  receiver does. For example: "from above, the crane spirals down through
  the rain, the camera descending with it; she looks up, tilts the umbrella
  back, raises her open palm; it lands softly in her hand".
- **Time-of-day and weather jumps** get a staged, timed beat list inside
  the shot. For example: 0–1.5 s morning sun; 1.5–3 s shadows race across
  the facades, sunset, dusk, windows light up floor by floor; 3–4 s night,
  neon snaps on, storm clouds roll in; 4–5 s first drops on the lens, then
  sheets of rain. Use "make the passage of time unmistakable". Give such
  shots 5 s, not 4, and take the time from a calm shot to hold the runtime.
- Before showing a plan, walk the relay object through every seam and ask:
  is each change of carrier, world, time and weather *visible on screen*, or
  only implied by the keyframes?
- **Duplicated relay object**, or one that has turned pink or restyled.

Report every weak spot you found but chose to keep, e.g. fake signage text or
a CG-leaning alien, in place of silently shipping it.

## Shot prompts

- Use H3's reference labels: "`<Picture 1>` is the first frame and
  `<Picture 2>` is the last frame." Name the object's action, its exit
  direction and the camera move in words, so the motion leaving shot N
  matches the motion entering shot N+1 ("rises toward the lens", "camera
  locked to it at frame centre").
- Say "continuous single take, no cut". Do NOT say "the <object> holds its
  screen position" for the whole shot: H3 obeys it literally and renders a
  hovering object over a cross-fade (see "Transitions must TRAVEL" below).
  Pin only the first and last frames.
- Hand-offs between people: a hand enters and takes the object, or a subject
  looks or throws toward the direction the next shot continues.
- World jumps (Egypt → a 2150 megacity → rainforest) happen *inside* a shot:
  describe the world transforming while the object persists, and give the
  transformation a physical cause (a time-lapse, rain stopping mid-air, a
  shadow). Keep it photoreal; rendering-style jumps (anime, claymation) were
  cut by this user.

## Optional short transition clips

If a direct seam still pops, generate a 2–4 s bridge clip between the last
frame of shot N and a new keyframe, and overlap by a few frames. H3's minimum
length is 4 s, so trim the bridge in ffmpeg. This adds cost, so use it only
on seams that fail the check.

## Assembly

**User rejected reel v1: "there are pauses from the same frames being shown
twice in the cut, the transitions need to be smoother between some scenes."**
`templates/relay_assemble.py` retimes each clip into a fixed slot by sampling
frame indices evenly. That repeats frames whenever a slot is longer than the
clip's usable frames, and H3 also bakes in its own holds. v1 had **134
repeated frames**. Don't use even-sampling retiming. The rules below replaced it:

1. **Play every clip at native speed; show each source frame once.** Let the
   timeline follow the clips' real lengths rather than fixed slots. (v2
   measured 0 repeated frames inside all 12 shots.)
2. **Trim H3's own holds.** H3 first/last-frame clips ease in and out, and
   often end on frozen frames: up to 32 on the fade-to-black shot, 18 and 12
   on calm shots. Per clip, compute the mean abs luma diff between frames
   (320×180 gray). Cut frozen tail frames (motion < 0.2), and trim ease-in and
   ease-out frames (motion < 12% of the clip's median) up to 6 per side. Keep
   the opening shot's head.
3. **Seams: best-match cut plus a short dissolve.** A hard cut on the shared
   keyframe still jumped at 3 seams (PSNR 15–23 dB across the cut). Search
   the last 7 frames of A × the first 7 of B for the highest-PSNR pair (with a
   0.1 dB penalty per trimmed frame). Cut there with a centred smoothstep
   crossfade of 4 frames (6 if the match is < 26 dB). Clamp the blend window
   inside both clips. Plan-stage scores: all 11 seams 29–41 dB.
4. **Fill a fixed runtime by slowing CALM shots**, never by holding frames:
   up to 1.2× with `minterpolate=mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1`.
   Motion compensation needs 1080p; it ran at about 1 frame/s on this 2-core
   box, so budget minutes. minterpolate delivers 1–2 frames short. Append
   `tpad=stop_mode=clone:stop=6` and cut to the exact count with `-frames:v`.
   Cache the output.
5. **Rapid-change inside the relay:** bracket it with the base look at both
   ends (base → looks → base), so both of its seams join the same outfit.
6. QC the final file for repeated frames (neighbour diff < 0.15) and for
   motion spikes (> 2.5× the median of ±6 neighbours + 1). Decode as uint8
   and diff pairwise: a float32 decode of 1,440 frames was OOM-killed on this
   2 GB box.

Status: rules 1–6 verified on the v3 file: 0 repeated frames inside all 12
shots, every seam ≥ 25 dB, no motion spike at any seam, logo centroid
0.499 × 0.498, -14.2 LUFS. The user watched v3 and called it "pretty good",
then moved on to shot content (next section).

**Superseded for seams (2026-10-01): the user supplied their own stitching
method. Use it as the default:** trim 2–3 extra frames off each side, overlap
0.5–1 s, and blend with an optical-flow cross-dissolve
(`scripts/flowblend_worker.py`). It replaces rule 3's 4-frame plain blend.
Rules 1, 2, 4, 5 and 6 still apply. The longer overlaps eat runtime (7 seams ×
0.5 s ≈ 3.3 s), so plan for it up front: slow calm shots ≤20% (rule 4), or
quote a shorter overlap (8 frames) as the alternative. Details and
measurements are in the section "Stitching: trim + overlap + optical-flow
cross-dissolve" at the end. Reel v9 used it. The user's verdict was pending at
the end of the session.

## Transitions must TRAVEL between worlds (user correction on v3)

User: "the crane needs to move more between certain scenes... the crane just
stays in the same place and doesn't really move or do anything. We should use
more camera movement." They named street → Egypt and future → nature as bad,
and **forest → water as the model** ("a really good example of it moving
between worlds").

**Measured cause:** median frame-to-frame motion per clip (mean abs luma diff,
320×180). The shots the user liked: forest → water 8.9, the dive 11.5, the
catch 11.7, rooftop 8.3. The shots they rejected: street → Egypt 2.2,
future → nature 1.5. Egypt → future (2.7) and the fade to void (1.1) were
nearly as static. **Rule of thumb: a world-change shot under about 4 reads as
static to this user.** Run the motion metric over every shot before assembly
and flag the low ones yourself.

**Prompt cause:** the weak prompts described a dissolve ("the street washes
away into", "the towers dissolve into") plus the global HOLD clause ("the
crane holds its screen position at the start and end of the shot"). H3 read
this as a near-still crane over a cross-fade. The strong prompt had:
1. **A physical event that moves the object:** "a gust knocks the crane off
   the branch; it tumbles into the pool".
2. **The camera crossing a physical boundary with it:** breaking through the
   water's surface.
3. **A new world revealed on the far side** of that boundary.

**Rewrite pattern for any world-change shot:**
- Replace HOLD with a TRAVEL clause: "Only the very first and very last
  frames match the pictures; in between, the crane and the camera travel a
  long way at speed and never hold still."
- Give the object a launch (it springs off a palm, folds its wings and dives),
  a camera move that chases it (whip tilt up, nose-dive follow, crash zoom),
  and a boundary to punch through: the cloud layer (street → above the storm
  at dawn → dive to the Nile), the leaf canopy (future city → jungle
  overgrowing its base → rainforest floor), the water surface, a throat.
- Split the time/light/weather sentence across the boundary: below vs above
  the clouds, above vs beneath the canopy.
- Give these shots 5 s, not 4; take the time from the end-card hold or a
  calm stretch.
- Never use "dissolve", "washes away" or "fades into" as the transition
  mechanism in a shot prompt. Those words produce cross-fades.

**Verified result (v4):** re-rendering the 3 weak shots with this pattern
($1.82, 0 failures) raised their median motion from 2.2 / 2.7 / 1.5 to
**8.4 / 10.0 / 11.9**. Their first and last frames still matched the
keyframes at 34–39 dB, so the first/last-frame lock survives aggressive
mid-shot camera motion. Seams in the assembled v4 all scored 26–40 dB.
**Write every world-change shot this way from the first draft.** Don't wait
for the user to find the static ones.

Also:
- Cut on the music beat where the timeline allows. A 120 BPM bed puts a beat
  every 0.5 s. Place the impacts on the ACTUAL cut times the assembler
  reports, not on the planned timecodes.
- Build the end card in code: the last frame plus a logo mask fading in.
- Verify the FINAL file, not just the clips: the frame count, the seam PSNR
  across every cut (compared with the within-shot median), and a contact sheet
  of the frame before and after each cut.
- Tell the user you checked frames and measurements but did not watch the reel
  in real time. Their watch-through is the real test.

## Planning deliverable the user expects

Before any generation, give the user a **Google Sheet** with one row per
keyframe, shot and edit. Columns: order, id, type, shot type/camera angle,
subject, style, camera move, model, inputs (first/last keyframe ids), length,
unit price, estimated cost, **full prompt**, notes. Include a summary tab
with the concept, how the seams work, the format, a cost breakdown with a
reroll buffer, and the staged gate. Read every cell back from the API and diff
it against the source data before sending the link. Keep the plan as data
(Python modules) so the sheet and the generation script can't drift apart.

## Stage-1 gate

Stage 1 is one first/last-frame shot plus the rapid-change base and 2 looks.
It was quoted at $2.60 and actually cost $2.73: a 6 s shot bills 6 s, and the
estimate assumed 5.

Gate checks:
- **Each seam:** a 4-tile still | first frame | last frame | still image.
- **Each look:** a same-frame grid, and a ±6-frame offset sweep against the
  base.
- **Preview:** a 3 s beat-cut preview.

Write the QC script WHILE the renders run, so the check follows immediately.

Before stage 2, upload the clips, the preview and the QC grids to a Drive
`stage1/` folder, and verify the sizes read back. Wrap QC and upload
pipelines in a `.sh` file. An inline `python ... | python3 -c` summary pipe
triggered an approval prompt that timed out, and the check never ran.

## Cost model (verified live 2026-09-29)

**Actual end-to-end for the 60 s reel through v7 plus two failed release patches and an end-frame-only patch: $31.89**
(stills $4.57, H3 video $26.52, music $0.80), against an $18.72 plan. Two $0.52 patches were spent on the same balcony defect because
endpoint geometry wasn't checked first (see the pitfall at the end). v6 → v7 added round 2 of long shots ($4.16) and a 4 s release patch ($0.52). The user called v6 "much
better, I like everything except" one 2 s span, so review rounds converge. Quote about 1.6× the plan for a reel the
user reviews frame by frame, and say up front that each round is priced and approved separately.
Earlier status (v5, $26.04): stills $4.57,
H3 video $20.67, music $0.80, against an $18.72 plan. The overrun came from the stills
(4 review rounds) and four video redos: the frozen-background walk ($1.95), one
misaligned look ($0.65), three static transitions ($1.82), and two long shots replacing
five choppy relay shots ($2.99). Quote about 1.4× the plan for a reel the user reviews visually. Most of the redos would have been avoided by
the self-review checklist above (background life, TRAVEL prompts, pinned object swaps, long shots for journeys).

Working scripts (not in the skill, reusable): `~/.hermes/data/sizzle-reel/`:
`plan*.py` (the plan as data), `make_keyframes.py`, `make_videos.py` (stages plus a
background-motion gate), `assemble_v3.py` (the working assembler: native speed, trims,
best-match seams, minterpolate slow-down, one-decoder-at-a-time), and `qc_reel_v3.py`.

H3 2K $0.13/s; nano-banana $0.039/image; nano-banana-pro 2K $0.15/image
(the photoreal default); flux-2-pro about $0.045 for a 16:9 image. A 60 s
reel with 12 shots and 13 nano-banana-pro keyframes came to about $18.72,
including the buffer. The actual keyframe spend over four rounds was $4.27, against a ~$1.95
single-pass estimate, so budget about 2× for stills when the user iterates visually. An 8-shot relay plus a 9-look rapid-change sequence plus 9 keyframes
came to about $13.72 including a 25% buffer on video, for about 41 s of
runtime. The linked format produces a shorter reel for the same number of
shots, so tell the user the runtime alongside the price.

Related: `rapid-change-sequence.md` (it slots in as one shot of the relay: the
base clip's first and last frames are relay keyframes).

## Measured: full reel assembly (2026-09-29, "Pass It On", 60 s)

Stage 2 (10 first/last-frame shots + 7 looks, 6 in flight) cost $10.53, with 0
failures, in about 17 min wall time. Scripts live in `~/.hermes/data/sizzle-reel/`
(`make_videos.py`, `assemble.py`, `qc_stage2.py`, `qc_reel.py`).

- **Seams hold in the final file.** Where frame 0 of each clip after the first
  is dropped (it repeats the previous clip's last frame), PSNR across every relay
  seam was 29–39 dB, against a median of 27 dB between neighbouring frames inside
  a shot. So the cuts are smoother than ordinary motion.
- **Seam PSNR on the SAMPLED v1 reel was 29–39 dB at most seams, but 3 seams
  (her scene → the quick changes, rooftop → dive, reef → divers) were 15–23
  dB, and the user saw them.** Report the worst seams, not the median.
- **Retiming:** do NOT sample frame indices evenly into a fixed slot; it
  repeats frames (see "Assembly"). Play clips at native speed and let the
  runtime follow them. Skip `setpts`, which drifts by a frame per clip.
- **One of 9 looks failed** by zooming in: "roses" became a big bouquet near the
  lens, with a -4 frame offset. The best-offset check flagged it. The fix was to
  give the replacement object's size and position explicitly, plus "no zoom", and
  reroll that one look ($0.65).
- **Music: stable-audio-2.5 ignores timestamps in a prompt.** A prompt with 8
  timed cues gave 60 BPM with 20 s of near-silence in the wrong places. What works:
  a CONTINUOUS bed at a stated BPM (detect its real grid, then `atempo` to exact),
  plus two isolated SFX (an impact and a riser) placed on the cut times in code.
  Duck the calm shot and loudnorm to -14 LUFS. Three calls cost $0.60.
- **End card:** the 320 px logo, upscaled 8x Lanczos, blurred and thresholded,
  gives clean edges at 1080p. Match the tagline weight by measuring the "I"
  stem width to cap height in the wordmark and picking the variable-font weight
  with the same ratio (Montserrat 575 for MERSIV). The first attempt measured the
  median stroke across the row, which picked up crossbars and came out too heavy.


## Pitfall: many concurrent 1440p decoders OOM a 2 GB box

The rapid-change Seq held one ffmpeg rawvideo decoder per look open at once (10 x 1440p). With about 1.2 GB
free, the encoder died mid-blend and Python only showed a bare BrokenPipe in `enc.stdin.write`.
The ffmpeg noise was also hidden because the log was filtered with `grep -v "Broken pipe"`.
Fix: keep only the current look's decoder open (close the others on switch), and send the encoder's
stderr to a file. Never filter the only log of a failing run.


## Long continuous shots (measured 2026-09-30)

**Trigger: the user says a sequence is "choppy".** v4's opening (rooftop → dive → street → catch, 3
relay shots) and reef → throat (2 shots) had NO repeated frames and NO single-frame jolts, so it was not
a frame problem. `scripts/motion_profile.py` on those time ranges showed the cause: motion per second
fell from ~15 to **3.9–4.4 at each internal join** (H3 eases into and out of every keyframe), then rose
again. A string of short first/last-frame shots pulses at every seam. Measure first, then quote the fix;
the user approved it at once: "take images from it and re run it as a longer generation".

The fix is to render the whole section as ONE H3 shot with first frame + last frame (H3 `duration` accepts 4–15 s). Results: L1 (15 s, rooftop -> dive -> day to
night -> catch) had no internal cuts, one crane throughout, and a visible time-lapse. L2 (8 s,
reef -> divers -> whale shark -> throat) worked but **H3 inserted a hard camera cut 1.5 s in**
(frame-to-frame motion 32.6 against a median of 7.6).

- **Prompt shape (mixed evidence, under test):** v5 used a "[Shot 1]" prefix plus a timed beat list
  ("0 to 2 seconds: ... 2 to 4 seconds: ..."). The 15 s L1 followed it beat by beat with no cut; the 8 s
  L2 got an H3-inserted hard cut. Suspected trigger: that shape reads like H3's multi-shot storyboard
  format. Round 2 (v6) dropped both, opening instead with "<Picture 1> is the first frame and <Picture 2>
  is the last frame. This is a single unbroken take with no cuts, no scene changes and no pauses; the
  camera moves continuously from the first frame to the last", followed by ONE continuous description.
  **Resolved in round 2+:** with the single-take shape, 6 renders had zero inserted cuts: 15 s L1b, 12 s L3,
  5 s S7b and two 4 s patches. (The one flag, in L1b, was a lightning flash.) Use the single-take shape as
  the rule. Always keep "there is only ever one crane". 2,000–2,200-char prompts were accepted.
- Cost/time: 15 s at 2K = $1.95 and took 633 s wall; 8 s = $1.04, 368 s. Run both in parallel.

- Always scan every long generation for internal cuts: flag frame i when
  motion[i] > 2.2 x median(motion[i-3..i+3]) + 3 (320x180 gray mean abs diff).
- An 8-frame `xfade` across the inserted cut brought the metric down (max 9.5 vs a median of 8.4),
  **but the user still saw it** on v5 ("there's a big frame difference in there"). A dissolve is a
  stopgap for a preview only. Budget a re-render of any long shot with an inserted cut, and tell the
  user the dissolve is there if you ship it meanwhile.
- A long shot can start from a frame taken out of an existing clip (here S8 frame 74, the first fully
  underwater frame by blue-minus-red). Splice clip[0..split] + long[1..] so the join is exact.
- H3 holds about 2 s on the first frame and about 2.5 s on the last in a 15 s shot. Trim by motion
  (keep 1 s of the start pose, cut 6 frames after the last frame with real motion).
- Do not motion-interpolate fast travel shots to fill time; only slow calm shots (here the void).
- **Status (v5, 2026-09-30): metrics passed, user review did not.** Both long shots replaced 5 relay
  shots and every automated check passed (0 repeated frames, all 9 seams 26–41 dB). The user still found
  three defects the checks were not looking for: cabs frozen for the last ~4 s of the 15 s opening,
  the dissolved-over cut, and a pause at the mouth plus a jolt and a still starfield at the throat → space
  join. Also, traffic reversed direction at the future → forest seam. All four are now in
  `background-motion-continuity.md` with optical-flow measurements. Round 2 ($4.16): a new 15 s opening
  that demands moving traffic through the last frame; ONE 12 s shot from the reef frame through the
  throat, the wormhole and the crash zoom (the throat/space join removed); and the forest dive with the
  traffic direction named. Reel total $30.20.
- **Merge across a pause-prone join:** when two adjacent shots join with a motion sag or a jolt (throat →
  space), render them as one longer shot from the earlier start frame to the later end frame instead of
  re-cutting the join.

**Plan long shots from the start where a section is one physical journey** (a fall, a dive, a chase).
Relay keyframes are still the right tool for jumps between worlds, but a journey through the same world
split into 3 short shots will pulse. Rough rule: one shot per world, or per boundary crossing.

## Delivery pitfall: large masters to Drive

An 87 MB master timed out (`TimeoutError: The read operation timed out`) as a single-request
`MediaFileUpload(resumable=True)` without a chunksize. What works: `chunksize=8 MB`, a
`req.next_chunk(num_retries=3)` loop with its own retry and backoff, skip files already present at the
right size, then list the folder and compare sizes. The partial first attempt had in fact landed the
master, and the size check caught that, so re-runs are idempotent.


## Round 2 of long shots (measured 2026-09-30, PASS IT ON v6)
- Prompt format matters: drop "[Shot 1]" and "0 to 2 s: ..." time segments. They read like H3's multi-shot storyboard
  syntax, and the v5 underwater take had an H3-inserted hard cut. With a plain single sentence starting "This is a single
  unbroken take with no cuts, no scene changes and no pauses", the 12 s reef->throat->space->planet take had ZERO cuts.
- Frozen background near the end frame: H3 freezes crowds/traffic as it converges on a still last frame (L1 road flow
  ~0.1 for the last 4 s). Saying "all still moving at full speed in the very last frame" fixed it (road flow 3-6).
  Measure it with optical flow on the road band (horizontal dx minus the global median), not by eye.
- Traffic direction across a seam: stating "every flying car keeps moving right to left exactly as in <Picture 1>" fixed
  the cars but not fully the train (still ~0.5 s wrong way while the camera tilts into the dive). Check direction per
  band with Farneback flow; a camera tilt can fake a direction, so confirm with a 1/8 s frame grid.
- The hard-jump scan false-positives on lightning (sky flashes white for 2-3 frames). Always look before "fixing".
- Merging a join into one longer take (throat + space) removed the join jolt; a short ease remains where the take
  converges on its last frame, so keep 0.5 s of margin in the timeline.
- Frame strips and grids for QC: ffmpeg `select='not(mod(n\,K))',scale=384:216,tile=6x4` writes one JPG with no
  image library needed. Use 1/8 s steps to find where a defect starts, and 1/6 s steps to judge direction.

## Surgical patch of the head of a kept long shot (measured 2026-09-30, v7)

User on v6: "I like everything except the very first couple seconds: the crane falls through the balcony instead of
over the edge, but the rest of the fall to the woman is perfect." **When the user approves most of a long take,
re-render ONLY the bad span.** Never re-roll the whole 15 s ($1.95), which risks losing the parts they liked.

1. **Localise the defect** with a 1/8 s frame grid over the first ~3 s. In this case the crane passed through the
   terrace floor at 1.6–2.1 s, and the fall was clean from about 2.2 s.
2. **Pick a clean end frame** a little after the defect (here 3.00 s = frame 72): object sharp, fully clear of the
   obstacle, no motion blur. Compare 4 candidates side by side. Export it at full 2560×1440 from the source clip
   (`select=eq(n\,72)`), never from the assembled reel.
3. **Render a 4 s patch** (H3 minimum, $0.52): the original start still → that extracted frame. Splice
   `patch + kept[73:]`, so the kept frame is shown once. Measured join motion was 13.0 against 10–12 on either
   side, so no jump. The opening grows by ~1 s, taken from the end-card hold.
4. **Spatial wording fixed the RELEASE but not the pass-through (user rejected twice).** Including the user's
   direction ("the hand should drop the crane over the rail"), the prompt had the hand reach out past the glass and
   let go on the outside, plus "never touches, crosses or passes through the glass, the rail or the floor". The
   hand-over-the-rail part rendered correctly. But the camera still dove down through the balcony slab, so the crane
   was drawn over dark concrete for ~0.5–0.75 s. My QC called that "briefly skimmed the outer lip, physically
   plausible". The user's verdict on v7: "the crane still looks like it's passing through the balcony and not to the
   side of it. It needs to get a little cut off by the base of the balcony." The cause is endpoint geometry, not
   wording: see the pitfall "endpoints on opposite sides of a solid object" below.
   **QC rule: if the relay object is drawn OVER any solid surface it should pass beside or behind, that is a defect.
   Never rationalise it as "plausible".** The user wants occlusion (the object partly hidden by the edge) as the
   visual proof that it went past the object, not through it.
5. The `make_long.py` source resolver checks `keyframes/long/<name>.png` before `keyframes/`, so extracted frames
   can serve as `start` or `end` without renaming.

Status: the splice mechanics (steps 1–3 and 5) are proven. The v7 join was clean and the rest of the fall was kept
as it was. The CONTENT of both 4 s patches (R1, R2) failed user review, as described in step 4.


## Pitfall: endpoints on opposite sides of a solid object force a pass-through (measured 2026-09-30)
Sizzle opening: first frame = camera ON the terrace behind a glass rail; last frame = camera OUTSIDE and BELOW the
balcony slab (slab underside at the top of frame). Two H3 renders (R1, R2, $0.52 each) both moved the camera straight
down through the terrace floor/slab, so the crane was drawn over dark concrete for ~0.5-0.75 s and read as passing
through the balcony. R2's prompt explicitly said "camera stays at the rail, does NOT sweep down across the balcony,
the base is always in front of the crane" and H3 ignored it: the interpolation takes the shortest path between the
two frames. Prompt wording cannot override endpoint geometry. A third render with the same endpoints would fail the
same way, so don't offer it.

Before rendering, check whether the camera path between the two endpoints crosses a solid object (floor, slab, wall,
glass). If it does, change the endpoints rather than the prompt.

**Rule (user correction): pin ONLY the frames that must match a neighbour.** I kept the rooftop still as the first
frame out of habit. The user asked: "Why don't you just use the end frame and let it decide the first frame based on
prompt and a reference image of the crane". The opening shot has no predecessor, so its first frame constrained
nothing and was the cause of the bad path. Before pinning a first or last frame, ask which seam it serves. The reel's
first shot needs only a last frame, and the last shot only a first frame, unless it's a code-built end card.

**Measured, end-frame-only (R3, 5 s, $0.65):** `last_frame_image` only, no `first_frame_image`, and a prompt that
invents the opening ("camera OUTSIDE the building just beyond the rail ... the concrete edge cuts off the lower half of
the crane ... the balcony is always in front of the crane"). H3 accepted it. The last frame matched the target at
35 dB, and the crane stayed on-model with no reference image, because the pinned last frame shows it large. It fixed
the defect the user named: the balcony base cut off the crane's lower half (frame 52), and the crane was never drawn
over concrete. It did NOT fully obey the camera position. H3 still started behind the rail and dropped the camera past
the slab, which gave a ~6-frame near-black wipe (mean luma 136 → 2 → 137 over frames 51–66). I offered three choices:
trim the black run to 2–3 frames (free), ship it uncut, or keep v7. The user answered "Show me 2" and wanted to judge
the uncut version on the phone before deciding, so v8 shipped with the full wipe. Their verdict was still pending at
session end. When a fix leaves a judgement-call artifact, build the free variant the user asks to see rather than
choosing for them. If they reject the wipe, trimming the near-black frames in the splice is the next free step.
- The opening grows to about 17 s (a 5 s patch plus L1b from frame 73). The assembler's L1 trim keeps 1 s of the start
  pose, and the end card absorbed the difference (3.5 s).
- A crane reference image was rejected: H3 returns `E006 First/last frames cannot be combined with reference media`
  (a free failure). Carry the object's identity through the pinned frame instead.
- QC for a camera passing through a solid: per-frame mean luma at 160×90. A run of frames near 0 in the middle of a
  daylight shot means the camera went inside or past geometry. Catch it before the user does.

Still untested: (a) about $1.19: a still with the camera already outside the rail (shown to the user first, $0.15),
then two clips. (b) Free: a match cut on the crane's screen position across the occluder.
Also tried and failed: painting the crane out wherever it overlaps the slab. When the slab fills the frame, only 2–4
frames have a usable edge, so the crane blinks out and back.
QC: a 1/12 s frame grid across the crossing, asking "is the crane drawn over the solid object?"


## Stitching: trim + overlap + optical-flow cross-dissolve (user method, 2026-10-01)
User-supplied editing technique, now `assemble_v3.py --flow` + `flowblend_worker.py` (sizzle-reel data dir):
1. Trim 2-3 frames off the end of clip A and the start of clip B (on top of the hold/ease trim) to drop the zone
   where the model decelerates into its pinned frame.
2. Overlap the clips by 0.5-1 s (12 frames at 24 fps used).
3. Cross-dissolve across the overlap (smoothstep weights).
4. Optical flow inside the dissolve: per frame at weight w, warp A forward by w*flow(A->B) and B back by
   (1-w)*flow(B->A) (Farneback at 480x270, scaled up), mix (1-w)*A' + w*B'. Pixels where forward/backward flow
   disagree by >3 px fall back to a plain dissolve so bad flow can't smear (occlusions, new content).
Measured on S6>S7b (future city, crane mid-frame): flow carried 85% of pixels (81% fully); full-res mid-frame crop
showed the plain dissolve doubling the crane, train and light trails while the flow blend kept one crisp crane and
far fainter doubles. Edge energy (a ghosting proxy) barely moved (6.19 vs 6.14), so judge by eye, not that number.
Costs: 7 seams x 0.5 s eat ~3.3 s of runtime (refill by slowing calm shots <=20% with minterpolate, or shorten the
end card); ~2 s CPU per blended 1080p frame on the 2-core box. cv2 lives in ~/.venvs/cdp (system python has none);
the worker speaks a tiny stdin protocol (8-byte float64 weight + two rgb24 frames) so the main assembler stays
on system python. The worker is packaged as `scripts/flowblend_worker.py` in this skill.

Assembler integration (what `--flow` changes):
- head += 2 for every clip except the first, and tail += 2 for every clip except the last, on top of the ease/hold trim.
- The seam overlap is fixed: A's last 12 kept frames over B's first 12. There's no best-match search, because the flow
  warp does the aligning.
- END_TARGET drops to 72 frames (3 s minimum), and SLOWABLE widens to the calm shots (Egypt, aliens, void). Watch the
  interpolated shots for warping in review.
- The long build (minterpolate for 3 shots at ~1 frame/s, plus 84 flow-blended frames, plus a 1440-frame encode) took
  about 40 min on the 2-core box. Run it in the background with notify and poll with `process(action="wait")`.
- Verify by comparing a full-res crop of the MIDDLE overlap frame, plain vs flow side by side. Seam PSNR drops (to
  22–33 dB) simply because the overlap is longer, so don't read that as a regression. The useful checks are the
  motion at the cut against the neighbouring shots (no spike) and whether you see doubled objects.

User review of v9 (flow stitch on all 7 seams): "a lot smoother in some parts but not others". The three seams
rejected were exactly the ones touching shots slowed x1.2 with minterpolate (to refill the ~3.3 s the 0.5 s overlaps
ate), plus RAPID>S5 where a 12-frame overlap reached back across a look boundary into the previous outfit. Measured
judder did NOT flag the interpolated shots (they scored as smooth as the sources), so trust the viewer over that metric.
Rule: apply the flow stitch per seam, not globally. Use it where both sides are native-speed footage with continuous
motion through the join; keep the short best-match blend on seams next to retimed shots, on look/edit boundaries, and
on calm static holds (aliens > void > end card). Don't buy back runtime with interpolation - shorten the end card or
pick shorter overlaps instead. `assemble_v3.py` takes FLOW_SEAMS (set of (A, B) pairs) for this.
