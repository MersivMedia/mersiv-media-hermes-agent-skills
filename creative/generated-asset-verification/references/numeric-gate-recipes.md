# Numeric gate recipes

Implementable estimators for verifying generated asset sets, with pass/fail values
measured on real sets. Pure stdlib + PIL — no vision model, no GPU.

Run these BEFORE spending any vision-subagent budget. A vision subagent took ~400s to
report a colour cast one of these measured exactly in under a second.

## Shared estimator: border sampling

Reference plates put the subject centre-frame, so the **border region is the
backdrop**. Sample it and you measure lighting without the subject contaminating the
result.

```python
def border_rgb(path, frac=0.10):
    """MEDIAN RGB of the outer frame — backdrop, not subject."""
    im = Image.open(path).convert("RGB")
    w, h = im.size
    bw, bh = max(1, int(w * frac)), max(1, int(h * frac))
    px = []
    for box in ((0, 0, w, bh), (0, h - bh, w, h),
                (0, 0, bw, h), (w - bw, 0, w, h)):
        px.extend(im.crop(box).getdata())
    m = len(px) // 2
    return (float(sorted(q[0] for q in px)[m]),
            float(sorted(q[1] for q in px)[m]),
            float(sorted(q[2] for q in px)[m]))
```

**MEDIAN, not mean.** A subject's hair or limb intruding into the border strip skews a
mean badly and barely moves a median. This matters beyond accuracy: a normalizer that
optimised the median while the grader graded the mean reported `PASS 2.0` on a set the
grader failed at `52.4`. **Fixer and grader must share the estimator.**

## Gate 1 — neutrality (per image)

Catches a colour cast baked into a reference plate: a cinematic grade in the prompt,
or wardrobe colour bleeding into the backdrop.

```python
r, g, b = border_rgb(path)
spread = max(r, g, b) - min(r, g, b)
cast = ("warm/amber" if r == max(r, g, b)
        else "cool/teal" if b == max(r, g, b) else "green")
ok = spread <= 12.0
```

Measured: neutral plates land **0.7–6.0**. Failures land **17.9–31.0**, and the cast
direction is diagnostic — a TAN-KHAKI wardrobe produced warm/amber 16–24, OLIVE-GREEN
produced cool/teal 20–31.

## Gate 2 — uniformity (across a set)

**This gate exists because neutrality alone gives false confidence.** Neutrality
measures cast *within* an image and says nothing about brightness *between* images.

Real miss: border lumas `[137, 232, 226, 238, 239]` — a **102/255 spread**, a mix of
white and mid-grey studios — passed neutrality on every single image.

```python
lumas = [0.299*r + 0.587*g + 0.114*b for r, g, b in map(border_rgb, paths)]
spread = max(lumas) - min(lumas)
ok = spread <= 20.0
```

Measured: good sets **0.4–19**. Failures **52–130**.

**Scope it.** Uniformity is correct for identity plates (they must share one studio so
the consumer reads albedo, not lighting) and **wrong** for location plates, where a
low-angle interior and a high-angle exterior of the same place *should* differ in
exposure. Provide a `--graded` flag that skips neutrality and uniformity for those.

## Gate 3 — distinctness (across a set)

Catches literal near-duplicate frames.

```python
def distinctness(paths, size=48):
    thumbs = {p.name: list(Image.open(p).convert("L")
                           .resize((size, size), Image.LANCZOS).tobytes())
              for p in paths}
    names, pairs = list(thumbs), []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = thumbs[names[i]], thumbs[names[j]]
            d = sum(abs(x - y) for x, y in zip(a, b)) / len(a)
            pairs.append((names[i], names[j], round(d, 2)))
    pairs.sort(key=lambda x: x[2])
    return pairs            # closest first
```

Measured: healthy sets have min delta **7–30**. Below **6** means duplicates.

**It does NOT check semantic correctness.** A body set with two ~90° profiles instead
of the requested 45° three-quarters passed at min delta **6.54**. Only vision review
can confirm a *ladder*.

**Always print the closest PAIRS, not just the minimum.** When two vision subagents
reported "collapsed into duplicate profiles", the matrix showed the closest pair was
actually `front` vs `three-quarter-right` (8.58) while `tq_left` vs `profile` sat
mid-pack — a *skewed* ladder, not a collapse. Different diagnosis, different fix.
**When vision and pixel data disagree, read the pair matrix before acting.**

## Gate 4 — conformance (authored colour canon)

Asserts a garment/object actually matches the **authored** spec. This gate is
worthless without authored ground truth — see the parent skill's rule 1.

```python
COSTUME_HUES = {
    "tan": (25, 55), "khaki": (25, 55), "olive": (45, 90), "brown": (10, 40),
    "cream": (30, 60), "green": (60, 160), "blue": (180, 260), "red": (340, 20),
    "grey": None, "gray": None, "charcoal": None, "black": None, "white": None,
}

# torso band: middle 20% horizontally, 30-50% vertically
crop = im.crop((int(w*.40), int(h*.30), int(w*.60), int(h*.50)))
# mean RGB -> colorsys.rgb_to_hls -> (hue_deg, lum, sat)
ok = (sat < 0.12 or hue_in_any_declared_range) and lum <= 0.80
```

Neutral words (grey/black/white) map to `None` and are skipped — hue is meaningless at
low saturation.

**Luminance is the honest discriminator, not saturation.** A first version used
hue + saturation and *passed* a WHITE coverall against canon that said TAN-KHAKI,
because HLS saturation stays deceptively high for near-white pixels. That plate
shipped into a paid video render. Measured:

| | RGB | hue | sat | lum | verdict |
|---|---|---|---|---|---|
| no canon (invented white) | (247,244,228) | 50 | 0.54 | **0.93** | FAIL washed out |
| with canon (tan) | (170,139,100) | 33 | 0.29 | **0.53** | PASS |

A tan or olive garment cannot sit above luminance 0.80.

## Correction: white balance then luma

Order matters — correcting brightness on a cast image bakes the cast in at the new
level.

```python
def white_balance(im, frac=0.10, tol=6.0):
    """Grey-world using the KNOWN-NEUTRAL backdrop as the target."""
    r, g, b = border_median_rgb(im, frac)
    if max(r, g, b) - min(r, g, b) <= tol:
        return im
    target = (r + g + b) / 3.0
    luts = [[min(255, max(0, int(round(i * (target / max(ch, 1.0))))))
             for i in range(256)] for ch in (r, g, b)]
    rr, gg, bb = im.convert("RGB").split()
    return Image.merge("RGB", (rr.point(luts[0]), gg.point(luts[1]),
                               bb.point(luts[2])))
```

Legitimate because the backdrop *should* be neutral, so per-channel gains that force
border R=G=B are a principled white balance rather than a guess. Applied to the whole
frame it also corrects the cast on the subject.

```python
def normalize_luma(im, target, frac=0.10):
    """Gamma onto a shared backdrop target. LUMA ONLY."""
    src = backdrop_luma(im, frac)
    if src <= 0 or abs(src - target) < 1.0:
        return im
    s = min(max(src / 255.0, 1e-3), 1 - 1e-3)
    t = min(max(target / 255.0, 1e-3), 1 - 1e-3)
    g = min(max(math.log(t) / math.log(s), 0.25), 4.0)
    lut = [min(255, max(0, int(round(255.0 * ((i / 255.0) ** g)))))
           for i in range(256)]
    y, cb, cr = im.convert("YCbCr").split()
    return Image.merge("YCbCr", (y.point(lut), cb, cr)).convert("RGB")
```

Two non-obvious requirements:

- **Gamma, not a flat offset.** An additive shift fixes the backdrop while clipping
  the subject's highlights; gamma compresses instead.
- **LUMA ONLY.** Applying the same LUT to R, G and B independently *amplifies* any
  existing channel imbalance. Verified regression: plates passing neutrality at 6.2
  came back at **12.6 (FAIL)** after an all-channel correction, and one plate's
  distinctness crashed to **2.71** — which was then misdiagnosed as an emotion
  collapse. Convert to YCbCr, curve Y, leave Cb/Cr alone.

Pick the target as the **median** of the set's backdrop lumas, so no single plate has
to move far.

## Triage: correct, re-measure, then regenerate

Correction cannot rescue an image whose backdrop is fundamentally a different studio.

```python
def triage(paths, target, tol=20.0):
    """Apply the correction, MEASURE the result, flag what refuses to land."""
    fix, regen = [], []
    for p in paths:
        landed = backdrop_luma(normalize_luma(white_balance(Image.open(p)), target))
        (fix if abs(landed - target) <= tol else regen).append(p)
    return fix, regen
```

Empirical triage beats a heuristic threshold — an earlier ratio-based guess
misclassified plates that gamma actually handled fine. Measured example: a plate at
luma 46 against a set median of 223 only reached 166, washing out the subject on the
way, and was correctly flagged must-regenerate. Typical outcome on a 5-plate set: 4
correct cleanly to under 20 spread, 1 needs a re-roll.

## Coverage: the fixer must process everything the gate grades

Anchor images were graded by the QC gate but excluded from the normalizer's file
globs. An uncorrected anchor then failed a set whose every derived plate passed —
a failure nobody could act on. Enumerate the same artifact classes in both tools.

## Backups: version by content hash

A flat `_raw/` directory plus a blanket "restore the originals" silently reinstated
older-generation plates over freshly generated, verified ones. The only signal was a
conformance failure afterwards.

```python
h = hashlib.sha1(p.read_bytes()).hexdigest()[:8]
shutil.copy(p, p.parent / "_raw" / f"{p.stem}.{h}{p.suffix}")
```

A restore then cannot cross generations. And **quarantine rather than delete** —
`mv` to `_quarantine/` beats `rm -rf` on assets you paid for.

## Suggested CLI shape

```
qc.py <dir>                 # neutrality + uniformity + distinctness
qc.py <dir> --costume "..."  # + conformance against authored canon
qc.py <dir> --graded         # location plates: skip neutrality + uniformity
normalize.py <dir> --dry-run # show corrections and outliers, write nothing
normalize.py <dir>           # apply, hash-backup originals
```

Exit non-zero on failure so the pipeline can gate on it. Print per-file numbers, not
just a verdict — the numbers are what let you spot a metric's blind spot.
