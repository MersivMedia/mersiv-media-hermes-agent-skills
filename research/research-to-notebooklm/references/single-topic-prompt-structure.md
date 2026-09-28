# Single-topic prompt.txt structure ([brand])

Field-tested shape for the one-off "research topic X" flow. Feeds directly into NotebookLM as the brief alongside sources.txt.

Target: ~700-1000 words. Two trailing blank lines for mobile copy-paste.

## Skeleton

```
Topic: <Display Name> — <one-line subtitle if useful>

Pillar: <Investing | Careers | Beginners | Tourism> (mention crossover appeal if relevant)

Voice: [brand] — [voice description]. No AI tells, no hype-deck adjectives. Treat the audience as smart adults who can handle nuance — this is a story where <the tension specific to this topic>.

The hook: <2-3 sentence framing of why this matters NOW. State the conflict between two forces — pitch vs reality, money vs physics, hype vs adoption, etc.>

Cover these <N> threads:

THREAD 1 — <Who/What is the landscape>
- <Specific name + specific detail + date or number>
- <Repeat for 5-10 entities>

THREAD 2 — <Why it could work / the bull case>
- <Specific advantage with a number>
- <Specific advantage with a name>
- ...

THREAD 3 — <Why the physics/economics/regulation fights back>
- <Specific obstacle with source attribution if a public figure said it>
- ...

THREAD 4 — <The under-priced obstacles / what no one is talking about>
- <Marketing-vs-reality gap>
- <Regulatory / spectrum / debris / NIMBY>
- <Honest economic question framed for the audience>

TONE NOTES
- <2-4 bullets reminding the script-writer what to keep and what to cut>
- <Always include: "Do not pick a winner. Lay out who is betting what and let the audience read the room.">
- <Always include: a "memorable specifics" callout — name 3-4 details that should make it into the final video>

<Close on the framing question. One sentence. Should make the viewer want to comment.>


```

## What makes this work

1. **Named threads, not generic sections.** "THREAD 1 — Who is actually doing this" forces specificity. "Background" doesn't.
2. **Every bullet carries a number, date, or proper noun.** "Solar panels are more efficient in orbit" is filler. "Solar panels in orbit can be ~8x more efficient than on Earth" lands.
3. **Pre-write the framing tension in the hook.** NotebookLM will mirror whatever frame you set. If the hook is "everything is great about X," the video will be sycophantic. If the hook is "the pitch and the physics disagree," the video will be useful.
4. **Tone notes at the bottom, not the top.** NotebookLM gives more weight to instructions near the source URLs. Top of the doc is for facts; bottom is for voice.
5. **Closing framing question is mandatory.** Drives engagement on the published video and forces the writer to land a thesis.

## What to leave out

- Per-source summaries. NotebookLM ingests the URLs itself.
- "I think..." — no first-person.
- Word counts, slide counts, runtime targets. NotebookLM picks those.
- Markdown formatting beyond plain headers and bullets. Some renderers mangle it.

## Validated example

Session of 2026-05-29: "Space Data Centers and Orbital AI" delivered with 4 threads (companies, feasibility, physics obstacles, under-priced obstacles), 35 sources, ~750-word prompt.txt. Output landed in `28 - Space Data Centers and Orbital AI — Investing/`.
