# OCR cascade, cost tables and corpus sizing

Merged in from `document-corpus-ingestion` and `corpus-ingestion-architecture`
(2026-09-27). Use with SKILL.md §1–§5: this file carries the worked numbers
and the confidence-routed alternative to one-pass vision.

## When the cascade is right, and when it isn't

SKILL.md §4 recommends one-pass vision for most archives, because stamps,
seals, redactions, photographs and marginalia are content. The cascade below
is the right design when they aren't: typed text is what matters, or budget
rules out a vision pass over every page. Existing OCR (SKILL.md §1) feeds
stage ① here; under one-pass vision it is a quality benchmark instead. Say
which architecture a cost figure assumes.

```
① cheap/self-hosted OCR on 100%  → text + per-word CONFIDENCE + BBOX
② route by confidence:  high → accept     low → VLM re-read
③ entity/relation extraction only on pages that survive filtering
④ embeddings only on surviving chunks
```

The confidence score is what makes it affordable: the OCR engine says where
it struggled, so escalation lands on degraded carbon copies and stamped pages
(near 5%) while clean typescript passes through. Without it you pay VLM rates
on everything.

A useful property of real archives: typed body text OCRs well while margins,
routing stamps, handwriting and classification markings OCR terribly. Sampled
word plausibility on a 1950s–70s government corpus ran 93.2% (range 90–97%).
That also means an archive can post excellent headline accuracy with near-zero
recall on the annotations a researcher wants. Report both.

## Worked cost table (13M pages; re-derive from live prices)

| Approach | $/1k pages | Total |
|---|---|---|
| Self-hosted OCR (GPU box, ~25 pg/s) | — | ~$116 (~144 h) |
| Commercial OCR, basic tier | 1.50 | $19,500 |
| Commercial OCR, high-volume tier | 0.60 | $7,800 |
| Cheap VLM on 100% of pages | ~0.42 | $5,460 |
| Mid-tier VLM on 100% | ~9.60 | $124,800 |
| Frontier VLM on 100% | ~16.00 | $208,000 |
| Commercial forms+tables parser | 65.00 | $845,000 |

VLM per page ≈ `(input_tokens/1e6 × $in) + (output_tokens/1e6 × $out)`; a page
image plus text runs roughly 1,200 in / 400 out. The ratios age; the method
doesn't.

The counterintuitive result in a commercial-OCR cascade:

```
commercial OCR on 100%   $19,500
VLM re-read of hard 5%      $273   ← 1.4% of the bill
```

The per-page OCR floor is the whole cost, so the lever is not which model but
not paying per page for OCR. Self-hosting the first pass takes the pipeline
from ~$20k to ~$1k. Users expect VLM cost to dominate and will optimise the
wrong term unless told. Under one-pass vision, the equivalent point is that
cost is nearly flat in GPU count: covering every page rather than the hard
~45% was ~$1,500 more on a 12M-page corpus.

## Pilot pricing

| Scope | Pages | Est. |
|---|---|---|
| One program | 20,000 | ~$34 |
| One large program | 90,000 | ~$151 |
| 1% sample | 130,000 | ~$218 |

## One-pass vision: extra checks

- Ask the schema for a `visual_elements` array and a per-page `legibility`
  score. Mean `visual_elements` per page is the honest test of whether vision
  earned its cost; near zero means it didn't.
- Deterministic grounding check: every extracted entity name must appear in
  that page's transcription. Ones that don't are hallucinations wearing a
  citation.
- Audit low-legibility pages with long transcriptions against the image.

## Sizing the corpus honestly

- Report a confidence interval and the share measured, e.g. "4.00 ± 0.18
  pages/item, n=24,154 (9% of corpus) → ~1.10M pages, CI 1.05–1.15M".
- State coverage against the advertised total: "8.5% of the stated 13M pages"
  is a usable scope; "all the documents" would be a lie.
- Item counts are not page counts. "13M pages" and a mirror holding "262,906
  items" are not comparable, and neither confirms the mirror is complete.

## Hosted answer engines are not a shortcut

"Can't I just use a search/answer API that already ingested this?" For a
scanned corpus, no: they search the live web with no ingestion endpoint, do
worst on image-only PDFs, and return unreliable citation arrays. Any "cite the
exact PDF page" requirement rules them out. State the structural reason.

## Transport and bot-wall traps

- **Bot-walled hosts return identical bytes** for a real document, a
  collection page and `sitemap.xml`. Compare `size_download` for a real and a
  deliberately invalid URL; if they match you learned nothing.
- **`curl` returning `000`** on archive URLs usually means spaces or commas in
  an unencoded filename. The request never formed; don't add retries.
- **Constrained decoding** (`guided_json` in vLLM, `response_format`
  json_schema) guarantees shape, not truth. Keep grounding and range checks.
