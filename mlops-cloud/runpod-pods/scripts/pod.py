#!/usr/bin/env python3
"""
RunPod pod + network-volume management.

Run from `terminal` (env is not inherited by execute_code):
    set -a; . ~/.hermes/.env; set +a
    python3 pod.py balance
    python3 pod.py gpus
    python3 pod.py volume-create --name models --size 50 --dc EU-RO-1
    python3 pod.py create --gpu "NVIDIA A40" --volume <id> --ports "7860/http,22/tcp"
    python3 pod.py wait <pod-id>
    python3 pod.py url <pod-id> 7860
    python3 pod.py terminate <pod-id>

REST  https://rest.runpod.io/v1      pods + volumes   (Bearer header)
GQL   https://api.runpod.io/graphql  pricing + stock  (key in query string)
"""
import argparse
import json
import os
import subprocess
import sys
import time

REST = "https://rest.runpod.io/v1"
GQL = "https://api.runpod.io/graphql"


def key() -> str:
    k = os.environ.get("RUNPOD_API_KEY")
    if not k:
        sys.exit("RUNPOD_API_KEY not set.\n"
                 "  set -a; . ~/.hermes/.env; set +a")
    return k


def _curl(args: list[str]) -> str:
    return subprocess.run(["curl", "-s", "--max-time", "90"] + args,
                          capture_output=True, text=True, check=True).stdout


def rest(path: str, method: str = "GET", body: dict | None = None):
    args = ["-X", method, "-H", f"Authorization: Bearer {key()}",
            "-H", "Content-Type: application/json"]
    if body is not None:
        args += ["-d", json.dumps(body)]
    args.append(f"{REST}{path}")
    out = _curl(args)
    if not out.strip():
        return {}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        sys.exit(f"Non-JSON from {path}:\n{out[:400]}")


def gql(query: str) -> dict:
    out = _curl(["-X", "POST", f"{GQL}?api_key={key()}",
                 "-H", "Content-Type: application/json",
                 "-d", json.dumps({"query": query})])
    d = json.loads(out)
    if "errors" in d:
        sys.exit("GraphQL error: " + json.dumps(d["errors"])[:300])
    return d["data"]


# ---------------------------------------------------------------- commands

def cmd_balance(a):
    d = gql("query { myself { email clientBalance currentSpendPerHr } }")["myself"]
    bal = d.get("clientBalance") or 0
    print(f"account   : {d.get('email')}")
    print(f"balance   : ${bal:.2f}")
    print(f"spend/hr  : ${d.get('currentSpendPerHr') or 0:.3f}")
    if bal <= 0:
        print("\n  WARNING: $0 balance — pod creation will fail.")
        print("  Add credit at runpod.io -> Billing")


def cmd_gpus(a):
    d = gql("""query { gpuTypes { id displayName memoryInGb communityCloud
               lowestPrice(input:{gpuCount:1}) { uninterruptablePrice stockStatus } } }""")
    rows = []
    for g in d["gpuTypes"]:
        mem = g.get("memoryInGb") or 0
        lp = g.get("lowestPrice") or {}
        price = lp.get("uninterruptablePrice")
        if mem < a.min_vram or not price:
            continue
        rows.append((price, mem, g["displayName"], lp.get("stockStatus"), g["id"]))
    rows.sort()
    print(f"{'$/hr':>7} {'VRAM':>6}  {'GPU':<26} stock")
    print("-" * 60)
    for price, mem, name, stock, gid in rows[:a.limit]:
        print(f"  {price:>5.2f} {mem:>5}G  {name:<26} {stock or '?'}")


def cmd_datacenters(a):
    d = gql("query { dataCenters { id location storageSupport } }")
    dcs = [x for x in d["dataCenters"] if x.get("storageSupport")]
    print(f"{len(dcs)} datacenters support network volumes:")
    for x in dcs:
        print(f"   {x['id']:<14} {x.get('location','')}")


def cmd_volumes(a):
    vols = rest("/networkvolumes")
    if not vols:
        print("no network volumes")
        return
    for v in vols:
        size = v.get("size", 0)
        print(f"  {v.get('id'):<24} {v.get('name'):<18} {size:>4} GB  "
              f"{v.get('dataCenterId')}  ~${size*0.07:.2f}/mo")


def cmd_volume_create(a):
    v = rest("/networkvolumes", "POST",
             {"name": a.name, "size": a.size, "dataCenterId": a.dc})
    if "id" not in v:
        sys.exit(f"create failed: {json.dumps(v)[:300]}")
    print(f"created volume {v['id']}  {a.size} GB in {a.dc}")
    print(f"  ongoing cost ~${a.size*0.07:.2f}/month until deleted")
    print(f"  mounts at /workspace")


def cmd_volume_delete(a):
    rest(f"/networkvolumes/{a.volume_id}", "DELETE")
    print(f"deleted volume {a.volume_id}")


def cmd_create(a):
    bal = (gql("query { myself { clientBalance } }")["myself"].get("clientBalance") or 0)
    if bal <= 0:
        sys.exit("balance is $0.00 — add credit first (runpod.io -> Billing)")

    # SSH keys ONLY land at creation time. Registering on the account or
    # doing stop/start will not inject them into an existing container.
    keypath = os.path.expanduser("~/.ssh/id_ed25519")
    if not os.path.exists(keypath + ".pub"):
        os.makedirs(os.path.dirname(keypath), exist_ok=True)
        subprocess.run(["ssh-keygen", "-t", "ed25519", "-N", "", "-q",
                        "-C", "hermes-runpod", "-f", keypath], check=True)
        print("generated ~/.ssh/id_ed25519")
    pubkey = open(keypath + ".pub").read().strip()

    body = {
        "name": a.name,
        "imageName": a.image,
        "containerDiskInGb": a.disk,
        "ports": a.ports.split(","),
        "env": {"PUBLIC_KEY": pubkey},
    }
    if a.cpu:
        # CPU pod: e.g. --cpu cpu3c-2-4 (flavor cpu3c, 2 vCPU, 4 GB). ~$0.06/hr.
        # Mounts network volumes like a GPU pod; use for setup / copies.
        flavor, vcpu = a.cpu.split("-")[0], int(a.cpu.split("-")[1])
        body.update({"computeType": "CPU", "cpuFlavorIds": [flavor], "vcpuCount": vcpu})
    else:
        body.update({"gpuTypeIds": [a.gpu], "gpuCount": a.gpu_count})
    if a.volume:
        body["networkVolumeId"] = a.volume
    if a.dc:
        body["dataCenterIds"] = [a.dc]

    p = rest("/pods", "POST", body)
    if "id" not in p:
        sys.exit(f"create failed: {json.dumps(p)[:400]}")
    if a.json:
        print(json.dumps(p))
    else:
        rate = p.get("costPerHr") or 0
        secure = (p.get("machine") or {}).get("secureCloud")
        print(f"created pod {p['id']}  ({a.gpu or a.cpu})")
        print(f"  rate      : ${rate:.2f}/hr  "
              f"({'SECURE' if secure else 'community'} cloud)")
        print(f"  ssh key   : injected at creation")
        print(f"  wait for it:  python3 pod.py wait {p['id']}")
        print(f"  TERMINATE when done — idle pods bill at the full rate")


def cmd_list(a):
    pods = rest("/pods")
    if not pods:
        print("no pods")
        return
    for p in pods:
        print(f"  {p.get('id'):<20} {p.get('name','?'):<16} "
              f"{p.get('desiredStatus','?'):<10} {p.get('machine',{}).get('gpuTypeId','')}")


def cmd_wait(a):
    print(f"waiting for {a.pod_id} ", end="", flush=True)
    for _ in range(a.timeout // 5):
        p = rest(f"/pods/{a.pod_id}")
        if p.get("desiredStatus") == "RUNNING" and p.get("publicIp"):
            print(" RUNNING")
            print(f"  ip   : {p['publicIp']}")
            for pm in p.get("portMappings") or []:
                print(f"  port : {pm}")
            return
        print(".", end="", flush=True)
        time.sleep(5)
    sys.exit("\ntimed out waiting for pod")


def cmd_ssh(a):
    p = rest(f"/pods/{a.pod_id}")
    ip = p.get("publicIp")
    pm = p.get("portMappings") or {}
    port = pm.get("22") if isinstance(pm, dict) else None
    if not ip or not port:
        sys.exit("pod has no public SSH yet — run `wait` first")
    cmd = f"root@{ip} -p {port} -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no"
    print(cmd if a.raw else f"ssh {cmd}")


def cmd_url(a):
    print(f"https://{a.pod_id}-{a.port}.proxy.runpod.net")


def cmd_start(a):
    """Resume a STOPPED pod. Same pod id, so the proxy URL and injected SSH key
    survive. Fails if the host no longer has a free GPU of that type; the
    caller should then create a new pod on the same network volume."""
    p = rest(f"/pods/{a.pod_id}/start", "POST")
    if isinstance(p, dict) and (p.get("error") or p.get("errors")):
        sys.exit(f"start failed: {json.dumps(p)[:400]}")
    print(f"start requested for {a.pod_id}; run `wait` next")


def cmd_info(a):
    """Raw pod JSON (status, GPU, costPerHr, ports) for scripts."""
    print(json.dumps(rest(f"/pods/{a.pod_id}")))


def cmd_stop(a):
    rest(f"/pods/{a.pod_id}/stop", "POST")
    print(f"stopped {a.pod_id} — GPU released and GPU billing halted")
    print("  /workspace kept (volume disk still billed); container disk is cleared")


def cmd_terminate(a):
    rest(f"/pods/{a.pod_id}", "DELETE")
    print(f"terminated {a.pod_id} — billing stopped")
    print("  anything outside /workspace is gone")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("balance").set_defaults(fn=cmd_balance)

    g = sub.add_parser("gpus"); g.set_defaults(fn=cmd_gpus)
    g.add_argument("--min-vram", type=int, default=16)
    g.add_argument("--limit", type=int, default=15)

    sub.add_parser("datacenters").set_defaults(fn=cmd_datacenters)
    sub.add_parser("volumes").set_defaults(fn=cmd_volumes)

    vc = sub.add_parser("volume-create"); vc.set_defaults(fn=cmd_volume_create)
    vc.add_argument("--name", required=True)
    vc.add_argument("--size", type=int, default=50, help="GB")
    vc.add_argument("--dc", required=True, help="e.g. EU-RO-1")

    vd = sub.add_parser("volume-delete"); vd.set_defaults(fn=cmd_volume_delete)
    vd.add_argument("volume_id")

    c = sub.add_parser("create"); c.set_defaults(fn=cmd_create)
    g = c.add_mutually_exclusive_group(required=True)
    g.add_argument("--gpu", help='e.g. "NVIDIA A40"')
    g.add_argument("--cpu", help='CPU pod instance, e.g. cpu3c-2-4 (2 vCPU/4 GB, ~$0.06/hr)')
    c.add_argument("--name", default="hermes-pod")
    c.add_argument("--image", default="runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04")
    c.add_argument("--disk", type=int, default=30, help="container disk GB")
    c.add_argument("--gpu-count", type=int, default=1)
    c.add_argument("--ports", default="7860/http,22/tcp")
    c.add_argument("--volume", help="network volume id")
    c.add_argument("--dc", help="datacenter id (must match volume)")
    c.add_argument("--json", action="store_true")

    sub.add_parser("list").set_defaults(fn=cmd_list)

    w = sub.add_parser("wait"); w.set_defaults(fn=cmd_wait)
    w.add_argument("pod_id"); w.add_argument("--timeout", type=int, default=600)

    s = sub.add_parser("ssh"); s.set_defaults(fn=cmd_ssh)
    s.add_argument("pod_id"); s.add_argument("--raw", action="store_true")

    u = sub.add_parser("url"); u.set_defaults(fn=cmd_url)
    u.add_argument("pod_id"); u.add_argument("port", type=int)

    sa = sub.add_parser("start"); sa.set_defaults(fn=cmd_start); sa.add_argument("pod_id")
    inf = sub.add_parser("info"); inf.set_defaults(fn=cmd_info); inf.add_argument("pod_id")
    st = sub.add_parser("stop"); st.set_defaults(fn=cmd_stop); st.add_argument("pod_id")
    t = sub.add_parser("terminate"); t.set_defaults(fn=cmd_terminate); t.add_argument("pod_id")

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
