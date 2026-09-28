"""Objective QC for generated reference plates — no vision model needed.

Three checks that arithmetic answers exactly and a vision model answers slowly,
expensively, and sometimes wrongly. Run this BEFORE spending any vision-review
budget, and before promoting a reference set into an expensive video stage.

  neutrality    is a cinematic grade baked into an identity lock? Measures
                per-channel RGB means on the border region (backdrop, not
                subject) and reports max channel spread plus cast direction.
  uniformity    do all plates in a set share ONE backdrop brightness? Compares
                border median luma ACROSS the set. Exists because neutrality
                alone gives false confidence: it checks cast *within* an image
                and passed a set whose brightness varied by 102/255.
  distinctness  are the N plates actually N different frames? Mean absolute
                difference of downsampled grayscale, flagging near-duplicates.

Measured thresholds from real runs:

  neutral plate        channel spread   0.7 -  3.0
  graded plate         channel spread  17.9 - 30.1   <- identity-lock failure
  uniform set          luma spread      6.8 - 13.7
  mixed-studio set     luma spread     88   - 129    <- needs normalize.py
  distinct plates      min delta        6.9 - 30.7
  literal duplicates   min delta        < 6

LIMITATION: distinctness measures pixels, not semantics. It CANNOT verify that
five plates show five different camera angles — a profile and a head-turned
profile differ substantially in pixels while being the same angle class. Verified
false negative: a set with two ~90-degree profiles in place of the requested
45-degree three-quarters passed at min delta 6.54. Use vision review for angle
ladders and expression semantics; use this for everything quantitative.

Usage:
  python qc.py assets/character/name              # identity locks: all checks
  python qc.py assets/plates/location --graded    # location plates keep the grade
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("pip install pillow")


def border_rgb(p: Path, frac: float = 0.10) -> tuple[float, float, float]:
    """Mean RGB of the outer frame — backdrop, not subject."""
    im = Image.open(p).convert("RGB")
    w, h = im.size
    bw, bh = max(1, int(w * frac)), max(1, int(h * frac))
    strips = [
        im.crop((0, 0, w, bh)),           # top
        im.crop((0, h - bh, w, h)),       # bottom
        im.crop((0, 0, bw, h)),           # left
        im.crop((w - bw, 0, w, h)),       # right
    ]
    tot, n = [0.0, 0.0, 0.0], 0
    for s in strips:
        px = list(s.getdata())
        n += len(px)
        for r, g, b in px:
            tot[0] += r
            tot[1] += g
            tot[2] += b
    return tuple(v / n for v in tot)


def neutrality(paths: list[Path], tol: float = 12.0) -> dict:
    """A neutral plate has near-identical R, G and B in the border.

    A baked-in grade shows up as channel spread: warm amber lifts R, teal/cyan
    lifts B and G. Tolerance ~12/255 is generous; a graded plate lands 18-60.
    """
    rows, worst = [], 0.0
    for p in paths:
        r, g, b = border_rgb(p)
        spread = max(r, g, b) - min(r, g, b)
        worst = max(worst, spread)
        cast = ("warm/amber" if r == max(r, g, b) else
                "cool/teal" if b == max(r, g, b) else "green")
        rows.append({"file": p.name, "rgb": (round(r), round(g), round(b)),
                     "spread": round(spread, 1),
                     "cast": cast if spread > tol else "neutral",
                     "pass": spread <= tol})
    return {"rows": rows, "worst_spread": round(worst, 1),
            "pass": worst <= tol, "tolerance": tol}


def uniformity(paths: list[Path], tol: float = 20.0) -> dict:
    """Do all plates in a set share ONE backdrop brightness?

    `neutrality` checks colour cast WITHIN each image; it says nothing about
    whether plate 3 is a white studio and plate 4 is mid-grey. Observed miss:
    border luma [137, 232, 226, 238, 239] -> spread 102/255, which passed
    neutrality cleanly on every image. A video model fed that set inherits
    inconsistent lighting cues instead of reading albedo.
    """
    lumas = []
    for p in paths:
        r, g, b = border_rgb(p)
        lumas.append((p.name, 0.299 * r + 0.587 * g + 0.114 * b))
    vals = [v for _, v in lumas]
    spread = max(vals) - min(vals)
    return {"rows": [{"file": n, "luma": round(v, 1)} for n, v in lumas],
            "spread": round(spread, 1), "pass": spread <= tol,
            "tolerance": tol,
            "darkest": min(lumas, key=lambda x: x[1])[0],
            "brightest": max(lumas, key=lambda x: x[1])[0]}


def distinctness(paths: list[Path], size: int = 48, tol: float = 6.0) -> dict:
    """Mean absolute pixel difference between downsampled grayscale frames.

    NOT an angle-correctness check — see the module docstring. This catches
    literal near-duplicates only. Note that adjacent turnaround angles of a
    static subject on a flat backdrop are genuinely similar, so a body set can
    legitimately pass at ~7 while an expression set sits at ~28. Keep the
    tolerance tight and inspect marginal passes rather than loosening it.

    The returned `closest` pair matrix is diagnostically valuable in its own
    right: when a vision review says "two plates collapsed", the pair distances
    reveal whether that is true or whether the set is skewed some other way.
    """
    thumbs = {}
    for p in paths:
        im = Image.open(p).convert("L").resize((size, size), Image.LANCZOS)
        thumbs[p.name] = list(im.convert("L").tobytes())

    names = list(thumbs)
    pairs = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = thumbs[names[i]], thumbs[names[j]]
            d = sum(abs(x - y) for x, y in zip(a, b)) / len(a)
            pairs.append({"a": names[i], "b": names[j], "delta": round(d, 2),
                          "suspect": d < tol})
    pairs.sort(key=lambda x: x["delta"])
    return {"closest": pairs[:5], "min_delta": pairs[0]["delta"] if pairs else None,
            "suspects": [p for p in pairs if p["suspect"]],
            "pass": not any(p["suspect"] for p in pairs), "tolerance": tol}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--graded", action="store_true",
                    help="location plates: skip neutrality AND uniformity")
    a = ap.parse_args()
    d = Path(a.dir)

    groups = {
        "body": sorted(d.glob("body_*.png")),
        "face": sorted(d.glob("face_*.png")),
        "plate": sorted(d.glob("plate_*.png")),
        "anchor": sorted(d.glob("anchor_*.png")),
    }
    groups = {k: v for k, v in groups.items() if v}
    if not groups:
        sys.exit(f"no reference images found in {d}")

    ok = True
    for name, paths in groups.items():
        print(f"\n=== {name}  ({len(paths)} images)")

        if not a.graded:
            n = neutrality(paths)
            print(f"  neutrality: {'PASS' if n['pass'] else 'FAIL'}  "
                  f"worst channel spread {n['worst_spread']} (tol {n['tolerance']})")
            for r in n["rows"]:
                flag = "  " if r["pass"] else "<-"
                print(f"    {flag} {r['file']:16s} rgb={r['rgb']} "
                      f"spread={r['spread']:5.1f} {r['cast']}")
            ok &= n["pass"]

        # Uniformity is an IDENTITY-LOCK rule, not a universal one. Locks must
        # share one studio so the video model reads albedo rather than lighting.
        # Location plates are the opposite case: a low-angle interior and a
        # high-angle exterior of the same place SHOULD differ in exposure,
        # because they become real first-frames carrying the grade. Enforcing
        # uniformity on them flagged a legitimate 44-luma spread as a failure.
        # Scope every metric to the artifact it actually governs.
        if len(paths) > 1 and not a.graded:
            u = uniformity(paths)
            print(f"  uniformity: {'PASS' if u['pass'] else 'FAIL'}  "
                  f"backdrop luma spread {u['spread']} (tol {u['tolerance']})")
            if not u["pass"]:
                print(f"    <- darkest {u['darkest']} vs brightest {u['brightest']}")
                print(f"       {[r['luma'] for r in u['rows']]}")
            ok &= u["pass"]

        if len(paths) > 1:
            s = distinctness(paths)
            print(f"  distinctness: {'PASS' if s['pass'] else 'FAIL'}  "
                  f"min delta {s['min_delta']} (tol {s['tolerance']})"
                  "  [near-duplicates only; NOT angle correctness]")
            for p in s["closest"][:3]:
                flag = "<-" if p["suspect"] else "  "
                print(f"    {flag} {p['a']} vs {p['b']}: {p['delta']}")
            ok &= s["pass"]

    print(f"\n{'ALL CHECKS PASS' if ok else 'CHECKS FAILED — do not promote this set'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
