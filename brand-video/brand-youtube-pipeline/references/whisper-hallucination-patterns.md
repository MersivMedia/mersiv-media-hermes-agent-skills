# Whisper Hallucination Patterns in NotebookLM Source Audio

Reference for Phase 2.5 cleanup. Real examples captured from Ep3 (AST SpaceMobile) and Ep4 (Reading Earnings) transcripts, May 2026.

## Pattern 1 — Foreign-language hallucination

Whisper drops CJK or other non-Latin characters mid-English narration when it hits ambiguous audio (compressed transitions, chart-change foley, brief gaps). Always nonsense in context.

**Ep3 example (scene 21, 202.93 → 212.93s):**

> "in the sky. That capacity will be pooled for 1600 units. With a growing 이상etата for 捷 än ℏ Plane Biology gratitude increase required after a lift in speed. It좀need atk for basic U.S. coverage..."

**Heuristic:** if `scene["text"]` matches `[\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]` (Hiragana/Katakana/CJK/Hangul ranges), flag for rewrite.

## Pattern 2 — Brand-name confusion

Whisper substitutes a real brand name for a phonetic neighbor. Often produces capitalized nonsense words.

**Ep3 example (scene 10):**

> "Reflex Ong. The company's growth rate is now at a $1.1 billion mark. The Pepsi lab Frau models are now still in crisis..."

(Source was talking about Rocket Lab Q1 revenue.)

**Ep3 example (scene 17):**

> "Bosing the largest communication arrays ever deployed..."

(Source said "Boasting the largest communication arrays...")

**Heuristic:** unfamiliar capitalized proper nouns that don't appear in the research brief or sources.txt are usually Whisper artifacts. Cross-check against the brief before keeping any brand/company name.

## Pattern 3 — Loop repetition

Near-silence in the source confuses Whisper into emitting the previous sentence's tail 2-3 times.

**Ep3 example (scenes 17, 20):**

> "...AST SpaceMobile is the largest communication array in the world. It's the largest two- Hopefully the largest communication array in the world. That means 505 devices mainframe standing..."

**Ep4 example (scene 19):**

> "The World Economic Forum projects a $1.8 trillion space economy by 2035. Which companies will actually survive the void to claim it? Keep watching the data to find out. World Economic Forum projects a $1.8 trillion space economy by 2035. Which companies will actually survive the void to claim it? Keep watching the data to find out."

**Heuristic:** detect when the same 8-12 word sequence appears twice within one scene — that's a loop, not narration.

## Pattern 4 — Empty / sub-3-word scenes

Whisper emits a segment for a sub-second audio span and assigns 0-3 words. Usually the boundary between two real beats.

**Ep4 example (scene 08):**

> "" (zero words, 4.0s duration)

**Ep3 example (scene 19):**

> "" (zero words, 3.83s duration)

**Heuristic:** scenes with `word_count < 3` AND `duration > 2s` are either title cards (likely) or empty-audio gaps (occasional). Title cards belong as `[NO VO — visual title card]` in the script; empty-audio gaps get merged into the adjacent scene's VO.

## Cleanup workflow

1. After Whisper completes, generate `scene-manifest-readable.md` and scan it visually
2. Mark every flagged scene with the pattern number (1-4) in a comment line
3. For each flagged scene, reconstruct the intended meaning from:
   - the surrounding scenes' context
   - `research/prompt.txt` (the brief)
   - `research/videoprompt.txt` (visual cues)
   - if still unclear, watch the source video at that timestamp range
4. Rewrite into the [brand] script in Phase 3 — never copy the garbage forward

## Why this matters

If you copy Whisper hallucinations into the rewritten script, ElevenLabs will dutifully voice "Pepsi lab Frau models" or "Reflex Ong" in the final video. The Angry [brand] voice will pronounce them with conviction. You will then have to regenerate every affected talking-head and scene VO at ElevenLabs + Replicate cost. Cleanup at Phase 2.5 is essentially free.
