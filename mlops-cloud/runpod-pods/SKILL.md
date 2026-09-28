---
name: runpod-pods
description: "RunPod GPU pods: launch on a network volume, check what is running, stop or terminate."
version: 1.0.1
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [runpod, gpu, cloud, rental, network-volume, inference, pod-lifecycle]
    related_skills: [wan2gp-yue2-covers, modal-serverless-gpu, lambda-labs-gpu-cloud, paid-resource-preflight]
---

# RunPod GPU Pods

## When to Use

Any GPU work on RunPod, start to finish: launch a pod (usually on one of our
network volumes), check whether a pod is running and what is on its volume,
SSH in, open its web UI, and stop or terminate it when the job is done. This
machine has no GPU (**no NVIDIA driver, 1.9 GB RAM, 2 cores**).

Triggers: "rent a GPU", "spin up a pod", "launch a GPU on our volume",
"is the pod running", "turn off / shut down the pod", "we don't have enough
VRAM".

For a *new* workload, check a hosted API first (Replicate, fal). Rent only
when no API serves the model, or when a session of many runs beats per-call
pricing.

## Credentials

In `~/.hermes/.env`, chmod 600:

```
RUNPOD_API_KEY                main API key
RUNPOD_S3_ACCESS_KEY_ID       S3 access to network volumes
RUNPOD_S3_SECRET_ACCESS_KEY
```

Account: `<your-account-email>`. Env vars are **not** inherited by
`execute_code` — run from `terminal` with `set -a; . …/.env; set +a`.

## Two APIs, use the right one

| API | Endpoint | Use for |
|---|---|---|
| **REST** (preferred) | `https://rest.runpod.io/v1` | pods, network volumes — clean JSON, `Authorization: Bearer` |
| **GraphQL** | `https://api.runpod.io/graphql?api_key=…` | GPU pricing, stock, datacenter list, account balance |

REST is easier and is what `scripts/pod.py` uses. GraphQL is still the only
source for `lowestPrice` and `stockStatus`.

## Always check balance first

A pod silently fails to start at $0.00 balance.

```bash
set -a; . ~/.hermes/.env; set +a
python3 scripts/pod.py balance
```

## Picking a GPU

```bash
python3 scripts/pod.py gpus          # live price + stock, >=16GB
```

Verified rates (re-check; they move and stock is often `Low`):

```
$0.35/hr  A40 48GB            best value
$0.50/hr  RTX PRO 4000 24GB
$0.69/hr  RTX 5090 32GB
$0.79/hr  L40S 48GB
$1.00/hr  A100 SXM 40GB
$2.69/hr  H100 SXM 80GB
```

**Match VRAM to the job, not to ambition.** A 3B int8 model needs ~6 GB; the
A40's 48 GB is already overkill and costs a third of an A100.

## Network volumes — the important detail

**Only `/workspace` survives pod termination.** The container filesystem does
not. This governs how everything gets installed.

```bash
python3 scripts/pod.py volume-create --name models --size 50 --dc EU-RO-1
```

Consequences to design around:

- Clone repos to `/workspace/<project>`, not `/root` or `/`
- Create venvs **inside** `/workspace` — a `pip install` into system Python is
  gone next session
- Point model caches at the volume: `export HF_HOME=/workspace/hf`
- A volume bills **continuously** (~$0.07/GB/month) whether or not a pod runs.
  50 GB ≈ $3.50/month. Delete it when the project ends.

Volumes are **datacenter-locked** — a pod can only mount one in its own
datacenter. Pick a DC with both storage support and the GPU in stock. Verified
storage-capable: `EU-RO-1`, `EU-NL-1`, `EU-FR-1`, `US-CA-2`, `CA-MTL-3`,
`CA-MTL-4`, `AP-JP-1`, `EUR-IS-1`, `EUR-NO-1`.

## SSH keys must be injected AT CREATION

Registering a key on the account (`updateUserSettings`) does **not** reach an
existing pod, and stop/start does not re-inject it. The key only lands via
`env.PUBLIC_KEY` in the create call:

```python
body["env"] = {"PUBLIC_KEY": open(os.path.expanduser(
    "~/.ssh/id_ed25519.pub")).read().strip()}
```

`scripts/pod.py create` does this automatically (generating a key if none
exists). If SSH says `Permission denied (publickey)`, the pod was created
without it — terminate and recreate; there is no way to fix it in place.

## Running things on the pod without losing them

Three traps, all hit in practice:

**Never `pkill -f <script>.py` over SSH.** The pattern matches your own SSH
command line (which contains that string), so it kills the shell issuing it.
Every command after it returns empty and looks like the pod is broken. Use a
bracket to break the self-match:

```bash
pkill -f "[w]gp.py"        # safe — the literal string never matches itself
```

Safer still: `tmux kill-server`, then relaunch.

**Logs on `/workspace` can vanish.** It is a MooseFS network mount
(`mfs#<region>.runpod.net`), not local disk. A log observed at 3 KB
disappeared between two reads. Write logs to `/root`, keep only models and
code on the volume.

**`nohup … &` dies with the SSH session.** Use tmux, launching from a small
script file so the pattern-matching trap above cannot bite:

```bash
apt-get install -y -qq tmux
printf 'cd /workspace/app\nexec ./venv/bin/python -u app.py --listen\n' > /root/start.sh
tmux new-session -d -s srv "bash /root/start.sh > /root/srv.log 2>&1"
tmux capture-pane -t srv -p -S -200 | tail -40   # read live output
```

**Read logs with the timestamp in mind.** After a failed restart the old log
is still on disk; re-reading it and seeing the original traceback looks like
the fix failed when the service never started. `rm` the log before relaunching.

## Lifecycle

```bash
python3 scripts/pod.py create --gpu "NVIDIA A40" --volume <id> --name work
python3 scripts/pod.py list
python3 scripts/pod.py wait <pod-id>          # blocks until RUNNING
python3 scripts/pod.py ssh <pod-id>           # prints the ssh command
python3 scripts/pod.py url <pod-id> 7860      # proxy URL for a web UI
python3 scripts/pod.py stop <pod-id>          # keeps disk, stops GPU billing
python3 scripts/pod.py terminate <pod-id>     # destroys the pod
```

**Stop vs terminate.** Stopping releases the GPU and halts GPU billing. It
keeps `/workspace` (volume disk or network volume) but **clears the container
disk**, so anything installed outside `/workspace` is gone after a stop too.
Volume disk keeps billing while stopped. Terminating destroys the pod; only a
network volume survives it. With a network volume attached, `/workspace` is
preserved either way, so terminate freely. On restart, a stopped pod may come
back with zero GPUs if capacity has changed (RunPod docs: Manage Pods).

**An idle running pod bills the full hourly rate.** Always terminate when done;
say so explicitly rather than assuming the user will.

## Reaching services on a pod

RunPod proxies any exposed HTTP port:

```
https://<pod-id>-<port>.proxy.runpod.net
```

Declare ports at create time (`--ports "7860/http,22/tcp"`). A Gradio app on
7860 becomes reachable without a tunnel. Bind to `0.0.0.0`, not `127.0.0.1`,
or the proxy sees nothing.

## Standard bring-up

```bash
POD=$(python3 scripts/pod.py create --gpu "NVIDIA A40" --volume $VOL \
        --ports "7860/http,22/tcp" --name myjob --json | jq -r .id)
python3 scripts/pod.py wait $POD

ssh $(python3 scripts/pod.py ssh $POD --raw) <<'REMOTE'
  set -e
  cd /workspace                      # everything lives here
  export HF_HOME=/workspace/hf
  [ -d proj ] || git clone <repo> proj
  cd proj
  [ -d venv ] || python -m venv venv
  . venv/bin/activate
  pip install -q -r requirements.txt
REMOTE

python3 scripts/pod.py url $POD 7860
```

## Pitfalls

- **$0.00 balance** — pod creation fails with an unhelpful error. Check first.
- **Cloud type is not pinned by default.** A GPU quoted at $0.34/hr on
  community cloud can land on secure cloud at $0.74/hr. Check `costPerHr` in
  the create response and `machine.secureCloud`; if the rate matters, say so
  before creating, and confirm after.
- **Installing outside `/workspace`** — lost on terminate. The venv too.
- **Logs on `/workspace` can disappear** — MooseFS mount; log to `/root`.
- **`pkill -f script.py` over SSH kills your own session.** Use `[s]cript.py`.
- **SSH keys only inject at creation** — see the section above.
- **Volume/GPU datacenter mismatch** — pod will not start. A volume is locked
  to its DC forever, so pick a DC that carries the GPUs you will want later.
- **`stockStatus: Low`** on most GPU types; fallbacks RTX 4090, A6000, 3090 Ti
  all work at ~$0.27-0.34. Check stock *per datacenter*, not globally — the
  global list shows availability that may not exist in your volume's DC.
- **Binding to 127.0.0.1** — the proxy cannot reach it. Use `0.0.0.0`.
- **RunPod's HTTP proxy can drop websockets.** Gradio/Jupyter UIs reconnect-loop
  through `<pod>-<port>.proxy.runpod.net`. Launch with `--share` and use the
  `*.gradio.live` tunnel instead; it bypasses the proxy entirely.
- **Idle pods bill.** No auto-shutdown by default.
- **Volumes bill while no pod exists.** Delete when the project ends.
- **GraphQL needs the key in the query string**, REST needs a Bearer header.

## Cost discipline

Estimate before creating; report actual on teardown.

```
setup + model download     15-25 min
working session            30-60 min
A40 @ $0.35/hr             ~$0.50 total
50GB volume                ~$3.50/month, ongoing
```

State the estimate, get agreement, run one item before batching.

## Related

- `wan2gp-yue2-covers` — a worked example of this skill
- `modal-serverless-gpu`, `lambda-labs-gpu-cloud` — alternatives
