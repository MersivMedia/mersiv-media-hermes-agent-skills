# Video generation providers — verified quirks and measured throughput

Companion to `references/reference-plate-generation.md` (which covers the *still*
image layer). This file covers the **clip layer**: which provider to use for what,
the API traps that cost real debugging time, and measured per-mode speed.

All figures verified by direct API calls, not from marketing pages.

---

## Provider split: stills on one, clips on another

| Job | Provider | Why |
|---|---|---|
| Character sheets, location plates (i2i) | Replicate `bytedance/seedream-4` | multi-reference i2i, ~$0.02/image, no GPU needed |
| Video clips (t2v / i2v / flf / ref2v) | **fal MiniMax H3 Max** | fal-exclusive; fast; safety checker is a parameter |

**H3 Max is not on Replicate.** `minimax/h3-max` returns 404 there — the
fal-post-trained fast variant is fal-only. Replicate carries base `minimax/h3`
(no fast variant) and the seedance family.

Two reasons the split matters beyond raw speed:

1. **Safety-checker false positives with no escape hatch.** Replicate's
   `bytedance/seedance-2.0` rejected a set of our *own* neutral-studio emotion
   reference plates with
   `ModelError: The input or output was flagged as sensitive (E005)`.
   An A/B isolated it: **identical prompt with no reference images succeeded**, so
   the flag came from the images, not the text. Plausibly the fear / grief
   close-ups read as human distress. fal exposes `enable_safety_checker` as a
   boolean, so the same content is usable.
2. **Mutually exclusive conditioning fields.** On seedance,
   `image`/`last_frame_image` and `reference_images` **cannot be combined**, so a
   chained shot cannot also carry the identity sheet. H3 Max separates these into
   distinct endpoints, which maps onto position-dependent mode validation cleanly.

---

## fal API traps

### 1. Endpoint IDs have NO `fal-ai/` prefix

The most expensive mistake in this file. The owner segment is `minimax`, so the
correct id is `minimax/h3-max/image-to-video`. With the prefix you get:

```json
{"detail":"Path /h3-max/text-to-video not found"}
```

A 404 that *looks like* a broken result-URL construction. In the origin session
the URL-building code was rewritten twice, then fal's **official client** was
tried — and reproduced the identical 404, because the identifier was wrong, not
the transport.

> **Heuristic:** when an official SDK fails in exactly the same way as your
> hand-rolled call, stop debugging transport and suspect the identifier.

Discover real ids instead of guessing:

```bash
curl -s "https://fal.ai/api/models?keywords=h3" -H "Accept: application/json"
```

Schema discovery is a separate URL and also wants the unprefixed id:

```bash
curl -s "https://fal.ai/api/openapi/queue/openapi.json?endpoint_id=minimax/h3-max/image-to-video"
```

### 2. Queue status/result URLs use the APP path, not the endpoint id

For `minimax/h3-max/image-to-video`, poll and fetch at:

```
https://queue.fal.run/minimax/h3-max/requests/{request_id}          # result
https://queue.fal.run/minimax/h3-max/requests/{request_id}/status   # status
```

fal returns this truncated two-segment form itself and **it is correct**.
Building from the full three-segment endpoint id returns `405 Method Not Allowed`.
Probe both forms with curl before writing the client.

### 3. `prompt_expansion_mode` is required, and `off` is not a value

Enum is `disabled | fast | balanced | quality`. Passing `off` yields a
`literal_error` — and the queue only surfaces it when you fetch the **result**,
not at submit time, so a naive client reports a mystery failure.

**Keep it `disabled`.** Expansion paraphrases the prompt, which would rewrite the
style bible and the exact character names the reference locks depend on.

### 4. Upload reference images; never inline them

Nine 2K PNGs as base64 data-URIs inflate a request to ~29 MB. Upload once, cache
the URL, and reuse across every shot in the scene — the same locks go to every
shot, so caching makes repeat use free.

fal upload is a two-step initiate-then-PUT flow (see `scripts/fal_client.py`).

### 5. Verified endpoint map

H3 Max **does** have reference-to-video, so there is no need to fall back to base
H3 for identity work:

```
t2v    minimax/h3-max-turbo/text-to-video     (H3 Max has no t2v of its own)
i2v    minimax/h3-max/image-to-video
flf    minimax/h3-max/image-to-video          + end_image_url
ref2v  minimax/h3-max/reference-to-video
```

`minimax/h3-max/director` also exists and is worth evaluating for **explicit
camera control** — precisely the capability that unreliable three-quarter
reference angles need (see `reference-plate-generation.md`).

### 6. A 403 "Exhausted balance" can lag a top-up

Immediately after credit was added, one endpoint returned 200 while another still
returned `403 User is locked. Reason: Exhausted balance.` A direct retry across
all endpoints minutes later returned 200 everywhere. Probe each endpoint before
concluding a permissions or account problem.

---

## Measured throughput — and the per-mode asymmetry

MiniMax H3 Max, 768P, real timings:

| Mode | Clip | Inference | Wall | Ratio to realtime |
|---|---|---|---|---|
| t2v (turbo) | 5s | 1.48s | 4.6s | **3.4x** |
| ref2v, 9 locks | 13s | 22.3s | 43.2s | **0.58x — slower than realtime** |
| flf, chained | 14s | 15.4s | 20.9s | 0.91x |
| flf, chained | 7s | 5.0s | 10.8s | 1.40x |

**`ref2v` with a full lock set is the slow mode and can run slower than
playback.** A flat "generation is ~1.7x faster than playback" assumption does not
survive contact with per-mode reality — the ratio swings roughly 6x across modes.

### Design consequence — CORRECTED by drift measurement

An earlier version of this file concluded "one `ref2v` per scene, then `flf` for
every subsequent shot," reasoning purely from the speed table. **A drift
measurement on the first real render reversed it.** Speed is the wrong axis to
optimise: `flf` is cheap precisely *because* it re-derives identity from a frame
instead of the reference sheet, and that is exactly what makes it decay.

Rated identity fidelity against the reference plates on a 3-shot chain:

| Shot | Mode | Fidelity |
|---|---|---|
| 1 | `ref2v` | **8/10** |
| 2 | `flf` ×1 | 5/10 |
| 3 | `flf` ×2 | **3/10** |

Monotonic decay, and by the third shot the character had visibly changed hair
colour and apparent age. Correct policy:

- **`ref2v` is the DEFAULT** — re-anchor identity on almost every shot.
- **`flf` is the exception**, reserved for shots that must continue an unbroken
  physical motion, and **never two in a row**. Enforce it in the validator:

```python
MAX_FLF_CHAIN = 1   # chain at most one shot off a ref2v, then re-anchor
```

Pay the `ref2v` cost. Identity drift is not recoverable in post; render time is
just money.

### The chaining mechanism is NOT the failure — shot LENGTH is

Critical distinction, because it is easy to blame the wrong component. The
handoff frames were **pixel-identical** across every cut: `shot_00`-last matched
`shot_01`-first exactly, same for the next link. The plumbing was perfect and the
cuts were invisible.

The breakage was **inside** each shot. Given 13–14 seconds, the model has enough
room to re-stage blocking, relight the set, change location and re-age a
character *within a single take*. Observed across 35 seconds of finished film:

```
night rain stone threshold  ->  sunny daylight balcony  ->  warm domestic interior
```

Location, time of day and weather all discontinuous — from three shots that were
each individually well-formed and correctly chained.

**So the provider's 15s ceiling is not the operative limit. Drift is.** Cap shots
at **4–6 seconds** and reach head duration with *more shots*, not longer ones
(3×5s, never 1×15s). This single change addresses identity drift, continuity and
style consistency simultaneously, and it inverts the "long heads buy tail runway"
guidance in `SKILL.md` §Pitfalls — long heads buy runway and destroy continuity.
Prefer more short shots.

Instruct the generator in the same terms: *"write ONE beat of action per shot — a
single gesture, a single line, a single camera move. If an action needs more than
6 seconds, split it into two shots."*

### Restate wardrobe canon on every shot prompt

The reference images carry costume visually, but a text reminder measurably
reduces wardrobe invention mid-shot. Inject the authored `costume` string into
each shot prompt alongside the style bible:

```
WARDROBE (mandatory, do not change): <name> wears: <costume canon verbatim>
```

Budget from **inference seconds, not clip count**: one 35.4s scene consumed 42.7s
of inference (~0.83x aggregate) at roughly **$1.05**. Note that shortening shots
raises the per-second cost of `ref2v` re-anchoring — measure the new figure rather
than reusing this one.

---

## Render-stage bugs worth pre-empting

Every one of these was caught by a `--dry-run` **before** any spend.

### Always ship `--dry-run` on a paid render path

Non-negotiable for spend-bearing pipelines. Print the exact payload, the resolved
reference list, and a cost estimate without calling the API. On first use it
caught three bugs at once: a 29 MB payload, duplicate reference filenames, and
mutually exclusive conditioning fields being sent together.

### Dedupe references on resolved paths, never on basename

Every character directory contains `body_00.png`. Name-based dedupe silently
drops the second character's locks — and the dry-run output made it obvious
because the same three filenames appeared twice.

### Round-robin the reference budget across characters

Filling the reference list sequentially let the first character consume the
9-slot cap and starve the second. Interleave per character, and when over budget
drop **location plates first** — identity outranks location.

### Never swallow the provider's error

A handler that printed a bare `RuntimeError: <model> failed:` hid
`E005 flagged as sensitive` for an entire debugging cycle. Always surface both
`error` and `logs` from the final poll payload; the real reason is usually in
`logs`.

```python
if status != "succeeded":
    raise RuntimeError(
        f"{model} {status}\n"
        f"  error: {pd.get('error')}\n"
        f"  logs: {(pd.get('logs') or '')[-800:]}\n"
        f"  id: {pid}")
```

---

## Audio: H3 Max cannot generate speech — condition it on a TTS track

A ported payload carried `generate_audio: True` from a previous provider. H3 Max
**silently ignores unknown fields**, so the calls succeeded and returned tracks —
but the tracks were a percussive ambience bed, not dialogue. Spectrogram analysis
caught it: ~30 evenly spaced broadband transients at a near-perfect 1.15s interval
(~52 BPM). **Speech is never metronomic.** The schema then confirmed it:

```
h3-max/image-to-video      audio fields: none
h3-max/reference-to-video  audio fields: reference_audio_urls  (INPUT only)
```

Two lessons beyond the fact itself:

- **Porting a payload between providers silently carries dead fields.** Diff your
  request against the target's schema after any provider migration; a field that
  no longer exists produces no error, just missing functionality.
- **Verify generated audio by spectrogram, not by "there is an audio stream."**
  `ffprobe` reporting an AAC track proves nothing about whether it contains speech.
  Metronomic regularity, and HF energy above 4 kHz sitting at −48 dB or lower
  (too dark for sibilance), both indicate no dialogue.

### CORRECTION — post-muxing was the wrong architecture

An earlier version of this file recommended muxing TTS over the rendered clip.
**That is wrong and was reported by a viewer as two distinct defects:** *"the
audio from the video is playing and the audio from the voices is also playing,
sometimes they line up and sometimes it's off."* Doubled audio, and no lip-sync.

Post-muxing **cannot ever** produce lip-sync, because the video is generated
before the speech exists. `reference_to_video` accepts `reference_audio_urls`, so
the voice track is an **input**:

```
WRONG   render video → mux TTS on top
RIGHT   synthesize TTS → pass as reference audio → model lip-syncs to it
```

The returned clip already contains the dialogue. **Mux nothing.** Verify by
stream count: exactly one audio stream per shot and zero `*_dub*` files on disk.
A second stream means the old ordering silently regressed.

Consequences:

- A dialogue shot **must** use `reference-to-video`. `image-to-video` has no
  audio input at all, so dialogue on a chained shot is structurally impossible —
  validate and reject it.
- **Reference audio has a minimum duration of 2s** (ceiling 15s). Real lines fall
  under it constantly — *"Who sent you?"* synthesizes to 1.44s and the prediction
  is rejected. Pad with trailing silence to the **shot length**, not merely to the
  floor: `ffmpeg -af "apad=whole_dur=5.0"`. That clears the minimum and gives the
  model audio spanning the whole clip, so the mouth is not still moving after the
  track ends.
- **Clip duration has a floor of 5s** on H3 Max: `duration: 4` returns
  `{"type":"greater_than_equal","loc":["body","duration"],"msg":"Input should be
  greater than or equal to 5"}`. It surfaces only at result-fetch, like the
  `prompt_expansion_mode` error. Combined with the 4–6s drift ceiling, the usable
  window is **5–6 seconds**.
- **Derive upload content types from the file extension.** An upload helper
  hardcoding `image/png` sent the mp3 up as a PNG and the provider rejected it
  with `Unsupported audio format: .png`. The file was fine; the declared type was
  not. Map the extension and raise on an unmapped one.

Assign one fixed voice id per character in the story file so a character sounds
identical across every shot and every run — the audio equivalent of an identity
lock. Raise TTS `stability` (~0.55) to keep delivery consistent between shots.

**Budget dialogue length in the validator, not with a warning.** Measure the real
rate (`chars / audio_seconds`) and budget at the slowest observed value — 15.7
chars/sec over three narrator voices, so a 5s shot holds ~69 characters. Reject
over-long lines at authoring time and teach the budget in the writer prompt. A
warning fires only after both audio and video are paid for.

---

## Chaining loop (flf) in practice

1. Render shot N.
2. Extract its final frame with ffmpeg:
   `ffmpeg -y -sseof -0.5 -i shot.mp4 -vsync 0 -q:v 2 -frames:v 1 last.png`
3. Pass that frame as `image_url` for shot N+1.
4. Concat with `-f concat -c copy` (no re-encode) once all shots exist.

Drift should **accumulate** along the chain, since each link inherits identity
from the previous frame rather than from the reference sheet. Verify how many
links you can chain before a fresh `ref2v` re-anchor is needed — this determines
maximum scene length, and it must be measured rather than assumed.
