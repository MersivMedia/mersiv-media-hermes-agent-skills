# Video model APIs — verified endpoint quirks

Session-verified detail for video generation via Replicate and fal. Costs and
availability drift; re-verify durations and ids from the live schema before relying on
them.

## Duration ceilings (verified)

| Model | Duration | Reference support |
|---|---|---|
| `bytedance/seedance-2.0` | ≤15s | `image`, `last_frame_image`, up to **9** `reference_images` |
| `bytedance/seedance-1-lite` | ≤12s | `image`, `last_frame_image`, 1–4 `reference_images` |
| `minimax/h3` (Replicate) | — | `first_frame_image`, `reference_image_urls` |
| MiniMax H3 / H3 Max (fal) | 5–15s | first+last frame, reference-to-video |

**15 seconds is the ceiling everywhere.** Any plan written around 25-second shots is
wrong by ~3x on cost. Confirm max duration from the live schema before designing shot
structure:

```bash
curl -s "https://api.replicate.com/v1/models/<owner>/<model>" \
  -H "Authorization: Bearer $REPLICATE_API_TOKEN" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print(json.dumps(d['latest_version']['openapi_schema']['components']['schemas']['Input']['properties'],indent=2))"
```

Some Replicate models expose no `latest_version` via the API. Fall back to
`default_example.input` keys to learn the field names.

## Replicate: `seedance-2.0` flagged our own reference images as sensitive

```
ModelError: The input or output was flagged as sensitive. (E005)
```

An A/B isolated it: the **identical prompt with no `reference_images` rendered fine**.
So the trigger was the reference images, not the prose — most likely tight facial
close-ups reading as human distress (fear with exposed sclera, grief/exhaustion).

Replicate exposes no way to scope this; fal has an explicit `enable_safety_checker`
boolean. **When a safety classifier blocks legitimate assets, A/B the prompt alone
first** to learn whether prose or images tripped it, before rewriting anything.

## Replicate: `image` and `reference_images` are MUTUALLY EXCLUSIVE

A frame-chained shot cannot also carry a character reference sheet. Resolve per shot:

- first shot of a scene, or any character shot with no prior frame → `reference_images`
  (establish identity)
- mid-scene continuation → chain from the real previous frame, which already contains
  correctly-locked characters, so identity is inherited *through the frame*

## Nine 2K PNGs as data URIs = 29MB request

Replicate caps around 10MB. Upload once via the files API and pass URLs, caching the
URL per resolved path since the same locks go to every shot in a scene. Request size
drops from ~29MB to under 1KB.

```python
# multipart POST to https://api.replicate.com/v1/files -> resp["urls"]["get"]
```

## Reference basenames collide across subjects

Every character directory has a `body_00.png`. **Dedupe on resolved paths, never on
name.** Round-robin per-subject locks so a 9-reference budget splits evenly instead of
the first subject consuming it all, and drop location plates before character locks
when over budget.

## fal: endpoint IDs have NO `fal-ai/` prefix

For MiniMax models the owner is `minimax`, so the correct id is
`minimax/h3-max/image-to-video`. Prefixing it returns:

```
{"detail":"Path /h3-max/text-to-video not found"}
```

That 404 **looks like a broken result URL**, not a bad endpoint id. It cost several
debugging rounds — the URL construction was rewritten twice, then fal's official
`fal-client` was installed and reproduced the *identical* 404, because the id was
wrong, not the client.

**Generalisable diagnostic: if a vendor's own official client fails exactly the way
your hand-rolled client does, the problem is your identifier, not your transport.**

Discover real ids rather than guessing:

```bash
curl -s "https://fal.ai/api/models?keywords=h3&page_size=30" -H "Accept: application/json"
curl -s "https://fal.ai/api/openapi/queue/openapi.json?endpoint_id=minimax/h3-max/image-to-video"
```

Schema discovery also wants the unprefixed id, and URL-encoding the slashes (`%2F`)
404s — pass them raw.

## fal: poll and fetch on the APP path

fal's returned `status_url` / `response_url` are truncated to the app segment, and that
truncated form is the one that works:

```
submit:  https://queue.fal.run/minimax/h3-max/image-to-video
status:  https://queue.fal.run/minimax/h3-max/requests/{id}/status   <- works
result:  https://queue.fal.run/minimax/h3-max/requests/{id}          <- works
```

Building status/result from the FULL endpoint id returns **405 Method Not Allowed**.

```python
app = "/".join(endpoint.split("/")[:2])
base = f"{QUEUE}/{app}/requests/{rid}"
```

## fal: `prompt_expansion_mode` is REQUIRED

Enum is `disabled | fast | balanced | quality`. **Not** `off` — passing `off` produces
a `literal_error` that only surfaces when fetching the *result*, after status already
reported `COMPLETED`.

Prefer `disabled` whenever prompt wording is load-bearing (style clauses, exact
subject names for reference locking). Expansion paraphrases the prompt before
generation and will rewrite precisely the language you depend on.

## fal: measured speed

`minimax/h3-max-turbo/text-to-video`, 5s clip, 768P, 21:9:

```
inference   1.48s
wall time   4.6s   (submit + queue + poll + fetch)
```

~3.4x realtime on inference. Useful when a design depends on "generation faster than
playback" — measure it rather than quoting marketing figures.

## fal: a 403 on submit can mean empty balance

```
403 {"detail":"User is locked. Reason: Exhausted balance."}
```

Valid key, valid endpoint, zero credit. Do not debug auth on this.

## Always surface the provider's real error

A handler that swallowed the API message produced:

```
RuntimeError: bytedance/seedance-2.0 failed:
```

...which wasted a full cycle. The reason was sitting in `logs` and `error`. Raise
everything:

```python
raise RuntimeError(f"{model} {status}\n"
                   f"  error: {pd.get('error')}\n"
                   f"  logs: {(pd.get('logs') or '')[-800:]}\n"
                   f"  id: {pid}")
```

Note `'pd' in dir()` does not test for an unbound local — that idiom is what hid the
payload.

## Dry-run before any video spend

Video clips cost ~100x an image. A `--dry-run` that prints exact payloads caught three
bugs at zero cost: the 29MB payload, duplicated/unbalanced references, and chained
shots being handed mutually exclusive fields. Build it into any render entry point and
have it report per-shot payload size, which references actually attached, and an
estimated cost.
