#!/usr/bin/env python3
"""Cheap-iteration rebuild: re-run the back half of the pipeline using cached
recolored-NN.png frames in an existing workdir.

Use when you've hand-edited (or AI-edited) one or more `recolored-NN.png`
frames in the workdir and just want to splice them back into the final video
without re-detecting scenes, re-classifying, or re-calling gpt-image-2.

Also supports inserting a NEW scene (e.g. a missing title card that the
scene detector dropped) by passing --insert-at IDX --insert-image PATH
--insert-duration SECS. The new scene is added at position IDX and all
later scenes are shifted; original audio from source.mp4 is re-trimmed
to match the new total content duration (which means audio sync is only
preserved if the inserted scene's duration matches the title-card gap
in the source audio — see pitfall in SKILL.md).

Usage:
    python rebuild_from_recolored.py WORKDIR OUTPUT.mp4 \\
        --source SOURCE.mp4 \\
        [--wordmark PATH] [--outro PATH] [--no-outro] \\
        [--insert-at IDX --insert-image PATH --insert-duration SECS] \\
        [--scene-durations "12.5,26.1,16.0,..."]

If --scene-durations is omitted, durations are re-read from source.mp4 by
re-running scene detection at the same threshold the original pass used
(0.25 by default). Pass --scene-threshold to override.
"""
import argparse, os, subprocess, json, shutil, tempfile, sys
from pathlib import Path


def run(cmd, check=True, capture=False):
    if capture:
        return subprocess.run(cmd, check=check, capture_output=True, text=True)
    return subprocess.run(cmd, check=check)


def probe(path):
    out = run(["ffprobe", "-v", "error", "-show_streams", "-show_format",
               "-of", "json", path], capture=True).stdout
    data = json.loads(out)
    v = next(s for s in data["streams"] if s["codec_type"] == "video")
    fps_num, fps_den = map(int, v["r_frame_rate"].split("/"))
    return {
        "width": int(v["width"]), "height": int(v["height"]),
        "fps": fps_num / fps_den, "duration": float(data["format"]["duration"]),
    }


def detect_scene_cuts(path, threshold):
    out = run(["ffmpeg", "-hide_banner", "-i", path,
               "-filter:v", f"select='gt(scene,{threshold})',showinfo",
               "-vsync", "vfr", "-f", "null", "-"], capture=True, check=False).stderr
    cuts = []
    for line in out.split("\n"):
        if "showinfo" in line and "pts_time:" in line:
            try:
                cuts.append(float(line.split("pts_time:")[1].split()[0]))
            except (ValueError, IndexError):
                pass
    return sorted(set(cuts))


def make_scene_video(image_path, duration, out_path, fps, width, height):
    aspect = f"{width}/{height}"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-loop", "1", "-i", image_path, "-t", f"{duration:.3f}",
         "-r", str(int(fps)), "-vf", f"scale={width}:{height},setsar=1",
         "-aspect", aspect,
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast",
         "-tune", "stillimage", "-an", out_path], check=True)


def reencode_to_match(src_video, dst_video, fps, width, height):
    aspect = f"{width}/{height}"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-i", src_video, "-vf", f"scale={width}:{height},setsar=1",
         "-r", str(int(fps)), "-aspect", aspect,
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast",
         "-c:a", "aac", "-b:a", "128k", "-ar", "44100", dst_video], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workdir")
    ap.add_argument("output")
    ap.add_argument("--source", required=True, help="Original source.mp4 (for audio + duration recomputation)")
    ap.add_argument("--wordmark", default=os.environ.get(
        "BRAND_WORDMARK_PATH",
        "/tmp/hermes/logos/brand-lockup-horizontal-transparent-outlined.png"))
    ap.add_argument("--outro", default=os.environ.get(
        "BRAND_OUTRO_PATH",
        "/tmp/hermes/logos/brand-intro-outro-v4.mp4"))
    ap.add_argument("--no-outro", action="store_true")
    ap.add_argument("--scene-threshold", type=float, default=0.25)
    ap.add_argument("--scene-durations", default=None,
                    help="Comma-separated durations override (skips re-detection)")
    ap.add_argument("--insert-at", type=int, default=None,
                    help="Index at which to insert an extra scene (0 = before scene 00)")
    ap.add_argument("--insert-image", default=None)
    ap.add_argument("--insert-duration", type=float, default=None)
    ap.add_argument("--drop-trailing-light", action="store_true",
                    help="Replicate original pipeline's NotebookLM end-card drop")
    args = ap.parse_args()

    workdir = Path(args.workdir)
    if not workdir.is_dir():
        sys.exit(f"Workdir not found: {workdir}")

    info = probe(args.source)
    W, H, FPS, DUR = info["width"], info["height"], info["fps"], info["duration"]

    # Recompute scene boundaries the same way edit_video.py does.
    if args.scene_durations:
        durations = [float(x) for x in args.scene_durations.split(",")]
    else:
        cuts = detect_scene_cuts(args.source, args.scene_threshold)
        boundaries = [0.0] + cuts + [DUR]
        durations = [boundaries[i+1] - boundaries[i]
                     for i in range(len(boundaries) - 1)]

    # Collect recolored frames.
    recolored = sorted(workdir.glob("recolored-*.png"))
    if not recolored:
        sys.exit(f"No recolored-*.png in {workdir}")
    if len(recolored) != len(durations) and not args.drop_trailing_light:
        print(f"WARN: {len(recolored)} recolored frames vs {len(durations)} scenes — "
              f"using min({len(recolored)}, {len(durations)})")
    n = min(len(recolored), len(durations))
    recolored = recolored[:n]
    durations = durations[:n]

    # Optional: drop trailing scenes that the original pipeline dropped
    # (end cards). We can't classify here without the raw frames, so this is
    # a manual hint — the user should know if their workdir had end cards
    # dropped and pass --drop-trailing-light to peel them off again.
    # (Already handled by recolored-*.png only existing for kept scenes.)

    # Insert new scene if requested.
    if args.insert_at is not None:
        if not (args.insert_image and args.insert_duration):
            sys.exit("--insert-at requires --insert-image and --insert-duration")
        idx = args.insert_at
        # Copy insert image into workdir so it survives.
        insert_dst = workdir / f"insert-at-{idx:02d}.png"
        shutil.copy(args.insert_image, insert_dst)
        recolored.insert(idx, insert_dst)
        durations.insert(idx, args.insert_duration)
        print(f"Inserted scene at index {idx} ({args.insert_duration:.2f}s) — "
              f"{insert_dst}")

    # Build clip-XX.mp4 for each scene.
    clip_paths = []
    for i, (frame, dur) in enumerate(zip(recolored, durations)):
        clip = workdir / f"rebuild-clip-{i:02d}.mp4"
        make_scene_video(str(frame), dur, str(clip), FPS, W, H)
        clip_paths.append(str(clip))
        print(f"  clip {i:02d}: {dur:.2f}s  {frame.name}")

    # Concat silent video.
    concat_list = workdir / "rebuild-concat-scenes.txt"
    with open(concat_list, "w") as f:
        for p in clip_paths:
            f.write(f"file '{p}'\n")
    silent = workdir / "rebuild-silent.mp4"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "concat", "-safe", "0", "-i", str(concat_list),
         "-c", "copy", str(silent)], check=True)

    # Trim audio from source to new content duration.
    total = sum(durations)
    audio = workdir / "rebuild-audio.aac"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-i", args.source, "-t", f"{total:.3f}",
         "-vn", "-c:a", "copy", str(audio)], check=True)

    # Mux.
    with_audio = workdir / "rebuild-with-audio.mp4"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-i", str(silent), "-i", str(audio),
         "-c:v", "copy", "-c:a", "copy", "-shortest", str(with_audio)], check=True)

    # Wordmark.
    with_wm = workdir / "rebuild-with-wordmark.mp4"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-i", str(with_audio), "-i", args.wordmark,
         "-filter_complex",
         "[1:v]scale=-1:ih*0.20[wm];[0:v][wm]overlay=W-w-W*0.02:H-h-H*0.02-25",
         "-c:a", "copy", str(with_wm)], check=True)

    # Outro.
    aspect_arg = f"{W}/{H}"
    if not args.no_outro and os.path.exists(args.outro):
        outro_m = workdir / "rebuild-outro-matched.mp4"
        reencode_to_match(args.outro, str(outro_m), FPS, W, H)
        final_list = workdir / "rebuild-concat-final.txt"
        with open(final_list, "w") as f:
            f.write(f"file '{with_wm}'\n")
            f.write(f"file '{outro_m}'\n")
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-f", "concat", "-safe", "0", "-i", str(final_list),
             "-vf", "setsar=1", "-aspect", aspect_arg,
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast",
             "-c:a", "aac", "-b:a", "128k", args.output], check=True)
    else:
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-i", str(with_wm), "-vf", "setsar=1", "-aspect", aspect_arg,
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast",
             "-c:a", "copy", args.output], check=True)

    final = probe(args.output)
    print(f"\n✓ Rebuilt: {args.output}")
    print(f"  {final['width']}x{final['height']} @ {final['fps']:.1f}fps, {final['duration']:.1f}s")
    print(f"  ({len(durations)} scenes, total content {total:.1f}s)")


if __name__ == "__main__":
    main()
