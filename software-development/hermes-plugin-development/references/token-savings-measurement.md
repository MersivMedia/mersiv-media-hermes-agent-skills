# Measuring token savings from a decision-layer plugin

Use this when the user asks whether the plugin *reduces tokens*, as opposed to
whether its decisions are *correct*. They are different measurements. Accuracy
tests (replay agreement, hand-labelled scores) and the plugin's own call cost
(e.g. about 10k Jev tokens, roughly $0.0004 per request) say nothing about how
many main-model tokens were saved. Say that plainly first, then offer the
measurement tiers below. This user chose tiers 1 and 3 and wanted both built
AND run in the same turn.

## Baseline: Hermes already records real usage

`$HERMES_HOME/state.db` (open read-only: `file:...state.db?mode=ro`):

- `sessions` columns: `input_tokens`, `output_tokens`, `cache_read_tokens`,
  `cache_write_tokens`, `reasoning_tokens`, `estimated_cost_usd`,
  `actual_cost_usd`, `api_call_count`, `model`.
- `messages`: `role`, `tool_name`, `content`, `token_count`, `session_id`, `id`.

**Don't trust `estimated_cost_usd` for new models.** Hermes' price table
(`agent/usage_pricing.py`) lacked Opus 5 / 5.5 and estimated ~$1 for what was
really ~$660 of usage. Price tokens yourself from the provider's official
pricing page (fetch `https://platform.claude.com/docs/en/about-claude/pricing.md`
for Anthropic), keep it as a sourced override table with the check date, and
fall back to Hermes' table only for models it knows. Also drop sessions whose
counters are clearly broken (e.g. zero api calls with tokens) before summing.

Input dominates (~99% of tokens), so savings come from what is **re-sent** on
every call, not from shorter replies.

## Where cuttable tokens are (query recipe)

For each `role='tool'` message, count later `role='assistant'` messages in the
same session. Tool-result characters × later calls ÷ 4 is an **upper bound** on
re-sent tokens: it ignores context compression, and chars/4 is only an
approximation. Group by `tool_name`, and count results over about 8,000 chars
(about 2k tokens), which are what a result filter targets.

Observed on that install: tool output ~1.9M tokens first time, up to ~550M
counting re-sends (~39% of input); 179 results over ~2k tokens held 42% of
tool-output tokens; 33 `skill_view` loads ~3.35k tokens each (~4% of input).

## Tier 1: offline estimate (built as `jermes savings`)

- **Share one code path with the live hook.** Split the hook's eligibility +
  question building into a pure `prepare_filter(tool, result, status, task)`
  used by both the hook and the estimator, so the estimate applies exactly the
  live rules (tool allowlist, min/max chars, section count).
- Rebuild each result's turn request from `state.db`, call Jev for real on
  eligible results, multiply removed chars by later calls.
- Add `input_tokens` to the engine's `Decision` so Jev's own cost is summed.
- **Sanity-check any suspiciously high removal** by reading what was dropped
  (a 90% drop turned out to be an injected directory listing: correct).
- Result on the real install: ~25M tokens (2.4% of prompt tokens, ~$11.60 of
  ~$948), Jev cost $0.03; skill-load savings negligible ($0.06); 3 sessions
  held 89% of the saving, so report it as lumpy.

## Tier 3: task-matched A/B (built as `jermes ab`)

Harness design that produced trustworthy numbers:

- **Fresh `HERMES_HOME` per run**: copy only `.env` + `auth.json` (chmod 600),
  the `model`/`providers`/`auxiliary` config keys, symlink `skills/`; memory
  off, approvals off, `--yolo`. "on" arm symlinks the plugin repo into
  `plugins/` and writes its config; "off" arm has no plugin at all.
- **Scrub the parent's env.** A child `hermes chat -Q -q` launched from inside
  a Hermes session inherits `TERMINAL_CWD`, `HERMES_SESSION_*`,
  `_HERMES_GATEWAY` etc. and ran in the *parent's* working directory. Drop
  every `HERMES_`, `_HERMES`, `TERMINAL_`, `JERMES_`, `BROWSER_`, `SUDO_` var,
  then set `HERMES_HOME`, `TERMINAL_CWD`, `PWD` to the run's own dirs. The
  first single-pair result was invalid because of this.
- **Preflight** before any spend: fail if the decision service's key isn't in
  the child env (the "on" arm would silently equal "off"), and strip that key
  from the "off" arm.
- Deterministic fixtures + automatic checks per task; alternate arm order per
  repeat; read tokens from the child's own `sessions` row; add Jev cost to the
  "on" arm.
- **Cost control:** run ONE task pair first, report its real cost, then ask
  how many repeats. Recommend 3 (noise: the same task varied 138k–194k prompt
  tokens with the plugin off). If the clarify times out, go with the
  recommended option and say so.
- Keep test homes out of `/tmp` in unit tests (`monkeypatch tempfile.tempdir`).

**Design tasks so the decision point actually fires.** In the first batch the
agent grepped big files instead of reading them, so the result filter never
ran and the A/B measured nothing about it. Check `applied` counts per run
before interpreting. Tasks that force a full read: a long transcript where the
answer changes over time (search finds stale answers), and release notes where
the answer has no greppable keyword; tell the agent to read in full.

Results (Opus 5.5 agent, 3 repeats): generic 6-task batch +1% cost (noise;
filter never fired; a followed skill suggestion doubled calls on an easy
task). Forced-read tasks: transcript −33% cost, release notes +5%, total −16%.
**Behaviour-change finding:** when the filter kept only the right section
(score 0.82 vs next 0.28), the agent distrusted the "sections omitted" note
and grepped the file itself, spending more. Savings depend on the agent
accepting trimmed output; the note wording is the next lever.

**How to diagnose an arm that cost more.** Re-run that single task/arm with
`run_one(..., keep=True)`, then read three things from the kept home before
deleting it:
- `jermes/decisions.sqlite`: per decision `action`, `applied`, and
  `detail_json` (`kept`/`chunks`/`kept_idx`) — did the point fire, and what
  did it keep?
- `state.db` `messages`: each assistant `tool_calls` entry and each tool
  result's length plus whether it carries the filter note — what did the
  agent do *after* seeing the trimmed result?
- For the filter's judgment itself, call the decision offline on the same
  fixture with a patient client (60–90 s deadline, retry loop with a 30 s
  sleep on 503) and print the per-section scores around the answer section.
Separate the two questions this answers: was the plugin's decision right
(here yes: the answer chunk scored 0.82) vs did the agent use it well (here
no). Report them separately to the user.

### Making filtered results usable (v0.5 iteration)

What each change did on the forced-read A/B (3 repeats each):

| Version | Transcript | Release notes | Total |
|---|---|---|---|
| v0.4 note ("sections omitted") | −33% | +5% | −16% |
| + line-mapped omissions, full copy saved on disk, "read only the range you need" | **+24%** | −11% | +9% |
| + targeted reads never filtered, shorter note | mixed | ≈0% | +5% cost, −10% prompt tokens |

Lessons:
- **Never filter a targeted read.** The agent re-read omitted ranges with
  `read_file(offset, limit)`, the filter screened *those* too and hid the very
  lines it asked for, so it re-read again and then grepped. Skip `read_file`
  with an explicit offset or a limit < default, and commands already piped
  through head/tail/sed/grep/awk/jq. Say in the note that range reads are
  never screened.
- **An offer to read omitted ranges gets taken** when the user's request says
  "read the whole thing". Ask Jev, in the same request, whether the task needs
  the complete output (`needs_all`); pass through when ≥ 0.6. Validated live:
  "summarise every release" 0.95, "translate" 0.97, specific lookups 0.07–0.29.
- **Chunking:** Hermes' `read_file` numbers blank lines (`   311|`), so a
  blank-line splitter must strip the prefix, or Markdown sections get cut
  every few lines; split blank-line-free walls (transcripts, logs) by line
  count so one chunk can't hold most of the text. Prefix a kept chunk that
  lacks its own heading with `(under: <heading>)`.
- **When prompt tokens fall but cost rises, split cost by bucket.** Cache
  writes went 54k → 81k on "on" runs: a followed skill suggestion loaded a
  ~5k skill up front and the range re-reads added fresh content. Read
  `cache_read_tokens` / `cache_write_tokens` per run, not just totals.
- A filter that errors (a Vercel 503) looks like "didn't fire" in the A/B;
  check the decision row's `error` before concluding the policy passed.

## Caveats to state with any estimate

- **Dollars fall less than tokens:** cache reads are billed at a fraction of
  input price.
- **List-output skill selection can increase loads**; measure before promoting.
- **Offline estimates can't see behaviour change** (the A/B above shows it
  matters in both directions).

## Tier 2 (not yet built)

Shadow logging: each live decision stores its estimated saving; a `savings`
subcommand totals it per decision point.
