---
name: generated-asset-verification
description: "Verify AI-generated images and video before shipping."
version: 1.0.0
author: Nous Research
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [image-generation, video-generation, quality-control, verification, character-consistency, vision-subagents, replicate, fal]
    related_skills: [replicate-api-generation, comfyui, branching-ai-film-engine]
    category: creative
---

# Generated Asset Verification

You cannot see images or video. Generated assets **look** plausible while being
subtly, expensively wrong — and the wrongness propagates: a bad reference plate
teaches a video model the wrong identity, and you discover it three paid renders
later.

This skill is the discipline for catching that. It is provider-agnostic and applies
to any pipeline that generates visual assets and then consumes them downstream.

## When to Use

- Generating reference/identity assets (character sheets, product plates, style
  references) that other generations will consume
- Any multi-image *set* where the images must relate to each other — distinct angles,
  distinct expressions, matched lighting
- Before spending on a video render conditioned on generated images
- Reviewing AI-generated video for drift, continuity, or content accuracy
- Any time you are about to trust "the model said it succeeded"

## Linked references

- `references/provider-api-traps.md` — concrete API-level failure modes with fixes
  (endpoint id shapes, phantom parameters after a provider port, reference-asset
  citation, audio ordering for lip-sync, payload size limits).
- `references/numeric-gate-recipes.md` — implementable estimators for neutrality,
  set uniformity, distinctness, and costume/colour conformance, with measured
  pass/fail values.

## 1. Authored ground truth comes FIRST

**If you cannot state the ground truth, you cannot detect drift.** This is the
foundational rule and the most expensive one to learn.

A real failure chain: a character pipeline had no `costume` field, so prompts sent
only name and role and the model invented clothing per call. Reference plates came
back with a near-white garment, `rgb(244,242,234)`. A verification subagent was then
asked to audit those plates against "tan coverall, brown boots" — **a specification
the reviewing agent had invented itself**, back-derived from an earlier report and
then treated as canon. So drift was being measured against a target that never
existed, and the wrong plates shipped into a paid render.

Rules:

- Every property you intend to QC must exist as **authored data** in a spec file, not
  in an agent's head or in prose scattered through a conversation.
- Inject it **verbatim** into every generation prompt in the chain.
- When you write a verification brief for a subagent, quote the authored spec and say
  where it came from. If you cannot cite it, do not assert it.

Verified effect of adding authored costume canon: garment went from `rgb(244,242,234)`
luminance 0.93 (white) to `rgb(170,139,100)` hue 33 luminance 0.53 (tan, as
specified).

## 2. Numeric gates BEFORE vision review

**Make numerical everything that can be numerical.** Vision review is for judgements
arithmetic cannot make — "does this expression read as grief". It is the wrong tool
for anything a histogram answers exactly.

Measured comparison on the same defect: a vision subagent spent **~400 seconds** to
report a colour cast that a border-region histogram measured exactly in **under a
second**, and the subagent's run truncated before it could check 7 of 10 files.

So the order is always:

```
1. numeric gates    cheap, exact, deterministic   -> blocks promotion
2. vision review    expensive, judgement-only     -> only on sets that already pass
```

Gate categories worth implementing (recipes in
`references/numeric-gate-recipes.md`):

| Gate | Catches | Typical good | Typical fail |
|---|---|---|---|
| neutrality | colour cast baked into a reference plate | spread 0.7–6 | 18–31 |
| uniformity | plates shot in different-brightness "studios" | luma spread <20 | 52–130 |
| distinctness | literal near-duplicate frames | min delta 7–30 | <6 |
| conformance | garment/colour ignoring authored canon | hue in range, lum <0.80 | lum 0.93 |

## 3. Four ways your own gates will lie to you

Hard-won. Every one of these shipped a bad set that a gate had passed.

### 3.1 A metric's blind spot is its real danger

`neutrality` measured colour cast *within* each image and said nothing about
brightness *across* the set. Border lumas `[137, 232, 226, 238, 239]` — a **102/255
spread**, a mix of white and mid-grey studios — passed neutrality on every single
image. The numbers were sitting in the QC output unchecked while two independent
vision reviews flagged it by eye.

**When you write a metric, immediately ask what it does NOT measure**, and add the
complementary gate.

### 3.2 Two tools must not measure the same property differently

A normalizer optimised the **median** border luma while the grader graded the
**mean**. The normalizer reported `PASS 2.0` on a set the grader failed at `52.4`.
Neither was buggy in isolation; they simply disagreed about what "backdrop
brightness" means.

Unify the estimator across fixer and grader. Prefer **median** — a subject's limb or
hair intruding into the sampled border skews a mean badly and barely moves a median.

### 3.3 Anything a gate grades, the fixer must process

Anchor images were graded by the QC gate but excluded from the normalizer's file
globs. Result: an uncorrected anchor failed the whole set while every derived plate
passed. Coverage mismatch between gate and fixer produces failures nobody can act on.

### 3.4 Pixel difference is not semantics

A distinctness gate measures pixel distance, **not meaning**. Two images can differ
substantially in pixels while being the same *class* of thing. Verified false
negative: a body set where two slots were both ~90° profiles instead of the requested
45° three-quarters **passed at min delta 6.54**.

Corollary — **when a vision report and pixel data disagree, check the pair-distance
matrix before acting on either.** Two subagents described a set as "collapsed into
duplicate profiles"; the matrix showed the closest pair was actually `front` vs
`three-quarter-right` (8.58), which meant a *skewed ladder*, not a collapse. Different
diagnosis, different fix.

### 3.5 Scope each metric to the artifact it governs

A uniformity rule that is correct for identity plates (they must share one studio so
the model reads albedo, not lighting) is **wrong** for location plates — a low-angle
interior and a high-angle exterior of the same place *should* differ in exposure,
because they become real graded frames. Running it there flagged a legitimate 44-luma
spread as a failure. Add a `--graded` style flag rather than one universal rule.

## 4. Compute it, don't prompt for it

**Prompts are for content; arithmetic is for quantities.** If a property is
measurable, correct it in post rather than asking the model again.

Case study — backdrop brightness. With `#808080, RGB 128 128 128` stated verbatim in
every prompt:

| Approach | Border-luma spread |
|---|---|
| single batched call | 64 |
| one call per item | **129.6 — worse** |

Per-item calls make it worse because each call is an independent roll. Three rounds of
escalating prompt specificity did not fix it. A post-process did, in one pass.

### Correction order and channel discipline

```
1. white balance (chroma)   grey-world, using the known-neutral backdrop as target
2. luma normalize           gamma onto one shared target, LUMA ONLY
3. re-measure and triage    anything still out of tolerance -> REGENERATE
```

- **Chroma before luma.** Correcting brightness on a cast image bakes the cast in at
  the new level.
- **Luma only.** Applying the same gamma LUT to R, G and B independently *amplifies*
  whatever channel imbalance existed. Verified regression: plates passing neutrality
  at 6.2 came back at **12.6 (FAIL)** after an all-channel correction, and one plate's
  distinctness crashed to 2.71. Convert to YCbCr, curve Y, leave Cb/Cr untouched.
- **Gamma, not a flat offset.** An additive shift fixes the backdrop while clipping
  the subject's highlights; a gamma curve compresses instead.
- **Then triage empirically.** Correction cannot rescue an image whose backdrop is
  fundamentally a different studio — one plate at luma 46 against a set median of 223
  only reached 166, washing out the subject on the way. Correct, **re-measure**, and
  treat anything still outside tolerance as must-regenerate. Empirical triage
  ("correct then verify") beats a heuristic ratio threshold, which misclassified
  plates that gamma actually handled fine.

Note the interaction: strong colour words in an authored spec **bleed into the
backdrop**. A TAN-KHAKI wardrobe produced a warm/amber cast (spread 16–24), OLIVE-GREEN
produced cool/teal (20–31) — on plates whose prompt explicitly demanded neutral grey.
Fixing the wardrobe *introduces* a chroma cast. Expect it and plan the white-balance
pass rather than treating it as a new bug.

## 5. One call per item — never batch "N distinct X"

Batched multi-image modes do not give you a coherent *set*. They give N independent
rolls sharing a prompt, so anything requiring **contrast between items** is left to
chance. This one mechanism produced four differently-shaped failures before it was
recognised as a single cause:

| Batched request | Failure |
|---|---|
| "9 images: 5 angles + 4 emotions" | silently returned **6** |
| "5 distinct camera angles" | ladder skewed, both intermediate angles wrong |
| "4 distinct emotions" | two emotions converged (distinctness 4.46 vs tol 6.0) |
| any sequential batch | backdrop luma spread 29.4 |

Fix: iterate in your own code, one prediction per item, focused brief, batching
disabled. Then **assert the returned count**:

```python
def expect(urls, want, label):
    if len(urls) != want:
        raise RuntimeError(f"{label}: expected {want}, got {len(urls)}. Re-run; "
                           "do not proceed with an incomplete set.")
    return urls
```

**Under-delivery is SILENT** — status comes back `succeeded` with fewer images than
requested. `max_images` is a ceiling, not a target. Never infer success from status
alone.

## 6. Stop asking for what the model cannot do

When three rounds of escalating prompt specificity fail on the same property, the
property is not promptable on that model. Ship what verifies and drop the rest.

Worked example: intermediate (45°) camera angles failed across **three generations and
two characters** — degrees, then shoulder-line percentages, then explicit
both-eyes-visible plus anti-cheat language, then one API call per angle. Front,
profile and back passed every single time. The intermediate slots over- and
under-rotated in opposite directions.

Decision: drop the 45s, ship front + profile + back. A *wrong* reference plate is
worse than a missing one — it teaches the downstream model an identity at an angle the
subject never actually holds. Revisit only with explicit camera control or a
novel-view-synthesis step, never with more prompt language.

Three attempts is enough evidence.

## 7. Prompt-writing rules that survive contact

- **Negate the rendered FEATURE, not its attributes.** "Grief" produced purple-mauve
  eye rings reading as bruising. Negating the colour ("no purple, use grey") still
  produced rings, just greyer. Redirecting the *mechanism* worked: convey exhaustion
  through "slack mouth, heavy upper eyelids, loose jaw", plus "under-eye skin CLEAN
  and EVEN, same tone as the cheeks", plus explicit no-rings / no-sunken-sockets /
  no-tears clauses.
- **Describe physical muscle action, not emotion labels.** "Neutral but guarded"
  yields placid. Dropping the word *neutral* and specifying "lower eyelids tightened
  and slightly raised, jaw clenched, lips pressed into a flat closed line, chin
  slightly lifted" worked.
- **Anchor comparatives to the reference, not to a number.** "Late 50s" reliably
  produced late 60s. "Must look the SAME AGE as the reference image and no older; do
  not add wrinkles, do not deepen lines" fixed it.
- **Never put a cinematic grade on a reference plate.** The grade bakes coloured light
  into the plate, and if downstream plates are generated i2i *from* it, the cast
  propagates through the whole set. The consumer then inherits coloured light instead
  of the subject's true albedo. Grades belong on the final shot, never the lock.
- Say **"no collage, each image separate"** or you get grid panels inside one image.
- Say **"THIS EXACT PERSON/OBJECT from the reference image"** and enumerate what must
  not change.
- For empty-location plates, "no people, no figures" must be stated or figures leak in.

## 8. Scoping vision subagents so they actually finish

Five subagents in one session hit their iteration caps and returned almost nothing,
all for the same reason: a flaky vision tool returned loader stubs and the children
retried indefinitely.

What works:

- **Build contact sheets with PIL first** — one labelled montage per group — and have
  the child judge the single image rather than opening ten files.
- **One group per subagent**, dispatched in parallel. Not one child for everything.
- Put this in the context **verbatim**: *"if the vision tool returns a loader stub,
  placeholder, or no rendered image, retry AT MOST TWICE, then STOP and report 'vision
  tool unavailable' and move on. An honest partial report is far more valuable than an
  exhausted one. Never fabricate observations."*
- **Name the specific known failure mode** under test so the child hunts for it rather
  than free-associating.
- **Tell the child how each asset was produced** (which conditioning mode, which
  references) so it can attribute a defect to a mechanism instead of guessing.
- **Demand unverified items be reported as unverified.** Explicitly reward saying "I
  could not see this file."
- Ask for **pixel samples with RGB values** for colour claims — "do not eyeball
  colour."

Truncated runs are still worth dispatching. Partial honest reports caught a grade
leak, an angle collapse, backdrop brightness variance, and the invented-spec error
above. **A partial honest report beats a complete generous one.**

## 9. Verifying generated VIDEO

Video adds failure modes stills do not have. Ask for each separately:

- **Identity drift across shots** — score each shot on the same scale so decay is
  visible as a trend, not a vibe. Tell the child which shots were re-anchored to
  references and which were chained, because drift attribution depends on it.
- **Within-shot stability** — compare first / middle / last frames of the *same* shot.
  Long takes let a model re-stage blocking, relight, change location and re-age a
  character *inside one shot*.
- **Continuity across cuts** — separate from within-shot. In one case the cuts were
  pixel-perfect (chaining worked) while each shot destroyed its own location, so the
  plumbing was right and the takes were wrong. Diagnosing that as a "cut problem"
  would have fixed the wrong thing.
- **Spatial coherence** — interior/exterior inversion is common and models do not
  infer it. A character opened a door from inside with the *exterior* landscape behind
  her. Pin the camera side in the prompt explicitly.
- **Audio** — check whether there is speech at all before judging sync. A spectrogram
  showing ~evenly spaced broadband transients at a fixed interval is a percussive
  ambience bed, not dialogue. Speech is never metronomic.

## 10. Working discipline

- **`--dry-run` every generation path.** Print the exact payload, the asset list, and
  a cost estimate. One dry run caught a 29MB payload against a ~10MB limit, duplicate
  reference filenames, and two mutually-exclusive parameters — all before spend.
- **Never swallow provider errors.** A handler written as
  `pd.get('error') if 'pd' in dir() else ''` produced a bare `failed:` and cost a full
  debugging cycle. Surface `error` AND `logs` AND the request id — the real reason is
  usually in `logs`.
- **Suspect your own fix when a new failure appears in the same step.** An
  all-channel gamma correction appeared to "break" emotion distinctness; the emotions
  were fine, the correction had flattened two plates toward each other. A misdiagnosis
  of your own bug as a model failure costs a regeneration cycle.
- **Version backups by content hash.** A flat `_raw/` directory plus a blanket
  restore silently reinstated older-generation plates over freshly generated verified
  ones. `body_00.<sha1[:8]>.png` makes that impossible.
- **Quarantine, never delete.** `mv` to `_quarantine/` beats `rm -rf` on assets you
  paid for.
- **Re-run the full gate after any "small" fix.** Three separate times a fix in one
  gate regressed another.

## Verification checklist

- [ ] Every property to be QC'd exists as authored data, injected verbatim into prompts
- [ ] Numeric gates implemented and passing BEFORE any vision-subagent spend
- [ ] For each gate, the complementary blind-spot gate also exists
- [ ] Fixer and grader use the SAME estimator for the same property
- [ ] Every artifact a gate grades is also processed by the fixer
- [ ] Returned asset counts asserted, not inferred from `succeeded`
- [ ] One API call per item for any set needing inter-item contrast
- [ ] Chroma corrected before luma; luma correction is luma-only
- [ ] Uncorrectable outliers regenerated, not force-corrected
- [ ] Vision subagents scoped to one group each, with retry limits stated verbatim
- [ ] `--dry-run` clean before any paid generation
- [ ] Provider errors surface `error` + `logs` + request id
