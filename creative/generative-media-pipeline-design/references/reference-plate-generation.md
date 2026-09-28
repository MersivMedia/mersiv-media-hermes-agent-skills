# Reference-plate generation: verified failure catalogue

Building character identity locks and location plates for a generative video
pipeline. Every number here was measured, not estimated. Provider in the origin
session was `bytedance/seedream-4` on Replicate, but the failure *classes*
generalise to any multi-image generation endpoint.

Companion to `SKILL.md` §Continuity. Total spend across all iterations: ~$2, no GPU.

---

## Rule 1: ONE CALL PER ITEM. Never batch a "N distinct X" request.

The highest-value rule here, and it took **three separate failures** to see because
it wears a different mask each time:

| Batched request | Failure |
|---|---|
| "9 images: 5 angles + 4 expressions" | silently returned **6** (5 body, 1 face) |
| "5 distinct camera angles" | angle ladder skewed, both 45s wrong |
| "4 distinct expressions" | two expressions converged to **4.46** distinctness (tol 6.0) |
| any sequential batch | backdrop luma spread **29.4** across the set |

A "sequential"/"auto" multi-image mode gives you **N independent rolls sharing a
prompt**, not a coherent set. Anything that requires *contrast between items* —
distinct angles, distinct expressions, matched backdrops — is left to chance.

**Fix:** iterate in your own code, one prediction per item, each with a single
focused brief, batching disabled. ~$0.02 per image. Result on expressions:
distinctness **4.46 → 13.07 / 15.16**.

**Meta-lesson worth more than the rule:** when the same fix works twice on
superficially different symptoms, stop and ask what *class* of thing you are fixing.
Two full rounds were spent treating a general mechanism as a local bug.

## Rule 2: assert returned counts — under-delivery is SILENT

One request for 9 images returned 9. The **identical** call for a second character
returned 6, with status `succeeded` and no error. A half-built identity lock silently
entering the video stage is the failure this pipeline cannot absorb.

```python
def _expect(urls, want, label):
    if len(urls) != want:
        raise RuntimeError(f"{label}: expected {want}, got {len(urls)}. Re-run; "
                           "do not proceed with an incomplete reference set.")
    return urls
```

Never infer success from a success status alone when the count matters.

## Rule 3: some things are not promptable at all — ship what verifies

### Camera angles

Three generations, two characters, escalating specificity: degrees → shoulder-line
percentage → "both eyes visible" + anti-head-turn language → one call per angle.

| Slot | Every attempt |
|---|---|
| front | PASS |
| profile | PASS |
| back | PASS |
| ¾ left | over-rotates toward profile |
| ¾ right | under-rotates toward front |

**It is a skewed ladder, not a collapse.** Pair-distance evidence:

```
character A   front vs tq_right:   8.58  <- CLOSEST pair in set
              tq_left vs profile: 13.57     mid-pack
character B   tq_right vs back:   14.33  <- CLOSEST
              tq_left vs profile: 15.17     mid-pack
```

Two vision subagents independently reported "collapsed into duplicate profiles". The
pair matrix disproved it — the 45° slots miss in *opposite* directions, which is why
`front ≈ tq_right` is the tightest pair. **When vision reports and pixel data
disagree, check the pair matrix before acting on either.**

Fix: drop the 45° slots. Revisit only with explicit camera control or a
novel-view-synthesis step, never with more prompt language. Three attempts is enough.

### Backdrop brightness

With `#808080, RGB 128 128 128` stated verbatim in every prompt:

| Approach | Border-luma spread |
|---|---|
| single batched call | 64 |
| per-angle calls | **129.6** — worse |

Per-angle calls regress this because each call is an independent roll, so **fixing
the angle ladder breaks backdrop uniformity.** Expect that interaction.

## Rule 4: measurable quantities get computed, not prompted

Post-process instead. Measure border **median** luma (median resists a limb intruding
into the border strip), apply a **gamma** curve onto one shared target (an additive
offset fixes the backdrop while clipping subject highlights), then re-measure.

Measured outcome:

```
character A  body 129.6 -> 6.8    face 77.0 -> 13.7
character B  body  20.7 -> 8.6    face 97.6 -> 10.5
```

### Correct LUMA ONLY

Applying the same gamma LUT to R, G and B independently **amplifies** existing channel
imbalance. Verified regression: face plates passing neutrality at 6.2 came back at
**12.6 (FAIL)**, and one plate's distinctness crashed to **2.77**. Convert to YCbCr,
curve Y, leave Cb/Cr untouched, recombine.

**Diagnostic lesson:** that 2.77 was initially called a content failure — "two
expressions collapsed". It was the correction flattening two plates toward each other.
**When a fix and a new failure appear in the same step, suspect the fix.**

### Triage empirically, don't guess a threshold

Gamma cannot rescue a plate shot on a fundamentally different backdrop — one at luma
46 in a set whose median was 223 only reaches 166, washing out the subject on the way.

Correct → re-measure → treat anything still outside tolerance as **must-regenerate**.
An earlier ratio-threshold heuristic misclassified plates that gamma handled fine;
"correct then verify" is simpler *and* more accurate. Typical outcome: 4 of 5 plates
land under tolerance, 1 needs a re-roll.

**Keep raw originals in a `_raw/` sibling directory** — but **key them by content
hash**, never by bare filename. See "Backups MUST be versioned" below; a flat
`_raw/` silently overwrote a freshly generated set with older-generation backups.

### Backups MUST be versioned, or they become a footgun

A flat `_raw/body_00.png` looks like a safety net and is a live grenade. Sequence
that actually happened: generate corrected plates → later run a blanket
"restore from `_raw/`" → **silently overwrite the new plates with backups taken
from an older prompt generation**. The only signal was a costume check failing
afterwards, and the recovery cost a full regeneration.

Key backups by content hash of the file being replaced:

```python
h = hashlib.sha1(p.read_bytes()).hexdigest()[:8]
shutil.copy(p, bak / f"{p.stem}.{h}{p.suffix}")   # body_00.a3f19c2e.png
```

A blanket restore then cannot reinstate a plate from a different generation, and
a flat restore also cannot resurrect files you deliberately retired.

## Rule 4b: wardrobe and appearance must be AUTHORED CANON

The most expensive mistake in the origin session, and it is invisible until video.

The character schema had `name`, `role`, `traits` — and **no costume field**. So
every anchor call invented clothing freely. A whole render cycle and a vision
delegation were spent auditing plates for "costume drift" against a wardrobe spec
that **existed nowhere except in the agent's own earlier summary**, back-derived
from a previous vision report and then treated as ground truth.

The plates were not drifting. They were *unspecified*, which is worse: nothing can
validate an unspecified property, and the error only surfaces once a video model
inherits it.

Fix: make `appearance` and `costume` first-class authored fields alongside `traits`,
written as literal, colour-explicit wardrobe copy, and inject them **verbatim** into
anchor, body, expression *and* shot prompts.

```
costume: "A faded TAN-KHAKI canvas coverall (one-piece boiler suit, colour like wet
          sand), sleeves rolled to the forearm, brass buttons, dark oil stains at the
          thighs. A charcoal-grey wool undershirt at the open collar. Scuffed DARK
          BROWN leather lace-up work boots. No hat, no jewellery, no glasses."
```

Measured effect on the torso region of the front plate:

```
no costume canon   rgb(247,244,228)  luminance 0.93   near-white
with costume canon rgb(170,139,100)  luminance 0.53   hue 33 (tan)
```

**Then gate it.** A weak hue check on the torso band catches the gross failure —
"canon says TAN-KHAKI, the plate is WHITE" — which is exactly the defect that
shipped into a video render.

Two traps in writing that check:

- **Luminance, not saturation, is the discriminator.** HLS saturation stays
  deceptively high for near-white pixels, so a hue+saturation test *passed* the
  white coverall. A tan or olive garment cannot sit above ~0.80 luminance.
- Skip hue-matching for neutral costume words (grey/black/white) — hue is
  meaningless at low saturation.

### Strong colour words in the costume bleed into the backdrop

Adding costume canon introduced a **new** failure, per character and causally
matched to the wardrobe palette:

```
TAN-KHAKI costume   -> warm/amber backdrop cast, channel spread 16-24
OLIVE-GREEN costume -> cool/teal backdrop cast,  channel spread 20-31
(anchor itself 31.0 cool/teal, on a prompt demanding neutral #808080)
```

Luma-only normalization **cannot** fix this by construction — it deliberately leaves
chroma alone. Add a grey-world white balance: the backdrop is *known* to be neutral,
so per-channel gains that force border R=G=B are a principled correction, not a
guess. Apply to the whole frame so the subject's cast is corrected too.

**Order matters: white balance FIRST, then luma.** Correcting brightness on a cast
image just bakes the cast in at the new level. After adding the chroma pass, the same
sets went to neutrality 2–6, uniformity 0.8–2.5, all gates green.

### Two tools must measure a shared property the SAME way

The QC gate computed border **mean** RGB; the normalizer optimized border **median**
luma. Same property, different estimator, so they disagreed on the same files:

```
normalize: "spread after 2.0  PASS"     qc: "uniformity FAIL, spread 52.4"
```

Neither was lying. Two tools disagreeing about one property is worse than either
being wrong, because it destroys trust in both. Unify on the robust estimator
(median resists subject limbs intruding into the border strip) and have the fixer
call the gate's own function where possible.

### Anything a gate GRADES, the fixer must PROCESS

Anchors were excluded from the normalizer's file groups — uniformity is meaningless
for a single image — but the QC gate still graded anchor *neutrality*. Result: an
uncorrected anchor failed a set whose every derived plate passed. Enumerate the
artifact list once and share it between gate and fixer.

## Rule 5: expression plates — describe muscle action, not emotion labels

Each of these survived at least one prompt revision.

| Defect | Fix | Stubbornness |
|---|---|---|
| downcast eyes | "eyes look DIRECTLY INTO THE CAMERA LENS, no downcast, no averted gaze, in any image" | fixes first try |
| fatigue rendered as **injury** — purple-mauve eye rings, tear streaks reading as black eyes | redirect the *mechanism*: slack mouth, heavy upper eyelids, loose jaw; under-eye skin "CLEAN and EVEN, same tone as the cheeks"; explicit no-rings / no-sunken-sockets / no-tears | **stubborn** |
| wardrobe drift mid-set (one plate in a different garment) | "costume collar and garment IDENTICAL to the reference in all N" | fixes reliably |
| "neutral guarded" reads placid/blank | drop the word *neutral* entirely; specify only muscle action — tightened lower lids, clenched jaw, lips pressed flat, chin lifted, "deciding what not to say" | needs full rewrite |
| age drift upward (~a decade older than brief, consistently) | anchor to the reference not a number: "SAME AGE as the reference image and no older. Do not add wrinkles, do not deepen lines" | fixes reliably |

**Two transferable patterns:**

1. **Describe physical muscle action, not emotion labels.** Labels yield generic or
   converging expressions.
2. **Negate the rendered feature, not its attributes.** "No purple rings" produced
   *grey* rings. "No rings at all, skin even and cheek-toned" produced no rings.

## Rule 6: retire bad plates, don't delete them

Move failures to a sibling `_retired_<reason>/` and renumber survivors contiguously:

```
assets/character/<name>/
  body_00.png body_01.png body_02.png   <- verified, contiguous
  _retired_45s/                          <- unreliable angles, kept for future models
  _raw/                                  <- pre-normalization originals
```

Contiguous numbering means downstream code cannot accidentally pick up a retired
plate. Keeping the files means a future model with camera control can be evaluated
against them.

## Pipeline order (the order matters)

```
1. anchor        neutral, NO style bible       -> check neutrality
2. body angles   ONE CALL PER ANGLE            -> check distinctness
                 (front / profile / back only)
3. expressions   ONE CALL PER EXPRESSION       -> check distinctness
                 (muscle-action briefs)
4. normalize     luma-only gamma onto target   -> check uniformity
5. regenerate    uncorrectable outliers only   -> re-run 4
6. vision check  scoped parallel subagents     -> semantics only
```

Steps 4–5 loop until the objective checks pass clean. Only then does the set enter
the video stage.

## Delegating vision review

You cannot see images, and sets look plausible while drifting badly. But scope it
tightly — one broad request (10 images, 6 questions) burned 50 API calls, hit the
iteration cap, and confirmed only 3 files, because the child retried a flaky tool.

- Build **contact sheets first** (one row per group), have the child judge the single
  montage rather than opening N files
- **One group per subagent**, dispatched in parallel
- Give a **hard cap on TOTAL attempts across all images**, not a per-image retry
  count: *"call the vision tool on the grid. If you get a loader stub, retry — but
  STOP after FIVE total attempts across all images and report 'vision tool
  unavailable'. An honest partial report beats an exhausted one. Do not fabricate
  observations."*
- **Name the specific known failure mode** under test so the child hunts for it
- Demand unverified files be reported as unverified
- **Put the priority questions first and say they are the priority.** Truncated
  children answer in order, so a question at position 5 may never be reached.

**A per-image retry limit is the wrong control.** Five consecutive delegations lost
most of their budgets to a flaky vision tool where *the same path alternates between
stub and successful render* — so "retry at most twice, then move on" still permits
dozens of attempts across a large set, and the child grinds. What actually worked:
one pre-built 6-panel grid, a total-attempt ceiling, and the two user-reported
questions listed first. That run answered both in **2 API calls and 25 seconds**,
after a broad one had burned 50 calls and 580 seconds answering neither.

Fewer, larger, pre-built images beat more retries.

Truncated honest reports still delivered value — they caught the grade leak, the
angle problem and the invented-costume spec. A partial honest report beats a complete
generous one.

## Final verified state

```
character A  body (3)  neutrality  9.7  uniformity  6.8  distinctness  6.96
             face (4)  neutrality  6.5  uniformity 13.7  distinctness 13.07
character B  body (3)  neutrality 10.7  uniformity  8.6  distinctness 14.33
             face (4)  neutrality  4.2  uniformity 10.5  distinctness 15.16
location     plates (6, graded)                          distinctness 30.71
```
