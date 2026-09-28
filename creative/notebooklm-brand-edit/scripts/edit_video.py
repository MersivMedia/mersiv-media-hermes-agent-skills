#!/usr/bin/env python3
"""NotebookLM → [brand] video re-brand pipeline.

Usage:
    python edit_video.py INPUT.mp4 OUTPUT.mp4 [--workdir DIR] [--no-ai]

Assumes:
    - ffmpeg, ffprobe on PATH
    - PIL installed
    - REPLICATE_API_TOKEN env var set (skip with --no-ai for cheaper run)
    - Brand assets in env vars:
        BRAND_WORDMARK_PATH (default: /tmp/hermes/logos/brand-lockup-horizontal-transparent-outlined.png)
        BRAND_OUTRO_PATH    (default: /tmp/hermes/logos/brand-intro-outro-v4.mp4)
"""
import os, sys, json, subprocess, argparse, tempfile, shutil, base64, time
import urllib.request, urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image, ImageFilter

# ── Brand palette ─────────────────────────────────────────────────────────────
BG = (18, 18, 18)        # #121212 [brand background color]
TEXT_COLOR = (240, 240, 240)   # #F0F0F0 [brand text color]
GOLD = (255, 193, 7)    # #FFC107 [brand accent color]
RED = (229, 57, 53)      # #E53935 [brand emphasis color]
TEAL = (38, 166, 154)    # #26A69A [brand secondary color]
GRAY = (107, 114, 128)   # #6B7280 [brand muted color]

# Use the SOLID-BACKGROUND horizontal lockup (the file without "transparent" in its name).
# The transparent variants render poorly over dark slides — they need the black backplate to
# stay readable. Do NOT switch this to *-transparent.png or *-transparent-outlined.png.
WORDMARK_DEFAULT = "/tmp/hermes/logos/brand-lockup-horizontal.png"
OUTRO_DEFAULT = "/tmp/hermes/logos/brand-intro-outro-v4.mp4"

# ── ffmpeg helpers ────────────────────────────────────────────────────────────

def run(cmd, check=True, capture=False):
    """Run a shell command, return CompletedProcess."""
    if capture:
        return subprocess.run(cmd, check=check, capture_output=True, text=True)
    return subprocess.run(cmd, check=check)

def probe(path):
    """Return dict with width, height, fps, duration."""
    out = run(["ffprobe", "-v", "error", "-show_streams",
               "-show_format", "-of", "json", path], capture=True).stdout
    data = json.loads(out)
    v = next(s for s in data["streams"] if s["codec_type"] == "video")
    fps_num, fps_den = map(int, v["r_frame_rate"].split("/"))
    return {
        "width": int(v["width"]),
        "height": int(v["height"]),
        "fps": fps_num / fps_den,
        "duration": float(data["format"]["duration"]),
        "codec": v["codec_name"],
    }

def detect_scene_cuts(path, threshold=0.25):
    """Return list of scene cut timestamps in seconds (excludes 0 and duration)."""
    out = run(["ffmpeg", "-hide_banner", "-i", path,
               "-filter:v", f"select='gt(scene,{threshold})',showinfo",
               "-vsync", "vfr", "-f", "null", "-"], capture=True, check=False).stderr
    cuts = []
    for line in out.split("\n"):
        if "showinfo" in line and "pts_time:" in line:
            try:
                t = float(line.split("pts_time:")[1].split()[0])
                cuts.append(t)
            except (ValueError, IndexError):
                pass
    return sorted(set(cuts))

def extract_frame(video, t, out_path):
    """Extract single frame at time t."""
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-ss", str(t), "-i", video, "-vframes", "1", out_path], check=True)

# ── Scene classification ──────────────────────────────────────────────────────

def classify_scene(img_path):
    """Return dict with brightness, complexity, light/dark, simple/complex."""
    img = Image.open(img_path).convert("RGB").resize((128, 72), Image.LANCZOS)
    pixels = list(img.getdata())
    brightness = sum(max(r, g, b) for r, g, b in pixels) / len(pixels)
    # Complexity: quantize and count distinct colors
    q = img.quantize(colors=256)
    palette_size = len(set(q.getdata()))
    return {
        "brightness": brightness,
        "complexity": palette_size,
        "is_light": brightness > 140,
        "is_complex": palette_size > 80,
    }

# ── Recoloring ────────────────────────────────────────────────────────────────

def recolor_text_scene(src_path, dst_path):
    """PIL-only recolor for text-heavy light scenes.
    Strategy:
      - White/light gray background → BG (#121212)
      - Dark gray/black text → TEXT_COLOR (#F0F0F0)
      - Coral/pink/red accents → GOLD (#FFC107)
      - Blue accents → TEAL
    """
    img = Image.open(src_path).convert("RGB")
    out = Image.new("RGB", img.size)
    src = img.load()
    dst = out.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b = src[x, y]
            # Background: very light pixels
            if r > 200 and g > 200 and b > 200:
                dst[x, y] = BG
            # Dark text: near-black or dark gray
            elif r < 90 and g < 90 and b < 90:
                dst[x, y] = TEXT_COLOR
            # Mid gray (body text, borders)
            elif abs(r - g) < 15 and abs(g - b) < 15 and 90 <= r < 200:
                # Light gray → BG, dark gray → TEXT_COLOR
                dst[x, y] = BG if r > 140 else TEXT_COLOR
            # Pink/coral/red (NotebookLM accent)
            elif r > g and r > b and r - max(g, b) > 30:
                dst[x, y] = GOLD
            # Blue
            elif b > r and b > g and b - max(r, g) > 30:
                dst[x, y] = TEAL
            # Green
            elif g > r and g > b and g - max(r, b) > 30:
                dst[x, y] = TEAL
            else:
                # Unknown: map by luminance to BG/TEXT_COLOR
                lum = (r + g + b) / 3
                dst[x, y] = BG if lum > 128 else TEXT_COLOR
    out.save(dst_path)

def recolor_via_gpt(src_path, dst_path, token):
    """Use gpt-image-2 to recolor a complex scene preserving content."""
    with open(src_path, "rb") as f:
        data_uri = "data:image/png;base64," + base64.b64encode(f.read()).decode()
    prompt = (
        "Recolor this image to match a dark editorial brand palette while keeping ALL "
        "text, layout, charts, illustrations, numbers, and composition EXACTLY THE SAME. "
        "Only change colors. Convert the light/white background to [brand background color] (default #121212). "
        "Convert dark text and elements to [brand text color] (default #F0F0F0). "
        "Convert coral/pink/red accent colors to [brand accent color] (default #FFC107). "
        "Convert blue accents to [brand secondary color] (default #26A69A). "
        "Preserve every word of text exactly as written, every line of every chart, "
        "every illustration detail at its original position. "
        "Output a dark-themed version of the same slide with identical information."
    )
    body = json.dumps({
        "input": {
            "prompt": prompt,
            "input_images": [data_uri],
            "aspect_ratio": "3:2",
            "output_format": "png",
            "number_of_images": 1,
            "quality": "high",
        }
    }).encode()
    req = urllib.request.Request(
        "https://api.replicate.com/v1/models/openai/gpt-image-2/predictions",
        data=body,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json",
                 "Prefer": "wait=60"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read())
    pid = resp["id"]
    status = resp.get("status")
    output = resp.get("output")
    deadline = time.time() + 240
    while status not in ("succeeded","failed","canceled") and time.time() < deadline:
        time.sleep(3)
        poll = urllib.request.Request(
            f"https://api.replicate.com/v1/predictions/{pid}",
            headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(poll, timeout=30) as r:
            pd = json.loads(r.read())
        status = pd.get("status")
        output = pd.get("output")
    if status != "succeeded":
        raise RuntimeError(f"gpt-image-2 failed: {status}")
    url = output if isinstance(output, str) else output[0]
    img_bytes = urllib.request.urlopen(url, timeout=60).read()
    # gpt returns 3:2 — need to fit to source aspect by center-crop
    tmp = dst_path + ".raw.png"
    with open(tmp, "wb") as f:
        f.write(img_bytes)
    # Resize+crop to source dimensions
    src_dims = Image.open(src_path).size
    gen = Image.open(tmp).convert("RGB")
    sw, sh = src_dims
    gw, gh = gen.size
    scale = max(sw / gw, sh / gh)
    new_size = (int(gw * scale), int(gh * scale))
    gen = gen.resize(new_size, Image.LANCZOS)
    left = (gen.width - sw) // 2
    top = (gen.height - sh) // 2
    gen = gen.crop((left, top, left + sw, top + sh))
    gen.save(dst_path)
    os.remove(tmp)

# ── NotebookLM branding strip ────────────────────────────────────────────────

def cover_notebooklm_badge(img_path, width, height):
    """Paint a brand-black rectangle over the bottom-right NotebookLM badge.
    NotebookLM badge is roughly at x=89%-99%, y=94%-99% of frame."""
    img = Image.open(img_path).convert("RGB")
    px = img.load()
    x1 = int(width * 0.85)
    y1 = int(height * 0.92)
    x2 = width
    y2 = height
    for y in range(y1, y2):
        for x in range(x1, x2):
            px[x, y] = BG
    img.save(img_path)

# ── Scene processing ─────────────────────────────────────────────────────────

def make_scene_video(image_path, duration, out_path, fps, width, height):
    """Convert a still image to a video clip of given duration matching source params."""
    aspect = f"{width}/{height}"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-loop", "1", "-i", image_path, "-t", f"{duration:.3f}",
         "-r", str(int(fps)), "-vf", f"scale={width}:{height},setsar=1",
         "-aspect", aspect,
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast",
         "-tune", "stillimage", "-an", out_path], check=True)

def reencode_to_match(src_video, dst_video, fps, width, height, audio_fade=None):
    """Re-encode a video to match source dimensions + fps so it concats cleanly.
    audio_fade: optional tuple (kind, start, duration) — e.g. ("out", 6.54, 0.5)
                applies an afade filter so the music doesn't end with a hard cut.
    """
    aspect = f"{width}/{height}"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-i", src_video, "-vf", f"scale={width}:{height},setsar=1",
           "-r", str(int(fps)), "-aspect", aspect]
    if audio_fade is not None:
        kind, start, dur = audio_fade
        cmd += ["-af", f"afade=t={kind}:st={start}:d={dur}"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", dst_video]
    run(cmd, check=True)

# ── Main pipeline ────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--no-ai", action="store_true",
                    help="Skip gpt-image-2; use PIL for all scenes")
    ap.add_argument("--wordmark", default=os.environ.get("BRAND_WORDMARK_PATH", WORDMARK_DEFAULT))
    ap.add_argument("--outro", default=os.environ.get("BRAND_OUTRO_PATH", OUTRO_DEFAULT))
    ap.add_argument("--no-outro", action="store_true", help="Skip appending outro video")
    ap.add_argument("--skip-wordmark", action="store_true",
                    help="Skip overlaying the brand wordmark. Useful when downstream "
                         "steps (e.g. [brand] pipeline Phase 7) will composite "
                         "wordmark + outro AFTER talking-heads. The output is "
                         "saved as content-with-audio.mp4 → final output path.")
    ap.add_argument("--scene-threshold", type=float, default=0.25)
    args = ap.parse_args()

    token = os.environ.get("REPLICATE_API_TOKEN")
    if not args.no_ai and not token:
        print("WARNING: no REPLICATE_API_TOKEN, using --no-ai mode")
        args.no_ai = True

    workdir = Path(args.workdir or tempfile.mkdtemp(prefix="nblm_edit_"))
    workdir.mkdir(exist_ok=True)
    print(f"Workdir: {workdir}")

    # 1. Probe
    info = probe(args.input)
    print(f"Source: {info['width']}x{info['height']} @ {info['fps']:.1f}fps, {info['duration']:.1f}s")
    W, H, FPS, DUR = info["width"], info["height"], info["fps"], info["duration"]

    # 2. Detect scenes
    cuts = detect_scene_cuts(args.input, args.scene_threshold)
    boundaries = [0.0] + cuts + [DUR]
    scenes = [(boundaries[i], boundaries[i+1]) for i in range(len(boundaries)-1)]
    print(f"Detected {len(scenes)} scenes")

    # 3. Extract midframe + classify each
    scene_data = []
    for i, (start, end) in enumerate(scenes):
        mid = (start + end) / 2
        frame = workdir / f"scene-{i:02d}.png"
        extract_frame(args.input, mid, str(frame))
        cls = classify_scene(str(frame))
        scene_data.append({
            "idx": i, "start": start, "end": end, "duration": end - start,
            "frame": str(frame), **cls,
        })
        print(f"  Scene {i:02d}: {start:6.1f}-{end:6.1f}s "
              f"bright={cls['brightness']:.0f} "
              f"colors={cls['complexity']} "
              f"{'LIGHT' if cls['is_light'] else 'dark '} "
              f"{'COMPLEX' if cls['is_complex'] else 'simple'}")

    # 4. Drop trailing NotebookLM end cards
    # Heuristic: any scene in last 10s with brightness>180 → drop
    dropped = []
    keep = []
    for s in scene_data:
        if s["start"] > DUR - 10 and s["brightness"] > 180:
            dropped.append(s)
            print(f"  DROP scene {s['idx']:02d} (NotebookLM end card, t={s['start']:.1f}s)")
        else:
            keep.append(s)
    scene_data = keep

    # 5. Recolor scenes that need it
    recolor_jobs = [s for s in scene_data if s["is_light"]]
    print(f"\nRecoloring {len(recolor_jobs)} light scenes...")

    def process_one(s):
        out = workdir / f"recolored-{s['idx']:02d}.png"
        try:
            if s["is_complex"] and not args.no_ai:
                recolor_via_gpt(s["frame"], str(out), token)
                method = "gpt"
            else:
                recolor_text_scene(s["frame"], str(out))
                method = "pil"
            cover_notebooklm_badge(str(out), W, H)
            s["recolored"] = str(out)
            return s["idx"], method, None
        except Exception as e:
            # Fallback: PIL
            recolor_text_scene(s["frame"], str(out))
            cover_notebooklm_badge(str(out), W, H)
            s["recolored"] = str(out)
            return s["idx"], "pil-fallback", str(e)

    with ThreadPoolExecutor(max_workers=4) as ex:
        for idx, method, err in ex.map(process_one, recolor_jobs):
            tag = f"[{method}]"
            if err:
                tag += f" (err: {err[:60]})"
            print(f"  Recolored scene {idx:02d} {tag}")

    # 6. For dark scenes, still strip NotebookLM badge by using ffmpeg drawbox
    #    Approach: process every kept scene as a still (cheaper to debug) using
    #    its mid frame, then for dark scenes just cover the badge.
    for s in scene_data:
        if "recolored" not in s:
            # Dark scene — keep original frame, just cover badge
            out = workdir / f"recolored-{s['idx']:02d}.png"
            shutil.copy(s["frame"], str(out))
            cover_notebooklm_badge(str(out), W, H)
            s["recolored"] = str(out)

    # 7. Build per-scene video clips
    # NOTE: This drops original motion/animation within each scene — accepted
    # tradeoff per skill v1. For motion preservation, use ffmpeg select filter
    # to extract scene segments + overlay recolored bg in compositing pass.
    print("\nBuilding scene clips...")
    clip_paths = []
    for s in scene_data:
        clip = workdir / f"clip-{s['idx']:02d}.mp4"
        make_scene_video(s["recolored"], s["duration"], str(clip), FPS, W, H)
        clip_paths.append(str(clip))

    # 8. Concat scenes (silent video track)
    # NOTE: ffmpeg's concat demuxer resolves `file` lines relative to the
    # concat list's own directory, NOT the process cwd. Since both the list
    # and the clips live inside `workdir`, write only the basenames.
    print("Concatenating scenes...")
    concat_list = workdir / "concat-scenes.txt"
    with open(concat_list, "w") as f:
        for p in clip_paths:
            f.write(f"file '{Path(p).name}'\n")
    silent_video = workdir / "silent-recolored.mp4"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "concat", "-safe", "0", "-i", str(concat_list),
         "-c", "copy", str(silent_video)], check=True)

    # 9. Trim audio to match new duration (audio is sourced from original up to last kept scene)
    new_content_duration = sum(s["duration"] for s in scene_data)
    audio_track = workdir / "audio.aac"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-i", args.input, "-t", f"{new_content_duration:.3f}",
         "-vn", "-c:a", "copy", str(audio_track)], check=True)

    # 10. Mux audio + silent video
    with_audio = workdir / "content-with-audio.mp4"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-i", str(silent_video), "-i", str(audio_track),
         "-c:v", "copy", "-c:a", "copy", "-shortest", str(with_audio)], check=True)

    # 11. Overlay wordmark (20% of video height, 2% margin from edges).
    # When --skip-wordmark is set, downstream pipeline ([brand] Phase 7) handles
    # the wordmark AFTER talking-head composites are added — keeps the visual
    # hierarchy clean (wordmark always sits on top of every overlay).
    if args.skip_wordmark:
        with_wordmark = with_audio
    else:
        with_wordmark = workdir / "content-with-wordmark.mp4"
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-i", str(with_audio), "-i", args.wordmark,
             "-filter_complex",
             "[1:v]scale=-1:ih*0.20[wm];[0:v][wm]overlay=W-w-W*0.02:H-h-H*0.02",
             "-c:a", "copy", str(with_wordmark)], check=True)

    # 12. Append outro AND prepend intro (same source file, used on both ends).
    # Apply 0.5s audio fades so the music doesn't hard-cut into/out of content:
    #   - INTRO: fade OUT in the last 0.5s (so it tapers into content narration)
    #   - OUTRO: fade IN in the first 0.5s (so content tapers into the music)
    # Use the concat FILTER (not demuxer) — decodes and re-encodes in one pass.
    # Slower but reliable across mixed codec params; the demuxer chokes on
    # subtle differences in NAL timestamps / sample rates between stream-copy
    # outputs and re-encoded outros.
    aspect_arg = f"{W}/{H}"
    if not args.no_outro and os.path.exists(args.outro):
        # Probe outro duration so the fade-out lands exactly at the tail
        outro_info = probe(args.outro)
        outro_dur = outro_info["duration"]
        fade_d = 0.5
        intro_clip = workdir / "intro-faded.mp4"
        outro_clip = workdir / "outro-faded.mp4"
        # Intro: fade out at (duration - fade_d) for fade_d seconds
        reencode_to_match(args.outro, str(intro_clip), FPS, W, H,
                          audio_fade=("out", max(0.0, outro_dur - fade_d), fade_d))
        # Outro: fade in at 0 for fade_d seconds
        reencode_to_match(args.outro, str(outro_clip), FPS, W, H,
                          audio_fade=("in", 0.0, fade_d))
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-i", str(intro_clip),
             "-i", str(with_wordmark),
             "-i", str(outro_clip),
             "-filter_complex",
             "[0:v:0]setsar=1[v0];[1:v:0]setsar=1[v1];[2:v:0]setsar=1[v2];"
             "[v0][0:a:0][v1][1:a:0][v2][2:a:0]"
             "concat=n=3:v=1:a=1[outv][outa]",
             "-map", "[outv]", "-map", "[outa]",
             "-aspect", aspect_arg,
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast",
             "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
             args.output], check=True)
    else:
        # Re-encode to ensure aspect ratio is set on output
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-i", str(with_wordmark), "-vf", "setsar=1", "-aspect", aspect_arg,
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast",
             "-c:a", "copy", args.output], check=True)

    final_info = probe(args.output)
    print(f"\n✓ Done. Output: {args.output}")
    print(f"  {final_info['width']}x{final_info['height']} @ {final_info['fps']:.1f}fps, {final_info['duration']:.1f}s")
    print(f"  ({len(dropped)} NotebookLM end cards removed, "
          f"{sum(1 for s in scene_data if 'recolored' in s and s['is_light'])} scenes recolored)")

if __name__ == "__main__":
    main()
