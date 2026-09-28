# Provider API traps — generative image/video

Concrete failure modes hit against live APIs, with the fix. All verified, not
speculative. Re-check schemas before trusting any table here — providers move.

## fal: endpoint IDs have NO `fal-ai/` prefix for MiniMax models

The owner segment is the actual model owner. For MiniMax the correct id is
`minimax/h3-max/image-to-video`. Prefixing it yields:

```
{"detail":"Path /h3-max/text-to-video not found"}
```

This 404 **looks like a broken result-URL bug**, not a bad endpoint id. It cost
several debugging rounds: the URL construction was rewritten twice, then fal's own
official Python client was tried and reproduced the *same* 404 — because the endpoint
id was wrong, not the client.

**Discover real ids instead of guessing:**

```
GET https://fal.ai/api/models?keywords=<query>
```

Returns entries like `minimax/h3-max/reference-to-video`. Note the discovery endpoint
for OpenAPI schemas also wants the un-prefixed form:

```
GET https://fal.ai/api/openapi/queue/openapi.json?endpoint_id=minimax/h3-max/image-to-video
```

**Lesson generalised:** when an official client reproduces your error exactly, the
input is wrong, not the transport. Stop rewriting the transport.

## fal: queue status/result URLs use the APP path

Submit to `https://queue.fal.run/<full/endpoint/id>`, but poll and fetch against the
**app** path, which is what fal itself returns:

```
submit  queue.fal.run/minimax/h3-max/image-to-video
status  queue.fal.run/minimax/h3-max/requests/<id>/status
result  queue.fal.run/minimax/h3-max/requests/<id>
```

Building status URLs from the full endpoint id gives `405 Method Not Allowed`.

## fal H3 Max: endpoint map and required fields

| Mode | Endpoint | Notes |
|---|---|---|
| text-to-video | `minimax/h3-max-turbo/text-to-video` | H3 Max has no t2v of its own |
| image-to-video | `minimax/h3-max/image-to-video` | `image_url` + optional `end_image_url` |
| first+last frame | same as i2v | set both `image_url` and `end_image_url` |
| reference-to-video | `minimax/h3-max/reference-to-video` | `reference_image_urls`, `reference_audio_urls`, `reference_video_urls` |

- `prompt_expansion_mode` is **REQUIRED**, enum `disabled | fast | balanced | quality`
  — **not** `off` (which returns a `literal_error`). Keep it **`disabled`** for
  pipeline work: expansion paraphrases the prompt, which rewrites the exact style and
  identity language your reference locks depend on.
- `duration` accepts up to 15s. `resolution` is `480P | 768P | 1080P`.
- `enable_safety_checker` is an explicit boolean — useful when a safety classifier
  flags your own reference plates (see below).
- Measured inference, 768P: 5s clip via reference-to-video ≈ **5.6s**; 13s clip ≈
  **22.3s**; a 5s chained i2v clip ≈ **2.9s**. Short clips are disproportionately
  faster, not linearly.

## Reference assets must be CITED IN THE PROMPT

This is easy to miss and silently degrades everything. H3's reference API expects
each attached asset to be **named in the prompt text**:

```
REFERENCE ASSETS:
Image 1: body reference for Ilse Wrenn
Image 2: face reference for Ilse Wrenn
Image 3: the location itself
Audio 1: the spoken dialogue for this shot
```

Attaching nine `reference_image_urls` without naming them leaves the model to guess
what each is for. A render conditioned on nine *unlabelled* references showed weak
identity conditioning "despite nine locks attached" — nine unlabelled images are not
nine locks.

Budget note: images + videos + audio must total **≤12 files**, and audio may never be
the only reference input.

## Audio: synthesize FIRST, pass as reference — never mux after

```
WRONG   render video -> mux TTS on top
        -> the model's own ambience bed plays under unrelated speech (doubled audio)
        -> mouths move independently of the words (no lip-sync)

RIGHT   synthesize TTS -> pass as reference_audio_urls -> model renders lip-synced
        -> the returned clip already contains the dialogue; mux nothing
```

Only **reference-to-video** accepts `reference_audio_urls` (2–15s each, ≤15s
combined). `image-to-video` has no audio input at all, so a chained shot **cannot**
lip-sync — enforce "dialogue implies reference-to-video" in your validator.

## Phantom parameters after a provider port

`generate_audio` is a **seedance** field. After porting a renderer from Replicate to
fal it stayed in the payload and was **silently ignored** — no error, no warning. The
resulting tracks were a ~52 BPM percussive ambience bed with no speech; spectrogram
analysis caught it and the live schema confirmed the field does not exist.

**Rule: after any provider port, diff your payload keys against the live schema.** A
parameter the API ignores fails silently and you will attribute the missing behaviour
to the model instead of your own payload.

## Payload size: upload, don't base64

Nine 2K PNGs as base64 data-URIs inflated a prediction request to **28.9MB** against
a ~10MB limit. Using each provider's file/storage API and passing URLs dropped the
same request to **0.8KB**, and uploaded assets are reusable across every shot in a
scene.

- Replicate: `POST /v1/files` (multipart), then pass `urls.get`.
- fal: `POST rest.alpha.fal.ai/storage/upload/initiate`, `PUT` to the returned
  `upload_url`, then pass `file_url`.

Cache uploads by resolved path — the same reference set is passed to every shot.

## Replicate: seedream-4 for consistent image sets

`bytedance/seedream-4` accepts 1–10 reference images via `image_input`, outputs up to
4K. `sequential_image_generation="auto"` with `max_images` returns a multi-image set
from one call — **but see the "one call per item" rule in the parent skill**: batched
sets are N independent rolls and under-deliver silently.

Measured: anchor ~12s, per-item plate ~30–40s, ~$0.02 per image.

Also available: `google/nano-banana-pro` takes up to **14** reference images at
1K/2K/4K — useful as a retouch or fallback pass.

## Safety classifiers can reject your own reference plates

A video model returned `ModelError ... flagged as sensitive (E005)` on a request whose
prompt rendered fine standalone. An A/B with the identical prompt and **no reference
images** succeeded, isolating the flag to the attached plates — most plausibly
convincing distress expressions (wide eyes, open mouth) on tight face close-ups.

Two responses: bisect by attaching subsets to find the offending asset class, and
prefer a provider that exposes an explicit safety-checker flag when the pipeline
legitimately needs distressed expressions.

## Error handling

Never write a handler that can lose the provider's message. This pattern produced a
bare `failed:` and cost a whole debugging cycle:

```python
raise RuntimeError(f"{model} {status}: {pd.get('error') if 'pd' in dir() else ''}")
```

`dir()` with no argument does not do what that expression assumes, and the useful
detail is usually not in `error` anyway. Surface all three:

```python
raise RuntimeError(
    f"{model} {status}\n"
    f"  error: {pd.get('error')}\n"
    f"  logs: {(pd.get('logs') or '')[-800:]}\n"
    f"  id: {pid}")
```

Also: initialise the poll payload to the submit response so it is never unbound when
the job fails on the first check.

## Transient 403s on a fresh balance

A newly funded account returned `403 User is locked. Reason: Exhausted balance` on one
endpoint while another returned 200 for the same key. It cleared on its own within a
few minutes. If auth and endpoint id are otherwise proven, probe each endpoint once
before concluding anything is wrong with the code.
