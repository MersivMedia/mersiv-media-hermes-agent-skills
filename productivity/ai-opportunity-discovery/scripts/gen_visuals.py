#!/usr/bin/env python3
"""Generate AI visual base plates for PRD deliverables via Replicate.

Layer 1 of the two-layer visual system: this script produces ONLY untexted or
lightly-texted imagery (cover backgrounds, section header bands, abstract
textures). Exact numbers, client names, and data labels are overlaid later by
compose_visuals.py in PIL — never asked of the model.

Env: REPLICATE_API_TOKEN (run from `terminal`, not execute_code — the sandbox
does not inherit secrets).

Usage:
  python3 gen_visuals.py --spec visuals.json --outdir assets/

Spec:
{
  "company": "Acme Logistics",
  "industry": "freight and logistics",
  "palette": "deep navy, warm bronze, off-white",
  "model": "ideogram-v3-turbo",
  "assets": [
    {"id": "cover", "kind": "cover", "aspect_ratio": "3:2"},
    {"id": "hdr_invoice", "kind": "header", "subject": "invoice documents flowing",
     "aspect_ratio": "3:1"},
    {"id": "panel", "kind": "texture", "aspect_ratio": "16:9"}
  ]
}

Models: ideogram-v3-turbo (fast, ~$0.03), ideogram-v3-quality (~$0.09),
gpt-image-2 (use only when legible text really must be rendered by the model).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

# Replicate 403s the default Python-urllib User-Agent.
_opener = urllib.request.build_opener()
_opener.addheaders = [("User-Agent", "HermesPRDVisuals/1.0")]
urllib.request.install_opener(_opener)

MODELS = {
    "ideogram-v3-turbo": "ideogram-ai/ideogram-v3-turbo",
    "ideogram-v3-quality": "ideogram-ai/ideogram-v3-quality",
    "gpt-image-2": "openai/gpt-image-2",
}

# Corporate-deck-safe defaults. Overridable per asset.
NEGATIVE = (
    "no text, no words, no letters, no numbers, no charts, no graphs, "
    "no logos, no watermarks, no UI mockups, no people's faces, "
    "no stock-photo businesspeople shaking hands, no glowing brains, "
    "no humanoid robots, no circuit-board cliches"
)

KIND_PROMPTS = {
    "cover": (
        "Abstract editorial cover artwork for a professional consulting report about "
        "{industry}. {palette} palette. Clean geometric composition with generous empty "
        "space in the lower third for a title to be placed later. Soft directional light, "
        "subtle paper grain, restrained and corporate, museum-quality print aesthetic. "
        "{negative}"
    ),
    "header": (
        "Wide abstract banner illustration representing {subject}, for a business report "
        "section header. {palette} palette. Minimal flat-geometric style, calm, lots of "
        "negative space, no focal clutter. Reads clearly at small size. {negative}"
    ),
    "texture": (
        "Subtle abstract background texture in a {palette} palette. Very low contrast, "
        "soft gradient, faint geometric structure. Designed to sit behind dark text "
        "without reducing legibility. Understated and premium. {negative}"
    ),
    "divider": (
        "Slim horizontal abstract divider graphic, {palette} palette, minimal geometric "
        "forms on a clean background, extremely simple. {negative}"
    ),
}

STYLE_DEFAULTS = {"style_type": "Design", "magic_prompt_option": "Off"}


def build_prompt(asset: dict, spec: dict) -> str:
    if asset.get("prompt"):
        return asset["prompt"] + " " + NEGATIVE
    kind = asset.get("kind", "texture")
    tpl = KIND_PROMPTS.get(kind, KIND_PROMPTS["texture"])
    return tpl.format(
        industry=spec.get("industry", "business operations"),
        palette=spec.get("palette", "deep navy, slate grey, off-white"),
        subject=asset.get("subject", "abstract business process"),
        negative=NEGATIVE,
    )


def submit(model_slug: str, payload: dict, token: str) -> dict:
    body = json.dumps({"input": payload}).encode()
    big = len(body) > 1_000_000
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if not big:
        headers["Prefer"] = "wait=60"
    req = urllib.request.Request(
        f"https://api.replicate.com/v1/models/{model_slug}/predictions",
        data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"replicate {e.code}: {e.read().decode()[:400]}")


def poll(pid: str, token: str, deadline_s: int = 420) -> tuple:
    end = time.time() + deadline_s
    while time.time() < end:
        req = urllib.request.Request(
            f"https://api.replicate.com/v1/predictions/{pid}",
            headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
        if d.get("status") in ("succeeded", "failed", "canceled"):
            return d.get("status"), d.get("output"), d.get("error")
        time.sleep(3)
    return "timeout", None, "polling deadline exceeded"


def download(output, path: str) -> None:
    url = output if isinstance(output, str) else output[0]
    if url.startswith("data:"):
        raw = base64.b64decode(url.split(",", 1)[1])
    else:
        with urllib.request.urlopen(url, timeout=90) as r:
            raw = r.read()
    with open(path, "wb") as f:
        f.write(raw)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--spec", required=True)
    p.add_argument("--outdir", default="assets")
    p.add_argument("--model", default=None, help="override spec model")
    p.add_argument("--dry-run", action="store_true",
                   help="print prompts and cost estimate, generate nothing")
    a = p.parse_args()

    token = os.environ.get("REPLICATE_API_TOKEN")
    with open(a.spec, encoding="utf-8") as f:
        spec = json.load(f)
    assets = spec.get("assets") or []
    if not assets:
        sys.exit("spec has no assets")

    name = a.model or spec.get("model", "ideogram-v3-turbo")
    if name not in MODELS:
        sys.exit(f"unknown model {name}; choose from {sorted(MODELS)}")
    slug = MODELS[name]
    unit = {"ideogram-v3-turbo": 0.03, "ideogram-v3-quality": 0.09,
            "gpt-image-2": 0.17}[name]

    if a.dry_run:
        for asset in assets:
            print(f"--- {asset['id']} [{asset.get('kind','texture')}]")
            print(build_prompt(asset, spec), "\n")
        print(json.dumps({"model": name, "count": len(assets),
                          "est_cost_usd": round(unit * len(assets), 2)}, indent=2))
        return

    if not token:
        sys.exit("REPLICATE_API_TOKEN not set — run this from `terminal`, "
                 "not execute_code")
    os.makedirs(a.outdir, exist_ok=True)
    results = []

    for asset in assets:
        prompt = build_prompt(asset, spec)
        ar = asset.get("aspect_ratio", "3:2")
        if name.startswith("ideogram"):
            payload = dict(STYLE_DEFAULTS, prompt=prompt, aspect_ratio=ar)
            if asset.get("style_preset"):
                payload["style_preset"] = asset["style_preset"]
        else:
            payload = {"prompt": prompt, "aspect_ratio": ar,
                       "output_format": "png",
                       "quality": asset.get("quality", "medium")}

        d = submit(slug, payload, token)
        status, output, err = d.get("status"), d.get("output"), d.get("error")
        if status not in ("succeeded", "failed", "canceled"):
            status, output, err = poll(d["id"], token)

        path = os.path.join(a.outdir, f"{asset['id']}.png")
        if status == "succeeded" and output:
            download(output, path)
            results.append({"id": asset["id"], "path": path, "ok": True})
            print(f"wrote {path}")
        else:
            results.append({"id": asset["id"], "ok": False,
                            "status": status, "error": str(err)[:200]})
            print(f"FAILED {asset['id']}: {status} {str(err)[:200]}",
                  file=sys.stderr)

    ok = sum(1 for r in results if r.get("ok"))
    print(json.dumps({"generated": ok, "failed": len(results) - ok,
                      "est_cost_usd": round(unit * ok, 2),
                      "results": results}, indent=2))
    if ok == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
