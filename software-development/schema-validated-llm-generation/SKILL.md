---
name: schema-validated-llm-generation
description: "LLM generates structured state; app owns canon."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [LLM, Schema, Validation, StateMachine, Generation, Pipeline, Continuity]
    related_skills: [writing-plans, spike, systematic-debugging]
---

# Schema-Validated LLM Generation Loops

## When to Use

Load this when building a system where an LLM generates **structured state
repeatedly** and later turns must stay consistent with earlier ones:

- branching narrative / interactive story engines
- multi-step agent planners that accumulate plan state
- procedural world or content generation with continuity requirements
- incremental data extraction across many documents into one schema
- large-scale extraction pipelines where records carry citations and a
  hallucinated field would silently corrupt the output
- simulation drivers, generated curricula, multi-turn game masters

Also load it when an existing loop of this kind is drifting, contradicting
itself, emitting invented fields, or silently dropping content.

Do **not** load it for one-shot structured extraction — a single call with a
schema needs no state machine.

The whole class fails the same way — the model drifts, contradicts itself, or
invents fields — and it is fixed the same way.

## The load-bearing rule

**The model proposes. The application owns canon.**

```
LLM ──proposes turn──▶ validate(schema + domain rules) ──▶ commit() mutates state
                              │
                              └─ on reject: feed the validator's OWN error
                                 message back, ask for a corrected object
```

Never let generated output mutate state directly. Route every mutation
through one `commit()` function so the state transition is auditable and
reproducible. If the model can write state, continuity is a matter of luck.

## Build order (do not reorder)

1. **Author the spine by hand.** Fixed skeleton (chapters/beats, phases,
   schema fields, task graph) in a JSON/YAML file. The LLM fills in *between*
   the fixed points; it never invents the structure. This split is the single
   biggest anti-slop lever — the model has creative latitude inside a shape
   you control.
2. **Write the state machine and the validator before any LLM call.** Data
   model, gates, `commit()`, append-only event log.
3. **Add the LLM writer last**, with a repair loop.
4. **Prove it in the cheapest medium first.** If the domain's expensive
   artifact is video/audio/images/paid API calls, get the whole loop working
   as *text only* first. That is a real go/no-go gate: if continuity fails in
   text, no amount of downstream pipeline saves it, and you'll have found the
   structural bugs for the price of a few LLM calls instead of a render farm.

## Two-layer validation

Schema alone is not enough. Every proposal gets checked twice:

**Layer 1 — JSON Schema** with `"additionalProperties": false` everywhere.
This is what catches invented fields. Constrain enums, `minLength`,
`maxLength`, numeric `minimum`/`maximum` on any delta the model can emit.

**Layer 2 — domain rules** the schema can't express:

- referenced entities must already exist in state (no unknown characters,
  ids, keys)
- only **pre-declared** keys may be set — reject undeclared flags outright,
  and list the declared set in the error message
- only keys **legal at this step** may be set (a flag belonging to a later
  phase is a rejection, not a warning)
- no self-referential deltas (`from == to`)
- no degenerate output: duplicate ids, two "different" options that are the
  same string, empty required collections

Raise a distinct exception type (e.g. `DeltaRejected`) so the repair loop can
distinguish "malformed output" from "programmer error".

## The repair loop

```python
for attempt in range(max_repairs + 1):
    raw = call_model(messages)
    try:
        turn = extract_json(raw)
        validate(turn)          # schema + domain
        return turn
    except Exception as e:
        if attempt == max_repairs:
            raise DeltaRejected(f"rejected after {attempt+1} tries: {e}")
        messages += [
            {"role": "assistant", "content": raw},
            {"role": "user", "content":
                f"REJECTED by the validator:\n{type(e).__name__}: {e}\n\n"
                "Fix exactly that and return the corrected JSON object only."},
        ]
```

Details that matter:

- **Echo the validator's literal error.** jsonschema's message names the
  failing path and constraint; models repair from it accurately. Paraphrasing
  it into "please try again" costs you the fix.
- **Keep the rejected output in the transcript** as the assistant turn. The
  model repairs its own object rather than starting over and drifting.
- **Log every repair to `repairs.log`.** A repair log is a schema bug report,
  not model noise — see the calibration pitfall below.
- **Tolerant JSON extraction**: strip markdown fences, then brace-match from
  the first `{` rather than trusting `json.loads` on the whole response.

## Prompt contract for the writer

Put the rules in the system prompt as a numbered list, and pass **state as
JSON**, not prose. Always include:

- the current step's spec, verbatim, and its exit condition
- entity state trimmed to what matters (recent memory only, e.g. last 6
  entries — not the full history)
- the explicit list of keys settable **at this step**, and an instruction to
  set none when that list is empty
- the exact JSON shape, as a one-line example object
- the distinction between display keys and internal keys (models will happily
  emit a human-readable name where you need a state key — say which)
- "output one JSON object, no markdown fence, no commentary"

## Continuity mechanics worth stealing

- **Flag/predicate gating.** Steps declare `requires_flags`. AND across
  entries, OR within one entry (`"a|b|c"`). Skipped steps get logged with the
  unmet gate so the run stays explicable.
- **Payoff contracts.** A first-class list mapping each flag to the step where
  it must come due, plus a description. Feed it into the prompt so the model
  is *told* to pay off what's already true. Without this, generated systems
  set state and then forget it — which reads as incoherence.
- **First-person memories over summaries.** Have the model write what an
  entity will *remember* about a moment, in its own frame of reference.
  Concrete quotable memories are what make later payoffs land; third-person
  summaries flatten into mush.
- **Asymmetric relationship state.** Track `trust[a][b]` separately from
  `trust[b][a]`. Same events, different reads — this is where the interesting
  behaviour comes from, and it's free.
- **Append-only event log.** Every accepted turn: what was offered, what was
  chosen, deltas applied, and full state after. Makes any run replayable and
  diffable.

## Extraction loops: add a grounding layer

When the loop is **extraction from a source document** rather than generation
from nothing, schema validity is not enough. A perfectly-shaped record can
still contain an entity the model knows from training but that is not on the
page. That is the worst failure mode in any cited corpus: a plausible
fabrication carrying a real citation, invisible to the reader.

Add a third, cheap, deterministic layer:

```python
def check_grounding(rec):
    """Every extracted entity must appear in the transcription."""
    text = (rec.get("transcription") or "").lower()
    if not text:
        return True, []
    ungrounded = []
    for e in rec.get("entities") or []:
        name = (e.get("name") or "").strip()
        parts = [p for p in name.lower().split() if len(p) > 2]
        if parts and not any(p in text for p in parts):
            ungrounded.append(name)
    return not ungrounded, ungrounded
```

Notes that matter in practice:

- **Treat it as advisory, not a hard reject.** OCR mangles names — a genuinely
  present `BRE2HNEV` will fail a literal match for "Brezhnev". Flag for review;
  don't silently drop real data.
- **Substring-per-token, not whole-string.** Matching the full name fails on
  any inflection or line break; requiring *any* token >2 chars is the right
  sensitivity.
- **Ask the model for a self-reported confidence** (`legibility`, 0-1) on each
  record. The audit query that finds hallucination is `confidence < 0.3 AND
  len(transcription) > 200` — the model said it could not read the page, then
  produced a lot of text.

## Guarantee the shape; validate the truth

Prompting for JSON is a request. **Constrained decoding is a guarantee.**

```python
# vLLM — the model cannot emit a token that breaks the schema
payload = {"model": MODEL, "messages": [...],
           "guided_json": SCHEMA, "temperature": 0}

# OpenAI-compatible
"response_format": {"type": "json_schema",
                    "json_schema": {"name": "rec", "schema": SCHEMA, "strict": True}}
```

This collapses the `unparseable` and `schema_invalid` failure classes to near
zero, which is worth a lot at scale — but **keep the validator running anyway.
Guided decoding guarantees shape, not truth.** Grounding, enum sanity, and
domain rules still need checking.

## Generate the prompt from the schema

Keep one source of truth. Build the prompt's shape section by serialising the
schema object itself:

```python
EXTRACTION_PROMPT = f"""...
Return ONLY a JSON object matching:
{json.dumps(SCHEMA, indent=2)}
..."""
```

Hand-written prompt copies of a schema drift the moment anyone adds a field,
and the drift shows up as mysterious validation failures rather than as an
obvious edit. Generating the prompt makes drift structurally impossible.

## Pitfalls

- **`maxLength` calibrated on the wrong shape.** A cap sized for a terse
  action label ("Open the door") strangles a dialogue-style option ("I'm a
  maritime radio historian; the case was unsolved"). Symptom: repeated
  `is too long` repairs on one field. Raise the cap; don't blame the model.
  Any field with mixed registers needs the *widest* register's budget.
- **Over-narrow gates silently delete content.** Two steps gated on the same
  single flag means one early decision quietly removes a chunk of the
  experience. Symptom: `skipped=2` in run stats. Gate on alternatives
  (`"a|b|c"`) unless you genuinely want that step to be conditional.
  Only visible if you instrument skips — so instrument skips.
- **Cross-step key leakage.** Without the "legal at this step" check, the
  model reaches ahead and sets a late-phase flag early, corrupting gates
  downstream. Cheap to check, expensive to debug.
- **Trusting one run.** Run at least three seeded paths before declaring the
  loop sound. Different decision paths exercise different gates; a single
  happy path proves almost nothing.
- **Metrics on the wrong noun.** "It produced output" is not success. Define
  the target up front (steps completed vs. skipped, repairs, payoffs armed,
  wall time, calls per run) and print it at the end of every run. Then report
  the miss honestly: a mechanism working while the *authored content* fails
  the target is an authoring fix, not a code fix, and saying so saves the
  next session from re-debugging working code.
- **Foreground timeouts on multi-run validation.** A 3-seed validation sweep
  at ~180s per run exceeds the 600s foreground cap. Launch it with
  `background=True, notify=True` and do other work (write the README) instead
  of polling.

## Verified reference implementation

`references/branching-narrative-engine.md` — a worked build: live branching
film engine (showrunner state machine + LLM turn writer + run harness), with
the file layout, JSON schema, measured run stats, and the two structural bugs
the text-only milestone caught. Read it before building a new one; the shape
transfers to any domain in this class.
