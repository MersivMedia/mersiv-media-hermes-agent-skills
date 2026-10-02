---
name: developer-tool-prd
description: "Write PRDs for dev tools and AI apps, then build v1."
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [prd, readme, open-source, code-review, api-verification, planning]
    category: software-development
    related_skills: [grounded-citations, google-workspace, github-repo-management, research-design-documents, writing-plans]
---

# Developer Tool PRD Skill

Turns a pasted design, sample code (often LLM-generated), or a rough idea into two repo-ready documents: a PRD and a full README. Once the user answers the open questions and says "make the repo and start coding", it continues into the build-out: repo, working core, tests, CI, and docs brought into line with the shipped code (Step 6 + `references/prd-to-v1-buildout.md`). The repo is never created before that sign-off.

## When to Use

- "Review this doc/sample code and write a PRD for it as a GitHub tool."
- "Make this work with any X" (any vector DB, any provider, any framework): the adapter/abstraction design is the core of the PRD.
- A README is requested alongside the PRD, before any code exists.

For novel-architecture research papers use `research-design-documents`. For client AI-ROI PRDs use `ai-opportunity-discovery`.

### Variant: consumer / personal AI app PRD ("research existing githubs and models, come back with a PRD and plan")

Example: a voice language tutor built on an ElevenLabs agent, deployed to Vercel or an iPhone app. There's no sample code to review, so replace §2 "Review of the sample" with **"Existing resources assessed"**. That is a table of resource | what it is | use it? (yes / reference only / fallback / no + reason), covering GitHub repos (check stars, licence and last push via `api.github.com/repos/<o>/<r>`), hosted APIs, and Hugging Face models. Say plainly if nothing existing covers the combination.

Sections that matter for this variant:
- **UX section first.** The user often adds UI requirements mid-research (here: plain chat, an audio-mode button, a language dropdown, topic suggestions that evolve with progress). Give each its own subsection. Make "evolving" features deterministic (rule-based slots over a curriculum graph), not free-form model output.
- **Memory/state owned by the app**, injected into the vendor agent at session start and reconciled after the session from the transcript webhook. Vendor agent memory is not the source of truth.
- **One agent for chat + voice** when the platform has a text-only flag.
- **Voice cloning:** flag the accent trap (see the ElevenLabs reference).
- **Deployment:** a PWA on Vercel first, native later only on a concrete trigger.
- **Cost table** with the per-minute driver, a daily cap, and [UNVERIFIED] rows.
- **Open questions** that block content work (region/dialect, current level, dates, budget).
- **Learner/user freedom over curriculum.** For a personal tutor/companion, the user wants the end user able to steer to *any* topic, including sexual or "unhinged" ones ("I want her to be able to learn whatever topics/phrases she wants, not just ones in our structured outline"). Write the curriculum as a fallback default, not a fence. Put open-topic handling in the agent prompt from the first draft: a single hard line on minors, crude-register tagging, no moralizing. Verify it live with deliberately crude test turns, and report the result with real examples rather than promising it.
- **Cut the heaviest optional subsystem when the user asks for less development.** The user dropped pronunciation scoring ("adds a lot more development that we don't need"). Remove it from v1 entirely, keep a seam for adding it later, and state honestly what the remaining approach can't do (here, conversational STT catches wrong words but not a slightly-off vowel).
- **Vendor comparisons asked mid-build** ("what about grok voice?"): answer with a feature-by-feature table plus the one decisive row, verified from the vendor's `.md` docs. Say what you couldn't test (e.g. accent quality without a key).
- **Phases:** the user corrected durations and pre-build spikes on dev tools. On this app PRD I wrote day estimates plus a Phase 0 spike, and the user didn't object before the session ended, so it's unclear whether they accept it. Default to the goals-only rule above. If a device-level spike is genuinely needed (iOS mic capture, multi-voice latency), make it the first milestone's "Done when" test rather than a separate time-boxed phase.

Domain references: `references/elevenlabs-agents-platform.md` and `references/pronunciation-assessment-apis.md`.

## Prerequisites

- Source doc access: Google Docs through `google-workspace` (`drive download ID --export-mime text/plain`). `web_extract` may not be able to read Docs URLs.
- The user's existing related repos, for real client code, limits and measured numbers. Example: `~/jermes` holds a working Jev client and live latency and rate-limit findings.

## Procedure

### 1. Read the source, then verify every API it calls against live primary docs

Sample code, especially LLM-generated code, invents method names, mixes up question and answer types, and calls deprecated SDK methods. Check each external call, in this order:

1. **Vendor docs as markdown.** Many doc sites (Mintlify and similar) serve `/llms.txt` as an index and `<page>.md` for any page. `curl -sL https://docs.vendor.ai/llms.txt`, then `curl -sL https://docs.vendor.ai/<path>.md`. The HTML versions are 300-700 KB of JS; the .md files are 5-40 KB of clean text.
2. **Current SDK versions.** `curl -s https://pypi.org/pypi/<pkg>/json` gives the latest version and summary, and shows deprecated packages (e.g. `pinecone-client` → `pinecone`). Pipe through a script file rather than `| python3 -c` to avoid approval prompts.
3. **The real method surface, without installing.** `python3 -m pip download --no-deps <pkg>==<ver> -d wheels && unzip -q wheels/<pkg>*.whl -d x`, then run `search_files` on the client class for the method the sample calls. This is how `qdrant-client` 1.19.1 was found to have no `search()` (use `query_points`), and Chroma's `l2` default metric was confirmed.
4. **Behavioural facts from DB docs** (filter-index requirements, metadata size limits, upsert and insert semantics) via `web_search` or `web_extract`.

### 2. Write the review as tables that map findings to requirement IDs

Three tables work well: **API mismatches**, **design problems** and **per-adapter bugs**, each with a `Requirement` column (FR-C2, FR-S5...). Every problem found must be fixed by a numbered requirement, so the review and the spec can't drift apart. Keep what the sample got right and say so in one sentence.

Common defects in LLM-drafted pipeline code:
- One remote call per item in a sequential loop, when the API accepts many questions or items per request.
- Random UUIDs for record IDs, so re-ingestion duplicates. Use UUIDv5 of (stable doc id, content hash) plus stale-record delete.
- `insert_many` described as upsert.
- Scores with different directions across adapters (distance vs similarity), which breaks shared thresholds.
- Character counts where tokens matter; no minimum size.
- A fixed category list with no "other" option.
- Features promised in prose but absent from the code (e.g. injection screening).
- A single top classifier guess used as a hard filter, so one wrong guess returns nothing.
- Citations that are bare domains.

### 3. PRD structure

```
1 Summary              what it does in 3 bullets; what is proven vs not
2 Review of the sample API mismatches / design problems / adapter bugs
3 Goals + non-goals
4 Users and use cases
5 The key dependency, in brief   capabilities, limits table, weak spots → design rules
6 Architecture         pipeline diagram (fence OK: layout is semantic), repo layout
7 Functional reqs      FR-<area><n> tables per stage
8 Cost and speed       estimates, labelled as estimates; name the binding limit
9 NFRs                 fail-soft, determinism, security, dependency pins, docs, licence
10 Risks               risk | mitigation
11 Milestones          GOALS ONLY, no durations or dates: Working core -> Measured -> Released
                       (tag v1.0.0) -> Coverage. Each has a "Done when" test
12 Success metrics     labelled as hypotheses until the Measured milestone
13 Open questions      name, client choice, defaults, integration, each with a recommendation
Sources                numbered primary URLs; [UNVERIFIED] where not confirmed
```

Rules the user holds to:
- **Milestones are goals, not a schedule.** The user iterates in one or two days and ships, so weeks-long time boxes were rejected ("don't add a timeline to the milestones, just have the goals"). Don't write durations, dates or "week 1" anywhere, and don't add a pre-build spike milestone that blocks coding. Fold the measurement in as its own goal, and make it non-blocking: a stage that misses its bar ships in `shadow` mode, not held back.
- **The first public release is v1.0 (tag `v1.0.0`), not v0.1.** Dev builds are `1.0.0.devN`. Mention that 1.0 commits to a stable API/CLI/config, so defaults should settle in the Measured step first.
- **Separate the proven from the plausible up front.** If the tool's headline feature (e.g. model-placed chunk cuts) has no published evidence, say so in the Summary and make the Measured milestone a go/no-go against cheap baselines for turning it on by default.
- **Label vendor-run figures** as vendor figures, and keep estimates out of claims.
- **Do the arithmetic, then re-check it.** Rate limit ÷ requests per operation = throughput. Count every request (routing + N items + gate), not only the main loop.
- **Every dependency gets an upper bound** (`>=floor,<next_major`); core deps minimal, integrations as extras.
- **"Works with any X"** = a small adapter interface + a portable filter/config language + capability flags + a conformance test suite every adapter must pass + bridges to LangChain/LlamaIndex-style ecosystems for the long tail.

### 4. README structure (user's standard)

Biggest claims and all features up top, then install and configure, then the long guides; results and known issues go in linked docs pages.

```
Title - one line
Bold one-sentence value claim
5 feature bullets
Status callout            be honest: "design stage, nothing benchmarked, stages ship in shadow"
What it does table        stage | what the model decides | what code does
Contents
Install (extras table, keys table, `check` command)
Quickstart (CLI + Python)
Configure (full YAML; thresholds marked placeholder until calibrated)
Guide 1 (e.g. ingestion) step by step, each step: what happens, what code decides, commands
Guide 2 (e.g. retrieval) same shape, ends with the result object and the optional answer helper
Integrations/backends table + "adding a backend" interface
Tuning and evaluation
Cost and limits
Agents/frameworks (HTTP, MCP)
More (links to PRD, RESULTS, KNOWN_ISSUES...)
Not-affiliated line, License
```

Put dry-run → one item → full batch in the guide itself. The user wants cost control before paid spend.

### 5. Deliver

- Write both as markdown in a local repo-shaped dir (`~/<tool>/README.md`, `~/<tool>/docs/PRD.md`).
- Upload to Google Docs with `md2gdoc.py` using the Drive folder convention (a root folder named for the project).
- Do **not** create the GitHub repo yet. End with the open questions (name, whether to create the repo now) as decisions for the user.
- Say that the work is unreviewed, and list the [UNVERIFIED] items.
- Renames and version changes after review: re-sync the Google Docs with `--doc-id` (links survive), rename the Drive docs/folder, and grep both files for leftovers of the old value (`grep -c M0`, `v0.1`) before reporting done.

### 6. Build-out (only after "make the repo and start coding")

Full recipe with commands: `references/prd-to-v1-buildout.md`. The short version:

1. `git fetch` if the repo exists; create it public with the docs as the first commit (the user hand-edits on GitHub).
2. Probe the live API with a tiny script before writing the client. Record latency, tokens and answer shape, and verify every SDK method by signature (`inspect.signature`) in the project venv.
3. Build stage by stage. After each stage run a quick live sanity script, not only unit tests: this is where question-wording bugs show up (see the Jev reference, "Question design").
4. Write one conformance suite every backend must pass, and run it against a real server in Docker for any backend that has one.
5. Offline tests use a deterministic fake of the remote model via `httpx.MockTransport`; keep one opt-in live test (`JEVRAG_LIVE=1`-style gate).
6. Before committing, re-check every README claim against the code (run each example) and put measured numbers in `docs/RESULTS.md`, limits in `docs/KNOWN_ISSUES.md`. Put a status block in the PRD's milestones saying what's built and what isn't.
7. Scan the staged diff for secrets, commit, push, and **wait for CI**. Report the CI result, not the local one.
8. Ship `.env.example` + a full commented `<tool>.example.yaml`, with a drift test (`templates/test_samples_drift.py`). Offer these proactively; the user had to ask "is there a sample .env and yaml?". Then live-test `.env` loading with a real key via `scripts/live_envfile_check.py`: the user OKs live key tests as long as the key is never exposed.
9. Backends with no account to test against (e.g. "forget about pinecone for now"): keep the code, mark it experimental everywhere, and move it out of the release's tested set into the Coverage milestone (reference §9).
10. **Benchmarks after v1** ("larger documents and more queries", "messy documents"): follow `references/retrieval-benchmarking.md`.
    - Generate verbatim-evidence questions, plus unanswerable questions from related held-out docs.
    - Compare chunkers × {vector-only, full pipeline}.
    - Give each config its own cache.
    - For messy input, use real PDFs, raw web pages and transcripts with planted boilerplate and injections.
    - Inspect loader output before running.
    - Report losses as plainly as wins.
    - After fixing a weakness, rerun the same questions and traps (re-parse, then re-place the traps). Archive the old runs and collections, add control configs that isolate the changed stage, and show a before/after table (reference §"Before/after reruns").
11. **When the evidence demotes a default** (here Jev chunking lost or tied on both benchmarks, so the user said "yes" to making `structural` the default), propose the switch with the numbers, then once they agree, change every surface in one commit:
    - Code: the dataclass default, the `init` template, both sample YAMLs (the drift test catches a mismatch between them), plus a comment pointing at RESULTS.md.
    - Tests: find the ones that relied on the old implicit default (they fail as soon as the default flips) and pin `method="jev"` explicitly in them. Add one test that pins the new default and asserts it makes **zero** model calls.
    - README: rewrite the tagline and feature bullets so they lead with what was measured, not the demoted feature. Mark the demoted feature's table row "opt-in". Remove "falls back to X" lines that now describe the default. Repoint `inspect --compare` examples at the opt-in method, since comparing against the default is a no-op.
    - PRD: mark the matching Risk row **Happened** and record the decision. KNOWN_ISSUES: replace "unbenchmarked" with what was actually tested.
    - Live-check the CLI (`init` writes the new default; `inspect` makes no model calls; `--compare <old>` still works), with the key never printed.
    - Then flag a **name mismatch before v1.0**: if the repo or package name advertises the demoted feature, ask about renaming before the first tag and PyPI upload, while a rename is still cheap.
12. **Renaming** (the user picked `jev-rag-retrieval`): follow `references/project-rename.md`.
    - Check that the new name is free on GitHub and PyPI, and check the **import/CLI name** on PyPI as well.
    - Rewrite tracked files only; quarantine untracked debris.
    - Reinstall under the new distribution name, run the tests, and build the wheel.
    - Run `gh repo rename`, then set the remote URL; the old URL should return 301.
    - Wait for CI.
    - `mv` the local directory and rebuild the venv, since venvs hard-code paths.
    - Do a clean install from the git URL.
    - Rename the Google Docs through the Drive API (`--title` doesn't rename them).
    - Update the memory entry.
    - **If the import/CLI name collides on PyPI** (here `jevrag` was taken, and the user chose to rename the import to `jev_retrieval` with the command `jev-retrieval`): list every identifier kind first, then map each one deliberately (reference §7). The kinds are the module, the entry point, env vars, config filenames, the state dir, DB table prefix and manifest keys, public class names, and CI DB names. One blind `sed` would break the module and command spellings, which differ. Tell the user that data stored under the old names becomes invisible to the new defaults. To keep using local benchmark data, migrate the tables and manifest rows in one transaction (reference §8).
13. **Measured milestone on public datasets** (BEIR SciFact and FiQA, QASPER): follow `references/public-eval-datasets.md`.
    - Confirm licences from primary sources first. A BEIR copy proves nothing about the licence.
    - Download and checksum the data (free), then plan the run as the shipped `eval` command.
    - Tune on dev and report on test, compare against an LLM-reranker baseline, and flag up front any PRD bar that might fail.
    - Present the plan with a cost estimate and wait for sign-off before spending anything.
    - Build the harness as **record once, score offline**: every candidate's model scores, LLM-rerank scores and gate scores go into JSONL once, then every system and threshold is scored on identical candidates for free. Pin the configs the report uses so a later default change can't move published numbers; diff against the committed results JSON after any default change (must be 0 differences).
    - Before computing test numbers for a new setting found on dev, write a preregistration file with the real `date -u` time and disclose any test numbers already seen.
    - Expect public data to contradict in-house synthetic benchmarks. In M2 the shipped threshold default failed the bar on all three sets, rank mode (same scores used to order rather than filter) passed 2 of 3, and the gate caught only 29–41% of real unanswerable questions. Lead the README status with the public numbers, then offer the default decision as numbered options with a recommendation (the user picked "1" = rank, top 5).
15. **Switching a default after an eval** (same shape as step 11): flip the dataclass default, the `init` template and both sample YAMLs; pin the old mode explicitly in tests that depended on it, and add tests for the new default plus the old mode's behaviour; rerun the eval report and confirm byte-identical results; live-check against the real model with the key never printed; rewrite README/PRD/KNOWN_ISSUES/RESULTS wording that called the old mode "default" or "shipped". Change only what the user picked: a second recommendation they didn't answer (here gate → shadow) stays as is and is flagged in the reply.
16. **PyPI release** ("did you put it on pypi"): follow `references/pypi-publishing.md`.
    - Check PyPI's JSON API and `session_search` before agreeing that an earlier release happened. jev-rag "v1.0.0" turned out to be a GitHub release only.
    - Absolutize README links, since relative ones break on pypi.org, and swap the git+ install text for `pip install`.
    - Build, run `twine check --strict`, and smoke-test the wheel in a fresh venv. Upload only after that.
    - Then tag, cut a GitHub release with the dist files attached, and verify by reinstalling from public PyPI with no cache.
14. **An ambiguous "ok" or "yes" after offering two next steps**, where one is destructive (e.g. "remove the container" vs "start the next milestone"): ask with `clarify`, recommended option first, rather than guessing. Here the user picked "start Measured, keep the container".

## Pitfalls

- **Spike the vendor agent in text mode from a script before building UI.** For the ElevenLabs tutor, a 60-line Node script over the raw WebSocket proved auth, dynamic variables, multi-voice tags, tool calls and real per-message cost in about 15 s. It also exposed the voice_not_found and English-TTS-model errors before any React code existed. See `references/elevenlabs-agents-platform.md` §"Build recipe".
- **"Text mode is free" is wrong for agent platforms.** ElevenLabs chat measured about $0.008/message (LLM tokens + platform fee). Budget caps must count chat, not just voice minutes, and the PRD cost table should say so.
- **Mid-task UI requirements interrupt the research.** When the user interrupts with new UI requirements, acknowledge them in one line and fold them into the UX section. Don't restart the research. Make sure each one appears as its own named subsection, so the user can see it was captured.
- **md2gdoc's "doc much shorter than source" warning is a false positive on table-heavy docs.** `verified_chars` ignores table cells. Export the doc as `text/plain` and check that distinctive strings from late sections, tables and fences are present. Run this from a script file (see `scripts/verify_gdoc_export.py`); long inline one-liners get hard-blocked. **Needles must be plain text**: the export drops Markdown backticks and `**`, so a needle like ``"Default: `structural`."`` fails even when the doc is correct. Use `"Default: structural."`. Also add a needle asserting that the *old* wording is gone, such as the old tagline after a repositioning.
- **md2gdoc `--html-only` debris.** Converting leaves `*.html` next to the sources. Move them out before the dir becomes a repo.
- **Citation renumbering.** After adding or dropping sources, check that the numbers used in the body equal the numbers in the list, with nothing unused (a regex check in Python).
- **Don't let vendor cookbook wording become your spec wording untested.** Question phrasing changes results (TypeSafe measured 17 vs 12 blocks from one wording change; the cookbook's injection question flagged a real refund policy). Make wording an output of the Measured milestone, and probe it live during build-out.
- **Local tests pass because another extra installed a shared dependency.** The pgvector adapter imported numpy, but numpy wasn't declared in `[pgvector]`. It passed locally because chromadb pulled numpy in, then failed in CI's per-extra job. Test each extra in its own fresh venv (`uv venv /tmp/x && uv pip install -e ".[extra,dev]"`) before pushing.
- **Stale counts after edits.** Test counts, adapter counts ("11" when the list had 13) and version strings drift in README/RESULTS/PRD. Get counts from a junit XML (`--junitxml`) rather than reading dots, and grep all docs for the old value after every change.
- **A shared model-answer cache across benchmark configs fakes cost and latency wins.** Later configs reuse earlier answers. Give each config its own cache dir, and report `cached_answers` (it must be 0).
- **`--dry-run` estimates must only count the stages that actually call the model.** A structural, no-enrichment config quoted Jev cost until this was fixed; keep a test that asserts a zero estimate.
- **Screen paragraphs before chunking, not chunks after merging.** Chunk-level screening merged a short injection or boilerplate into its neighbours, so quarantine hid real answers (4 of 91), and junk below `min_tokens` survived (0 of 12 dropped). The fix that measured well: Nouls per paragraph/list item/table, 40 per request with the paragraph inline. Cut flagged paragraphs from a space-blanked working copy so offsets stay exact. Store each injection alone as a quarantined record, and collapse blank runs left in chunks. Result: 0 answers hidden, 11/12 junk removed, hit rate 93.4→96.7%. It also cuts reference lists, so ship a `shadow` mode. Measure "answerable evidence lost to quarantine" in any benchmark.
- **When a fix improves a benchmark, run control configs before crediting the headline feature.** Running the same screen with structural and fixed chunking gave all three chunkers the identical 96.7%, so the gain was the screen, not Jev chunking, and structural plus the screen did it at half the ingest cost. Recommend the default the evidence supports, even when it demotes the tool's namesake feature.
- **Check the import name for collisions at naming time, not only the distribution name.** `jev-rag-retrieval` was free on PyPI, but the import/CLI name `jevrag` had been taken 10 days earlier by an unrelated Jev RAG project. Two distributions that ship the same top-level module silently overwrite each other. When writing the PRD's naming open question, run `curl -s -o /dev/null -w "%{http_code}" https://pypi.org/pypi/<name>/json` for the repo, distribution, import and CLI names, and recommend from that.
- **Benchmark scoring with fuzzy matching is quadratic.** `SequenceMatcher` over questions × chunks × configs took more than 7 minutes per report. Try an exact normalised-substring check first, run the fuzzy match only when word overlap clears a threshold, and confirm on about 1,000 sampled pairs that the fast and slow verdicts agree. The fast path was 15× faster with 0 disagreements.
- **When renaming storage, rename the metadata rows too.** Archiving old benchmark collections by renaming their pgvector tables left the `jevrag_manifests` rows behind. The next ingest would then have found a manifest for a table that didn't exist. Update both the tables and the manifest rows (`UPDATE ... SET collection = replace(...)`).
- **HTML-to-markdown cleanup regexes must keep table separator rows.** A rule dropping table rows with no letters would also delete `|---|`. Exclude rows made only of `-:|`, and test this.
- **Fake-model test fixtures need whole-word matching.** A keyword fake matched "api" inside "capital", and the old data happened to hide it. New tests exposed it as a wrong pipeline answer. Use `\bword\b` regexes in fakes.
- **Verify every number you write into docs against data before committing.** Two claims typed from memory this project were wrong or unchecked: "208 offline tests" (actual 180; the 206 included pgvector, so count with `--collect-only` without the DB DSN) and "max_passages 8 recovers recall on all three sets" (true, but only confirmed after running it against the recordings). Run a small script for each new quantitative claim in KNOWN_ISSUES/README/RESULTS.
- **Rate limiters must be shared per key, not per client.** If every client instance builds its own limiter and semaphore, N concurrent clients get N× the published rate limit. Key a module-level `WeakKeyDictionary` by event loop, then by (backend, base_url, sha256(key)[:16]). Prove it with a mutation test: the test must fail when the old per-client limiter is restored.

## Verification

- Every review finding cites a requirement ID, and every requirement ID exists.
- Body citation numbers equal the Sources list numbers.
- Throughput and cost numbers re-derived once by hand.
- The Google Docs text export contains strings from the last section and from inside tables.

## References

- `references/jev-typesafe-api.md`: Jev / TypeSafe System One API facts, limits, weak spots and RAG cookbook patterns, verified September 2026.
- `references/vector-db-adapter-pitfalls.md`: per-store gotchas found while reviewing multi-DB adapter code.
- `scripts/verify_gdoc_export.py`: export a Google Doc as text and check that given strings survived.
- `references/prd-to-v1-buildout.md`: build-out recipe (repo, probes, fake-model tests, Docker conformance, CI, sample files, doc alignment), from the jev-rag build.
- `templates/test_samples_drift.py`: pytest that fails when `.env.example` or the example YAML drifts from the code.
- `scripts/live_envfile_check.py`: live-test a CLI's `.env` loading with a real key that is never printed, argv-passed or left on disk, plus a control run.
- `references/project-rename.md`: verified pre-v1.0 rename recipe covering GitHub, the PyPI distribution, the local directory and venv, the Google Docs titles, and the import-name collision check.
- `references/retrieval-benchmarking.md`: scale and messy-document benchmark method. It covers evidence-span scoring, held-out unanswerable questions, planted boilerplate and injections, per-config caches, PDF/HTML loader fixes, and the write-up rules.
- `references/pypi-publishing.md`: first-PyPI-release recipe. It covers safe token handling, README link absolutizing, build + twine check + wheel smoke test, the per-repo publish order, and the outside-in verification.
- `references/public-eval-datasets.md`: licences checked against primary sources, download URLs with MD5s, data shapes for BEIR SciFact/FiQA and QASPER, and run-design rules for the Measured milestone.
- `references/elevenlabs-agents-platform.md`: ElevenLabs Agents capabilities, the verified agent-as-code build recipe (tool/agent upsert, adding library voices, the English TTS model rule), measured chat cost, guardrail defaults, open-topic prompting, the Grok voice comparison, pricing, the clone-accent trap, and the `.md` docs trick.
- `templates/elevenlabs-text-spike.mjs`: Node 22 raw-WebSocket text-mode spike. It drives a real agent with scripted turns, then prints tool calls, voice-tag hits and the conversation's USD cost.
- `references/pronunciation-assessment-apis.md`: Azure / SpeechSuper / Speechace / wav2vec2 scorer comparison by language, the iOS Safari PCM capture trap, and open phrasebook sources (Tatoeba, kaikki, ts-fsrs).
