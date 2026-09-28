# GPU availability, approved fallbacks, and the poller

## What happened (2026-09-28)
- `pod.py start <pod-id>` failed: `start pod: There are not enough free
  GPUs on the host machine to start this pod.` A stopped pod is pinned to its
  host. The fallback is creating a new pod on volume `<volume-id>`, which gives a
  new pod id, proxy URL and SSH port. `refswap_up.sh` saves the id to
  `~/.hermes/data/ref-character-replacement/pod_id` and terminates the
  superseded EXITED pod.
- RTX PRO 6000 Server/Workstation Edition had zero instances in EU-NL-1 for
  hours. The only big card free was a B300 at $7.89/hr. The poller placed a PRO
  6000 Server Edition on attempt 4 (~4 min) once it was running.
- Placed pod `<pod-id>` died at the first push: the RunPod image has no
  `rsync`. The poller stopped it with no measurable spend. All transfers are now
  tar over ssh, checked by `tests/test_transfer.sh`.

## User decisions (binding until they say otherwise)
- Approved order: **RTX PRO 6000 → H100 PCIe → H100 SXM**. B300 excluded.
- Poll **every 60 s** (the user asked for 1 min, not the proposed 15). Give up
  after 24 h with no spend.
- Never substitute a card that isn't on the list; ask first.

## Exact RunPod GPU ids (validate against GraphQL `gpuTypes { id }`)
- `NVIDIA RTX PRO 6000 Blackwell Server Edition` (the one that gets placed)
- `NVIDIA RTX PRO 6000 Blackwell Workstation Edition` /
  `... Max-Q Workstation Edition` (usually "could not find any pods with
  required specifications")
- `NVIDIA H100 PCIe`, `NVIDIA H100 80GB HBM3` (SXM)

## Why not the B300 for the perf session
- Break-even needs ≥2.26× H100 speed ($7.89 / $3.49).
- The H3 weights here are int8, and B300 int8 throughput is cut, so any speedup
  is unclear.
- sm_103 may lack kernels in torch 2.11+cu128, so it could fall back or fail.
- 288 GB hides exactly what the shared-lane test measures (VRAM contention),
  and its per-clip cost describes a card we won't rent.

## Mechanics (scripts/poll_and_run.sh)
- Loop: `refswap_up.sh --allow-gpu "NVIDIA H100 PCIe" --allow-gpu "NVIDIA H100 80GB HBM3"`.
  Exit 2 means nothing was placed, so sleep `POLL_S`. Any other non-zero exit
  after placement means stop the pod, then exit, so a half-bootstrapped pod
  never bills.
- On placement: start `autostop_watch.sh` with the three batch names, run
  `perf_session.sh` with `PERF_DATE` fixed, wait for the watcher to sync + stop.
- `perf_session.sh` touches `/root/SESSION_HOLD`; `pod/autostop.py` treats it as
  busy so lane restarts between phases can't trigger a stop.
- Status in `~/.hermes/data/ref-character-replacement/poll.status`, log in
  `poll.log`, per-attempt bring-up output in `up_attempt.log`.
- Before any restart: `bash tests/test_transfer.sh && bash tests/test_offline.sh`.
- Launch as a Hermes background process (`terminal background=true,
  notify=true`). Shell `setsid/nohup/disown` wrappers are rejected by the
  harness. The launch itself needs user approval (unattended paid spend), and
  on Telegram that prompt can expire, so tell the user to watch for it.
- A notify of `exit 1` means placement happened and bring-up failed. Read
  `poll.status` + the `poll.log` tail and confirm via `pod.py list` that the pod
  is EXITED before anything else.
