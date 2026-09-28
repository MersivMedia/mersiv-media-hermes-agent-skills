# Brain-Inspired AI — Verified Review Findings

Condensed output of three parallel literature reviews (glia, affect,
vision/recursive learning) run for a neurobiologically-grounded AI architecture
proposal. Every URL below returned 2xx/3xx when checked. Reuse this instead of
re-running the reviews; extend it rather than starting fresh.

---

## 1. The framing that survived

**Use the timescale argument, not the cell-count argument.**

```
milliseconds     spiking, synaptic transmission        ANN: forward pass ✓
seconds          astrocytic Ca²⁺, neuromodulator tone  ANN: ~absent
minutes-hours    consolidation, myelin plasticity      ANN: ~absent
days+            structural pruning, weight change     ANN: training ✓
```

Transformers have fast volatile state (context) and slow frozen state (weights)
and nothing structurally between. What exists is ad hoc and unrelated —
fast weights, SSM hidden states, EMA teachers, LR schedules, KV caches. None is
a general commitment to multi-timescale computation, none persists across
episodes.

**Drop the "glia are 50% / 90% of brain cells" claim.** Human glia:neuron is
roughly 1:1 overall and varies by region (cortex neuron-poor, cerebellum
glia-poor). Higher figures are artefacts of older estimates. The claim is both
contested and argumentatively weak — abundance ≠ computational importance.

Astrocyte numbers worth quoting instead: Ca²⁺ transients rise ~0.5–3 s, decay
~5–30 s; intercellular waves ~10–25 μm/s; one astrocyte enwraps 10⁴–10⁵
synapses in a non-overlapping domain that tiles cortex. That is 10²–10⁴× slower
than a 1 ms spike — a slow state variable computed by pooling over a large fixed
population and fed back multiplicatively onto that same population.

---

## 2. Glia — verdicts

### Astrocytes: mostly redundant, one deep result

| Mechanism | Closest ML primitive | Verdict |
|---|---|---|
| Glutamate/K⁺ clearance | Divisive normalisation / LayerNorm | Redundant |
| Gliotransmitter gain over a domain | Squeeze-and-excitation / FiLM | Redundant, and *worse* — pooling group fixed by anatomy, not learned |
| Self-repair after synapse loss | Dropout robustness + weight noise | Real but narrow; damage regime only, baselines undefended |

**The load-bearing result — build on this.** Kozachkov et al.,
*Neuron-Astrocyte Associative Memory*, [arXiv:2311.08135](https://arxiv.org/abs/2311.08135)
(PNAS 2025). Astrocytic multi-synapse contact yields **supralinear memory
capacity** — memories-per-neuron *grows* with network size, where every other
known biological Hopfield implementation has a constant ratio.

Why it is genuinely novel: Dense Associative Memory needs higher-order (>2-body)
interaction terms, normally requiring an explicit Nᵏ weight tensor. The
astrocyte process supplies them physically via sparse, factorised, spatially
local structure. Same energy function as attention, cheaper parameterisation.
That is an implementation advantage, not a relabelling.

**The bridge result — cite carefully.** Kozachkov, Kastanenka & Krotov,
*Building transformers from neurons and astrocytes*, PNAS 2023
([PMC10450673](https://pmc.ncbi.nlm.nih.gov/articles/PMC10450673/),
[IBM writeup](https://research.ibm.com/blog/AI-transformers-astrocytes)) —
tripartite-synapse dynamics can implement self-attention's normalisation and
weighted summation, with astrocytic Ca²⁺ holding key-value products. Important
science, **zero engineering justification**: it recovers an architecture we
already have, with no demonstrated benefit.

Toy-scale evidence: SNAN spiking neuron-astrocyte networks on MNIST report
faster convergence and better bias-variance tradeoff
([Neural Computation 2025](https://hal.science/hal-04982224v1/file/Jh-Lorenzo-et-al-2025neco_a_01740.pdf),
[code](https://github.com/izeemeen/SNANet)). Honest work, not benchmarked
against tuned modern SNNs.

### Microglia: reject

Complement C1q/C3b tagging of weak synapses plus CR3-mediated engulfment is
**iterative magnitude pruning with extra steps**. The field has a decade of more
principled work — lottery tickets, movement pruning, SNIP/GraSP, EWC-style
importance accumulation. "Immune memory" is an importance buffer. Everything
microglia-branded in the AI literature reviewed was preprint- or essay-grade
with no benchmarks.

One mildly novel cheap variant if someone insists: tag-then-delete with active
protection ("don't-eat-me" signals on high-activity units) under a *global
inflammatory scalar* shifting the pruning threshold network-wide. Test against
magnitude pruning at matched sparsity. Expect little.

### Oligodendrocytes: most underrated, real gap

Standard ANNs including transformers are **delay-free and synchronous** — there
is no per-edge propagation-delay parameter anywhere in the architecture.
Myelination sets conduction velocity, and activity-dependent myelin plasticity
tunes it so signals from different sources **arrive coincidentally**. Temporal
binding by construction rather than by learned weights.

Indirect but strong support: in spiking networks, *learnable delays alone*
achieve SOTA on temporal benchmarks (SHD/SSC) —
[arXiv:2306.17670](https://arxiv.org/abs/2306.17670).

The untried part is the **control structure**: in biology delays are set by a
slow homeostatic controller optimising a *synchrony objective*, hundreds of
times slower than activity — a self-supervised auxiliary objective on temporal
geometry, different in kind from backprop-through-delays. Cheap to test.

---

## 3. Affect — the neuromodulator mapping

The most direct biology-to-ML correspondence available. Each maps to a variable
already present in RL and Bayesian inference — but currently a **hand-set
hyperparameter**. The proposal is to make them state variables the system
computes about itself.

| System | Computational variable |
|---|---|
| **Dopamine** | Reward prediction error δ; tonic vigour / opportunity cost; plasticity gate (third factor in three-factor Hebbian rules) |
| **Serotonin** | Aversive prediction error; behavioural inhibition; temporal discount factor γ |
| **Norepinephrine** | Unexpected uncertainty; network reset/reconfiguration; gain control |
| **Acetylcholine** | Expected uncertainty; balance between sensory evidence and prior |

### Somatic markers — use the architecture, not the disputed claim

Damasio: vmPFC stores links between situation categories and bodily states;
re-encountering a situation re-enacts them via a real body loop or an "as-if"
loop, biasing selection before explicit deliberation.

⚠ The strong claim that anticipatory skin-conductance responses precede explicit
knowledge in the Iowa Gambling Task has been substantively challenged (Maia &
McClelland; Dunn, Dalgleish & Lawrence). Cite the *architecture* — cached
bodily-grounded value estimates biasing policy — not the contested empirical
result.

For an AI, "interoception" means monitoring variables genuinely at stake:
compute budget, memory pressure, model uncertainty, task progress,
prediction-error history, self-consistency.

### Homeostasis as the origin of goals

```
regulated variables    H(t) with setpoints H*
drive function         D(H) — weighted deviation from setpoint
derived reward         r = D(H_t) − D(H_{t+1})
goals                  policies minimising expected cumulative deviation
```

Goals *emerge* from regulation rather than being hand-specified. In active
inference terms, prior preferences.

### On phenomenality

LeDoux & Brown's higher-order argument cuts precisely here: even in humans, the
machinery generating defensive behaviour and bodily affect is dissociable from
the higher-order representation constituting conscious experience. Building the
former entails nothing about the latter. Claim the functional account; decline
the sentience claim; do not dismiss the question either.

---

## 4. Vision and recursive learning

**The unifying principle** — predict future sensory latents conditioned on your
own actions, and let prediction error serve three roles at once: learning
signal, attention/precision signal, and intrinsic reward.

- **Dorsal/ventral is about output purpose, not input type.** Goodale & Milner
  ([Trends Neurosci 1992](https://pubmed.ncbi.nlm.nih.gov/1374953/)): the split
  is vision-for-perception vs vision-for-action. Design implication — maintain
  **two representations of the same scene** with different coordinate frames and
  update rates, not one shared embedding.
- **Active vision** — saccades are information-seeking actions; where to look is
  a decision problem ([arXiv:1406.6247](https://arxiv.org/abs/1406.6247)).

| World-model work | Contribution |
|---|---|
| [World Models (1803.10122)](https://arxiv.org/abs/1803.10122) | Train a controller inside learned dream rollouts; transfer back |
| [I-JEPA (2301.08243)](https://arxiv.org/abs/2301.08243) | Predict in *latent* space — avoids modelling irrelevant detail |
| [V-JEPA 2 (2506.09985)](https://arxiv.org/abs/2506.09985) | 1B+ video encoder; action-conditioned → zero-shot robot planning |
| [DreamerV3 (2301.04104)](https://arxiv.org/abs/2301.04104) | Cross-domain learning with fixed hyperparameters |

Two enduring lessons from World Models: separate a large slow-learning
perceptual model from a small fast-learning policy (credit assignment on a tiny
controller is trivial), and raise model uncertainty temperature during dream
training so the controller cannot exploit model flaws.

### Continual learning

Complementary learning systems — hippocampus fast and specific, neocortex slow
and general, replay interleaving so cortex sees an approximately i.i.d. mixture
([Kumaran, Hassabis & McClelland 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC4248671/)).
Directly implementable as a fast episodic buffer plus slow consolidation with
generative replay.

| Forgetting mitigation | Failure mode |
|---|---|
| [EWC (1612.00796)](https://arxiv.org/abs/1612.00796) | Importance estimates drift over long task sequences |
| [Generative replay (1705.08690)](https://arxiv.org/abs/1705.08690) | Generator quality degrades recursively |
| [Progressive nets (1606.04671)](https://arxiv.org/abs/1606.04671) | Parameters grow without bound |

Intrinsic motivation for sparse/absent reward: prediction-error curiosity
([1705.05363](https://arxiv.org/abs/1705.05363)), random network distillation
([1810.12894](https://arxiv.org/abs/1810.12894)).

**The biggest unsolved obstacle: what to forget.** No principled eviction or
compression policy exists. This blocks continuous learning from visual
experience more than any other single gap. Full survey of what has been tried
and why each fails — plus the one computable criterion worth building — is in
`brain-inspired-ai-mechanisms.md` §4.

**On recursive self-improvement:** no existing system self-improves in the
strong sense — all are single-loop improvement with a human-fixed outer
objective and architecture. Specify bounded, verifiable self-modification with a
human gate, not an open-ended self-rewriting optimiser.

---

## 6. Corrections from the second pass

A narrowly-scoped follow-up review overturned two claims implied above. The
detail lives in `brain-inspired-ai-mechanisms.md`; the corrections matter enough
to state here.

- **Predictive coding is a weaker claim than "the brain's learning rule."** It
  provably converges to backprop gradients on arbitrary computation graphs
  ([arXiv:2006.04182](https://arxiv.org/abs/2006.04182)) — a local,
  relaxation-based *implementation* of gradient descent, at 5–100× cost per
  step. Adopt the motif; do not present it as a superior learning rule. Its
  signature prediction (dedicated error units) has never been cleanly found.
- **"Humans reason via mental imagery" needs narrowing.** Aphantasics report
  zero voluntary imagery yet perform mental rotation at normal levels
  ([review](https://pmc.ncbi.nlm.nih.gov/articles/PMC6500925/)). The defensible
  claim is analog **spatial/structural** simulation, not pictorial imagery —
  which argues for an object-centric metric medium and against pixel-space
  generative simulation. The field independently moved the same way (V-JEPA 2
  predicts in representation space).

Also worth carrying forward: the three-factor Hebbian rule gives the affect
proposal a concrete mechanical role. `M(t)` — the neuromodulatory third factor
gating plasticity — is where an affect/arousal state plugs in, making it
load-bearing in the learning rule rather than decorative. See §5 of the
mechanisms file.

---

## 5. Standing caveats for this domain

- No glial mechanism has shown benefit at modern scale. Every result is
  MNIST-scale, simulation-only, or a capacity theorem.
- Most glial computational work assumes SNNs, which do not train efficiently on
  GPUs. Porting to backprop-friendly dense architectures is unsolved and may
  lose the property that made the mechanism interesting.
- Affect dimensionality and setpoints would be hand-chosen — a genuine weak
  point, since biology derives them from embodiment we do not have.
