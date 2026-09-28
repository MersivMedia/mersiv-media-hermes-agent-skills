#!/usr/bin/env python3
"""Numeric QC gates + backdrop correction for character reference plates.

Recipes (and the measured thresholds) come from generated-asset-verification
references/numeric-gate-recipes.md. Pure PIL, no GPU, no vision model.

Gates
  neutrality   per plate   backdrop channel spread <= 12   (cast baked in)
  uniformity   per group   backdrop luma spread   <= 20    (different "studios")
  distinctness per group   min pairwise delta     >= 6     (duplicate plates)

Correction (normalize): white balance on the known-neutral backdrop, then a
LUMA-ONLY gamma onto the set median, then re-measure. Anything that still
misses is reported as must-regenerate. Raw originals are never touched.

Groups that have no studio backdrop in frame (costume close-ups, material
swatches) are exempt from neutrality/uniformity.
"""
import math
from pathlib import Path

from PIL import Image

NEUTRALITY_TOL = 12.0
UNIFORMITY_TOL = 20.0
DISTINCT_MIN = 6.0
NO_BACKDROP = {"costume", "materials"}


def border_rgb(im, frac=0.10):
    """MEDIAN RGB of the outer frame = the backdrop. Median, not mean: a limb or
    hair in the border strip skews a mean and barely moves a median. The fixer
    and the grader both use THIS function (same estimator, or they disagree)."""
    im = im.convert("RGB")
    w, h = im.size
    bw, bh = max(1, int(w * frac)), max(1, int(h * frac))
    px = []
    for box in ((0, 0, w, bh), (0, h - bh, w, h), (0, 0, bw, h), (w - bw, 0, w, h)):
        px.extend(im.crop(box).resize((64, 64)).getdata())
    m = len(px) // 2
    return tuple(float(sorted(q[c] for q in px)[m]) for c in range(3))


def luma(rgb):
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


def neutrality(im):
    r, g, b = border_rgb(im)
    spread = max(r, g, b) - min(r, g, b)
    cast = "warm" if r == max(r, g, b) else "cool" if b == max(r, g, b) else "green"
    return round(spread, 1), cast


def distinct_pairs(paths, size=48):
    th = {Path(p).stem: list(Image.open(p).convert("L").resize((size, size), Image.LANCZOS).tobytes())
          for p in paths}
    names, out = list(th), []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = th[names[i]], th[names[j]]
            out.append((names[i], names[j], round(sum(abs(x - y) for x, y in zip(a, b)) / len(a), 2)))
    return sorted(out, key=lambda x: x[2])      # closest first: print PAIRS, not just the min


def white_balance(im, tol=6.0):
    r, g, b = border_rgb(im)
    if max(r, g, b) - min(r, g, b) <= tol:
        return im
    t = (r + g + b) / 3.0
    luts = [[min(255, max(0, round(i * t / max(ch, 1.0)))) for i in range(256)] for ch in (r, g, b)]
    rr, gg, bb = im.convert("RGB").split()
    return Image.merge("RGB", (rr.point(luts[0]), gg.point(luts[1]), bb.point(luts[2])))


def normalize_luma(im, target):
    """Gamma (not offset: an offset clips highlights) on Y only. Curving R, G, B
    independently amplifies channel imbalance (measured: neutrality 6.2 -> 12.6)."""
    src = luma(border_rgb(im))
    if src <= 0 or abs(src - target) < 1.0:
        return im
    s = min(max(src / 255, 1e-3), 1 - 1e-3)
    t = min(max(target / 255, 1e-3), 1 - 1e-3)
    g = min(max(math.log(t) / math.log(s), 0.25), 4.0)
    lut = [min(255, max(0, round(255 * (i / 255) ** g))) for i in range(256)]
    y, cb, cr = im.convert("YCbCr").split()
    return Image.merge("YCbCr", (y.point(lut), cb, cr)).convert("RGB")


def run(plates, correct=True):
    """plates: list of dicts {key, group, raw: Path, out: Path}. Writes corrected
    plates to `out` (raw untouched). Returns a report dict."""
    rep = {"plates": {}, "groups": {}, "regenerate": [], "pass": True}
    backdrop = [p for p in plates if p["group"] not in NO_BACKDROP]
    target = None
    if backdrop:
        ls = sorted(luma(border_rgb(Image.open(p["raw"]))) for p in backdrop)
        target = ls[len(ls) // 2]                  # set median: nobody moves far
    rep["target_luma"] = round(target, 1) if target else None

    for p in plates:
        im = Image.open(p["raw"]).convert("RGB")
        row = {"group": p["group"]}
        if p["group"] not in NO_BACKDROP:
            row["raw_neutrality"], row["raw_cast"] = neutrality(im)
            row["raw_luma"] = round(luma(border_rgb(im)), 1)
            if correct:
                im = normalize_luma(white_balance(im), target)
            row["neutrality"], row["cast"] = neutrality(im)
            row["luma"] = round(luma(border_rgb(im)), 1)
            ok_n = row["neutrality"] <= NEUTRALITY_TOL
            ok_l = abs(row["luma"] - target) <= UNIFORMITY_TOL
            row["ok"] = ok_n and ok_l
            if not row["ok"]:
                row["why"] = ("cast %s %.1f" % (row["cast"], row["neutrality"]) if not ok_n else "") + \
                             (" luma %.0f vs target %.0f" % (row["luma"], target) if not ok_l else "")
                rep["regenerate"].append(p["key"])
        else:
            row["ok"] = True
        p["out"].parent.mkdir(parents=True, exist_ok=True)
        im.save(p["out"])
        rep["plates"][p["key"]] = row

    by_group = {}
    for p in plates:
        by_group.setdefault(p["group"], []).append(p)
    for g, ps in by_group.items():
        grow = {"n": len(ps)}
        if g not in NO_BACKDROP:
            ls = [rep["plates"][p["key"]]["luma"] for p in ps]
            grow["luma_spread"] = round(max(ls) - min(ls), 1)
            grow["uniform"] = grow["luma_spread"] <= UNIFORMITY_TOL
        if len(ps) > 1 and g in ("turnaround", "face", "expressions", "poses"):
            pairs = distinct_pairs([p["out"] for p in ps])
            grow["closest"] = pairs[:3]
            grow["distinct"] = pairs[0][2] >= DISTINCT_MIN
            if not grow["distinct"]:
                a, b, _ = pairs[0]
                for p in ps:
                    if Path(p["out"]).stem in (a, b) and p["key"] not in rep["regenerate"]:
                        rep["regenerate"].append(p["key"])
        rep["groups"][g] = grow
        if grow.get("uniform") is False or grow.get("distinct") is False:
            rep["pass"] = False
    if rep["regenerate"]:
        rep["pass"] = False
    return rep


def print_report(rep):
    print(f"backdrop target luma: {rep['target_luma']}")
    print(f"{'plate':<28} {'group':<12} {'neut':>5} {'luma':>6}  ok")
    for k, r in rep["plates"].items():
        if "neutrality" in r:
            print(f"{k:<28} {r['group']:<12} {r['neutrality']:>5} {r['luma']:>6}  "
                  f"{'yes' if r['ok'] else 'NO  ' + r.get('why', '')}")
    for g, r in rep["groups"].items():
        extra = []
        if "luma_spread" in r:
            extra.append(f"luma spread {r['luma_spread']} ({'ok' if r['uniform'] else 'FAIL'})")
        if "closest" in r:
            a, b, d = r["closest"][0]
            extra.append(f"closest {a}~{b} {d} ({'ok' if r['distinct'] else 'FAIL'})")
        print(f"  group {g:<12} n={r['n']:<3} " + "; ".join(extra))
    print("QC:", "PASS" if rep["pass"] else f"FAIL  regenerate: {', '.join(rep['regenerate'])}")
