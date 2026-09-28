"""Minimal fal queue client — submit, poll, upload, fetch.

Extracted from a working generative-film render pipeline. The value here is not
the HTTP plumbing but the three encoded corrections that each cost real
debugging time (see references/video-generation-providers.md):

  1. Endpoint ids have NO `fal-ai/` prefix. The owner is the first segment,
     e.g. `minimax/h3-max/image-to-video`. Prefixing yields a 404 that reads
     like a broken result URL, and fal's own official client fails identically
     because the id is wrong, not the transport.
  2. Queue status/result URLs use the APP path (first two segments), not the
     full endpoint id. fal returns this truncated form itself and it is
     correct; the three-segment form returns 405.
  3. Reference images must be UPLOADED, not inlined. Nine 2K PNGs as base64 is
     ~29MB. Upload once, cache the URL, reuse across every shot.

Requires FAL_KEY in the environment.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

UA = "GenerativePipeline/1.0"
_op = urllib.request.build_opener()
_op.addheaders = [("User-Agent", UA)]
urllib.request.install_opener(_op)

QUEUE = "https://queue.fal.run"
REST = "https://rest.alpha.fal.ai"

# NOTE: no `fal-ai/` prefix. Discover ids via
#   curl -s "https://fal.ai/api/models?keywords=<q>" -H "Accept: application/json"
ENDPOINTS = {
    "t2v": "minimax/h3-max-turbo/text-to-video",   # H3 Max has no t2v of its own
    "i2v": "minimax/h3-max/image-to-video",
    "flf": "minimax/h3-max/image-to-video",        # + end_image_url
    "ref2v": "minimax/h3-max/reference-to-video",
}

# Required field. Enum: disabled | fast | balanced | quality  (NOT "off").
# Keep DISABLED — expansion paraphrases the prompt, rewriting the style bible
# and the exact character names that reference locks depend on.
EXPANSION = "disabled"


def _key() -> str:
    k = os.environ.get("FAL_KEY")
    if not k:
        raise SystemExit("FAL_KEY not set")
    return k


def _req(url: str, data: bytes | None = None, method: str | None = None,
         extra: dict | None = None) -> urllib.request.Request:
    h = {"Authorization": f"Key {_key()}"}
    if data is not None:
        h["Content-Type"] = "application/json"
    h.update(extra or {})
    return urllib.request.Request(url, data=data, headers=h, method=method)


_UPLOAD_CACHE: dict[str, str] = {}


def upload(path: str | Path) -> str:
    """Upload a local file to fal storage, return its public URL (cached)."""
    p = Path(path)
    key = str(p.resolve())
    if key in _UPLOAD_CACHE:
        return _UPLOAD_CACHE[key]

    init = json.dumps({"file_name": p.name, "content_type": "image/png"}).encode()
    with urllib.request.urlopen(
            _req(f"{REST}/storage/upload/initiate?storage_type=fal-cdn-v3",
                 data=init, method="POST"), timeout=120) as r:
        d = json.loads(r.read())

    put = urllib.request.Request(d["upload_url"], data=p.read_bytes(),
                                 method="PUT",
                                 headers={"Content-Type": "image/png"})
    with urllib.request.urlopen(put, timeout=300):
        pass
    _UPLOAD_CACHE[key] = d["file_url"]
    return d["file_url"]


def run(endpoint: str, payload: dict, timeout: int = 900,
        poll: float = 2.0) -> dict:
    """Submit to the queue and poll to completion. Returns the result dict."""
    body = json.dumps(payload).encode()
    try:
        with urllib.request.urlopen(
                _req(f"{QUEUE}/{endpoint}", data=body, method="POST"),
                timeout=120) as r:
            sub = json.loads(r.read())
    except urllib.error.HTTPError as e:
        # A 403 "Exhausted balance" can lag a top-up and may differ per
        # endpoint. Probe each endpoint before concluding an account problem.
        raise RuntimeError(f"fal submit {endpoint} {e.code}: "
                           f"{e.read().decode()[:600]}") from None

    rid = sub.get("request_id")
    if not rid:
        raise RuntimeError(f"fal submit gave no request_id: {json.dumps(sub)[:400]}")

    # APP path only — first two segments. The full endpoint id gives 405.
    app = "/".join(endpoint.split("/")[:2])
    base = f"{QUEUE}/{app}/requests/{rid}"
    status_url, resp_url = f"{base}/status", base

    deadline = time.time() + timeout
    st: dict = {}
    while time.time() < deadline:
        with urllib.request.urlopen(_req(status_url), timeout=60) as r:
            st = json.loads(r.read())
        s = st.get("status")
        if s == "COMPLETED":
            with urllib.request.urlopen(_req(resp_url), timeout=120) as r:
                return json.loads(r.read())
        if s in ("FAILED", "ERROR", "CANCELLED"):
            # Surface everything: a bare "failed" hides the real reason
            # (e.g. a safety-checker rejection) for a whole debug cycle.
            raise RuntimeError(f"fal {endpoint} {s}: {json.dumps(st)[:800]}")
        time.sleep(poll)
    raise RuntimeError(f"fal {endpoint} timed out after {timeout}s "
                       f"(last status {st.get('status')})")


def fetch(url: str, dest: str | Path) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(urllib.request.Request(url), timeout=600) as r:
        dest.write_bytes(r.read())
    return dest


if __name__ == "__main__":
    t0 = time.time()
    out = run(ENDPOINTS["t2v"], {
        "prompt": "A stone lighthouse on a rocky island at dusk, coastal fog "
                  "drifting past, the lamp turning slowly. Anamorphic 35mm, "
                  "deep teal shadows, film grain.",
        "prompt_expansion_mode": EXPANSION,
        "duration": 5,
        "resolution": "768P",
        "aspect_ratio": "21:9",
    })
    print(json.dumps(out, indent=2)[:600])
    print(f"wall {time.time() - t0:.1f}s")
