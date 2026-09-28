# Benchmarks, baselines and metrics for ML experiment design

Gathered while specifying a methodology section for a brain-inspired AI
proposal. All URLs verified HTTP 200/203 at time of writing. Use this to name
concrete benchmarks instead of writing "evaluate on standard benchmarks."

The general pattern: **for each experiment, name the benchmark, the baseline
that actually threatens the claim, the metric, and the discriminating
condition.** The last one is what most proposals omit.

---

## Associative memory capacity

**Protocol** — three tiers, standard in the Dense Associative Memory literature:

1. Synthetic random-pattern storage: store N random patterns of dimension d,
   query with masked or sign-flipped versions, measure exact-retrieval
   probability as N grows.
2. Retrieval under corruption on MNIST / CIFAR-10 with occluded queries.
3. The Hopfield layer as a drop-in module on multiple-instance learning tasks.

**Discriminating condition: correlated patterns.** Independent random patterns
are the easy case. Drawing from a mixture model degrades capacity and separates
methods with a structural advantage from those restating attention.

**Baselines**
- Classical Hopfield — capacity 0.14d
- Krotov & Hopfield Dense Associative Memory, rectified polynomial energy at
  degree n = 2, 3, 20 — https://arxiv.org/abs/1606.01164
- Modern continuous Hopfield, softmax energy — https://arxiv.org/abs/2008.02217

**Metric** — storage capacity C = max patterns retrievable with probability
≥ 1−p, reported as a **scaling curve against d**, not a single number. Match and
report parameter count.

---

## Non-stationary / continual RL

**Check the non-stationarity TYPE before choosing.** "Changes without warning"
covers two structurally opposite regimes, and picking the wrong one can invert
the hypothesis being tested:

```
resampled per episode    latent structure redrawn at each boundary.
                         Carried state is STALE; optimal play is to RESET
                         belief at episode start.
drifting / autocorrelated  structure evolves continuously and is never reset.
                         Recent history IS informative across boundaries.
```

A hypothesis about **state that persists across episodes** requires the second.
Evaluating it in the first tests the opposite claim, and a null result is
uninterpretable. This exact error reached a full draft before peer review caught
it — see `design-document-peer-review.md`.

**Environments**

| Environment | Type | Use | URL |
|---|---|---|---|
| **Daw 4-armed restless bandit** | Drifting | **Primary for persistence claims.** Payoff means follow a decaying Gaussian random walk (λ≈0.9836, sd≈2.8), never reset at boundaries. **The Kalman posterior is the closed-form optimal persistent variable**, so the mechanism can be tested by direct correlation against a known target | https://www.nature.com/articles/nature04766 |
| **Behrens volatility task** | Drifting regimes | Interpretable companion. Estimated volatility (which should drive learning rate) has a known analytic counterpart | https://www.nature.com/articles/nn1954 |
| NeuroGym | — | Gym implementations of both of the above | https://github.com/neurogym/neurogym |
| Agar.io continual RL | Continuous stream | Higher-capacity scale confirmation | https://arxiv.org/abs/2505.18347 |
| DeepMind Alchemy | **Resampled per episode** | Good for meta-RL / within-episode inference. **Wrong for cross-episode persistence** — and useful precisely as a zero-autocorrelation *control* where a persistence mechanism should show no benefit. Note the paper reports "a frank and specific failure of meta-learning" by strong agents, so improvement sits near the floor | https://arxiv.org/abs/2102.02926 |
| bsuite | Mixed | Standardised sanity harness, **not evidence** | https://arxiv.org/abs/1908.03568 |

**Prefer an environment with a closed-form optimum.** When the Bayes-optimal
version of the proposed variable is analytically available, the hypothesis gains
a falsification criterion independent of task score — e.g. "`a(t)` correlates
with the Kalman posterior at r < 0.3" refutes the mechanism regardless of
reward. Simple interpretable environments often test a mechanism more sharply
than complex ones.

**The baseline that must be included: RL²** (https://arxiv.org/abs/1611.02779).
An LSTM-A2C/PPO agent is the standard "the recurrence already does it" rebuttal.
Any architecture proposing a separate slow/modulatory variable must beat it —
beating a feedforward agent demonstrates nothing.
VariBAD (https://arxiv.org/abs/1910.08348) is the belief-state comparison.

**Metrics**

- **Dynamic (tracking) regret** against the per-timestep oracle — the standard
  measure under non-stationarity, reported as a function of drift rate rather
  than a single number — https://proceedings.mlr.press/v119/cheung20a/cheung20a.pdf
- **Latent tracking error** — correlation/MSE between the agent's persistent
  variable and the analytic posterior. The most direct test available
- **Boundary reset cost** — regret difference in trials immediately after an
  artificial episode boundary, carried state vs zeroed state
- Recovery time τ and post-change AUC for abrupt change points
- CORA conventions for comparability with the continual-RL literature —
  https://arxiv.org/abs/2110.10067

Avoid change-point-detection metrics (detection delay, false-alarm rate) under
smooth drift — they assume abrupt shifts and are ill-defined otherwise.

### Operationalising behavioural predictions

Computational neuroscience supplies statistics for claims that otherwise read as
narrative. These are fitted to an artificial agent exactly as to an animal:

| Claim | Statistic | Source |
|---|---|---|
| Risk calibration | ρ in `p(a) ∝ exp(β[Q̂(a) + ρ·σ̂(a)² + γ·σ̂(a)])`, Q̂/σ̂ from a Kalman observer on the same stream | https://pubmed.ncbi.nlm.nih.gov/29289795/ |
| Perseveration / failure to disengage | κ in `p(a) ∝ exp(β·Q_t(a) + κ·1[a = a_{t−1}])`; also lose-shift probability, post-reversal switch latency | https://pubmed.ncbi.nlm.nih.gov/31850845/ |
| Effective learning rate | α̂ from sliding-window delta-rule fit — the regression slope of ΔV_t on δ_t — regressed on true volatility | https://www.nature.com/articles/nn1954 |

---

## Predictive coding and active vision

**There is no accepted benchmark. Say so rather than implying one.** The field
is genuinely fragmented across two literatures with incompatible conventions.

**Video prediction** — PredNet's own evaluation sets: synthetic rotating-face
sequences and the KITTI driving corpus (https://arxiv.org/abs/1605.08104).

**Mandatory degenerate baseline: copy-last-frame.** PredNet's headline result
was substantially attributable to copying the previous frame. Any predictive
model that omits this baseline has not been evaluated.

Metrics: MSE / PSNR / SSIM as **per-horizon curves** (t+1 … t+10), never a
single aggregate. LPIPS or FVD for longer rollouts.

**Representation quality** — linear-probe transfer to downstream tasks, which
tests whether prediction produced structure rather than pixel copying.

**Glimpse-based attention** — no standard suite exists; cross-paper comparison
is unreliable and should be labelled as such.

---

## Temporal / delay learning (spiking)

**Benchmarks** — Spiking Heidelberg Digits (SHD, 20 classes, 700 input channels
from a cochlea model) and Spiking Speech Commands (SSC, 35 classes, spiking
conversion of Google Speech Commands v0.02).

**The bar** — DCLS-Delays: **~95.1% SHD, ~80.7% SSC**
(https://arxiv.org/abs/2306.17670). Re-confirm against the paper's own table
before quoting.

Weaker rungs for context: feedforward LIF SNN with surrogate gradients and no
delays ≈ 48–72% SHD; recurrent SNN with surrogate gradients sits between.

**Reporting** — top-1 accuracy, mean ± SD over **5–10 seeds**. SHD's test set is
small enough that single-run numbers are untrustworthy; seed spread of 1–2% is
typical.

**Framing note:** whether delays help is settled. The open question for a
homeostatic/self-supervised delay controller is whether it sets them *better
than task gradients do* at matched parameter count.

---

## Continual learning

**Benchmarks** — Split-CIFAR-10, Split-CIFAR-100, Split-TinyImageNet under the
class-incremental protocol. Use the Mammoth reference implementation so baseline
numbers are directly comparable.

**Baselines that must be beaten**
- Reservoir-sampling experience replay — https://arxiv.org/abs/1902.10486
  (famously hard to beat; a policy that does not clear it has shown nothing)
- DER++ — https://arxiv.org/abs/2004.07211

**Metrics** — following the GEM convention (https://arxiv.org/abs/1706.08840):
average accuracy after the final task, backward transfer (negative =
forgetting), forward transfer.

**Buffer sizes** — 200, 500, 5120 are conventional reporting points. **The
smallest buffer is the most diagnostic**, since eviction policy only matters
when capacity binds.

---

## Statistical practice

**Supervised benchmarks** — minimum 5 seeds, 10 preferred. Report mean ±
standard deviation, state the seed count in every table caption, and say
explicitly whether the interval is SD or SEM. Conflating them is a common
reviewer complaint.

**Reinforcement learning** — follow Agarwal et al., *Deep RL at the Edge of the
Statistical Precipice* (https://arxiv.org/abs/2108.13264):

- Interval estimates via **stratified bootstrap confidence intervals over the
  interquartile mean (IQM)**, not point-estimate means
- Performance profiles (score-distribution curves)
- Probability of improvement, optimality gap
- Library: `rliable` (github.com/google-research/rliable)

Ten seeds with IQM and 95% bootstrap CIs is a defensible budget. **Point-estimate
means over 3–5 seeds are not**, and stating this in the methodology section
signals the work is aware of current expectations.
