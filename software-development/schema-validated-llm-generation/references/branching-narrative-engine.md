# Worked build: live branching AI film engine ([`generative-video-consistency-agent-pipeline`](https://github.com/MersivMedia/generative-video-consistency-agent-pipeline))

A verified reference implementation of the pattern in the parent SKILL.md.
Domain: an audience-voted branching film where video generation runs ahead of
playback. Milestone 1 was **text-only** — no video, no generation cost — and
existed purely to prove continuity holds before spending on renders.

Reference repo: [`MersivMedia/generative-video-consistency-agent-pipeline`](https://github.com/MersivMedia/generative-video-consistency-agent-pipeline).

## File layout

```
stories/the_signal.json    authored spine: chapters, beats, characters,
                           flags_declared, payoff_contracts, style_bible
engine/showrunner.py       state machine — owns canon, validates deltas,
                           gates beats on flags, builds LLM context
engine/writer.py           LLM proposes shot + 2 choices as strict JSON,
                           self-repairs on validator rejection
engine/run_story.py        harness — voting, script rendering, canon log
runs/<story>_<runid>/      script.md, canon.json, final_state.json, repairs.log
```

Deps: `anthropic`, `jsonschema` in a venv (host Python is PEP-668 managed).

## Spine shape (the authored part)

```json
{
  "id": "the_signal",
  "title": "...", "logline": "...", "style_bible": "...",
  "characters": { "<key>": {
      "name","role","visual_lock_refs","voice_id","traits",
      "secret","memory":[], "relationships":{"<key>":0} } },
  "world_facts": ["..."],
  "flags_declared": { "<flag>": "human description" },
  "chapters": [ { "id","title","premise","beats": [ {
      "id","premise","exit_conditions","branch_axis",
      "sets_flags":[], "requires_flags":[] } ] } ],
  "payoff_contracts": [ {"flag","pays_off_in","description"} ]
}
```

`branch_axis` per beat is what keeps the two generated options genuinely
different instead of rephrasings — it names the axis of the decision
("Answer the transmission, or log it and stay silent?").

`style_bible` is appended verbatim to every generated video prompt by prompt
contract, which is the cheapest available consistency lever for the later
render milestone.

## Turn schema (the generated part)

```
{"shot":{ "slug", "video_prompt", "narration",
          "dialogue":[{"character","line"}],
          "characters_on_screen":["key"] },
 "choices":[{ "id":"A"|"B", "label", "kind":"action"|"dialogue",
              "consequence_hint",
              "deltas":{ "set_flags":{"<flag>":bool},
                         "trust":[{"from","to","amount":-4..4}],
                         "memories":[{"character","memory"}],
                         "world_facts":[] } }]}
```

`additionalProperties: false` at every level. `choices` is
`minItems:2, maxItems:2` with `id` enum-constrained to A/B.

## Domain rules enforced beyond the schema

- characters on screen and dialogue speakers must exist in state
- flags must be in `flags_declared` **and** in the current beat's `sets_flags`
- trust deltas: both parties must exist, `from != to`, clamped to ±10 on commit
- memory targets must exist
- the two choice labels must not be identical (case/space-insensitive)
- duplicate choice ids rejected

## Flag gate semantics

`requires_flags` entries are ANDed; `"a|b|c"` within one entry is ORed.
`advance()` walks forward until a gate passes, appending a
`{"type":"beat_skipped","reason":"gate unmet: ..."}` event for each skip.
Skips must be logged and counted or you will not notice content vanishing.

## Measured results

Story: 3 chapters, 9 beats, 3 characters, 7 flags, 6 payoff contracts.
Model: `claude-sonnet-4-5`.

| run | shots | skipped | repairs | payoffs armed | wall |
|---|---|---|---|---|---|
| seed 7 (before fixes) | 7 | 2 | 2 | 2 | 156s |
| seed 42 (before fixes) | 7 | 2 | 0 | 2 | 150s |
| seed 42 (after fixes) | 9 | 0 | 0 | 2 | 177s |
| seed 7 (after fixes) | 9 | 0 | 0 | 2 | 198s |

~9 LLM calls per full run. Trust went asymmetric on its own — one path ended
`wrenn→okonjo +3` while `okonjo→wrenn -6` from the same events.

Sample generated memory (first-person, quotable, exactly what makes payoffs
land later):

> "I read my own handwriting aloud: 'Hail logged, probable hoax, set silenced
> per standing order.' He didn't say I told you so. That was worse."

## The two structural bugs the text-only milestone caught

1. **Choice `maxLength: 90`** was sized for terse action labels. Dialogue-kind
   options overflowed it repeatedly (`ValidationError: ... is too long`),
   burning a repair round-trip per occurrence. Raised to 150 → repairs to
   zero. Lesson: size mixed-register fields for the widest register.

2. **Two beats gated on the same single flag** (`answered_the_hail`). One
   early vote against answering silently deleted a third of chapter 2 —
   `shots=7 skipped=2`. Widened both gates to alternatives
   (`"answered_the_hail|logbook_burned|coordinates_written"`) → 9/9 beats on
   every path. Lesson: single-flag gates on core beats are content deletion
   disguised as branching.

Both are structural, both would have cost real render money to find in the
video milestone, and both were free to find in text.

## Honest residual gap

Payoff contracts armed at 2 per run against a ≥3 target. The *mechanism* is
correct — flags fire, contracts feed into the prompt, the showrunner pays
them off. The branch structure just means most vote paths only set two
flags. That is an **authoring** fix (add a flag most paths set), not a code
fix. Reporting it that way is what stops a future session re-debugging
working code.

## Editing the spine

Do not hand-patch a large JSON spine with string replacement — a mid-array
edit fails syntax validation. Load it, mutate the parsed object, dump it:

```python
s = json.load(open(p))
for ch in s["chapters"]:
    for b in ch["beats"]:
        if b["id"] == "b5_the_ask":
            b["requires_flags"] = ["answered_the_hail|logbook_burned|coordinates_written"]
json.dump(s, open(p, "w"), indent=2)
```
