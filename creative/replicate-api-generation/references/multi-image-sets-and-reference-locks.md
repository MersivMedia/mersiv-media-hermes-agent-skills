# Replicate: multi-image sets, reference locks, and video model matrix

Session-verified detail for jobs that need **many images to be consistent with each
other**, or that feed reference images into a video model. Companion to the main
SKILL.md pitfalls.

## 1. `sequential_image_generation="auto"` is N independent rolls, NOT a set

`bytedance/seedream-4` accepts `sequential_image_generation: "auto"` with
`max_images` up to 15 and returns multiple images from one call. It is tempting to
treat that as "generate a coherent set". It is not.

Same mechanism, four different-looking failures observed in one session:

| Batched request | Failure |
|---|---|
| "9 images: 5 body angles + 4 face emotions" | silently returned **6** (5 body, 1 face) |
| "5 distinct camera angles" | angle ladder skewed; requested 45° views wrong |
| "4 distinct emotions" | two emotions converged (pixel delta 4.46 vs tolerance 6.0) |
| any sequential batch | backdrop brightness spread **29–130/255** across the set |

Anything requiring **contrast between items** — distinct angles, distinct
expressions, matched backdrops — is left to chance, because each image is an
independent roll sharing one prompt.

**Fix: iterate in your own code. One prediction per item**, each with a focused brief
and `sequential_image_generation: "disabled"`. ~$0.02 per image, fully deterministic.

Reserve batched `auto` for when you genuinely want unspecified variations on a theme.

### `max_images` is a CEILING and under-delivery is SILENT

A 9-image request returned 9 for one subject and **6** for the next, with
`status: "succeeded"` and no error. Always assert the count before using the result:

```python
def _expect(urls, want, label):
    if len(urls) != want:
        raise RuntimeError(f"{label}: expected {want}, got {len(urls)}. Re-run; "
                           "do not proceed with an incomplete set.")
    return urls
```

Never infer success from `status == "succeeded"` on `auto` mode — count the outputs.

## 2. Upload once, cache the URL

Base64 data-URIs are fine for one or two images. Nine 2K PNGs are not:

```
inline data-URIs:  28.88 MB request body   (Replicate limit ~10 MB)
files API + URLs:   0.80 KB request body   (+21.7 MB uploaded once)
```

Cache by resolved path so repeated use across many predictions is free — the same
reference locks typically go to every shot in a scene:

```python
_UPLOAD_CACHE: dict[str, str] = {}

def upload_file(p: Path) -> str:
    key = str(p.resolve())
    if key in _UPLOAD_CACHE:
        return _UPLOAD_CACHE[key]
    # multipart POST /v1/files, form field name "content"
    # url = json.loads(resp)["urls"]["get"]
    _UPLOAD_CACHE[key] = url
    return url
```

## 3. Surface the real API error

A bare `RuntimeError: <model> failed:` costs an entire debugging cycle. Replicate puts
the useful text in `error` **and** `logs`. Include both plus the prediction id:

```python
if status != "succeeded":
    raise RuntimeError(
        f"{model} {status}\n"
        f"  error: {pd.get('error')}\n"
        f"  logs: {(pd.get('logs') or '')[-800:]}\n"
        f"  id: {pid}")
```

**Anti-pattern that silently ate the message:**
`pd.get('error') if 'pd' in dir() else ''`. Inside a function `dir()` returns local
*names*, so this guard misbehaves and yields an empty error. Initialise the poll
variable (`pd = d`) before the loop and reference it directly.

Doing this turned an opaque `failed:` into
`ModelError: The input or output was flagged as sensitive (E005)` — a completely
different investigation.

## 4. Schema probe: guard for `latest_version: null`

Some models (observed on `minimax/h3`) return `latest_version: null`, so the usual
path raises `TypeError: 'NoneType' object is not subscriptable`, and the `/versions`
sub-endpoint 404s. Fall back to the example input to discover field names:

```python
d = json.load(...)                       # GET /v1/models/<owner>/<model>
lv = d.get("latest_version")
if lv:
    props = lv["openapi_schema"]["components"]["schemas"]["Input"]["properties"]
else:
    ex = d.get("default_example") or {}
    print(list((ex.get("input") or {}).keys()))
```

Always `.get("latest_version")`, never index it directly.

## 5. Video model reference-input matrix (verified live)

| Model | Duration | Reference inputs |
|---|---|---|
| `bytedance/seedance-2.0` | ≤15s (`-1` = model picks) | `image`, `last_frame_image`, up to **9** `reference_images`, 3 `reference_audios`, 3 `reference_videos`, `generate_audio` |
| `bytedance/seedance-1-lite` | ≤12s | `image`, `last_frame_image`, **1–4** `reference_images`, `camera_fixed`, `fps` [24] |
| `bytedance/seedance-1-pro` | ≤12s | `image`, `last_frame_image` (no `reference_images`) |
| `minimax/h3` | schema not exposed | `first_frame_image`, `reference_image_urls`, `reference_audio_urls`, `reference_video_urls`, `ratio`, `resolution` |
| `minimax/hailuo-02` | — | `first_frame_image`, `last_frame_image` |
| `minimax/hailuo-2.3` / `-fast` | — | `first_frame_image` only |
| `minimax/video-01` | — | `first_frame_image`, `subject_reference` |
| `wan-video/wan-2.5-i2v` | — | `image` |
| `kwaivgi/kling-v2.1` | — | none exposed |

`seedance-2.0` has the richest reference surface on Replicate — 9 reference images
plus first/last frame plus native audio.

**`minimax/h3-max` is 404 on Replicate.** The fal-post-trained fast variant
(~3s wall time for a 5s clip) is fal-exclusive. If a project needs that speed for a
latency-critical path, plan a two-provider deployment: fal for the fast path,
Replicate for everything else. Base `minimax/h3` *is* on Replicate, without the speed.

Image-side companion: `google/nano-banana-pro` takes up to **14** reference images at
1K/2K/4K — useful fallback or retouch pass alongside `seedream-4`'s 1–10.

## 6. seedance-2.0: `image` and `reference_images` are MUTUALLY EXCLUSIVE

Stated in the schema description, enforced by the API. A shot chained from a previous
frame **cannot also carry a character reference sheet**. If a pipeline needs both
continuity chaining and identity locks, decide per shot which carries identity:

- **Establishing shot** (no prior frame) → `reference_images`, to establish identity.
- **Continuation shot** → `image` chained from the real previous frame. Identity is
  inherited *through the frame*, which already contains the correctly-locked subject.

Chaining does not lose identity; it changes how identity is carried. Log which path
each shot took — a chained shot that silently fell back to references behaves
differently and should be visible in run metadata.

## 7. Allocating a hard reference cap across subjects

With a 9-reference ceiling and 2+ subjects on screen:

- **Dedupe on resolved paths, never basenames.** Parallel asset directories usually
  reuse filenames (`body_00.png` in every character folder), so name-based dedupe
  silently drops the second subject's locks and double-lists the first.
- **Round-robin interleave** per subject instead of concatenating. Concatenation lets
  the first subject consume the whole budget; interleaving produced a clean 4/4 split
  plus one location plate.
- **Drop scene/location references before subject references** when over budget.
  Identity is the harder problem.

## 8. Isolating a content-safety flag (E005)

`seedance-2.0` can fail with:

```
ModelError: The input or output was flagged as sensitive.
Please try again with different inputs. (E005)
```

The message does not say *which* input. **Validated isolation method:** re-submit the
identical prompt with the reference images removed, at minimum cost (480p, 5s, no
audio, ~$0.05). If the prompt-only request succeeds, the flag is in the images; if it
fails, it is in the text. This localised one case to the reference images in a single
cheap call.

Continue bisecting by group (subject plates only, then expression plates only) at the
same minimum settings. Note that emotionally intense close-ups are a plausible
classifier trigger, but that remains a hypothesis unless the bisect confirms it — do
not assume a fix without the measurement.

## 9. Always dry-run a multi-image payload before spending

A `--dry-run` mode that prints the exact payload, the reference list, and the
serialized size caught three separate bugs before a single cent was spent: a 29 MB
over-limit body, duplicate/unbalanced reference selection, and a mutually-exclusive
field conflict. For anything assembling more than two inputs, build the dry-run
first — it is cheaper than the first failed prediction.
