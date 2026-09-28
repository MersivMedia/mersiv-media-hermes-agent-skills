# Episode runner — the long-term "paste-link-and-walk-away" design

Goal: user pastes a Drive video link, a cron job ships the full episode to the topic Drive folder without either Opus or Sonnet in the loop. Eliminates the `delegate_task` 10-min timeout entirely.

## Why this matters

Current Phase 1-8b pipeline is mostly mechanical:
- Phase 1 recolor — pure ffmpeg + Replicate gpt-image-2 calls
- Phase 2 transcribe — Replicate WhisperX
- Phase 4 TTS — ElevenLabs API
- Phase 6 talking-heads — Replicate `prunaai/p-video-avatar`
- Phase 6.5 thumbnail — PIL composition
- Phase 8b metadata — text emission
- Drive uploads — googleapiclient

The only step that actually needs a model is **Phase 3 script rewrite** (and arguably Phase 8b title/description copy). Everything else is deterministic given the inputs.

## Proposed architecture

A single `scripts/run_episode.py` that takes:
- `--source-file-id` (Drive file ID of the NotebookLM-generated video)
- `--topic-folder-id` (Drive folder where deliverables upload)
- `--pillar` (investing/careers/beginners/tourism — drives thumbnail color)
- `--slug` (filesystem-safe episode slug)

The script runs Phases 1, 2, 4, 6, 6.5, 8b serially in the cron job's process. Phase 3 is the only step that hits a language model — it shells out to a one-shot Sonnet call (anthropic SDK, single turn, ~2-4k input tokens, ~1k output) with the transcript, scene manifest, and Phase 02 prompt template. Then continues mechanically.

Total wall-time: 10-20 min depending on TTS chunk count and talking-head queue. Total cost: ~$1.10 + one Sonnet call (~$0.02) instead of 35+ tool calls of Opus reasoning time.

## Cron invocation

```bash
cronjob action=create name="ep-runner" \
  prompt="ignore, no_agent=True" \
  no_agent=True \
  script="~/.hermes/skills/brand/brand-youtube-pipeline/scripts/run_episode.py --source-file-id $ID --topic-folder-id $TID --pillar $PILLAR --slug $SLUG" \
  schedule="2026-XX-XX 12:00"
```

Wrapped in a thin "queue an episode" helper the user can text from their phone.

## Phases that stay manual (out of scope for runner)

- **Phase 5 user assembly** — CapCut is the user's job; they own creative final cut. The runner ships deliverables, not a finished video.
- **Phase 7 final composition** — same reason.

## Open questions before building

- Phase 3 script-rewrite quality from a single-shot Sonnet call vs an iterative agent loop — needs an A/B on Ep08 to confirm quality is acceptable.
- Thumbnail pose-selection logic (currently agent picks based on content vibe) — needs codification into a pillar+sentiment lookup table, or a tiny Sonnet sub-call.
- Failure mode handling: a Replicate prediction failing mid-run should retry once then surface a Telegram alert.

## Status

Not built. Captured here because the cost-control conversation (May 2026, Ep07) made it a near-term priority. Build after Ep08-10 stabilize.
