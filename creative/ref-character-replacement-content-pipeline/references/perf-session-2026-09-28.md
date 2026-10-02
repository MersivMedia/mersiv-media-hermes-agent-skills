# First v1.1 perf session (2026-09-28, H100 80GB HBM3, $3.49/hr)

Unattended via `poll_and_run.sh`: the H100 was placed on attempt 7, bootstrap
finished at 19:20, the budget cap was hit at 20:50, and the pod stopped at
20:52 (desiredStatus EXITED, verified). Cost $5.69. Only Phase A ran; Phases
B (SageAttention) and C (shared lanes) never started, and the PRO 6000 was
never tested.

Drive: batch `2026-09-28_perf-a-serial` (renders, 1 upscale, compare, results Sheet).

## Measured (5 s clip, turbo, background on, seed 4242)

| Job | Output | exec | Cost | Peak VRAM |
|---|---|---|---|---|
| J01 480p 4 steps (first job, includes model load) | 832×480, 124 f | 467 s | $0.45 | 76.4 GB |
| J02 768p 4 steps (warm) | 1344×768 | 340 s | $0.33 | 80.8 GB |
| J03 768p 3 steps (warm) | 1344×768 | 339 s | $0.33 | 80.8 GB |
| J01 → 2K SeedVR2 7B int8, 6 steps | 2496×1440 | 562 s exec / 902 s wall | $0.55 | 81.1 GB |
| J01 → 4K SeedVR2 | output lost to worker bug | ~40 min wall | ~$2.30 | ? |

## Conclusions

- **768p is the default:** once warm it costs the same as 480p and is visibly sharper.
- **3 vs 4 turbo steps: no time saved.** The output did change (J02 vs J03 PSNR
  25 dB), so the override applied. The step count isn't what sets the pace.
  Suspected cause: text-encoder/model offload churn at 80.8/80 GB. That's
  unproven, because per-step timing was empty. If it's right, the 96 GB PRO 6000
  is the real lever.
- **SeedVR2 costs more than the render.** In a 640² crop, 480p→2K about
  matches bicubic-upscaled 768p and is only slightly sharper. 4K at ~40 min per
  5 s clip isn't viable. Answer to "480 ×N vs 768 ×M": render 768p and upscale
  only when a deliverable needs it. SeedVR2 3B or ESRGAN for 4K are still untested.
- Identity held in all four. The reference's background people were copied
  again (known background-mode behaviour).

## Bugs found (1–3 FIXED offline 2026-09-28, red/green tested; 4 open)

1. **Upscale worker took the wrong output entry.** `upscale_run.py` collects
   `videos/gifs/images` from EVERY node in the ComfyUI history. That includes
   the load node's preview of the input clip. The worker took `vids[-1]`,
   resolved it under `output/`, and hit
   `FileNotFoundError: /workspace/ComfyUI/output/J01_..._480p.mp4` (the INPUT
   name). The worker crashed and J02's 2K/4K tickets were stranded. Fix: keep
   only entries with `type == "output"`, preferring the SaveVideo node; never pick by position.
   **Fixed:** `comfy_api.pick_output()` (type=="output", prefix match first,
   file must exist) is used by both `batch_runner.py` and `upscale_worker.py`.
   The render lane had the same latent bug. The worker now runs every ticket in
   try/except (one bad ticket marks itself `.failed`, the lane lives), writes a
   heartbeat, and requeues stale `.working` tickets on start.
2. **`wait_batch` didn't notice a dead worker.** It waits while ticket files
   exist, and the crash left a `.working` ticket behind, so it spun for about
   25 min until the budget guard fired. It needs a liveness check
   (`pgrep upscale_worker` / tmux session) and should fail fast.
   **Fixed:** `pod/batch_status.sh` returns DONE / BUSY / WORKER_DEAD (no
   process, or heartbeat >120 s old). `wait_batch` restarts the worker once
   (`bootstrap.sh --restart-upworker`); a second death marks the batch's tickets
   `.abandoned` and moves on. It also prints monitor lines only when they
   change (the old log repeated one line ~300 times).
3. **Timing capture is wrong.** The whole render is credited to
   `H3PromptDirector` (node 160: 455 s / 335 s), `median_step_s` is empty, and
   `gpu` = "?". Per-node attribution from websocket `executing` events is off by
   one node or missing sampler events. Until it's fixed, `exec_s` (from ComfyUI's
   own timestamps) is the only trustworthy number.
   **Fixed (root cause found):** the websocket was opened with `timeout=15`,
   which also applies to `recv()`. The Director's Claude call is silent for
   longer than that, so recv timed out, the client treated it as a dead socket
   and fell back to HTTP polling, and no more events arrived. Now recv uses a 5 s
   timeout that means "silence" (the loop continues, with a history check every
   30 s as a safety net). `gpu="?"`: RunPod's REST omitted `machine.gpuTypeId`,
   and bootstrap trusted the "?". Bootstrap now treats "?" as unknown and falls
   back to nvidia-smi. **Unverified on a pod:** step timing fires on the real
   server.
4. **Pod self-stop check: `GET /pods/<id>` → 403 with an EMPTY body** (unlike
   the Cloudflare 1010 UA block). Likely the pod's injected `RUNPOD_API_KEY`
   is scoped and can't read or stop pods. Unverified. The local stop worked,
   so the session still ended cleanly. Don't count on the pod-side cap until a
   stop call from inside a pod is proven, e.g. with a user key in `/root/secrets.env`.

## Next session (~30 GPU-min)

Run `PHASES=RBC scripts/perf_session.sh ...` (A_BATCH defaults to this batch):
- **R** runs `pod/recover_upscales.sh`, which adopts the 4K that ComfyUI saved
  but the worker never copied (no redo) and re-tickets J02's 2K/4K from the
  render already on the volume. It doesn't re-render phase A.
- **B** is SageAttention on vs off. **C** is shared-lane overlap.
- Prefer a PRO 6000 for the H100 comparison (80.8/80 GB was the suspected brake).

Tests: `test_perf_fixes.py` (13; it FAILS 8 against the pre-fix code, verified),
`test_waitbatch.sh` (5), `test_recover.sh` (7). The mock ComfyUI now lists the
loaded video as a `type: "input"` history output, like the real server does.
