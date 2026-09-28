#!/usr/bin/env python3
"""Generate [brand] talking-head clips via Replicate prunaai/p-video-avatar.

Reads a chunks.json manifest (same one used by emit_tts_chunks.py), filters to the
talking_head entries, pairs each with its matching pose image + the already-rendered
audio chunk, and fans out 6 parallel Replicate predictions. Polls until all done,
then downloads each MP4 to talking-heads/.

Filenames match the WAV naming convention:
  th{N}-{section}_[{start}-{end}]_pose-{NN}-{action}.mp4

Usage:
  python generate_talking_heads.py \
    --chunks /path/to/chunks.json \
    --vo-dir /path/to/vo-chunks \
    --pose-dir /path/to/character-pose-library \
    --out-dir /path/to/talking-heads
"""
import os
import sys
import json
import time
import base64
import argparse
import urllib.request
import urllib.error
import threading
from pathlib import Path

UA = "Brand-Pipeline/1.0"
opener = urllib.request.build_opener()
opener.addheaders = [("User-Agent", UA)]
urllib.request.install_opener(opener)

VIDEO_PROMPT = (
    "A [character] speaks directly to the camera with natural lip-sync and "
    "expressive head movement. Subtle nods on key points, occasional eyebrow "
    "emphasis. CRITICAL — camera: the camera is completely locked off on a tripod. "
    "NO zoom (in or out), NO push-in, NO pull-back, NO dolly, NO pan, NO tilt, NO "
    "shake, NO handheld motion. Framing stays IDENTICAL from the first frame to the "
    "last — only the character moves within the frame. Lighting and background match "
    "the source portrait exactly. CRITICAL — hat logo: the [brand emblem] on "
    "his hat is a flat embroidered patch sewn into the wool fabric. It conforms to "
    "the curvature of the cap, rotates with the head in correct perspective, shares "
    "the same lighting and shadows as the surrounding fabric, and never appears as a "
    "separate floating layer, 3D protrusion, or frontal-locked decal. The patch stays "
    "stitched flush against the hat at all times."
)


def to_data_uri(path: Path, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def upload_to_replicate(token: str, path: Path, mime: str) -> str:
    """Use Files API for assets >1.5MB (Replicate request size guard)."""
    import uuid
    boundary = f"----HermesBoundary{uuid.uuid4().hex}"
    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(b'Content-Disposition: form-data; name="content"; filename="')
    body.extend(path.name.encode())
    body.extend(b'"\r\n')
    body.extend(f"Content-Type: {mime}\r\n\r\n".encode())
    body.extend(path.read_bytes())
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
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())["urls"]["get"]


def asset_ref(token: str, path: Path, mime: str) -> str:
    """Use data URI for small files; Files API for big ones."""
    size = path.stat().st_size
    if size < 1_500_000:
        return to_data_uri(path, mime)
    return upload_to_replicate(token, path, mime)


def get_model_version(token: str, model: str) -> str:
    req = urllib.request.Request(
        f"https://api.replicate.com/v1/models/{model}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["latest_version"]["id"]


def submit_prediction(token: str, version: str, payload: dict) -> dict:
    req = urllib.request.Request(
        "https://api.replicate.com/v1/predictions",
        data=json.dumps({"version": version, "input": payload}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def poll_prediction(token: str, get_url: str, deadline: float) -> dict:
    while True:
        if time.time() > deadline:
            raise TimeoutError(f"polling deadline exceeded for {get_url}")
        time.sleep(6)
        req = urllib.request.Request(get_url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req) as r:
            pred = json.loads(r.read())
        if pred["status"] in ("succeeded", "failed", "canceled"):
            return pred


def download(url: str, dest: Path) -> None:
    with urllib.request.urlopen(url, timeout=300) as r:
        dest.write_bytes(r.read())


def derive_pose_filename(pose_field: str) -> str:
    """chunks.json 'pose' is like '08-pointing-at-camera'."""
    return f"character-pose-{pose_field}.png"


def chunk_basename(ch: dict) -> str:
    """Match the WAV naming from emit_tts_chunks.py."""
    start = f"{ch['start']:.2f}"
    end = f"{ch['end']:.2f}"
    pose = ch["pose"]
    return f"th{ch['th_id']}-{ch['section']}_[{start}-{end}]_pose-{pose}"


def run_one(token: str, version: str, ch: dict, pose_dir: Path, vo_dir: Path,
            out_dir: Path, results: dict, lock: threading.Lock) -> None:
    base = chunk_basename(ch)
    out_path = out_dir / f"{base}.mp4"
    if out_path.exists() and out_path.stat().st_size > 100_000:
        with lock:
            results[base] = {"status": "skipped", "path": str(out_path)}
        print(f"[{base}] exists, skip")
        return

    pose_path = pose_dir / derive_pose_filename(ch["pose"])
    audio_path = vo_dir / f"{base}.wav"
    if not pose_path.exists():
        print(f"[{base}] MISSING pose: {pose_path}")
        with lock:
            results[base] = {"status": "error", "error": f"pose missing: {pose_path}"}
        return
    if not audio_path.exists():
        print(f"[{base}] MISSING audio: {audio_path}")
        with lock:
            results[base] = {"status": "error", "error": f"audio missing: {audio_path}"}
        return

    print(f"[{base}] preparing assets ({pose_path.stat().st_size:,}B pose, "
          f"{audio_path.stat().st_size:,}B audio)")
    image_ref = asset_ref(token, pose_path, "image/png")
    audio_ref = asset_ref(token, audio_path, "audio/wav")
    payload = {
        "image": image_ref,
        "audio": audio_ref,
        "resolution": "720p",
        "video_prompt": VIDEO_PROMPT,
        "disable_prompt_upsampling": False,
    }
    pred = submit_prediction(token, version, payload)
    print(f"[{base}] submitted {pred['id']} ({pred['status']})")

    deadline = time.time() + 900  # 15 min per clip
    try:
        final = poll_prediction(token, pred["urls"]["get"], deadline)
    except Exception as e:
        print(f"[{base}] poll error: {e}")
        with lock:
            results[base] = {"status": "error", "error": str(e)}
        return

    if final["status"] != "succeeded":
        print(f"[{base}] FAILED: {final.get('error')}")
        with lock:
            results[base] = {"status": "failed", "error": final.get("error")}
        return

    output = final["output"]
    url = output if isinstance(output, str) else output[0]
    print(f"[{base}] downloading {url}")
    download(url, out_path)
    print(f"[{base}] saved {out_path} ({out_path.stat().st_size:,} bytes)")
    with lock:
        results[base] = {"status": "succeeded", "path": str(out_path),
                         "prediction_id": pred["id"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", required=True, type=Path)
    ap.add_argument("--vo-dir", required=True, type=Path)
    ap.add_argument("--pose-dir", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--manifest", type=Path,
                    help="Optional output path for talking-heads.json")
    args = ap.parse_args()

    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        print("ERROR: REPLICATE_API_TOKEN not set", file=sys.stderr)
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)
    chunks = json.loads(args.chunks.read_text())
    th_chunks = [c for c in chunks if c.get("kind") == "talking_head"]
    print(f"found {len(th_chunks)} talking-head chunks")
    if not th_chunks:
        print("nothing to do")
        return 0

    print("resolving prunaai/p-video-avatar version...")
    version = get_model_version(token, "prunaai/p-video-avatar")
    print(f"version: {version}")

    results: dict = {}
    lock = threading.Lock()
    threads = []
    for ch in th_chunks:
        t = threading.Thread(
            target=run_one,
            args=(token, version, ch, args.pose_dir, args.vo_dir,
                  args.out_dir, results, lock),
        )
        t.start()
        threads.append(t)
        time.sleep(2)  # gentle stagger
    for t in threads:
        t.join()

    if args.manifest:
        args.manifest.write_text(json.dumps(results, indent=2))
        print(f"manifest -> {args.manifest}")

    failed = [k for k, v in results.items() if v["status"] not in ("succeeded", "skipped")]
    if failed:
        print(f"FAILED: {failed}")
        return 1
    print("all talking-heads generated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
