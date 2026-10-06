#!/usr/bin/env python3
"""frames.py — turn each section clip into a scroll-scrub frame sequence (WebP) + a poster + a mobile set.

    python3 frames.py <site_dir> [--fps 24] [--width 1600] [--mobile-width 720] [--q 72] [--max-frames 144]
                      [--trim SECONDS] [--only id1,id2]
--trim keeps only the first N seconds of each clip (shorter scrub = fewer frames = faster first load).

Reads  <site_dir>/assets/clips/<section>.mp4  (from gen.py)
Writes <site_dir>/assets/frames/<section>/f0001.webp ...      desktop sequence
       <site_dir>/assets/frames/<section>/m/f0001.webp ...    mobile sequence (smaller, same count)
       <site_dir>/assets/posters/<section>.webp               first frame (shown before frames load / reduced motion)
       <site_dir>/assets/frames.json                          {section: {count, w, h, mw, mh, bytes, mbytes}}
Frame budget: canvas scrubbing preloads every frame, so keep each section <= ~5 MB desktop / ~2 MB mobile.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

args = sys.argv[1:]
if not args:
    sys.exit(__doc__)
site = Path(args[0]).resolve()


def opt(name, default):
    return type(default)(args[args.index(name) + 1]) if name in args else default


FPS, WIDTH, MW, Q, MAXF = opt("--fps", 24), opt("--width", 1600), opt("--mobile-width", 720), opt("--q", 72), opt("--max-frames", 144)
TRIM = opt("--trim", 0.0)                                 # seconds from the start of each clip; 0 = whole clip
CUT = ["-t", f"{TRIM:.3f}"] if TRIM > 0 else []
ONLY = set(opt("--only", "").split(",")) - {""}          # process just these clips, keep the rest of frames.json
clips = sorted((site / "assets/clips").glob("*.mp4"))
if ONLY:
    clips = [c for c in clips if c.stem in ONLY]
if not clips:
    sys.exit(f"no clips in {site}/assets/clips")
mf = site / "assets/frames.json"
manifest = json.loads(mf.read_text()) if (ONLY and mf.exists()) else {}
for clip in clips:
    sec = clip.stem
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(clip)],
                               capture_output=True, text=True).stdout or 0)
    if TRIM > 0:
        dur = min(dur, TRIM)
    fps = min(FPS, MAXF / dur) if dur else FPS
    out = site / "assets/frames" / sec
    if out.exists():
        shutil.rmtree(out)
    (out / "m").mkdir(parents=True)
    # "<id>_m" clips are PHONE-ONLY variants (e.g. a 9:16 hero, used via a section's "mobile_clip"): mobile frames
    # only, at no more than the clip's native width (upscaling adds bytes, not detail).
    if sec.endswith("_m"):
        nw = int(json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width",
                                            "-of", "json", str(clip)], capture_output=True, text=True).stdout)["streams"][0]["width"])
        mw = min(MW, nw)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), *CUT, "-vf", f"fps={fps:.4f},scale={mw}:-2:flags=lanczos",
                        "-c:v", "libwebp", "-quality", str(Q), "-compression_level", "4", str(out / "m" / "f%04d.webp")], check=True)
        mfiles = sorted((out / "m").glob("f*.webp"))
        (site / "assets/posters").mkdir(parents=True, exist_ok=True)
        shutil.copy(mfiles[0], site / "assets/posters" / f"{sec}.webp")
        mprobe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                                            "-of", "json", str(mfiles[0])], capture_output=True, text=True).stdout)["streams"][0]
        mb = sum(f.stat().st_size for f in mfiles)
        manifest[sec] = {"count": len(mfiles), "mw": mprobe["width"], "mh": mprobe["height"], "mbytes": mb,
                         "fps": round(fps, 3), "mobile_only": True}
        warn = "  <-- over budget" if mb > 5e6 else ""
        print(f"{sec} (phone-only): {len(mfiles)} frames @ {fps:.1f} fps, {mprobe['width']}x{mprobe['height']}, {mb/1e6:.1f} MB{warn}")
        continue
    for w, d in ((WIDTH, out), (MW, out / "m")):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), *CUT, "-vf", f"fps={fps:.4f},scale={w}:-2:flags=lanczos",
                        "-c:v", "libwebp", "-quality", str(Q), "-compression_level", "4", str(d / "f%04d.webp")], check=True)
    files = sorted(out.glob("f*.webp"))
    mfiles = sorted((out / "m").glob("f*.webp"))
    if len(files) != len(mfiles):
        sys.exit(f"{sec}: desktop {len(files)} vs mobile {len(mfiles)} frames")
    (site / "assets/posters").mkdir(parents=True, exist_ok=True)
    shutil.copy(files[0], site / "assets/posters" / f"{sec}.webp")
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                                       "-of", "json", str(files[0])], capture_output=True, text=True).stdout)["streams"][0]
    mprobe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                                        "-of", "json", str(mfiles[0])], capture_output=True, text=True).stdout)["streams"][0]
    b = sum(f.stat().st_size for f in files)
    mb = sum(f.stat().st_size for f in mfiles)
    manifest[sec] = {"count": len(files), "w": probe["width"], "h": probe["height"], "mw": mprobe["width"], "mh": mprobe["height"],
                     "bytes": b, "mbytes": mb, "fps": round(fps, 3)}
    warn = "  <-- over budget, lower --q/--width/--max-frames" if b > 5e6 or mb > 2e6 else ""
    print(f"{sec}: {len(files)} frames @ {fps:.1f} fps, {probe['width']}x{probe['height']}, desktop {b/1e6:.1f} MB, mobile {mb/1e6:.1f} MB{warn}")
(site / "assets/frames.json").write_text(json.dumps(manifest, indent=1))
print(f"wrote {site}/assets/frames.json ({len(manifest)} sections, total {sum(v.get('bytes', 0) for v in manifest.values())/1e6:.1f} MB desktop)")
