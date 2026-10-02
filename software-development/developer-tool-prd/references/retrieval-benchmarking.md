# Benchmarking a retrieval / RAG tool at realistic scale

From the jev-rag build (2026-09-30). These are two benchmarks the user asked for
after v1 shipped: "run more tests with larger document sizes and more queries",
then "let's try messy documents". The scripts live in the tool's repo
(`scripts/bench_wiki.py`, `scripts/bench_messy.py`). Below is the method plus the
traps that skewed results the first time around.

## Dataset design (scored by machine, no human labelling)

- **Answerable questions carry a verbatim evidence span.** The question model gets one
  paragraph and returns `{question, answer, evidence}`, where `evidence` is an exact
  quote. A "hit" means a returned passage contains that span: a normalised substring
  check, falling back to a longest-common-run of at least 80% of the span. This needs
  no LLM judge, so verdicts are deterministic.
- **Spread question sources across each document.** Sample paragraphs from the start,
  middle and end, and record `para_index / n_paras`. Otherwise every question comes from
  the lead section and the test only measures the easy part.
- **Unanswerable questions come from held-out documents that are related but never
  ingested.** Examples: Apollo 12 against an Apollo 11 corpus, K2 against Everest, Blues
  against Jazz. These test the gate properly. Questions about unrelated topics are too
  easy to refuse.
- **Reject leaky phrasing** such as "this paragraph", "the text" or "according to the
  article" in the question generator. Count how many slipped through.
- **Messy corpus.** Mix real PDFs (arXiv two-column papers, a long government report),
  raw saved web pages with their menus, tables of contents and reference lists left in,
  and synthetic meeting transcripts written from a fixed brief of planted facts
  (speaker turns, timestamps, small talk, no headings).
- **Planted traps, recorded in `dataset.json`:**
  - boilerplate paragraphs: cookie banner, newsletter prompt, share bar, legal footer,
    advert, "related articles";
  - prompt injections, blunt through disguised, one per document, placed mid-document
    and never in the first 10%.

  Also add injection probes: questions an attacker would want answered from the
  injected text.
- Save everything (articles, questions, traps, the question model used, build time) to
  `dataset.json`, so reruns are exact.

## Configs and runs

- **Chunkers × retrieval modes.** Test `jev`, `structural` and `fixed` chunking, each
  with `vector` retrieval (plain top-k, no model) and the full model pipeline. Ingest
  each chunker into its own collection.
- **Give each config its OWN answer cache directory.** On the first run all configs
  shared one Jev cache, so the 2nd and 3rd configs reused cached answers and looked
  cheaper and faster. Fix: `cache_dir=<bench>/cache_<config>`, and report
  `cached_answers` per run. It must be 0 for cost and latency claims. Quarantine runs
  that were contaminated (move them aside) and rerun them.
- **Measure latency separately**: sequential, uncached, about 25 queries per config,
  with per-stage timings. Concurrent bulk runs inflate per-query latency.
- **Before paid ingest**, do a dry-run cost estimate, then a `--limit 6` query smoke test,
  then the full run in the background with `notify`.

## Metrics worth reporting

- hit rate, hit@1 (right passage ranked first), MRR, split by source type (pdf / web /
  transcript);
- false abstain on answerable questions, true abstain on held-out questions;
- context tokens sent to the answer model, and model cost per query;
- traps:
  - injection chunks quarantined at ingest;
  - injection text present in any query's final context;
  - boilerplate passages in context;
  - answerable evidence lost because its chunk was quarantined or dropped;
  - evidence coverage: the share of answerable spans sitting inside one reachable
    stored chunk;
- a hand-checkable list of what ingest dropped and why (reason + first 140 characters).

## Inspect before reporting

- **Re-check by hand every gate pass on a held-out question.** In one case an LLM judge
  marked "Apollo 12 launch weight" correct when the answer actually used Apollo 11's
  figure.
- **For every "lost" answer, find the chunk that held it.** In this run the injections
  had been merged with nearby paragraphs into chunks of 170 to 420 tokens, so chunk-level
  quarantine hid real answers. That was a design finding, not a scoring bug. It was fixed
  by screening at paragraph level before chunking: 4 hidden answers became 0.
- **Check whether boilerplate traps were actually dropped.** Paragraphs shorter than
  `min_tokens` get merged into a content chunk before enrichment sees them.

## Loader problems that only show up on messy input

Inspect what each loader produces before benchmarking. Print word counts, block kinds,
hyphen breaks, the share of short lines, and junk markers.

- **PDF with plain `page.get_text()`** returns hard-wrapped lines, line-break
  hyphenation (332 instances in one paper), page numbers, arXiv margin stamps, and no
  headings. Fix: use `get_text("dict", flags=TEXT_DEHYPHENATE)`, join each block's lines
  into one paragraph, and rejoin words of the form `lower-\nlower`. Drop margin blocks
  (top or bottom 8% of the page) that repeat with digits masked on at least 40% of
  pages, plus the arXiv stamp. Treat short blocks that are all bold, or whose font size
  is at least 1.15× the body size, as headings.
- **Raw Wikipedia HTML.** Hidden navigation boxes come out as runs of bare `-` bullets,
  which `fixed` chunking turned into 358 "duplicate" chunks. Strip empty list items and
  empty table rows, but keep `|---|` separator rows. Also skip any chunk that contains
  no alphanumeric character.

## Write-up rules (the user's standard)

- Lead with the table, then a "What this shows" section that states the losses as plainly
  as the wins. Examples: "Jev chunking did not beat structural: 0 of 2 sets won", "latency
  above target", "the gate made 2 real mistakes".
- Every number in RESULTS.md says what was run, how, and what it does **not** show
  (single run, machine-written questions, synthetic traps, an easy set if the vector
  baseline already finds about 98%).
- Name your own methodology mistake (the shared cache) in the reply, and rerun before
  reporting.
- Turn each weakness into a KNOWN_ISSUES entry with a workaround, and add a short status
  line to the PRD's Measured milestone.
- Give total benchmark spend computed from the per-run cost fields.
- End by offering the next test that targets the weakest finding.

## Before/after reruns (after fixing a measured weakness)

Getting a fair before/after comparison took these steps in the paragraph-screening round:

1. **Keep the questions and the traps. Change only the parse.** Add a `reparse` stage that
   re-loads the raw files with the current loaders. Back up the dataset to
   `dataset.v0.json` first.
   - Re-insert each trap after the paragraph it originally followed. Find that paragraph
     by its first 80 normalised characters, using the nearest preceding paragraph of at
     least 8 words.
   - List any trap whose anchor was lost (1 of 18 here) and any answerable question whose
     evidence is no longer in the text (0 here).
2. **Archive the old run completely.**
   - Move `runs_*.jsonl`, `report.json`, `ingest.json`, the per-config caches and the
     traces into `v0/`.
   - For pgvector, rename each table (`ALTER TABLE jevrag_messy_x RENAME TO
     jevrag_messyv0_x`) **and** update its row in `jevrag_manifests`. Otherwise the next
     ingest finds a manifest whose table is gone.
3. **Add control configs that isolate the change.** If the change is an ingest stage
   (screening), run it with every chunker (`structural_screen`, `fixed_screen`) as well as
   the headline config. Here all three reached the same 96.7%, which proved the gain came
   from the screen and not from Jev chunking.
4. **Sanity-check the volume of what the new stage removed before reading any scores.**
   Embedding tokens fell 22% and about 1,000 paragraphs were dropped. Sample 25 of the
   drops (nearly all were reference-list entries) and check every answerable evidence span
   against the dropped text. One bibliography question lost its evidence.
5. **Match traps within their own document.** The same boilerplate text was planted in two
   documents, so a corpus-wide match double-counted it.
6. **Report it as a before → after table** with the same columns, cached_answers = 0, plus
   the ingest-side trap table:
   - injections quarantined alone;
   - answers hidden by quarantine;
   - planted junk removed;
   - false-positive quarantines, quoting each one;
   - paragraphs dropped and what they mostly were;
   - ingest cost per config.

## Speed of the scorer

The fuzzy evidence check is O(questions × chunks) `SequenceMatcher` calls, and took more
than 7 minutes per report. Two changes made it 15× faster: put `lru_cache` on the
normalisation step, and skip the fuzzy match unless the two texts share at least
0.64× the span's words. Before swapping it in, check on about 1,000 real pairs that the
fast and slow versions give identical verdicts.

## Partial reruns overwrite the full report

`report --configs <one>` rewrites `report.json` with only that config. A post-rename smoke
test wiped the five-config report this way. Either write smoke reports to a separate path,
or rebuild the full report straight afterwards (`report --configs a b c d e`) and confirm
the config list and the headline numbers match RESULTS.md. If it happens, tell the user.

## Next step: public datasets

For the PRD's formal Measured milestone (BEIR SciFact and FiQA, QASPER), see
`public-eval-datasets.md`: licence checks, download URLs and MD5s, dataset shapes, and the
rules for tuning on dev and reporting on test.
