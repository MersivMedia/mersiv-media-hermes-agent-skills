# Verified claim corrections — neuroscience/cognition figures

Quantitative claims checked against primary sources during a brain-inspired AI
review. Several are widely repeated in secondary literature with numbers that do
not appear in the cited paper. All URLs verified (PubMed returns 203, not 404).

Use these values directly rather than re-deriving them. If extending this file,
keep the format: claim as commonly stated, verdict, accurate value, source.

---

## Cognition / psychology

### Mental rotation — Shepard & Metzler 1971, *Science* 171:701–703
[PDF](https://facultypsy.hope.edu/psychlabs/exp/rotate/readings/ShepardMetzler_1971.pdf)

| Common claim | Verdict | Reality |
|---|---|---|
| RT linear in angular disparity, `r ≈ 0.99` | **CORRECTED** | **No correlation coefficient of any kind appears in the paper.** It reports a significant linear component (p<.001) in all 16 subject × rotation-type regressions, with no significant quadratic or higher-order effects (p>.05). The `r = .99` is a later textbook accretion |
| Rotation rate ~60°/s | **CONFIRMED** | Verbatim: "roughly 60° per second". Note both hedges — "roughly", and "these particular objects". An order-of-magnitude estimate, not a constant |
| Depth slope indistinguishable from picture-plane | **CORRECTED** | Depth RT was "if anything, somewhat *shorter*" at large angles, dismissed as "of doubtful significance" because absent or reversed in 4 of 8 subjects. No per-condition slopes published. This is a failure to find a difference, not demonstrated equality |

Other figures from the paper: mean RT ~1 s at 0°, rising to 4–6 s at 180°;
"different" pairs averaged 3.8 s; 3.2% error rate; 8 subjects × 1600 pairs.

### Aphantasia

| Common claim | Verdict | Reality |
|---|---|---|
| Prevalence 1–4% | **CORRECTED** | ~0.9–1.2% for strict aphantasia ([Wright et al. 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11518826/), pooled n=9,063; Study 1 n=3,049 → 1.2%). ~0.7–0.8% under the strictest VVIQ=16 criterion (Dance et al. 2022). The ~4% upper bound only holds if hypophantasia is folded in |
| Aphantasics perform mental rotation "at normal levels" | **MATERIALLY REVISED** | [Kay, Keogh & Pearson 2024](https://pubmed.ncbi.nlm.nih.gov/38657474/): **slower but more accurate** than controls on both block-shape and manikin tasks. Both groups show the classic linear RT increase with angle. Controls favour object-based rotation; aphantasics favour analytic/feature-counting strategies. [Pounder et al. 2022](https://pubmed.ncbi.nlm.nih.gov/35180481/) (n=20 vs 20 matched): no accuracy differences; RT difference confined to the most severe subgroup (VVIQ=16) |

**Safe claim:** aphantasics reach normal-to-superior *accuracy* via analytic
rather than depictive strategies, at a speed cost. This is **strategy
substitution, not equivalence** — it does not license "imagery is functionally
irrelevant". Getting this wrong reverses an architectural argument.

### Image scanning — Kosslyn, Ball & Reiser 1978
[record](https://psycnet.apa.org/record/1979-00241-001)

Linearity **CONFIRMED** from the primary abstract: more time to scan further
distances across visual images, even with equal intervening material (4
experiments, 61 subjects). The frequently-quoted `r = .97` could only be
verified in secondary sources — cite the linearity without a coefficient unless
you pull the primary PDF.

Standing caveat: Pylyshyn's task-demand critique shows the effect can be
abolished under non-imagery instructions, so it is not a pure architectural
signature.

---

## Cellular neuroscience

### Glia-to-neuron ratio

**The 10:1 ratio is an unsourced consensus error**, explicitly debunked.

- [Azevedo et al. 2009](https://pubmed.ncbi.nlm.nih.gov/19226510/) (isotropic
  fractionator, adult human): **86.1 ± 8.1 B neurons vs 84.6 ± 9.8 B
  non-neuronal cells → ≈1:1**. Only 19% of neurons are in cerebral cortex
  despite cortex being 82% of brain mass.
- [von Bartheld et al. 2016](https://pubmed.ncbi.nlm.nih.gov/27187682/):
  ratio **less than 1:1**, total glia under 100 billion (histological range
  40–130 B).

Never write "glia outnumber neurons" brain-wide. Ratio is region-dependent —
above 1 in cortical white matter, far below 1 in cerebellum.

### Astrocyte synapse coverage — split by species

[Oberheim et al. 2009](https://pubmed.ncbi.nlm.nih.gov/19279265/)

```
rodent    ~20,000-120,000 synapses per protoplasmic astrocyte   (10^4-10^5 ✓)
human     up to ~2 x 10^6                                        (~20x rodent)
```

Human astrocytes are **2.6× larger in diameter with 10× more GFAP+ primary
processes**. Using the rodent figure for human understates by ~20× — and in a
brain-inspired argument, understates in the direction that *weakens* your case.

### Astrocytic calcium

| Quantity | Value |
|---|---|
| Ca²⁺ wave propagation, human cortical slice | **36 µm/s** (Oberheim 2009) — ~4× faster than rodent |
| Rodent / cultured astrocyte | ~8–20 µm/s (Cornell-Bell 1990) |
| Transient rise / decay constants | **UNVERIFIED — do not print a number** |

Kinetics are strongly compartment-, indicator- and state-dependent (soma vs
endfoot vs microdomain; OGB vs GCaMP6; anaesthetised vs awake). Safe qualitative
claim only: seconds-scale, 1–2 orders of magnitude slower than action
potentials. For a specific constant, pull a compartment-matched primary source
(Bindocci 2017 *Science*; Srinivasan 2015 *Nat Neurosci*).

### Neuromodulator and plasticity timescales

**Dopamine phasic burst** — [Schultz 1998](https://pubmed.ncbi.nlm.nih.gov/9658025/),
*J Neurophysiol* 80:1–27. The abstract confirms phasic activation qualitatively
but contains no millisecond values. Standard full-text figures: ~70–100 ms
latency, burst <200 ms (2–5 spikes), striatal DA transient ~200–600 ms. Cite as
"~100–200 ms phasic burst, sub-second transient" — do not attribute a precise
number to the abstract.

**BTSP eligibility window** — [Bittner et al. 2017](https://pubmed.ncbi.nlm.nih.gov/28883072/),
*Science* 357:1033–1036. "Seconds-long" is **CONFIRMED verbatim**, but the
crucial qualifier is usually dropped: the window is **asymmetric and spans
seconds both before *and after*** the plateau potential, potentiating inputs
that were "neither causal nor close in time" — explicitly non-Hebbian. Commonly
quoted kernel ~±2–4 s; fitted constants (~0.7 s rise, ~1.7–2 s decay) come from
follow-up modelling (Milstein et al. 2021), not Bittner's abstract.
