# Vetting a user-named third-party model before putting it in a PRD

When the user says "integrate <model> for <use>" (e.g. "TRIBE v2 for A/B
testing of human attention"), don't design the integration first. Answer
three questions from primary sources, then decide whether it is a production
component or a research track behind a gate.

## The three questions

| Question | Where to look | What to capture |
|---|---|---|
| 1. What license covers the weights and code? | The repo README "License" section, the HF model card, and the license legal code itself | Exact license ID. For NC licenses, quote the legal definition. Also check the licenses of **upstream dependencies** (e.g. a gated LLM used as a feature extractor) |
| 2. What does it actually output? | README quick start (the output shape), the paper abstract | Units and resolution of the output. Whether it predicts an average subject or a specific person. Input modalities it actually accepts |
| 3. Has anyone independently tested it for this use? | arXiv search for "<model> does not / fails / predicts <behavior>"; aggregator topic pages (e.g. emergentmind.com/topics/<model>) that list follow-on papers | Effect size with CI, baselines it was compared against, the authors' own stated limitations |

Tell the user if a named metric (e.g. "attention") isn't what the model
measures. That mismatch is the most common way these requests go wrong.

## Design pattern when any answer is unfavourable

1. **Ship the parts that don't depend on the model.** Keep the model out of
   Phase 1.
2. **Blocking gate table:** each question, the finding, whether it is Class A
   (sourced) or Class B (inference), and who decides (counsel, the vendor,
   leadership). No client-facing output until the gate passes. Say plainly
   that this is not legal advice.
3. **Validate against the platform's own ground truth.** For Amazon listing
   creative that is Manage Your Experiments (MYE). Log each experiment's pair
   and winner, then:
   - pre-register the candidate scores before looking at outcomes;
   - include cheap baselines (image statistics, an LLM rubric, a licensed
     commercial tool);
   - use pairwise accuracy against a 50% null.
4. **Pairs needed** (one-sided test, α=0.05, power 0.8):

   | Accuracy to detect | Pairs |
   |---|---|
   | 70% | 37 |
   | 65% | 67 |
   | 60% | 153 |

   Formula: `n = ((z_a*sqrt(p0(1-p0)) + z_b*sqrt(p1(1-p1)))/(p1-p0))^2`,
   with p0=0.5, z_a=1.6449, z_b=0.8416.
5. **Decision rules:** beats baselines → limited pilot (still gated); ties
   baselines → use the cheaper baseline; ties chance → drop it and record the
   null internally.
6. **Commercial fallback:** a vendor licensed for commercial use, judged by
   the same scorecard, trialled only after enough ground-truth results exist.
7. **Guardrails:** scores labelled "predicted"; no implied endorsement by the
   licensor (CC licenses explicitly grant none); a compute budget and stop
   rule set before any GPU run.

## Worked finding: TRIBE v2 (Meta FAIR), checked Sep 2026

- License: CC BY-NC 4.0 (github.com/facebookresearch/tribev2,
  huggingface.co/facebook/tribev2). The text encoder is LLaMA 3.2-3B, which is
  gated under the Llama 3.2 Community License.
- Output: average-subject fMRI predictions on fsaverage5 (~20k vertices),
  offset 5 s for hemodynamic lag. Inputs are video, audio and text; static
  images must be converted to short still videos. Video patch tokens are
  averaged, so it cannot produce spatial attention heatmaps.
- Independent test: arXiv:2607.01400 found its predicted signal did not track
  YouTube "most replayed" heatmaps (partial r=+0.058, 95% CI [−0.04, 0.15]),
  no better than loudness/motion baselines.
- Its subcortical predictions are 2–3× weaker than its cortical ones, and the
  nucleus accumbens (the region with the best neuroforecasting evidence,
  Knutson & Genevsky 2018) is subcortical.
- Result: a gated research track, not a deployable A/B metric.

## Adjacent pattern: ad analytics PRDs for inventory-owning sellers

When the company owns inventory, rank PPC recommendations by contribution
margin, not ROAS:

- `CM = price − landed COGS − fees − fulfilment`
- break-even ACoS = CM ÷ price
- target ACoS = (CM − required margin) ÷ price

Show a worked example where a term that passes a flat ACoS rule loses money.
Scoring and joins belong in the warehouse; Apps Script only drives the review
Sheet and bulk export. Treat branded spend as a question for a controlled
pause test, not something to read off a report.
