---
name: generative-media-pipeline-design
description: "Architect live/interactive generative video pipelines."
version: 1.0.0
author: Nous Research
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [architecture, generative-video, prd, latency, cost-modelling, state-machine, continuity]
    related_skills: [comfyui, replicate-api-generation, writing-plans, spike]
    category: creative
---

# Generative Media Pipeline Design

Architecture for systems that generate video/audio/images on a clock — live or
interactive generative film, branching narrative engines, real-time media tools,
anything where **latency, per-run cost, and visual continuity** all bind at once.

This is a *design* skill, not an API-calling skill. For actually invoking
providers see `comfyui` and `replicate-api-generation`.

## References and scripts

- `references/reference-plate-generation.md` — verified failure catalogue for
  generating character identity locks and location plates: the one-call-per-item
  rule, which prompt instructions are simply not honoured, luma normalization,
  expression-plate defects, and how to scope vision delegation. **Load this before
  generating any reference sheet.**
- `references/video-generation-providers.md` — the **clip** layer: which provider
  for stills vs video, fal endpoint-id and queue-URL traps, safety-checker false
  positives on your own reference plates, measured per-mode throughput, and
  render-stage bugs a dry-run catches. **Load this before rendering any clip.**
- `references/measured-drift-experiments.md` — A/B numbers from two renders of the
  same scene: identity drift with and without chaining, the 4-6s stability ceiling,
  per-mode inference timings, and costume-canon pixel evidence. **Cite these instead
  of re-deriving them** — each cost a paid render.
- `references/publishing-media-pipeline-repos.md` — shipping one of these projects
  to a public repo: secret audit at source/staged/remote, media exclusions,
  duplicate-module check, and what the README should actually carry.
- `references/agent-harness-operations.md` — running the pipeline *from* an agent
  harness: the LIVE / BETWEEN / GATE boundary, a ranked automate-vs-never table,
  task-prompt shapes for QC sweeps, gated regeneration, scoped vision review and
  drift analysis. **Load this before automating any part of the loop.**
- `references/scheduling-and-deadlines.md` — the **live schedule**: simulating it
  before building the player, why parallelism cannot rescue a just-in-time
  dependency, the two parameters that set the whole budget, measured concurrency
  and upload-cache numbers, and queue priority/pruning semantics with a
  fake-clock test list. **Load this before building any live or speculative
  render layer.**
- `scripts/plate_qc.py` — objective gates (neutrality / uniformity / distinctness)
  with measured thresholds. Run before spending vision-review budget.
- `scripts/plate_normalize.py` — luma-only gamma normalization onto a shared
  backdrop target, plus empirical outlier triage.
- `scripts/fal_client.py` — working fal queue client (upload / submit / poll /
  fetch) with the endpoint-id and app-path corrections already encoded.
- `scripts/cutaway_library.py` — character-free fallback clips: generator plus a
  no-repeat runtime picker and the tested failure-path integration shape. Use
  when the pipeline must never stall on a missed deadline.
- `scripts/render_queue.py` — deadline-ordered speculative queue with priority
  classes, branch-aware pruning, vote promotion and an injectable clock for
  deterministic tests. Pair with `references/scheduling-and-deadlines.md`.
- `references/live-screening-layer.md` — the **audience-facing layer**: why the
  server owns the playhead, HLS EVENT playlists for a stream still being
  written, vote-tally integrity and deterministic tie-breaking, the two
  transport bugs a GET-only smoke test misses, and verifying external
  reachability before handing anyone a URL. **Load this before building any
  player, voting surface or public endpoint.**
- `references/audience-identity-and-durability.md` — viewer identity (never
  `id(obj)`), append-only journalling and resume, the bitrate ladder, and why
  CPU-bound work in an async loop is a liveness bug.
- `references/audio-remix-and-stems.md` — the **audio** branch: route selection
  when an existing recording must survive, stem separation, the hosted-model
  fidelity ceiling, event-driven local synthesis that cannot drift, deriving a
  generation prompt by measuring a reference track, and the ffmpeg measurement
  traps that produce confidently wrong numbers. **Load this before any remix,
  cover, or audio-restyle work.**
- `references/model-hosting-status.md` — **the routing question**: which video
  models are API-only versus rentable, verified Seedance 2.5 input schema, the
  LTX-2.5 weight inventory with a fitted working set, and the four-step
  hosted-vs-rent heuristic. **Load this before recommending a provider or
  creating a pod** — a ComfyUI node pack existing for a model does not mean
  weights exist.
- `references/wan22-vace-v2v.md` — **reference-locked video-to-video without
  training**: the verified Wan 2.2 Fun VACE graph (dual-expert handoff,
  `trim_latent` wiring, exact file list and parameters), which model families
  support VACE at all, why 16 fps is the native rate and interpolation is the
  finishing step, and how to prove an output is not a silent passthrough.
  **Load this before training any motion or character LoRA** — conditioning
  usually solves the problem for free.
- `references/video-character-replacement.md` — **which node family to use at
  all** when swapping a person in existing footage: SCAIL-2 vs Animate vs
  VACE with measured identity/leak/warping numbers per configuration, why
  binary masks cannot substitute for colored per-identity masks, semantic
  person-selection in multi-subject footage, pose-skeleton caching, and the
  pixel metrics that judge an output you cannot see. **Load this before
  wiring any character-replacement graph** — the node choice is the whole
  decision, and parameter tuning cannot rescue a wrong one.
- `references/video-upscaling-and-finishing.md` — the **finishing** layer:
  why upscaling belongs in its own script, ESRGAN vs SeedVR2 with measured
  times, the SeedVR2 chunk-before-conditioning wiring trap and its own
  required VAE, generate-native/interpolate-for-delivery frame rates,
  measured VRAM ceilings that decide whether lanes can actually run in
  parallel, and why a full-frame side-by-side cannot compare two upscales.
  **Load this before building any upscale or delivery pass.**
- `references/rented-gpu-operations.md` — renting hardware when a hosted API
  cannot reach the fidelity bar: sizing VRAM against real weight files, SSH keys
  that must be injected at creation, quoted-vs-billed rates, why only the mounted
  volume survives, per-datacenter stock (§4.1, the one irreversible decision),
  latency when the deliverable is a screen recording (§4.2), reaching the service
  from a phone, and teardown discipline. **Load this before creating any pod.**
- `scripts/dc_stock.py` — per-datacenter GPU stock/price probe. **Run before
  creating any network volume**; the global stock list shows cards that exist in
  zero volume-capable regions, and a volume is datacenter-locked forever.
- `references/public-deployment-hardening.md` — the **last layer before
  strangers**: CDN cacheability rules, prefix independence, TLS through an
  existing proxy, making identity minting cost something, path allowlisting,
  and why a resumed process must regenerate every derived artifact. **Load this
  before exposing a screening publicly.**

## Rule 0: verify provider constraints BEFORE writing architecture

Every number in a media pipeline design cascades from clip length. Get it wrong
and the cost model, the interaction loop, and the concurrency requirements are
all wrong together.

A real failure from this skill's origin session: a PRD was written assuming
25-second shots. The actual provider ceiling was **15 seconds**. Blast radius:

| Assumption | Reality | Consequence |
|---|---|---|
| 25s shots | 15s max | Whole shot-duration column invalid |
| 40–60 shots/run | ~150 shots/run | Cost model **3x** understated |
| Per-shot branch points | ~6s vote window | Interaction model unusable |
| Serial generation fine | 12 clips in flight | Concurrency became a hard requirement |

The user caught it, not the agent. Before writing §Architecture, confirm and
write down, per model: **max duration, resolutions, available conditioning modes
(t2v / i2v / first-and-last-frame / reference-to-video), wall-clock speed, and
audio support.** Put them in a table in the document and state explicitly when a
later section depends on them.

Do not trust a model's marketing page for duration alone — check the API/endpoint
docs, and check the *specific variant* (a fast post-trained variant often trades
resolution and may differ in supported modes from its base model).

## Latency hiding

The enabling condition for interactive generative video is **generation faster
than playback**. Once true, invert the loop: never make the viewer wait, instead
speculatively render ahead during playback.

Three patterns, in order of leverage:

1. **Branch at the scene, not the shot.** A single clip is too short to give an
   audience time to read options and decide. Cluster 2–4 shots into a scene
   (20–40s) and make the scene the unit of branching.
2. **Head/tail split.** Only speculate the shots that play *while the choice is
   open* (the head). Generate the consequence shots (the tail) just-in-time once
   the decision resolves. Cuts waste from 50% to ~33% and, as a bonus, the tail
   can be authored *knowing the outcome* instead of hedging across both.
3. **Asymmetric lookahead depth.** Layers that differ in cost by orders of
   magnitude get different depths. Waste moves onto the layer where it is nearly
   free. But **cheap does not mean worth speculating deeply** — derive the depth,
   don't pick it:

   ```
   depth = ceil(generation_seconds_for_that_layer / scene_seconds) + 1
   ```

   At ~10–15s per prepared frame against ~35s scenes that gives **2**, not the
   3–4 an earlier version of this skill recommended. Measured utilization over
   simulated runs:

   | Frame-layer depth | Generated | Used | Utilization |
   |---|---|---|---|
   | 1 | 88 | 5 | 5.7% |
   | **2** | **166** | **5** | **3.0%** |
   | 3 | 298 | 5 | 1.7% |
   | 4 | 538 | 5 | 0.9% |

   Generation **doubles per level while consumption stays flat**. The reason is
   structural: a prepared frame only has to exist before the *clip consuming it is
   submitted*, and clips already lead playback by one scene. Anything past that is
   speculation about speculation. If the cheap layer is ever slow relative to scene
   length, the fix is a faster model, not a deeper tree.

   **Bias quality, not depth.** Uniform depth is correct, but the branches at that
   depth need not get equal treatment. If telemetry shows one branch *type* is
   reliably favoured, prepare the likely branch at full quality and the unlikely one
   reduced, upgrading only if it wins.

Always show the arithmetic. `2 branches × 4 shots = 8 generations, 4 wasted`
versus `2×2 head + 2 canon tail = 6, 2 wasted` is a conversation the user can
engage with; "this reduces waste" is not.

Then **report measured waste, not predicted waste.** The origin session predicted
33% and measured 38%, because beats with 1-shot tails have a worse ratio than the
2+2 case the math assumed. Say the real number.

**Simulate the schedule before building the live layer.** A discrete-event
simulator fed with measured inference and overhead ranges costs an hour and
answers the only question that matters — does the next clip exist before the
current one ends, for a whole run? It found a *structurally impossible* tail
deadline that no amount of concurrency could fix, and the remedy was two
configuration parameters rather than any code. Sweep slot count and print a
verdict column, not raw floats. See `references/scheduling-and-deadlines.md`.

## Continuity

Consistency is decided by what conditions the generation, not by prompt wording.

- **Author every constant visual property as canon.** Before generating anything,
  the entity schema needs explicit `appearance` and `costume` fields written as
  literal, colour-explicit copy — not just `name` / `role` / `traits`. Skipping
  this cost a full render cycle in the origin session: with no costume field the
  model invented clothing per call, and the resulting variation was misdiagnosed as
  "drift" against a spec that existed nowhere. **Unspecified is worse than wrong,
  because nothing can validate it.** Inject the canon verbatim into anchor, plate
  *and* shot prompts, then gate it (torso hue check; luminance is the honest
  discriminator, not saturation).
- **Reference sheets over stills.** A character locked to a set of plates across
  angles and expressions beats two hand-picked images. But **ship only the plates
  that verify** — measured across three generations and two characters, front,
  profile and back are reliable while 45° three-quarters are not (they skew, one
  toward profile and one toward front). 3 body angles + 4 expression plates = 7
  solid locks, which fits inside typical `reference_images` limits. A *wrong* plate
  is worse than a missing one: it teaches the model an identity at an angle the
  character never holds. Details in
  `references/reference-plate-generation.md`.
- **Re-anchor to the sheet; don't chain away from it.** `reference-to-video` is the
  DEFAULT mode for any shot with a named character. Frame-chaining modes inherit
  identity from the previous frame instead of the sheet, so fidelity decays
  monotonically — measured 8/10 → 5/10 → 3/10 over two chained links.

  A follow-up A/B **retired frame-chaining entirely**. Capping it at one link was
  not enough; it lost on three independent axes at once:

  | Axis | Chained shot | Surrounding re-anchored shots |
  |---|---|---|
  | Identity fidelity | 6/10 | 8/10, flat across the scene |
  | Within-shot stability | the **only** shot still re-staging at 5s — interior two-shot → doorway from outside → legs/boots, inside one clip | stable |
  | Audio | **cannot lip-sync** — only reference-to-video accepts reference audio | works |

  Chaining's theoretical benefit is unbroken motion. It did not survive measurement.
  Re-anchor every shot; enable chaining only for a dialogue-free shot continuing one
  physical motion, and never twice in a row.

- **Author camera geometry as a required field for any boundary shot.** Models do
  not reason about architecture. A rendered shot placed the camera *outside* a
  building, opened the door, and showed open sea *through* it — exterior on both
  sides, a building with no interior. The user spotted it immediately; vision review
  confirmed it.

  Require a `camera_side` string on any shot whose prompt, slug **or** narration
  mentions door, doorway, threshold, window, hatch, gate, entry, porch, inside or
  interior. Reject it unless the value names INSIDE/INTERIOR or OUTSIDE/EXTERIOR
  **and** contains the word "behind", naming what lies behind the subject:

  ```
  "camera is OUTSIDE in the storm looking IN through the open doorway; the warm
   lamplit interior room is behind Wrenn"
  ```

  Then append to the shot prompt: *"Everything behind the subject must belong to
  that side of the doorway — do not show the opposite side's environment behind
  them."* This is the same move as costume canon: make the invisible assumption an
  explicit, validated field.

- **CITE every reference asset in the prompt.** Attaching reference images is not
  enough — the API expects each to be named in the prompt text as "Image 1",
  "Image 2", "Audio 1". Nine unlabelled images leave the model guessing what each is
  for, and plausibly explain a render with weak identity conditioning "despite nine
  locks attached". Nine unlabelled images are not nine locks. Budget the slots by
  priority (character identity outranks location) and scope them to who is actually
  on screen.
- **Keep shots SHORT — this is the highest-leverage continuity control.** A long
  take gives the model room to re-stage, relight and re-age *within one shot*, and
  no amount of conditioning prevents it. The behavioural ceiling (4–6s measured) is
  much tighter than the provider ceiling (15s).
- **Prepared frames make chaining fully specified.** If both ends of every chain
  exist as real images before the clip is requested, no shot is ever
  unconditioned — and a bad frame is cheap to re-roll while a bad clip is not.
- **Style bible appended verbatim to every SHOT prompt** — plus a normalizing LUT
  pass so shots from different generations match.

### The grade must NOT touch the identity lock

The subtlest continuity bug in this class of system. Appending the style bible to a
character *anchor* or *reference sheet* prompt bakes coloured light into the plate,
and because sheets are generated i2i **from** the anchor, the cast propagates into
every reference image. Verified: an amber gradient with teal pooling and directional
shadow across a whole set, measured as a 30.1/255 channel spread versus 0.7–2.9 for
a neutral plate.

The video model then inherits the coloured light as if it were the **albedo** of face
and costume. Reference plates must be neutral; the grade belongs on the shot prompt.

Location plates are the **exception** — they become real first-frames, so they should
carry the style bible, and they legitimately vary in exposure between angles.

### Gate reference sets with objective metrics before human/vision review

Anything measurable should be measured, because vision review is slow, expensive and
sometimes wrong. Three cheap checks that caught real defects:

| Check | Method | Catches |
|---|---|---|
| neutrality | per-channel RGB means over the border region | grade baked into an identity lock |
| uniformity | border **median** luma compared *across* the set | plates shot on different-brightness backdrops |
| distinctness | mean abs difference of downsampled grayscale | literal near-duplicate frames |

Two hard-won caveats:

- **Ask what a metric does *not* measure.** `neutrality` checks cast *within* an
  image and passed a set whose backdrop brightness varied by 102/255 across plates.
  The failure was already in the numbers, unchecked, until a second metric was added.
- **Pixel difference is not semantics.** `distinctness` passed a set where two slots
  held the same camera angle, because a profile and a head-turned profile differ a
  lot in pixels. Only vision review confirms an angle *ladder*.
- **Scope each metric to the artifact it governs.** Uniformity is an identity-lock
  rule; enforcing it on location plates flags legitimate exposure variety as failure.

### Keep heavy local tooling OUT of the hot loop

Local ComfyUI/diffusion generation is tens of seconds to minutes per clip against
a few seconds for a fast hosted endpoint, and hosted Comfy tiers cap concurrency
in the single digits. Putting it in the live render path destroys the speculative
buffer.

Its real value is an **offline asset factory**: reference sheets, world plates,
the pre-rendered fallback/cutaway library, and drift repair between runs. Same
workflows can also run *during* a session at strictly lower queue priority to
build the prepared-frame tree — with an abandon-on-deadline policy so frame jobs
never contend with clip jobs.

## Dialogue: synthesize FIRST, condition the video on it

If characters speak, the order of operations is not negotiable. A user reported it
as: *"the audio from the video is playing and the audio from the voices is also
playing, sometimes they line up and sometimes it's off."* Two defects, one cause.

```
WRONG   render video → mux TTS on top
        → the model's own ambience bed plays under unrelated speech (doubled audio)
        → mouths move independently of the words (no lip-sync, drifting in and out)

RIGHT   synthesize TTS → pass as reference audio → model generates the shot
        lip-synced to the real voice track
        → the returned clip already contains the dialogue; mux nothing
```

Post-muxing cannot ever produce lip-sync, because the video was generated before the
speech existed. The fix is a pipeline *ordering* change, not an audio-processing one.

Consequences to encode as rules:

- **Any shot with dialogue must use the mode that accepts reference audio**
  (reference-to-video). Image-to-video has no audio input at all, so a dialogue shot
  in a chaining mode is structurally impossible — validate it.
- Assign a fixed voice id per character in canon so a character sounds identical
  across every shot of every run.
- **Budget dialogue length at authoring time, don't warn about it afterwards.**
  Measure your voices' actual rate once — `characters / audio_seconds` over real
  synthesized lines — and budget at the **slowest** observed rate, not the median.
  Measured across three ElevenLabs narrator voices: 15.69–18.79 chars/sec, so a
  5-second shot holds roughly **69 characters including spaces** — about one short
  sentence. Enforce it in the validator (reject with the character count to cut
  to) *and* state it in the writer prompt so the model authors within budget
  instead of burning repair round-trips. A post-hoc warning fires only after both
  the audio and the video have been paid for; the constraint is knowable before
  either. Re-measure when a voice changes.
- **Reference-audio clips have a MINIMUM duration** (2s on the endpoint measured
  here, with a 15s ceiling). Real dialogue routinely falls under it — *"Who sent
  you?"* synthesizes to 1.44s and the prediction is rejected outright. Pad short
  tracks with trailing silence out to the **shot length** (`apad=whole_dur=`), not
  merely to the minimum: that clears the floor and gives the model audio spanning
  the whole clip, so the mouth is not still moving after the track ends.
- Verify the result by **stream count**, not by listening intent: each shot should
  have exactly one audio stream and there should be zero `*_dub*` files on disk. A
  second stream or a dub artifact means something re-muxed on top and the ordering
  fix silently regressed.

### The model will INVENT speech unless forbidden

Reported by a viewer as *"there's still some weird narratives over non-dialogue
parts."* Video models of this class **always return an audio track and expose no
mute parameter**, so silence is not an option they can choose. Given a shot with
no dialogue and no instruction about audio, the model fills the gap — muttering,
crowd murmur, and voice-over narration over shots where nobody speaks.

Note what this is *not*: the story's `narration` field (authorial subtext, never
sent to the model) was not leaking. The speech was pure invention, which means
no amount of auditing your own prompt content finds it. The absence of an
instruction was the bug.

State the division of labour explicitly on **every** shot prompt:

```
AUDIO: generate DIEGETIC BACKGROUND SOUND ONLY — weather, sea, wind, rain on
surfaces, footsteps, cloth, doors, machinery, room tone. Absolutely NO speech,
NO dialogue, NO voice-over, NO narrator, NO muttering, NO whispering, NO
singing, NO humming, NO crowd voices. No human vocal sound of any kind.
```

and for a dialogue-free shot append: *"This shot is SILENT of speech: nobody
talks, no lips move to form words, no off-screen voice is heard."*

The model owns **diegetic background only**; every spoken word comes from TTS and
reaches the model as reference audio — which also means a dialogue shot gives it
a voice track to lip-sync rather than a vacuum to fill.

**A speech *detector* is the obvious safety net, and it does not work.** The
hypothesis is reasonable: speech is 300–3400 Hz energy modulated at syllable
rate (2–8 Hz), while wind and sea are stationary. Measured against labelled
clips it does not separate:

| clip | modulation index |
|---|---|
| no-dialogue shot | 0.014 |
| real TTS speech | 0.106 – 0.173 |
| pure ambience (lamp, sea) | 0.102 – 0.157 |
| **pure ambience (rain)** | **0.228** — above every speech clip |

Rain is amplitude-modulated at almost exactly syllable rate: drops and gusts
fluctuate 2–8 times a second. Any threshold catching speech at 0.106 destroys
the weather the model is supposed to provide. The distributions overlap
completely; there is no cut. Per debugging principle 4.5, it was shipped
disabled with the numbers recorded rather than shipped as a gate.

The deterministic fallback that *does* work, when a bad take must be salvaged:
a **250 Hz low-pass** destroys vocal intelligibility while keeping sea, wind and
rumble. It costs air and rain detail, so make it opt-in per shot rather than
automatic.

## Never show a spinner: the fallback library

If the product promise is "no waiting," then a failed or late generation must
still play something. Pre-render a **cutaway library** (ambient establishing
shots, reaction inserts, weather) graded to the style bible, and cut to it while
retrying. Cover fallbacks *per position* — a just-in-time tail shot has no cached
alternate branch behind it, so it needs its own coverage, not a generic insert.

**Character-free is the entire trick, not a stylistic choice.** Every drift
failure this class of pipeline produces is a *character* failure: faces aging,
wardrobe changing, blocking re-staging. A shot containing no character cannot
break identity continuity, which makes it the only shot type safe to substitute
arbitrarily and reuse across runs. Generate from the location plates so it also
cannot break the world. Five subjects per location covers it — the mechanism or
machine, water/weather, a window or glass surface, a worn practical detail, and
an empty wide. Add an explicit negative: *"absolutely NO people, NO figures, NO
silhouettes, NO hands."*

Film grammar absorbs this completely. Cutting to the lamp while someone decides
is normal editing, not an apology.

Runtime rules that make it work:

- Reuse across screenings, but **never repeat within one** — track usage per run,
  or the fallback starts reading as a fallback.
- Falling back to *another* location's cutaway beats stalling. A slightly
  wrong-place insert is far cheaper than a visible wait.
- **When the library is exhausted, raise.** A silent stall is precisely the
  failure the library exists to prevent; an explicit error says "generate more
  cutaways for this location," which is actionable.
- **Test the failure path by monkeypatching the provider call to throw.** This is
  the one code path that only ever executes on a bad day, so it will not be
  exercised by normal runs and will rot silently. Assert the render *continues*
  and produces a playable file. Doing this caught an `UnboundLocalError` on the
  first attempt: the success-path result variable was still referenced after the
  fallback branch, so the substitution worked and the function crashed anyway.

## Validator-owned state (when an LLM drives the story)

For any system where a model advances long-running state, **the model proposes and
a state machine commits.** Full pattern and schema shapes in
`references/validator-owned-canon.md`. The load-bearing ideas:

- Author the skeleton (chapters/beats/steps) ahead of time; generate only the
  branches. This is the anti-slop mechanism — the audience *uncovers* a plot
  rather than inventing a random one.
- Validate proposals against a JSON schema **and** against domain rules (known
  entities only, declared flags only, flags settable at this step only).
- Feed the validator's own error message back and let the model repair. Never
  silently accept a rejected proposal.
- **Position-dependent validation is the cheap structural win.** Make the
  illegal thing unrepresentable: "a shot with a locked character may not be
  `t2v`", "a mid-scene shot must chain". The generator then cannot emit output
  that breaks continuity. In the origin session this caught real violations
  before any generation spend, on multiple runs.
- Append every committed turn to an immutable log so a run is reconstructable.

## Cost modelling

Structure the estimate as layers, not one number:

```
video layer   clips × per-clip price × (1 + waste ratio)   ← dominates
image layer   prepared frames, ~2 orders of magnitude less ← rounding error
audio layer   TTS/music, cheap
infra         ffmpeg/CDN, negligible
```

Then give **ranked levers**, not a list: speculation strategy first, branch-point
count second, clip length third, reuse fourth, asymmetric quality (speculate at
low res, re-render the winner at high res) fifth, runtime last.

State the waste ratio as a deliberate purchase: it buys zero latency. Do not
present it as an inefficiency to be optimized away.

## Working style for this class of task

- **Outline + PRD before building.** Get sign-off on architecture before spending
  on generation.
- **Text-only milestone first.** For a narrative system, prove continuity holds
  as plain text before any video pipeline exists. It is free, and it is the real
  go/no-go gate — no render pipeline rescues a broken story engine.
- **Build a replay/demo mode before the delivery layer.** One flag that swaps
  the provider render call for "reuse a clip already on disk", with the seam at
  exactly one function. A live layer needs dozens of restarts to develop, and
  each one would otherwise re-render a scene. Everything except that single call
  should be identical between demo and live, or it stops being a test of the
  real system.
- **Revise documents in place.** Use the doc-id/update path so shared links and
  comment threads survive. Say what changed and by how much.
- **Retract wrong numbers explicitly in the document**, don't just overwrite
  them. "An earlier draft assumed X; that is not achievable" prevents the stale
  figure resurfacing from someone's memory of v1.
- **Flag honest gaps and blockers** rather than papering over them (a metric
  below target, a hardware requirement you can't satisfy). This user
  specifically values stated confidence over confident-sounding filler.

## Debugging generative pipelines

Four principles, each earned by getting it wrong first:

1. **Anything measurable, measure — don't prompt for it and don't eyeball it.**
   Backdrop brightness, colour cast, frame similarity, clip counts, live job counts
   are all arithmetic. A vision subagent spent ~400 seconds to report a colour cast
   that a border histogram measured exactly in under a second. Prompts are for
   content; arithmetic is for quantities.

2. **When you write a metric, ask what it does *not* measure.** A per-image cast
   check passed a set whose *cross-set* brightness varied by 102/255. The failure was
   already sitting in the tool's own output. Every metric has a blind spot; name it
   in the tool's output so a future reader cannot mistake its scope.

3. **When a fix and a new failure appear in the same step, suspect the fix.** A
   correction pass "revealed" two collapsed expression plates. It had flattened them
   itself. Keep raw originals so this costs a re-run rather than a regeneration.

4. **When the same fix works twice on different-looking symptoms, generalise.** One
   underlying mechanism produced silent under-delivery, a skewed angle ladder, and
   converging expressions. Two full rounds were spent treating a general mechanism as
   a local bug before the pattern was named.

And on evidence: **when a vision report and the numbers disagree, get a third
signal before acting on either.** Two independent subagents reported "duplicate
plates"; the pair-distance matrix showed a differently-shaped problem, and the
matrix was right.

4.5. **Validate a new metric against LABELLED examples before shipping it —
   and be willing to throw it away.** Not every property that feels measurable
   is. Two cheap silhouette metrics were built to close the known "distinctness
   cannot see camera angle" gap, and both failed against plates whose angles
   were already known:

   | Attempt | Result on labelled data |
   |---|---|
   | mirror-symmetry of the centroid-aligned subject mask | **inverted** — profile scored 0.228, front 0.632. A profile silhouette is narrow and compact, so it mirrors onto itself *well* |
   | shoulder-width ÷ subject-height | worked on one character (0.752 / 0.47 / 0.153) and collapsed on the next (0.317 ≈ 0.330 ≈ 0.394), because framing and crop vary per generation |

   Both measured *pose and framing* rather than *facing*. Neither shipped; the
   gate was deleted and the gap documented in the neighbouring metric's
   docstring instead.

   **A gate that silently mis-scores is worse than an acknowledged gap.** The
   acknowledged gap gets routed to vision review; the plausible-but-wrong gate
   gets believed, and it will pass bad assets forever. Two more consequences:
   quarantined failures are your labelled test set, which is a second reason
   never to delete them — and a metric you cannot validate is a finding to
   report, not a deliverable to ship.

5. **Two tools must measure a shared property the SAME way.** A QC gate computed
   border *mean* RGB while the normalizer optimized border *median* luma — same
   property, different estimator, so they contradicted each other on identical
   files (`normalize: PASS 2.0` vs `qc: FAIL 52.4`). Neither was lying. Two tools
   disagreeing about one property is worse than either being wrong, because it
   destroys trust in both. Share the estimator function between gate and fixer.

6. **Anything a gate GRADES, the fixer must PROCESS.** Anchors were excluded from
   the normalizer's file list (uniformity is meaningless for one image) but the
   gate still graded their neutrality — so an uncorrected anchor failed a set whose
   every derived plate passed. Enumerate the artifact list once and share it.

7. **Verify generated media by content, not by container.** `ffprobe` reporting an
   AAC stream proves nothing about whether it contains speech. A "dialogue" track
   turned out to be ~52 BPM metronomic transients; speech is never metronomic.
   Spectrograms cost seconds and settle it.

8. **Fixing one property often breaks another — expect the interaction.** Adding
   colour-explicit costume canon introduced a *backdrop colour cast* matched to the
   wardrobe palette (tan → amber, olive → teal). Per-angle calls fixed the angle
   ladder and *worsened* backdrop uniformity. Re-run the full gate suite after every
   fix, never just the check you were targeting.

9. **Verify every code edit actually LANDED.** The most expensive failure mode in
   this class of work, because the feedback arrives as a paid render. Repeated
   `str.replace` calls silently no-op'd against stale anchors: a required field
   appeared **zero** times in a file after being "added" twice, and two validators
   were absent entirely from the module that was supposed to enforce them. Three
   generation runs were spent proving rules that had never been in the file — and
   the symptom looked like "the model is ignoring my instructions," which sent the
   debugging in the wrong direction.

   String-replace edits fail *silently and invisibly*. Assert the anchor exists
   before replacing, assert the result contains the new text after writing, and
   grep the file independently. An assertion that fires costs nothing; a render
   that fires costs money and misleads you. When a rule "isn't being followed,"
   check that the rule is physically present before blaming the model.

   Corollary: when you patch a validator AND its prompt template, verify both. A
   validator demanding a field the JSON shape example omits just burns repair
   round-trips and then fails — the model cannot supply a field it was never shown.

10. **Derive upload content types from the file extension.** A hardcoded
    `image/png` in an upload helper sent an mp3 voice track up as a PNG, and the
    provider rejected the prediction with "Unsupported audio format: .png". The
    file was fine; the declared type was not. Map the extension, and raise on an
    unmapped one rather than defaulting.

11. **Account for the gap between inference time and wall time before buying
    capacity.** A 5.6s inference was costing 22.2s wall. The provider was not
    the problem: identical reference plates were being re-uploaded on every
    single shot, 16.9MB a time. Cache reusable uploads **by content hash, not by
    path** — a regenerated plate keeps its filename, so a path-keyed cache
    serves a stale URL for new pixels. Measured 3.3s cold against 0.047s warm.
    Transfer, queue wait and redundant re-upload hide in that gap and are
    usually cheaper to fix than more slots.

12. **When a simulation reports failure, verify the model before changing the
    system.** A scheduling simulator charged branch-head rendering against the
    *current* scene and reported ~50% missed head deadlines — but speculative
    heads render during the *previous* scene, which is the whole point of
    speculating. The architecture was fine; the model was wrong. A wrong model
    that reports failure will send you rebuilding something that works.

13. **Verify what a model EMITS, not only what it accepts.** Checking that a
    candidate has the right *input* (audio-in, image-in, the conditioning mode
    you need) is half the check. A restyle model accepted 44.1 kHz audio and
    emitted **32 kHz / 48 kbps** — architectural, not a setting — so the whole
    route had a fidelity ceiling below the source material, discovered only
    after a paid render and a user rejecting the result. Read `sample_rate` /
    resolution / bitrate off a **real output** before recommending any route.
    See `references/audio-remix-and-stems.md` §2.

14. **A fixed grid always drifts against a real performance.** Whenever
    synthesized elements must lock to existing recorded material — beats to a
    song, animation to a take, subtitles to speech — deriving a global rate and
    laying down a regular grid fails, because real performances are syncopated
    and the estimate is never exact. Measured: best-case grid fit 96.6 ms RMS,
    with inter-onset intervals clustering at three unrelated values. **Delete
    the independent clock** and trigger every element from detected events in
    the source. Drift then becomes structurally impossible rather than merely
    small — the same move as validator-owned canon. See
    `references/audio-remix-and-stems.md` §4.2.

15. **A quiet flag can suppress the measurement you are reading.** `ffmpeg
    -v error` silences `volumedetect`'s own output, so a parse returns the
    default and every number in the resulting table is fabricated. Cumulative
    versus per-block statistics caused a second false reading in the same
    session. When a measurement looks suspiciously smooth, uniform, or all
    identical, suspect the harness before the data. See
    `references/audio-remix-and-stems.md` §5.

## Pitfalls

1. **Assuming clip duration.** See Rule 0. Verify per model *variant*.
2. **Gating conditional content on a single flag.** If two later steps both
   require the same one flag, one early choice silently deletes a chunk of the
   experience. Gate on alternatives (`a|b|c`).
3. **Asymmetric branch flags.** If only the "active" side of an early choice
   sets a flag, resistant audiences arm far fewer downstream payoffs. Give both
   sides of a branch their own flag and their own payoff contract.
4. **Pruning a speculative tree by immediate loser only.** You must prune
   against the *entire canon path*, or stale subtrees from earlier speculation
   stay alive and live-job count grows without bound instead of holding steady.
   Verify with a full-run simulation that the live count is flat, not rising.
5. **Serial-throughput thinking.** "Generation is 1.7x faster than playback"
   does not survive 12 clips in flight. Compute in-flight job count for your
   chosen depth, multiply by wall time, compare against playback seconds, and
   treat parallel job slots as a procurement requirement.
5.5. **Believing more slots will fix a just-in-time deadline.** They cannot.
   Any work that must wait on a decision — a tail generated after the vote —
   sits on a dependency chain concurrency does not shorten. Simulated at 1
   through 8 slots, a 6.0s tail runway against a 7.1–9.1s render wave missed
   **9/9 deadlines at every slot count**. When a sweep is flat across slot
   counts, the constraint is in the timeline, not the scheduler: lengthen the
   runway (close voting earlier, or lengthen the head) instead. Full derivation
   in `references/scheduling-and-deadlines.md`.
6. **Heavy local generation in the live path.** Keep it offline. See above.
7. **Uniform shot lengths — and long shots generally.** Two separate traps here.
   Long heads buy tail runway, so an early version of this skill said "prefer long
   heads." **Measurement reversed that.** At 13–14s a video model re-stages
   blocking, relights and changes location *inside a single take* — verified: night
   rain threshold → sunny balcony → interior across 35s of three individually
   well-chained shots. Cap shots at **4–6s** and reach head duration with *more
   shots* (3×5s, never 1×15s). Encode both rules in validation: reject a shot over
   the drift ceiling, and reject a head whose total is under the vote window.
8. **Assuming the provider ceiling is the operative limit.** It usually is not.
   The provider allowed 15s; drift forced 4–6s. Find the *behavioural* limit by
   rendering and measuring, then write the tighter number into the validator with
   a comment saying why, so nobody later "optimises" it back to the API maximum.
9. **Leaving a property unspecified and then calling its variation "drift."**
   The character schema had `name`, `role`, `traits` — no `costume`. A whole render
   cycle and a vision delegation were spent auditing plates against a wardrobe spec
   that existed only in the agent's own earlier summary. Unspecified is worse than
   wrong: nothing can validate it, and it surfaces first in video. Any visual
   property that must stay constant needs an **authored, colour-explicit canon
   field** injected verbatim into every prompt — and a gate that checks it.
10. **Porting a payload between providers.** Unknown fields are silently ignored,
    not rejected. A `generate_audio` flag carried over from another provider
    produced successful calls with no dialogue for an entire render. Diff the
    request against the new provider's schema after any migration.
11. **Concurrent writes to the same output path.** Parallel ffmpeg/provider jobs
    need unique output paths or you get corrupt containers.
12. **Batching a "N distinct items" generation request.** Multi-image "auto" modes
    return N independent rolls sharing a prompt, not a coherent set — so distinct
    angles, distinct expressions and matched backdrops are all left to chance. One
    call per item. See `references/reference-plate-generation.md`.
13. **Trusting a success status when the count matters.** An identical multi-image
    call returned 9 images once and 6 the next time, both `succeeded`, no error.
    Assert the returned count before using the output.
14. **Deleting failed assets.** Move them to `_retired_<reason>/` or
    `_quarantine/<name>_<ts>/` and renumber survivors contiguously. A *wrong* plate
    is worse than a missing one, and a future model may handle what this one
    couldn't. Version any `_raw/` backup by content hash — a flat one silently
    restored older-generation files over a freshly corrected set. Paid-for artifacts
    should never be unrecoverable; prefer `mv` to `rm -rf`, which is also the
    difference between an operation that proceeds and one that gets blocked.
15. **Letting a viewer's report get filed as "already fixed."** Two user-reported
    defects in this class — inverted door geography and desynced dialogue — were
    both real, both structural, and neither was visible in any metric being tracked.
    Objective gates only catch what they were written to catch. A person watching
    the output remains the highest-signal detector of continuity failures nobody
    thought to instrument; treat their report as a specification gap, and fix it in
    the schema rather than in a prompt.
16. **Publishing a media-pipeline repo without an exclusion + secret audit.** These
    projects accumulate hundreds of MB of generated assets beside code that reads
    four or five provider credentials. Before the first commit: gitignore
    `assets/ renders/ runs/ .venv/ .env`, ship a `.env.example` with empty values,
    then audit in three places — grep the source for key literals, grep the
    **staged diff**, and after pushing list the **remote tree** to confirm what the
    world actually sees. Every client should read `os.environ`; a scan that returns
    only `os.environ.get("...")` hits is the passing result.
17. **Truncated or duplicate module files hiding in the source tree.** A
    byte-identical copy of a provider client existed under a mangled name, and the
    renderer was importing *that* copy — so edits to the real module had no effect.
    Before publishing, list the package directory, diff same-purpose files, and
    confirm every module still imports after removing a duplicate. Related to
    debugging principle 9: an edit can land perfectly in a file nothing loads.
18. **Letting an agent near the validator.** The operating loop for these
    pipelines is itself a design decision: measurement and analysis are safe to
    automate fully, regeneration needs a spend gate, and schema/validation rules
    must stay human-gated. An agent asked to satisfy a constraint it can edit will
    edit the constraint. See `references/agent-harness-operations.md`.
19. **Declaring a demo reachable after testing it only from the host.** A server
    bound to `0.0.0.0` answered 200 on loopback *and* on its own public IP, and
    the user still saw nothing on their phone — the host firewall was dropping
    the port inbound, and traffic originating on the box never traverses that
    path. Curling your own public IP proves the listener works, not that anyone
    can reach it. Check the firewall's allowed ports, and check what already owns
    80/443: if a TLS proxy is running, route through it rather than opening a
    custom port, since HTTPS on a standard port survives mobile networks and
    phone browsers that resist plain HTTP. See
    `references/live-screening-layer.md`.
20. **Shipping a viewer you never viewed.** Protocol checks (status codes,
    content types, `ffprobe` on a served segment) prove the plumbing, not the
    page. When the rendering surface is genuinely unverified — headless host,
    browser tooling down — say so explicitly and hand it over for a ten-second
    human look, rather than letting a stack of green curl output imply the UI
    was checked. This paid off directly: an honest handover produced two
    structural defects (pitfalls 21 and 22) inside one viewing, both of which a
    full green suite had missed.
21. **Serving provider clips as HLS segments unchanged.** Rendered clips are
    progressive MP4 (`ftyp`+`moov`+`mdat`) — one self-contained movie each.
    `hls.js` cannot splice those into a timeline: it loads the first and stalls,
    presenting as a player that never advances. Remux to MPEG-TS
    (`-c copy -bsf:v h264_mp4toannexb -f mpegts`, ~50 ms, no re-encode) or use
    fMP4 with an `#EXT-X-MAP` init segment. The deeper lesson is about
    verification: `curl` 200, correct content type and `ffprobe` reporting
    h264/aac **all passed**, because the files were valid *video*. Serving valid
    video and serving a valid *stream* are different claims — assert the
    container structure the protocol requires, not merely that the media decodes.
21.5. **Verifying a stream layer by layer instead of end to end.** Three
    successive rounds of "I'm not seeing any video" were each diagnosed by
    inspecting one layer — the file decodes, the container is spliceable, the
    timestamps increase — and each layer passed while the stream stayed
    unplayable, because the failure kept moving. Point a **real client at the
    real URL first**: `ffmpeg -v error -i http://host:port/stream/index.m3u8
    -t 20 -f null -`. Silence means a genuine HLS client fetched the manifest,
    followed the segments and decoded a continuous timeline. If that passes and
    the browser still shows nothing, the bug is in the client code — which is
    where it actually was, after two rounds of blaming the media. Also stamp
    each remuxed segment with its running playlist offset
    (`-output_ts_offset`): clips that each begin at the same PTS make time jump
    backwards at every boundary and stall the player.
21.6. **A resync loop that presents as "no video at all."** Server-authoritative
    playback sync was the deliberate, careful part of the design and it broke
    playback harder than anything else. Correcting drift whenever it exceeded
    2s, against state pushes arriving twice a second, meant the player seeked,
    began rebuffering, received the next push and seeked again — no frame ever
    rendered. Any correction that costs a rebuffer must be rare, late and
    rate-limited: require playback to have started, a wide tolerance (~8s), and
    a cooldown (~10s). A few seconds of drift is invisible to an audience; a
    stalled player is not. Related: high-frequency state pushes also destroy
    interactive controls if the page rebuilds them on every message — build
    once per logical unit and mutate in place, use `pointerdown` over `click`
    on touch, and expose a player-status field so a remote viewer can report
    *where* it failed. See `references/live-screening-layer.md` §3.2–§3.4, §4.2.
22. **Timing an audience-facing event on the render clock.** A speculative
    pipeline runs two clocks separated by the entire buffer (measured 20–26s):
    when a clip is *published* versus what the audience is *watching*. Opening a
    vote at publish time asked the room to decide a scene that had not appeared
    yet, and closed the window ~8s before it did — every tap silently rejected,
    with buttons disabled ~73% of each beat. It also silently invalidated the
    schedule model, which had assumed viewer time throughout, so the derived tail
    runway never existed in the live path while every unit test still passed.
    Gate anything the audience reacts to on the **playhead** (wait until the
    the playhead enters the scene, *then* open the vote); keep resource scheduling on
    the render clock. For every timed event, ask which clock it is on.
23. **Assuming a generative model can produce silence.** It cannot opt out of
    audio. Given a shot with no dialogue and no audio instruction, it invents
    speech — voice-over, muttering, crowd murmur. Forbid human vocal sound
    explicitly on **every** shot prompt and name what the model *is* for
    (diegetic background), with an extra "nobody talks" clause on dialogue-free
    shots. Auditing your own prompt text for leaked narration will not find
    this: the bug is an absent instruction, not a present one.
24. **Serving render masters to the delivery layer.** The renderer's output
    bitrate is chosen for quality, not for phones — ~9 Mbps here, meaning
    several MB before the first frame. Transcode at publish time (~2 Mbps,
    2.7s CPU per clip, inside the existing buffer) and treat that step as the
    place a bitrate ladder will later live. Re-encoding replaces a stream-copy
    remux, so carry any timestamp-offset flags across or a fixed defect
    silently returns.
25. **Trusting a derived artifact left on disk by a previous process.** After
    changing the playlist URL format, the unit tests passed while the *running
    server still served the old format*: a resumed screening replayed its
    journal and reused playlist files written by the previous build. The tell
    is a timestamp — the artifact predated the process serving it. On resume,
    **regenerate every derived file from restored state** (playlists, caches,
    manifests, indexes) rather than trusting its format to match current code.
    Component tests structurally cannot catch this: the test exercises the
    generator while the server serves the artifact, so only diffing the running
    server against the source finds it. See
    `references/public-deployment-hardening.md` §6.
26. **Absolute paths in playlists and client code.** Emitting `/segments/...`
    and fetching `/token` only works mounted at the domain root, which rules
    out a path-mounted reverse proxy or a CDN-fronted subpath — and it fails at
    deploy time, invisible to every test. Emit **relative** segment URIs (HLS
    resolves them against the manifest URL) and derive client paths from
    `location.pathname`. Costs nothing if done before the first deploy.
27. **Shipping uncacheable media and then wanting a CDN.** Each viewer pulls
    1–2 Mbps continuously from the box that is also encoding. A CDN only helps
    if the origin says what may be cached: segments are immutable once written
    (`max-age=31536000, immutable`), playlists must be `no-store`. A cached
    *playlist* freezes a viewer at their connection moment and presents
    identically to the timestamp and resync bugs — expensive to diagnose twice.
28. **Interpolating a request path segment into a filesystem path.** Use a
    regex plus an allowlist (`seg_\d{4}\.ts`, known rung names), not
    sanitisation, and verify the percent-encoded traversal form too since
    frameworks differ on when they decode.
29. **Making an irreversible commitment from an AGGREGATED reading.** A global
    GPU stock list showed one card at `High` availability; a per-datacenter
    sweep found it in none of the thirteen regions where a network volume can
    live, and the region chosen from that global reading had zero GPUs of any
    size. The commitment — a datacenter-locked volume — would have been
    permanent and billing monthly for storage no pod could attach to. Before
    anything irreversible (locked regions, reserved capacity, a paid tier),
    re-query at the **granularity of the thing being committed**, and gate it
    behind a script rather than a sentence: the prose warning to "check
    per-datacenter" was present, was read, was agreed with, and the wrong
    recommendation still got made. A written caution is not a control; a
    runnable probe is. See `scripts/dc_stock.py`.
30. **Treating region latency as negligible when the deliverable is a
    recording.** For batch rendering, geography is a rounding error. When the
    user will drive the UI **on camera** — portfolio reels, demos, tutorials —
    every interaction pays the round trip, and ~160–190 ms reads on video as
    operator hesitation rather than network lag. Ask what the session's output
    actually is before optimising for price or reusing an existing far-region
    volume; a saved storage fee that buys visibly worse footage is a bad trade.
    Say the latency figure out loud in the decision — it is the one factor
    absent from a price table.

31. **Provisioning hardware before confirming the model can be self-hosted.**
    Many of the strongest video models are API-only at every version — no
    weights, no local inference, ever. A GPU was rented and billing before
    anyone checked, and the ComfyUI workflows that made the model *look*
    self-hostable were API nodes calling a remote endpoint. Ask "do public
    weights exist?" before "how much VRAM?", because a negative answer
    invalidates the whole hardware track rather than resizing it. A vendor page
    offering only "Try Now" and "Get API" is the tell. When the user names an
    API-only model, say so plainly and split the work: hosted API from the
    local box for that model, open weights on the GPU for the rest — the two
    tracks run in parallel. See `references/rented-gpu-operations.md` §1.0.
32. **Letting a paid resource idle through an unresolved decision.** When a
    verification finishes, or a plan turns out to be wrong, or a question is
    put to the user, the meter is still running. Stopping is reversible and
    forecloses nothing, which makes it the honest default while waiting —
    and state the accrued spend when raising the question, not afterwards.
    An idling pod discovered at the end of a session is a worse conversation
    than a stopped one that needs restarting.
33. **Sizing a download from `df` on a network volume.** On RunPod's MFS
    mount, `df -h` reports the **shared backing store**, not your volume
    quota — it showed `155T free` while the volume sat at 96/100 GB. A
    download sized against that number died on its last and largest file
    with `IO Error: Disk quota exceeded (os error 122)`, after transferring
    everything before it. Use `du -sh` against the volume root for true
    usage, and count **everything**, not just models: two virtualenvs with
    CUDA wheels were 25 GB combined and were omitted from the estimate
    entirely.

    ```bash
    du -sh /workspace              # real usage vs quota
    du -sh /workspace/* | sort -rh | head
    ```

    The recovery is usually to grow the volume, not to delete — via the REST
    API, which GraphQL does not expose:

    ```bash
    curl -s -X PATCH "https://rest.runpod.io/v1/networkvolumes/<volume-id>" \
      -H "Authorization: Bearer $RUNPOD_API_KEY" \
      -H "Content-Type: application/json" -d '{"size":200}'
    ```

    It applies immediately to a running pod — no restart, no remount. `df`
    still shows the backing store afterwards, so confirm empirically by
    exceeding the old ceiling. When the alternative is deleting weights the
    user paid GPU-hours to install and debug, storage is the cheap side of
    the trade: offer the resize before offering a deletion menu.

34. **Selecting a node family by schema resemblance instead of by purpose.**
    Three Wan nodes look interchangeable and are not: `WanAnimateToVideo`
    *animates a still* from driving motion, while `WanSCAILToVideo` *replaces
    a person in existing footage* and carries an explicit `replacement_mode`
    boolean. Four failed runs and two wrong hypotheses were spent tuning the
    animation node for a replacement job. The mask formats are not
    interchangeable either — Animate takes a plain binary mask, SCAIL-2 wants
    **colored per-identity** masks from `SCAIL2ColoredMask` — so inverting
    mask polarity, the obvious next fix, could never have worked in either
    direction. Read what a node is *for* before reading what it accepts; the
    node choice is the whole decision and parameter tuning cannot rescue a
    wrong one. See `references/video-character-replacement.md`.
35. **Trusting a formatted schema dump over the raw JSON.** Printing
    `input.required.<field>[0]` on a ComfyUI COMBO yields the literal string
    `"COMBO"`, which rendered as `['C','O','M','B','O']` and produced a
    confident wrong conclusion about which classes a detector supported. The
    options live in `[1]["options"]`. When a schema read returns something
    shaped oddly, dump the raw JSON for that one field before building on it.
36. **Assuming separate scripts means separate lanes.** Process architecture
    and hardware capacity are different claims. Two independent scripts still
    share one GPU: generation peaked at ~33 GB and the upscaler at 36.5 GB on
    a 46 GB card, so "run them at the same time" was impossible despite the
    clean separation. Measure the peak of each lane and state the ceiling
    before promising concurrency.
37. **Reinstalling nothing on a redeployed pod because the volume looks
    intact.** Only the mounted volume persists. Models, venvs and outputs all
    survive a redeploy while `apt`-installed binaries do not, so a finishing
    script dies on `ffprobe` while every model check passes and ComfyUI is
    healthy. Put container-level dependencies in the bring-up script, not in
    your memory of the last pod.

## Working-style notes for this user

- **Plan first, then execute.** Outline and PRD before spending; wait for sign-off
  on anything paid.
- **Report measured numbers, not predicted ones**, and retract superseded figures
  explicitly rather than quietly overwriting them.
- **Volunteer honest blockers** — a metric below target, a hardware requirement you
  can't meet, an unverified file. Stated confidence beats confident-sounding filler.
- **Own your own bugs plainly** when a fix you wrote caused a regression. Several
  failures this class of work produces are self-inflicted, and saying so is faster
  than a diplomatic framing.
- This user reliably spots over-engineering (e.g. "maybe images only need to be one
  depth level ahead of the videos?"). When they question a design parameter,
  **measure it rather than defend it** — the measurement has vindicated them.
- **Deliver visual output where the user can actually see it.** A path on the
  agent's box is not a deliverable; this user is frequently on a phone. Upload
  to Drive (or the project's shared folder) and give the link in the reply.
  For any before/after work, ship a **labelled side-by-side**, not a bare
  output file — quality cannot be judged without the input beside it.
- **State the delivery frame rate and why.** Native model rates (16 fps for
  Wan 2.2) look like a mistake in a deliverable. This user pushed back with
  "why are we using 16 fps?? It should be 30 at least" and was right about the
  deliverable. Generate at the model's trained rate, interpolate up for
  delivery, and say both numbers out loud so the native rate reads as a
  deliberate choice rather than an oversight.
- **Separate "the pipeline ran" from "the output is good."** Frame counts,
  codecs and pixel deltas prove mechanics only. When you cannot see the
  frames, say the visual result is unjudged and hand it over — do not let a
  stack of green checks imply the picture was reviewed.
- **When the user's eyes contradict your metrics, the metrics lose.** Colour
  histograms ranked a character-replacement output third and it was actually
  the best one — it had adapted the character's *lighting* to the scene,
  which no pixel-percentage measure can see. The agent nearly talked the user
  off the correct tool on that basis. Metrics are for catching regressions
  and proving something ran; human review judges quality. When they disagree,
  say plainly that the measurement was the wrong instrument rather than
  defending the number.
- **Ship the comparison video, not just the numbers.** This user asks "I don't
  see the comparison video" when handed a results table. Every measured
  comparison needs the labelled side-by-side uploaded and linked in the same
  reply — and for anything resolution-related, a **1:1 pixel crop**, because
  full-frame panels downscale away the exact detail under evaluation.
- **Report a bad metric as inapplicable, don't launder it into a verdict.** A
  per-pixel detail measure scored both upscalers below their own source, which
  is a property of the measure (same edge, twice the pixels), not a finding.
  Saying "this metric cannot compare across resolutions" is more useful than a
  table that reads like a ranking.

## Verification checklist

- [ ] Provider constraint table written down, with variant named
- [ ] Every duration/resolution assumption traceable to that table
- [ ] Lookahead depth **derived** from generation-vs-scene timing, not chosen
- [ ] In-flight job count computed for chosen lookahead depth
- [ ] Cost model layered, with waste ratio stated as measured, not predicted
- [ ] Fallback coverage exists for every position, including just-in-time slots
- [ ] Validator rejects illegal-by-position output (proved by a real rejection)
- [ ] Text-only / cheap-layer milestone passes before expensive spend
- [ ] Live-job count verified flat across a simulated full run
- [ ] Reference sets pass `plate_qc.py` BEFORE any vision-review spend
- [ ] Returned image counts asserted, not inferred from a success status
- [ ] Semantics (angle ladder, expression reads) confirmed by vision, since no
      pixel metric can judge them
- [ ] Schedule simulated against measured inference/overhead, swept across slot
      counts, before any live-layer code is written
- [ ] Vote-close fraction and head length recorded in config **with their
      derivation inline**, so they are not "optimised" back
- [ ] Inference-vs-wall-time gap accounted for (redundant uploads cached) before
      concluding more render slots are needed
- [ ] Queue behaviour covered by fake-clock tests: priority, earliest-deadline,
      whole-branch pruning, promotion, expiry, error surfacing, real overlap
- [ ] Simulated results reported **as simulated**, with the unmodelled failure
      modes named
- [ ] Live layer exercised in demo/replay mode before any paid live run
- [ ] Playlist manifest served `no-store`, and `HEAD` answered on manifest and
      segments (a GET-only smoke test misses both)
- [ ] Segments are in a spliceable container (MPEG-TS, or fMP4 with an init
      segment) — not progressive MP4 that merely `ffprobe`s clean
- [ ] Remuxed segments carry increasing PTS across the playlist
      (`-output_ts_offset`), verified on consecutive segments
- [ ] Whole stream decoded end-to-end by an independent HLS client
      (`ffmpeg -i <manifest> -f null -`) before any client-side debugging
- [ ] Playback drift correction is rate-limited and gated on playback having
      started — never a seek per state push
- [ ] Interactive controls built once per logical unit and mutated in place,
      not rebuilt on every state message
- [ ] Every audience-facing timed event gated on the **playhead**, not on
      publish time; vote window verified to open while its own scene is on
      screen
- [ ] Vote winner computed server-side, ties broken deterministically, every
      resolved decision appended to an immutable log with its tally
- [ ] External reachability confirmed against the host firewall — not by curling
      your own public IP — before a URL is handed to anyone
- [ ] Any unviewed rendering surface declared unverified rather than implied
      checked by passing protocol tests
- [ ] Every shot prompt forbids human vocal sound explicitly, with an extra
      "nobody talks" clause on dialogue-free shots — the model cannot choose
      silence on its own
- [ ] Delivery segments transcoded to a mobile-appropriate bitrate, with a
      keyframe interval that allows mid-segment decode start
- [ ] Muted autoplay exposed as a visible "tap for sound" control, not left for
      the viewer to discover
- [ ] Segments served `immutable`, playlists `no-store`, CORS open — verified by
      reading response headers, not by intent
- [ ] Playlists emit relative URIs and the client derives paths from
      `location.pathname`, so a proxy or subpath mount needs no rebuild
- [ ] TLS terminated by a proxy forwarding `X-Forwarded-For` (without it every
      viewer shares one rate-limit bucket)
- [ ] A resumed process **regenerates** every derived artifact rather than
      serving files the previous build wrote
- [ ] Filesystem-bound request paths allowlisted, traversal verified in plain
      and percent-encoded form
- [ ] Public weights confirmed to EXIST before any GPU is provisioned for a
      named model
- [ ] Conditioning/reference-lock route tried and genuinely rejected before
      committing to LoRA training
- [ ] V2V output proved non-passthrough by pixel comparison, not by frame
      count or codec
- [ ] Visual deliverables uploaded to shared storage with links given, as a
      labelled side-by-side where a before/after exists
- [ ] Disk growth per hour of screening stated, with pruning either implemented
      or explicitly deferred
