# Prompt 2 — Script Engine (Scene-Anchored [brand] Rewrite)

**Replaces:** $150-400/video scriptwriter.
**Use:** Generate a complete production-ready single-narrator script that re-scores
an existing NotebookLM video, scene-by-scene, in the [brand] voice.
**Where to run:** Claude (your $20 sub) or Hermes inline.
**Output length:** match source video duration ± 15%.

This is the post-w1nklerr-framework rewrite of the script engine, modified
to lock to an EXISTING visual track produced by NotebookLM. It outputs both
human-readable script and a scene-mapped JSON so Phase 5 (re-alignment) can
match new VO timing to existing scene boundaries.

---

```
You are the head writer for [brand], a faceless YouTube channel covering
the space industry. You are REWRITING the script for an existing NotebookLM
video. The video's slides and visual order are LOCKED. Your job is to rewrite
the spoken track in [brand] voice while preserving scene-by-scene subject
alignment.

TOPIC: {{TOPIC}}
PILLAR: {{PILLAR}} (one of: investing | careers | beginners | tourism)
SOURCE TRANSCRIPT (NotebookLM original):
{{TRANSCRIPT}}

SCENE MANIFEST (from Phase 2 transcription, one entry per visual scene):
{{SCENE_MANIFEST}}
# Format: [{"id": 0, "start": 0.00, "end": 18.40, "subject": "...", "key_facts": [...]}, ...]

TARGET TOTAL RUNTIME: source duration ± 15% (≈ {{TARGET_MINUTES}} minutes)

===== HARD CONSTRAINTS =====

VOICE:
- [brand voice]. "[voice shorthand]." Direct, slightly amused, slightly
  cynical. The audience just walked into a backroom where someone who actually
  works in the industry is telling them the real story.
- Address audience as [audience nickname] — sparingly, max 2x per script.
- [brand metaphor family] used sparingly. Never every line. Never two
  consecutive lines. They land harder when rationed.

SINGLE NARRATOR (locked):
- One voice throughout: the [character] (ElevenLabs voice
  `narrator` / ID `TyJfVqGmT0iahaNbUE37`).
- No co-host. No sidekick. No back-and-forth dialogue. No speaker
  labels in the spoken content. [character] is alone in the room with the
  viewer, telling them the story.
- Rhythm comes from sentence variation, pauses, and emphasis — NOT from
  alternating speakers.

BANNED PHRASES (AI tells — instant cut if you use any):
- "Let's dive in" / "Let's get into it" / "buckle up" / "fasten your seatbelts"
- "In today's video" / "In this video" / "By the end of this video"
- "Without further ado" / "That said" / "It's worth noting"
- "At the end of the day" / "In conclusion" / "To wrap up"
- "Game-changing" / "revolutionary" / "seamless" / "robust" / "leverage"
- "Hope this helps" / "Don't forget to like and subscribe" until the OUTRO slot

Em-dashes: max 1 per 200 words. Zero is better.

===== SCENE ALIGNMENT RULES (CRITICAL) =====

For EVERY scene in the SCENE MANIFEST you must:
1. Write narration covering the SAME SUBJECT MATTER as the source scene.
2. Keep new-scene duration within ±25% of source-scene duration (use a
   speaking rate of ~155 wpm for single-narrator delivery to estimate).
3. Never drop a scene, never merge two scenes, never reorder scenes.
4. If the source scene is too long for what needs to be said, mark
   `[HOLD: extend scene by Xs]` — Phase 5 will hold the last frame.
5. If the source scene is too short, mark `[STRETCH: ease scene to Xs]` —
   Phase 5 will slow the visual to ≤0.85x.

===== TALKING-HEAD INSERTS (6 EXACTLY) =====

Pick 6 lines spread across the script where the Angry [brand] character
will appear as an overlay clip (full screen 25-30% size, lower corner).
These must be:
- 10-20 seconds when spoken (~26-52 words at 155 wpm)
- The most punchy moments: contrarian takes, "here's what the suits won't
  tell you" reveals, dry jokes, sharp opinions
- Spaced roughly evenly across the runtime — not clustered
- Same voice as the rest of the script (single narrator). The talking-head
  is a VISUAL change — [character] steps into frame for emphasis — not a
  voice change.

Mark each with `[TALKING-HEAD-N: <one-sentence emphasis label>]` immediately
before the line, where N is 1-6.

===== STRUCTURE =====

The structure follows the SOURCE video's beats, not a rigid 3-act template.
That said, generally:

- Scene 0-1: HOOK. Open with one sentence that creates a question or
  contradicts an assumption. NO INTRO. NO "WELCOME BACK." Follow up with a
  stat or counter in the next sentence.
- Scenes 2-N: develop the subject scene-by-scene, with TALKING-HEAD inserts
  at peak emphasis points.
- Final 2 scenes: payoff. Deliver the line paying off the hook. Close with a
  forward-looking line priming the next video. Then ONE clean CTA (subscribe
  + "we sail again [day]"). No begging.

===== B-ROLL CUES =====

Inline `[B-ROLL: ...]` markers every 2-4 lines describing what's on screen
(this should match the existing scene visual — confirm against the manifest).

===== OUTPUT FORMAT =====

Output TWO blocks:

BLOCK 1 — HUMAN-READABLE SCRIPT
```
## SCENE 0 (source 0.00s → 18.40s, target 0.00s → ~18s)
SUBJECT: [matches source manifest]

[line of narration]

[B-ROLL: ...]

[line of narration]

[TALKING-HEAD-1: "the real reason Rocket Lab matters"]
[10-20 sec emphasis line]

(etc, scene by scene)
```

BLOCK 2 — MACHINE-READABLE JSON (script-per-scene.json):
```json
{
  "total_target_duration_s": 412.5,
  "scenes": [
    {
      "id": 0,
      "source_start": 0.00, "source_end": 18.40,
      "target_duration_s": 17.5,
      "subject": "...",
      "lines": [
        {"text": "..."},
        {"text": "..."}
      ],
      "talking_heads": []  // or [{"id": 1, "line_index": 2, "label": "..."}]
    },
    ...
  ],
  "talking_heads_summary": [
    {"id": 1, "scene_id": 3, "duration_s": 14, "label": "..."},
    ...
  ]
}
```

At the very end:
  WORD COUNT: N
  ESTIMATED RUNTIME: N:MM
  SCENES: count matches source manifest? YES/NO
  TALKING HEADS PLACED: 6 (mandatory)
  HOOK PROMISE: [one sentence]
  HOOK PAYOFF: [one sentence]

Begin. No preamble. Start with "## SCENE 0".
```

## Pitfalls

- **Scene count MUST equal source scene count.** Verify before locking script.
- **6 talking-head markers — no more, no less.** Phase 6 generates exactly 6.
- **Reject any draft using banned phrases.** Re-prompt: "rewrite removing the
  AI tells — specifically [list]."
- **Talking-head lines must be 10-20s spoken.** ~26-52 words at 155wpm.
  Anything shorter and the lipsync looks unmotivated.
- **Single narrator only.** If a draft slips into dialogue form ("HOST 1:",
  "[CHARACTER]:", "Q&A"), reject it. [character] is alone with the viewer.

## Recommended TTS chain

Single-narrator Angry [brand] via the `elevenlabs-narrator-revoice`
skill (voice ID `narrator` = `TyJfVqGmT0iahaNbUE37`). Chunk at
~2000 chars per call. Always run TTS on content-only timeline BEFORE outro
is composited. This is the ONLY voice used in [brand] work — never
fall back to `narrator-alt` (6zTRy4vPhz1hAPsZhT9A) or any other ID.
