---
name: rented-cpu-render-jobs
description: "Use for heavy renders: self-terminating CPU pod per job."
version: 1.0.0
author: Hermes Agent (proven Oct 2026 on the French space channel, 7 pod jobs)
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [runpod, cpu, render, ffmpeg, playwright, parallel, subagents, cost-control]
    related_skills: [runpod-pods, motion-graphics, viral-youtube-video, generated-asset-verification, paid-resource-preflight, subagent-driven-development]
---

# Rented CPU render jobs (one pod per job, many in parallel)

## When to use
- Any heavy render or encode: 1080p canvas/Playwright graphics, photo-motion (Ken Burns/parallax) slots, full
  video assembly, batch ffmpeg. **User's standing rule: always rent the fast CPU server for this, no need to
  ask.** This box (2 cores, ~1.9 GB RAM) is for small previews only.
- Several deliverables (episodes, films) need rendering at the same time.
- Not for GPU work or persistent services: use `runpod-pods` (network volumes, GPUs, tmux services).

Scale of the win: a 1080p graphic took 680–1,864 s locally. On a pod, 14–16 graphics plus 15 photo slots
rendered in 24–253 s.

## The job script (one file, self-contained)
Pod: `cpu3c-16-32` (16 vCPU / 32 GB, ~$0.48/hr, EU-RO-1), image `runpod/base:0.6.2-cpu`, no network volume.
Lifecycle: `~/.hermes/skills/mlops-cloud/runpod-pods/scripts/pod.py` (`balance`, `create`, `wait`, `ssh`,
`list`, `terminate`). Load `.env` with `set -a; . ~/.hermes/.env; set +a`; never print keys.

1. **Pack locally:** every input, the code, `~/.fonts`, and `~/.cache/ms-playwright/chromium_headless_shell-*`.
   The pod image is Ubuntu 20.04, where `playwright install` refuses; the shipped shell runs once apt has
   libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libgbm1 libxkbcommon0 libpango-1.0-0 libasound2.
   Use static node and ffmpeg tarballs.
2. **Create → wait → scp → run a remote script FILE.** Never send inline `pkill -f <name>` over ssh: it matches
   its own command line and kills the session (use `[n]ame` patterns).
3. **On the pod:** untar, then `mkdir -p` EVERY output directory the steps write to. An episode rendered fine,
   then assembly failed because `edit/` wasn't in the tarball. Run items concurrently (`xargs -P 16` or
   background jobs + `wait`), each with a unique output path (concurrent ffmpeg writes to one path corrupt
   the moov atom).
4. **Pull back, verify locally** (file counts, frame totals, `ffprobe`), print `OK`/`FAILED`.
5. **`trap` on EXIT terminates the pod**, whatever happened. Print the balance before and after, and report
   the real cost next to the estimate.

Measured: pod wall ~7–8 min (create + apt + upload dominate), render 24–253 s, $0.04–0.63 per job. The first
estimate ($0.20) undercounted startup. Put everything one job needs into a single pod session.

Worked examples: `~/.hermes/data/yt-arbitrage/fr-space/pod_graphics.sh` (graphics jobs as `ID:from:to`) and
`pod_episode.sh <episode> <graphics-project>` (graphics + photo slots + assembly + sync audit, ~320 MB upload,
prints `EPISODE OK/FAILED`). Episode tool table: `references/fr-space-episode-pipeline.md`.

## Running many jobs in parallel
- Each job creates its OWN pod and temp dir (`/tmp/vgpack/pod_<job>`). Only the account balance is shared:
  check it once before fanning out.
- Never start the same job twice: two pods. After killing or double-starting a run, `pod.py list` and
  terminate leftovers by id BEFORE reporting. A SIGKILLed local script never runs its trap.
- Render is minutes; prep (planning, generation, QC, specs) is hours. To actually parallelise deliverables,
  give each one a subagent worker that also runs its own pod job (see below). Say this split to the user up
  front instead of promising "parallel rendering" alone.

## Subagent workers that build and render
- `delegation.child_timeout_seconds` was 600 s by default: enough for writing a script, fatal for a media
  build (a worker died at 10 min mid-spec with no summary). Media workers need ~7200 s and
  `delegation.max_iterations` ~250. Config changes need the user's approval: ask in chat FIRST (the approval
  prompt times out unattended), then run `hermes config set …` from a small script file. Check both values
  before dispatching any worker expected to exceed 10 minutes.
- Give every worker one brief FILE (rules, paths, worked example, spend caps, QC gates, final JSON) plus
  `output_schema`. Per-worker context adds only deliverable-specific facts. Lessons learned mid-run go into
  the brief file; `steer` only reaches live children.
- Max 3 concurrent children here; start the longest deliverable as soon as a slot frees.
- Workers share this box: every local preview goes through `flock /tmp/vgpack/preview.lock <cmd>`.
- **Resuming a cut-off worker:** files survive. Read the tail of
  `~/.hermes/cache/delegation/live/<deleg_id>/task-N.log`, then dispatch with what exists, spend used,
  REMAINING caps, and "do NOT regenerate".

## Verification
- `EPISODE OK` / `OK` line, local counts match, `pod.py list` shows no pods, balance delta reported.
- Automatic gates passing is not QC. Pull frames at the start, middle and end of every camera move and look
  at them before uploading (`generated-asset-verification/references/archive-localization-and-framing-qc.md`).
- **A rendered episode is not a delivered one.** Check the Drive `edit/` folder for every episode you report on.
  On 2026-10-06 the user found that two `EPISODE OK` renders had never been uploaded.
- Full-episode visuals builds (in session or delegated: lessons, worker context, verifying a worker's claims):
  `references/episode-visuals-worker-lessons.md`.
