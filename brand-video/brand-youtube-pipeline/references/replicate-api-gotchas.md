# Replicate API Gotchas ([brand] Pipeline)

Three failure modes that all look like `HTTP 403 Forbidden` (or unhelpful 422)
but have nothing to do with auth. Hit any of them and you'll burn 5-10 attempts
debugging the wrong layer.

The umbrella `replicate-api-generation` skill is the canonical home for these
patterns — this file is the [brand]-specific summary so the pipeline-side
agent doesn't have to load that skill for a quick reference.

## 1. `Prefer: wait=N` + large request bodies → silent 403

**Symptom:** Identical payload works in `curl` but the Python script gets `HTTP 403 Forbidden` with no useful response body.

**Cause:** The synchronous-wait path on `/v1/predictions` rejects requests where the JSON body exceeds ~1MB. Our character poses are 1.5MB PNGs → 2MB+ as base64 data URIs. Standard talking-head audio chunks are smaller and squeeze through.

**Fix path A (preferred for big inputs):** upload via the files API first, pass the returned URL:

```python
import uuid, urllib.request, json
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
with urllib.request.urlopen(req, timeout=120) as r:
    file_url = json.loads(r.read())["urls"]["get"]

# Now reference file_url in the predictions input — fits in any-size payload.
```

**Fix path B (when prediction body is the only thing that's big):** drop the `Prefer: wait` header entirely and poll. The async submit path accepts much larger bodies. Live `strip_pose_backgrounds.py` uses this pattern.

## 2. `Python-urllib/X.Y` User-Agent → silently filtered to 403

**Symptom:** Identical payload + identical headers in `curl` work fine. From Python `urllib.request`, same payload returns `HTTP 403` with no detail. Switching to `requests` library also works.

**Cause:** Replicate's predictions endpoint filters the default `urllib` User-Agent (`Python-urllib/3.12`). The block is silent — no rate-limit message, no challenge, just 403.

**Fix:** install a global opener with a non-default UA at the top of any script using `urllib`:

```python
import urllib.request
UA = "Brand-Pipeline/1.0"  # any non-default string works
_opener = urllib.request.build_opener()
_opener.addheaders = [("User-Agent", UA)]
urllib.request.install_opener(_opener)
```

This applies to every `urllib.request.urlopen()` in the process. If you're using `requests`, it's already fine — its default UA isn't on the blocklist.

## 3. Don't trust the first 403 — check both 1 and 2 simultaneously

When a new Replicate integration starts 403'ing on the first run, the failure could be either gotcha (or both). The diagnostic sequence:

1. Try the same call via `curl` from the terminal. Works? → it's a Python-side issue → apply fix #2 (custom UA opener).
2. Curl also 403s? → check payload size. If `Content-Length: > 1MB` and you're using `Prefer: wait`, → apply fix #1 (files API upload OR drop `Prefer: wait`).
3. Both apply? → fix #2 first (cheaper to test), then fix #1.

`strip_pose_backgrounds.py` was held up by both at once. After fixing only one, the script still 403'd — the second symptom looked like the first hadn't actually worked. Address both before re-running.

## Symptoms vs causes (debug table)

| Symptom | Cause | Fix |
|---------|-------|-----|
| curl works, urllib 403s | Default `Python-urllib/X.Y` UA filtered | Install opener with custom UA |
| 403 only on big payloads, smaller payloads work | `Prefer: wait` body cap | Drop `Prefer: wait` OR upload via files API first |
| 422 with `aspect_ratio` field | gpt-image-2 only accepts 1:1, 3:2, 2:3 | Pick supported ratio, crop in PIL after |
| 422 with `output_format` field | gpt-image-2 only accepts jpeg/png/webp | Use `jpeg` not `jpg` |

## Verified working scripts

- `scripts/strip_pose_backgrounds.py` — uses both fixes (files API upload + custom UA opener). Reference implementation.
- `scripts/emit_tts_chunks.py` — passes small text payloads to ElevenLabs directly. No Replicate workaround needed.
