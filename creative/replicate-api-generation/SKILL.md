---
name: replicate-api-generation
description: Generate images and video directly via Replicate REST API — model selection, image-to-image editing, first-frame/last-frame video interpolation, brand-asset iteration workflows. Use when the user asks for AI image/video generation through Replicate (flux, gpt-image, seedance, kling, etc.) or for iterative refinement of brand assets.
related_skills: [character-reference-sheet]
---

# Replicate API: Image & Video Generation

Direct REST calls to `api.replicate.com` for image and video models. Works from `terminal` with `curl` or Python `urllib`. Required env var: `REPLICATE_API_TOKEN`.

Reach for this when:
- User mentions Replicate by name, links a `replicate.com/<owner>/<model>` URL, or asks to use a specific Replicate model.
- User wants iterative image refinement (edit an existing image, not regenerate from scratch).
- User wants video with controlled start/end frames.
- The `inference-sh-cli` or `comfyui` skills don't fit because the user specified Replicate as the platform.
## Character references

For character sheets or multi-angle identity sets, use the `character-reference-sheet` skill rather than hand-rolling calls: it wraps seedream-4.5 / nano-banana-pro / flux-2-pro i2i with one call per plate, uploads through the files API, asserts the returned count, and composes the sheet with drawn (never generated) text.

## Pitfall: do NOT use the wrapper packages

There is often a stub `custom-tools/replicate/` or partial install in the workspace. Use the **REST API directly** via `urllib` or `curl`. Skip `pip install replicate` and any custom wrappers — they shadow each other and the failure modes are opaque.

## Core call pattern

```python
import os, json, time, urllib.request

TOKEN = os.environ["REPLICATE_API_TOKEN"]
MODEL = "black-forest-labs/flux-2-pro"  # owner/model

body = json.dumps({"input": {"prompt": "...", "aspect_ratio": "1:1"}}).encode()
req = urllib.request.Request(
    f"https://api.replicate.com/v1/models/{MODEL}/predictions",
    data=body,
    headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "Prefer": "wait=60",   # MAX is 60 — sets server-side blocking wait
    },
)
with urllib.request.urlopen(req, timeout=120) as r:
    resp = json.loads(r.read())

# Poll until terminal status
pid = resp["id"]
status = resp.get("status")
output = resp.get("output")
deadline = time.time() + 360
while status not in ("succeeded","failed","canceled") and time.time() < deadline:
    time.sleep(3)
    poll = urllib.request.Request(
        f"https://api.replicate.com/v1/predictions/{pid}",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    with urllib.request.urlopen(poll, timeout=30) as r:
        pd = json.loads(r.read())
    status = pd.get("status"); output = pd.get("output")
```

**`Prefer: wait=N` max is 60 seconds.** Anything higher returns 422. Use 60 + polling for long jobs.

## Pitfall: `Prefer: wait` 403s on large request bodies

When the prediction `input` includes a base64 data URI larger than ~1MB (typical for high-res PNGs, audio files), the `Prefer: wait=N` synchronous-wait path 403s with no useful error body. The async submit + poll path (same request without the `Prefer` header) works fine for the same payload.

**Fix:** for inputs over ~1MB total, drop `Prefer: wait` entirely and rely on the poll loop. Don't try to chase the 403 — it's a quirk of the wait path, not an auth issue.

Better fix when uploading multiple large files: use Replicate's files API to upload first, pass URLs in the input:

```python
# Upload via multipart, get a URL, then submit prediction with that URL
boundary = f"----HermesBoundary{uuid.uuid4().hex}"
body = bytearray()
body.extend(f"--{boundary}\r\n".encode())
body.extend(b'Content-Disposition: form-data; name="content"; filename="')
body.extend(image_path.name.encode())
body.extend(b'"\r\n')
body.extend(b"Content-Type: image/png\r\n\r\n")
body.extend(image_path.read_bytes())
body.extend(b"\r\n")
body.extend(f"--{boundary}--\r\n".encode())

req = urllib.request.Request(
    "https://api.replicate.com/v1/files",
    data=bytes(body),
    headers={"Authorization": f"Bearer {token}",
             "Content-Type": f"multipart/form-data; boundary={boundary}"},
    method="POST",
)
with urllib.request.urlopen(req) as r:
    file_url = json.loads(r.read())["urls"]["get"]
# Now pass file_url as "image": file_url in the prediction input
```

## Pitfall: `Python-urllib/X.Y` User-Agent gets silently filtered to 403

The default `urllib.request` User-Agent (`Python-urllib/3.12`) is rate-limited / blocked by Replicate's predictions endpoint. Symptom: identical payload works via `curl` but 403s from `urllib`. There's no "User-Agent blocked" error — just 403 with no detail.

**Fix:** install a global opener with a custom UA at the top of any script that calls Replicate from `urllib`:

```python
UA = "Brand-Pipeline/1.0"  # or any non-default string
opener = urllib.request.build_opener()
opener.addheaders = [("User-Agent", UA)]
urllib.request.install_opener(opener)
```

This applies to every `urllib.request.urlopen()` call in the process. Skip this and you'll burn 5+ attempts debugging "why does curl work but my Python script doesn't."

## Pitfall: `execute_code` sandbox does not inherit env vars

`REPLICATE_API_TOKEN` is not visible inside `execute_code`. Run Replicate API scripts from `terminal` instead. (Same goes for `GOOGLE_*` creds and most other secrets.)

## Image-to-image editing (CRITICAL workflow)

When the user wants to **tweak** an existing image rather than regenerate, ALWAYS use image-to-image with the previous output as input. Regenerating from a text prompt almost always produces a different composition that throws away the parts they liked.

Strong user signal: "use the original image as input", "iterate on this", "fix only X", "keep everything the same except". When you hear this, IMMEDIATELY switch to i2i mode.

Encode the source as a data URI:

```python
import base64
with open("/path/to/original.png", "rb") as f:
    DATA_URI = "data:image/png;base64," + base64.b64encode(f.read()).decode()

body = json.dumps({"input": {
    "prompt": "Keep this exact composition identical — <describe what stays>. "
              "Only ONE change: <describe the single edit>.",
    "input_images": [DATA_URI],
    "aspect_ratio": "match_input_image",
    "output_format": "png",
}}).encode()
```

The phrase **"Only ONE change"** in the prompt dramatically improves i2i fidelity. State everything that should stay the same, then state the single edit.

## Model selection cheat sheet

| Task | Model | Why |
|------|-------|-----|
| General image generation | `black-forest-labs/flux-2-pro` | Best general quality, supports 1:1, 3:2, 2:3, 4:3, 3:4, 16:9, 9:16, custom |
| Text/typography in images | `openai/gpt-image-2` | Far better at rendering legible text. **Required for wordmarks, logos with letterforms, letter substitutions.** |
| Image editing (general) | `black-forest-labs/flux-2-pro` with `input_images` | Good for compositions without text |
| Image editing (with text) | `openai/gpt-image-2` with `input_images` | Required when the source or edit involves rendered text |
| Consistent multi-image sets / character sheets | `bytedance/seedream-4` with `image_input` (1–10 refs) | i2i from a canonical anchor. **One call per item** — see the multi-image pitfall below |
| Many reference images | `google/nano-banana-pro` (up to 14 refs, 1K/2K/4K) | Highest reference count; good retouch/fallback pass |
| Video with first+last frame | `bytedance/seedance-2.0` | Supports `image` (first) + `last_frame_image`; up to 15s; can generate audio |
| Video with character reference locks | `bytedance/seedance-2.0` (up to 9 `reference_images`) | Richest reference surface on Replicate. NOTE: `image` and `reference_images` are **mutually exclusive** |
| Video, lighter/cheaper | `bytedance/seedance-1-lite` | ≤12s, 1–4 `reference_images`, `camera_fixed` |
| Voice cover (swap the singer) | `zsxkib/realistic-voice-cloning` | Separation + conversion + remix in one call. **Preserves** the original instrumental |
| Stem separation | `ryan5453/demucs`, or `triadmusic/stems-separator` for a `youtube_url` | Returns a **dict of stems**; there is no `mixture` key |
| Style/genre cover | No single model — chain separation → `sakemin/musicgen-remixer` → optional voice swap | `minimax/music-01` does it in one call but caps at ~60 s |
| Melody-conditioned cover (new arrangement) | Not on Replicate — self-hosted YuE2 | **Regenerates** the backing track; see `references/audio-models.md` |

Audio details, the full verified survey, the preserve-vs-regenerate decision, and
the text-only models that look like cover models are in `references/audio-models.md`.

**`minimax/h3-max` is 404 on Replicate** — the fal-post-trained fast variant is
fal-exclusive. Base `minimax/h3` is available here without that speed. Latency-critical
paths may need fal alongside Replicate; measured on fal,
`minimax/h3-max-turbo/text-to-video` returned a 5s 768P clip at **1.48s inference /
4.6s wall** (~3.4x realtime). Full reference-input matrix:
`references/multi-image-sets-and-reference-locks.md` §5. fal endpoint quirks (no
`fal-ai/` prefix, app-path polling, required `prompt_expansion_mode`):
`references/video-model-apis.md`.

## When a vendor's own client fails identically, suspect your IDENTIFIER

Generalisable debugging rule, learned expensively. A 404 whose body named a *path*
(`{"detail":"Path /h3-max/text-to-video not found"}`) was read as a broken result-URL
construction. Two rewrites later, installing the vendor's official client reproduced
the **exact same 404** — because the endpoint id was wrong, not the transport.

**If an official SDK fails the same way your hand-rolled HTTP does, stop debugging
transport and go verify the identifier against a live registry.** Do not guess ids;
list them (`https://fal.ai/api/models?keywords=<q>` for fal,
`/v1/models/<owner>/<model>` for Replicate).

Corollary: a `403` on submit with a known-good key may be **billing**, not auth —
`{"detail":"User is locked. Reason: Exhausted balance."}`.

## Pitfall: gpt-image-2 aspect ratios are restricted

Only accepts `1:1`, `3:2`, `2:3`. Any other value → 422 error. Pick the closest ratio and crop/extend in PIL afterward if you need exact dimensions.

## Pitfall: gpt-image-2 `output_format` must be `jpeg`/`png`/`webp`

`jpg` is rejected with HTTP 422 — the schema enum is strict. Use `jpeg`.

## Pitfall: flux-2-pro fails at letter substitutions in wordmarks

When the user wants something like "replace the O in [BRAND] with a logo shape" — flux outputs glitched text. Use `openai/gpt-image-2` with the original wordmark as `input_images`. It handles letterform replacements cleanly.

## Video: first-frame to last-frame interpolation

`bytedance/seedance-2.0` supports `image` (first frame) + `last_frame_image` (last frame) + `prompt` (animation description).

**Pitfall — background drift between frames:** if the first frame and last frame have **different backgrounds** (e.g. first = empty bg, last = bg + logo composited on top), the model interpolates the entire image and the background morphs visibly during the animation.

**Fix:** make the first frame's background pixel-identical to the last frame's background. Build the first frame by running the *exact same processing pipeline* (cover-fit, darken, etc.) that was used on the background layer of the last frame, then save without compositing the foreground elements. Only the foreground (logo, text, overlays) should differ between the two frames.

Other video pitfalls:
- `duration: -1` lets the model pick — useful when you don't know how long the animation needs.
- `generate_audio: True` adds synced sound from the prompt — use double-quoted dialogue or sound-effect descriptions.
- Polling deadline should be 600s+ for video; jobs commonly take 3-5 min.
- Submit video jobs with `terminal(background=True, notify_on_complete=True)` so you can keep working.

## Pitfall: large payloads when sending images as data URIs

Encoding multiple high-res PNGs as base64 inflates the request body to multi-MB. Replicate accepts up to ~10MB request bodies but the upload is slow. If you need to pass many large images, host them somewhere (Drive public link, S3, etc.) and pass URLs instead.

Measured on nine 2K PNGs passed as `reference_images`: **28.88 MB inline vs 0.80 KB** after uploading via the files API and passing URLs. Cache uploads by resolved path so the same references reused across many predictions upload once. See `references/multi-image-sets-and-reference-locks.md` §2.

## Pitfall: multi-image "sets" are N independent rolls, not a set

`sequential_image_generation="auto"` (seedream-4, up to 15 images) does NOT produce a
coherent set. Each image is an independent roll sharing one prompt, so anything
requiring **contrast between items** — distinct camera angles, distinct expressions,
matched backdrops — is left to chance. Observed in one session: a 9-image request
silently returned **6** with `status: "succeeded"`, two requested emotions converged,
an angle ladder skewed, and backdrop brightness varied by up to 130/255 across a set.

**Fix: one prediction per item**, focused brief, `sequential_image_generation="disabled"`.
~$0.02 per image and fully deterministic. `max_images` is a CEILING, not a target —
always assert the returned count instead of trusting `succeeded`.

Full failure table, the `_expect()` assertion helper, and reference-budget allocation
rules are in `references/multi-image-sets-and-reference-locks.md`.

## Pitfall: surface the REAL error, or lose a debugging cycle

A bare `RuntimeError: <model> failed:` hides everything useful. Replicate puts the
reason in `error` **and** `logs`:

```python
if status != "succeeded":
    raise RuntimeError(
        f"{model} {status}\n"
        f"  error: {pd.get('error')}\n"
        f"  logs: {(pd.get('logs') or '')[-800:]}\n"
        f"  id: {pid}")
```

Avoid `pd.get('error') if 'pd' in dir() else ''` — inside a function `dir()` returns
local *names*, so that guard silently yields an empty message. Initialise `pd = d`
before the poll loop. Fixing this turned an opaque `failed:` into
`ModelError: ... flagged as sensitive (E005)`, a completely different investigation.

## Pitfall: `latest_version` can be null on the schema probe

Some models (observed on `minimax/h3`) return `latest_version: null`, so the
schema-dump one-liner raises `TypeError: 'NoneType' object is not subscriptable`, and
`/versions` 404s. Guard with `.get("latest_version")` and fall back to
`default_example.input` keys to discover field names.

## Dry-run any payload assembling more than two inputs

Print the exact payload, the resolved input list, and the serialized byte size before
submitting. On a 9-reference video request this caught three bugs pre-spend: an over
-limit body, duplicate/unbalanced reference selection, and a mutually-exclusive field
conflict. Cheaper than the first failed prediction.

## Output: download immediately

`output` is a URL (or list of URLs) that **expires in ~1 hour**. Always download the bytes immediately after generation succeeds and save to disk.

```python
url = output if isinstance(output, str) else output[0]
img = urllib.request.urlopen(url, timeout=60).read()
with open(out_path, "wb") as f:
    f.write(img)
```

## Brand-asset workflow (composite > regenerate)

When working on brand systems (logos, lockups, banners, social images):

1. **Generate base assets via Replicate** (emblem, wordmark) — these are the AI-touched parts.
2. **Composite everything else in PIL** (lockups, banners, transparent versions, outlines, favicons, social formats). Pixel-perfect, no AI drift, exact brand colors.
3. **Only use AI generation for backgrounds and one-of textures.** Logos, wordmarks, and lockups should be reproducible from the same source assets every time.

This pattern shipped 20+ assets in one session for the [brand] brand. See `references/brand-asset-composition.md` for the PIL recipes (transparent backgrounds, outlines, lockups, favicons).

## Cost notes

- `flux-2-pro`: ~$0.04/image
- `gpt-image-2` high quality: ~$0.17/image (quality "high"), ~$0.05 (quality "medium")
- `seedance-2.0`: ~$0.30-0.50 per 5-7s clip
- Batch wisely. For 25+ images of the same type, do a test of 1, validate, then run the batch.

## A description states intent; only the INPUT SCHEMA states capability

Model cards, blog posts and LLM-suggested pipelines describe what a model is
*for*. The schema describes what it can actually accept. When those disagree the
schema wins, and the disagreement is common enough to check every time.

Two measured instances from one session, both from a user-supplied pipeline:

```
fofr/sheetsage      404 — the model does not exist at all
fofr/yue            exists, described as a music generator, but its inputs are
                    lyrics + genre_description only. No audio, no score.
                    It cannot cover anything.
minimax/music-1.5   advertises 4-minute songs with vocals; inputs are
                    lyrics + prompt. No audio input -> not a cover model.
```

A pipeline built from those IDs fails in the worst way: extra input keys are
**silently ignored**, so the call succeeds and returns confident, unrelated
output rather than an error.

**Verify every model ID against the live API before writing a line of code** —
and before quoting a price or a capability to the user. Check existence with
`GET /v1/models/{owner}/{name}`, then dump the schema (below). The transform a
model performs is defined by which inputs carry `format: uri`; if the thing you
want to transform has nowhere to go, the model cannot do the job.

This is the same lesson as the identifier-verification rule above, arriving from
the other direction: there, an official SDK reproduced a hand-rolled 404 because
the *id* was wrong; here, a valid id does not imply the *capability* claimed for
it. Registry-verify both.

## Pitfall: schema check before guessing fields

Different models have different input fields. Before generating, dump the schema:

```bash
curl -s "https://api.replicate.com/v1/models/<owner>/<model>" \
  -H "Authorization: Bearer $REPLICATE_API_TOKEN" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d['latest_version']['openapi_schema']['components']['schemas']['Input']['properties'], indent=2))"
```

This shows every input field, default, and constraint (including the aspect ratio enum). Saves a round of 422 errors.

## Validating outputs after a prompt fix

When you iterate on a prompt to remove a visual artifact (floating logo, jittery camera, face drift), don't trust solo-frame vision checks — they compare to a physical-sim ideal and report "still wrong" even after meaningful fixes. Use the labeled OLD-vs-NEW A/B grid pattern in `references/output-validation.md`: dense-sample frames during motion peaks, build a two-row labeled PIL grid, then ask `browser_vision` a COMPARATIVE question ("is this better in NEW than OLD") not a binary one ("is this fixed").

## Know what is promptable before you iterate

**Anything you can measure, COMPUTE — prompts are for content, arithmetic is for
quantities.** Reaching for stronger prompt language on a measurable property is the
most common way to burn a session. Verified across many attempts:

| Property | Verdict |
|---|---|
| Backdrop/background brightness | **NOT promptable** — normalize in PIL (luma-only gamma) |
| Intermediate camera angles (45° three-quarter) | **NOT promptable** — ship front/profile/back, drop the rest |
| Emotion and expression | Promptable, but only as **physical muscle action**, never as emotion labels |
| Apparent age, wardrobe | Promptable only when **anchored to the reference image**, not to a number |
| Unwanted rendered features | Negate the **feature and its mechanism**, not its colour/attributes |
| Style/grade on a reference plate | Must be **excluded** — it propagates through i2i into every derived image |

Full measurements, the luma-only gamma recipe, the QC-gate thresholds, and the
"suspect your own fix" pattern are in `references/prompt-vs-compute.md`. Read it
before iterating on a prompt more than twice.

**Three failed attempts is enough evidence.** If a property has resisted three
generations of escalating prompt specificity, it is not a prompt problem — either
compute it in post or drop the requirement. Keep raw originals in a `_raw/` sibling
directory so a buggy post-process never forces a regeneration.

## Linked references

- `references/brand-asset-composition.md` — PIL recipes for transparent bgs, outlines, horizontal/vertical lockups, favicons.
- `references/output-validation.md` — A/B vision-grid pattern for verifying that a prompt fix actually landed.
- `references/multi-image-sets-and-reference-locks.md` — consistent multi-image sets, `sequential_image_generation` failure modes, files-API upload caching, error surfacing, video-model reference-input matrix, reference-budget allocation, content-safety (E005) isolation method.
- `references/prompt-vs-compute.md` — what a model will and won't obey: luma-only gamma normalization, unpromptable camera angles, muscle-action expression prompts, objective QC gate thresholds, "suspect your own fix".
- `references/video-model-apis.md` — video duration ceilings, `image` vs `reference_images` mutual exclusion, content-safety (E005) A/B isolation, and fal-specific quirks (unprefixed endpoint ids, app-path status/result polling, required `prompt_expansion_mode`, measured H3 Max speed, balance-as-403).
- `references/audio-models.md` — music, cover and voice-conversion models: the preserve-vs-regenerate decision that picks the tool, the `format: uri` capability check, a verified survey of cover/voice/separation models, the text-only models that masquerade as cover models, the multi-step chain for full-length style covers, the audio-specific API rules (pinned versions, 15 s reference minimum, stem-dict output), and the self-hosted YuE2 fallback with measured weight sizes.
- `scripts/replicate_generate.py` — reusable helper for parallel generation with polling.

## Verifying image output when you cannot see images

Text-only agents must delegate visual judgement, and generated sets **look plausible
while drifting badly**. File sizes clustering correctly is a useful prior but is NOT
verification.

Scope the delegation tightly. One request to verify 10 images across 6 questions
burned 50 API calls, hit the iteration cap, and confirmed only 3 files, because the
child retried a flaky vision tool. Effective shape:

- **Build contact sheets with PIL first** (one row per group), then have the child
  judge the single montage rather than opening ten files.
- **One group per subagent** (e.g. 5 angles, or 4 expressions), dispatched in
  parallel — not one child for everything.
- Include verbatim: *"if the vision tool returns a loader stub, retry AT MOST TWICE,
  then STOP and report 'vision tool unavailable'. An honest partial report beats an
  exhausted one. Do not fabricate observations."*
- Name the **specific known failure mode** under test so the child hunts for it.
- Demand that unverified files be reported as unverified.

Partial honest reports are worth having: a truncated run still caught both a
style-grade leak and an angle-ladder defect that automated checks had passed.
