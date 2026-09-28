# Where agent spend goes: routing vs compaction (evidence before building)

When the user proposes a cost lever ("model routing could drastically reduce
costs"), price it on their own sessions before building. On this user's
install the intuitive lever (routing) was worth <1% and the other one
(compaction) 22–33%. Present that with numbers and a plan, then wait for
sign-off (the user prefers plan-first for paid work).

## Step 1: cost structure from `state.db`

Price each session's `input/output/cache_read/cache_write_tokens` with the
provider's list prices (Hermes' table lacks new models; see
`token-savings-measurement.md`). Observed: 90% of spend was cache read +
cache write, 10% output; top 5 sessions 76% of spend; ~280k tokens re-sent
per call in the big sessions; 49% of calls inside turns with ≥ 20 model
calls. Cost ≈ context size × number of calls.

Break the live context down by kind at every call (rebuild from `messages`
in order, restarting at each `[CONTEXT COMPACTION` summary): in the costliest
sessions **old tool traffic** (tool results + tool-call arguments from ≥ 2
user turns ago) was 70–80% of every call. Tool-call *arguments* (heredoc
scripts, file contents in `write_file`) were as big as results — include them.

## Step 2: why same-conversation model swapping rarely pays

- Cache-read price, not list price, dominates: Opus 5.5 reads cache at
  $0.20/M, Sonnet 4.5 at $0.30/M (more expensive), Haiku 4.5 at $0.10/M but
  its 200k window can't hold a 280k conversation.
- Switching model rewrites the whole context into the new model's cache
  (~$1 on Sonnet at 280k), which erases the saving on most turns.
- So a router must refuse when the prompt won't fit the cheap model's window
  or the rewrite costs more than the turn saves, and should only act on a
  **cold** turn (prompt cache already expired). Jermes' `switch_pays()` does
  this: compares `calls` requests staying (warm: cache reads; cold: one write)
  vs switching (full write on the cheap model + reads); unknown prices or the
  first turn of a session (current model unknown) → don't switch. The
  middleware records model, rough prompt size and last-request time per
  session for it.

## Step 3: offline cost simulator (`jermes costsim`)

`costsim.py` rebuilds every call's context and prices it under a policy with
the provider cache rules: call > TTL (5 min) after the previous one starts
cold (full write); otherwise read the cached prefix + write the delta. Fit a
fixed per-call overhead (system prompt + tool schemas) so the rebuilt
baseline matches Hermes' recorded tokens; skip sessions whose stored
transcript covers < 70% of recorded calls (pruned rows). Pitfalls hit:
compaction resets must be tracked as a context start index, not by
reassigning the item list; the gap for a turn is measured from the last
*model call*, not the last message.

Results (13 sessions, $742):

| Policy | Cost |
|---|---|
| Baseline | $742 |
| Stub old tool traffic at cold turns, Jev keeps top 30% | $580 (−22%) |
| Stub all old tool traffic at cold turns | $496 (−33%) |
| + route cold turns Jev rates easy/low-stakes to Haiku | −0.6% more |

Routing ceiling: Jev rated 5 of 137 cold turns easy and low-stakes. On 88
long turns (≥ 15 calls), 0 passed "self-contained AND mechanical AND
low-stakes" (closest: a ticket download that depended on conversation state;
a render comparison that was self-contained but needed judgment). A
judgment-heavy, single-strong-model user gains little from routing; users
with many short simple turns gain more.

## Hermes surfaces for building either

- **Compaction:** `agent/context_engine.py` `ContextEngine` ABC — required
  `name`, `update_from_response`, `should_compress`, `compress`; optional
  `select_context(request_messages, ...)` runs per provider request, may
  replace the request-only message list (history in the DB untouched), before
  cache-control is applied. Register with `ctx.register_context_engine(engine)`
  and select via `context.engine: <name>` in config.yaml. Hermes deep-copies
  the plugin engine per agent; if the copy fails it falls back to the
  built-in compressor. Only rewrite at cold turns so the rewrite rides on a
  cache miss that happens anyway.
- **Routing:** `llm_request` middleware (applied in
  `agent/conversation_loop.py` with `session_id`, `model`, `api_call_count`)
  fires in-process, so it also sees `delegate_task` children. The child's
  model comes from `delegation.model` config, not a per-call argument.
- Built-in compressor defaults here: threshold 0.5 of a 1M window, so context
  grows to 280–500k before anything shrinks it.

## Building the trimming context engine (Jermes v0.5, `jermes/context_engine.py`)

- **Subclass Hermes' own `ContextCompressor`** so compaction keeps working,
  and override only `select_context()` (+ `on_session_start/reset`). Filter
  constructor kwargs through `inspect.signature(ContextCompressor.__init__)`
  so other Hermes versions still load. Return `None` from the builder when
  `ContextEngine` has no `select_context`; the plugin then doesn't register.
- **Mirror ALL of Hermes' compression settings yourself.** When a plugin
  engine is selected, Hermes (`agent/agent_init.py`) passes it no compression
  config — it only calls `update_model()`. The first version rebuilt 5
  settings and silently dropped `min_tail_user_messages`,
  `proactive_prune_*`, `model_thresholds`, `threshold_tokens`, so switching
  engines would have changed compaction. Read `compression.*` from the user's
  config with the same defaults/validation as `agent_init.py`, then **prove
  it**: build Hermes' built-in `ContextCompressor` and yours from the same
  config and diff `vars()` attribute by attribute (non-callables) — must be
  empty, for the real config AND with extra settings added.
- **Deepcopy:** keep the decision engine (HTTP client, sqlite, locks) in a
  **module-level shared object** (`set_shared_engine(h.engine)` in
  `register`); the engine instance stays copyable.
- **Per-session state at module level, keyed by Hermes session id**
  (`trimmer_for(session_id)`, bounded LRU, cleared in `on_session_reset`).
  The gateway evicts and rebuilds agents mid-conversation (idle TTL, memory
  pressure), each with a fresh deep copy; per-instance state would treat a
  warm cache as cold and change the cached prefix. Take the id from
  `on_session_start(session_id)`. Test: two deep copies, same session id →
  the second makes no Jev call 60 s later and renders identical bytes.
- **Cold turns only:** decide only when `now - last_request > ttl_s` (300).
  Mid-loop requests only re-apply existing stubs.
- **Stubs by `tool_call_id`** (`<id>:r` results, `<id>:a` arguments),
  re-applied byte-for-byte on every request, so the trimmed prefix is what
  gets cached. Shorten long string values *inside* tool-call argument JSON so
  it stays valid; leave non-JSON args alone.
- **Re-decide everything at each cold turn** (build a fresh stub map, then
  swap it in); an item needed again comes back verbatim. On any Jev error,
  clear the stubs.
- Save full text to `data_dir()/full_results/<sha16>.txt` (0600) and name
  it in the stub. Never trim `memory`/`todo`/`clarify` or the last
  `keep_turns` (2) user turns.
- **Shadow mode must log WHAT would be dropped** (key, tool, short call,
  chars) plus the session id, so a later report can check whether the agent
  re-read any of it. Pass the shadow thread a copy of the message list.
- **E2E:** symlink the plugin, `context: {engine: jermes}`,
  `discover_plugins()`, `get_plugin_context_engine()`, `copy.deepcopy()`,
  `update_model(...)`, then a request through Hermes' real
  `agent.conversation_loop._apply_context_engine_selection`. Assert the stub
  AND that the original list is untouched. Also build a real `AIAgent` from
  the user's config and check `type(agent.context_compressor)`.
- Hermes raises the threshold to 0.75 for small windows (≤ 200k,
  `_SMALL_CTX_THRESHOLD_PERCENT`) for any engine — not a plugin bug.

## Multi-turn A/B with real cache expiry

- Task = first prompt + `followups` + `pause_s`. Run turns with
  `hermes chat -Q --yolo -q ...`, adding `--continue` for turns 2+ in the same
  isolated HERMES_HOME. **Both arms pause.** Isolate the point under test:
  every other point off in the on arm (`--guards-mode off` also removes risk
  gate / loop guard Jev calls).
- Runs are mostly sleep, so run pairs concurrently — but each Hermes run
  needs ~150–200 MB; on this 2 GB box cap with `--parallel 3` (8 would OOM).
- In the on arm confirm `Plugin 'jermes' registered context engine` in
  `logs/agent.log` and a `context_trim` row with `action=trim`.
- Two tasks: `session` (later questions answerable from the agent's own
  summary) and **`recall`** (later questions need a minor planted detail —
  one line in a 1,400-line log, one figure in a 40-section spec — unique in
  the file; check fails until all parts are right). The recall task is the
  real test that trimming is safe.
- Results, 5 pairs, Opus 5.5, 4 turns, 5.5 min pauses: $19.83 → $12.05
  (**−39%**), 5/5 correct both arms, every pair cheaper (−32% to −63%). Jev
  dropped every old item every time; on `recall` the agent grep'd/searched
  the file for the one line (more calls, much smaller prompts). Noise is
  large (same off task $2.70 vs $4.26). Untested: content that can't be
  recovered from disk (non-rerunnable command output, changed web pages).
- **Cost estimate:** a 4-turn pair costs ~$7 (not $1–2). Estimate from
  context size × calls × cache-write price per cold turn; if reality beats
  the estimate by > 2x, re-ask before the batch.

## Deploying to the user's own Hermes (shadow first)

1. Push and install the released plugin (`hermes plugins install
   owner/repo --enable`), not a symlink to the dev checkout.
2. Back up `config.yaml` to `~/.hermes/data/<plugin>/backups/` first.
3. Plugin config: only the new point in `shadow`, every other point `off`.
4. `hermes config set context.engine jermes`. **It rewrites the file and
   dropped the trailing commented-out "Fallback Model" block.** Afterwards
   diff against the backup (text diff with secrets filtered, plus a YAML
   key-walk diff); restore dropped comment blocks from the backup so the only
   differences are the intended keys.
5. `hermes <plugin> status` (key resolves, modes right), restart the gateway
   (`hermes gateway restart`; systemd `hermes-gateway`), grep the log for
   `registered context engine`, and run one shadow decision on a real past
   session to show it logs and leaves the request unchanged.
6. **Verify it is collecting, not just loaded**: within minutes, run
   `hermes <plugin> check` and query the live decision log
   (`~/.hermes/jermes/decisions.sqlite`) for recent rows with no error. A
   shadow point that fails open (e.g. the Jev gateway returning 403) looks
   exactly like a quiet one. "Loaded but not logging" is a blocker to report.
7. Tell the user the rollback command (`context.engine compressor` + restart)
   and what evidence to collect before promoting to enforce.
