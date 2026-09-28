#!/usr/bin/env python3
"""Generate video with ByteDance Seedance via the Replicate API.

Submits a prediction, polls to completion, downloads the result.
Uses curl for all HTTP (Replicate 403s some default user agents).

Usage:
    python3 seedance.py --prompt "..." --duration 10 --output-dir ./outputs
"""

import argparse
import base64
import json
import mimetypes
import os
import subprocess
import sys
import time
from pathlib import Path

API = "https://api.replicate.com/v1"

MODELS = {
    "2.5": "bytedance/seedance-2.5",
    "2.0": "bytedance/seedance-2.0",
    "1-pro": "bytedance/seedance-1-pro",
    "1-lite": "bytedance/seedance-1-lite",
}

RESOLUTIONS = ["480p", "720p"]
ASPECT_RATIOS = ["16:9", "4:3", "1:1", "3:4", "9:16", "21:9", "adaptive"]


def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def token():
    t = os.environ.get("REPLICATE_API_TOKEN")
    if not t:
        die("REPLICATE_API_TOKEN is not set")
    return t


def curl(method, url, payload=None, timeout=120):
    """HTTP via curl. Returns (status_code, parsed_body_or_text)."""
    cmd = [
        "curl", "-sS", "-X", method, url,
        "-H", f"Authorization: Bearer {token()}",
        "-H", "Content-Type: application/json",
        "-w", "\n__STATUS__%{http_code}",
        "--max-time", str(timeout),
    ]
    if payload is not None:
        cmd += ["-d", json.dumps(payload)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        die(f"curl failed: {r.stderr.strip()}")
    out = r.stdout
    body, _, status = out.rpartition("\n__STATUS__")
    try:
        return int(status), json.loads(body)
    except (ValueError, json.JSONDecodeError):
        return int(status or 0), body


def to_uri(value):
    """Pass through URLs; convert local files to data URIs."""
    if value is None:
        return None
    if value.startswith(("http://", "https://", "data:")):
        return value
    p = Path(value).expanduser()
    if not p.is_file():
        die(f"file not found: {value}")
    mime = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


def build_input(a):
    inp = {}
    if a.prompt:
        inp["prompt"] = a.prompt
    if a.image:
        inp["image"] = to_uri(a.image)
    if a.last_frame_image:
        inp["last_frame_image"] = to_uri(a.last_frame_image)
    if a.reference_image:
        inp["reference_images"] = [to_uri(x) for x in a.reference_image]
    if a.reference_video:
        inp["reference_videos"] = [to_uri(x) for x in a.reference_video]
    if a.reference_audio:
        inp["reference_audios"] = [to_uri(x) for x in a.reference_audio]
    if a.duration is not None:
        inp["duration"] = a.duration
    if a.resolution:
        inp["resolution"] = a.resolution
    if a.aspect_ratio:
        inp["aspect_ratio"] = a.aspect_ratio
    if a.output_format:
        inp["output_format"] = a.output_format
    if a.seed is not None:
        inp["seed"] = a.seed
    inp["generate_audio"] = not a.no_audio
    if a.watermark:
        inp["watermark"] = True
    return inp


def validate(a, inp):
    """Catch the mutually-exclusive combos before spending money."""
    if inp.get("reference_images") and (inp.get("image") or inp.get("last_frame_image")):
        die("reference_images cannot be combined with image / last_frame_image")
    if inp.get("last_frame_image") and not inp.get("image"):
        die("last_frame_image requires image (first frame)")
    if inp.get("reference_audios") and not (
        inp.get("reference_images") or inp.get("reference_videos") or inp.get("image")
    ):
        die("reference_audios requires at least one reference image or video")
    if not inp.get("prompt") and not any(
        inp.get(k) for k in
        ("image", "reference_images", "reference_videos", "reference_audios")
    ):
        die("need a prompt or at least one media input")


def main():
    ap = argparse.ArgumentParser(description="Seedance video generation via Replicate")
    ap.add_argument("--model", default="2.5", choices=sorted(MODELS),
                    help="Seedance version (default: 2.5)")
    ap.add_argument("--prompt", default="")
    ap.add_argument("--image", help="first-frame image (path or URL)")
    ap.add_argument("--last-frame-image", help="last-frame image; requires --image")
    ap.add_argument("--reference-image", action="append",
                    help="reference image, repeatable (up to 30)")
    ap.add_argument("--reference-video", action="append",
                    help="reference video, repeatable (up to 10)")
    ap.add_argument("--reference-audio", action="append",
                    help="reference audio, repeatable (up to 10)")
    ap.add_argument("--duration", type=int, help="1-30 seconds, or -1 for auto")
    ap.add_argument("--resolution", choices=RESOLUTIONS)
    ap.add_argument("--aspect-ratio", choices=ASPECT_RATIOS)
    ap.add_argument("--output-format", choices=["mp4", "mov"])
    ap.add_argument("--seed", type=int)
    ap.add_argument("--no-audio", action="store_true", help="disable audio generation")
    ap.add_argument("--watermark", action="store_true")
    ap.add_argument("--output-dir", default="./outputs")
    ap.add_argument("--timeout", type=int, default=1800, help="poll timeout seconds")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the request payload and exit without spending")
    a = ap.parse_args()

    model = MODELS[a.model]
    inp = build_input(a)
    validate(a, inp)

    if a.dry_run:
        redacted = {
            k: (f"<{len(v)} data-uri(s)>" if isinstance(v, list)
                and v and str(v[0]).startswith("data:")
                else ("<data-uri>" if str(v).startswith("data:") else v))
            for k, v in inp.items()
        }
        print(json.dumps({"model": model, "input": redacted}, indent=2))
        return

    # Official models take NO version hash.
    status, body = curl("POST", f"{API}/models/{model}/predictions", {"input": inp})
    if status not in (200, 201):
        die(f"submit failed HTTP {status}: {json.dumps(body)[:500]}")

    pred_id = body.get("id")
    print(f"prediction: {pred_id}", file=sys.stderr)

    deadline = time.time() + a.timeout
    delay = 2
    while time.time() < deadline:
        status, body = curl("GET", f"{API}/predictions/{pred_id}")
        state = body.get("status") if isinstance(body, dict) else None
        if state in ("succeeded", "failed", "canceled"):
            break
        print(f"  {state}...", file=sys.stderr)
        time.sleep(delay)
        delay = min(delay * 1.5, 15)
    else:
        die(f"timed out after {a.timeout}s; prediction {pred_id} may still be running")

    if state != "succeeded":
        die(f"prediction {state}: {body.get('error')}")

    url = body.get("output")
    if isinstance(url, list):
        url = url[0] if url else None
    if not url:
        die("no output URL returned")

    outdir = Path(a.output_dir).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)
    ext = a.output_format or "mp4"
    dest = outdir / f"seedance_{pred_id}.{ext}"
    dl = subprocess.run(["curl", "-sSL", "-o", str(dest), url], capture_output=True, text=True)
    if dl.returncode != 0 or not dest.exists():
        die(f"download failed: {dl.stderr.strip()}")

    metrics = body.get("metrics") or {}
    print(json.dumps({
        "status": "success",
        "prediction_id": pred_id,
        "model": model,
        "file": str(dest),
        "bytes": dest.stat().st_size,
        "predict_time": metrics.get("predict_time"),
        "url": url,
    }, indent=2))


if __name__ == "__main__":
    main()
