# GPU Pod Provisioning for ComfyUI Video Work

Verified on RunPod (L40S 48 GB, EU-NL-1, network volume), Sept 2026.
Complements `comfyui/references/gpu-pod-ltx25-setup.md`; this file covers
the provisioning and disk-management traps specifically.

## Provisioning via GraphQL

```graphql
mutation {
  podFindAndDeployOnDemand(input: {
    cloudType: SECURE
    gpuCount: 1
    volumeInGb: 0
    containerDiskInGb: 40
    gpuTypeId: "NVIDIA L40S"
    imageName: "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"
    dataCenterId: "EU-NL-1"
    networkVolumeId: "<volume-id>"
    volumeMountPath: "/workspace"
    ports: "8188/http,22/tcp"
    env: [{ key: "PUBLIC_KEY", value: "<your ssh public key>" }]
  }) { id name costPerHr }
}
```

Two traps that cost an hour each:

- **`env: PUBLIC_KEY` is mandatory.** API-deployed pods do NOT inherit the
  account SSH key the way console-deployed pods do. Without it every
  connection is `Connection refused` and the pod is unreachable.
- **Do not pass `dockerArgs`.** Overriding the command (e.g.
  `bash -c 'sleep infinity'`) replaces the image start script that launches
  sshd. The pod runs; you cannot get in.

The network volume is pinned to one data centre — the pod must deploy in the
same `dataCenterId` or it cannot attach.

## Getting a GPU when stock is thin

- **A stopped pod often can't restart:** `There are not enough free GPUs on
  the host machine to start this pod`. With a network volume that doesn't
  matter: create a new pod on the same volume, then terminate the old EXITED
  one. The proxy URL and SSH port change with the new pod id.
- **Read create errors precisely:**
  `There are no instances currently available` means the type is valid and
  simply busy, so retry. `could not find any pods with required
  specifications` means the variant isn't offered in that DC/spec at all, so
  polling won't help.
- **Poll, don't upsell.** When nothing on the approved list is free, loop
  every 60 s over an ordered list (cheapest approved first). It costs
  nothing while waiting. In EU-NL-1 an RTX PRO 6000 freed up about 4 minutes
  in. Don't quietly fall back to a pricier card: say the rate and get a yes.
- **Unattended bring-up must stop its own pod on failure.** See the next
  section: "stop on failure" as written here once wasn't enough.
- **Stuck placement:** the pod shows `desiredStatus: RUNNING` but has
  `runtime: null` and no IP for minutes (healthy pods get one in 15–30 s).
  Bound the wait (~8 min), then TERMINATE (a stopped pod restarts on the same
  host), verify it's gone, clear the saved pod ID, and cap retries. In a thin
  DC, a fresh pod landed on the same bad `machineId` again. After the second
  stall on one machine, stop and offer another GPU, DC or a support ticket.
- **Do setup on a CPU pod, not a GPU.** Installs, downloads, inventory and
  volume copies need no GPU. CPU pods attach network volumes at
  $0.06–0.12/hr. Details, and how to copy a volume to another DC (there is no
  migrate API): `paid-resource-preflight/references/runpod-cpu-pods-and-volume-moves.md`.

## Unattended runs: stop on EVERY exit path (incident, $4.48 lost)

An H100 idled about 75 min with zero output. Four bugs stacked:
1. The first batch push died: root `tar` on MooseFS gave `Cannot change
   ownership`. Fix: `tar --no-same-owner -x` on every remote extract.
2. The failure branch **waited on a watcher** (`wait $WATCH`) instead of
   stopping the pod.
3. The pod's own auto-stop was silently refused. RunPod REST returns 403
   (Cloudflare 1010) to Python's default `Python-urllib` User-Agent, and
   bring-up had only checked that the key *existed*.
4. The "120-min pod cap" didn't exist. The only cap was on the controller
   box, so it never fired in time.

Rules now:
- Register `trap stop_pod EXIT INT TERM` the moment a pod id exists.
- Put `timeout` on the pre-stop sync. Retry the stop, then read back
  `desiredStatus == EXITED`.
- Use two caps: one on the controller and one on the pod itself. Never
  describe a cap you haven't tested.
- Any urllib call to RunPod needs an explicit UA. Health-check self-stop with
  a real authenticated GET from the pod at bring-up.
- Log pod-side watchdogs to `/workspace`, because `/root` is wiped on stop
  and takes the evidence with it.
- Test offline with stubs: a deliberately broken step must stop the pod
  within seconds. Reproduce transfer failures as root on a filesystem that
  refuses chown. If the dev box has rsync or permissive ownership, a normal
  test passes anyway.

### Second session: dead worker, ~$1.50 idle (2026-09-28)

The pod stopped correctly this time, but a pod-side worker crashed and the
controller waited on it for about 25 minutes until the budget cap fired.
- **Every wait loop on pod-side work needs a liveness check.** Use a
  heartbeat file the worker touches each loop, plus `pgrep`. Worker gone or
  heartbeat stale with work pending: restart it once, then abandon the
  remaining items and move on.
- **Keep the status probe in a script on the pod** (`bash /root/pod/status.sh
  <batch>`) and don't build it from nested inline quoting sent over ssh.
  `'$1'` inside a `bash -c` string never expands, and a script can be
  unit-tested locally.
- **A pod-side self-stop can still be refused** (403, empty body) even with a
  proper User-Agent. Treat the host-side stop as the real guarantee.
- **Order phases so the new measurements run first.** Recovery or re-runs of
  earlier work go last, where the budget cap cuts them first. Skip anything
  known to be slow (SeedVR2 4K took ~40 min per 5 s clip) unless it is the thing
  being measured.

### Honour GPU restrictions on restart

"Start the existing stopped pod first" silently reuses the GPU it was created
with. When the user limits the GPU type ("PRO 6000 only"), check the old pod's
`gpuTypeId` against the allow-list before restarting it. If the type is missing
or not allowed, create a new pod and terminate the old EXITED one. REST `info`
sometimes omits the GPU type, so treat unknown as not allowed. Cover it with a
stub test that asserts no `start` call and no disallowed `create`.

## The container disk is rebuilt on every start

Everything outside `/workspace` is wiped on **stop**, not just terminate:
apt packages, nginx config, secrets, pip installs outside a volume venv. Keep
one idempotent bootstrap script (apt, config, secrets, service launch,
self-check) and run it on every start.

- **The base image has no `rsync`.** Transfers die with
  `rsync: command not found` / `code 12`. Use tar over ssh:
  `tar -C src -czf - . | ssh -p $P root@$IP "mkdir -p dst && tar -C dst -xzf -"`.
  A local mock/offline test won't catch this if the dev box has rsync.
- **`/workspace` ignores chmod**: a 600 file reads back 666. Secrets go to
  `/root/` (container disk), pushed fresh on each start.

## Disk quota: `df` lies

On RunPod's MFS-backed volumes, `df -h /workspace` reports the **shared
backing store** (e.g. `155T free`), not your volume quota. Sizing a download
off that number leads straight to:

```
RuntimeError: File reconstruction error: IO Error: Disk quota exceeded (os error 122)
```

**Use `du -sh /workspace` against the known quota instead.** And count the
venvs — two Python environments with CUDA wheels were 25 GB combined,
entirely absent from any model-size estimate.

### Resizing beats deleting

```bash
curl -X PATCH "https://rest.runpod.io/v1/networkvolumes/<id>" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" -d '{"size":200}'
```

Takes effect immediately on the running pod. `df` will not reflect it —
verify by completing the download that previously failed. Doubling a volume
is cheap next to deleting a model you spent an hour installing.

## Keep everything on the volume

Put ComfyUI, the venv, **and** the models under `/workspace`. Terminating
the pod then costs only volume storage, and redeploy is a ~3 minute reattach
with zero rebuild — verified: 182 GB of installed models came back intact.
Container disk is wiped on termination; never install there.

## Browser access

RunPod proxies HTTP ports at `https://<pod-id>-8188.proxy.runpod.net`.
That URL is **public**. Anyone who has it reaches your GPU. Put a login on it.

### Basic auth on the pod (preferred: no tunnel, works from a phone)

Run ComfyUI on `127.0.0.1:8189`; nginx on the exposed `8188` does
`auth_basic` and proxies to it, with websocket headers
(`proxy_http_version 1.1; Upgrade $http_upgrade; Connection "upgrade"`),
`client_max_body_size 2g`, and a long `proxy_read_timeout`. Two traps specific
to RunPod's image:

- **The image already runs its own nginx** (RunPod's service proxies), and its
  `nginx.conf` never includes `sites-enabled/`. Your site file is ignored,
  and `nginx -t` still passes because it never reads it. Symptom: port 8188
  returns `000`. Add `include /etc/nginx/sites-enabled/*;` inside `http {`
  (back up the original first), then `nginx -s reload`.
- **Workers run as `nobody`**, not `www-data`. A `.htpasswd` owned by the
  `www-data` group returns **500 for right and wrong passwords alike**.
  `chown root:$(id -gn nobody) /etc/nginx/.htpasswd && chmod 640`.

Verify from outside via the proxy URL, not localhost: no creds → 401, wrong
password → 401, right → 200, `/object_info/<YourNode>` → 200, an authed
websocket to `/ws` connects, and an unauthed one gets 401.

### Fallback: reverse-proxy through your own host

```
ssh -N -L 127.0.0.1:8189:127.0.0.1:8188 -p <ssh-port> root@<ip>
```

then point Caddy at `localhost:8189`. Two hard-won details:

- **Serve at root on its own port, never under a subpath.** ComfyUI loads
  assets from absolute paths and opens a WebSocket at `/ws`; a
  `handle_path /comfy/*` block breaks both. Symptom: logo renders, app never
  loads.
- **Disable HTTP/3.** Caddy advertises `Alt-Svc: h3` on UDP. If only TCP is
  open in the firewall, the browser loads the first page over TCP, upgrades
  to QUIC, and every later request is silently dropped — an infinite loading
  screen. `curl` never reproduces it because it does not negotiate HTTP/3 by
  default. Fix in Caddy global options:
  ```
  { servers { protocols h1 h2 } }
  ```

Verify with a real client, not just `curl`: check the JS bundle returns 200
*and* that `/ws` returns `101 Switching Protocols`.

## Cost discipline

Query actual uptime rather than estimating from wall-clock:

```graphql
query { pod(input:{podId:"<id>"}) { costPerHr runtime { uptimeInSeconds } } }
```

Running estimates drift high when a pod has been redeployed mid-session.
Report the API figure.

Idle billing, not rendering, is usually the biggest cost: in one session
only ~$0.97 of $6.13 was rendering, and the rest was setup, cold starts and a
pod idling while approvals timed out. Auto-stop when the queue empties (sync
results off the pod first if the volume has no S3 endpoint) and batch work
into one warm session.
