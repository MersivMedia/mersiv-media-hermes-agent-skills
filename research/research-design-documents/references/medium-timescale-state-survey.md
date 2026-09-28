# Medium-timescale state in ML — the novelty landscape

Survey run to test the claim *"ANNs lack a principled medium-timescale state
variable structurally coupled to fast computation."* Verdict: **the unqualified
form is false**; the qualified form survives. All URLs verified HTTP 200.

Useful whenever a proposal involves persistent state, adaptation at deployment,
neuromodulation, or "the model should keep learning" — these are the mechanisms
a reviewer will say already solve it.

---

## The mechanisms, and what each actually persists

| Mechanism | Timescale | Persists | Assessment |
|---|---|---|---|
| **Fast weights** ([Ba 2016](https://arxiv.org/abs/1610.06258), [Schlag 2021](https://arxiv.org/abs/2102.11174), [Irie 2021](https://arxiv.org/abs/2106.06295)) | Per-token, decay λ≈0.9–0.95 → tens of tokens | Reset per sequence | Post-Schlag, **linear attention *is* fast-weight programming**, so Mamba-2/DeltaNet/RWKV are all fast-weight systems. Mainstream — but explicitly the FAST variable. The two-timescale split it creates is the structure being criticised |
| **Selective SSMs** ([S4](https://arxiv.org/abs/2111.00396), [Mamba](https://arxiv.org/abs/2312.00752), [Mamba-2](https://arxiv.org/abs/2405.21060)) | Per-token, learned per-channel decay Δ | Reset per sequence | HiPPO gives each channel its own decay rate — genuinely multi-timescale *within context*. But state is a deterministic function of tokens seen, never written to weights. Enriches the fast scale; adds no new one |
| **Test-time training** ([TTT layers](https://arxiv.org/abs/2407.04620), [TENT](https://arxiv.org/abs/2006.10726), [Sun 2019](https://arxiv.org/abs/1909.13231)) | Gradient step per batch/token | Mostly reset per sequence | **Closest existing thing.** Documented brittleness: error accumulation and collapse under long streams, small/imbalanced batches, mixed shift — a whole sub-literature of stabilisers exists because of it |
| **Titans** ([arXiv:2501.00663](https://arxiv.org/abs/2501.00663)) | Surprise-gated, momentum + decay | Across segments | **The strongest live threat.** Has surprise gating, momentum, and decay-as-forgetting — a genuine dynamical medium-term memory |
| **Retrieval** ([Memorizing Transformers](https://arxiv.org/abs/2203.08913), [RETRO](https://arxiv.org/abs/2112.04426)) | Indefinite | Yes | Persists, but as **inert content**. No decay, no integration, no tone/level, does not gate computation — supplies tokens to attend over |
| **NTM / DNC** ([arXiv:1410.5401](https://arxiv.org/abs/1410.5401)) | Per-timestep | Cleared per episode | Episodic scratchpad; never scaled, effectively abandoned for LMs |
| **Hypernetworks** ([arXiv:1609.09106](https://arxiv.org/abs/1609.09106)) | Frozen after training | n/a | Has the slow-gates-fast **topology** — closest structural precedent. Missing: the modulator does not evolve at deployment |
| **Learned optimizers** ([L2L](https://arxiv.org/abs/1606.04474)), [MAML](https://arxiv.org/abs/1703.03400) | Training timescale | Discarded after run | Wrong side of the gap by construction |
| **Neuromodulation-inspired ML** ([Backpropamine](https://arxiv.org/abs/2002.10585), [Vecoven 2019](https://arxiv.org/abs/1812.09113), [NMGT](https://arxiv.org/abs/2204.04297)) | Within-episode | Reset per episode | **Direct prior art.** Backpropamine genuinely implements a network-emitted global scalar gating Hebbian fast-weight plasticity, meta-learned end-to-end, beating non-modulated baselines. Small, low-citation, toy-scale |

---

## The qualified claim that survives

> Deployed neural architectures have no state variable that simultaneously
> **(i)** persists across episode/context boundaries at deployment,
> **(ii)** evolves under its own low-dimensional dynamics — integration, decay,
> homeostatic setpoint — rather than being recomputed from current input, and
> **(iii)** gates computation and plasticity rather than merely supplying
> content.

Four axes on which the survey found gaps:

- **Persistence** — SSM state, fast-weight matrices, TTT-layer state, DNC
  memory and Backpropamine traces are all zeroed per sequence/episode. Titans
  and continual-TTA are the partial exceptions.
- **Principle** — existing medium-scale mechanisms are engineering patches for
  distribution shift or long-context efficiency, not variables with committed
  semantics, homeostatic dynamics, or a specified reset policy.
- **Maturity** — TTA is documented-brittle; nothing here is a load-bearing
  component of a frontier system.
- **Coupling** — retrieval persists but is inert; hypernetworks gate but are
  frozen. Nobody has combined persistence + dynamics + gating at scale.

## Framing rules this produced

1. **Do not claim novelty for the neuromodulation framing.** Cite Backpropamine
   and Vecoven as direct prior art; position the contribution as persistence +
   principled dynamics + scale.
2. **Do not present per-sequence reset as an oversight.** It is a deliberate
   design choice. The burden is showing nobody made an *unreset* variable work,
   not that nobody thought of it.
3. **Name the live competitor.** The 2024–2026 TTT/Titans line is moving in
   exactly this direction — state explicitly what you add beyond surprise-gated
   momentum memory.

---

## Second-pass audit: the gap is narrower than the table above suggests

A follow-up survey covering agent memory, homeostatic RL and the spiking
literature found work satisfying **all three conditions**. The claim needs
scoping to *deployed, general-purpose* architectures.

### The closest work — supporting evidence, NOT a competitor

**Astrocyte-Gated Multi-Timescale Plasticity (AGMP)**, Dong & He, *Frontiers in
Neuroscience* 2026 —
https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2025.1768235/full

⚠️ **The audit subagent labelled this "the strongest live threat." That framing
was wrong, and checking the primary source is what showed it.** Despite the
neuroscience venue it is a machine-learning paper. From the abstract: an
"online learning framework" for deep spiking networks, benchmarked against
backpropagation-through-time, evaluated on N-Caltech101, DVS128 Gesture, SHD
and Split CIFAR-100. Zero occurrences of "episode" or "forward pass" in the
neuroscience sense.

**Its results support the thesis rather than pre-empting it:**

- Accuracy competitive with offline BPTT at **constant O(1) temporal memory**
- Substantially reduced catastrophic forgetting in class-incremental learning
  **without a replay buffer**
- Mechanism: a slow astrocytic variable integrates activity and multiplicatively
  modulates plasticity, suppressing updates in stable regimes while enabling
  adaptation under distribution shift

Three consequences for any proposal in this space:

1. **The mechanism is validated, not speculative.** The standard weakness of a
   glial-computation argument is that supporting results are toy-scale or
   theoretical. AGMP removes it — an astrocyte-inspired slow gate produces
   measurable gains on recognised benchmarks. Lead with this.
2. **It independently corroborates consolidation-gated learning.** Suppressing
   plasticity when the regime is stable is the same principle as
   "evict/consolidate once the slow model predicts it", reached from a
   different direction. Convergence from independent starting points is
   stronger evidence than either result alone.
3. **It narrows what remains to be shown** — extension axes, not defensive
   distinctions:

| Property | Demonstrated by AGMP | Remaining open |
|---|---|---|
| Slow variable with own dynamics | Yes — activity-integrating gate | Homeostatic setpoint with explicit decay toward a target |
| Multiplicative gating | Yes — of plasticity | Of forward computation and attention precision |
| Persistence | Within training stream | Across episode/context boundaries at deployment |
| Setting | Spiking neural networks | Dense, backprop-trained architectures |

A proposal here extends a validated mechanism along three axes. That is a
stronger and more honest position than claiming untested novelty.

### Ownership of the component ideas

| Idea | Established by |
|---|---|
| Homeostatic setpoint dynamics as reward | Keramati & Gutkin, eLife 2014 — cite the PMC mirror https://pmc.ncbi.nlm.nih.gov/articles/PMC4270100/ (elifesciences.org returns HTTP 406 to scripted requests); HRRL 2025 (https://arxiv.org/abs/2507.04998) |
| Multiplicative neuromodulatory gating of plasticity | Backpropamine (https://arxiv.org/abs/2002.10585) |
| Two-timescale intrinsic neuronal state | IP²-RSNN 2025 (https://arxiv.org/abs/2501.14539) |
| Cross-session persistent agent state | MemGPT (https://arxiv.org/abs/2310.08560), A-MEM (https://arxiv.org/abs/2502.12110), Generative Agents (https://arxiv.org/abs/2304.03442) |

### Why agent memory does not close the gap

Persistent memory for LLM agents satisfies (i) and is often described in terms
suggesting (ii). It does not satisfy it:

- **Generative Agents** applies exponential recency decay — the closest thing to
  a decay dynamic — but it scores *retrieval ranking* only. Not a
  low-dimensional state, never gates computation.
- **A-MEM's "memory evolution"** is LLM-driven rewriting of stored notes, not a
  differential update law.
- All of them **supply content into a context window**; none modulates how that
  content is processed.

### The scoped claim

> No **deployed, general-purpose** architecture satisfies all three conditions.
> The astrocyte-gated spiking line has demonstrated the slow-variable mechanism
> for plasticity gating within a training stream; extending it to forward
> computation, homeostatic dynamics and cross-episode persistence in dense
> architectures is what remains.

Novelty is claimed for the **conjunction plus deployment-time cross-episode
persistence with wall-clock constants** — not for homeostatic setpoints
(Keramati & Gutkin own that) nor multiplicative neuromodulatory gating
(Backpropamine owns that) nor astrocyte-gated plasticity itself (AGMP
demonstrated it).

---

## Process lesson

An audit dispatched with "find what threatens this thesis" returns threats,
because that is the frame it was given. It does not evaluate whether adversarial
framing is the right one. **Open the primary source before writing positioning
prose** — venue is not field, and the nearest work is as likely to be supporting
evidence as competition.
