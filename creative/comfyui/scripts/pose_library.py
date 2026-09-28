#!/usr/bin/env python3
"""Pose library: extract, store, and reuse motion skeletons.

Pose extraction costs ~40s per clip and is fully deterministic — the same
source video always yields the same skeleton. Caching it means every later
generation that wants the same motion skips straight to
reference-image + skeleton -> video.

Library lives at /workspace/pose_library/ with a JSON manifest.

  add   <video> --name walk_forward_turn_left --desc "..."
  list
  show  <name>
  path  <name>        # prints the skeleton mp4 path (for scripting)
  remove <name>
"""

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

LIB = Path("/workspace/pose_library")
MANIFEST = LIB / "manifest.json"
HOST = "http://127.0.0.1:8188"
COMFY_IN = Path("/workspace/ComfyUI/input")
COMFY_OUT = Path("/workspace/ComfyUI/output")


def load_manifest():
    if MANIFEST.exists():
        try:
            return json.loads(MANIFEST.read_text())
        except json.JSONDecodeError:
            print("WARN: manifest corrupt, starting fresh", file=sys.stderr)
    return {"version": 1, "poses": {}}


def save_manifest(m):
    LIB.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST.with_suffix(".tmp")
    tmp.write_text(json.dumps(m, indent=2))
    tmp.replace(MANIFEST)


def http(method, url, payload=None, timeout=120):
    cmd = ["curl", "-sS", "-X", method, url,
           "-H", "Content-Type: application/json",
           "-w", "\n__S__%{http_code}", "--max-time", str(timeout)]
    if payload is not None:
        cmd += ["-d", json.dumps(payload)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return 0, f"curl: {r.stderr.strip()}"
    body, _, st = r.stdout.rpartition("\n__S__")
    try:
        return int(st), json.loads(body)
    except (ValueError, json.JSONDecodeError):
        return int(st or 0), body


def probe(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames",
         "-show_entries", "stream=width,height,nb_read_frames,r_frame_rate",
         "-of", "json", str(path)],
        capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        st = json.loads(r.stdout)["streams"][0]
        num, _, den = st["r_frame_rate"].partition("/")
        return {
            "width": st.get("width"),
            "height": st.get("height"),
            "frames": int(st.get("nb_read_frames") or 0),
            "fps": round(float(num) / float(den or 1), 2),
        }
    except (KeyError, IndexError, ValueError, ZeroDivisionError):
        return None


def extract_skeleton(video_filename, fps):
    """Run a pose-only ComfyUI graph and return the output skeleton path."""
    prefix = f"poselib_{int(time.time())}"
    wf = {
        "1": {"class_type": "LoadVideo", "inputs": {"file": video_filename}},
        "2": {"class_type": "GetVideoComponents", "inputs": {"video": ["1", 0]}},
        "20": {"class_type": "CheckpointLoaderSimple",
               "inputs": {"ckpt_name": "sdpose_wholebody_fp16.safetensors"}},
        "22": {"class_type": "SDPoseKeypointExtractor",
               "inputs": {"model": ["20", 0], "vae": ["20", 2],
                          "image": ["2", 0], "batch_size": 8}},
        "23": {"class_type": "SDPoseDrawKeypoints",
               "inputs": {"keypoints": ["22", 0],
                          "draw_body": True, "draw_hands": True,
                          "draw_face": False, "draw_feet": True,
                          "stick_width": 4, "face_point_size": 3,
                          "score_threshold": 0.3, "draw_head": True}},
        "40": {"class_type": "CreateVideo",
               "inputs": {"images": ["23", 0], "fps": float(fps)}},
        "41": {"class_type": "SaveVideo",
               "inputs": {"video": ["40", 0], "filename_prefix": prefix,
                          "format": "mp4", "codec": "h264"}},
    }
    st, body = http("POST", f"{HOST}/prompt", {"prompt": wf})
    if st != 200 or not isinstance(body, dict):
        print(f"ERROR submit HTTP {st}: {str(body)[:400]}", file=sys.stderr)
        return None
    pid = body.get("prompt_id")
    print(f"  extracting (prompt {pid})…", flush=True)

    t0 = time.time()
    while time.time() - t0 < 1800:
        time.sleep(8)
        st, hist = http("GET", f"{HOST}/history/{pid}")
        if st == 200 and isinstance(hist, dict) and pid in hist:
            e = hist[pid]
            status = (e.get("status") or {}).get("status_str")
            if status == "error":
                for m in (e.get("status") or {}).get("messages", []):
                    print("   ", json.dumps(m)[:500], file=sys.stderr)
                return None
            # ComfyUI reports SaveVideo output under "images" with
            # animated:true — NOT under "videos". Check every list.
            for nd in (e.get("outputs") or {}).values():
                for key in ("videos", "gifs", "images"):
                    for it in (nd.get(key) or []):
                        fn = it.get("filename", "")
                        if fn.startswith(prefix):
                            return COMFY_OUT / fn
            return None
    print("  ERROR: timeout", file=sys.stderr)
    return None


def cmd_add(a):
    src = Path(a.video).expanduser()
    if not src.is_file():
        print(f"ERROR: not found: {src}", file=sys.stderr); sys.exit(1)

    m = load_manifest()
    if a.name in m["poses"] and not a.force:
        print(f"ERROR: '{a.name}' exists (use --force)", file=sys.stderr); sys.exit(1)

    info = probe(src)
    if not info:
        print(f"ERROR: could not probe {src}", file=sys.stderr); sys.exit(1)
    print(f"source: {info['frames']}f {info['width']}x{info['height']} @{info['fps']}")

    # ComfyUI can only LoadVideo from its input dir
    staged = COMFY_IN / src.name
    if not staged.exists() or staged.stat().st_size != src.stat().st_size:
        shutil.copy2(src, staged)

    out = extract_skeleton(src.name, a.fps or info["fps"])
    if not out or not Path(out).exists():
        print("ERROR: extraction failed", file=sys.stderr); sys.exit(2)

    LIB.mkdir(parents=True, exist_ok=True)
    dest = LIB / f"{a.name}.mp4"
    shutil.copy2(out, dest)
    sk = probe(dest) or {}

    m["poses"][a.name] = {
        "file": dest.name,
        "description": a.desc or "",
        "tags": [t.strip() for t in (a.tags or "").split(",") if t.strip()],
        "frames": sk.get("frames"),
        "fps": sk.get("fps"),
        "width": sk.get("width"),
        "height": sk.get("height"),
        "source_video": src.name,
        "added": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    save_manifest(m)
    print(json.dumps({"added": a.name, **m["poses"][a.name]}, indent=2))


def cmd_list(a):
    m = load_manifest()
    if not m["poses"]:
        print("(library empty)"); return
    print(f"{'NAME':<30} {'FRAMES':>7} {'FPS':>5} {'RES':>10}  DESCRIPTION")
    for name, p in sorted(m["poses"].items()):
        res = f"{p.get('width')}x{p.get('height')}"
        print(f"{name:<30} {str(p.get('frames')):>7} {str(p.get('fps')):>5} "
              f"{res:>10}  {p.get('description','')[:40]}")


def cmd_show(a):
    m = load_manifest()
    p = m["poses"].get(a.name)
    if not p:
        print(f"ERROR: no pose '{a.name}'", file=sys.stderr); sys.exit(1)
    print(json.dumps({"name": a.name, "path": str(LIB / p["file"]), **p}, indent=2))


def cmd_path(a):
    m = load_manifest()
    p = m["poses"].get(a.name)
    if not p:
        print(f"ERROR: no pose '{a.name}'", file=sys.stderr); sys.exit(1)
    print(LIB / p["file"])


def cmd_remove(a):
    m = load_manifest()
    p = m["poses"].pop(a.name, None)
    if not p:
        print(f"ERROR: no pose '{a.name}'", file=sys.stderr); sys.exit(1)
    f = LIB / p["file"]
    if f.exists():
        f.unlink()
    save_manifest(m)
    print(f"removed {a.name}")


def main():
    ap = argparse.ArgumentParser(description="Pose skeleton library")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("add", help="extract + store a skeleton")
    s.add_argument("video")
    s.add_argument("--name", required=True)
    s.add_argument("--desc", default="")
    s.add_argument("--tags", default="")
    s.add_argument("--fps", type=int)
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_add)

    s = sub.add_parser("list"); s.set_defaults(fn=cmd_list)
    s = sub.add_parser("show"); s.add_argument("name"); s.set_defaults(fn=cmd_show)
    s = sub.add_parser("path"); s.add_argument("name"); s.set_defaults(fn=cmd_path)
    s = sub.add_parser("remove"); s.add_argument("name"); s.set_defaults(fn=cmd_remove)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
