# Peer-reviewing a design document — worked example

Structured adversarial review of a brain-inspired AI architecture proposal,
with the findings and the revisions that resolved them. Use as a template for
what a real review turns up and how deep the fixes have to go.

---

## Review structure that worked

```
1  Summary of the submission        what it claims, stated neutrally
2  Major issues                     blocking; each with location + required fix
3  Moderate issues                  weaken the work, do not invalidate it
4  Minor issues and corrections     table: location | issue
5  Second detailed read             section by section, with line numbers
6  Assessment of significance       strongest and weakest element, named
7  Recommendation                   priority-ordered, blocking items flagged
```

Separating blocking from moderate is what makes the review actionable. Three
blocking items with locations beat twenty equal-weight observations.

---

## The finding that mattered most

**The flagship experiment tested the opposite of the hypothesis.**

- H1 required state that **persists across episode boundaries**.
- Methodology named DeepMind Alchemy because its latent structure "resamples
  between episodes."
- Alchemy's causal structure is *resampled procedurally from episode to
  episode*. Carried state is therefore stale; optimal play is to **reset**
  belief at episode start.

A null result would have been uninterpretable — mechanism failure, or an
environment hostile to the mechanism? Nothing else in the review came close to
this in severity, and it was invisible until the hypothesis precondition and
the benchmark structure were written side by side.

Secondary problem with the same environment: the Alchemy paper reports "a frank
and specific failure of meta-learning" by strong agents. Demonstrating
improvement near the baseline floor is not attributable to a specific
architectural change.

### The replacement, and why it was an upgrade

**Daw et al. (2006) four-armed restless bandit**, run as one continuous stream
with artificially imposed episode boundaries:

```
μ_{t+1} = λ·μ_t + (1−λ)·θ + ν        λ ≈ 0.9836,  sd(ν) ≈ 2.8
```

Payoff means drift continuously and are **never reset at a boundary**, so an
episode boundary is an arbitrary segmentation of one drifting life — exactly
the regime the hypothesis describes.

The decisive advantage: **the Bayes-optimal persistent variable is available in
closed form.** The Kalman posterior is precisely what the proposed variable
should approximate, so the hypothesis becomes testable by direct correlation
against a known target. This added a falsification criterion that did not exist
before — `r < 0.3` against the Kalman posterior refutes the mechanism
independently of task performance.

Companion: **Behrens et al. (2007) volatility task** — two-option probabilistic
reward with unsignalled stable/volatile regimes, where estimated volatility has
a known analytic counterpart that should drive learning rate.

Both retained Alchemy as a **zero-autocorrelation control** where the mechanism
should show no benefit; benefit there indicates an artefact.

Verified sources:
- Daw restless bandit — https://www.nature.com/articles/nature04766
- Behrens volatility — https://www.nature.com/articles/nn1954
- NeuroGym implementations — https://github.com/neurogym/neurogym
- Agar.io continual RL (scale confirmation) — https://arxiv.org/abs/2505.18347
- Dynamic regret under non-stationarity — https://proceedings.mlr.press/v119/cheung20a/cheung20a.pdf
- CORA continual metrics — https://arxiv.org/abs/2110.10067

---

## Blocking issue 2: conjunctive hypothesis tested as a bundle

H1 claimed a variable with (i) persistence, (ii) intrinsic dynamics,
(iii) multiplicative gating. The original four conditions tested the
conjunction against its absence — which cannot attribute an effect to any one
property.

This was disqualifying because the document's own prior-art section had already
conceded that gating belongs to Backpropamine and homeostatic dynamics to
Keramati & Gutkin. **Persistence was the only claimed increment, and the design
could not isolate it.**

Fix: seven conditions with single-property knockouts (table in SKILL.md §6c),
plus an explicit statement that condition 2 — reset at episode boundary — is
the decisive comparison, since matching condition 1 there means the claimed
contribution does not exist.

---

## Blocking issue 3: the predicted signature was unfalsifiable

"Structured degradation rather than uniform decline" with three narrative
predictions and no statistic for any of them.

Resolved with standard computational-psychiatry measures, fitted to the
artificial agent as they would be to an animal:

| Prediction | Statistic | Source |
|---|---|---|
| Loss of risk calibration | ρ in `p(a) ∝ exp(β[Q̂(a) + ρ·σ̂(a)² + γ·σ̂(a)])`, with Q̂/σ̂ from a Kalman observer | Gershman 2018 — https://pubmed.ncbi.nlm.nih.gov/29289795/ |
| Failure to disengage | Perseveration κ in `p(a) ∝ exp(β·Q_t(a) + κ·1[a = a_{t−1}])`; lose-shift probability; post-reversal switch latency | Lau & Glimcher 2005; Daw et al. 2011 — https://pubmed.ncbi.nlm.nih.gov/31850845/ |
| Learning-rate control fails | α̂(t) by sliding-window delta-rule fit (regression slope of ΔV_t on δ_t), regressed on true volatility | Behrens 2007 — https://www.nature.com/articles/nn1954 |

Structured-vs-uniform test:

```
y_{s,m} = β₀ + β₁·Arm + β₂·MetricFamily + β₃·(Arm × MetricFamily)
          + (1 | seed) + (1 | metric within family)
```

All metrics z-scored and sign-aligned. Structured = significant interaction by
likelihood-ratio test, then pre-planned contrasts with Benjamini–Hochberg at
q = 0.05. Uniform degradation must be established **positively** via TOST
equivalence against a declared ±0.3 SD bound — never inferred from p > 0.05.

---

## Moderate findings worth reusing

**Power asserted rather than derived.** Fixed with a declared minimum effect of
interest (5% improvement in normalised dynamic regret over the threatening
baseline, probability of improvement ≥ 0.6) and a bootstrap power procedure
over a 10-seed pilot. rliable reports IQM at 5 runs achieving interval widths
the median needs ~20 runs to reach — https://arxiv.org/abs/2108.13264

**Circular eviction criterion.** "Evict once the slow model predicts it" — but
the slow model trains on retained data, so the buffer drifts toward what the
model finds hard, where label noise concentrates. Same pathology the document
criticised in gradient-coreset methods. Fixed with a 25% reservoir-sampled
exempt fraction, a stability requirement across k consolidation passes, and
promotion of buffer composition to a **primary measured outcome**.

**Internal contradiction between sections.** §1.1 marked a timescale band
"Absent"; §2.1 then documented systems operating in it. Qualify at first
assertion — "no principled equivalent; see §2.1 for partial implementations" —
rather than correcting two sections later.

**Mechanism unimplementable.** `g`, the setpoint, τ, gate placement and
architecture sizes were all unspecified. "Parameter-matched" is not
implementable without a parameter count.

**Missing compute budget and ethics statement.** The compute table earned its
place by exposing that the least promising experiment consumed roughly half the
programme's GPU-hours — which justified its position last in the sequence.

---

## Minor findings: the stale-edit class

All four came from earlier structural edits, and all were invisible in prose:

| Location | Issue |
|---|---|
| Abstract | "five distinct roles" after a cut reduced it to four |
| §8 table | Cross-reference to `§Method`, merged away earlier |
| §7.3 | "affect state" surviving a terminology change to "modulatory state" |
| §1.2 | Claim that ML never arrived at modulatory signals independently — contradicted by the document's own Backpropamine row |

Grep for counts and cross-references after any structural change.

---

## What the review affirmed

Worth recording because it shapes what to keep doing:

- **Publishing negative results.** Three ideas rejected with reasons, numerical
  claims corrected against primaries. This materially increased confidence in
  the surviving claims.
- **The mandatory threatening baseline.** Naming RL² as required — the
  "ordinary recurrence already does this" rebuttal — rather than comparing
  against a weak baseline.
- **Conceding against interest.** Stating that predictive coding "provably
  converges to backpropagation gradients, and therefore confers no capability
  advantage" strengthened rather than weakened the document.
- **The shuffled control.** Present from the first draft; it is the control
  most authors omit.
