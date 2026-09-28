# Prompt-vs-compute: what a generative model will and won't obey

Hard-won division of labour. Every item below was verified across multiple attempts
with escalating prompt specificity, then solved (or abandoned) a different way.

**The governing rule: anything you can measure, COMPUTE. Prompts are for content;
arithmetic is for quantities.** Reaching for stronger prompt language on a
measurable property is the most common way to burn a session.

## Not promptable — move it to post-process

### Backdrop / background brightness

Stating `"exactly 50 percent grey, hex #808080, RGB 128 128 128 — not white, not
light grey"` in every call did **not** work. Measured border-luma spread across a
5-image set:

| Approach | Spread (0–255) |
|---|---|
| Single batched call | 64 |
| One call per image (better for other reasons) | **129.6 — worse** |

Per-item calls make brightness *worse*, because each call is an independent roll. So
fixing set-level consistency in one dimension can regress another — expect it.

**Fix in PIL, not in the prompt:**

1. Measure each image's border **median** luma (median, not mean — a subject's limb
   intruding into the border strip skews a mean badly, barely moves a median).
2. Apply a **gamma** correction onto one shared target. Not a flat additive offset:
   an offset fixes the backdrop while clipping the subject's highlights, whereas a
   gamma curve compresses instead of clipping and preserves tonal separation.
3. **Correct LUMA ONLY.** Applying the same gamma LUT to R, G and B independently
   amplifies any pre-existing channel imbalance. Verified regression: images passing
   a colour-neutrality check at 6.2 came back at **12.6 (FAIL)** after an
   all-channel correction, and one image's distinctness metric crashed from ~13 to
   **2.77** — i.e. the "fix" flattened two images toward each other. Convert to
   **YCbCr, curve Y, leave Cb/Cr untouched, recombine.** The same set then passed
   everything.
4. **Re-measure and triage.** Gamma cannot rescue an image shot on a fundamentally
   different backdrop — one at luma 46 in a set whose median was 223 only reached 166
   while washing out the subject. Correct, re-measure, and treat anything still
   outside tolerance as **must-regenerate**, not correctable. Typical outcome on a
   5-image set: 4 correct cleanly, 1 needs a re-roll.

Empirical triage ("correct then verify") beats a heuristic threshold — an earlier
ratio-based guess misclassified images that gamma actually handled fine.

**Keep raw originals in a `_raw/` sibling directory.** When a post-process turns out
to be buggy you need untouched sources to re-run from; regenerating to recover from
your own bug is pure waste. This directly saved a set during the luma-only fix.

## Not promptable — drop the requirement

### Intermediate camera angles (three-quarter / 45°)

Verified across **three generations and two subjects**, escalating through: degrees
→ shoulder-line percentage → explicit both-eyes-visible plus anti-head-turn language
→ one API call per angle.

| Requested slot | Outcome, every attempt |
|---|---|
| front | **PASS** |
| profile (90°) | **PASS** |
| back (180°) | **PASS** |
| three-quarter left (45°) | over-rotates toward profile |
| three-quarter right (45°) | under-rotates toward front |

The failure is a **skewed ladder, not a collapse**: `front` vs `tq_right` was the
*closest* pair in the set (delta 8.58) while `tq_left` vs `profile` sat mid-pack.
Both 45° slots miss, in opposite directions.

**Decision: ship front + profile + back, drop the 45s.** Three attempts is enough
evidence. Revisit only with a model offering explicit camera control or a
novel-view-synthesis step — not with more prompt language.

For reference-lock use, a *wrong* intermediate angle is worse than a missing one: it
teaches the downstream video model an identity at an angle the subject never holds.

## Promptable — but only with the right phrasing

### Negate the rendered FEATURE, not its attributes

Asking for "grief and exhaustion" produced purple-mauve eye rings and tear streaks
reading as bruising. Negating the *colour* — "no purple, use subtle grey shadow
instead" — still produced rings, just greyer.

What worked was redirecting the **mechanism**: convey exhaustion through
"SLACK MOUTH, HEAVY UPPER EYELIDS, loose jaw", require under-eye skin "CLEAN and
EVEN, the same tone as the cheeks", and add explicit no-rings / no-sunken-sockets /
no-tears clauses.

Generalisation: if a model keeps rendering an unwanted feature, don't constrain the
feature's properties — remove the feature and supply a different mechanism for the
same intent.

### Describe physical muscle action, not emotion labels

"Neutral but guarded" reliably yielded placid and blank. Dropping the word *neutral*
entirely and specifying only physical action worked: "lower eyelids tightened and
slightly raised, jaw clenched, lips pressed into a flat closed line, chin slightly
lifted — sizing up the person in front of them and deciding what not to say."

Same for fear ("wide eyes, sclera visible above the iris, inner brow ends pulled up,
jaw dropped, neck tendons tensed") and cold anger ("brows down and together with a
deep vertical crease, narrowed hard stare, tight downturned closed mouth, nostrils
slightly flared — no open mouth, no bared teeth").

### Anchor identity attributes to the reference, not to a number

"Late 50s" consistently rendered as late 60s–70s. What works: "must look the SAME AGE
as the reference image and no older. Do not add wrinkles, do not deepen lines, do not
age the face. Keep skin texture identical to the reference."

Same pattern for wardrobe drift mid-set: "costume collar and garment IDENTICAL to the
reference image" fixes it reliably.

### Style/grade must NOT go on a reference plate

A cinematic grade in the prompt for a *reference* image bakes coloured light into the
plate. If subsequent images are generated i2i from that anchor, the cast propagates
through the whole set, and a downstream video model inherits the coloured light
instead of the subject's neutral **albedo**. Verified failure: amber gradient with
teal pooling plus directional shadow across an entire reference set, measured at
30.1 channel spread, dropping to 0.7 once the grade was removed from the anchor.

Reference plates get an explicit negative block:

```
"Neutral mid-grey (#808080) seamless studio backdrop, completely flat and even
 white-balanced lighting from the front, no coloured gels, no warm amber cast,
 no teal or cyan cast, no directional shadows, no vignette, no film grain,
 no cinematic colour grading. Clean technical reference plate lighting only."
```

Apply the style/grade on the **final output** prompt instead. Images intended to
become real frames in the finished piece are the exception — those *should* carry it.

### Other phrasings that matter for multi-image work

- **"no collage, each image separate, NOT a grid of panels"** — otherwise you get
  grid panels inside a single image.
- **"THIS EXACT PERSON from the reference image"**, then enumerate what must not
  change: face, hair, build, costume, footwear.
- **"eyes look DIRECTLY INTO THE CAMERA LENS, no downcast, no averted gaze"** — fixes
  averted-gaze plates on the first try.
- For empty locations, **"no people, no figures"** must be stated or figures leak in.

## Objective QC gates before any vision review

Cheap arithmetic catches most defects and costs ~1 second; a vision subagent costs
minutes and can exhaust its budget. Gate first, then review.

| Check | What it catches | Good | Failing (observed) |
|---|---|---|---|
| colour neutrality | grade baked into a reference plate | channel spread 0.7–3.0 | 17.9–30.1 |
| set uniformity | images from different-brightness studios | luma spread < 20 | 88–130 |
| pairwise distinctness | literal near-duplicate images | min delta 6.5–30.7 | < 6 |

Two lessons about the metrics themselves:

**Ask what a metric does NOT measure.** A neutrality check measuring colour cast
*within* each image passed every image in a set whose border lumas were
`[137, 232, 226, 238, 239]` — a 102/255 brightness spread. The numbers were in the
output the whole time, unchecked, and two vision reviews independently flagged what
the metric had ignored. Add the complementary check.

**Scope each metric to the artifact it governs.** A uniformity rule that is correct
for reference plates is wrong for scene/location images, where different angles
*should* differ in exposure. Enforcing it there flagged a legitimate 44-luma spread
as a failure. Provide a `--graded` style flag rather than one universal rule.

**Distinctness is not semantic.** It measures pixel difference. A profile and a
head-turned profile differ substantially in pixels while being the same angle class —
a set with two wrong angles passed at min delta 6.54. Only vision review can confirm
a semantic ladder.

**When vision reports and pixel data disagree, check the pair matrix before acting on
either.** Two subagents reported "collapsed into duplicate profiles"; the pairwise
distances showed a skewed ladder instead, which implied a different fix.

## Suspect your own fix

Twice in one session a new failure appeared in the same step as a fix, and the fix was
the cause: the all-channel gamma correction flattened two images toward each other
(read initially as a content failure), and per-item calls regressed backdrop
uniformity while fixing set contrast. **When a fix and a new failure appear together,
suspect the fix first** — and keep `_raw/` originals so you can prove it cheaply.
