#!/usr/bin/env python3
"""
NotebookLM PDF slideshow builder.

Usage:
    build_slideshow.py --pdf-id <DRIVE_FILE_ID> --topic-slug <SLUG> --topic-folder-id <DRIVE_FOLDER_ID>

Renders each PDF page to a numbered horizontal JPG, then sends each one to
gpt-image-2 (via Replicate) for a 2:3 brand-styled vertical alternate.
Uploads everything back to a 'slideshow/' subfolder under the topic folder.

See SKILL.md for full docs.
"""
import argparse, base64, json, os, shutil, subprocess, sys, time, urllib.request
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Paths & defaults
# ─────────────────────────────────────────────────────────────────────────────

ROOT = Path(os.environ.get(
    "BRAND_SLIDESHOW_ROOT",
    os.path.expanduser("~/.hermes/data/notebooklm-pdf-slideshow"),
))
ROOT.mkdir(parents=True, exist_ok=True)

GAPI_SCRIPT = os.path.expanduser("~/.hermes/skills/productivity/google-workspace/scripts/google_api.py")
REPLICATE_MODEL = "openai/gpt-image-2"

# Brand-locked vertical reformat prompt — see SKILL.md for narrative description
VERTICAL_PROMPT = """Reformat this 16:9 slide into a 2:3 vertical poster suitable for Instagram Reels and TikTok.
Keep ALL content from the original — every headline, every bullet, every number, every chart.
Reflow the layout so it reads top-to-bottom instead of left-to-right.
Maintain the [brand] brand:
- Background: [brand background color] (default #121212) with subtle parchment-paper texture overlay
- Headlines: [brand accent color] (default #FFC107), slab-serif (Rockwell / Roboto Slab / Arvo)
- Body: [brand text color] (default #F0F0F0), clean sans-serif
- Accents: [brand secondary color] (default #26A69A) for positive/up data, [brand emphasis color] (default #E53935) for warnings/down data
- Numbers: tabular monospace
- Subtle gold rule lines, slight film grain, weathered ship's-log meets terminal-screen mood
- NO mascot inserts, NO logos in the body — the wordmark goes on later in post

If the original has a chart, redraw it cleanly in the brand palette (gold/teal up, red down), tall orientation.
If the original has a comparison table, stack rows vertically with clear hierarchy.
Do NOT add new content. Do NOT change the data values. Do NOT use stock photos.
Output: single image, 1024x1536, no margins, full-bleed."""


# ─────────────────────────────────────────────────────────────────────────────
# Drive helpers (uses installed google_api.py module's get_credentials())
# ─────────────────────────────────────────────────────────────────────────────

def _drive_service():
    sys.path.insert(0, os.path.dirname(GAPI_SCRIPT))
    from google_api import get_credentials  # type: ignore
    from googleapiclient.discovery import build  # type: ignore
    return build("drive", "v3", credentials=get_credentials())


def gapi(*args):
    """Shell out to google_api.py CLI for simple ops (create-folder, upload, delete, search)."""
    # Prefer the explicit interpreter we're running under; fall back to PATH lookup
    # so the script works whether `python` or only `python3` is available.
    py = sys.executable or shutil.which("python") or shutil.which("python3") or "python3"
    cmd = [py, GAPI_SCRIPT] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"gapi failed: {' '.join(args)}\nstderr: {r.stderr}\nstdout: {r.stdout}")
    return json.loads(r.stdout) if r.stdout.strip() else {}


def find_or_create_slideshow_folder(topic_folder_id, svc=None):
    q = (f"name = 'slideshow' and '{topic_folder_id}' in parents "
         f"and mimeType = 'application/vnd.google-apps.folder' and trashed = false")
    results = gapi("drive", "search", q, "--raw-query", "--max", "5")
    if results:
        return results[0]["id"]
    return gapi("drive", "create-folder", "slideshow", "--parent", topic_folder_id)["id"]


def move_to_folder(file_id, new_parent_id, svc):
    """Move a Drive file by adding new parent + removing old parents."""
    meta = svc.files().get(fileId=file_id, fields="parents,name").execute()
    if new_parent_id in meta["parents"] and len(meta["parents"]) == 1:
        print(f"  PDF already in slideshow folder; skipping move")
        return
    old_parents = ",".join(p for p in meta["parents"] if p != new_parent_id)
    svc.files().update(
        fileId=file_id,
        addParents=new_parent_id,
        removeParents=old_parents,
        fields="id,parents",
    ).execute()
    print(f"  Moved {meta['name']} → slideshow/")


def download_pdf(file_id, dest):
    gapi("drive", "download", file_id, "--output", str(dest))
    print(f"  Downloaded → {dest}")


# ─────────────────────────────────────────────────────────────────────────────
# PDF rendering
# ─────────────────────────────────────────────────────────────────────────────

def render_pdf(pdf_path, out_dir, zoom=2.0):
    import fitz  # PyMuPDF
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    n = len(doc)
    paths = []
    for i, page in enumerate(doc, start=1):
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        out = out_dir / f"slide-{i:02d}.jpg"
        # PyMuPDF saves as PNG natively; use Pillow for JPG control
        from PIL import Image
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        img.save(out, "JPEG", quality=92)
        paths.append(out)
        print(f"  Rendered page {i}/{n} → {out.name} ({pix.width}x{pix.height})")
    return paths


# ─────────────────────────────────────────────────────────────────────────────
# Replicate (gpt-image-2) vertical generation
# ─────────────────────────────────────────────────────────────────────────────

def replicate_predict(model, payload, token, poll_timeout=240):
    body = json.dumps({"input": payload}).encode()
    req = urllib.request.Request(
        f"https://api.replicate.com/v1/models/{model}/predictions",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Prefer": "wait=60",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"Replicate {e.code}: {body[:2000]}") from None
    pid = resp["id"]
    status = resp.get("status")
    output = resp.get("output")
    pd = resp  # capture initial response so post-loop access works even when no polling happens
    deadline = time.time() + poll_timeout
    while status not in ("succeeded", "failed", "canceled") and time.time() < deadline:
        time.sleep(3)
        poll = urllib.request.Request(
            f"https://api.replicate.com/v1/predictions/{pid}",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(poll, timeout=30) as r:
            pd = json.loads(r.read())
        status = pd.get("status")
        output = pd.get("output")
    if status != "succeeded":
        # Surface the error message so callers can detect content-filter rejections
        err = pd.get("error", "") if isinstance(pd, dict) else ""
        raise RuntimeError(f"prediction {pid} ended with status={status} error={err}")
    return output


def _is_content_filter_error(exc_msg: str) -> bool:
    """gpt-image-2 content-filter rejections show up as E005 / 'flagged as sensitive'."""
    msg = exc_msg.lower()
    return ("e005" in msg) or ("flagged as sensitive" in msg) or ("content_policy" in msg)


def pil_letterbox_vertical(horizontal_path, vertical_path):
    """Fallback when AI vertical generation is blocked (content filter, rate limit, etc.).
    Pads the horizontal slide to 2:3 (1024x1536) on a [brand background color] background.
    Preserves all original content — no AI, no reflow, just a clean letterbox so the
    slide still drops into a Reels/Shorts edit without breaking aspect-ratio."""
    from PIL import Image
    src = Image.open(horizontal_path).convert("RGB")
    target_w, target_h = 1024, 1536
    # Scale source to fit width with margin
    margin = 32
    avail_w = target_w - margin * 2
    scale = avail_w / src.width
    new_w = avail_w
    new_h = int(src.height * scale)
    src = src.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGB", (target_w, target_h), (18, 18, 18))  # #121212 [brand background color]
    y = (target_h - new_h) // 2
    canvas.paste(src, (margin, y))
    canvas.save(vertical_path, "JPEG", quality=88)
    print(f"  Vertical [PIL fallback] → {vertical_path.name} "
          f"({vertical_path.stat().st_size} bytes)")


def make_vertical(horizontal_path, vertical_path, quality, token):
    with open(horizontal_path, "rb") as f:
        data_uri = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
    payload = {
        "prompt": VERTICAL_PROMPT,
        "input_images": [data_uri],
        "aspect_ratio": "2:3",
        "output_format": "jpeg",
        "quality": quality,
    }
    out = replicate_predict(REPLICATE_MODEL, payload, token)
    url = out if isinstance(out, str) else out[0]
    img = urllib.request.urlopen(url, timeout=60).read()
    vertical_path.write_bytes(img)
    print(f"  Vertical → {vertical_path.name} ({len(img)} bytes)")


# ─────────────────────────────────────────────────────────────────────────────
# Drive upload
# ─────────────────────────────────────────────────────────────────────────────

def upload_slides(slide_dir, slideshow_folder_id):
    # Delete prior slide-*.jpg in Drive folder
    existing = gapi("drive", "search",
                    f"'{slideshow_folder_id}' in parents and trashed = false",
                    "--raw-query", "--max", "200")
    for f in existing:
        if f["name"].startswith("slide-") and f["name"].endswith(".jpg"):
            gapi("drive", "delete", f["id"])
            print(f"  Deleted prior {f['name']}")
    # Upload in numeric order
    for jpg in sorted(slide_dir.glob("slide-*.jpg")):
        up = gapi("drive", "upload", str(jpg), "--parent", slideshow_folder_id)
        print(f"  Uploaded {jpg.name} → {up['id']}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf-id", required=True, help="Drive file ID of the source PDF")
    ap.add_argument("--topic-slug", required=True, help="Local working dir slug (e.g. 01-pure-play-space-stocks)")
    ap.add_argument("--topic-folder-id", required=True, help="Drive folder ID of the topic folder (slideshow/ created inside)")
    ap.add_argument("--quality", choices=["medium", "high"], default="medium")
    ap.add_argument("--skip-vertical", action="store_true", help="Only render horizontal JPGs")
    ap.add_argument("--vertical-only", action="store_true", help="Skip PDF render; use existing slide-NN.jpg")
    ap.add_argument("--from", dest="from_", type=int, default=1, help="First slide to process (1-indexed)")
    ap.add_argument("--to", type=int, default=None, help="Last slide to process (inclusive)")
    ap.add_argument("--zoom", type=float, default=2.0, help="PDF render zoom (2.0 ≈ 2560x1440 for 16:9)")
    ap.add_argument("--no-upload", action="store_true", help="Skip Drive upload (local-only run)")
    args = ap.parse_args()

    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token and not args.skip_vertical:
        sys.exit("REPLICATE_API_TOKEN missing. Set env var or use --skip-vertical.")

    work_dir = ROOT / args.topic_slug / "slideshow"
    work_dir.mkdir(parents=True, exist_ok=True)
    print(f"Work dir: {work_dir}")

    svc = _drive_service()

    # 1. Ensure slideshow/ subfolder + move PDF into it
    print("\n[1] Setting up Drive slideshow/ folder")
    slideshow_id = find_or_create_slideshow_folder(args.topic_folder_id, svc)
    print(f"  slideshow folder: {slideshow_id}")
    move_to_folder(args.pdf_id, slideshow_id, svc)

    # 2. Download PDF
    pdf_meta = svc.files().get(fileId=args.pdf_id, fields="name").execute()
    pdf_path = work_dir / pdf_meta["name"]
    if not pdf_path.exists():
        print("\n[2] Downloading PDF")
        download_pdf(args.pdf_id, pdf_path)
    else:
        print(f"\n[2] PDF already local: {pdf_path}")

    # 3. Render pages
    if args.vertical_only:
        slides = sorted(work_dir.glob("slide-[0-9][0-9].jpg"))
        if not slides:
            sys.exit("--vertical-only set but no slide-NN.jpg files found. Run without this flag first.")
        print(f"\n[3] Skipping render; found {len(slides)} existing slides")
    else:
        print("\n[3] Rendering PDF pages to JPG")
        slides = render_pdf(pdf_path, work_dir, zoom=args.zoom)

    # 4. Generate verticals
    if not args.skip_vertical:
        print(f"\n[4] Generating verticals (quality={args.quality}) for slides {args.from_}-{args.to or len(slides)}")
        filter_fallbacks = []
        for slide in slides:
            n = int(slide.stem.split("-")[1])
            if n < args.from_ or (args.to is not None and n > args.to):
                continue
            vert = slide.with_name(f"slide-{n:02d}-vertical.jpg")
            if vert.exists():
                print(f"  slide-{n:02d}-vertical.jpg exists, skipping (delete to force re-run)")
                continue
            print(f"  Generating vertical for slide-{n:02d} ...")
            # Try AI generation up to 2 times (filter rejections are sometimes nondeterministic);
            # on persistent content-filter rejection, fall back to PIL letterbox so the deck
            # still completes and the user has a usable 2:3 frame for every slide.
            last_err = None
            for attempt in range(2):
                try:
                    make_vertical(slide, vert, args.quality, token)
                    last_err = None
                    break
                except RuntimeError as e:
                    last_err = e
                    msg = str(e)
                    if _is_content_filter_error(msg):
                        print(f"    content filter rejection on attempt {attempt+1}: {msg[:200]}")
                        if attempt == 0:
                            time.sleep(2)
                            continue
                        break  # don't retry forever on filter
                    # Non-filter error — re-raise so we fail loud
                    raise
            if last_err is not None and _is_content_filter_error(str(last_err)):
                print(f"    falling back to PIL letterbox for slide-{n:02d}")
                pil_letterbox_vertical(slide, vert)
                filter_fallbacks.append(n)
        if filter_fallbacks:
            print(f"\n  NOTE: {len(filter_fallbacks)} slide(s) used PIL letterbox fallback "
                  f"due to content-filter rejection: {filter_fallbacks}")
    else:
        print("\n[4] --skip-vertical set; skipping AI step")

    # 5. Upload
    if args.no_upload:
        print("\n[5] --no-upload set; skipping Drive upload")
    else:
        print("\n[5] Uploading to Drive slideshow/ folder")
        upload_slides(work_dir, slideshow_id)

    print("\n=== Done ===")
    print(f"Drive: https://drive.google.com/drive/folders/{slideshow_id}")


if __name__ == "__main__":
    main()
