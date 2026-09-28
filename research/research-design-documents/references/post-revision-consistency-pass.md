# The post-revision consistency pass

A design document that has been revised several times accumulates a specific
class of defect: sections that were correct when written and became false when
something else changed. None of these are visible while writing, and most are
invisible to grep.

This is the pass to run **after** all substantive revisions and **before**
final delivery. In the worked example it found six issues in a document that
had already passed an adversarial peer review.

---

## Why this pass is separate from peer review

Peer review asks *is the argument sound?* This pass asks *does the document
still say one thing?* They find different defects. The review found the
flagship experiment tested the opposite of the hypothesis; this pass found the
open-problems section contradicting a result cited two pages earlier.

Both had shipped through the other check.

---

## 1. Verdict propagation

The highest-yield check. When any mechanism's verdict changed during revision,
every section that cited that verdict is suspect.

In the worked example, microglia moved from **rejected** to **pruning not
adopted, one mechanism retained** after a challenged rejection was re-derived.
Four sites went stale, none caught by the mechanical greps:

| Site | Stale content | Why it broke |
|---|---|---|
| Abstract tally | "Four claims survived verification; three did not" | Microglia was now *partly* supported, and a new supported claim had been added. The two-outcome framing no longer fit — it needed a third category |
| Open problems | "No glial mechanism has demonstrated benefit at modern scale. Every supporting result is small-scale, simulation-only, or a capacity theorem" | Directly contradicted the benchmarked AGMP results now cited in the mechanism section and the positioning section |
| Evaluation table | No row for the newly-retained feedback-control mechanism | A mechanism the document adopts but never proposes to test |
| §5 title | "Affective control signals", while §5.1 disclaimed the term | Terminology changed; the heading did not |

The open-problems case is the instructive one. That section is written early,
read as boilerplate, and states absolutes — which is exactly the combination
that produces a flat contradiction after a verdict flips.

**The check:** grep for each mechanism's *name*, not for the stale phrasing,
and read every prose hit against the current verdict table.

```bash
grep -niE 'microglia|astrocyte|oligodendrocyte' doc.md | grep -viE '^\s*[0-9]+:\|'
```

---

## 2. Unit reconciliation across the domain boundary

A cross-domain document states its motivating gap in the **source** field's
units and specifies experiments in the **target** field's units. Each section
is internally consistent; the correspondence between them is never stated.

Worked example:

```
§1  motivating gap      "0.1–10 s"            biological measurement
§10 experiment sweep    "{10 … 3000} steps"   inference steps
                        ↑ nothing connects these
```

An artificial system has no intrinsic seconds-per-step. The document's central
timescale argument therefore rested on an equation it never made.

**Fix: restate as a ratio internal to the target domain.**

> The useful τ should be one to three orders of magnitude longer than the
> recurrent state's effective memory and substantially shorter than a training
> run. That ratio is what the biological argument supports, and it is what the
> sweep measures. Any correspondence to literal seconds is coincidental and is
> not claimed.

This is strictly stronger than the implicit version: it converts an unstated
assumption into a prediction the sweep can confirm or refute.

Generalises to any imported quantity — energy budgets, connectivity fan-out,
population sizes. Ask for each: *what is the conversion, and did the document
state it?*

---

## 3. Closed-loop amplification

Distinct from the circularity check. Circularity is a criterion feeding on its
own output. **Amplification** is a controller whose input signal is influenced
by the controller itself, so that a systematic bias reinforces rather than
corrects.

Worked example: the modulatory state was computed from prediction error and
gated learning rate and attention precision. A systematically overconfident
predictor therefore produces a systematically wrong control signal — and the
loop strengthens it. Noise averages out across episodes; bias does not.

The design had no detector for that case, which belonged in the unresolved
section:

> The proposal assumes the drive signal is trustworthy. `a(t)` is computed from
> prediction error, so a systematically miscalibrated predictor produces a
> systematically miscalibrated control signal, and the feedback loop could
> amplify rather than correct it. No mechanism in the current design detects
> this case.

**The question to ask of any feedback architecture:** what happens if the drive
signal is systematically wrong rather than noisy?

---

## 4. Cross-section coverage checks

Two structural checks that are cheap and catch real omissions:

```bash
# every experiment in the sequence table has a protocol section
grep -oE '^\| [0-9] \| ([^|]{5,55})' doc.md          # sequence
grep -oE '^## 10\.[0-9] Experiment [0-9]+ — (.*)$' doc.md   # protocols

# every adopted mechanism has an evaluation row
grep -c '^| ' <evaluation-table-range>
```

Mismatched counts mean either an experiment with no protocol or a protocol for
an experiment no longer proposed. Both occurred at some point during the worked
example's revisions.

---

## Full checklist

```
[ ] verdict table current, and every prose mention of each mechanism agrees
[ ] abstract tally recounted after any verdict change
[ ] open-problems entries checked against newly-cited results
[ ] evaluation table has a row per adopted mechanism
[ ] section titles match current terminology and current verdicts
[ ] source-domain units reconciled with target-domain units, explicitly
[ ] feedback loops checked for amplification of bias, not just circularity
[ ] sequence table entries ↔ methodology subsections, one to one
[ ] counts ("four roles", "three conditions") recounted
[ ] cross-references resolve to sections that still exist
[ ] title and subtitle match the current section list
[ ] second-person sweep: grep -niE '\byou\b|\byour\b'
[ ] all citations re-verified after edits (link rot plus newly added sources)
```

The last item matters more than it looks: revisions add citations, and a pass
that verified 54 URLs earlier does not cover the 63 present after a round of
additions.
