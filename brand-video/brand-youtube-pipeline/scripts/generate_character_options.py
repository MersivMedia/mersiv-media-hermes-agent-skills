#!/usr/bin/env python3
"""Generate 6 [brand] character variants via gpt-image-2.

Parallel submission, polling with shared deadline. Saves to
~/.hermes/data/brand-youtube-pipeline/character-options/

Requires REPLICATE_API_TOKEN in env (source from ~/.hermes/.env).

USAGE:
  set -a; source ~/.hermes/.env; set +a
  python3 ~/.hermes/skills/brand/brand-youtube-pipeline/scripts/generate_character_options.py

PITFALL: gpt-image-2 read-timeouts at provider layer are not retried by the
client. If a variant errors with "ReadTimeout", retry that single variant
rather than re-running the whole batch.
"""
import os, json, time, urllib.request, urllib.error, sys, threading, traceback
from pathlib import Path

TOKEN = os.environ.get("REPLICATE_API_TOKEN")
if not TOKEN:
    print("ERROR: REPLICATE_API_TOKEN not set", file=sys.stderr); sys.exit(2)

OUT_DIR = Path.home() / ".hermes/data/brand-youtube-pipeline/character-options"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL = "openai/gpt-image-2"

# Brand emblem (later swappable via i2i once the brand emblem asset is set as reference)
EMBLEM = (
    "a small embroidered patch on the front of his hat: the [brand emblem] "
    "in gold thread on a dark "
    "background — small, weathered, looks authentic and lived-in, not a sticker"
)

BASE = (
    "Photorealistic portrait of a middle-aged [character], "
    "[character appearance: age, build, face, hair, expression baseline]. "
    "Wardrobe: [costume]. "
    f"{EMBLEM}. "
    "Lighting is dramatic: [brand background color] background (#121212) with a single warm [brand accent color] "
    "key light from camera-left and a faint [brand secondary color] rim light from behind. Subtle [brand text color] "
    "highlights on the face. Cinematic, high-detail, sharp focus on the face, shallow depth of field. "
    "Shot on 85mm portrait lens. No cartoon, no illustration — must look like a real human in a "
    "real photograph. Color palette anchored in: [brand background color] (default #121212), [brand text color] (default #F0F0F0), "
    "[brand accent color] (default #FFC107), [brand emphasis color] (default #E53935), [brand secondary color] (default #26A69A)."
)

VARIANTS = [
    {
        "name": "01_centered",
        "tag": "[costume variant 1: headwear/outfit detail]. Angle: dead-on, chest-up, looking directly at viewer. Expression: slight smirk, one eyebrow raised. Grunge: medium — clean enough to look intentional.",
    },
    {
        "name": "02_three_quarter",
        "tag": "[costume variant 2: headwear/outfit detail]. Angle: three-quarter view, head tilted slightly down, eyes looking up at viewer. Expression: deadpan, almost daring. Grunge: heavier — visible dust, frayed edges on the [costume].",
    },
    {
        "name": "03_profile_turn",
        "tag": "[costume variant 3: headwear/outfit detail]. Angle: profile pivoting toward camera, dynamic, like he just turned to address someone. Expression: knowing half-smile, like he just heard the punchline first. Grunge: high — [costume] shows clear wear, soot on one cheekbone.",
    },
    {
        "name": "04_clean_authoritative",
        "tag": "[costume variant 4: headwear/outfit detail]. Angle: dead-on, head and shoulders, slight upward camera angle making him look authoritative. Expression: serious, mouth a thin line, but the eyes have humor. Grunge: low — this is his clean version, sharper [costume].",
    },
    {
        "name": "05_three_quarter_dynamic",
        "tag": "[costume variant 5: headwear/outfit detail]. Angle: three-quarter, slight lean forward, arms cropped just at the elbow showing hand resting on a prop. Expression: leaning into a story he's about to tell — engaged, alive, eyes locked on the viewer. Grunge: medium-high.",
    },
    {
        "name": "06_close_portrait_intense",
        "tag": "[costume variant 6: headwear/outfit detail]. Angle: tight close-up, face only, shoulders barely visible. Expression: dead serious, intense direct eye contact, like the cold open of the video. Grunge: medium — focused on the texture of skin, hair, [costume] fabric. Background goes nearly pure [brand background color].",
    },
]


def build_prompt(variant_tag: str) -> str:
    return f"{BASE}\n\nSPECIFICS FOR THIS SHOT:\n{variant_tag}"


def submit(prompt: str) -> str:
    body = json.dumps({
        "input": {
            "prompt": prompt,
            "aspect_ratio": "2:3",
            "output_format": "png",
            "quality": "high",
        }
    }).encode()
    req = urllib.request.Request(
        f"https://api.replicate.com/v1/models/{MODEL}/predictions",
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "Prefer": "wait=0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body_err}") from e
    return d["id"]


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
        time.sleep(4)
    raise TimeoutError(f"timeout polling {pid}")


def download(url: str, dest: Path):
    data = urllib.request.urlopen(url, timeout=90).read()
    dest.write_bytes(data)


def run_one(variant, results):
    name = variant["name"]
    try:
        prompt = build_prompt(variant["tag"])
        pid = submit(prompt)
        print(f"[{name}] submitted -> {pid}", flush=True)
        deadline = time.time() + 480
        d = poll(pid, deadline)
        if d.get("status") != "succeeded":
            results[name] = {"ok": False, "err": f"status={d.get('status')} err={d.get('error')}"}
            print(f"[{name}] FAILED: {d.get('error')}", flush=True)
            return
        output = d.get("output")
        url = output if isinstance(output, str) else output[0]
        dest = OUT_DIR / f"{name}.png"
        download(url, dest)
        results[name] = {"ok": True, "path": str(dest), "url": url}
        print(f"[{name}] saved -> {dest}", flush=True)
    except Exception as e:
        traceback.print_exc()
        results[name] = {"ok": False, "err": str(e)}


def main():
    results = {}
    threads = []
    for v in VARIANTS:
        t = threading.Thread(target=run_one, args=(v, results), daemon=True)
        t.start()
        threads.append(t)
        time.sleep(0.5)
    for t in threads:
        t.join(timeout=540)
    print("\n=== RESULTS ===")
    for v in VARIANTS:
        r = results.get(v["name"], {"ok": False, "err": "no result"})
        print(f"{v['name']:50s} {'OK ' if r['ok'] else 'ERR'}  {r.get('path') or r.get('err')}")
    (OUT_DIR / "manifest.json").write_text(json.dumps({
        "variants": [{**v, **results.get(v["name"], {})} for v in VARIANTS]
    }, indent=2))


if __name__ == "__main__":
    main()
