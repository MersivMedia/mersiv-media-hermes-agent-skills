#!/usr/bin/env python3
"""Prepare a motion-LoRA training dataset from source video clips.

Segments long clips into fixed-length chunks, normalizes fps/resolution,
drops chunks containing scene cuts (which poison temporal learning), and
writes a caption stub per clip for manual editing.

Requires ffmpeg/ffprobe on PATH.

Usage:
    python3 prep_motion_dataset.py --input ./source --output ./dataset \
        --frames 49 --fps 24 --resolution 768x448
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def need(tool):
    if not shutil.which(tool):
        die(f"{tool} not found on PATH")


def probe(path):
    """Return (duration_s, fps, width, height) or None."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate,width,height",
        "-show_entries", "format=duration",
        "-of", "json", str(path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        d = json.loads(r.stdout)
        st = d["streams"][0]
        num, _, den = st["r_frame_rate"].partition("/")
        fps = float(num) / float(den or 1)
        return (
            float(d["format"]["duration"]),
            fps,
            int(st["width"]),
            int(st["height"]),
        )
    except (KeyError, IndexError, ValueError, ZeroDivisionError):
        return None


def scene_cut_times(path, threshold):
    """Timestamps (s) where ffmpeg detects a scene change."""
    cmd = [
        "ffmpeg", "-v", "info", "-i", str(path),
        "-filter:v", f"select='gt(scene,{threshold})',showinfo",
        "-f", "null", "-",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    times = []
    for line in r.stderr.splitlines():
        if "pts_time:" in line:
            try:
                times.append(float(line.split("pts_time:")[1].split()[0]))
            except (IndexError, ValueError):
                pass
    return times


def main():
    ap = argparse.ArgumentParser(description="Prep a motion-LoRA dataset")
    ap.add_argument("--input", required=True, help="dir of source clips")
    ap.add_argument("--output", required=True, help="dataset output dir")
    ap.add_argument("--frames", type=int, default=49,
                    help="frames per training clip (default 49)")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--resolution", default="768x448", help="WxH")
    ap.add_argument("--caption-template", default="a figure {action}, {camera}",
                    help="stub written to each .txt for manual editing")
    ap.add_argument("--scene-threshold", type=float, default=0.3,
                    help="ffmpeg scene score above which a cut is assumed")
    ap.add_argument("--keep-cuts", action="store_true",
                    help="do NOT drop segments containing scene cuts")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    need("ffmpeg")
    need("ffprobe")

    try:
        w, h = (int(x) for x in a.resolution.lower().split("x"))
    except ValueError:
        die("--resolution must look like 768x448")

    src = Path(a.input).expanduser()
    if not src.is_dir():
        die(f"input dir not found: {src}")
    out = Path(a.output).expanduser()

    clips = sorted(p for p in src.iterdir() if p.suffix.lower() in VIDEO_EXTS)
    if not clips:
        die(f"no video files in {src}")

    seg_dur = a.frames / a.fps
    print(f"segment length: {a.frames} frames @ {a.fps}fps = {seg_dur:.2f}s")
    print(f"found {len(clips)} source clip(s)\n")

    if not a.dry_run:
        out.mkdir(parents=True, exist_ok=True)

    written = skipped_cut = skipped_short = 0

    for clip in clips:
        info = probe(clip)
        if not info:
            print(f"  ! unreadable, skipping: {clip.name}")
            continue
        dur, fps, cw, ch = info
        n_seg = int(dur // seg_dur)
        if n_seg < 1:
            print(f"  - too short ({dur:.1f}s): {clip.name}")
            skipped_short += 1
            continue

        cuts = [] if a.keep_cuts else scene_cut_times(clip, a.scene_threshold)
        print(f"  {clip.name}: {dur:.1f}s {cw}x{ch} @{fps:.1f} "
              f"-> {n_seg} seg, {len(cuts)} cut(s)")

        for i in range(n_seg):
            start = i * seg_dur
            end = start + seg_dur
            if any(start < c < end for c in cuts):
                skipped_cut += 1
                continue

            name = f"{clip.stem}_{i:03d}"
            dst = out / f"{name}.mp4"
            if a.dry_run:
                written += 1
                continue

            cmd = [
                "ffmpeg", "-v", "error", "-y",
                "-ss", f"{start:.3f}", "-i", str(clip),
                "-t", f"{seg_dur:.3f}",
                "-vf", (f"scale={w}:{h}:force_original_aspect_ratio=increase,"
                        f"crop={w}:{h},fps={a.fps}"),
                "-frames:v", str(a.frames),
                "-an", "-c:v", "libx264", "-crf", "16",
                "-pix_fmt", "yuv420p", str(dst),
            ]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0 or not dst.exists():
                print(f"    ! ffmpeg failed on {name}: {r.stderr.strip()[:160]}")
                continue
            (out / f"{name}.txt").write_text(a.caption_template + "\n")
            written += 1

    print(f"\nwritten: {written}  |  dropped(scene cut): {skipped_cut}  "
          f"|  dropped(too short): {skipped_short}")
    if a.dry_run:
        print("(dry run — nothing written)")
        return

    print(f"\ndataset: {out}")
    print("NEXT: edit every .txt by hand.")
    print("  Motion LoRA  -> describe ACTION + CAMERA, keep the subject generic.")
    print("  Character LoRA -> lead with the identity token, vary the rest.")
    print("Captioning decides whether this trains motion or appearance.")


if __name__ == "__main__":
    main()
