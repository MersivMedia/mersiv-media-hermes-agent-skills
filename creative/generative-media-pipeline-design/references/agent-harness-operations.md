# Operating a generative pipeline from an agent harness

How to run one of these pipelines from Hermes / OpenClaw / Claude Code, and —
more importantly — **where the agent must stop**. Derived from a session that
built the pipeline inside a harness and then shipped the harness layer as part of
the repo.

## The boundary is the whole design

```
LIVE      deterministic service, NO agent
          state machine + render queue + player
          ONE constrained, schema-validated LLM call per phase

BETWEEN   agent harness, scheduled or on demand
          QC sweeps · asset regeneration · drift analysis · telemetry review
          prompt and story-spine proposals

GATE      human review before merge
```

**Why the live tier is not an agent.** During a run the system has a hard
deadline: the next clip must exist before the current one ends. The state machine
already makes one strict-JSON call per phase. Adding open-ended tool use there
trades bounded latency for unbounded latency in the one place the product cannot
absorb it.

**Why the offline tier should be.** Deciding *which* asset failed and *why*,
whether a prompt revision helped, whether drift is worsening — judgement work
over noisy artifacts, which is what an agent with shell access is good at.

## What to automate, ranked

| Task | Automate? | Why |
|---|---|---|
| QC sweeps | **yes, fully** | measurement only, no spend, no writes |
| Drift analysis between renders | **yes, fully** | read-only, high signal |
| Normalization | **yes** | deterministic, reversible |
| Asset regeneration | **with approval gate** | costs money |
| Prompt revisions | **propose only** | needs a human read of the output |
| Story/spine edits | **propose only** | authorial judgement |
| Validator / schema changes | **never** | the agent relaxes constraints instead of meeting them |
| Anything in the live path | **never** | latency is the product |

## Two guardrails to state explicitly in every task prompt

1. **Never optimize for audience votes.** Tuning content toward crowd preference
   converges on mush and rebuilds the infinite-content machine the authored
   skeleton exists to prevent. Optimize for **completion rate** and **payoff
   recognition** instead.
2. **The agent may never edit its own validator.** Prompts, spines and assets are
   fair game for automated proposals. Schema and validation rules stay
   human-gated — otherwise the system meets its constraints by deleting them.

## Task prompt shapes that worked

### QC sweep — safest first automation

```
Run the asset QC sweep at <repo>.
For each character dir: python engine/qc.py <dir> --costume "<canon string>"
For each location dir:  python engine/qc.py <dir> --graded

Report ONLY which dirs fail, which gate, and the measured value against
tolerance. Do not regenerate anything. Do not edit any file.
```

Pure measurement, no spend, no writes. Suitable for a cron/scheduled job with a
terminal-only toolset.

### Regeneration — must stop before spending

```
1. Run normalize, re-run qc. Normalization fixes backdrop brightness and
   colour casts without spending.
2. If it still fails, identify the specific outlier files, report the list
   and the estimated cost, then STOP and wait for approval.
3. Only after approval, regenerate ONE item per API call — never a batch —
   and assert the returned count.
4. Re-run normalize + qc, report before/after numbers.

Never delete assets. Quarantine with `mv` to _quarantine/<name>_<date>/.
```

### Vision review — scope it or lose the budget

Naive dispatch is how review budgets die: several review agents were truncated at
their iteration cap by a vision tool that intermittently returned loader stubs
instead of rendered images. What works:

- **Pre-build the comparison grid yourself** with ffmpeg + PIL and hand over one
  labelled image. One grid beats twenty tool calls.
- **Two questions maximum.** Broad review briefs get truncated before answering.
- **Cap retries explicitly and grant permission to fail**: *"retry at most FIVE
  times TOTAL across all images, then report 'vision tool unavailable' and stop.
  An honest partial answer is worth more than an exhausted budget."*
- **Ask for pixel samples** on anything colour-related. Vision reports and pixel
  data disagreed repeatedly, and the pixels were right.
- State *"you cannot regenerate anything — verify and report only"* so the child
  cannot spend.

### Drift analysis — the task that produces the rules

```
Compare renders/<A>/ (baseline) and renders/<B>/ (after changes).
Changes made: <list>.
Extract first/mid/last frames per shot. Sample garment pixels with PIL and
report RGB numbers — do not eyeball colour. Score identity 0-10 per shot on
the same scale as the baseline. Report whether fidelity holds flat or decays.
```

This task class is what generated the measured evidence behind the shot-length
cap and the mode policy. Run it after every pipeline change.

## Harness mechanics worth remembering

- **Sandboxed code-execution tools usually do not inherit shell env.** Run
  anything touching a provider API from the terminal tool, sourcing the env file
  per command, not from the Python sandbox.
- **Keep the credentials file outside the repository** and source it inline:
  `set -a && . ~/.secrets/<proj>.env && set +a && <command>`.
- **Long jobs go to the background.** A full pre-production run exceeds typical
  foreground timeouts. Start detached, poll for completion.
- **Append results to a file, then aggregate in code.** For multi-item sweeps,
  write each result to JSON as you go instead of holding it in context; count and
  dedupe with Python.

## Shipping the harness layer with the repo

If the project is published, the operating layer is part of the deliverable, not
incidental tooling:

- `docs/AGENT_HARNESS.md` — the boundary, the ranked automate/never table, and
  the ready-to-paste task prompts.
- `skills/<name>/SKILL.md` — portable markdown with YAML frontmatter loads in any
  harness (`~/.hermes/skills/`, `~/.claude/skills/`). Ship the QC and
  normalization scripts alongside so an agent can gate assets without the repo
  checked out.

**Deduplicate before shipping a skill.** An accumulated SKILL.md had a 177-line
block duplicated, and the two copies had *diverged* — the stale one carried prompt
advice that later measurement had inverted. Diff repeated headings before
exporting; a skill that contradicts itself is worse than a shorter one.
