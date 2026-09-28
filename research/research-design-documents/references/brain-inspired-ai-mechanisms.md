# Brain-Inspired AI — Mechanistic Detail

Second-pass findings, from a narrowly-scoped re-run after a broad review timed
out. Companion to `brain-inspired-ai-review.md`, which covers glia, the
neuromodulator mapping, and affect criteria. This file covers **predictive
coding, active vision, visual simulation, continual-learning eviction, and
three-factor plasticity** — with the implementable detail rather than verdicts
alone.

All URLs verified 2xx/3xx. Items marked `[UNVERIFIED]` were cited from model
knowledge and never fetched — check before relying on the numbers.

Verdict scale: **BUILD TODAY** / **RESEARCH PROBLEM** / **DEAD END**.

---

## 1. Predictive coding (Rao & Ballard 1999)

*Nat Neurosci* 2(1):79–87, PMID 10195184. Levels `l = 0..L`, representation
`r^l`, `r^0` = image.

```
prediction     r̂^(l-1) = f(W^l r^l)
error          e^(l-1) = r^(l-1) − r̂^(l-1)
```

Inference is **iterative gradient descent on r with weights frozen** — a
relaxation dynamic, not a single forward pass:

```
ṙ^l = Wᵀ[Σ⁻¹ e^(l-1) ⊙ f'(W^l r^l)]   ← bottom-up precision-weighted error
      − Σ⁻¹ e^l                        ← top-down error vs level above
      − g'(r^l)                        ← prior
```

Learning is a local Hebbian outer product once `r` settles:
`ΔW^l ∝ Σ⁻¹ e^(l-1) (r^l)ᵀ − λW^l`

Two architecturally useful properties:

- **Only residuals flow up.** A perfectly predicted input sends *nothing*.
  End-stopping and surround suppression fall out unbuilt.
- **Precision `Σ⁻¹` is the formal locus of attention.** Attending = raising the
  gain on a channel's prediction error. This is where an affect/arousal system
  couples into vision.

### The result that caps the claim

PC **provably converges to backprop gradients** on arbitrary computation graphs
([arXiv:2006.04182](https://arxiv.org/abs/2006.04182); graph generalisation
[arXiv:2201.13180](https://arxiv.org/abs/2201.13180)).

So PC is not a different learning rule — it is a local, relaxation-based
*implementation* of gradient descent. Simultaneously the strongest argument for
its biological plausibility and the strongest argument that **it buys no
capability**, at 5–100× cost per step.

### Evidence against, stated fairly

The signature prediction — a dedicated population of **error units**,
anatomically distinct from representation units, silenced by expectation — has
never been cleanly identified. Layer-specific recordings show no clean
segregation. Many "expectation suppression" results are confounded with
stimulus-specific adaptation, and reliable cases of expectation *enhancement*
exist, which a subtractive scheme gets backwards unless precision is invoked as
a free parameter. That flexibility is the standard unfalsifiability complaint.

PredNet ([arXiv:1605.08104](https://arxiv.org/abs/1605.08104)) is the honest
high-water mark: real deep PC-style video model, reproduced neural phenomena,
then shown to largely **copy the last frame**. No PC system is competitive on
standard vision benchmarks.

**BUILD TODAY** as an architectural motif (top-down prediction, residual-only
feedforward, learned precision gain). **RESEARCH PROBLEM** as a backprop
replacement.

---

## 2. Active vision — three options, one that works

Common skeleton: policy `π(ℓ_t | h_t)` over fixation location, glimpse sensor
returning a foveated stack (e.g. crops at 32²/64²/128² all downsampled to 32²),
recurrent state, task head. They differ only in how `ℓ_t` is chosen.

| Approach | Status |
|---|---|
| **Hard attention + REINFORCE** ([RAM 1406.6247](https://arxiv.org/abs/1406.6247)) | Works at MNIST scale, **never scaled**. Variance ∝ glimpse count; on real images collapses to degenerate policies (always centre, or ignore state). σ needs hand-annealing; seed-fragile |
| **Expected information gain / BOED** | Theoretically correct: `argmax_ℓ H[p(y|h)] − E[H[p(y|h,o_ℓ)]]`, the epistemic-value term in active inference. Requires simulating the observation you haven't made — **harder than the recognition task itself**. O(\|L\|) rollouts per saccade. No competitive vision system uses it |
| **Foveated multi-res + differentiable top-k** | **What actually works.** Token pruning / dynamic-resolution ViT; deployed as NaViT-style variable resolution and AnyRes tiling in modern VLMs. Gradients flow, no RL, scales |

Honest cost of option three: it is not really a *decision*. You still encode
everything at low resolution before choosing — a representation win, not a
sublinear-compute win, and no sequential evidence accumulation.

**Recommended synthesis:** foveated pyramid + differentiable top-k as substrate,
plus a cheap information-gain-flavoured bonus — reconstruct the unglimpsed
periphery with a JEPA-style latent predictor and saccade to maximum
predicted-latent-error. Gradient-trainable, no REINFORCE, defensible
approximation to expected information gain. V-JEPA 2 supplies the predictor.

The fallback that actually ships: RND/ICM surprise proxies approximate "look
where the model is wrong" without ever computing an expectation over unobserved
outcomes.

**BUILD TODAY** for foveated + differentiable top-k with a latent-error saccade
bonus. **RESEARCH PROBLEM** for REINFORCE hard attention and true EIG targeting.

---

## 3. Visual simulation as reasoning

### Human evidence, quantitative

- **Mental rotation.** RT linear in angular disparity 0°–180°, `r ≈ 0.99`,
  implying ~**60°/s**. The depth-rotation slope is indistinguishable from
  picture-plane — a 2D-template account predicts they differ. Strongest
  behavioural signature of an analog process: the representation passes through
  *intermediate states*. [UNVERIFIED — Shepard & Metzler 1971, *Science*
  171:701–703, cited from knowledge]
- **Image scanning.** Time to shift attention between points on an imagined map
  is linear in *actual* map distance → the medium preserves metric structure.
  [UNVERIFIED — Kosslyn 1973/1978]
- **Neural.** Early visual cortex retinotopically active during pure imagery;
  imagined object *size* modulates which V1 eccentricity band activates.
  Perception-trained decoders cross-generalise to imagery. TMS to occipital
  cortex disrupts imagery-based judgments.

### The counter-evidence that should change the claim

**Aphantasics report zero voluntary imagery yet perform mental rotation and
spatial reasoning at normal levels**
([review](https://pmc.ncbi.nlm.nih.gov/articles/PMC6500925/)). With Pylyshyn's
tacit-knowledge critique (scanning effects partly reflect subjects simulating
what they think should happen), the defensible claim is analog
**spatial/structural** simulation — **not a picture in the head**.

Design consequence: argues for an object-centric metric spatial medium, and
against pixel-space generative simulation.

### Where AI actually is

- **World models / latent imagination** ([1803.10122](https://arxiv.org/abs/1803.10122),
  [1809.01999](https://arxiv.org/abs/1809.01999),
  [DreamerV3](https://arxiv.org/abs/2301.04104)) genuinely reason by simulation —
  rolling policies forward in learned latent dynamics. But rollouts are in a
  compressed latent, horizons ~15–50 steps, task-specific controllers.
- **V-JEPA 2** predicts in representation space, **deliberately abandoning pixel
  reconstruction** because it wastes capacity on unpredictable detail. Note the
  direction: the field moved away from literally simulating images because it
  does not pay.
- **Video generation as reasoner** — demo genre; frames not physically
  consistent enough to trust as inference steps.
- **"Draw and reason" / VLM chain-of-thought** — symbol manipulation with images
  as inputs/outputs. The model still reasons in tokens.

**The gap:** nothing has (i) an object-centric metrically-consistent spatial
medium, (ii) transformation through intermediate states with readable
intermediate results, or (iii) **any way to know when its own simulation is
reliable**. The third is the killer — humans have decent metacognition about
when imagery misleads; learned simulators hallucinate confidently.

**RESEARCH PROBLEM.**

---

## 4. What to forget — the eviction problem

| Method | Mechanism | Why it is not principled |
|---|---|---|
| **Reservoir sampling** | Uniform sample of the stream | Uniform over the *stream* ≠ uniform over *what matters*; rare classes vanish; acceptance prob → 0 so the buffer freezes on the distant past |
| **Herding** ([iCaRL 1611.07725](https://arxiv.org/abs/1611.07725)) | Exemplars approximating class feature mean | First-moment match in a **frozen-at-selection-time** feature space; representation drift makes exemplars unrepresentative. Ignores decision boundaries |
| **Gradient coresets** ([GSS 1903.08671](https://arxiv.org/abs/1903.08671)) | Maximise loss-gradient diversity | Gradients are a property of *current* parameters — optimal at θ_t, not θ_t+1. Re-selecting every step is O(\|M\|²). Conflates "informative" with "hard", so it **reliably hoards label noise** |
| **MIR** ([1908.04742](https://arxiv.org/abs/1908.04742)) | Replay what a virtual step damages most | A *retrieval* policy, not eviction — presupposes the right things are stored. One-step greedy lookahead |
| **Generative replay** ([1705.08690](https://arxiv.org/abs/1705.08690)) | Compress into a generator | Generator itself forgets; self-training compounds error into model collapse |
| **EWC** ([1612.00796](https://arxiv.org/abs/1612.00796)) | Diagonal-Fisher penalty | Ignores parameter correlations; protects *parameters* not *functions* — two nets computing the same function have different Fisher diagonals |

⚠ [Dark Experience Replay](https://arxiv.org/abs/2004.07211) is reservoir +
logit distillation and remains an embarrassingly strong baseline that most
sophisticated methods fail to beat. Benchmark against it before believing any
clever eviction scheme.

### The actual diagnosis

Every method optimises a surrogate for *retention of the past*. The correct
objective is expected loss under the **unknown future**:

```
M* = argmin_{|M| ≤ k}  E_{T ~ p(future)} [ L_T( θ trained on M ∪ stream ) ]
```

Ill-posed three ways: unknown `p(future)`, combinatorial subset selection, and
**bilevel** — a buffer's value depends on the training trajectory it induces,
which depends on the buffer. Practical methods collapse it by assuming the
future resembles the past and scoring samples independently at current
parameters. Both assumptions are wrong.

> No method scores a memory by expected future utility, because that requires a
> model of what queries are coming.

**What a principled solution needs:** an explicit prior over future tasks; value
assigned to the buffer **as a set** (submodular → 1−1/e guarantee);
drift-invariant scoring by functional rather than snapshot quantities; graded
compression instead of binary keep/evict.

**The biologically-grounded bet.** Systems consolidation does not evict episodes
— it *abstracts* them, discarding specifics only once the invariant is
extracted. Computable, drift-aware criterion:

```
evict episode x  when  L_slow(x) < threshold
```

Discard an episode once the slow semantic model already predicts it.

**RESEARCH PROBLEM** — build reservoir+DER as the working baseline and the
"evict once predicted" criterion as the research bet. Do not claim a solution.

---

## 5. Three-factor plasticity — the hook for affect

Two-factor Hebb (`ẇ = η·x·y`) is local but directionless. Three-factor adds a
global scalar `M(t)` (dopamine, ACh, NA):

```
ẇ_ij(t) = η · M(t) · e_ij(t)
ė_ij(t) = −e_ij(t)/τ_e  +  f(x_j(t), y_i(t))        τ_e ≈ 0.2–2 s
```

For rate units `f = x_j y_i`; for spiking units `f` is the STDP kernel. `M` is
usually written as prediction error `r − r̄` rather than raw reward, which is
what makes it a policy-gradient estimator rather than a reward-magnitude bias.

**The eligibility trace** `e_ij` is a synapse-local, exponentially-decaying
memory of recent coincidence — not a weight change, but a *tag* making the
synapse capable of changing if a neuromodulator arrives within `τ_e`. It solves
temporal credit assignment by turning it into a multiplication: the weight
change at reward time is automatically proportional to how recently and strongly
that synapse participated. This is exactly TD(λ)'s eligibility trace.

**Structural appeal:** `e` is local and synapse-specific, `M` is global and
scalar. Broadcast one number and every synapse knows what to do with it.

vs backprop: no backward pass, no weight transport, no stored activation
history, causal and online, O(1) memory in time. Cost is **variance** — a scalar
carries far less information than a per-weight gradient, so the estimator
degrades as width grows. The REINFORCE wall.

| Implementation | Contribution |
|---|---|
| [Differentiable plasticity (1804.02464)](https://arxiv.org/abs/1804.02464) | `w + α·Hebb(t)`; α trained by backprop, Hebb updates online at runtime |
| [Backpropamine (2002.10585)](https://arxiv.org/abs/2002.10585) | Adds network-computed `M(t)` — the network learns *when* to learn |
| [e-prop (1901.09049)](https://arxiv.org/abs/1901.09049) | Factorises BPTT exactly into forward-computable eligibility trace × learning signal. A principled truncation of BPTT, not a biological analogy — strongest technical result in the area |

**Maturity.** Real and reproducible, but every scaling comparison shows these
matching backprop only on small recurrent tasks and degrading with depth, width
and horizon. No competitive large model is trained this way.

**But modulatory gating is deployable today** on an ordinary backprop backbone:
a network-computed scalar gating plasticity rate ("learn hard now") as a learned
per-layer learning rate or a surprise-gated write to fast weights. For an
affect-integrated architecture this is the precise hook — **the affect/arousal
signal becomes `M(t)`**, which makes affect load-bearing in the learning rule
rather than decorative.

**BUILD TODAY** as neuromodulator-gated fast weights / learned plasticity
coefficients on a backprop backbone. **RESEARCH PROBLEM** as a full backprop
replacement (e-prop is the credible path).

---

## 6. Prior art to check any such proposal against

- **Numenta / Thousand Brains** — cortical columns, reference frames,
  sensorimotor prediction. Overlaps the vision story heavily.
- **Active inference / Friston** — free-energy minimisation subsumes prediction
  error, precision-as-attention and homeostatic drives in one formalism. Any
  affect-plus-prediction-error proposal is arguably a special case. Reviewers
  will raise it; name it first.
- **Neuromodulated meta-learning** — Backpropamine, ANML/OML already implement a
  learned signal gating plasticity.
- **Intrinsically-motivated RL** — large literature where prediction error is
  already reward.
