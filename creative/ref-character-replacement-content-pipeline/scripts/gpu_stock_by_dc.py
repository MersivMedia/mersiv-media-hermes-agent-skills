#!/usr/bin/env python3
"""RunPod GPU stock + price for ONE datacenter (volumes pin pods to their DC).

  set -a; . ~/.hermes/.env; set +a
  python3 scripts/gpu_stock_by_dc.py                      # EU-NL-1, >=48 GB
  python3 scripts/gpu_stock_by_dc.py --dc EU-RO-1 --min-vram 80
  python3 scripts/gpu_stock_by_dc.py --gpu "NVIDIA RTX PRO 6000 Blackwell Server Edition" --all-dcs

stockStatus null = none in that DC. The global list shows stock that may not
exist in your volume's DC, so always ask per DC.
"""
import argparse
import json
import os
import subprocess

K = os.environ["RUNPOD_API_KEY"]


def gql(q):
    r = subprocess.run(["curl", "-s", "-H", "Content-Type: application/json",
                        "-H", f"Authorization: Bearer {K}", "-d", json.dumps({"query": q}),
                        "https://api.runpod.io/graphql"], capture_output=True, text=True).stdout
    d = json.loads(r)
    if "errors" in d:
        raise SystemExit(d["errors"])
    return d["data"]


def one_dc(dc, min_vram):
    q = ("query { gpuTypes { id memoryInGb securePrice lowestPrice(input:{gpuCount:1, "
         f'dataCenterId:"{dc}", secureCloud:true}}) {{ uninterruptablePrice stockStatus }} }} }}')
    rows = []
    for g in gql(q)["gpuTypes"]:
        lp = g.get("lowestPrice") or {}
        if (g.get("memoryInGb") or 0) >= min_vram and lp.get("stockStatus"):
            rows.append((g["memoryInGb"], g["id"], lp.get("uninterruptablePrice"), lp["stockStatus"]))
    print(f"{dc}: in stock, >= {min_vram} GB")
    for m, i, p, s in sorted(rows, key=lambda x: (-x[0], x[1])):
        print(f"  {m:>4} GB  ${p}/hr  {s:<6} {i}")
    if not rows:
        print("  (nothing)")


def all_dcs(gpu):
    dcs = [d["id"] for d in gql("query { dataCenters { id } }")["dataCenters"]]
    hits = []
    for dc in dcs:
        q = (f'query {{ gpuTypes(input:{{id:"{gpu}"}}) {{ lowestPrice(input:{{gpuCount:1, '
             f'dataCenterId:"{dc}", secureCloud:true}}) {{ uninterruptablePrice stockStatus }} }} }}')
        try:
            lp = gql(q)["gpuTypes"][0]["lowestPrice"] or {}
        except Exception:
            continue
        if lp.get("stockStatus"):
            hits.append(f"{dc}={lp['stockStatus']}(${lp.get('uninterruptablePrice')})")
    print(f"{gpu}: {', '.join(hits) or 'none'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dc", default="EU-NL-1")
    ap.add_argument("--min-vram", type=int, default=48)
    ap.add_argument("--gpu")
    ap.add_argument("--all-dcs", action="store_true")
    a = ap.parse_args()
    all_dcs(a.gpu) if a.all_dcs and a.gpu else one_dc(a.dc, a.min_vram)
