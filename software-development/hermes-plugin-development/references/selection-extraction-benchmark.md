# Selection-based extraction pipeline and how to benchmark it

Pattern used for Jermes' ingestion workstream (`jermes/ingest/`): a cheap
classifier (Jev) never writes values; it only picks among spans that code
found, and code copies the chosen span verbatim. Benchmarked against "one LLM
reads every document" on real SEC 10-Ks.

## Pipeline shape (each stage one logged, cached request)

1. **Triage**: in-scope / readable / English Nouls + doc-type Choice on the
   first ~3k chars. Out of scope or unreadable → reject after one request.
2. **Screen**: chunk (~1500 chars on paragraph boundaries); per chunk Nouls
   `relevant`, `contains_instruction`, optional `contradicts_premise`.
   Routes: quarantine (instruction ≥0.7) > conflict > evidence > drop.
3. **Candidates**: regex finders that over-find and dedupe by normalized
   value (first occurrence wins, so a Choice never splits probability across
   duplicates); gazetteers are finders too (jurisdiction list).
   `from_list()` admits generator/LLM proposals only if they occur in the text
   (whitespace/case-insensitive match, but return the document's own span).
4. **Select**: one Choice per field over candidate ids + `not_stated`, state
   shows each candidate in context with `[[ ]]` markers. Candidates come from
   evidence chunks first; a field with none there, or answered `not_stated`,
   is retried over the whole document (a wrongly dropped chunk costs one
   request, not a lost value).
5. **Verify**: per-field Nouls framed so true = something is wrong
   (`wrong`, `unrelated`). Gate on **max** of flags, not mean.
6. **Escalate**: flagged fields (and required fields left missing/review) go
   to a strong model in **one call per record**; its answer must also be a
   real span or it goes to review.
7. **Classify**: hierarchical Choice; below the confidence cutoff report the
   parent.
8. Disposition: accepted / review / rejected / error. Exceptions become error
   records, never raise.

Safety rules worth testing (all have tests): values are exact spans;
invented strong-model values rejected; quarantined chunks blanked before
candidate finding and classification (chunk-grained, so real values in the
same chunk are lost and the record goes to review, fail-safe); low-confidence
pick → review; Jev failure → error record; off mode makes no calls.

**Mutation-check the suite with `sed` plants** (copy the file, sed one
threshold or rule, run the tests, restore; also assert the plant actually
changed the file). The first ingestion suite passed with `pick_min_p` set to
0, so a low-confidence pick could be accepted untested; a dedicated test
fixed it. Plants that must go red: max→mean flag gate, strong-model answer
not re-located in the document, confidence gate removed.

Writing an injection test: put the planted instruction in its **own chunk**
(pad with filler so the real values sit in a different chunk) and assert the
values are still extracted; add a second test where it shares a chunk with
real values and assert the record goes to review. A test where the planted
note and the values share chunk 0 proves only the fail-safe path.
Batch requests under a character budget (~60k state chars; Jev takes ~32k
tokens per request).

## Benchmark recipe (SEC 10-K cover pages)

- `scripts/build_sec_bench.py` in the Jermes repo. Ground truth from EDGAR,
  independent of the document text: submissions API (`stateOfIncorporation`,
  `ein`, `reportDate`, `fileNumber`) plus XBRL companyfacts
  `dei:EntityCommonStockSharesOutstanding` / `dei:EntityPublicFloat` matched
  by accession number (skip when several share classes disagree).
- **SEC rejects User-Agents containing a URL (403).** Use
  `"<Company> research <email>"`; ≤10 req/s.
- HTML→text: strip script/style/`ix:header`, then collapse `" ,"` to `","`
  (iXBRL splits "December 31 , 2025").
- **Validate ground truth against the text before scoring**: any value not
  findable in the document is excluded (not counted against any arm). Canon
  comparisons by meaning: file numbers `1-3215` == `001-03215`, dates to ISO,
  numbers to 7 significant figures.
- The first four fields were too easy (every arm 100%); shares outstanding and
  public float sit among dozens of numbers and are the discriminating fields.
- **Keep a held-out set** never looked at while tuning finders/questions, and
  report it separately from the development set.
- Baselines need paid models: if the gateway key is free-tier ("Free tier
  users do not have access to this model"), call the Anthropic Messages API
  directly with ANTHROPIC_API_KEY and price from the official pricing page.
  Record real usage per call.
- Cost control: 2–3 docs on the Jev arm only first, then all arms.

## Results (Sept 2026)

- Dev set, 20 docs × 6 fields: Jev pipeline 120/120, $0.047; Sonnet 4.5
  reading every doc 120/120, $0.379; Haiku 4.5 120/120, $0.126.
- Held-out, 16 docs (94 scored values): all arms 94/94; Jev $0.027 vs Sonnet
  $0.298 (94% fewer strong-model input tokens) vs Haiku $0.099.
- Latency ~34 s/doc (4 sequential Jev calls under Vercel pacing): batch only.
- The benchmark doesn't separate arms on accuracy; it shows equal accuracy at
  far lower cost. Harder field sets are needed to test accuracy.

## Pitfalls hit

- **Most "Jev wrong" values were finder bugs**: the right span was never
  offered. `710,398,642.` lost its last group (trailing period); `526.7
  million` lost its scale word; a bare `208,464,334,129` amount had no money
  finder; `$ 3.6 trillion` lacked the `trillion` scale. Before blaming the
  selector, check whether the true value was among the candidates, and add the
  real line as a regression test.
- Phone/number finders over-match dates; that's acceptable (the selector
  drops them), missing a candidate is not.
- Field questions must disambiguate when a document states the same quantity
  twice (public float "as of the last business day of the second fiscal
  quarter", not the later date).
