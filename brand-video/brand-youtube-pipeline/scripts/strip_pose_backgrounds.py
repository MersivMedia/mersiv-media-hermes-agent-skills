#!/usr/bin/env python3
"""Background-remove the [brand] pose library via Replicate.

Reads every `character-pose-NN-<action>.png` from the character pose library and
emits a sibling `character-pose-NN-<action>-transparent.png` with the background
stripped (used for YouTube thumbnails and any other compositing).

Idempotent: skips poses that already have a `-transparent.png` companion unless
`--force` is passed. New poses added later will be picked up on next run.

Model: 851-labs/background-remover (Replicate). ~$0.01/image, ~5s per call.

Usage:
    strip_pose_backgrounds.py             # process new poses only
    strip_pose_backgrounds.py --force     # re-run even if -transparent.png exists
    strip_pose_backgrounds.py --pose 08   # single pose by number
    strip_pose_backgrounds.py --no-upload # skip Drive upload (local only)

Environment:
    REPLICATE_API_TOKEN     required
    GOOGLE_*                required unless --no-upload
"""
import argparse
import base64
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

POSE_DIR = Path(os.path.expanduser(
    "~/.hermes/data/brand-youtube-pipeline/character-pose-library"
))
DRIVE_CHARACTER_FOLDER_ID = os.environ.get("BRAND_CHARACTER_FOLDER_ID", "<DRIVE_FOLDER_ID>")
GAPI_SCRIPT = os.path.expanduser(
    "~/.hermes/skills/productivity/google-workspace/scripts/google_api.py"
)
MODEL = "851-labs/background-remover"
# Replicate's predictions endpoint returns 403 to requests using the default
# `Python-urllib/X.Y` User-Agent. Set a generic UA so urllib requests don't
# get filtered. (Discovered May 2026 — same model works fine with curl.)
UA = "Brand-Pipeline/1.0"


def _add_ua(req: urllib.request.Request) -> urllib.request.Request:
    req.add_header("User-Agent", UA)
    return req


# Install a global opener that injects the UA on every urllib request.
_opener = urllib.request.build_opener()
_opener.addheaders = [("User-Agent", UA)]
urllib.request.install_opener(_opener)


def _py():
    return sys.executable or shutil.which("python") or shutil.which("python3") or "python3"


def gapi(*args, timeout=120):
    cmd = [_py(), GAPI_SCRIPT] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"gapi failed: {' '.join(args)}\n{r.stderr}")
    return json.loads(r.stdout) if r.stdout.strip() else None


def data_uri(path: Path) -> str:
    mt = mimetypes.guess_type(str(path))[0] or "image/png"
    return f"data:{mt};base64,{base64.b64encode(path.read_bytes()).decode()}"


def replicate_upload_file(image_path: Path, token: str) -> str:
    """Upload a file to Replicate's files API and return the get URL.

    Necessary because data-URIs over ~1MB in the predictions request body get
    rejected with 403. The files API has a much higher limit and the model
    fetches by URL.
    """
    import uuid

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
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        info = json.loads(r.read())
    return info["urls"]["get"]


def replicate_predict(image_path: Path, token: str) -> bytes:
    """Run background-remover; return the output PNG bytes."""
    # Get latest version of the model
    req = urllib.request.Request(
        f"https://api.replicate.com/v1/models/{MODEL}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        version = json.loads(r.read())["latest_version"]["id"]

    # Upload via files API (avoids 403 on large data-URIs)
    file_url = replicate_upload_file(image_path, token)

    payload = json.dumps({
        "version": version,
        "input": {"image": file_url, "format": "png"},
    }).encode()
    req = urllib.request.Request(
        "https://api.replicate.com/v1/predictions",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        pred = json.loads(r.read())

    # Poll if still running
    deadline = time.time() + 120
    while pred["status"] not in ("succeeded", "failed", "canceled"):
        if time.time() > deadline:
            raise TimeoutError(f"prediction timeout: {pred['id']}")
        time.sleep(2)
        req = urllib.request.Request(
            pred["urls"]["get"],
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            pred = json.loads(r.read())

    if pred["status"] != "succeeded":
        raise RuntimeError(f"prediction {pred['status']}: {pred.get('error')}")

    out = pred["output"]
    if isinstance(out, list):
        out = out[0]
    with urllib.request.urlopen(out, timeout=60) as r:
        return r.read()


def find_drive_file(name: str, parent_id: str):
    q = f"name='{name}' and '{parent_id}' in parents and trashed=false"
    res = gapi("drive", "search", q, "--raw-query", "--max", "5")
    return res[0] if res else None


def upload_or_update(local: Path, parent_id: str):
    existing = find_drive_file(local.name, parent_id)
    if existing:
        # Replace via delete + upload (simpler than update API in google_api.py)
        gapi("drive", "delete", existing["id"])
    res = gapi("drive", "upload", str(local), "--parent", parent_id)
    return res["id"]


POSE_RE = re.compile(r"^character-pose-(\d{2})-([a-z0-9-]+)\.png$")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="Re-run even if -transparent.png exists")
    ap.add_argument("--pose", type=int,
                    help="Only process this pose number (1-12)")
    ap.add_argument("--no-upload", action="store_true",
                    help="Skip Drive upload (local-only)")
    args = ap.parse_args()

    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        sys.exit("REPLICATE_API_TOKEN missing")

    if not POSE_DIR.exists():
        sys.exit(f"pose dir missing: {POSE_DIR}")

    # Discover poses
    poses = []
    for p in sorted(POSE_DIR.iterdir()):
        m = POSE_RE.match(p.name)
        if not m:
            continue
        num = int(m.group(1))
        if args.pose and num != args.pose:
            continue
        out = POSE_DIR / f"character-pose-{num:02d}-{m.group(2)}-transparent.png"
        poses.append((num, p, out))

    if not poses:
        sys.exit("No poses matched.")

    print(f"Found {len(poses)} pose(s) to consider")

    for num, src, dst in poses:
        if dst.exists() and not args.force:
            print(f"  [skip] pose {num:02d} — {dst.name} already exists")
            continue
        print(f"  [run]  pose {num:02d} — {src.name}", flush=True)
        try:
            bytes_out = replicate_predict(src, token)
            dst.write_bytes(bytes_out)
            print(f"         saved {dst.name} ({len(bytes_out)//1024} KB)")
            if not args.no_upload:
                fid = upload_or_update(dst, DRIVE_CHARACTER_FOLDER_ID)
                print(f"         uploaded -> {fid}")
        except Exception as e:
            print(f"         FAILED: {e}")

    print("\nDone.")


if __name__ == "__main__":
    main()
