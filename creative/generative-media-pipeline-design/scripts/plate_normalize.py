"""Backdrop normalization for reference plates — fix brightness in post.

Reference plates come from separate generation calls, and each call picks its own
backdrop brightness no matter how precisely the prompt pins a value. Measured:
"exactly 50 percent grey, hex #808080, RGB 128 128 128" stated verbatim in every
prompt still produced a border-luma spread of 129.6/255 across one 5-image set.
Splitting into per-item calls (which fixes other problems) makes this one WORSE,
because each call is an independent roll.

Prompting is the wrong tool for a measurable, computable quantity. Compute it:
estimate each plate's backdrop, apply a smooth correction onto one shared target,
and flag whatever refuses to land as a must-regenerate outlier.

Pair with plate_qc.py: normalize until `uniformity` passes clean.

Usage:
  python plate_normalize.py assets/character/name --dry-run
  python plate_normalize.py assets/character/name
  python plate_normalize.py assets/character/name --target 200
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("pip install pillow")


def backdrop_luma(im: Image.Image, frac: float = 0.10) -> float:
    """Median luma of the border region — backdrop, not subject.

    Median rather than mean: a subject's hair or a limb intruding into the
    border strip skews a mean badly but barely moves a median.
    """
    g = im.convert("L")
    w, h = g.size
    bw, bh = max(1, int(w * frac)), max(1, int(h * frac))
    vals: list[int] = []
    for box in ((0, 0, w, bh), (0, h - bh, w, h),
                (0, 0, bw, h), (w - bw, 0, w, h)):
        vals.extend(g.crop(box).getdata())
    vals.sort()
    return float(vals[len(vals) // 2])


def normalize(im: Image.Image, target: float, frac: float = 0.10) -> Image.Image:
    """Shift the plate so its backdrop sits at `target`.

    Gamma-style correction, not a flat additive offset: an additive shift fixes
    the backdrop while clipping the subject's highlights, whereas a gamma curve
    compresses rather than clips, so faces and costume keep tonal separation.

    LUMA ONLY. Applying the same gamma LUT to R, G and B independently amplifies
    whatever channel imbalance already existed — verified regression: plates
    passing a neutrality check at 6.2 came back at 12.6 (FAIL) after an
    all-channel correction, and one plate's distinctness crashed to 2.77 because
    the correction flattened two plates toward each other. That was initially
    misdiagnosed as a content failure. When a fix and a new failure appear in the
    same step, suspect the fix.

    Brightness and colour cast are separate properties and must be corrected
    separately: convert to YCbCr, curve Y, leave the chroma planes untouched.
    """
    src = backdrop_luma(im, frac)
    if src <= 0 or abs(src - target) < 1.0:
        return im

    import math
    s, t = src / 255.0, target / 255.0
    s = min(max(s, 1e-3), 1 - 1e-3)
    t = min(max(t, 1e-3), 1 - 1e-3)
    g = math.log(t) / math.log(s)
    g = min(max(g, 0.25), 4.0)  # sanity clamp

    lut = [min(255, max(0, int(round(255.0 * ((i / 255.0) ** g)))))
           for i in range(256)]

    if im.mode != "RGB":
        im = im.convert("RGB")
    y, cb, cr = im.convert("YCbCr").split()
    y = y.point(lut)
    return Image.merge("YCbCr", (y, cb, cr)).convert("RGB")


TOL = 20.0  # match the uniformity tolerance in plate_qc.py


def triage(lumas: dict, target: float, tol: float = TOL) -> tuple[list, list]:
    """Correct, then MEASURE. Flag whatever refuses to land.

    An earlier version guessed with a ratio threshold and misclassified plates
    that gamma actually handled fine. Empirical is better and simpler: apply the
    correction, re-measure the result, and treat any plate that still misses
    tolerance as a must-regenerate outlier.

    Gamma handles moderate drift but cannot rescue a plate shot on a
    fundamentally different backdrop — observed luma 46 in a set whose median was
    223, which gamma lifts only to 166 while washing out the subject.

    Typical outcome on a 5-plate set: 4 correct cleanly, 1 needs regeneration.
    """
    fix, regen = [], []
    for pth, v in lumas.items():
        landed = backdrop_luma(normalize(Image.open(pth), target))
        (fix if abs(landed - target) <= tol else regen).append(pth)
    return fix, regen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--target", type=float, default=None,
                    help="target backdrop luma; default = median across the set")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    a = ap.parse_args()

    d = Path(a.dir)
    groups = {
        "body": sorted(d.glob("body_*.png")),
        "face": sorted(d.glob("face_*.png")),
        "plate": sorted(d.glob("plate_*.png")),
    }
    groups = {k: v for k, v in groups.items() if v}
    if not groups:
        sys.exit(f"no plates found in {d}")

    for name, paths in groups.items():
        lumas = {p: backdrop_luma(Image.open(p)) for p in paths}
        vals = sorted(lumas.values())
        # Median target: no single plate has to move very far, versus anchoring
        # on an arbitrary value that drags the whole set.
        target = a.target if a.target is not None else vals[len(vals) // 2]
        spread_before = max(vals) - min(vals)

        print(f"\n=== {name}  ({len(paths)} plates)  target luma {target:.0f}")
        print(f"  spread before: {spread_before:.1f}")

        fix, regen = triage(lumas, target)
        if regen:
            print(f"  OUTLIERS (regenerate, do not correct): "
                  f"{[p.name for p in regen]}")
            for p in regen:
                landed = backdrop_luma(normalize(Image.open(p), target))
                print(f"    {p.name:16s} luma {lumas[p]:6.1f} -> best {landed:6.1f} "
                      f"vs target {target:.0f} — uncorrectable, regenerate")

        after = []
        for p in fix:
            src = lumas[p]
            out = normalize(Image.open(p), target)
            new_l = backdrop_luma(out)
            after.append(new_l)
            print(f"    {p.name:16s} {src:6.1f} -> {new_l:6.1f}")
            if not a.dry_run:
                # Keep untouched originals. Recovering from a buggy correction by
                # regenerating is pure waste — and corrections DO turn out buggy.
                if not a.no_backup:
                    bak = p.parent / "_raw"
                    bak.mkdir(exist_ok=True)
                    if not (bak / p.name).exists():
                        shutil.copy(p, bak / p.name)
                out.save(p)

        if after:
            sp = max(after) - min(after)
            print(f"  spread after (corrected plates): {sp:.1f}  "
                  f"{'PASS' if sp <= TOL else 'STILL FAILING'}")
        if regen:
            print(f"  SET NOT PROMOTABLE — regenerate {len(regen)} outlier(s) first")

    if a.dry_run:
        print("\n(dry run — nothing written)")


if __name__ == "__main__":
    main()
