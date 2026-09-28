# Offline shadow replay over real Hermes sessions

This is the fastest way to evaluate a decision-layer plugin. You don't wait for
new sessions: replay past user turns from Hermes' own session database through
the plugin's decision code, offline. It was built as `jermes replay` in
`~/jermes/jermes/replay.py`; copy that module as a starting point.

## Data source: `$HERMES_HOME/state.db`

Open it **read-only** so a running Hermes is never disturbed or locked:
`sqlite3.connect(f"file:{db}?mode=ro", uri=True)`.

Relevant columns in the `messages` table: `id`, `session_id`, `role`
(`user`/`assistant`/`tool`/`session_meta`), `content`, `tool_calls` (a JSON
list), `tool_name`, and `timestamp`.

**Turn reconstruction:** a turn is one `role='user'` row plus every assistant
row after it in the same session, up to the next user row (`MIN(id) WHERE
role='user' AND id > ?`). Tool calls sit in the assistant rows' `tool_calls`
JSON as `[{"function": {"name", "arguments": "<json string>"}}]`.

**Filter out harness-generated "user" messages.** On this box roughly a
quarter of user rows are synthetic, with prefixes such as:

- `[IMPORTANT: ...`
- `[ASYNC DELEGATION ...`
- `[System note: ...`
- `[CONTEXT COMPACTION ...`
- `[The user sent an image ...`

Drop them with a prefix regex, and drop very short turns (under 15 characters,
such as "ok" or "yes").

## Weak labels already present in the data

- **Skill choice:** the first `skill_view` call in the turn gives the skill the
  agent actually loaded. Ignore calls that carry `file_path`; those load
  sub-files, not a skill choice. Normalise names with `split(":")[-1].split("/")[-1]`,
  because `skill_view` accepts `category/name` and `plugin:name`.
- **Risk gating:** replay the gated tool calls that really happened (terminal,
  write_file, ...) through the risk policy, and list what it would have
  blocked or escalated.

These labels are **weak**. The agent itself loads the wrong skill part of the
time (TypeSafe measured 16.8% on the Hermes roster). Report agreement metrics
as top-1, top-3, and "said none when agent loaded none", export the
disagreements to JSONL with an empty `label` field for a human to fill in,
and never tune thresholds on raw agreement alone.

## Mechanics

- Force synchronous evaluation during replay
  (`harness.background_shadow = False`). Otherwise shadow-mode points submit
  work to the background pool, and the replay returns before any decisions
  are logged.
- Replay must never mark decisions `applied`. Replay sessions get a
  `replay:<session_id>` id so they can be told apart in the log.
- The decision cache makes reruns free, so iterate on policy thresholds by
  re-running.
- **Run replay in batch mode.** Pace requests (about 2.1 s apart for a gateway
  allowing ~30 requests per minute) and raise the client's deadline and retries
  so `retry-after` is honoured. Without this, most turns failed on 429s; with
  it, 1 of 50 did. A 50-turn run then takes about 5–8 minutes, so run it in the
  background with notify rather than in the foreground (600 s cap).
- **Dedupe copied requests.** Context compaction and session forks copy
  earlier user messages into new sessions, so the same request appears several
  times. Key on the whitespace-normalised first 500 characters; the newest
  copy wins.
- **Redact what replay prints and writes.** Past turns can contain pasted API
  keys. Run the request text through the same redactor used for the outbound
  payload before it goes into progress lines, the JSON report, or the JSONL
  export. Test that a constructed fake key appears in none of them.
- Test it with a synthetic `state.db` that uses the same columns: one covered
  turn with a `skill_view`, one `file_path` sub-load, one synthetic
  `[System note:` turn, and one too-short turn. Also assert the db file is
  byte-identical afterwards, to prove it was opened read-only.
- **Rebuild the live hook's context.** When a decision point reads
  `conversation_history`, replay must feed it the same thing: the prior
  user/assistant rows of that session (`id < request id`), oldest first, with
  **blank-content rows excluded**
  (`AND content IS NOT NULL AND trim(content) != ''`, `LIMIT 20`).
  Tool-call-only assistant rows have empty content. In a plain `LIMIT 12` they
  took 272 of 918 slots (30%), starving tool-heavy turns of context and making
  the "with context" arm of an A/B understate context's value. Otherwise
  replay measures a different system than the one that runs live.
- **Retry failed turns in a later pass.** Gateway 503 bursts can outlast the
  client's per-call retries. After the first pass, sleep about 60 s and re-run
  only the failed turns, repeating up to 3 times. In one run this took 32
  failed calls down to 0. The cache makes the successful turns free on
  re-runs.
- **Compare design variants as a PAIRED A/B.** Run both arms (for example with
  context vs `--no-context`) on the identical turn list, retry until every
  turn has an answer in both, and only then compare. Two separate runs that
  each lose different turns to errors aren't comparable. Report the number of
  paired turns, the counts per arm, and the specific turns where the outcome
  flipped, with the request text. The flipped turns are what explain a
  tradeoff to the user.
- **Measure both classes of turn.** Covered turns (the agent loaded a skill)
  measure recall: is the agent's skill in the list, and is it primary.
  Uncovered turns (the agent loaded nothing) measure restraint: did it say
  none, and how many skills per turn. A change that raises recall usually
  lowers restraint, so always show both.
- **Latency logged during replay is not live latency.** Pacing sleeps and
  `retry-after` waits land inside the logged `latency_ms` (the skim's p90 was
  32 s). Quote single live-call timings instead.

## Scale seen on this box (2026-09-24)

About 520 user rows, of which 400 were real after filtering. Only 36 of those
contained a `skill_view`, so use `--with-skill` to evaluate skill ranking on
the covered turns specifically. Hermes' `_find_all_skills()` (what the agent
actually sees) returned 200 skills. A direct scan with
`agent.skill_utils.get_all_skills_dirs` + `iter_skill_index_files` returned
206: that path skips disabled and platform-gated skills' filtering, so don't
use it for a roster. The raw `find SKILL.md` count was higher still.

Weak labels only measure agreement. For correctness, add a hand-labelled
answer key: `hand-labelled-eval.md`.
