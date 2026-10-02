# Public eval datasets for a retrieval tool's "Measured" milestone

Verified 2026-10-01 during jev-rag-retrieval's M2 (BEIR SciFact, BEIR FiQA, QASPER). It covers
licence checks, downloads, dataset shapes, the harness design, run-design rules, and what
actually happened in the run. Downloads are free. Stop for user sign-off before any paid run,
with a cost estimate.

## Licence check: primary sources, in this order

1. **The dataset's own repo LICENSE file** (raw GitHub). SciFact:
   `https://raw.githubusercontent.com/allenai/scifact/master/LICENSE.md` says the claims
   are CC BY 4.0 and the abstracts (from S2ORC) are ODC-By 1.0.
2. **Hugging Face API metadata**: `curl -sL https://huggingface.co/api/datasets/<org>/<name>`,
   then read the `license:*` tags and `cardData.license`. `allenai/qasper` gives cc-by-4.0,
   and `BeIR/scifact` / `BeIR/fiqa` give cc-by-sa-4.0. The `mteb/*` mirrors say "unknown",
   so don't cite them.
3. **The loader script's `_LICENSE` constant**. `allenai/qasper/raw/main/qasper.py` contains
   `_LICENSE = "CC BY 4.0"` along with the real data URLs.
4. **BEIR's README disclaimer** says BEIR redistributes the data but does not vouch for
   licences. So a BEIR copy proves nothing about the licence: go to the original source.

**FiQA-2018 stayed [UNVERIFIED].** The organisers' Google Site couldn't be fetched (and
`web_extract` may be search-only on this box). The corpus is crawled StackExchange
"Investment" posts, which are CC BY-SA. Local evaluation without redistribution is low risk,
but write it up as unverified rather than claiming a licence.

Run the curls from a script file, with one `-o /tmp/lic_<name>.txt` output per URL, then
parse them in Python.

## Downloads (all verified)

```bash
# BEIR zips: check against the md5 column of BEIR's README table
curl -sL -o scifact.zip https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip  # md5 5f7d1de60b170fc8027bb7898e2efca1
curl -sL -o fiqa.zip    https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/fiqa.zip     # md5 17918ed23cd04fb15047f73e6c3bd9d9
python3 -m zipfile -e scifact.zip .      # no unzip binary needed
# QASPER: the HF repo holds only a loader script; the data lives on S3
curl -sL -o test.tgz https://qasper-dataset.s3.us-west-2.amazonaws.com/qasper-test-and-evaluator-v0.3.tgz
# train/dev: https://qasper-dataset.s3.us-west-2.amazonaws.com/qasper-train-dev-v0.3.tgz
```

Keep the data under the project's gitignored state dir (`.jev-retrieval/eval_data/`).

## Shapes

| Set | Corpus | Test queries | Notes |
|---|---|---|---|
| SciFact | 5,183 abstracts, median 192 words | 300 (339 qrels) | `corpus.jsonl`, `queries.jsonl`, `qrels/{train,test}.tsv`. Small enough to run whole. **Queries are claims, not questions.** That matters for any answerability gate (see below) |
| FiQA | 57,638 posts, median 90 words | 648 (1,706 qrels, about 2.6 relevant per query) | Also has a `dev.tsv`. Too big for a ~2 GB RAM box with a 256 MB pgvector container: subsample. **Some labelled posts have empty text** (e.g. `117276`): drop those labels and report the count; don't let unretrievable labels lower every system's recall |
| QASPER test | 416 NLP papers, median 3,192 words | 1,451 questions | `full_text[] = {section_name, paragraphs[]}`; `answers[].answer = {unanswerable, extractive_spans, yes_no, free_form_answer, evidence[], highlighted_evidence[]}`. 139 human-marked unanswerable; 1,279 have evidence paragraphs |

QASPER is the strongest test of an answerability gate, because its unanswerable questions
come from people. It is also the only one of the three where chunking matters, since the
documents are long. Search each question within its own paper (a doc_id filter; pgvector
HNSW returned the full top-k under a 1-in-100 filter in a probe, so filter starvation was not
an issue at this scale).

Sample used: SciFact full corpus (300 test, 100 dev from train qrels), FiQA 300 test + 100
dev with all their qrels docs + 10k distractors, QASPER 100 test papers split by paper into
test (233 q) and dev (87 q). Script: the project's `scripts/prepare_eval.py`.

## Harness design that worked: record once, score offline

Build it as the shipped `eval` command (BEIR / QASPER / JSONL loaders) with offline tests.

1. **Record** each query once: vector top-30 candidates with similarity, token count,
   evidence-unit labels, Jev's four passage scores, an optional LLM reranker score, and gate
   scores for each passage set a system might send. Write a JSONL row per query and a
   `.meta.jsonl` with usage and cost per run. Resume by skipping recorded ids.
2. **Score offline** with no API calls: `vector@N`, `jev` (any ClassifyConfig), `jev-rerank@N`,
   `llm-rerank@N`, all on *identical* candidates. Threshold grids and select modes become
   free to explore.
3. Paired bootstrap 95% intervals for system differences on the same queries.
4. **Pin the configs the report uses** (`ClassifyConfig(select="threshold", max_passages=8)`
   etc.) instead of relying on library defaults. When the default later changes, rerun the
   report and diff it against the committed `m2_results.json`: it must show 0 differences.
5. If a new system needs a score that wasn't recorded (e.g. a gate on a new passage set),
   **backfill** only that score with a script, after the batch finishes. A separate process
   doesn't share the rate limiter.

## Run-design rules

- **Tune on dev and report on test.** The earlier in-house benchmarks set thresholds on the
  data they reported, which flattered the results.
- **Preregister a new setting before computing its test numbers.** Write
  `docs/m2_preregistration.json` with the real clock time (`date -u`, never typed by hand),
  the dev numbers, the exact config and the test rule. **Disclose what you'd already seen**:
  here the old threshold mode's test failures had been printed before the rank mode was
  chosen. Commit it with the results.
- **Use a real reranker baseline**: gpt-4.1-mini listwise 0–10 scores through the same
  gateway key. Plain vector search alone is too easy to beat.
- **Expect a recall@10 risk on multi-relevant sets** and say so in the plan.
- **Recall@10 cuts off at the first 10 passages sent.** If conflicts are appended after kept
  passages, lists longer than 10 lose them in the metric. Report "recall of everything sent"
  next to recall@10 whenever a setting can send more than 10 passages.
- Run batches sequentially. Before any concurrent run, make sure the model client's rate
  limiter is shared per (event loop, backend, key); see Pitfalls.
- Follow the usual cost order: dry run, then one item (inspect the recorded row by hand),
  then the batch. Include the baseline reranker's spend in the estimate. Actual: $1.66 Jev
  + $3.43 gpt-4.1-mini + ~$0.08 embeddings against a $4–6 estimate.
- Turn ingest enrichment and screening off for sets made of short single-passage docs
  (SciFact, FiQA). They cost Jev money and aren't what's being measured.

## What M2 found (jev-rag-retrieval, test splits)

| | SciFact | FiQA | QASPER |
|---|---|---|---|
| Threshold mode (old default, top 8) | recall@10 −21.9 pts | −3.7 | −5.5 |
| Rank mode, top 5 (preregistered, now default) | −0.6, 44% less context | **−4.9** | −1.9, 43% less context |
| Rank mode, top 8 | +1.2 | +0.1 | +2.4 |
| Jev vs gpt-4.1-mini as reranker (nDCG) | +3.2 | level | +2.3 (level) |

- A **filter** (keep passages above score thresholds) threw away answers; the same scores
  used to **rank** worked. Jev's strength was ordering, at a quarter to a third of the LLM's
  cost.
- The gate caught 29–41% of QASPER's human unanswerable questions (synthetic sets had shown
  95%), and wrongly refused 26% of SciFact queries because they're claims. Gate thresholds
  tuned on dev did not transfer to test (false refusals 1% → 9%).
- On SciFact, `contradicts_query_premise` fires on refuting abstracts (0.6 conflicts per
  query). Conflict routing is meaningful for questions with false premises and noisy for
  claim verification.
- Jev chunking tied structural on QASPER and can't be compared on the short-doc sets, so a
  "wins on 2 of 3 sets" rule for chunking can't be met with these three.
- In-house synthetic benchmarks looked much better than public data. Lead the README status
  with the public numbers.

## Pitfalls hit

- **Per-client rate limiter.** Each client made its own limiter and semaphore, so
  concurrent clients each got the full requests-per-second budget. Fix: one limiter per
  (event loop, backend, key hash) in a `WeakKeyDictionary`. Add a test that fails on the old
  code: two clients, 10 requests, `max_rps=5`, elapsed must be ≥ ~1.5 s.
- **Fake transport wire format.** The Jev answer format is `{"type": "noul", "noul": 0.5}`,
  not `{"value": ...}`, and responses need `usage`. Copy the shape from `conftest.py`.
- **A smoke run overwrote the full report.** `report --configs X` rewrote `report.json` with
  one config. Rebuild it from the stored runs, or write smoke output to another path.
- **Typed timestamps.** A preregistration timestamp typed by hand didn't match the clock.
  Use `date -u` and record the file's sha256.
