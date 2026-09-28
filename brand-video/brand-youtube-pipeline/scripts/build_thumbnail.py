#!/usr/bin/env python3
"""Build YouTube thumbnails for [brand] episodes.

Composes a 1280×720 thumbnail from:
  - one of the dark brand backgrounds (or solid #121212 fallback)
  - a transparent-background [character] pose (chest-up crop)
  - 2-3 line big chunky title text in [brand accent color] + [brand text color]
  - the horizontal wordmark in the bottom-left corner

Run mode: spits out N variants (different pose + title-color combos) into a
`thumbnail-variants/` folder so the user can pick. The chosen variant gets
copied as the canonical `thumbnail.png` next to the talking-heads.

No AI cost — pure PIL composition.

Usage:
    build_thumbnail.py \\
      --episode-slug 01-pure-play-space-stocks \\
      --title "PURE-PLAY|SPACE STOCKS" \\
      --sub "5 tickers Wall Street is hiding" \\
      --pose 08 \\
      [--hook-color gold|teal|red]   default gold
      [--variants 3]                  default 3 (different poses)

The title is split on `|` for line breaks. Recommended: 1-3 lines, 2-5 words
each. Keep it under ~24 chars per line so it stays readable on mobile.

The script auto-picks alternative poses for the other variants from the
intent table (see `INTENT_POSES` below) so the variants feel meaningfully
different, not just-the-same-pose-with-different-titles.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(os.path.expanduser("~/.hermes/data/brand-youtube-pipeline"))
POSE_DIR = ROOT / "character-pose-library"
FONT_DIR = ROOT / "fonts"
BRAND_DIR = ROOT / "brand"
EP_ROOT = ROOT / "episodes"

# Brand palette
BRAND_BG = (18, 18, 18)         # #121212
BRAND_TEXT = (240, 240, 240)      # #F0F0F0
BRAND_ACCENT = (255, 193, 7)     # #FFC107
BRAND_EMPHASIS = (229, 57, 53)        # #E53935
BRAND_SECONDARY = (38, 166, 154)     # #26A69A
BRAND_MUTED = (107, 114, 128)      # #6B7280

HOOK_COLORS = {
    "gold": BRAND_ACCENT,
    "teal": BRAND_SECONDARY,
    "red": BRAND_EMPHASIS,
}

# When the user picks pose N for variant 1, these are sensible alts for v2/v3
# (chosen to feel visually different — gestures from different parts of the
# pose taxonomy). Each list is ordered by preference.
INTENT_POSES = {
    1: [8, 3, 12],    # arms-down → assertive alternates
    2: [12, 4, 8],    # hand-on-chest → emphatic alternates
    3: [10, 8, 9],    # arms-crossed → confident/questioning alternates
    4: [5, 8, 12],    # gesturing → explaining/pointing/fist alternates
    5: [4, 12, 8],
    6: [10, 11, 8],   # thumbs-up → confident/sign-off alternates
    7: [9, 3, 4],     # thinking → questioning/skeptical
    8: [12, 4, 3],    # pointing → emphatic alternates
    9: [3, 7, 10],    # palms-up → skeptical alternates
    10: [8, 6, 12],
    11: [6, 10, 1],
    12: [8, 4, 3],
}

GOOGLE_API = os.path.expanduser(
    "~/.hermes/skills/productivity/google-workspace/scripts/google_api.py"
)


def _py():
    return sys.executable or shutil.which("python") or shutil.which("python3") or "python3"


def gapi(*args, timeout=120):
    cmd = [_py(), GOOGLE_API] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"gapi failed: {' '.join(args)}\n{r.stderr}")
    return json.loads(r.stdout) if r.stdout.strip() else None


def load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = FONT_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"Missing font {name} at {path}. Run the font-bootstrap step in "
            "the skill (see scripts/build_thumbnail.py header)."
        )
    return ImageFont.truetype(str(path), size=size)


def find_pose(pose_num: int) -> Path:
    """Find a pose's transparent-bg PNG. Raise if it doesn't exist."""
    matches = list(POSE_DIR.glob(f"character-pose-{pose_num:02d}-*-transparent.png"))
    if not matches:
        raise FileNotFoundError(
            f"Missing transparent companion for pose {pose_num:02d}. "
            "Run strip_pose_backgrounds.py first."
        )
    return matches[0]


def find_background() -> Path | None:
    """Locate a dark background image to use behind the thumbnail."""
    # Prefer a local mirror; fall back to None (we'll generate a solid+grain fill)
    candidates = [
        ROOT / "brand" / "bg-youtube-channel.png",
        ROOT / "brand" / "bg-youtube-endscreen.png",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def ensure_background_cached() -> Path:
    """Download a YouTube background from Drive into brand/ if not present."""
    target = BRAND_DIR / "bg-youtube-channel.png"
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    # Drive file id from `[brand]/brand/backgrounds/bg-youtube-channel.png`
    fid = os.environ["BRAND_BG_FILE_ID"]
    gapi("drive", "download", fid, "--out", str(target))
    return target


def draw_textured_background(canvas: Image.Image, bg_path: Path | None):
    """Lay down the base background — either a brand bg image (cropped to fit)
    or a solid [brand background color] fill with a subtle vignette + grain."""
    w, h = canvas.size
    if bg_path and bg_path.exists():
        bg = Image.open(bg_path).convert("RGB")
        # Cover-crop to 1280×720
        bw, bh = bg.size
        scale = max(w / bw, h / bh)
        nw, nh = int(bw * scale), int(bh * scale)
        bg = bg.resize((nw, nh), Image.LANCZOS)
        x0 = (nw - w) // 2
        y0 = (nh - h) // 2
        canvas.paste(bg.crop((x0, y0, x0 + w, y0 + h)), (0, 0))
        # Darken slightly so text reads
        overlay = Image.new("RGBA", canvas.size, (18, 18, 18, 90))
        canvas.paste(overlay, (0, 0), overlay)
    else:
        canvas.paste(BRAND_BG, (0, 0, w, h))
    return canvas


def crop_pose_chest_up(pose_img: Image.Image) -> Image.Image:
    """Tightly crop the pose to its alpha bbox, then crop to chest-up.

    Heuristic: alpha bbox is the full character; the top of the bbox is the
    head crown. Crop down to roughly the top 60% to get chest-up.
    """
    if pose_img.mode != "RGBA":
        pose_img = pose_img.convert("RGBA")
    bbox = pose_img.getbbox()
    if bbox is None:
        return pose_img
    x0, y0, x1, y1 = bbox
    # Crop to bbox
    pose_img = pose_img.crop(bbox)
    pw, ph = pose_img.size
    # Take top 65% of the bounded pose → chest-up.
    chest_up_h = int(ph * 0.65)
    return pose_img.crop((0, 0, pw, chest_up_h))


def fit_pose_to_panel(pose_img: Image.Image, panel_w: int, panel_h: int) -> Image.Image:
    """Scale the pose to fit the panel while preserving aspect ratio."""
    pw, ph = pose_img.size
    scale = min(panel_w / pw, panel_h / ph)
    nw, nh = int(pw * scale), int(ph * scale)
    return pose_img.resize((nw, nh), Image.LANCZOS)


def draw_title_block(
    canvas: Image.Image,
    title_lines: list[str],
    sub: str | None,
    hook_color: tuple,
    text_box_w: int,
    text_box_h: int,
    text_box_x: int,
    text_box_y: int,
):
    """Draw the big chunky title + optional subline.

    `title_lines` is a list of strings (one per line). Auto-fit the font size
    so the longest line fits within text_box_w with a healthy stroke.
    """
    draw = ImageDraw.Draw(canvas)
    title_font_name = "RobotoSlab-Black.ttf"

    # Find largest font size where every line fits within text_box_w.
    # Cap at a sane upper bound so single short words don't blow up.
    max_size = min(180, text_box_h // max(len(title_lines), 1) - 10)
    min_size = 60
    chosen = min_size
    for size in range(max_size, min_size - 1, -2):
        font = load_font(title_font_name, size)
        widths = [draw.textlength(line, font=font) for line in title_lines]
        line_h = font.getbbox("Ag")[3] - font.getbbox("Ag")[1]
        total_h = line_h * len(title_lines) + (len(title_lines) - 1) * 8
        if max(widths) <= text_box_w - 24 and total_h <= text_box_h - (40 if sub else 0):
            chosen = size
            break

    title_font = load_font(title_font_name, chosen)
    line_h = title_font.getbbox("Ag")[3] - title_font.getbbox("Ag")[1]
    stroke_w = max(4, chosen // 18)

    # Total title block height for centering
    title_block_h = line_h * len(title_lines) + (len(title_lines) - 1) * 8
    sub_h = 70 if sub else 0
    gap = 18 if sub else 0
    total_h = title_block_h + gap + sub_h

    y = text_box_y + (text_box_h - total_h) // 2

    # Draw each title line with stroke (outline) + drop shadow
    for line in title_lines:
        line_w = draw.textlength(line, font=title_font)
        x = text_box_x + (text_box_w - line_w) // 2

        # Drop shadow
        shadow_offset = max(3, chosen // 30)
        draw.text(
            (x + shadow_offset, y + shadow_offset),
            line,
            font=title_font,
            fill=(0, 0, 0, 180),
            stroke_width=stroke_w,
            stroke_fill=(0, 0, 0),
        )
        # Main text with outline stroke
        draw.text(
            (x, y),
            line,
            font=title_font,
            fill=hook_color,
            stroke_width=stroke_w,
            stroke_fill=(0, 0, 0),
        )
        y += line_h + 8

    # Subline
    if sub:
        y += gap
        sub_font = load_font("RobotoSlab-Black.ttf", 44)
        sub_w = draw.textlength(sub, font=sub_font)
        x = text_box_x + (text_box_w - sub_w) // 2
        # Subline always [brand text color] for contrast
        draw.text(
            (x + 2, y + 2),
            sub,
            font=sub_font,
            fill=(0, 0, 0, 200),
            stroke_width=3,
            stroke_fill=(0, 0, 0),
        )
        draw.text(
            (x, y),
            sub,
            font=sub_font,
            fill=BRAND_TEXT,
            stroke_width=3,
            stroke_fill=(0, 0, 0),
        )


def build_one_thumbnail(
    title: str,
    sub: str | None,
    pose_num: int,
    hook_color_name: str,
    out_path: Path,
):
    """Render a single thumbnail at 1280×720."""
    canvas = Image.new("RGB", (1280, 720))

    # Background
    bg_path = find_background()
    if not bg_path:
        bg_path = ensure_background_cached()
    draw_textured_background(canvas, bg_path)

    # Pose: right side of frame, 50% of width
    pose_panel_w = 540
    pose_panel_h = 720
    pose_panel_x = 1280 - pose_panel_w - 20  # right-aligned with 20px margin

    pose_path = find_pose(pose_num)
    pose_img = Image.open(pose_path).convert("RGBA")
    pose_img = crop_pose_chest_up(pose_img)
    pose_img = fit_pose_to_panel(pose_img, pose_panel_w, pose_panel_h)

    # Bottom-aligned within panel
    pw, ph = pose_img.size
    px = pose_panel_x + (pose_panel_w - pw) // 2
    py = 720 - ph  # flush to bottom
    canvas.paste(pose_img, (px, py), pose_img)

    # Title block: left ~58% of frame
    text_box_x = 30
    text_box_y = 40
    text_box_w = 720
    text_box_h = 600

    title_lines = [s.strip() for s in title.split("|") if s.strip()]
    hook_color = HOOK_COLORS.get(hook_color_name, BRAND_ACCENT)
    draw_title_block(
        canvas, title_lines, sub, hook_color,
        text_box_w, text_box_h, text_box_x, text_box_y,
    )

    # (Earlier draft had a vertical gold rule line between text and [character] —
    # vision review flagged it as dated/PowerPoint-y, so we removed it. The
    # warm [character] lighting + the gold title already create the divide.)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, "PNG", optimize=True)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode-slug", required=True,
                    help="Episode slug under episodes/, e.g. 01-pure-play-space-stocks")
    ap.add_argument("--title", required=True,
                    help="Title with `|` for line breaks, e.g. 'SPACE|STOCKS'")
    ap.add_argument("--sub", default=None,
                    help="Optional smaller subline beneath the title")
    ap.add_argument("--pose", type=int, required=True,
                    help="Primary pose number (1-12)")
    ap.add_argument("--hook-color", choices=["gold", "teal", "red"],
                    default="gold",
                    help="Title color (default: gold)")
    ap.add_argument("--variants", type=int, default=3,
                    help="Number of variants to render (default: 3)")
    ap.add_argument("--no-upload", action="store_true",
                    help="Skip Drive upload")
    ap.add_argument("--drive-folder-id", default=None,
                    help="Drive folder to upload variants to. If omitted, "
                         "skip upload.")
    args = ap.parse_args()

    ep_dir = EP_ROOT / args.episode_slug
    variants_dir = ep_dir / "thumbnail-variants"
    variants_dir.mkdir(parents=True, exist_ok=True)

    # Pick variant poses (primary, then alternates from INTENT_POSES)
    alt_poses = INTENT_POSES.get(args.pose, [args.pose])
    variant_poses = [args.pose] + [p for p in alt_poses if p != args.pose]
    variant_poses = variant_poses[:args.variants]

    # Also rotate hook colors for variants (gold, teal, red)
    color_rotation = ["gold", "teal", "red"]
    hook_colors = [args.hook_color]
    for c in color_rotation:
        if c != args.hook_color and len(hook_colors) < args.variants:
            hook_colors.append(c)

    rendered = []
    for i, (pose_num, color) in enumerate(zip(variant_poses, hook_colors), 1):
        out = variants_dir / f"thumbnail-v{i}_pose-{pose_num:02d}_{color}.png"
        print(f"  [v{i}] pose-{pose_num:02d} color={color} -> {out.name}", flush=True)
        try:
            build_one_thumbnail(args.title, args.sub, pose_num, color, out)
            rendered.append(out)
        except Exception as e:
            print(f"        FAILED: {e}", flush=True)

    # Symlink/copy variant 1 as the canonical "thumbnail.png"
    if rendered:
        canonical = ep_dir / "thumbnail.png"
        shutil.copy2(rendered[0], canonical)
        print(f"\nCanonical -> {canonical}")

    # Upload to Drive if asked
    if args.drive_folder_id and not args.no_upload:
        print(f"\nUploading {len(rendered)} variants to Drive {args.drive_folder_id}")
        for f in rendered:
            res = gapi("drive", "upload", str(f),
                       "--parent", args.drive_folder_id)
            print(f"  uploaded {f.name} -> {res['id']}")
        canonical = ep_dir / "thumbnail.png"
        if canonical.exists():
            res = gapi("drive", "upload", str(canonical),
                       "--parent", args.drive_folder_id)
            print(f"  uploaded thumbnail.png -> {res['id']}")


if __name__ == "__main__":
    main()
