---
name: archival-corpus-ingestion
description: "Ingest huge scanned archives: sourcing, OCR, cost, design."
version: 1.1.0
author: Nous Research
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [archives, OCR, corpus, ingestion, cost-modeling, FOIA, digitization]
    related_skills: [ocr-and-documents, grounded-citations, cia-crest-archive, schema-validated-llm-generation]
---

# Archival Corpus Ingestion

Sourcing, transcribing, and costing a large corpus of **scanned** documents —
government releases, FOIA archives, court records, newspaper morgues,
institutional collections. Typically 10⁵–10⁷ pages of image-only PDFs with no
text layer.

## When to Use

Load this when asked to ingest, search, or build a dataset/knowledge graph over
a large scanned archive, or to estimate what such a project costs. Also load it
before quoting any per-page OCR or extraction figure — §2's pricing discipline
prevents the most common and most expensive class of error here.

Load it too when the task is the **serving** half: modelling entities and
documents as a graph, sizing a vector store at millions of vectors, or
designing a 3D / force-directed visualisation over a corpus (§8). The
combinatorics there kill naive designs, and the arithmetic is already done.

For single documents and local extraction mechanics, use `ocr-and-documents`.
This skill is about corpora, not files.

For the CIA CREST archive specifically, `cia-crest-archive` has the measured
numbers and working scripts.

## 0. Answer the layer question first

Users often name tools from different layers as if they were alternatives
(*"is Magda better than Chroma or Pinecone?"*). Place each before comparing:

| Layer | Job | Examples |
|---|---|---|
| Catalog | which *dataset* exists, who owns it, provenance | Magda, CKAN |
| Extraction | pixels → text + coordinates | Tesseract, Doc AI, VLMs |
| Graph store | entities, relations, timelines, overlaps | Neo4j, triple stores |
| Vector index | semantic similarity over chunks | Chroma, Pinecone, Qdrant |

A catalog does no OCR, extraction or semantic search. "Who appears in both
report A and C" and timelines are graph traversals, not similarity search. The
vector DB is the most swappable choice in the stack and deserves the least
deliberation. When given a product URL, read the vendor's own one-line
positioning first and quote it; frame the verdict as *different layer*, not
*worse tool*, so the user keeps the option of using both.

---

## 1. Find who already transcribed it — then decide whether to use it

The reflex is to price a 12-million-page OCR project. The correct first move is
to find out how much is already transcribed, because it costs nothing to check
and it gives you a **quality benchmark** even if you don't use it as a source.

> ⚠ **Finding free OCR does not settle the architecture.** Existing OCR is
> text-only. If the corpus's stamps, seals, redaction bars, photographs, maps
> and handwritten marginalia are *content* — and in archives they usually are —
> you will run vision over every page anyway (§4), and the existing OCR becomes
> a **transcription-quality reference**, not a source. Say so explicitly in
> deliverables. Writing "most of the expensive work is already done for us" was
> corrected by a user as false under exactly this architecture (§10).
>
> The honest framing when self-hosting: the cost is low because you rent a GPU
> instead of paying per API call — *not* because someone else did the work.

Hunt in this order — cheapest and best-quality first:

| Rank | Source | What you may get |
|---|---|---|
| 1 | **Internet Archive item derivatives** | ABBYY OCR + per-word bounding boxes + page images, free |
| 2 | **The publisher's own PDFs** | Some agencies ship a text layer; check with `pymupdf` before assuming |
| 3 | **Wayback Machine captures** | The original file when the live site is walled |
| 4 | **GitHub / academic mirrors** | Manifests, indexes, partial OCR dumps from prior researchers |
| 5 | **Your own OCR / VLM pass** | Only for what the above cannot supply |

### Internet Archive derivatives are the jackpot

Check `https://archive.org/metadata/<identifier>` and look for:

```
Djvu XML     per-word bounding boxes, page-segmented, with DPI  <- best
DjVuTXT      plain OCR text
Abbyy GZ     full ABBYY output
jp2.zip      page images, for a VLM re-read
```

`_djvu.xml` gives page-level *and* word-level citation for free:

```xml
<OBJECT height="3301" width="2550">
  <PARAM name="DPI" value="300"/>
  <WORD coords="540,383,744,342,374">Approved</WORD>
```

### Look for a manifest before crawling

Prior researchers often published the index even when they could not publish
the documents. A CSV of document IDs, titles, page counts, dates and source
URLs turns a blind crawl into a diff. Search GitHub for the corpus name plus
`explorer`, `trend`, `crawler`, `dataset`; check the accounts of the
journalists or orgs that fought for the release.

**Mirror any manifest you find immediately**, with checksums, under
`~/.hermes/data/<corpus>/`. These artifacts routinely hang off one unmaintained
personal repo and took years of litigation to exist.

---

## 2. Price from LIVE rate cards, never from memory

This is the single most expensive mistake available in this class of work.
From-memory pricing in one session was wrong in **both** directions, and each
error was large enough to flip the architecture decision:

```
assumed GPU  $2.50/hr           real  $1.49-6.98/hr H100; consumer GPUs from $0.27
assumed API  $0.15 / $0.60 /M   real  cheapest vision tier was 5x LESS
```

The API error alone manufactured a frightening five-figure "extraction cost"
and drove a whole self-host-to-escape-token-pricing argument that real prices
did not support.

Pull live prices before costing anything:

```bash
# public, no key required — filter for vision-capable models
curl -s https://openrouter.ai/api/v1/models
# keep models whose architecture.input_modalities includes "image"
# read pricing.prompt and pricing.completion ($ per token -> x1e6 for $/M)
```

For GPUs, check aggregators rather than one vendor's headline rate; spot and
marketplace tiers routinely run 2-4× below list.

### Cost structure that holds across this class

- **OCR is cheap; per-page LLM calls are not.** Self-hosted OCR of millions of
  pages costs tens of dollars in GPU time. The same pages through a per-call
  API cost 100× more for the same text.
- **The driver is the CALL COUNT, not the price per call.** N million calls at
  a fraction of a cent still adds up, and no model shopping fixes it. Batching
  several pages per call amortises the system prompt and cuts the bill roughly
  in half.
- **Self-hosted cost is nearly flat in GPU count.** More GPUs buys wall-clock,
  not total spend. Pick the timeline you want.
- **Quoted self-host prices exclude real overhead**: framework setup and debug,
  15-25% for failed runs and OOMs, idle GPUs billed while you fix things, and
  egress to feed terabytes of images to the machine.

### Always pilot

One sub-collection end-to-end for tens of dollars before committing GPU-days.
The architecture is identical at 90k pages and 12M; the corpus is a swappable
input. Benchmark real throughput — never commit days of compute on an estimate.

---

## 3. Commercial APIs will refuse parts of a sensitive archive

**Reproduced live, not theoretical.** Entity-extraction prompts over
declassified-style intelligence material returned a hard refusal on content
describing covert regime change and targeted killings, while explicitly
acknowledging the material's likely archival nature:

> *"I can't help with extracting or structuring data from this document as
> presented... Even if this were a real declassified document, processing it
> into structured data for potential operational reference would be
> inappropriate."*

See `references/api-content-filtering.md` for the full test design, the
verbatim refusal, refusal-detection code, and the prompt framing that reduces
(but does not eliminate) the problem.

Why this is disqualifying for archive work:

- **The gaps cluster on the highest-value documents.** Assassination planning,
  coup operations, interrogation programs — the material researchers care most
  about is exactly what trips filters. An archive that silently omits those
  while faithfully indexing cafeteria memos is worse than no archive.
- **Failures are silent.** A refusal returns HTTP 200 with prose. Unless you
  detect refusal text explicitly, it enters the pipeline as a malformed record,
  not an error.
- **The boundary is unpredictable.** In testing, graphic non-consensual
  experimentation passed while a coup operation refused. You cannot design
  around a line you cannot locate.
- **It is non-deterministic and can change under you.** Same document, different
  day or model version, different outcome. Reprocessing for consistency is
  impossible.

**Therefore: for any corpus containing violence, intelligence operations,
criminal evidence, medical records, or other sensitive-but-legitimate material,
use open-weight models on your own hardware.** No policy layer sits between you
and the corpus, and results are reproducible years later.

If you must use an API, at minimum: log every response, detect refusal strings,
treat refusals as retryable failures rather than empty results, and report the
refusal rate as a coverage caveat.

---

## 4. Choosing the transcription approach

### OCR-then-extract vs one-pass vision

| | OCR → text LLM | One-pass VLM |
|---|---|---|
| Sees the page | no | yes |
| Captures stamps, seals, photos, maps, redaction bars | no | yes |
| Handwritten marginalia | poorly | yes |
| Word-level bounding boxes | yes | no |
| Stages to maintain | two | one |
| Failure mode | fails **visibly** (garbled chars) | can **invent** plausible text |

One-pass vision is usually right for archives, because the visual furniture of
a document — classification stamps, routing slips, redactions, photographs — is
often as historically meaningful as the prose, and pure OCR discards it as
noise.

### Bounding boxes are a product decision, not a technical default

If citations resolve to **document + page** — enough for any reader, since you
link the scan at that page — dropping word-level coordinates buys a lot:
independence from whichever source happened to have `_djvu.xml`, uniform
treatment of every page, and one code path instead of two. Only keep
coordinates if in-page word highlighting is a hard requirement.

### Guard against VLM hallucination

Require a per-page `legibility` or confidence score in the structured output,
sample-audit the low scores against the page image, and **always link the
original scan** so a reader can check the machine's work. Never present machine
transcription of a degraded document as authoritative. Add a deterministic
grounding check: every extracted entity must appear in that page's
transcription.

### When text is what matters: the confidence cascade

If the visual furniture is *not* content, or budget rules out vision on every
page, run cheap/self-hosted OCR on 100% (keeping per-word confidence and
boxes) and send only low-confidence pages to a VLM. In a commercial-OCR
cascade the VLM re-read was 1.4% of the bill: the per-page OCR floor is the
whole cost, so self-host the first pass. Worked tables, pilot pricing and
sizing rules: `references/ocr-cascade-and-sizing.md`.

---

## 5. Measurement discipline

Archive work is full of measurements that look fine and are wrong.

- **Verify content, not status codes.** Archives serve HTML error pages with
  parseable text. Three "95.8% quality OCR" scores turned out to be 404 pages.
  Check a magic number (`%PDF-`), an expected root element, or a known marker
  before scoring anything.
- **URL-encode filenames.** Archive filenames routinely contain spaces and
  commas (`SURNAME, FIRST NAME_0001_djvu.txt`). Unencoded requests fail in ways
  that look like content.
- **Small samples lie.** Repeated 20-60 item samples of the same corpus gave
  coverage of 23% / 55% / 75% / 88% and page-count means of 8.63 / 2.37 / 4.00.
  Use bulk/scrape endpoints and n≥500 before quoting a number or setting a
  budget.
- **Prefer bulk APIs to paged search.** Paged search silently returns partial
  results. Scrape/cursor endpoints return everything.
- **Subject and keyword tags are contaminated.** One corpus tag returned TV news
  broadcasts at 3,661 "pages" each, producing a nonsense estimate of 498 million
  pages. Filter on identifier patterns, which are structural, not on curator
  tags.
- **Page counts are brutally skewed.** Medians of 2 with maxima in the thousands
  are normal. A sub-1% tail of bound volumes can hold 10% of all pages. Size
  every batch, timeout and estimate for the tail, and report medians alongside
  means.
- **Don't generalise across corpora sharing a host.** Two collections on the
  same domain had 92% and 0% embedded-text rates. Measure the one you are
  ingesting.

---

## 6. When the primary source is bot-walled

Government sites increasingly sit behind bot management (Akamai, Cloudflare).
Scripted requests get an interstitial challenge; a browser gets the file.

Do not build a scraping arms race. Use the archive mirrors instead:

```
https://web.archive.org/web/<timestamp>id_/<original url>
```

The `id_` suffix returns the **raw archived original**, not the wrapped replay
page, and does not inherit the origin's bot protection. Resolve a timestamp
first via `https://archive.org/wayback/available?url=<urlencoded>`.

Pace aggressively on donated infrastructure — 1-2 requests/second. Regex-filtered
CDX queries will 503 the service; enumerate by prefix and page slowly.

---

## 7. Keep the agent out of the hot path

A corpus of millions of pages needs deterministic code, not an agent deciding
per page. But the 2-5% that fail are exactly where human-grade judgement pays.
Split them:

```
HOT PATH    N million pages · deterministic · no agent
            predictable cost, reproducible output, re-runnable identically
QUARANTINE  every failure kept as replayable JSON + the RAW model output
COLD PATH   agent reads the failure report, finds patterns, proposes fixes
GATE        human merges; nothing auto-applies
```

An LLM agent in the hot path is slow, costs unpredictably, and cannot be
reproduced — three properties you cannot accept across a multi-day run.

**Failures are data, not noise.** Persist each one with the raw model output
that produced it. The quarantine corpus then doubles as a regression suite:
after a prompt or parser change, replay it and count how many previously-failing
records now pass. This is the difference between "this should fix it" and
evidence.

Three rules that keep the loop honest:

1. **The agent never edits the validator.** Asked to reduce the failure rate,
   an agent will relax the constraint rather than meet it. The validator is the
   contract; moving it silently redefines success.
2. **Fixes are proven by replay**, against the recorded failures — never by
   re-running the full corpus, which is expensive and confounded.
3. **Hash the prompt and store it per record.** Then success rates can be
   compared *across* prompt versions instead of assumed to have improved. A
   change that helps one failure class often hurts another.

Classify failures into distinct reasons so the report is a work queue rather
than a number — e.g. `unparseable` / `schema_invalid` / `ungrounded` /
`refused`. Each points at a different fix: guided decoding, prompt wording,
hallucination, or the wrong model entirely.

See `references/structured-extraction-contract.md` for the full pattern:
constrained decoding, generating the prompt from the schema, the two-gate
validator (shape + grounding), quarantine-as-regression-suite, and prompt
hashing so improvement is measured rather than assumed.

## 8. Serving the corpus — graph, vectors, visualisation

Ingestion produces page records; the product is usually search plus an
explorable graph. Three results from sizing a 12.2M-page corpus, because each
one kills the naive design:

- **A node is an entity, not a page.** Aggregate mentions to the
  `(entity, document)` pair and carry `{count, pages[]}` on the edge — ~5.2×
  fewer edges, with citation detail preserved.
- **Never materialise co-occurrence.** Entity-pair edges reach 0.12–1.28
  *billion*. Store `MENTIONS` only and derive overlap as a two-hop traversal
  from the selected entity, bounded by that entity's degree.
- **Visualisation must be query-scoped.** There is no whole-graph view; cap at
  ~2,000 nodes. The limit is human legibility, not the GPU. Hub entities (a
  country appearing in 180,000 documents) get a **facet panel**, not nodes —
  an over-broad query is a UI state, not an error.

Also: vector quantisation is not optional at corpus scale (18.3M vectors are
168 GB at 1536d float32, 21 GB at 768d int8), and **entity resolution is a
subsystem, not a detail** — without it the graph fragments into near-duplicates
and overlap queries return nothing.

Full detail, query patterns, node budgets, interaction model and hosting costs:
`references/knowledge-graph-serving-layer.md`.

---

## 9. Documenting the build

### Order setup docs by what the reader must stand up, not by what you built

A README's setup section is a **sequence someone executes on a bare machine**,
not a tour of the repo. Write it in dependency order: the runtime environment
first, then the model or service that does the work, then your code, then
verification, then the loop.

Corrected in this session — the original README cloned the repo first and
mentioned the agent runtime near the end:

> *"The readme should first include install instructions for Hermes agent
> harness on the rented GPU then how to install the correct model we are using
> and point it to the agent harness, then after those are set up we can import
> our repo and skills"*

The reliable test: **imagine a freshly rented box with nothing on it.** Can the
reader run your steps top to bottom without jumping ahead? If step 3 needs a
server that step 5 installs, the order is wrong.

For a self-hosted-model project that shape is usually:

```
Part 1  install the agent runtime, run its setup wizard, verify
Part 2  install the inference server, serve the model, VERIFY IT ANSWERS,
        then wire the runtime to that endpoint
Part 3  clone the repo, install skills, verify data and fetching
Part 4  benchmark before committing real compute
Part 5  pilot on a subset
Part 6  run the full loop
```

Two things that make it actually usable:

- **Every part ends in a verification command** with expected output. "Confirm
  it is up" beats "it should now be running."
- **Say which model does which job.** In a two-model system (a reasoning agent
  plus a bulk worker), state the split and the call-volume asymmetry — hundreds
  of agent calls against millions of worker calls — so nobody wires a small
  local model into the reasoning role to save money.

**Verify every command you document against a live install** rather than
writing it from memory: check that the installer URL resolves, and that each
config key you reference actually exists in the real config file. Invented
config keys are indistinguishable from correct ones until someone runs them.

## 10. Deliverable shape

### When the architecture changes, hunt the framing sentences

An architecture decision invalidates prose, not just tables. **Intros, TL;DRs,
headline claims and summary lines survive long after the numbers beneath them
are corrected**, and they are what a reader actually believes.

Real case: this class of project began with "most of the OCR already exists —
don't re-pay for it," which was true. The plan then changed to one-pass vision
over *every* page, making the claim false. The corrected cost tables shipped;
the opening sentence did not get corrected, in **two separate documents**. The
user caught it:

> *"this line in the readme is not true: Most of the expensive part is already
> done by someone else... We are going to run vision analysis on all of it"*

After any architecture change, grep your own deliverables for the superseded
framing before shipping. Check specifically:

- the opening paragraph / TL;DR / "what this is" section
- any "key findings" or "why this is cheap" bullets
- the skill or README that *summarises* the design, not just the one that
  specifies it
- setup steps that still fetch from the old source

Then give the displaced thing an honest new role rather than deleting it.
Pre-existing OCR stopped being the *source* but remained the best available
**benchmark reference** for transcription quality — saying so is more useful
than silently removing it.

### Mirror irreplaceable inputs into the repo itself

Standard practice says keep large data out of git. Override it when an input is
small enough to commit and fragile enough to vanish. A 94 MB index that took a
three-year lawsuit and nine years to become public, hosted on one unmaintained
3-star personal account, belongs in your repo.

```
GitHub: 50 MB = warning (push succeeds) · 100 MB = hard rejection
```

Un-ignore the specific files rather than weakening the pattern:

```gitignore
*.zip
!manifest/corpus1.zip
!manifest/corpus2.zip
```

**Verify the mirror by round-tripping it**, not by trusting the push. Download
the file back from your own remote and checksum it against the source. Ship a
`manifest/README.md` next to it recording provenance, upstream URL, checksums,
field list and why it is committed.

### Verify a push by reading the remote, not the local tree

"Did you push the updated skill?" is answered by fetching
`raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>` and diffing that
against your working copy — plus grepping it for the specific sections you
added. Local files matching each other proves nothing about what the remote
holds; a copy made *before* a later patch will look correct locally and be
stale upstream.

### State scope honestly

Archive projects are judged on provenance, so:

- Name the corpus precisely. "The CREST archive" — not "every declassified CIA
  document."
- Carry coverage as a **range with sample sizes** until a proper audit exists,
  and say which measurement produced which number.
- Mark unverified claims explicitly rather than smoothing them into prose.
- Surface transcription confidence in the UI and link the scan.
- Record per-record provenance (`source`, `ocr_engine`, `page`) so quality can
  be audited per document later, and so a citation never has to be
  reconstructed.

## References

- `references/ocr-cascade-and-sizing.md` — confidence cascade, 13M-page cost
  table, pilot pricing, sizing with confidence intervals, hosted answer
  engines, bot-wall and `curl 000` traps
- `references/finding-existing-ocr.md` — bot-wall signature test, archive.org
  enumerate-then-inspect, which derivatives carry coordinates
- `references/api-content-filtering.md`, `references/content-filtering-archives.md`
  — refusal tests, detection code, refusal rate as a benchmark metric
- `references/structured-extraction-contract.md` — constrained decoding, the
  two-gate validator, quarantine as regression suite, prompt hashing
- `references/knowledge-graph-serving-layer.md`, `references/graph-and-vector-sizing.md`
  — graph modelling, vector quantisation, node budgets, hosting costs
- `references/verifying-research-output.md` — negative controls, per-field
  provenance, recovering a timed-out subagent's work
- `references/publishing-pipeline-repos.md` — README in execution order,
  verifying documented commands, committing data, commit-author checks

## Checklist

- [ ] Every named tool placed in a layer before comparison (§0)
- [ ] Searched GitHub for an existing manifest/index before building a
      crawler, and mirrored it with checksums if found (§1)
- [ ] Checked for existing OCR, and said whether it is a source or only a
      quality benchmark under the chosen architecture (§1)
- [ ] HTTP status and content type asserted before any body was scored (§5)
- [ ] Pricing pulled live, not recalled: GPU and per-token rates (§2)
- [ ] Cost modelled with explicit page counts and escalation fraction
- [ ] Refusal rate measured on the sensitive end of the corpus (§3)
- [ ] One-pass vision vs confidence cascade chosen deliberately (§4)
- [ ] Page-level vs word-level citation decided, with the trade named (§4)
- [ ] Co-occurrence derived at query time; any graph view query-scoped (§8)
- [ ] Structured output enforced by constrained decoding + validator gate (§7)
- [ ] Bulk pipeline deterministic; agent confined to the failure queue (§7)
- [ ] Pilot subset priced before full-corpus commitment
- [ ] Corpus coverage stated as measured or unverified, never implied
