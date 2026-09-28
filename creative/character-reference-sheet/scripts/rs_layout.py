#!/usr/bin/env python3
"""Compose the human-readable character reference sheet from verified plates.

Layout follows the 7-section production sheet format:
  1 CHARACTER PROFILE    2 FULL-BODY TURNAROUND
  3 FACE AND IDENTITY    4 EXPRESSION SHEET
  5 POSE AND BODY LANG.  6 COSTUME DETAILS
  7 COLOR AND MATERIAL PALETTE
Every word, swatch and hex code is drawn here from the authored spec. None of
it is generated, so nothing can be misspelled or drift. Missing plates (dropped
by QC) reflow out of their row instead of leaving holes.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

INK = (32, 33, 36)
MUTED = (95, 99, 104)
RULE = (218, 220, 224)
PAPER = (255, 255, 255)
CELL = (246, 247, 248)
FONT_DIRS = [Path.home() / ".fonts", Path("/usr/share/fonts/truetype/dejavu")]


def font(size, weight="Regular"):
    for name in (f"Inter-{weight}.ttf", "Inter-Regular.ttf",
                 "DejaVuSans-Bold.ttf" if weight in ("Bold", "SemiBold", "ExtraBold") else "DejaVuSans.ttf"):
        for d in FONT_DIRS:
            p = d / name
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def text_w(draw, s, f):
    return draw.textbbox((0, 0), s, font=f)[2]


def wrap(draw, s, f, width):
    words, lines, cur = str(s).split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if text_w(draw, t, f) <= width or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def cover(im, w, h, anchor_y=0.5):
    """Cover-fit crop. anchor_y<0.5 keeps the top (faces), 0.5 centres."""
    im = im.convert("RGB")
    s = max(w / im.width, h / im.height)
    r = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    x = (r.width - w) // 2
    y = int((r.height - h) * anchor_y)
    return r.crop((x, y, x + w, y + h))


def contain(im, w, h, bg=CELL):
    """Fit whole plate (full-body: never crop feet or head)."""
    im = im.convert("RGB")
    s = min(w / im.width, h / im.height)
    r = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    out = Image.new("RGB", (w, h), bg)
    out.paste(r, ((w - r.width) // 2, (h - r.height) // 2))
    return out


class Sheet:
    def __init__(self, W=2400, H=3300):
        self.W, self.H = W, H
        self.im = Image.new("RGB", (W, H), PAPER)
        self.d = ImageDraw.Draw(self.im)
        self.f_sec = font(30, "Bold")
        self.f_lab = font(20, "SemiBold")
        self.f_body = font(24)
        self.f_key = font(24, "SemiBold")
        self.f_small = font(19)

    def section(self, x, y, w, h, title):
        self.d.rectangle((x, y, x + w, y + h), outline=RULE, width=2)
        self.d.text((x + 18, y + 14), title.upper(), font=self.f_sec, fill=INK)
        self.d.line((x + 18, y + 58, x + w - 18, y + 58), fill=RULE, width=2)
        return x + 18, y + 72, w - 36, h - 90          # content box

    def label(self, cx, y, s, f=None):
        f = f or self.f_lab
        s = s.upper()
        self.d.text((cx - text_w(self.d, s, f) / 2, y), s, font=f, fill=MUTED)

    def row_of(self, x, y, w, h, items, fit="contain", label_top=True, anchor_y=0.5, gap=12):
        """items: [(label, PIL image or None)]. Label above each cell."""
        items = [it for it in items if it[1] is not None]
        if not items:
            self.d.text((x, y), "(no verified plates)", font=self.f_small, fill=MUTED)
            return
        n = len(items)
        cw = (w - gap * (n - 1)) // n
        lh = 30 if label_top else 0
        for i, (lab, im) in enumerate(items):
            cx = x + i * (cw + gap)
            if label_top:
                self.label(cx + cw / 2, y, lab)
            tile = contain(im, cw, h - lh) if fit == "contain" else cover(im, cw, h - lh, anchor_y)
            self.im.paste(tile, (cx, y + lh))

    def grid(self, x, y, w, h, items, cols, anchor_y=0.35, gap=12, label_below=True):
        items = [it for it in items if it[1] is not None]
        if not items:
            return
        rows = (len(items) + cols - 1) // cols
        cw = (w - gap * (cols - 1)) // cols
        ch = (h - gap * (rows - 1)) // rows
        lh = 30 if label_below else 0
        for i, (lab, im) in enumerate(items):
            r, c = divmod(i, cols)
            cx, cy = x + c * (cw + gap), y + r * (ch + gap)
            self.im.paste(cover(im, cw, ch - lh, anchor_y), (cx, cy))
            if label_below:
                self.label(cx + cw / 2, cy + ch - lh + 4, lab)

    def kv(self, x, y, w, key, val, kw=190):
        self.d.text((x, y), f"{key}:", font=self.f_key, fill=INK)
        lines = wrap(self.d, val, self.f_body, w - kw)
        for i, ln in enumerate(lines):
            self.d.text((x + kw, y + i * 34), ln, font=self.f_body, fill=INK)
        return y + max(1, len(lines)) * 34 + 8

    def swatch(self, x, y, s, hexv, label=None):
        rgb = tuple(int(hexv.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
        self.d.rectangle((x, y, x + s, y + s), fill=rgb, outline=RULE, width=2)
        if label:
            self.label(x + s / 2, y + s + 8, label, self.f_small)


def compose(spec, plates, out_path, W=2400, H=3300):
    """spec: loaded YAML dict. plates: {key: Path} of VERIFIED plates only."""
    S = Sheet(W, H)
    d = S.d
    P = lambda k: Image.open(plates[k]) if k in plates else None   # noqa: E731
    M, G = 24, 16
    iw, ih = W - 2 * M, H - 2 * M
    rows = [0.31, 0.255, 0.25, 0.185]           # must sum to 1.0 or the page ends in a dead band
    hs = [int((ih - G * 3) * r) for r in rows]
    ys = [M]
    for h in hs[:-1]:
        ys.append(ys[-1] + h + G)
    prof = spec.get("profile", {})

    # ---- row 1: profile | turnaround ------------------------------------
    w1 = int(iw * 0.42)
    x, y, w, h = S.section(M, ys[0], w1, hs[0], "1. Character Profile")
    tw = int(w * 0.52)
    hdr = spec.get("header", "AI VIDEO PRODUCTION · CHARACTER REFERENCE SHEET").upper()
    while hdr and text_w(d, hdr, S.f_small) > tw:          # never run under the portrait
        hdr = hdr[:-2].rstrip(" ·") + "…"
    d.text((x, y), hdr, font=S.f_small, fill=MUTED)
    name_f = font(64, "Bold")
    for i, ln in enumerate(wrap(d, spec["name"], name_f, tw)[:2]):
        d.text((x, y + 30 + i * 72), ln, font=name_f, fill=INK)
    yy = y + 30 + 72 * min(2, len(wrap(d, spec["name"], name_f, tw))) + 16
    for k, lab in (("role", "Role"), ("age", "Age"), ("height", "Height"), ("body_type", "Body Type")):
        if prof.get(k):
            yy = S.kv(x, yy, tw, lab, prof[k], kw=150)
    if prof.get("personality"):
        pv = prof["personality"]
        yy = S.kv(x, yy, tw, "Personality", ", ".join(pv) if isinstance(pv, list) else pv, kw=150)
    traits = prof.get("distinctive_traits") or []
    if traits:
        d.text((x, yy + 6), "Distinctive Traits:", font=S.f_key, fill=INK); yy += 44
        for t in traits[:7]:
            for j, ln in enumerate(wrap(d, t, S.f_body, tw - 26)):
                d.text((x + (0 if j else 0), yy), ("•  " if j == 0 else "    ") + ln, font=S.f_body, fill=INK)
                yy += 32
    pal = spec.get("palette") or []
    if pal and yy < y + h - 90:
        d.text((x, yy + 8), "Signature Colors:", font=S.f_key, fill=INK)
        for i, c in enumerate(pal[:6]):
            S.swatch(x + i * 58, yy + 48, 46, c["hex"])
    portrait = P("face_front") or P("anchor")
    if portrait:
        px0 = x + tw + 16
        S.im.paste(cover(portrait, w - (px0 - x), h, 0.25), (px0, y))

    x2 = M + w1 + G
    x, y, w, h = S.section(x2, ys[0], iw - w1 - G, hs[0], "2. Full-Body Turnaround")
    S.row_of(x, y, w, h, [("Front", P("turn_front")), ("3/4 View", P("turn_three_quarter")),
                          ("Side", P("turn_side")), ("Back", P("turn_back"))])

    # ---- row 2: face | expressions ----------------------------------------
    w2 = int(iw * 0.45)
    x, y, w, h = S.section(M, ys[1], w2, hs[1], "3. Face and Identity Details")
    fh = int(h * 0.56)
    S.row_of(x, y, w, fh, [("Front", P("face_front")), ("Profile", P("face_profile")),
                          ("3/4 View", P("face_three_quarter"))], fit="cover", anchor_y=0.2)
    face = spec.get("face", {})
    yy = y + fh + 14
    for k, lab in (("structure", "Facial Structure"), ("eyes", "Eyes"), ("eyebrows", "Eyebrows"),
                   ("nose", "Nose"), ("lips", "Lips"), ("skin_tone", "Skin Tone"), ("hair", "Hair"),
                   ("makeup", "Makeup"), ("marks", "Scars/Tattoos")):
        if face.get(k) and yy < y + h - 30:
            yy = S.kv(x, yy, w, lab, face[k], kw=220) - 6
    x, y, w, h = S.section(M + w2 + G, ys[1], iw - w2 - G, hs[1], "4. Expression Sheet")
    ex = [(k.replace("_", " "), P(f"expr_{k}")) for k in spec.get("_expressions", [])]
    S.grid(x, y, w, h, ex, cols=4, anchor_y=0.2)

    # ---- row 3: poses | costume ---------------------------------------------
    w3 = int(iw * 0.52)
    x, y, w, h = S.section(M, ys[2], w3, hs[2], "5. Pose and Body Language")
    S.row_of(x, y, w, h, [(k.replace("_", " "), P(f"pose_{k}")) for k in spec.get("_poses", [])], gap=8)
    x, y, w, h = S.section(M + w3 + G, ys[2], iw - w3 - G, hs[2], "6. Costume Details")
    cd = [(c["label"], P(f"costume_{i:02d}")) for i, c in enumerate((spec.get("costume") or {}).get("details") or [])]
    S.grid(x, y, w, h, cd, cols=4 if len(cd) > 3 else max(1, len(cd)), anchor_y=0.5)

    # ---- row 4: palette + materials -----------------------------------------
    x, y, w, h = S.section(M, ys[3], iw, hs[3], "7. Color and Material Palette")
    half = w // 2 - 20
    d.text((x, y), "KEY COLORS (HEX)", font=S.f_lab, fill=MUTED)
    if pal:
        n = min(8, len(pal)); gap = 18
        # tall swatch blocks fill the row height (the example sheets use blocks, not chips)
        s = int((half - gap * (n - 1)) / n)
        sh = h - 90
        for i, c in enumerate(pal[:n]):
            sx = x + i * (s + gap)
            rgb = tuple(int(c["hex"].lstrip("#")[j:j + 2], 16) for j in (0, 2, 4))
            d.rectangle((sx, y + 36, sx + s, y + 36 + sh), fill=rgb, outline=RULE, width=2)
            S.label(sx + s / 2, y + 36 + sh + 8, c["hex"].upper(), S.f_small)
    mx = x + half + 40
    d.text((mx, y), "MATERIAL REFERENCES", font=S.f_lab, fill=MUTED)
    mats = [(m["label"], P(f"material_{i:02d}")) for i, m in enumerate(spec.get("materials") or [])]
    mats = [m for m in mats if m[1] is not None]
    if mats:
        n = len(mats); gap = 14
        s = int((w - half - 40 - gap * (n - 1)) / n)
        sh = h - 90
        for i, (lab, im) in enumerate(mats):
            S.im.paste(cover(im, s, sh), (mx + i * (s + gap), y + 36))
            S.label(mx + i * (s + gap) + s / 2, y + 36 + sh + 8, lab, S.f_small)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    S.im.save(out_path, quality=92)
    return out_path
