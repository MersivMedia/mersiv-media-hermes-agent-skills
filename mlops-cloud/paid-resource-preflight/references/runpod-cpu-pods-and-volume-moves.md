# RunPod: CPU pods for setup, moving a volume, stuck placements

Learned Sept 2026 while trying to leave EU-NL-1 after a bad RTX PRO 6000 host.

## Setup, inventory and copying don't need a GPU

The user's correction: "can we do that using a cpu or something cheaper for
setup and then we can use a gpu later for testing". Default to this. Installs,
downloads, volume inventory and cross-DC copies all run on CPU pods. Rent the
GPU only for the render or test itself.

CPU pods can attach a network volume. REST `POST /v1/pods` fields, read from
`https://rest.runpod.io/v1/openapi.json` (`PodCreateInput`):

```json
{"computeType": "CPU", "cpuFlavorIds": ["cpu3c", "cpu3g"], "vcpuCount": 4,
 "networkVolumeId": "<id>", "dataCenterIds": ["US-NE-1"],
 "containerDiskInGb": 20, "cloudType": "SECURE"}
```

Flavors (GraphQL `cpuFlavors { id groupId displayName minVcpu maxVcpu ramMultiplier diskLimitPerVcpu }`):
`cpu3c`/`cpu5c` compute (2 GB RAM per vCPU), `cpu3g`/`cpu5g` general (4 GB per vCPU),
`cpu3m`/`cpu5m` memory (8 GB per vCPU), 2–32 vCPU. `CpuFlavor` has NO `securePrice`
field. Price and stock come from `specifics`, and `instanceId` is `<flavor>-<vcpu>-<ramGB>`:

```graphql
query { cpuFlavors { id
  specifics(input:{dataCenterId:"US-NE-1", instanceId:"cpu3c-4-8"}) { stockStatus securePrice } } }
```

Live read (2026-09-29, same in EU-NL-1 and US-NE-1): cpu3c-2-4 $0.06/hr,
cpu3c-4-8 $0.12, cpu3g-4-16 $0.16, all `High` stock. cpu5* showed `None`.
Report the rate read back from the created pod, not this table.

**Verified 2026-09-29:** a cpu3c-2-4 pod on `runpod/base:0.6.2-cpu` mounted the
existing GPU-created EU-NL-1 volume and ran a full inventory in ~3 min
(under a cent). `scripts/pod.py create --cpu <instanceId>` in `runpod-pods`
builds the body above. Still unverified: whether a venv copied from a GPU
image imports elsewhere. Venvs symlink the image's Python, so verify on a CPU
pod running the **same image** as the GPU pod.

Create-time gotchas (all hit on day one):
- **Small flavors cap the container disk at 20 GB.** A larger disk fails
  with `Container Disk must be less than or equal to 20`. Always use 20.
- **`High` stock still fails** with `There are no longer any instances
  available`. The same DC gave a pod on the first try in the morning and
  refused every flavor that afternoon. Try several flavors in order, then
  poll every 60 s up to a deadline. Failed creates cost nothing.
- **Capture `2>&1`.** RunPod's error goes to stderr, and a stdout-only
  capture logged a blank failure line.

## "Move our volume" = copy to a new one

There is no migrate or move endpoint for network volumes. Docs describe only a
pod-to-pod copy into a new volume in the target DC. Options:

- **Copy known-good dirs** (ComfyUI at its pinned commit, the working venv,
  the models in use) between two CPU pods. With CPU pods this cheap, this beats
  re-downloading: it keeps the exact tested versions. Skip dead weight (broken
  venvs, rejected model files).
- **Rebuild from scratch.** Proves reproducibility, but risks version drift.

Either way: inventory first and send the user a keep/drop list, size the new
volume from it (≈$0.07/GB/mo), keep the old volume until a real job has run
from the new one, then ask before deleting.

Inventory worth taking (read-only, one script over ssh): `du` per top-level
dir and per model subdir, ComfyUI `git log -1`, `custom_nodes/`, `pip freeze`
per venv (flag broken ones), model files >1 GB by size and date, and a
search for secret files (`.hf_token`, `*.env`). In practice the working set
was 92 of 250 GB. Present the older stacks with their $/mo so the user can
choose. They picked "H3 only". Dropped weights re-download from HF in
minutes, so dropping is reversible.

Copy mechanics: `rsync -a --partial --no-owner --no-group` over ssh
(MooseFS refuses root chown), 2–3 parallel streams with the largest files
split out, then a second pass filtered to real differences
(`grep -E '^(<|c[fL])'`, not directory mtime lines) that must be empty.
Verify on the target: every `.safetensors` header length ≤ file size (catches
truncation), the venv imports torch, and ComfyUI `--cpu` boots with the
required nodes. Terminate both pods on every exit path.

**Choosing the target DC:** query `dataCenters { id storageSupport }` and scan
per-DC stock for every GPU you'd use. Pick one with both the preferred card and
a fallback. A DC with only the preferred card loses the fallback. S3 API
endpoints exist only in some DCs (`https://s3api-<dc-lowercase>.runpod.io/`):
EU-CZ-1, EU-RO-1, EUR-IS-1, EUR-NO-1, US-CA-2, US-GA-2, US-IL-1, US-KS-2, US-MD-1,
US-MO-1, US-MO-2, US-NC-1, US-NC-2, US-NE-1, US-WA-1. EU-NL-1 has none, so a
volume there can only be inspected from a pod. S3 access is a real reason to
prefer a DC.

## Stuck placement: the pod is "RUNNING" but never boots

Symptom: `desiredStatus: RUNNING`, `runtime: null`, no `publicIp` or ports, for
minutes. Healthy pods reach an IP in 15–30 s. GraphQL
`pod { machineId machine { gpuDisplayName } runtime { uptimeInSeconds } }` shows
the host.

- **Terminate, don't stop.** Restarting a stopped pod lands on the same machine.
- RunPod placed a FRESH pod on the same stuck machine too (`machineId`
  repeated), because only one host in that DC had the card free. When a second
  placement lands on the same `machineId` and stalls, stop retrying. Offer
  another GPU in the same DC, another DC, or a support ticket (pod IDs, machine
  ID, timestamps).
- Automation: bound the wait (~8 min), terminate, verify the pod is gone, clear
  the saved pod ID, and cap retries (3). Each stalled attempt still bills
  ~$0.2–0.3 on a $2/hr card.
