# Jev (TypeSafe System One) as a decision backend

Jev was verified on 2026-09-24 while building the Jermes plugin
(github.com/MersivMedia/jermes, local path `~/jermes`). The PRD is in the repo
at `docs/PRD.md` and in a Google Doc under Drive `Hermes Agent/Research/`.

## What Jev is

Jev doesn't generate text. You send it a `state` (a string, object, or array)
plus named typed questions. It evaluates every question in parallel, each on
its own, and returns typed answers with probabilities.

- **Price:** $0.042 per million input tokens; output is free.
- **Speed:** vendor-reported ~70–500 ms.
- **Context:** 64k tokens per request, or 32k for the state plus the longest
  single question.
- **Input:** text only.

| Type | Request `criteria` | Answer |
|---|---|---|
| `noul` (yes/no) | optional `{"true": ..., "false": ...}` | `noul`: P(yes). No confidence field |
| `choice` | `{option: description or null}`, 2–255 options | `choice`, `probabilities`, `confidence` |
| `score` | ordered list, 2–10 levels | `score` (probability-weighted), `probabilities`, `legend`, `confidence` |

## Access: Vercel AI Gateway is the default route

The user chose to reach Jev through Vercel rather than a TypeSafe key.

- **TypeSafe-compatible endpoint:** `POST https://ai-gateway.vercel.sh/typesafe/v1/systemone`
  with model `typesafe-ai/jev`. It uses TypeSafe's own wire format, so a
  TypeSafe client only needs its base URL changed.
- **Native endpoint:** `POST https://ai-gateway.vercel.sh/v1/evaluate`. It uses
  the `boolean` + `probability` dialect instead of `noul`, and camelCase
  `usage.inputTokens`. A parser should accept both dialects.
- **Auth:** `Authorization: Bearer $AI_GATEWAY_API_KEY`, a key starting `vck_…`
  that the user creates in the Vercel dashboard. A Vercel account/API token
  (`VERCEL_TOKEN`) returns **401** here.
- **OIDC alternative:** OIDC tokens from `vercel link` + `vercel env pull` work,
  but expire every 12 h, so a long-running harness needs the API key.
- **Card requirement:** HTTP 403 `customer_verification_required` means the
  AI Gateway hasn't verified a card for the Vercel team. It blocks every model,
  not just Jev. Upgrading the team to Pro did NOT clear it. The user also had
  to complete the separate "add credit card" modal in the team's AI tab (the
  URL in the error message). A key that authenticates can still read
  `GET /v1/credits`, which returns 200 with the balance, so use that to
  confirm which team the key belongs to. Report the 403 as a blocker; it
  isn't a code bug.
- **Rate limits (measured 2026-09-24):** about 30 requests and 250k tokens per
  rolling window. Overruns return 429 with `retry-after` (~24 s) and
  `x-ratelimit-*` headers. Batch jobs need about 2 s between requests. A live
  agent using every decision point could hit this limit, so budget for it
  before any point leaves shadow mode.
- **Transient 503s** (`service_unavailable_error`) came in bursts of one to
  three on launch day. They're retryable.
- **Free-tier model gating can reach Jev itself.** On 2026-09-26 every Jev
  call started returning HTTP 403 `no_providers_available` "Free tier users
  do not have access to this model" (before that it hit only paid models).
  Live hooks fail open, so nothing breaks, but shadow logs stay silently
  empty. Before relying on a live or shadow deployment, run `jermes check`
  and look for recent rows in the decision log; if it's this 403, the fixes
  are paid Vercel credits or switching to the OpenRouter/TypeSafe route.
- **Measured latency** through the gateway was a ~2 s median on the ~8k-token
  skim (a single tiny call took 835 ms), well above the vendor's 70–500 ms.
  Size hook deadlines from measured numbers.
- **Pricing check:** `GET /v1/models` lists `typesafe-ai/jev` with
  `input 0.000000042`, `output 0`.
- **Zero data retention:** add
  `"providerOptions": {"gateway": {"zeroDataRetention": true}}` to the request.
- **Direct route:** `https://api.typesafe.ai/v1/systemone`, model `jev-1.13.0`,
  key `TYPESAFE_API_KEY`.
- **OpenRouter route:** `POST https://openrouter.ai/api/v1/systemone`, model
  `typesafe/jev-1.13`, `Authorization: Bearer $OPENROUTER_API_KEY`. This is the
  same TypeSafe wire format (OpenRouter adds `id`, `provider`, `usage.cost`).
  Docs: `openrouter.ai/docs/guides/community/typesafe-sdk.md`. **Jev is NOT
  in OpenRouter's chat `GET /api/v1/models` catalog** (460 models, none
  matching), so a catalog check alone wrongly concludes "not on OpenRouter".
  Check the provider's docs before telling the user a route doesn't exist.
  The `~typesafe/jev-latest` alias is reportedly unreliable, so pin the
  versioned ID. Also an alpha native API: `POST /api/alpha/decisions`.
- **Multi-provider plugins:** pick the backend automatically from whichever key
  is set, in this order: Vercel, TypeSafe, OpenRouter. OpenRouter goes last
  because many Hermes users already have `OPENROUTER_API_KEY` for their main
  model, and a Jev-specific key should win over it. An explicit
  `backend.name` or `JERMES_BACKEND` overrides the order. In `plugin.yaml` use
  `optional_env` (rich dicts with description, url, secret) for the keys, NOT
  `requires_env`. `hermes plugins install` prompts for every `requires_env`
  entry, so listing all three forces users to face prompts for keys they
  don't have.
- **Fetching docs:** Vercel docs have markdown twins. Append `.md` to any
  vercel.com docs or changelog URL, or use `docs.typesafe.ai/llms.txt` plus
  `<page>.md`. These are far easier to read than the rendered HTML.

## Design rules (from TypeSafe's "jaggedness" page and cookbooks)

- Code owns the policy. Map each (answer, confidence) pair to an action through
  thresholds that scale with stakes, using three bands: act, confirm, fall back.
- Every Choice needs a real `none`, `other`, or `unclear` option, because
  probability has to land somewhere.
- Do no arithmetic, counting, or date comparison in Jev. Extract the parts as
  Choices and compute in code.
- Keep state minimal. Accuracy drops as irrelevant content grows. Point
  questions at named fields with backticks: `` `arguments` ``.
- Select, don't generate. Use a regex or an LLM to propose candidates and let
  Jev pick one of them.
- For more than 255 options, rank chunk by chunk, then rerank the top few with
  richer text. This is the skill-suggestion cookbook pattern; TypeSafe
  measured it on the Hermes roster, cutting wrong loads from 16.8% to 7.3%.
- **Skill selection: what the user asked for (v3, current design).** The user
  wants Jev to FILTER 100+ skills into a short LIST for the agent (primary plus
  supporting skills, e.g. `research-design-documents` + `grounded-citations`),
  with "no skill needed" as an explicit option. The design:
  - **"No skill needed" is a Choice option** (`(no skill needed)`, with
    criteria describing chat, status questions, acknowledgements and uncovered
    requests) in BOTH calls. It replaces the cookbook's three gate Nouls and
    their hand-tuned threshold. Chunks hold 254 skills plus none, and none
    wins the skim only if it tops EVERY chunk.
  - **Skim:** if none wins, stop after one call. Otherwise carry the top 5.
  - **Select:** a Choice over the shortlist plus none, and one Noul per
    candidate: "would loading X help with all or a distinct part of the
    request?"
    - Primary skill: the Choice winner.
    - Supporting skills: other candidates whose Noul is at least 0.50, up to
      4 skills in total.
    - The Choice answers "which one most"; the Nouls answer "does this one
      help at all".
  - **Context:** the state is `{"request": ..., "recent_context": ...}`,
    built from the last 4 user/assistant text messages (400 characters each).
    Tool calls, tool results and `[System note:`-style harness messages are
    stripped. Hermes passes `conversation_history` to `pre_llm_call` at no
    cost. It may already end with the current request, so drop that before
    formatting. Questions must say to judge the latest `request` and to use
    `recent_context` only to resolve references.
  - **Injected block:** one skill → "Relevant skill for this request: X.
    Ignore it if...". Several → a numbered "primary first, then supporting"
    list. None → "No skill is needed for this request."
  - Truncate skim option descriptions to about 200 characters (206 skills ≈
    8.3k tokens, inside Jev's 32k budget).
  - **Roster:** read on EVERY Jev call via `tools.skills_tool._find_all_skills()`,
    so skills created mid-session are seen on the next request and disabled
    skills are never offered. This was the user's explicit requirement.
    SKILL.md bodies are fetched lazily for the shortlist only.
  - **Context budget:** the user chose **10 messages × 400 characters**
    (about 1k tokens) as the default on 2026-09-25. The state plus the longest
    question may use 32k tokens and the skim question is about 6.6k, so
    roughly 20k tokens of context would fit, at about $0.0002 per extra 2k
    tokens. The risk is TypeSafe's "large irrelevant state" failure mode, not
    cost. Untested next ideas: longer messages, plus the skills already
    loaded this session and the recent tool names. Settle each by rescoring
    the hand-labelled set, not by raw agreement.
- **Labelled scores (2026-09-25, batch 1: 40 turns, 29 needing skills, 11
  none; same turns in both arms):**

  | Metric | 4 msgs | 10 msgs | Agent |
  |---|---|---|---|
  | Decision accuracy | 88% | 90% | 35% |
  | Primary hit | 66% | 69% | 7% |
  | Recall | 69% | 63% | 4% |
  | Precision | 79% | 62% | 75% |
  | False alarms | 0% | 9% | 0% |
  | Misses | 17% | 10% | 90% |

  Ten messages fixed 2 turns and broke 2. It lowers misses and adds extra
  suggestions; the user accepts that trade.
  - **Anchoring caveat:** labels were made on a sheet showing the 4-message
    list, and 26 of 40 match it exactly.
  - **Main remaining miss:** the `runpod-pods` description.
  - **Where the labels live:** `~/.hermes/jermes/labels.jsonl` (copy in
    `/tmp/<plugin>-backup/`).
- **v3 A/B results (2026-09-24, 206 skills, paired on identical turns):**

  | Turns | Measure | Request only | + last 4 messages |
  |---|---|---|---|
  | 32 where the agent loaded a skill | agent's skill in Jev's list | 50% | 63% |
  | 32 where the agent loaded a skill | Jev primary = agent's skill | 34% | 38% |
  | 49 where the agent loaded nothing | Jev said none | 53% | 41% |

  (The v1 gate design said none on only 19–27% of these turns.)
  - **What context gains:** follow-ups resolve ("process this video like the
    previous one" → the brand-edit skill; a bare music link → audio mixing).
  - **What it costs:** short follow-ups inherit skills from the earlier
    topic ("let's try masked" → ComfyUI skills).
  - **Decision:** context stays on (a missed right skill costs more than an
    ignorable extra one). The tradeoff needs human labelling before promotion.
  - **Caveat:** these numbers came from replay before the blank-row history
    fix, so the context arm saw less conversation than live. It probably
    understates context's value.
  - **Labelling set:** batch 1 (40 turns) is the Google Sheet "Hermes Agent -
    Jermes skill labels (batch 1)" in Drive `Hermes Agent/Research/`, id
    `<DRIVE_FILE_ID>`. Import with
    `jermes label --import gdrive:<id>`, then run `jermes score`.
  - **Cost:** ~10k tokens per request (skim ~8.3k + select ~2k). About 290
    calls used 1.56M tokens ≈ $0.07.
- **Replay cost estimate:** about 7.5k tokens for the skim plus about 2k for
  the rerank per turn, so 50 turns ≈ 0.5M tokens ≈ $0.02. Cached reruns are
  free. Measured: 84 live calls used 383k tokens (≈ $0.016).
- **v1 baseline (superseded by v3 above):** with only the latest message and
  gate Nouls at 0.30, Jev's #1 matched the agent 46% of the time (sample
  shrunk by errors), and it ranked skills on about 80% of turns where the
  agent loaded none. Those two gaps drove the v3 changes. Compare any future
  threshold change against the v3 table, on the same turns.
- **Skill overlap / duplicate detection (`skill_overlap`, built 2026-09-26,
  offline-tested only).** The user asked for (a) merge suggestions across the
  installed library and (b) an overlap check whenever a new skill is about to
  be created, whether the user asked for it or the agent decided to. Design:
  - **Two steps per target skill.** Shortlist: the skim Choice over the whole
    roster (254 per chunk + an explicit "no overlapping skill" option),
    asking which covers the *same job* (not same area or tools); keep up to
    4 with P ≥ 0.08. Judge: one request with target and shortlist side by
    side (description + 1.5k-char SKILL.md excerpt), per candidate a Noul
    "same job?", a Noul "could one skill serve both without becoming a
    grab-bag?", and a Choice of relation (duplicate / target contained /
    existing contained / partial / related / unrelated). Nothing shortlisted
    means one request and no judge call.
  - **Create check** hooks `pre_tool_call` on `skill_manage` with
    `action: create` (parse name/description/body from the `content`
    frontmatter). In `advise`, overlap returns a `block` whose message names
    the skill(s), says to prefer `skill_manage patch` on the existing one, and
    — if the user asked for the skill — to tell them and let them choose.
    **Shown once per (session, proposed name)**, so retrying the same create
    goes through; nobody gets stuck. Shadow logs off-thread. Needs a longer
    deadline than live hooks (two sequential calls, 12 s, still under the
    30 s hook timeout): add a per-call `deadline_s` through
    `engine.decide` → `client.ask` rather than raising the global one.
  - **Audit** (`jermes skills-audit`): run the same check for each local skill
    against the whole library, union-find the overlapping pairs into groups,
    and pick the keeper in code (bundled/hub skills always win because updates
    overwrite them; otherwise the one others are "contained in", then the
    larger body). **Suggestions only, never edits** — Hermes' curator already
    has an opt-in LLM consolidation pass that edits; this is the review-first
    counterpart. ~2 requests per skill (~$0.01 for 200 skills).
  - **Provenance:** use Hermes' public `tools.skill_usage.is_bundled`,
    `is_hub_installed`, `is_agent_created`, not private manifest readers.
- A Noul threshold isn't transferable to a Choice, and P(x) + P(not x) ≠ 1
  across separate questions.
- Jev isn't hardened against adversarial state. Use it as defence in depth
  only, and strip shell comments before judging commands.
- Pin a versioned model ID once thresholds are tuned, and cache decisions by
  (model, canonical state, question spec) so the harness stays deterministic.

## Evidence caveats to repeat in deliverables

- The headline 193.6x speed / 444.6x cost figures are vendor-run and scored
  against averaged LLM answers, not ground truth.
- On TypeSafe's own workflow data, Jev matched mid-tier models on agreement
  (~67.8%) but trailed the best ones by ~6 points.
- "Can't hallucinate" means only that the output always fits the schema. It
  says nothing about correctness.
