---
name: narrated-video-cut-sync
description: "Use when video cuts must land between voiceover words."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  platforms: [linux, macos]
  hermes:
    tags: [video, voiceover, sync, edit, qc, word-timestamps, scribe, cuts]
    related_skills: [viral-youtube-video, brand-youtube-pipeline, motion-graphics, elevenlabs-narrator-revoice]
---

# Narrated video: cuts that land between words

## When to Use
- Any edit where each visual slot belongs to a sentence of narration: faceless documentaries, explainers,
  slideshow videos.
- After the voiceover exists and before rendering the visual slots.
- When the user asks whether a clip is "in the right place", especially in a language they don't speak.

Pairs with `viral-youtube-video` (script → VO → visuals); this skill covers the step between the voiceover
and the render.

## Why
Script-estimate cue times drift from the real VO by up to ~3 s. A cut that comes early chops the end of
the previous sentence: on episode 1 of the French channel, the end card cut off
"…un bonjour dans cinquante-cinq langues". A drift tolerance alone isn't enough: 5 cuts within 0.6 s of
their target still landed INSIDE a word, one of them mid-sentence ("D'abord, ce | qui").

## Steps
1. **Word timings from the real VO.** Use ElevenLabs Scribe (`POST /v1/speech-to-text`, `scribe_v1`, word
   timestamps), or any STT with word-level timing. Save `build/words.json` as `[{w, s, e}]`.
2. **Locate each cue.** For every `[VISUAL]` cue, take the first 3–4 words that follow it in the script,
   find them in order in `words.json`, and set the target cut just before that sentence's first word.
3. **Strict rule, the real gate:** a cut is valid only if `not any(w.s < cut < w.e for w in words)` AND it
   sits after the previous sentence's last word ends. Print `prev word @end | next word @start` for every
   cue and place the cut mid-gap. A late cue moves back into the gap before its sentence.
4. **One source of truth.** Write all corrected times to `build/cue_overrides.json` (`{"<cue index>": t}`).
   The assembler, the photo/slot renderer and the graphics cue table must all read this file. Shift
   camera keyframes and overlay end times that sat on an old boundary. A small script applies the overrides
   to the graphics CUE table and to the `until=` values in the slot spec.
5. **Audit BEFORE rendering anything, then render once.** Episode 1 needed 3 render rounds (9 → 5 → 2 bad
   cuts) because each audit only ran after a rebuild. Moving a cut means re-rendering both neighbouring
   slots: batch them all into one render session (one rented pod, not three).
6. **Gate the upload on the audit.** Rebuild, re-run the strict check on the final cut list, and only then
   replace the delivered file (same Drive file name keeps the shared link). A failing build never reaches
   the link.
7. **Hand-off check.** Verify the assembled frame total matches the expected count, with no silence gaps.

## Talking to a user who can't follow the narration language
When they ask "is this clip in the right place?", answer per clip with:
- what the narration says at that moment, in English;
- the word timings around the cut;
- whether the picture matches.
"Looks fine" can't be checked by someone who doesn't speak the language.

## Pitfalls
- Chapter timestamps: YouTube rounds down, so a chapter at 94.6 s shows 1:34 even if the previous sentence
  ends at 94.38. Check the first word of each section in `words.json`.
- STT punctuation tokens (`?`) appear as words with near-zero duration; don't let them count as a gap.
- Cutting exactly on a word's start time counts as inside the word for most viewers. Aim for the middle of
  the pause.

## Worked example
French space channel episode 1: `~/.hermes/data/yt-arbitrage/fr-space/<episode>/build/`
(`words.json`, `sync_audit.py`, `cue_overrides.json`, `apply_overrides.py`) and `edit/pod_finish.sh`
(batch re-render on a CPU pod, upload gated on the audit).

## Related production notes
`references/faceless-production-notes.md` covers the rest of the production pass:
- the CPU-pod standing rule and its real costs;
- script length at the narrator's real pace;
- the fact pass;
- the FR→EN review-doc builder;
- code-built thumbnails with a vision critique;
- checking parallel research subagents.
