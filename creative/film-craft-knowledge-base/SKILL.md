---
name: film-craft-knowledge-base
description: Shot grammar + film craft reference for video pipelines.
platforms: [linux, macos, windows]
version: 1.0.0
author: Hermes
license: MIT
metadata:
  hermes:
    tags: [film, video, shot-grammar, taxonomy, generative-video, pre-production]
    related_skills: [branching-ai-film-engine, generative-media-pipeline-design]
---

# Film Craft Knowledge Base

## When to Use

- Planning shots, coverage, or edit patterns for a film/video project.
- A generative video pipeline needs a **controlled camera vocabulary** instead
  of freeform prose that drifts between beats.
- Questions about production paperwork, crew roles, or on-set language.
- Authoring or validating `shot_specs` on story beats in [`generative-video-consistency-agent-pipeline`](https://github.com/MersivMedia/generative-video-consistency-agent-pipeline).
- Rebuilding or extending the shot taxonomy after editing the source docs.

A local reference set of filmmaking craft documents (shot types, composition,
editing, genres, crew roles, production paperwork) plus a parser that turns the
craft docs into a machine-readable **controlled vocabulary**.

Two distinct uses, don't confuse them:

- **Human-facing craft reference** — answering "what coverage does this scene
  need", "what paperwork before a shoot", "what does a dirty single communicate".
- **Machine-facing shot grammar** — a closed term set the story layer selects
  from, so camera direction is stable across beats instead of re-improvised.

## Locations

| Thing | Path |
| --- | --- |
| Source docs (23 markdown files) | `~/knowledge/Filmmaker Knowledge base/` |
| Parser | `~/generative-video-consistency-agent-pipeline/engine/build_shot_taxonomy.py` |
| Generated taxonomy (committed) | `~/generative-video-consistency-agent-pipeline/engine/data/shot_taxonomy.json` |
| Runtime loader | `~/generative-video-consistency-agent-pipeline/engine/shot_grammar.py` |
| Tests | `~/generative-video-consistency-agent-pipeline/tests/test_shot_grammar.py`, `tests/test_frame_planner_grammar.py` |

Source docs are curated by @byemmasvision. They are third-party reference
material: cite/point to them, quote sparingly, don't republish them wholesale
into public repos. The *taxonomy* (term IDs + short glosses) is derived data and
is fine to commit.

## The taxonomy

206 terms across 10 axes, parsed from 6 of the 23 docs:

```
shot_size (17)      camera_angle (14)     framing (22)
camera_movement(31) lens (19)             focus (10)
shot_type (6)       visual_technique (28) edit_technique (28)   genre (31)
```

Each term: `id`, `label`, `aliases` (`MCU`, `Cowboy`, `ECU`), `group`,
`gloss` (what it is), `purpose` (what it communicates), `sources`.

`SHOT_AXES` in `shot_grammar.py` is the subset describing one camera setup.
`genre` and `edit_technique` are deliberately excluded from frame prompts —
they belong to the story bible and the editor, not to an image model.

## Using the shot grammar

```python
from engine.shot_grammar import ShotGrammar, ShotSpec

g = ShotGrammar.load()
spec = ShotSpec(shot_size="MCU", camera_angle="low_angle",
                camera_movement="push_in", visual_technique=["negative_space"])

g.validate(spec)   # canonicalizes aliases, raises UnknownTerm w/ suggestions
g.to_prompt(spec)  # "medium close-up, low angle, push in, negative space"
g.intent(spec)     # psychology notes — for the WRITER, never the prompt
g.options("shot_size")  # valid IDs, to constrain an LLM
g.menu()           # compact vocabulary listing for a system prompt
```

Key invariant: **`to_prompt` is deterministic and axis-ordered.** Same IDs in,
same string out, regardless of the order fields were set. That's the whole point
— it's what makes camera direction reproducible across a branching story.

**`intent()` output must never reach a render prompt.** "Communicates
vulnerability" is a note to a human; an image model will try to draw it.
There's a test enforcing this.

## Authoring shots in a story

Beats carry `shot_specs`, keyed by phase, using term IDs:

```json
{
  "id": "b1_arrival",
  "shots": 5,
  "shot_specs": {
    "head": [{"shot_size": "extreme_wide_shot", "camera_movement": "crane"}],
    "tail": [{"shot_size": "ECU", "focus": "rack_focus"}]
  }
}
```

**Pitfall:** the beat's existing `shots` key is an integer count from the story
schema. Do not overload it — that's why the vocabulary key is `shot_specs`.

Unauthored shots fall back to `FramePlanner.DEFAULT_COVERAGE`: heads open wide
to re-establish geography after a branch, tails push to MCU on the pending
decision. Invalid terms raise `ValueError` naming the beat and shot index.

`FramePlanner(story, grammar=None)` disables validation (tree shape only).
Omitting the arg loads the shipped vocabulary — a sentinel distinguishes the
two, since `None` had to stay meaningful as the opt-out.

## Rebuilding the taxonomy

```bash
cd ~/generative-video-consistency-agent-pipeline
python engine/build_shot_taxonomy.py \
  --src "~/knowledge/Filmmaker Knowledge base" \
  --out engine/data/shot_taxonomy.json
python -m pytest tests/test_shot_grammar.py tests/test_frame_planner_grammar.py -q
```

The build is reproducible; a test asserts a rebuild equals the committed JSON.
If you change the parser, rebuild AND commit the JSON, or that test fails.

Note: `pytest tests/` fails at collection on `tests/test_live.py` — that file is
a standalone script that parses `sys.argv`, not a pytest module. Use
`--ignore=tests/test_live.py`. Pre-existing, unrelated to this skill.

### Parser pitfalls (all hit during the first build)

- **Numbered bold headings are ambiguous.** `**1\. SHOT SIZES**` is a section,
  `**07\. Close-Up**` is an entry. Disambiguation uses two signals: ALL-CAPS is
  always a section, otherwise a heading is a section only if it's at a
  *shallower* markdown depth than the entry depth measured for that document.
  Depth is measured per-document in a first pass — docs that use one depth
  throughout (the genres doc) would otherwise parse to zero entries.
- Docs label descriptions inconsistently: `Cut Line:`, `Purpose:`,
  `Can communicate:`, `Function:`. All are captured; a lone `Function:` is
  promoted to `gloss` so no term ships with an empty description.
- Section banners vary in wording between docs for the same concept
  (`SHOT SIZES` vs `FRAMING & SHOT SIZES`) — `GROUP_ALIASES` normalizes them.
- Terms appearing in several docs are merged: longer gloss wins, aliases union,
  `sources` accumulates.

`parse_doc` raises if a document yields zero entries. Keep that — it's what
caught the genres doc silently contributing nothing.

## Non-shot documents

Not parsed, read directly when relevant:

- **Pre-production** — indie production roadmap, director's pre-pro blueprint,
  complete pre-shoot checklist, 30 documents needed before a shoot.
- **On set** — 26 daily documents, set-language cheat sheet, director's on-set
  playbook, crew responsibilities, production roles breakdown.
- **Tools** — 33 free filmmaking tools, app toolkit, screenwriting tools,
  screenplay-reading sites, shot list templates, industry reading list.

Find them with `search_files` against the knowledge base path rather than
guessing filenames; several contain typographic apostrophes (`’`) that break
naive shell globs.

## Extending

To add an axis: add a `DOC_SPECS` entry mapping section headings to axis names
(`section_axis`) with a `default_axis` fallback, rebuild, then add the axis to
`SHOT_AXES` in `shot_grammar.py` only if it describes a camera setup.
