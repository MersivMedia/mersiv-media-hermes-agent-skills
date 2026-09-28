---
name: brand-youtube-pipeline
description: End-to-end [brand] video production pipeline — takes a NotebookLM-generated video, re-skins slides to dark [brand] theme, transcribes audio with scene timestamps, rewrites the script in [brand] voice using the w1nklerr 4-prompt framework, generates new ElevenLabs voiceover with the Angry [brand] voice, re-aligns the video to the new VO, overlays 6 talking-head clips of the locked [brand] character via prunaai/p-video-avatar, watermarks with the horizontal lockup, and bookends with the outro. Use for any "make a video", "process this NotebookLM video", or channel-pipeline task.
when_to_use: |
  - User provides a NotebookLM video and wants it published as a [brand] asset
  - User asks for a script, title, tags, or full video for the [brand] channel
  - User asks for talking-head [character] clips to overlay on existing video
  - User mentions "the pipeline", "process this video", "make a video"
  - Anything touching the [brand] YouTube channel production loop
---

# [brand] — Video Production Pipeline

The full process: NotebookLM in → [brand] video out. 8 sequential phases, each with a designated tool/skill. The w1nklerr 4-prompt framework (niche analyst, script engine, metadata, scaling) lives in `templates/` and is invoked from inside this pipeline.

Source attribution: framework adapted from @w1nklerr on X (article "How I Made an AI Channel That Generated $12,000 in One Month", May 2026, article ID 2054239999957012480).

## Brand constraints (always apply)

- **Voice:** [brand voice]. Address audience as [audience nickname] — max 2x per script. [brand metaphor family] used sparingly, never in consecutive lines.
- **Single narrator (locked):** ElevenLabs voice `narrator` / ID `TyJfVqGmT0iahaNbUE37` is the ONLY voice used in every aspect of the pipeline — slide narration, talking-head overlays, intros, outros, all of it. The earlier two-host format and the secondary `narrator-alt` (6zTRy4vPhz1hAPsZhT9A) voice are DROPPED. If you see references to a second host, a two-host split, "two-host delivery", or the `narrator-alt` voice anywhere in this skill or its templates, treat them as stale and rewrite to single-narrator using `TyJfVqGmT0iahaNbUE37`. Never call ElevenLabs TTS with any other voice ID for [brand] work.
- **No AI tells:** strip "in conclusion", "let's dive in", "in today's video", "buckle up", "fasten your seatbelts", em-dash stacks, bullet-pointy narration.
- **Pillars (rotate):** ① investing ② careers ③ beginners ④ tourism. Target RPM band $15-50.
- **Locked character — pose library (12 poses, content-driven selection):** Once the [character] is picked, we keep a library of 12 distinct body poses. Each talking-head insert uses a pose CHOSEN to match the body language of the line being spoken (not just round-robin). See Phase 6 for the full mapping table. The library lives at `~/.hermes/data/brand-youtube-pipeline/character-pose-library/` (mirror of Drive `[brand]/brand/character/`, folder id `<DRIVE_FOLDER_ID>`). Filename pattern: `character-pose-NN-<action>.png`.

## Persistent workdir

All state lives at `~/.hermes/data/brand-youtube-pipeline/`:
- `character-options/` — the 6 generated [character] variants
- `locked-character.png` — the one we picked (symlink or copy)
- `episodes/{slug}/` — per-episode workdir (NotebookLM source, recolored frames, scripts, audio, talking-heads, final)

Never use `/tmp` for episode state — sessions get killed and lose progress.

## The 8-phase pipeline

**Pipeline mode A — fresh episode (NotebookLM video → [character] version, RECOMMENDED):**
This is the canonical flow. The NotebookLM video is the visual source only — we generate fresh audio via ElevenLabs TTS so we always know exact sentence boundaries and never need to transcribe-back to find talking-head cut points.

```
NotebookLM video (visual source)
  ↓
[Phase 1] Slide re-skin to [character] dark theme (silent video out)
  ↓
[Phase 2] Whisper transcribes ORIGINAL NotebookLM audio + detects scene cuts
          → manifest of scenes with subject matter + timestamps
  ↓
[Phase 3] Claude rewrites script in [brand] voice, scene-aligned, with 6 [TALKING-HEAD] markers
  ↓
[Phase 4] ElevenLabs TTS generates VO as NUMBERED CHUNKS:
          - One chunk per scene (for full-VO assembly)
          - 6 chunks already split as the talking-head lines (we know boundaries — no re-transcription)
          - Files named with target source-video timestamps (where each chunk drops in)
  ↓
[Phase 5] Deliverable to user: dark silent video + numbered VO chunks. User assembles in CapCut.
  ↓
[Phase 6] Generate 6 talking-head clips from the chunked talking-head audio (no transcription needed)
  ↓
[Phase 6.5] Build 1280×720 YouTube thumbnail (transparent pose + chunky title)
  ↓
[Phase 7] Optional: composite if user wants
  ↓
[Phase 8] Metadata
  ↓
[Phase 8b] youtube-metadata.txt — title/description/tags/hashtags/SEO for the upload form (.txt, mobile-friendly, trailing whitespace)
```

### Partial-pipeline mode — pre-edited / pre-recolored sources

When the user hands you a video that's ALREADY been recolored (or hand-edited, or that they explicitly say "skip recolor on"), run the partial pipeline: **Phases 2 → 3 → 4 → 6 → 6.5 → 8b**. Treat the supplied video as the canonical final visual, do not re-encode the slides, do not run `edit_video.py`. The Drive folder layout, naming conventions, and deliverables are identical to the full pipeline — only Phase 1 is skipped. Validated across Ep1-5 (May 2026) when the user supplied pre-edited NotebookLM dark-theme exports for the backlog.

**Pipeline mode B — already-rendered episode (used for episode 01 backfill):**
When the user gives us a video that already has VO baked in (no separate audio track to swap), we work backwards:

```
Rendered character-narrator video (audio baked in)
  ↓
Whisper transcribes the full audio with timestamps
  ↓
Pick 6 talking-head moments by reading the transcript
  ↓
Probe-verify each timestamp by re-transcribing a 6s window
  (Whisper's full-file timestamps drift on long audio — short-window probes are accurate)
  ↓
Extract source-video audio clips with exact start/duration
  ↓
Generate talking-heads from those clips
```

Mode B is the FALLBACK. **User has explicitly asked for mode A going forward** — give them the unedited NotebookLM video and the agent does the TTS-first path so chunks have known content + known boundaries, eliminating the transcribe-verify round-trip. Only fall back to mode B when the input video has VO already baked in and there's no separate audio track available.

**Pipeline mode A-skip — already-recolored visual, skip Phase 1:**
Sometimes the user has already done the slide re-skin themselves (CapCut pass, manual recolor, or a previous pipeline run) and wants to skip Phase 1. They will say "skip recolor", "the visual is final", or "use this video as-is." In that case:

- Treat the provided video as both visual source AND audio source for transcription. Whisper still runs on its audio (Phase 2) because the spoken content drives the script rewrite.
- Use the provided video's actual duration as Phase 3's target runtime budget (no ±15% wiggle — user already locked the pacing visually).
- Detect scene cuts on the PROVIDED video (the one with already-recolored slides), not on a separately-fetched NotebookLM original — they may have different cut counts or boundaries.
- Skip the `notebooklm-brand-edit` invocation entirely. The first phase that runs is Phase 2.
- Drive uploads still go to the episode folder; do NOT replace the existing recolored video — it's the user's canonical visual.

This mode reuses every other phase unchanged (2 → 3 → 4 → 6 → 6.5 → 8b). Verified on Ep2 — Rocket Lab vs SpaceX, May 2026.

**Pipeline mode A-resume — partial state on disk, finish specific phases:**
Sometimes the user comes back to an episode and asks for a specific subset of phases (e.g. "complete Phases 3 → 4 → 6 → 6.5 → 8b, Phases 1-2 are done") — typically because a prior session crashed mid-pipeline, or because the slow Phase 1 recolor was kicked off in parallel and the agent should pick up everything else. Always **inspect the episode workdir BEFORE re-running anything**:

```bash
ls -la episodes/{slug}/
# look for: source-notebooklm.mp4, transcript.json, scene-cuts.txt,
# scene-manifest.json, script.md, chunks.json, vo-chunks/, talking-heads/,
# talking-heads.json, thumbnail.png, thumbnail-variants/, youtube-metadata.txt,
# recolor-work/, recolor.log, recolored-video.mp4
```

Decision matrix per artifact:

| Artifact on disk | What it means | Action |
|------------------|---------------|--------|
| `recolored-video.mp4` exists, >500s | Phase 1 done | Skip Phase 1; ready to upload |
| `recolor.log` tail shows ffmpeg concat error + clip-NN.mp4 in `recolor-work/` | Phase 1 crashed at final concat (see concat-path bug pitfall) | Run recovery snippet, do NOT re-run `edit_video.py` |
| `recolor-work/` missing or no clip-NN.mp4 | Phase 1 never ran | Run `edit_video.py` from scratch |
| `transcript.json` + `scene-manifest.json` present | Phase 2 done | Skip |
| `script.md` + `chunks.json` present | Phase 3 done | Skip unless user explicitly asks for rewrite |
| `vo-chunks/*.mp3` (scenes) + `vo-chunks/*.wav` (6 talking-heads) all present | Phase 4 done | Skip — `emit_tts_chunks.py` is idempotent anyway, but re-running burns ElevenLabs spend if you're not careful |
| `talking-heads.json` shows mixed `succeeded`/`failed` statuses | Phase 6 partial | Re-run `generate_talking_heads.py` — idempotent, only failed clips re-submit |
| `talking-heads/` has <6 mp4s + matching json shows some `failed` | Same as above | Same |
| `thumbnail.png` + `thumbnail-variants/` populated | Phase 6.5 done | Skip unless user wants new variants |
| `youtube-metadata.txt` populated + has trailing-newline pad | Phase 8b done | Skip — verify content matches the locked script though |
| Background processes claim to be running parallel jobs | Maybe stale, maybe live | `process(action="list")` first; trust filesystem state over stale notifications |

**The contract for resume mode:** confirm what's actually on disk, fix anything broken (don't re-run successful phases), upload everything to the target Drive folder, then send ONE completion message. No play-by-play. Verified on Ep07 SpaceX Valuation Tender (May 2026): prior session left recolor crashed at concat + 5/6 talking-heads done + th5 failed + everything else complete. Total recovery: 2 ffmpeg invocations to finish recolor + 1 idempotent talking-heads re-run for th5 + 1 Drive upload pass. Saved an estimated $3+ in re-spend vs. naive restart.

### Phase 0 — Lock the [character] character (one-time)

Run `scripts/generate_character_options_v2.py` to produce 6 photorealistic variants WITH the real [brand] emblem ([brand emblem]) embroidered on the hat. The script passes `brand/brand-logo.png` as `input_images` to gpt-image-2 so the emblem matches the actual brand asset, not a guess.

Prereq: the brand logo must exist at `~/.hermes/data/brand-youtube-pipeline/brand/brand-logo.png`. If missing, pull from Drive (file id `<DRIVE_FILE_ID>`):
```bash
curl -sL "https://drive.google.com/uc?export=download&id=<DRIVE_FILE_ID>" \
  -o ~/.hermes/data/brand-youtube-pipeline/brand/brand-logo.png
```

User picks one variant from `character-options-v2/`. Symlink or copy it as `locked-character.png`. This is the face for every talking-head clip.

**Drive locations:**
- Brand folder: `<DRIVE_FOLDER_ID>`
- Character folder (where final locked character + variants live): `<DRIVE_FOLDER_ID>` ([brand]/brand/character/)
- Brand logo: file id `<DRIVE_FILE_ID>` (1024×1024 PNG)

**Drive naming convention for character poses (REQUIRED):**
Files in the character/ folder use the pattern `character-pose-NN-<short-action-name>.png` where NN is a 2-digit sequence number and `<short-action-name>` is a hyphenated description of what the [character] is doing (e.g. `arms-down`, `hand-on-chest`, `arms-crossed`, `one-hand-gesturing`, `both-hands-explaining`, `thumbs-up`, `hand-on-chin`, `pointing-at-camera`, `palms-up-questioning`, `hand-on-hip`, `tipping-hat`, `fist-at-chest`). This lets you (and CapCut) eyeball which pose is which without opening files. NEVER upload character images with generic names like `01_full_torso_xyz.png` — always rename to the descriptive convention before pushing to Drive.

**Every pose ALSO needs a transparent-background companion** for YouTube thumbnails and any future compositing work. Filename: `character-pose-NN-<action>-transparent.png` (sibling to the original, same folder, both stay). After adding any new pose to the library, run:

```bash
/tmp/hermes/venv/bin/python3 \
  ~/.hermes/skills/brand/brand-youtube-pipeline/scripts/strip_pose_backgrounds.py
```

It's idempotent — skips poses that already have a transparent companion. Uses Replicate's `851-labs/background-remover` (~$0.01/pose). Both the original (solid background, needed for `prunaai/p-video-avatar` lipsync) and the transparent version (for thumbnails) live in the same folder on disk AND on Drive.

**Pitfalls:**
- Parallel gpt-image-2 calls occasionally time out at the provider layer (read timeout, not our bug). Retry single failures individually with `retry_character_variant.py` rather than re-running the whole batch.
- **Detach long-running python pollers from the bash shell.** Hermes' background terminal mode kills child processes when the parent bash dies (which happens on user-interrupt). Wrap python pollers with `nohup setsid python3 SCRIPT > LOG 2>&1 &` + `disown` so SIGHUP doesn't cascade. Verified bug: a `python3 SCRIPT | tee LOG` chain that gets interrupted in the parent shell silently auto-cancels every in-flight Replicate prediction (status flips to `canceled` at the provider). Detached `nohup setsid` survives.
- High-quality calls take 60-180s each. Always background with `notify_on_complete=true`.
- v1 script (`generate_character_options.py`) without the input_images reference is kept only as fallback. The emblem it generated was a generic emblem, not our brand asset — don't use it for production characters.
- The reference logo is FLAT VECTOR ([brand emblem] on solid black). The prompt explicitly converts that to RAISED EMBROIDERY on hat fabric. If you change the prompt, keep that conversion instruction or the result looks like a sticker pasted on the hat.

### Phase 1 — Re-skin NotebookLM slides to [character] dark theme

**Delegate to the `notebooklm-brand-edit` skill.** It already handles:
- Scene cut detection (threshold 0.25)
- Frame extraction at scene midpoints
- Light-vs-dark classification (mean brightness >140)
- Text-heavy → PIL recolor; illustration → gpt-image-2 recolor with the locked prompt
- NotebookLM badge strip (bottom-right rectangle)
- End-card removal (brightness >180 in last 10s)

Output of Phase 1: `episodes/{slug}/recolored-video.mp4` — same audio, dark-themed slides, NotebookLM branding gone. **Wordmark and outro are NOT added yet — those are Phase 7.**

To run it inline (positional `input` and `output`, NOT `--input/--output`):
```bash
/tmp/hermes/venv/bin/python3 ~/.hermes/skills/creative/notebooklm-brand-edit/scripts/edit_video.py \
  episodes/{slug}/source-notebooklm.mp4 \
  episodes/{slug}/recolored-video.mp4 \
  --workdir episodes/{slug}/recolor-work \
  --skip-wordmark --no-outro      # we composite those at Phase 7
```

If `edit_video.py` doesn't support those flags yet, run the full pipeline and strip the wordmark/outro afterward — better fix: patch the script to accept skip flags. See `notebooklm-brand-edit` skill for the full pitfalls list.

### Phase 2 — Transcribe audio with scene-aligned timestamps

For each scene in the recolored video, transcribe the audio inside that scene's start→end window. Output a JSON manifest:

```json
{
  "video_duration": 412.5,
  "scenes": [
    {
      "id": 0, "start": 0.00, "end": 18.40,
      "words": [
        {"t": 0.20, "text": "Today"},
        {"t": 0.55, "text": "we're"},
        ...
      ],
      "transcript": "Today we're looking at..."
    },
    ...
  ]
}
```

**Whisper is run via Replicate (`victor-upmeet/whisperx`), NOT a local whisper install.** There is no `whisper` python module in any env on this box — the `mlops/models/whisper` skill is reference docs only. Use the same WhisperX-on-Replicate pattern that `elevenlabs-narrator-revoice/scripts/revoice.py` uses: upload the audio to tmpfiles.org → POST to `/v1/predictions` with `victor-upmeet/whisperx` latest version → poll until `succeeded`. Save the raw `output` blob (segments + word timestamps) at `episodes/{slug}/transcript.json`. WhisperX returns `{segments: [{start, end, text, words: [...]}], detected_language, ...}` — same structure your downstream code already expects. Pitfall: do NOT call `import whisper` or `import faster_whisper` from a phase-2 script — both will fail with ModuleNotFoundError. **Full standalone invocation recipe: `references/whisperx-replicate-invocation.md`.**

Why this matters: Phase 3 rewrites the script per scene, and Phase 5 must re-time the new VO to fit each scene's visual content (slightly stretch or shorten, but stay scene-aligned).

**Scene-cut density varies wildly across sources.** Observed range (May 2026, Ep1-5):
- ~14 cuts / 6-min source (Ep5 SPAC Graveyard) — sparse, well-paced
- ~16 cuts / 7-min source (Ep2 Rocket Lab vs SpaceX) — moderate
- ~20 cuts / 6-min source (Ep4 Reading Earnings) — moderate, includes 5 title cards
- ~37 cuts / 6-min source (Ep3 AST SpaceMobile) — DENSE, many chart-change cuts mid-narration

**Phase 3 rule:** when raw cut count > ~25 for a 5-7 min source, collapse over-segmented scenes into narrative beats for the VO. Keep the original `scene-cuts.txt` for CapCut visual alignment, but write the VO chunks against logical 8-15 beats, not against every detected cut. Mid-narration chart cuts should land inside ONE VO chunk, not split a sentence across two.

**Title-card detection heuristic:** scenes shorter than ~5s with very few words (typically just a section name like "Section 1: The Great Filter") are almost always visual title cards meant to be held silent — mark them `[NO VO — visual title card]` in the script and omit from `chunks.json`. The visual hold contributes runtime so target word count can drop accordingly (155 wpm × VO-only seconds, not total runtime).

### Phase 2.5 — Whisper hallucination cleanup (REQUIRED before Phase 3)

NotebookLM source audio occasionally contains brief gaps, chart-change foley, or compressed transitions that confuse Whisper into producing garbage transcripts for that span. Observed failure modes (May 2026):

- **Foreign-language hallucinations:** Whisper drops Korean/Chinese characters mid-English narration (Ep5 scene 06: `이상etата for 捷 än ℏ`)
- **Brand-name confusion:** real brand names get swapped for similar-sounding nonsense (`Reflex Ong`, `Pepsi lab Frau`, `Bosing` for "Boasting")
- **Loop repetition:** Whisper repeats a phrase 2-3 times back-to-back when the audio source has near-silence ("largest communication array in the world. It's the largest two- Hopefully the largest communication array in the world")
- **Empty segments:** brief silences emit a segment with 0 words (Ep4 scene 08)

**Detection:** when reviewing `scene-manifest-readable.md` before drafting Phase 3, flag any scene whose text contains non-ASCII characters, sub-3-word fragments, or obvious sentence-loop repetition. These are NOT in the source narration — they are Whisper artifacts.

**Resolution:** rewrite those scenes from the surrounding context + the research brief + the visible source video frames. Do not parrot the Whisper garbage into the [brand] script. If the meaning of a hallucinated span is genuinely unclear, watch the source video for that timestamp range and reconstruct the beat from the slide visuals.

This step is now standard pre-Phase-3 hygiene. Ep3 (37 cuts, 3 garbled scenes) and Ep4 (20 cuts, 3 garbled scenes) both required it.

### Phase 3 — Rewrite script in [brand] voice (w1nklerr framework)

Use the 4 Claude prompts in `templates/`:

1. `templates/01_niche_analyst.md` — optional, only for borderline topics. If the user already greenlit the topic, skip.
2. `templates/02_script_engine.md` — **required.** Inputs: the original transcript (Phase 2), the scene manifest, target runtime (default = source duration ± 15%). Output: single-narrator script in [brand] voice with **scene-anchored beats** — each script section maps to a source scene by index. This is critical: the new script must align scene-by-scene with the existing video.
3. `templates/03_metadata.md` — run AFTER script lock. Title pivots on the actual hook line.
4. `templates/04_scaling_analyst.md` — monthly, not per-video.

Save at `episodes/{slug}/script.md` and `episodes/{slug}/script-per-scene.json`.

**Scene-alignment rule baked into Prompt 02:** each scene in the new script can be ±25% of its source-scene duration but cannot drop or merge scenes. Subject matter per scene must match the source visual subject. Tag the talking-head insert points (6 of them) inside the script with `[TALKING-HEAD: emphasis-line]` markers.

**Collapse over-segmented scenes into narrative beats.** Whisper + ffmpeg scene-change detection often returns 30-40+ cuts for a 6-7 min source because every chart change, every bullet appearance, every visual transition counts as a "scene." Ep3 (AST SpaceMobile, May 2026) produced 37 raw cuts on a 6:17 source — most were chart-change cuts mid-sentence, not narrative breaks. Ep2 (Rocket Lab vs SpaceX) had 15 cuts but 4 were sub-5s section-title cards meant as visual holds. The workflow is:
1. Keep `scene-cuts.txt` (raw ffmpeg output) as the canonical CapCut alignment reference — every cut still matters visually.
2. Collapse the raw scenes into **12-16 narrative VO beats** for the script rewrite. A narrative beat is a self-contained thought (~30-45s of speech typically). One narrative beat may span 2-4 raw scenes when those raw scenes are just chart changes inside the same point.
3. Title-card scenes (sub-5s, single visual flash with no narration) should be marked `[NO VO — visual title card]` in the script with the raw scene_id preserved, so the user knows to let the visual breathe in CapCut without inserting audio.
4. In `chunks.json`, only emit TTS for narrated beats — skip the title-card scene_ids. Filenames still use the raw scene_id from `scene-cuts.txt` so they sort correctly against the source.
5. Whisper artifacts (garbled OCR/foreign characters when source has bad audio passages, e.g. Ep3 scenes 17-21, Ep5 scene 08) get rewritten in the script — never preserve garbage verbatim, infer intent from surrounding context.

**Word-count budgeting (verified across Ep2/3/4/5/12, May 2026).** The single-narrator [brand] voice reads at ~155 wpm. To leave enough breath room and avoid running long against the source video duration, target **scene-VO total word count = ~2.3 × VO-only-seconds** (where VO-only-seconds = source duration minus the sum of all title-card scene durations). Example math: a 376s source with ~9s of title-card holds = 367 VO-only seconds → target ~840 words, hard cap ~950. Going over 950 words on a 376s source forces TTS into a rushed cadence and burns the breath room the audio mix needs at scene transitions. Verified targets:
- Ep5 (357.8s, 0 title cards): 1026 words at 397s computed → fit, used.
- Ep2 (419.3s, 22s title cards): 1000 words at 387s computed → fit, used.
- Ep3 (376.9s, 0 title cards): 979 words at 379s computed → fit, used.
- Ep4 (346.4s, 25s title cards): 779 words at 301s computed → comfortable fit (the cushion is what makes Phase 4 TTS sound natural rather than rushed).
- Ep12 (315.9s, 18s title cards): 708 words at 274s computed → comfortable fit.

If first-draft VO word count blows past the target, the rewrite is too literal to the source — cut filler ("really need to", "let us take a step back", "what I am about to tell you"), collapse double-emphasis sentences, and merge tangential sub-points into the dominant beat. Do this BEFORE Phase 4, not after — re-running TTS on a tightened script is cheap, re-mixing audio after the fact is not.

**Talking-head pose plan goes into Phase 3, NOT Phase 6.** The pose for each talking-head is baked into the `chunks.json` filename during Phase 4 TTS render (e.g. `th3-sda-contract_..._pose-04-one-hand-gesturing.wav`), which means by Phase 6 the pose is already locked. The Phase 3 script.md needs a final "Talking-head pose plan" table that maps each of the 6 slots to a pose AND explicitly documents the rotation check.

**MANDATORY Phase 3 step BEFORE writing the pose plan table:**

```
skill_view(name='brand-youtube-pipeline', file_path='references/pose-rotation-ledger.md')
```

Read the slot-by-slot history and the underused-poses list. Then for each of the 6 slots:

1. Pick the intent-best pose from the Phase 6 pose table.
2. Check the ledger's slot-by-slot history. If the intent-best pose is currently "NUCLEAR HOT" or "HOT" for that slot, force-swap to one of the currently underused poses (01, 02, 06, 07, 09, 11) that still fits the line at a passable intent level.
3. Write the swap reasoning in the script.md pose plan table's intent column, e.g. "th2 SETUP intent → 02-hand-on-chest (sincere setup; rotation: 05-explaining is NUCLEAR HOT in slot 2 across 5 of last 6 eps)."

**Real failure: Ep3 + Ep4 + Ep12 shipped the IDENTICAL pose sequence `08 → 05 → 12 → 03 → 04 → 10` three consecutive times because the ledger-load step was scheduled at Phase 6 instead of Phase 3 — by Phase 6 the poses were already baked into WAV filenames and the agent silently shipped the duplicate.** Moving the ledger-load to Phase 3 closes the loop. If you find yourself drafting a script.md pose plan table without first running `skill_view` against `references/pose-rotation-ledger.md`, STOP and load the ledger — this is non-negotiable, the rotation drift is the channel's single biggest visual quality problem.

**Phase-skip mode (no recolor).** Sometimes the user provides a video where the slides are already brand-themed (or they want to handle the visual side separately). In that case, run Phases 2-8b only and treat the linked video as the final visual asset. Ep2 + Ep3 (May 2026) ran this way. The pipeline is identical except: don't run `notebooklm-brand-edit/edit_video.py` and don't expect a `recolored-video.mp4` deliverable. Everything else (transcript, scene manifest, script, chunks, TTS, talking-heads, thumbnail, metadata) is unchanged. The Phase 2 transcript still runs against the source audio extracted from whatever video the user provides.

### Phase 4 — Generate VO as numbered chunks via ElevenLabs TTS

Use the `elevenlabs-narrator-revoice` skill. Single narrator, locked: Angry [brand] / `narrator` voice → `TyJfVqGmT0iahaNbUE37`. This is the only voice used in the pipeline — never call ElevenLabs with any other voice ID for [brand] work.

**CRITICAL — Output as NUMBERED CHUNKS, not a monolithic file:**

The user assembles the final video in CapCut. To make assembly mechanical, generate ALL audio as discrete labeled clips with target-timestamp filenames:

1. **Scene VO chunks** — one per scene (Phase 3 produced scene-aligned dialogue). Naming:
   `scene-{NN}_[{target_start}-{target_end}].wav`
   where `target_start/end` is where the scene should land in the realigned video.

2. **Talking-head VO chunks** — the 6 lines tagged `[TALKING-HEAD-N]` in Phase 3, each generated as its OWN chunk so we have the exact audio file already isolated for Phase 6. Naming:
   `th{N}-{section-tag}_[{target_start}-{target_end}]_pose-{NN}-{action}.wav`

Because we generated these chunks ourselves, we already know:
- The exact text in each clip (no transcription needed)
- The complete-sentence boundaries (we wrote them)
- The intended target timestamp (per Phase 3's scene plan)
- Which pose to use (Phase 3 chose it, or Phase 6 picks via the content-driven selector)

Save all chunks at `episodes/{slug}/vo-chunks/`. Upload to Drive `{episode-folder}/vo-chunks/` for the user.

**The canonical Phase 4 runner is `scripts/emit_tts_chunks.py`.** It takes a `chunks.json` manifest and renders one audio file per chunk, named per the convention above. Schema:

```json
[
  {"kind": "scene",  "scene_id": 0, "start": 0.0, "end": 44.1,
   "text": "Seven hundred and sixty million dollars..."},
  {"kind": "talking_head", "th_id": 1, "section": "cold-open",
   "start": 0.0, "end": 12.0, "pose": "08-pointing-at-camera",
   "text": "Seven hundred and sixty million dollars..."}
]
```

Run:

```bash
/tmp/hermes/venv/bin/python3 \
  ~/.hermes/skills/brand/brand-youtube-pipeline/scripts/emit_tts_chunks.py \
  --chunks episodes/{slug}/chunks.json \
  --out-dir episodes/{slug}/vo-chunks
```

Voice is locked to `TyJfVqGmT0iahaNbUE37` in the script — do not override with `--voice-id`. Idempotent: skips chunks whose output file already exists (handy for partial re-runs after script edits). The output filenames bake in the target timestamps so CapCut placement is mechanical.

For a 14-scene + 6-talking-head episode, expect ~80s wall time at ~4s/chunk.

**Pitfall: always run TTS on content-only timeline BEFORE intro/outro composite.** TTS over silent music sections produces dead air at the bumpers.

**Chunk size note:** ElevenLabs sweet spot is ~2000 chars per call. Most scenes will fit in one call. For scenes that exceed it, split at sentence boundaries within the scene and concat the resulting WAVs before saving the scene chunk.

### Phase 5 — Deliverable handoff to user (CapCut assembly)

Default mode: I do NOT auto-composite. The user assembles the final video in CapCut. The deliverable to the user is:

1. `{slug}-dark-slides-silent.mp4` — Phase 1 output: re-skinned NotebookLM video with NO audio.
2. `voiceover-chunks/scene-{NN}_[{start}-{end}].wav` — N scene-VO chunks with target timestamps in filenames.
3. `voiceover-chunks/th{N}-{section}_[{start}-{end}]_pose-{NN}-{action}.wav` — 6 talking-head audio chunks.
4. `talking-heads/th{N}-{section}_[{start}-{end}]_pose-{NN}-{action}.mp4` — 6 talking-head videos (Phase 6 output).
5. `script.md` and `talking-heads.json` for reference.

All uploaded to the episode's Drive folder under structured subfolders so CapCut import-by-folder works cleanly.

Phase 5 in the previous spec ("re-align video to new VO") is NOT needed in mode A — the silent video is already at NotebookLM's pacing, and each VO chunk's filename tells CapCut exactly when to place it. The user adjusts in CapCut if a scene wants slight stretch/hold.

### Phase 6 — Generate 6 talking-head [character] clips via prunaai/p-video-avatar

From the script, pick the 6 most punchy 10-20 second moments. These should be:
- Lines where Angry [brand] POV makes the line hit harder (contrarian takes, "here's what the suits won't tell you", reveals, jokes)
- Spaced across the video — not clustered
- Marked in the script with `[TALKING-HEAD: ...]` from Phase 3

**Content-driven pose selection (REQUIRED):**

For EACH of the 6 talking-head clips, read the transcript text of that clip and pick the pose whose body language matches what's being said. The library lives in `~/.hermes/data/brand-youtube-pipeline/character-pose-library/` (mirror of the Drive `character/` folder). Use this lookup:

| Filename | Body language | Best for talking-head lines like... |
|----------|---------------|-------------------------------------|
| `character-pose-01-arms-down.png` | Neutral, open, hands at sides | Calm setup beats, "here's the situation", baseline narration, intro hooks |
| `character-pose-02-hand-on-chest.png` | Hand on chest | Personal/sincere beats, "this matters because...", values statements |
| `character-pose-03-arms-crossed.png` | Arms folded across chest | Skeptical, authoritative, contrarian takes, "actually...", calling BS |
| `character-pose-04-one-hand-gesturing.png` | One hand raised mid-gesture | Making a specific point, "but here's what they won't tell you", building the argument |
| `character-pose-05-both-hands-explaining.png` | Both hands framing the air | Walking through a concept, structured explanations, "let me show you" |
| `character-pose-06-thumbs-up.png` | Right-hand thumbs-up | Approval / endorsement, "this is the good news", celebrating a win, payoff lines |
| `character-pose-07-hand-on-chin.png` | Hand on chin, thinking pose | Reflective beats, "let's think about this", weighing trade-offs, posing a question |
| `character-pose-08-pointing-at-camera.png` | Index finger pointed at camera | Direct address / callout, "if you're holding [X], listen up", confronting the viewer |
| `character-pose-09-palms-up-questioning.png` | Both palms up, skeptical | Rhetorical "come on now", incredulous reactions, "what did you expect?" |
| `character-pose-10-hand-on-hip.png` | One hand on hip, cocky stance | Confident takes, swagger lines, "told you so", I-saw-this-coming beats |
| `character-pose-11-tipping-hat.png` | Hand at hat brim, tipping it | Sign-offs, smooth transitions, charming punctuation, "and that, friends..." |
| `character-pose-12-fist-at-chest.png` | Closed fist at chest, emphatic | Hard truths, emphatic delivery, "this is what matters", climax lines |

**Selection algorithm:**
1. **The pose plan was finalized in Phase 3 (script.md), not here.** If you're starting Phase 6 and the script.md does not yet have a 6-row pose plan table that explicitly cross-references `references/pose-rotation-ledger.md`, STOP and complete that step before generating talking-heads. The ledger-load belongs at Phase 3 because the pose is locked into the `chunks.json` filename at Phase 4 TTS render time — by Phase 6 you can't rotate poses without re-running TTS.
2. Read `references/pose-rotation-ledger.md` once more to confirm the locked pose plan still matches the rotation rule. If a previously-shipped episode just landed and changed the slot history, the plan may now be obsolete — but in practice the script is locked before Phase 6 starts, so this is a sanity check, not a re-decision.
3. Use the intent classification table below as the lookup the Phase 3 pose plan referenced.

If two clips genuinely map to the same intent, pick the SECOND-best pose for one of them and split the difference — rotation matters more than perfect intent-match. If a clip's intent is unclear or generic, default to pose 01 (arms-down) as the neutral baseline.

For each clip, extract the matching audio slice from `voiceover-final.wav`, then call `prunaai/p-video-avatar`:

```python
{
  "image": <DATA_URI of the SELECTED pose for this clip>,
  "audio": <DATA_URI of audio clip>,
  "resolution": "720p",
  "video_prompt": "A [character] speaks directly to the camera with natural lip-sync and expressive head movement. Subtle nods on key points, occasional eyebrow emphasis. CRITICAL — camera: the camera is completely locked off on a tripod. NO zoom (in or out), NO push-in, NO pull-back, NO dolly, NO pan, NO tilt, NO shake, NO handheld motion. Framing stays IDENTICAL from the first frame to the last — only the character moves within the frame. Lighting and background match the source portrait exactly. CRITICAL — hat logo: the [brand emblem] on his hat is a flat embroidered patch sewn into the wool fabric. It conforms to the curvature of the cap, rotates with the head in correct perspective, shares the same lighting and shadows as the surrounding fabric, and never appears as a separate floating layer, 3D protrusion, or frontal-locked decal. The patch stays stitched flush against the hat at all times.",
  "disable_prompt_upsampling": False
}
```

Schema (verified live):
- Required: `image` (jpg/jpeg/png/webp data URI or URL)
- `audio` data URI → drives lipsync (used instead of voice_script when present)
- `resolution: "720p"` per spec
- `video_prompt` controls visual behavior; `voice_prompt`/`voice_script` ignored when audio is provided

Cost: model name "p-video-avatar" — "fastest and cheapest avatar/lipsync video model" per its description. Verify cost against current Replicate pricing before running 6 in parallel.

Save each as `episodes/{slug}/talking-heads/th{N}-{section}_[{start}-{end}]_pose-{NN}-{action}.mp4` — filenames mirror the WAV chunk convention so each talking-head video pairs unambiguously with its source audio chunk. Manifest `talking-heads.json` keeps `{clip_basename: {status, path, prediction_id}}` written by the runner.

**Canonical runner — use this, do not roll your own inline:**

```bash
/tmp/hermes/venv/bin/python3 \
  ~/.hermes/skills/brand/brand-youtube-pipeline/scripts/generate_talking_heads.py \
  --chunks episodes/{slug}/chunks.json \
  --vo-dir episodes/{slug}/vo-chunks \
  --pose-dir ~/.hermes/data/brand-brand/character \
  --out-dir episodes/{slug}/talking-heads \
  --manifest episodes/{slug}/talking-heads.json
```

The script filters `chunks.json` to `kind == "talking_head"` entries, uploads >1.5MB assets via Replicate Files API (data URIs below that), submits all 6 predictions in parallel via threads with a 2-second stagger, polls each to terminal, downloads MP4s with unique filenames, and writes the manifest. Embroidery + camera-lock + `video_prompt` are baked into the script — single source of truth.

**Pitfalls:**
- Submit all 6 in parallel (the runner already does this via threads). Each takes ~30-120s wall, so total ~3-5 min.
- ALWAYS use a unique output filename per parallel job (the runner does — clip basename includes section + timestamp + pose). Concurrent writes to the same path corrupt the moov atom. (Known issue from prior background ffmpeg work — see memory.)
- `disable_safety_filter` defaults true; leave it. Don't toggle defaults you don't need.
- **`.wav` chunks from Phase 4 MUST have RIFF headers — `pcm_24000` is headerless raw PCM.** ElevenLabs' `pcm_24000` output format returns raw PCM bytes with no WAV/RIFF wrapper. If you write those bytes directly to a `.wav` file, `prunaai/p-video-avatar` rejects them with `"Audio file could not be decoded. Please upload a valid audio file."` and `ffprobe` reads them as garbage Targa data. The fix is baked into `emit_tts_chunks.py` (May 2026): after each `pcm_24000` write, the script reopens the file with `wave.open(..., "wb")`, writes a proper 1-channel/16-bit/24kHz RIFF header, and replaces the raw bytes. If you ever see "Audio file could not be decoded" in the Replicate manifest, check `xxd $file | head -1` — if it doesn't start with `RIFF`, the wrap step didn't run. Discovered on Ep5 (May 2026) when all 6 talking-heads failed simultaneously; fix locked into the emit script so it self-heals on every run.
- **Hat-logo "floating decal" artifact (locked fix in `video_prompt`):** Without explicit embroidery language, the model treats the [brand emblem] as a frontal-locked 2D billboard that doesn't rotate with the head — reads visually like the patch is lifting off the hat. The fix is the `CRITICAL — hat logo:` clause in the prompt above. Discovered on Ep1 th5 (May 2026), regenerated with the clause → patch reads flat and stitched. Never strip this clause when iterating on the prompt; if you need to change the visual direction, add a separate clause for it rather than rewriting the embroidery lock.
- **Quick zoom-in/zoom-out artifact (locked fix in `video_prompt`, NOT FULLY SUPPRESSED):** The model defaults to subtle push-ins and pull-backs to "match" emphasis beats — this reads as jittery and pulls focus from the character. The current fix is the `CRITICAL — camera:` clause in the prompt above (explicit NO list: zoom, push-in, pull-back, dolly, pan, tilt, shake, handheld). Discovered on Ep1 regen pass (May 2026, second pass after embroidery fix). Locked-off framing is mandatory because talking-heads are composited as overlays in Phase 7 — any camera motion fights the underlying slide motion. **Ep5 status (May 2026): prompt reduces but does not eliminate camera drift — user confirmed clips are "good enough to use" but motion is still visible on all 6 talking-heads.** Investigate before Ep6: try (a) prepending the NO list to the very front of the prompt instead of mid-prompt, (b) testing if `disable_prompt_upsampling: True` preserves the NO list (the upsampler may be paraphrasing the negatives away), (c) building an A/B vision grid per `references/generative-output-validation.md` to measure delta. Never strip the existing clause — only ADD constraints.
- **Validate prompt changes with an A/B vision grid before mass-regenerating.** When you change the `video_prompt` (or any generative prompt in this pipeline), run a single test clip, build an OLD-vs-NEW labeled montage, and pass it to `browser_vision` with a COMPARATIVE question. Solo-frame vision compares to a physical-sim ideal and will say "still wrong" even when you've meaningfully improved things. See `references/generative-output-validation.md` for the full recipe (ffmpeg crop → 8-frame sample → labeled PIL grid → browser_vision A/B prompt).

### Phase 6.5 — YouTube thumbnail (per episode)

Run `scripts/build_thumbnail.py` to render a 1280×720 YouTube thumbnail from a transparent-bg pose + the dark brand background + a chunky title.

**Composition (no AI cost — pure PIL):**
- Background: `brand/bg-youtube-channel.png` (cover-cropped + darkened 35%) or solid `#121212` fallback
- Text block: left ~58% of frame. Title in Roboto Slab Black (`fonts/RobotoSlab-Black.ttf`), [brand accent color] by default with black stroke + drop shadow. Auto-fits font size to keep within bounds. Subline (optional) in [brand text color], smaller, also stroked.
- Pose: right ~40% of frame, chest-up crop (top 65% of alpha bbox), bottom-aligned. Uses `character-pose-NN-<action>-transparent.png` from the character library.
- No vertical divider line between text and [character] (looks dated — earlier draft had one and the eye flagged it immediately).

**Pose selection** matches the same intent-based system as talking-heads (Phase 6). For thumbnails specifically, lean toward higher-energy poses (08-pointing, 12-fist-at-chest, 04-gesturing, 03-arms-crossed) — calm poses like 01-arms-down rarely earn clicks.

**Hook color treatment:**
- `gold` (default) — most content
- `teal` — upside/growth/win stories
- `red` — warnings, contrarian takes, "this is a trap" angles

**Variants:** the script renders 3 alternates with different poses + hook colors so you can pick the strongest one. The chosen one is the canonical `thumbnail.png`; the rest live in `thumbnail-variants/`.

**Run:**

```bash
/tmp/hermes/venv/bin/python3 \
  ~/.hermes/skills/brand/brand-youtube-pipeline/scripts/build_thumbnail.py \
  --episode-slug 01-pure-play-space-stocks \
  --title "PURE-PLAY|SPACE STOCKS" \
  --sub "5 tickers Wall Street is hiding" \
  --pose 08 \
  --hook-color gold \
  --variants 3 \
  --drive-folder-id <DRIVE_FOLDER_ID>
```

Title uses `|` as a line-break delimiter. Aim for 1-3 lines, 2-5 words each, ≤24 chars per line so mobile compression doesn't shred it.

**Output:**
- Local: `episodes/{slug}/thumbnail.png` (the chosen variant) + `episodes/{slug}/thumbnail-variants/` (all 3)
- Drive: all 4 files uploaded to the episode folder when `--drive-folder-id` is passed

**Pitfalls:**
- **Font files must exist** at `~/.hermes/data/brand-youtube-pipeline/fonts/RobotoSlab-Black.ttf` and `Anton-Regular.ttf`. They're downloaded from Google Fonts' CDN via the gstatic.com URLs (not the github redirect — that 302's to an HTML page and saves garbage). If missing, refetch:
  ```bash
  cd ~/.hermes/data/brand-youtube-pipeline/fonts
  curl -sL -o RobotoSlab-Black.ttf "https://fonts.gstatic.com/s/robotoslab/v36/BngbUXZYTXPIvIBgJJSb6s3BzlRRfKOFbvjoJYOWaA.ttf"
  curl -sL -o Anton-Regular.ttf "https://fonts.gstatic.com/s/anton/v27/1Ptgg87LROyAm0K0.ttf"
  ```
  Verify with `file *.ttf` — should say "TrueType Font data", NOT "HTML document".
- **Transparent-pose companions are a prereq.** Run `strip_pose_backgrounds.py` once during Phase 0; it's idempotent so re-running is safe.
- **Validate the variant visually before locking the canonical.** Run `browser_vision` over the rendered PNG to confirm the cutout is clean (no halo), text is readable, layout balanced.
- **YouTube wants ≤2MB for the thumbnail file** — our PNGs are usually 1.2-1.5MB at 1280×720 which is fine. If a thumbnail file gets above 2MB (rare), convert to JPEG at quality=90.

### Phase 7 — Composite talking-heads + wordmark + outro

For each talking-head in the manifest, overlay onto the realigned video at the marked timestamp. Sizing: 25-30% of frame width, lower-left or right corner depending on visual balance per slide. Fade in/out 0.2s each side.

Then add [brand] horizontal lockup wordmark bottom-right (use `brand-lockup-horizontal.png` — solid-bg version, NEVER the transparent variant per `notebooklm-brand-edit` pitfall list). Height = 10% of video height, 2% margin.

Finally concat the brand outro at the end (NOT at the start, per the updated spec — intro is gone). Match codec/timebase: re-encode outro to source fps/dimensions first, then concat-filter (not demuxer) to avoid NAL-unit errors.

```bash
# Talking-head overlay (per clip, chained)
ffmpeg -i realigned-video.mp4 -i th-0.mp4 -i th-1.mp4 ... \
  -filter_complex "
    [1:v]scale=iw*0.28:-1,fade=in:st=0:d=0.2,fade=out:st=END-0.2:d=0.2[th0];
    [0:v][th0]overlay=W-w-W*0.03:H-h-H*0.20:enable='between(t,T0,T1)'[v1];
    [v1][th1]overlay=...:enable='between(t,T2,T3)'[v2];
    ...
  " -c:a copy with-heads.mp4

# Wordmark
ffmpeg -i with-heads.mp4 -i brand-lockup-horizontal.png \
  -filter_complex "[1:v]scale=-1:ih*0.10[wm];[0:v][wm]overlay=W-w-W*0.02:H-h-H*0.02" \
  -c:a copy with-wordmark.mp4

# Concat outro (no intro)
ffmpeg -i with-wordmark.mp4 -i brand-outro-matched.mp4 \
  -filter_complex "[0:v:0]setsar=1[v0];[1:v:0]setsar=1[v1]; \
                   [v0][0:a:0][v1][1:a:0]concat=n=2:v=1:a=1[v][a]" \
  -map "[v]" -map "[a]" final.mp4
```

### Phase 8 — Metadata + upload

Run `templates/03_metadata.md` → 5 title variants, description with timestamps, 25 tags, thumbnail brief. Save at `episodes/{slug}/metadata.md`.

Upload to YouTube via the channel's normal process. Capture the URL.

### Phase 8b — YouTube upload package (`youtube-metadata.txt`)

For every episode, ALSO produce the canonical YouTube upload package — title (+ alternates), description (+ 150-char snippet hook + chapter timestamps + CTAs), tags, hashtags, and SEO breakdown. This is the one document the user pastes into the YouTube upload form.

Run `templates/05_youtube_metadata.md` (the Claude prompt) with these inputs:
- `EPISODE_TITLE` — current working title
- `PILLAR` — investing | careers | beginners | tourism
- `RUNTIME_MIN` — total runtime in minutes
- `HOOK` — first ~15s of the locked script
- `KEY_POINTS` — 3-6 bullets summarizing the script
- `ENTITIES` — comma-separated tickers/companies/people referenced
- `SOURCE_FACTS` — the specific dollar figures, dates, contracts the video carries

Output: a fully-filled `youtube-metadata.txt` file. Save at `episodes/{slug}/youtube-metadata.txt` and upload to the topic's Drive folder (sibling to `research/`, `slideshow/`, `talking-head-samples/`).

**File format requirements (mobile-friendly):**
- Extension MUST be `.txt`, not `.md`. The user reads this on their phone from Drive — `.txt` previews instantly without rendering, `.md` opens in a Markdown viewer that often clips content or requires extra taps.
- Append ~50 blank lines to the END of the file before saving. Mobile copy-all gestures need padding past the content or the OS clips the last paragraph or grabs Drive UI chrome. Shell:
  ```bash
  printf '\n%.0s' {1..50} >> youtube-metadata.txt
  ```
- Internal structure can still use Markdown notation (`#`, `**`, `###`) — it degrades cleanly to readable plain text. Don't strip the formatting.

The doc's `## Thumbnail brief` section drives `build_thumbnail.py` (Phase 6.5) — it specifies the hook word, pose, and color treatment. **Run Phase 8b BEFORE Phase 6.5** so the thumbnail uses the same hook word and pose intent that the metadata copy promises.

**Pitfalls:**
- **Investing pillar disclaimer is mandatory.** The template enforces this — don't strip it. We are not licensed to give financial advice.
- **First 150 chars matter most.** This shows in search snippets above "show more." Treat it as a sharper, separate hook than the full description body.
- **Hashtags = exactly 3.** First 3 hashtags in the description render above the video title on the watch page. More than 3 is wasted; 1-2 looks sparse. 3 is the sweet spot.
- **Tags: 15-25 max.** More signals stuffing to YouTube's algo. Front-load the title-exact match, broaden to category.
- **`.txt` not `.md`.** Mobile preview. Repeat: `.txt`. With trailing whitespace.

## Workflow rules (user preferences — DO NOT skip)

### Cost discipline: opus-4-8 + reasoning_effort=low across both orchestrator AND subagent

**Updated May 2026:** the cost-control answer is no longer \"delegate to Sonnet from Opus.\" It's `claude-opus-4-8` with `reasoning_effort: low` set in both `agent.*` (main session) and `delegation.*` (subagents). Opus 4.8 ships adaptive thinking — at `low` effort it responds directly on simple steps and only reasons on hard ones, which is dramatically cheaper than opus-4-7-at-medium for routine pipeline work. Sonnet override is no longer needed for cost.

Verify the active config is correct before kicking off an episode:
```bash
grep -nE \"^model:|reasoning_effort|^delegation\" ~/.hermes/config.yaml
# Expect:
#   model: claude-opus-4-8
#   agent.reasoning_effort: low
#   delegation.model: claude-opus-4-8
#   delegation.reasoning_effort: low
```

If those four values match, `delegate_task(goal=..., context=..., toolsets=[...])` with NO `model` argument is the correct call — subagents inherit opus-4-8 low automatically. The old advice to pass `model={\"model\": \"claude-sonnet-4-5\"}` explicitly is OBSOLETE; do not add that override unless the user has explicitly asked for Sonnet in this session.

The split between main session and subagent is unchanged: main session owns the slow background jobs (recolor, Whisper, talking-heads polls), subagent owns the LLM-heavy work (script rewrite, metadata copy, thumbnail composition, Drive uploads).

**Important pitfall — `delegate_task` has a 10-minute timeout per subagent run.** A full episode (Phase 1 recolor 5+ min + Phase 4 TTS ~17 chunks + 6 talking-heads at 60-120s each + Drive uploads) blows past 10 min if the subagent is responsible for blocking-polling all of them inline. Verified May 2026 on Ep07 SpaceX Valuation Tender: subagent timed out at 600s with 35 API calls completed, mid-pipeline.

**Working split (the "A pattern"):**
- **Main session (Opus) launches** Phase 1 recolor + Phase 2 WhisperX + scene-detect as `terminal(background=true, notify_on_complete=true)` jobs. These are slow but agent-free — no model tokens consumed while they run.
- Main session also kicks off Phase 6 talking-heads in parallel once the script is locked (each Replicate prediction is its own backgrounded poller).
- **Sonnet subagent does:** Phase 3 script rewrite (the actual reasoning), Phase 4 TTS submission, Phase 6.5 thumbnail composition (PIL/i2i), Phase 8b metadata draft, Drive upload assembly. All of these are short individually — Sonnet just needs to think and submit, not babysit Replicate polls.
- Subagent prompt MUST tell it to NOT block-wait on recolor or talking-heads — those return via main-session notify. Subagent's job ends with "deliverables drafted, awaiting heavy-job completion to upload."

Long-term: see `references/episode-runner-design.md` for the cron-runner pattern that removes both agents from the loop entirely (paste Drive link → cron ships episode).



These are durable preferences for how this user wants the pipeline operated, captured from session corrections. Treat them as hard rules.

### NO play-by-play during multi-phase runs

When running an episode through the pipeline, the user does NOT want narration of every step. The contract is:

1. One short message at the START: "Started Ep{N}. Will surface only blockers or the final handoff."
2. SILENT execution through Phases 2-4-6-6.5-8b. No progress reports between phases. No status updates. No "now running TTS" intermediate messages.
3. If a phase BLOCKS on a question (e.g. multiple candidate files in the Drive folder and you can't tell which is the source), THEN message and wait. One blocker question at a time, narrowly scoped.
4. One COMPLETION message at the end with the deliverables (Drive link, canonical thumbnail MEDIA: preview, th1 cold-open MEDIA: preview, cost). That's it.

The user explicitly told me to stop the play-by-play (May 2026, Ep4 kickoff): "You don't need to tell me every step of the way because that wastes tokens, just let me know when you've started, if you have any questions or issues, and when it's completed." This is a HARD rule. Token efficiency on these runs matters because the agent burns hundreds of background-process-completion tool calls per episode, and surfacing each one as a user-facing message bloats the chat.

Specifically banned during a pipeline run:
- "Phase 4 starting" / "Phase 4 complete" announcements
- Mid-flight "still processing" status messages
- "Whisper done, 74 segments" type counters
- Cost estimates partway through ("so far ~$0.45")

Specifically allowed (and required):
- Real blockers: "I see 3 candidate source videos in the Drive folder, which is the recolored one?"
- Real questions: "The pose I'd pick is in the under-used ledger but the intent match is weaker — go with it anyway?"
- Final handoff with Drive link + previews + cost + any notes

If you find yourself drafting a message that isn't a START, a BLOCKER, or a COMPLETION, delete it before sending.

### Plan-before-execute on any new multi-step build

When the user proposes a new pipeline phase, new script, or any multi-step build that touches paid APIs (Replicate, gpt-image-2, ElevenLabs), the FIRST response is a written plan — layout, file paths, costs, deliverables — and a `clarify()` call asking the user to greenlight or tweak. Do NOT pre-emptively render samples, burn credits, or commit to a layout direction.

The user explicitly chose "Plan first" over "execute everything" when given the option (May 2026, thumbnail rollout). Cheap or zero-cost operations (PIL composition, font downloads, skill scaffolding) can run before approval; anything that calls a paid model needs the plan checkpoint first.

### Variants, not one-shot finals

When generating creative deliverables (thumbnails, character poses, social cards), default to rendering N variants (3 is the sweet spot) and let the user pick. Save them under `<artifact>-variants/` and copy the chosen one as the canonical filename. The intent table in `build_thumbnail.py::INTENT_POSES` is the model — variants should differ meaningfully (different pose family + different hook color), not just be the same composition with cosmetic tweaks.

### Validate visual outputs with `browser_vision` BEFORE locking the canonical

The A/B vision-grid pattern in `references/generative-output-validation.md` was originally for prompt iteration on `prunaai/p-video-avatar`. It applies equally to PIL composition outputs: render → load in browser → ask vision a SPECIFIC question about readability/cutout/balance → fix any flagged issue → re-render.

Example from session: vision flagged a vertical gold divider line on the first thumbnail draft as "dated/PowerPoint-y" — caught it before the user did. Removing it took one patch. If you ship the canonical first and ask vision second, you double the work.

For thumbnails specifically, the questions to ask:
1. Is the title text readable and bold enough at thumbnail size?
2. Is the pose cutout clean (no halo, no jaggies along hat/hair)?
3. Is the layout balanced?
4. Any visual problems?

### Bake new conventions into scripts + SKILL.md, not just into the current task

When a new convention emerges mid-task ("transparent pose companions for thumbnails", "single locked voice ID across the pipeline", "one prompt file not two"), the convention belongs in the script and the SKILL.md, not just applied to the current episode. This user treats skills as durable infrastructure; the same convention applied silently in this session will be forgotten next session if it isn't documented.

### Mid-pipeline checkpoint preference: Phases 1-4 → review → Phases 6+

For fresh episodes (mode A), the default execution strategy is to run **Phases 1-4 first** (re-skin, transcribe, script rewrite, TTS chunks), pause for user review of the script and a sample VO chunk, THEN run **Phases 6-8b** (talking-heads, thumbnail, metadata) once the script is approved.

Why this split: the script (Phase 3) carries the brand voice and the entire narrative arc, and the 6 talking-head AI generations (Phase 6) bake those exact lines into ~$0.50 of irreversible video assets. Letting the user catch a bad line BEFORE Phase 6 saves a regen cycle.

When the user is offered the choice between "full pipeline now" vs "Phases 1-4 first then review", they pick the checkpoint. Don't ask if you're not sure — just execute Phases 1-4 and send the deliverables (recolored video + script.md + th1 audio preview as a voice sample) with an explicit "approve or revise" prompt before continuing.

Cheap operations during the checkpoint pause (scene manifest building, chunk audio uploads to Drive, writing youtube-metadata.txt against the locked script) can run while waiting — they're free to redo if the script changes. Anything that calls `prunaai/p-video-avatar` waits for the green light.

### Delegate heavy episode pipelines to a subagent — the split, with long polls staying in main

**Updated May 2026:** the cost-control story changed (see \"Cost discipline\" section above). Active config sets `model: claude-opus-4-8` + `reasoning_effort: low` for both main session AND delegation, so subagents auto-inherit cheap opus-4-8 calls. No per-call `model=` override is needed anymore.

The reason to still delegate is **wall-clock and context isolation**, not cost: full episode pipelines (Phases 1-8b) and slideshow builds produce a lot of tool-trace noise that bloats the parent context. Push the LLM-heavy thinking into a subagent so the main session stays clean for the user-facing handoff.

**But: don't put the slow phases inside the subagent.** `delegate_task` has a 600-second wall-clock cap. Recolor alone runs 4-6 min, the 6 talking-heads each take 30-120s, and Replicate/ElevenLabs polls dominate the timeline. A naive single-shot delegation (\"run the whole pipeline\") hits the timeout at ~35 API calls with talking-heads still in flight, and the subagent's work is discarded — verified failure mode, Ep07 SpaceX Valuation first attempt (May 2026).

**The split (use this pattern):**

1. **Main session kicks off the slow background jobs** before delegating:
   - Phase 1 recolor (`edit_video.py`) → `terminal(background=True, notify_on_complete=True)`
   - Phase 2 Whisper transcription → background
   - Scene-cut detection → background
   - Talking-head generation (`generate_talking_heads.py`) is also a candidate to start from main if the script is already locked
2. **Subagent picks up once the cheap-but-thinking work is unblocked:**
   - Phase 3 script rewrite (the expensive LLM work)
   - Phase 4 TTS chunk emission (fast, no thinking — but uses the script)
   - Phase 6.5 thumbnail composition (PIL, fast)
   - Phase 8b youtube-metadata.txt (LLM work)
   - Drive uploads
3. **Main session collects the final manifest** and writes the user-facing handoff with MEDIA: previews.

This keeps the subagent under the 10-minute wall while still offloading the per-turn token cost. The subagent's brief must explicitly say: \"Phase 1 recolor + Phase 6 talking-heads + Whisper are running as background processes in the main session. Wait for their notify_on_complete signal via the user's relay, OR check log tails. Do not re-run them.\"

Trigger: cues like \"run the pipeline\", \"process this episode\", \"don't dump the trace on me\" mean adopt this split pattern.

**Correct call signature (current — May 2026):**
```python
delegate_task(
    goal=\"...\",
    context=\"...\",
    toolsets=[\"terminal\", \"file\", \"skills\"],
    # NO model= override needed — delegation.model in config.yaml is already claude-opus-4-8 + low effort
)
```

If the user explicitly asks for a DIFFERENT model in a specific session (\"use sonnet for this one\", \"try gpt-5\"), pass `model={\"model\": \"...\"}` for that delegation only. Otherwise, no override — the config does the right thing.

**Historical note (May 2026 cost-override era):** before opus-4-8 launched, the cost strategy was `model={\"model\": \"claude-sonnet-4-5\"}` on every delegate_task call. That guidance is obsolete and was removed from this skill when the user switched to opus-4-8 low effort. If you find an old session transcript referencing the Sonnet override, do not reapply it.

### Verify subagent self-reports against the filesystem + Drive before relaying

`delegate_task` returns a subagent-authored summary that LOOKS like a status report but is a self-report, not verified ground truth. Subagents have been observed claiming \"uploaded successfully\", \"all 6 talking-heads delivered\", \"manifest written\" when one or more of those was partial or wrong. The main session is responsible for the user-facing handoff; that handoff must reflect verified state.

**The minimum verification checklist before relaying a pipeline subagent's summary:**

1. `ls -la episodes/{slug}/` — confirm every artifact named in the summary actually exists locally with non-trivial size (e.g. `recolored-video.mp4` > 5MB, each `talking-heads/*.mp4` > 1MB, `thumbnail.png` > 500KB).
2. Drive list against the target folder ID — `svc.files().list(q=\"'{folder}' in parents and trashed=false\", ...)` and confirm the expected file count + subfolders are present. The subagent can complete locally and fail silently on the upload step.
3. For talking-heads specifically: `talking-heads/` should have exactly 6 MP4s with distinct pose numbers in the filenames (the rotation-ledger rule). A summary that says \\\"6 talking-heads delivered\\\" with only 4 files on disk is a partial run, not a complete one.
4. For thumbnails: `thumbnail.png` + `thumbnail-variants/` populated; the canonical and the 3 variants are 4 separate files.

If any check fails, surface the discrepancy in the handoff (\"subagent reported 6 talking-heads, only 5 on disk — th5 missing\") rather than relaying the summary as-is. The user trusts the main agent's handoff; a subagent's wrong claim becomes the main agent's wrong claim if you don't verify.

Verified May 2026 on Ep07 SpaceX Valuation Tender: subagent summary was accurate (14 root Drive items + 3 subfolders matched expectations), but the model field in the result revealed the cost-control override didn't take effect — a check that only happened because the verification pass was already running.

### Background-process notifications fire from STALE attempts too

`terminal(background=True, notify_on_complete=true)` delivers a completion event for every backgrounded shell exit, including attempts that failed early before the real worker ever started. When debugging a flaky background job (e.g. Replicate 403 → patch → re-launch), you'll receive notifications for the OLD failed attempts AFTER the new attempt has already produced output.

**Don't treat a late notification as authoritative status.** Always verify the actual state by:
1. Checking the log tail (`tail /tmp/<job>.log`) for the most recent successful or in-progress markers.
2. Listing the output directory (`ls -la <output_dir>`) for the artifacts that should exist if the job finished.
3. `pgrep -af <script.py>` to see whether the worker is still alive.

If the late notification's PID matches an OLD attempt, treat it as a stale signal and reaffirm what you observed from the log/filesystem. Don't restart a job that's already running fine. Don't tell the user a finished job is still in progress because the notification arrived late.

### Phase 9 — File-naming convention for episode artifacts

Per-episode files use a consistent pattern so CapCut alignment is mechanical and naming is self-documenting:

**Audio chunks (Phase 4):** `th{N}-{section-tag}_[{start_ss}-{end_ss}]_pose-{NN}-{action}.wav`
**Talking-head clips (Phase 6):** `th{N}-{section-tag}_[{start_ss}-{end_ss}]_pose-{NN}-{action}.mp4`

Where:
- `{N}` = 1-6, the talking-head index in script order
- `{section-tag}` = short slug for the moment (e.g. `intro-hook`, `key-point-1`, `setup-thesis`, `payoff`, `outro`)
- `[{start_ss}-{end_ss}]` = source-video timestamps in seconds.cs format (e.g. `[08.00-18.50]`) — these are the cut points relative to the SOURCE character-narrator MP4 the audio came from
- `pose-{NN}-{action}` = the chosen pose, matching the pose library naming (e.g. `pose-08-pointing-at-camera`)

Audio file and video file MUST share the same basename (only the extension differs). This way CapCut can find each pair by glob, and the talking-head video filename tells you everything: which slot, what content, where it cuts from the source, and what pose plays.

**Verified working sample:** episode `01-pure-play-space-stocks` produced `th1-intro-hook_[08.00-18.50]_pose-08-pointing-at-camera.wav` + `.mp4` — 10.5s clip, line "Your host here. Most of you buying into space are accidentally buying a defense contractor. You look at a ticker, you see a rocket, and you assume you own the frontier." Uploaded to Drive at `[brand]/.../01 - Pure-Play Space Stocks/talking-head-samples/` (folder id `<DRIVE_FOLDER_ID>`).

**Full episode 01 backfill (mode B):** all 6 talking-heads delivered to the same Drive folder.
- th1 intro-hook 08:00-18.50 → pose-08-pointing-at-camera (DIRECT-ADDRESS)
- th2 etf-trap 18:10-32.38 → pose-03-arms-crossed (SKEPTICAL)
- th3 spacex-ipo 76:50-91.00 → pose-05-both-hands-explaining (EXPLAINING)
- th4 five-tickers 135.08-154.98 → pose-02-hand-on-chest (SINCERE)
- th5 avoid-traps 237.36-254.62 → pose-10-hand-on-hip (CONFIDENT)
- th6 outro-cta 423.04-438.00 → pose-12-fist-at-chest (EMPHATIC)
6 distinct poses, no adjacent visual conflicts.

**Pitfall: Whisper timestamps drift on long audio.**
When transcribing a full-episode audio file (>3 minutes), Whisper's segment timestamps drift relative to source video time — they're consistent at the start, sometimes consistent in the middle, and can be 5-10s off near the end. For mode B, ALWAYS verify each candidate timestamp by extracting a 6-second window FROM SOURCE VIDEO at the target time and re-transcribing that short window. Whisper short-window transcription is accurate. The `find_th_timestamps.py` pattern in this skill demonstrates the probe-verify-adjust loop. In mode A this is a non-issue because we generate the VO ourselves and own the timing.

**Pitfall: Whisper auto-trims leading silence in standalone short clips.**
If you extract `-ss 0 -t 25` from the start of a video that has 8s of silent intro, Whisper may report content starting at t=0 (it dropped the silence). The actual source-video offset of the first spoken word can be anywhere in that window. Always probe the source video at the candidate timestamp, not from a pre-extracted clip.

## Worked-example folder tree (per episode)

```
~/.hermes/data/brand-youtube-pipeline/episodes/01-pure-play-space-stocks/
├── source.mp4                       # NotebookLM input
├── recolor-work/                    # notebooklm-brand-edit workdir
├── recolored-video.mp4              # Phase 1 output
├── transcript.json                  # Phase 2
├── script.md                        # Phase 3
├── script-per-scene.json
├── voiceover.wav                    # Phase 4
├── realigned-video.mp4              # Phase 5 (silent)
├── voiceover-final.wav
├── talking-heads/                   # Phase 6
│   ├── th-0-32s.mp4
│   ├── th-1-89s.mp4
│   ...
│   └── talking-heads.json
├── with-heads.mp4                   # Phase 7 intermediate
├── with-wordmark.mp4
├── final.mp4                        # ready for upload
└── metadata.md                      # Phase 8
```

## How to use this skill (the agent's checklist)

1. User provides NotebookLM video → drop it into a new `episodes/{slug}/source-notebooklm.mp4`. **If the Drive episode folder has multiple same-named or similar videos, ASK which is the source before downloading** — folders accumulate raw NotebookLM exports, recolored intermediates, and HTML-rendered variants. Ambiguity here costs an unrecoverable hour if you pick wrong (you'll TTS-rewrite for the wrong audio track). Confirmed pattern from Ep2 (May 2026): three same-named videos in the Drive folder, only the user could disambiguate. Always list candidate file IDs back to the user when more than one MP4 sits at the topic level.

**1a. Determine the topic slug from the Drive PARENT folder name, NOT the filename or assumed episode number.** The user pastes a `drive.google.com/file/d/{id}/view` link and the natural-feeling next step is to assume the next sequential episode number — that's wrong. Filenames like `SpaceX_Valuation_Strategy.mp4` or `Space_Job_Salaries.mp4` don't encode the topic number, and the user's source organization is by Drive folder, not by chronology. Always do:

```python
meta = svc.files().get(fileId=fid, fields='id,name,parents').execute()
parent = svc.files().get(fileId=meta['parents'][0], fields='id,name,parents').execute()
# parent['name'] is the canonical topic folder, e.g. "07 - SpaceX Valuation Tender — Investing"
```

Parse `NN - Title — Pillar` from the parent folder name to derive:
- Episode slug = `{NN}-{slug-of-title}` (lowercase, hyphenated)
- Pillar = the trailing `— Pillar` segment (Investing | Careers | Beginners | Tourism)
- Drive upload destination = the parent folder's own ID

Verified failures (May 2026): twice in one session, source filename suggested one topic but the Drive parent folder revealed it was actually a different topic in a different pillar. The parent folder is authoritative.
2. Verify `locked-character.png` exists. If not, run Phase 0.
3. Run phases 1→8 in order, with explicit confirmation checkpoints after Phase 3 (script lock) and Phase 6 (talking-heads).
4. After each phase, save the artifact and report to the user with a quick MEDIA: preview where possible (for video phases, send a 3-5s sample MP4).
5. Update `talking-heads.json` and `script-per-scene.json` as the single sources of truth for timing.

## The 4 Claude prompts (production templates)

All in `templates/`:
- `01_niche_analyst.md` — go/no-go on a topic
- `02_script_engine.md` — single-narrator [brand] script, scene-anchored, talking-head markers
- `03_metadata.md` — internal: titles + description + tags + thumbnail brief
- `04_scaling_analyst.md` — monthly analytics review
- `05_youtube_metadata.md` — public-facing YouTube upload package (`youtube-metadata.md`)

Scripts in `scripts/`:
- `generate_character_options_v2.py` — Phase 0 character generation
- `retry_character_variant.py` — Phase 0 single-variant retry
- `select_poses.py` — content-driven pose selection for talking-heads (Phase 6)
- `strip_pose_backgrounds.py` — Phase 0 follow-up: bg-remove every pose into a `-transparent.png` companion (idempotent, runs whenever new poses are added)
- `build_thumbnail.py` — Phase 6.5: render 1280×720 YouTube thumbnail with 3 variants
- `emit_tts_chunks.py` — Phase 4: read a `chunks.json` manifest, render one ElevenLabs TTS file per chunk (scene VOs as .mp3, talking-head clips as .wav, filenames encode target timestamps + pose). Voice locked to `TyJfVqGmT0iahaNbUE37`. Idempotent — skips chunks whose output already exists. Reuses `tts_chunk()` from `elevenlabs-narrator-revoice/scripts/revoice.py` for the actual API call. **Self-heals talking-head WAVs:** after each `pcm_24000` write, wraps the raw PCM in a proper RIFF/WAV header (1ch/16-bit/24kHz) so `prunaai/p-video-avatar` can decode.
- `generate_talking_heads.py` — Phase 6: read `chunks.json`, filter to talking-head entries, fan out 6 parallel `prunaai/p-video-avatar` predictions via threads (2s stagger), poll each to terminal, download MP4s with WAV-matching filenames. Auto-uploads >1.5MB assets via Replicate Files API; data URIs below that. Embroidery + camera-lock `video_prompt` baked in — single source of truth. Writes `talking-heads.json` manifest.

References in `references/`:
- `generative-output-validation.md` — A/B vision-grid recipe for validating prompt changes
- `whisper-hallucination-patterns.md` — Phase 2.5 cleanup catalog: foreign-language hallucinations, brand-name confusion, loop repetition, empty scenes. Real examples from Ep3 + Ep4 with detection heuristics.
- `pose-rotation-ledger.md` — per-episode pose usage tracker; READ before Phase 6 selection, UPDATE after Phase 6 ships. Source of truth for the anti-repetition rule.
- `replicate-api-gotchas.md` — Three failure modes that look like auth bugs but aren't (Prefer-wait body cap, urllib UA filter, Files API for big inputs). Read this BEFORE wiring up any new Replicate model in the pipeline.
- `model-and-effort-config.md` — current locked Hermes `model` + `reasoning_effort` for the pipeline (opus-4-8 + low across orchestrator + delegation), switching procedure, verification commands, and history of the obsolete Sonnet-override era.

## Critical pitfalls (do not skip)

- **Workdir lives at `~/.hermes/data/`, NEVER `/tmp`.** Sessions die. Episode state must survive.
- **Phase 1 strips NotebookLM badge from EVERY scene.** Their watermark is at bottom-right x≈1140-1270 y≈680-715 on a 1280×720 frame. Cover with solid `#121212` rectangle before our wordmark goes on top.
- **NEVER use the transparent wordmark variant.** Letterforms become unreadable over slide artwork. Use solid-bg `brand-lockup-horizontal.png` only.
- **Outro at END only — no intro at start.** Updated brand spec.
- **Intro/outro must fade.** 0.5s `afade=in` at start of outro to prevent hard music cut from content narration.
- **TTS runs on content-only timeline before bumpers are composited** — bumpers have music, TTS over silent music creates dead air.
- **Concurrent ffmpeg/Replicate writes need unique output paths.** Two parallel jobs writing to the same path corrupts the moov atom (verified bug, see memory).
- **gpt-image-2 read-timeouts** at provider layer are not retried by the SDK. Single-variant retry beats restarting the whole batch.
- **Scene alignment is sacred.** Phase 3's script can stretch/shorten a scene ±25% but cannot drop, merge, or reorder them. Visual subject must match audio subject per scene.
- **Talking-head clips are 10-20s only.** Shorter and the lipsync looks unmotivated, longer and viewer attention shifts off the slides.
- **Wordmark height = 10% of frame height, 2% bottom-right margin** — no manual offset shifts. The 2% formula handles all resolutions.
- **Don't use the concat demuxer for the final intro+content+outro merge** — use concat FILTER instead. Demuxer throws `Invalid NAL unit size` on mixed stream-copy + re-encode chains.
- **Phase 1 `edit_video.py` concat-path bug (recoverable, expensive if you re-run from scratch).** `notebooklm-brand-edit/scripts/edit_video.py` writes `recolor-work/concat-scenes.txt` with `file 'recolor-work/clip-NN.mp4'` entries, but the ffmpeg concat command is invoked from the parent episode dir → ffmpeg resolves the paths as `recolor-work/recolor-work/clip-NN.mp4` and fails with `Impossible to open ...`. All 15 clip-NN.mp4 scene assets AND the 6 gpt-image-2 light-scene recolors have already completed at that point — DO NOT re-run the whole script, you'll burn the recolor spend again. Recovery (verified Ep07 SpaceX Valuation Tender, May 2026):\n  ```bash\n  cd episodes/{slug}/recolor-work\n  # rewrite concat with relative-to-cwd paths\n  ls clip-*.mp4 | sort | awk '{print \"file \\047\"$0\"\\047\"}' > concat-fixed.txt\n  ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i concat-fixed.txt -c copy silent-recolored.mp4\n  cd ..\n  ffmpeg -hide_banner -loglevel error -y -i recolor-work/silent-recolored.mp4 \\\n    -i source-audio.mp3 -c:v copy -c:a aac -shortest recolored-video.mp4\n  ```\n  Long-term fix: patch `notebooklm-brand-edit/scripts/edit_video.py` to either (a) chdir into `recolor-work/` before invoking ffmpeg on `concat-scenes.txt`, or (b) emit absolute paths in the concat file. Until that patch lands, the recovery snippet above is the standard play.\n- **Phase 6 `generate_talking_heads.py` is idempotent — re-run it to retry partial failures.** When 1 of 6 talking-heads fails (Replicate "Prediction interrupted; please retry (code: PA)" is the common one), just re-invoke the runner with the same args. The script checks `out_path.exists() and size > 100_000` per clip and prints `[clip-name] exists, skip` for the 5 that succeeded — only the failed clip re-submits. Single-clip retry costs ~$0.10-0.15, not the full $0.80. Verified Ep07 May 2026: th5-tactical-setup failed with PA code, re-run picked it up, finished in ~30s, manifest auto-updated. No need to write an inline one-off retry script.

## Source attribution

Framework derived from @w1nklerr's X article "How I Made an AI Channel That Generated $12,000 in One Month" (May 2026, ID 2054239999957012480). 4-prompt structure (niche analyst / script engine / metadata / scaling) is his; prompts and process are rewritten for [brand] voice, single-narrator format (one locked voice `TyJfVqGmT0iahaNbUE37`), and the specific NotebookLM → re-skin → revoice → talking-head workflow.

Talking-head model: `prunaai/p-video-avatar` (Replicate). 720p, audio-driven lipsync from a single reference image.
