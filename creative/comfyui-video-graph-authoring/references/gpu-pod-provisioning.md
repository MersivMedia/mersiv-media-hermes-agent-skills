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

RunPod proxies HTTP ports at `https://<pod-id>-8188.proxy.runpod.net`,
which requires a RunPod session in the browser.

If that fails, reverse-proxy through your own host instead:

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
