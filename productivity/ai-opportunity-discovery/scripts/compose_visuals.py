#!/usr/bin/env python3
"""Composite exact text and data onto AI-generated base plates (PIL).

Layer 2 of the two-layer visual system. gen_visuals.py makes the imagery;
this puts every number, name, and label on top with pixel-exact control, so
no figure in a client deliverable was ever drawn by a generative model.

Usage:
  python3 compose_visuals.py --spec compose.json --outdir figures/

Spec:
{
  "palette": {"ink": "#12212E", "accent": "#B5762F", "paper": "#FFFFFF",
              "muted": "#6B7280", "wash": "#0E1B27"},
  "figures": [
    {"type": "cover", "out": "cover.png", "base": "assets/cover.png",
     "title": "Acme Logistics", "subtitle": "AI Opportunity Plan",
     "meta": ["Prepared for Jane Doe", "March 2026", "Confidential"]},

    {"type": "header", "out": "hdr_invoice.png", "base": "assets/hdr_invoice.png",
     "title": "Project 1 — Invoice Intake", "kicker": "$48,900 / year"},

    {"type": "kpi", "out": "kpi.png", "base": "assets/panel.png",
     "title": "What this program delivers",
     "items": [{"value": "3,419", "label": "hours returned each year"},
               {"value": "$160,900", "label": "estimated annual savings"},
               {"value": "month 16", "label": "pays for itself"}]},

    {"type": "beforeafter", "out": "flow.png",
     "title": "Invoice intake, today and after",
     "before": {"label": "Today", "steps": ["Email arrives", "Manual key-in",
                                            "Second review", "Post to ledger"],
                "note": "14 min each · 120 per week"},
     "after": {"label": "After", "steps": ["Email arrives", "System drafts entry",
                                           "One approval", "Posted"],
               "note": "4 min each · same volume"}}
  ]
}

Fonts resolve from a bundled list of common Linux/macOS faces; override with
"font_regular"/"font_bold" absolute paths in the spec.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:
    sys.exit("Pillow not installed. Run: pip install pillow")

FONT_CANDIDATES = {
    "bold": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ],
    "regular": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ],
}

W, H = 1800, 1200  # base canvas; cover is portrait, headers are wide

PALETTE_DEFAULT = {
    "ink": "#12212E", "accent": "#B5762F", "paper": "#FFFFFF",
    "muted": "#6B7280", "wash": "#0E1B27",
}


def _font_path(kind: str, spec: dict) -> str:
    override = spec.get(f"font_{kind}")
    if override and os.path.exists(override):
        return override
    for p in FONT_CANDIDATES[kind]:
        if os.path.exists(p):
            return p
    sys.exit(f"no {kind} font found; set font_{kind} in the spec")


def font(kind: str, size: int, spec: dict):
    return ImageFont.truetype(_font_path(kind, spec), size)


def base_plate(path: str | None, size: tuple, palette: dict,
               darken: float = 0.0, blur: float = 0.0) -> Image.Image:
    """Load an AI plate cover-fitted to size, or a flat paper fallback."""
    if path and os.path.exists(path):
        img = Image.open(path).convert("RGB")
        tw, th = size
        sc = max(tw / img.width, th / img.height)
        img = img.resize((max(1, int(img.width * sc)), max(1, int(img.height * sc))),
                         Image.LANCZOS)
        left = (img.width - tw) // 2
        top = (img.height - th) // 2
        img = img.crop((left, top, left + tw, top + th))
    else:
        # No AI plate: fall back to a flat fill. Dark-text figures get paper;
        # light-text figures (cover/header) get the wash so text stays legible.
        img = Image.new("RGB", size,
                        palette["wash"] if darken >= 0.4 else palette["paper"])
        darken = 0.0
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    if darken:
        veil = Image.new("RGB", size, palette["wash"])
        img = Image.blend(img, veil, min(max(darken, 0.0), 1.0))
    return img


def scrim(img: Image.Image, box: tuple, palette: dict, alpha: int = 205):
    """Solid-ish panel behind text so contrast never depends on the AI plate."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(box, radius=18, fill=_rgba(palette["paper"], alpha))
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def _rgba(hex_color: str, a: int) -> tuple:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def wrap(draw, text: str, f, max_w: int) -> list:
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=f) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fig_cover(fig: dict, spec: dict, palette: dict) -> Image.Image:
    size = (1654, 2339)  # A4 @ 200dpi portrait
    img = base_plate(fig.get("base"), size, palette, darken=0.55, blur=1.0)
    d = ImageDraw.Draw(img)
    m = 130
    y = int(size[1] * 0.52)

    d.rectangle([m, y, m + 190, y + 9], fill=palette["accent"])
    y += 60

    f_title = font("bold", 96, spec)
    for line in wrap(d, fig.get("title", ""), f_title, size[0] - 2 * m):
        d.text((m, y), line, font=f_title, fill=palette["paper"])
        y += 112

    if fig.get("subtitle"):
        y += 14
        f_sub = font("regular", 54, spec)
        for line in wrap(d, fig["subtitle"], f_sub, size[0] - 2 * m):
            d.text((m, y), line, font=f_sub, fill=palette["accent"])
            y += 68

    y = size[1] - m - 40 * len(fig.get("meta", []))
    f_meta = font("regular", 32, spec)
    for line in fig.get("meta", []):
        d.text((m, y), line, font=f_meta, fill="#D8DEE4")
        y += 44
    return img


def fig_header(fig: dict, spec: dict, palette: dict) -> Image.Image:
    size = (1800, 600)
    img = base_plate(fig.get("base"), size, palette, darken=0.5, blur=0.6)
    d = ImageDraw.Draw(img)
    m = 90

    f_title = font("bold", 66, spec)
    lines = wrap(d, fig.get("title", ""), f_title, size[0] - 2 * m - 40)
    total = len(lines) * 80 + (70 if fig.get("kicker") else 0)
    y = (size[1] - total) // 2

    d.rectangle([m - 30, y, m - 18, y + total], fill=palette["accent"])
    for line in lines:
        d.text((m, y), line, font=f_title, fill=palette["paper"])
        y += 80
    if fig.get("kicker"):
        d.text((m, y + 8), fig["kicker"], font=font("bold", 44, spec),
               fill=palette["accent"])
    return img


def fig_kpi(fig: dict, spec: dict, palette: dict) -> Image.Image:
    size = (1800, 760)
    img = base_plate(fig.get("base"), size, palette, darken=0.08, blur=2.5)
    img = scrim(img, (60, 60, size[0] - 60, size[1] - 60), palette, 216)
    d = ImageDraw.Draw(img)

    if fig.get("title"):
        d.text((110, 118), fig["title"], font=font("bold", 46, spec),
               fill=palette["ink"])

    items = fig.get("items", [])[:4]
    if not items:
        return img
    top, bottom = 250, size[1] - 120
    col_w = (size[0] - 220) // len(items)
    f_val = font("bold", 92, spec)
    f_lab = font("regular", 30, spec)

    for i, it in enumerate(items):
        cx = 110 + col_w * i + col_w // 2
        if i:
            x = 110 + col_w * i
            d.line([(x, top + 20), (x, bottom - 20)], fill="#D4D9DE", width=2)
        val = str(it.get("value", ""))
        vw = d.textlength(val, font=f_val)
        d.text((cx - vw / 2, top + 30), val, font=f_val, fill=palette["accent"])
        ly = top + 160
        for line in wrap(d, it.get("label", ""), f_lab, col_w - 70):
            lw = d.textlength(line, font=f_lab)
            d.text((cx - lw / 2, ly), line, font=f_lab, fill=palette["muted"])
            ly += 40
    return img


def fig_beforeafter(fig: dict, spec: dict, palette: dict) -> Image.Image:
    size = (1800, 1000)
    img = base_plate(fig.get("base"), size, palette, darken=0.05, blur=3.0)
    img = scrim(img, (50, 50, size[0] - 50, size[1] - 50), palette, 224)
    d = ImageDraw.Draw(img)

    if fig.get("title"):
        d.text((100, 95), fig["title"], font=font("bold", 48, spec),
               fill=palette["ink"])

    f_col = font("bold", 34, spec)
    f_step = font("regular", 30, spec)
    f_note = font("regular", 28, spec)
    top = 220
    col_w = (size[0] - 260) // 2

    for idx, key in enumerate(("before", "after")):
        col = fig.get(key) or {}
        x = 100 + idx * (col_w + 60)
        accent = palette["muted"] if key == "before" else palette["accent"]
        d.rounded_rectangle([x, top, x + col_w, size[1] - 110], radius=16,
                            outline="#C9D0D6", width=2,
                            fill="#F7F8F9" if key == "before" else "#FFFFFF")
        d.rounded_rectangle([x, top, x + col_w, top + 74], radius=16, fill=accent)
        d.text((x + 30, top + 20), col.get("label", key.title()),
               font=f_col, fill="#FFFFFF")

        y = top + 118
        for n, step in enumerate(col.get("steps", []), 1):
            d.ellipse([x + 30, y + 2, x + 62, y + 34], fill=accent)
            nw = d.textlength(str(n), font=f_note)
            d.text((x + 46 - nw / 2, y + 6), str(n), font=f_note, fill="#FFFFFF")
            for line in wrap(d, step, f_step, col_w - 120):
                d.text((x + 82, y + 2), line, font=f_step, fill=palette["ink"])
                y += 40
            y += 26

        if col.get("note"):
            d.text((x + 30, size[1] - 178), col["note"], font=f_note, fill=accent)
    return img


RENDERERS = {"cover": fig_cover, "header": fig_header, "kpi": fig_kpi,
             "beforeafter": fig_beforeafter}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--spec", required=True)
    p.add_argument("--outdir", default="figures")
    a = p.parse_args()

    with open(a.spec, encoding="utf-8") as f:
        spec = json.load(f)
    palette = dict(PALETTE_DEFAULT, **(spec.get("palette") or {}))
    os.makedirs(a.outdir, exist_ok=True)

    out = []
    for fig in spec.get("figures", []):
        r = RENDERERS.get(fig.get("type"))
        if not r:
            print(f"skip unknown figure type {fig.get('type')}", file=sys.stderr)
            continue
        img = r(fig, spec, palette)
        path = os.path.join(a.outdir, fig.get("out", f"{fig['type']}.png"))
        img.save(path, "PNG")
        out.append({"out": path, "type": fig["type"], "size": img.size,
                    "ai_base": bool(fig.get("base"))})
        print(f"wrote {path} {img.size}")

    print(json.dumps({"figures": len(out), "results": out}, indent=2))


if __name__ == "__main__":
    main()
