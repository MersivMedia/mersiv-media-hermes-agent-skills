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

## Stuck-host placements (2026-09-29)
- Two PRO 6000 placements in a row (`<pod-id-1>`, then `<pod-id-2>`)
  landed on the SAME machine `<machine-id>`. Both sat with `desiredStatus
  RUNNING`, `runtime: null` and no IP, and never booted. `pod.py wait` timed out
  at 600 s on the first. Healthy pods here reach RUNNING in 15–30 s.
- Diagnose while waiting, not after:
  GQL `pod(input:{podId:"<id>"}) { machineId runtime { uptimeInSeconds } }`.
  If runtime is null after ~60 s on a machineId that already stalled, terminate
  it and stop polling. Report to the user: pod ids, the machine id,
  "Rented by User" timestamps, and runtime null.
- `refswap_up.sh` terminates stalled pods (exit 3) and the poller retries up to
  `MAX_STALLS`. That helps only if the DC has more than one free machine for the
  GPU. With one free machine it just repeats the stall at ~$0.28 per try.
- The user asked "is there another GPU we can use?" Answer with
  `scripts/gpu_stock_by_dc.py --dc EU-NL-1` (in-DC table: VRAM, $/hr, verdict
  vs H3's measured 80.8 GB peak) plus `--gpu <id> --all-dcs` to show where the
  preferred card IS in stock. Also give the real cost of moving: a new volume,
  the rebuild and monthly storage.
  Snapshot 2026-09-29 EU-NL-1: PRO 6000 Server $2.09 (stuck host only),
  H100 SXM $3.49 (reliable), L40S $1.09 (48 GB, too small), B300 $7.89
  (excluded). PRO 6000 Server was in stock in 12 other DCs incl. EU-RO-1.
