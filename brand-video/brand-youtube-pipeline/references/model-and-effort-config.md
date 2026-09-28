# Hermes model + effort configuration for the video pipeline

Single source of truth for which model + reasoning effort the [brand]
pipeline runs on. Updated when the user requests a model switch.

## Current locked config (May 2026)

```yaml
model: claude-opus-4-8
agent:
  reasoning_effort: low
delegation:
  model: claude-opus-4-8
  reasoning_effort: low
```

Both the main session AND delegated subagents run on `claude-opus-4-8` at
`reasoning_effort: low`. Subagents inherit the `delegation.*` values
automatically — no per-call `model=` override is needed in `delegate_task`.

## Why opus-4-8 low (not sonnet, not opus-4-7 medium)

- **Adaptive thinking.** Opus 4.8 ships with model-side adaptive reasoning:
  at `effort: low` it responds directly on simple lookups and short steps,
  and only spends thinking tokens on genuinely hard multi-step problems.
  Previous Opus generations spent thinking tokens uniformly.
- **Cost.** Low-effort opus-4-8 is materially cheaper than opus-4-7 at
  medium for routine pipeline work (slide reskin orchestration, Drive
  uploads, chunk-emit dispatch). The Sonnet-override workaround that was
  needed in the opus-4-7 era is no longer the right cost answer.
- **Quality on hard phases.** Phase 3 script rewrite, Phase 8b metadata
  copy, and pose-rotation reasoning still get full opus-4-8 capability
  when the adaptive thinker decides the step warrants it.

## Switching procedure

```bash
hermes config set model claude-opus-4-8
hermes config set agent.reasoning_effort low
hermes config set delegation.model claude-opus-4-8
hermes config set delegation.reasoning_effort low
```

Valid effort levels: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`.
See `hermes_constants.py::VALID_REASONING_EFFORTS` for the authoritative
list and `parse_reasoning_effort()` for the mapping.

**Changes take effect on the NEXT session.** Hermes snapshots the model
config at session start; `/reset` (CLI) or `/restart` (gateway) is
required to pick up new values mid-conversation. Don't tell the user a
config change is live in the current turn — it isn't.

## Verifying it took effect

```bash
grep -nE "^model:|reasoning_effort|^delegation:" ~/.hermes/config.yaml
```

Confirms all four lines landed in the YAML. The TUI `hermes config show`
output displays the model field but masks `reasoning_effort` as
"Reasoning: off" (that field is the *show-reasoning UI toggle*, not the
effort level) — don't trust the show output for verification, grep the
YAML directly.

After a session restart, you can verify delegated subagents inherited
the override by checking any `delegate_task` result's `tool_trace[0].model`
field — it should read `claude-opus-4-8`, not the older `claude-opus-4-7`
or `claude-sonnet-*`.

## Tuning effort per phase (future direction, not yet active)

If specific phases burn too many tokens at `low` effort (rare with
adaptive thinking, but possible on dense Phase 3 rewrites), drop the
delegated subagent's effort further via per-call override:

```python
delegate_task(
    goal="...",
    context="...",
    model={"model": "claude-opus-4-8", "reasoning_effort": "minimal"},
)
```

Don't preemptively do this — the config default of `low` is the right
starting point. Only override per-call when a specific phase has
demonstrated cost issues across multiple episodes.

## What changed and why

The `references/` history of this skill previously documented a
"delegate to Sonnet for cost control" pattern with mandatory
`model={"model": "claude-sonnet-4-5"}` override on every `delegate_task`
call. That guidance was correct in the opus-4-7 era but is OBSOLETE
under opus-4-8 + low effort + adaptive thinking. The skill's
"Cost discipline" and "Delegate heavy episode pipelines" sections were
patched to remove the Sonnet-override requirement; this reference
exists so future agents can find the rationale without spelunking the
session history.
