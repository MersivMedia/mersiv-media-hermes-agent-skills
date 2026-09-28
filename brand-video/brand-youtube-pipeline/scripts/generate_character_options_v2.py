#!/usr/bin/env python3
"""Generate 6 [brand] character variants WITH the real brand logo
embroidered on the hat.

Differences from v1 (generate_character_options.py):
- Passes the actual brand-logo.png as input_images reference
- Prompt explicitly describes the emblem composition
  ([brand emblem]) and demands it be rendered as raised hand-sewn embroidery, not a
  flat sticker
- Saves to character-options-v2/

Requires the logo at:
  ~/.hermes/data/brand-youtube-pipeline/brand/brand-logo.png

USAGE:
  set -a; source ~/.hermes/.env; set +a
  python3 ~/.hermes/skills/brand/brand-youtube-pipeline/scripts/generate_character_options_v2.py

This is the canonical character-generation script going forward. v1 is kept
only as fallback for runs without the logo file.
"""
import os, json, time, urllib.request, urllib.error, base64, sys, threading, traceback
from pathlib import Path

TOKEN = os.environ["REPLICATE_API_TOKEN"]

OUT_DIR = Path.home() / ".hermes/data/brand-youtube-pipeline/character-options-v2"
OUT_DIR.mkdir(parents=True, exist_ok=True)

LOGO_PATH = Path.home() / ".hermes/data/brand-youtube-pipeline/brand/brand-logo.png"
if not LOGO_PATH.exists():
    print(f"ERROR: logo not found at {LOGO_PATH}", file=sys.stderr)
    print("Download from Drive (file id <DRIVE_FILE_ID>):", file=sys.stderr)
    print(f"  curl -sL 'https://drive.google.com/uc?export=download&id=<DRIVE_FILE_ID>' -o {LOGO_PATH}", file=sys.stderr)
    sys.exit(2)
LOGO_DATA_URI = "data:image/png;base64," + base64.b64encode(LOGO_PATH.read_bytes()).decode()

MODEL = "openai/gpt-image-2"

EMBLEM = (
    "An embroidered emblem patch on the FRONT-CENTER of his hat, matching the reference image: "
    "[brand emblem — describe your logo's shapes, colors and layout here]. The emblem is rendered as "
    "RAISED EMBROIDERY: visible thread texture, slight relief from the hat fabric, threads catching "
    "the warm key light, edges sewn with a tight satin stitch. The patch is roughly 3-4 inches wide, "
    "weathered from wear (a few loose threads at one corner), and sits perfectly readable on the hat. "
    "It must look hand-sewn and authentic — NOT a printed sticker, NOT a flat 2D graphic pasted on. "
    "Composition of the emblem matches the provided reference image exactly."
)

BASE = (
    "Photorealistic portrait of a middle-aged [character], "
    "[character appearance: age, build, face, hair, expression baseline]. "
    "Wardrobe: [costume]. "
    f"{EMBLEM} "
    "Lighting is dramatic: [brand background color] background (#121212) with a single warm [brand accent color] "
    "key light from camera-left and a faint [brand secondary color] rim light from behind. Subtle [brand text color] "
    "highlights on the face. Cinematic, high-detail, sharp focus on the face AND on the embroidered "
    "emblem (the [brand emblem] should be clearly readable), shallow depth of field. "
    "Shot on 85mm portrait lens. No cartoon, no illustration — must look like a real human in a real "
    "photograph. Color palette anchored in: [brand background color] (default #121212), [brand text color] (default #F0F0F0), [brand accent color] "
    "#FFC107, [brand emphasis color] (default #E53935), [brand secondary color] (default #26A69A)."
)

VARIANTS = [
    {"name": "01_centered",
     "tag": "[costume variant 1: headwear/outfit detail]. Angle: dead-on, chest-up, looking directly at viewer. Expression: slight smirk, one eyebrow raised. Grunge: medium."},
    {"name": "02_three_quarter",
     "tag": "[costume variant 2: headwear/outfit detail]. Angle: three-quarter view, head tilted slightly down, eyes looking up at viewer. Expression: deadpan, almost daring. Grunge: heavier — visible dust, frayed edges."},
    {"name": "03_profile_turn",
     "tag": "[costume variant 3: headwear/outfit detail]. Angle: three-quarter pivoting toward camera, dynamic. Expression: knowing half-smile. Grunge: high — [costume] shows clear wear, soot on one cheekbone."},
    {"name": "04_clean_authoritative",
     "tag": "[costume variant 4: headwear/outfit detail]. Angle: dead-on, head and shoulders, slight upward camera angle making him authoritative. Expression: serious, mouth thin line, eyes have humor. Grunge: low — clean version."},
    {"name": "05_three_quarter_dynamic",
     "tag": "[costume variant 5: headwear/outfit detail]. Angle: three-quarter, slight lean forward, arms cropped at elbow showing a hand resting on a prop. Expression: leaning into a story — engaged, alive. Grunge: medium-high."},
    {"name": "06_close_portrait_intense",
     "tag": "[costume variant 6: headwear/outfit detail]. Angle: tight close-up, face and upper chest, emblem patch in upper portion of frame. Expression: dead serious, intense direct eye contact. Grunge: medium — focused on texture of skin, hair, [costume] fabric, and thread texture of emblem. Background nearly pure [brand background color]."},
]


def build_prompt(tag: str) -> str:
    return (f"{BASE}\n\nSPECIFICS FOR THIS SHOT:\n{tag}\n\n"
            "REFERENCE IMAGE: The provided input image shows the EXACT logo "
            "composition that must appear as embroidery on the hat. Match its "
            "composition but render "
            "it as raised hand-sewn thread on dark hat fabric, not as a flat "
            "vector graphic. The reference is for COMPOSITION ONLY — the final "
            "emblem on the hat should look like real embroidery: weathered, "
            "slightly bumpy, threads catching the key light.")


def submit(prompt: str) -> str:
    body = json.dumps({"input": {
        "prompt": prompt, "input_images": [LOGO_DATA_URI],
        "aspect_ratio": "2:3", "output_format": "png", "quality": "high",
    }}).encode()
    req = urllib.request.Request(
        f"https://api.replicate.com/v1/models/{MODEL}/predictions",
        data=body,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json", "Prefer": "wait=0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read())["id"]
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}") from e


def poll(pid: str, deadline: float) -> dict:
    while time.time() < deadline:
        req = urllib.request.Request(
            f"https://api.replicate.com/v1/predictions/{pid}",
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
        if d.get("status") in ("succeeded", "failed", "canceled"):
            return d
        time.sleep(5)
    raise TimeoutError(f"timeout polling {pid}")


def download(url: str, dest: Path):
    dest.write_bytes(urllib.request.urlopen(url, timeout=120).read())


def run_one(variant, results):
    name = variant["name"]
    try:
        pid = submit(build_prompt(variant["tag"]))
        print(f"[{name}] submitted -> {pid}", flush=True)
        d = poll(pid, time.time() + 540)
        if d.get("status") != "succeeded":
            results[name] = {"ok": False, "err": f"{d.get('status')} {d.get('error')}"}
            return
        url = d["output"] if isinstance(d["output"], str) else d["output"][0]
        dest = OUT_DIR / f"{name}.png"
        download(url, dest)
        results[name] = {"ok": True, "path": str(dest)}
        print(f"[{name}] saved -> {dest}", flush=True)
    except Exception as e:
        traceback.print_exc()
        results[name] = {"ok": False, "err": str(e)}


def main():
    results = {}
    threads = []
    for v in VARIANTS:
        t = threading.Thread(target=run_one, args=(v, results), daemon=True)
        t.start(); threads.append(t); time.sleep(0.7)
    for t in threads:
        t.join(timeout=600)
    print("\n=== RESULTS ===")
    for v in VARIANTS:
        r = results.get(v["name"], {"ok": False, "err": "no result"})
        print(f"{v['name']:50s} {'OK ' if r['ok'] else 'ERR'}  {r.get('path') or r.get('err')}")
    (OUT_DIR / "manifest.json").write_text(json.dumps({
        "variants": [{**v, **results.get(v["name"], {})} for v in VARIANTS]
    }, indent=2))


if __name__ == "__main__":
    main()
