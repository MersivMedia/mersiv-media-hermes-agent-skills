#!/usr/bin/env python3
"""Per-datacenter GPU stock + price probe (RunPod).

WHY THIS EXISTS
---------------
The global GPU list aggregates across ALL datacenters and routinely reports
`High` stock for a card available in ZERO volume-capable regions. Network
volumes are datacenter-locked permanently, so creating one in a region without
GPU stock strands it: you pay ~$0.07/GB/month for storage no pod can attach to.

Measured failure this was written from: global list showed A40 48GB at `High`
(the only non-Low card anywhere); a sweep of all 13 volume-capable regions
found A40 in none of them, and the region picked from the global reading
(US-CA-2) had zero GPUs of any size.

Run this BEFORE creating any network volume.

    set -a; . ~/.hermes/.env; set +a
    python3 scripts/dc_stock.py                  # all storage DCs, >=24GB
    python3 scripts/dc_stock.py --min-vram 48
    python3 scripts/dc_stock.py --dc US-KS-2
    python3 scripts/dc_stock.py --json

Companion doc: references/rented-gpu-operations.md sections 4.1-4.3.

NOTE: urllib gets HTTP 403 from api.runpod.io (user-agent filtering) even with
a valid key. This uses curl via subprocess for that reason. Do not "simplify"
it back to urllib.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

# Regions that support network volumes. Re-check if a create call rejects one.
STORAGE_DCS = [
    "US-CA-2", "US-KS-2", "US-TX-3", "US-GA-1", "US-IL-1",
    "CA-MTL-3", "CA-MTL-4",
    "EU-RO-1", "EU-NL-1", "EU-FR-1", "EUR-IS-1", "EUR-NO-1",
    "AP-JP-1",
]

GQL = "https://api.runpod.io/graphql"


def query_dc(api_key: str, dc: str) -> list[tuple[float, int, str, str]]:
    """Return sorted [(price, vram_gb, gpu_name, stock_status)] for one DC."""
    q = (
        "{ gpuTypes { displayName memoryInGb "
        f'lowestPrice(input:{{gpuCount:1,dataCenterId:"{dc}"}})'
        "{uninterruptablePrice stockStatus} } }"
    )
    try:
        proc = subprocess.run(
            ["curl", "-s", "-X", "POST", f"{GQL}?api_key={api_key}",
             "-H", "Content-Type: application/json",
             "-d", json.dumps({"query": q})],
            capture_output=True, text=True, timeout=60,
        )
        data = json.loads(proc.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError):
        return []

    if not data.get("data"):
        return []

    rows = []
    for g in data["data"].get("gpuTypes") or []:
        lp = g.get("lowestPrice") or {}
        price, stock = lp.get("uninterruptablePrice"), lp.get("stockStatus")
        if price and stock:
            rows.append((price, g.get("memoryInGb") or 0, g["displayName"], stock))
    return sorted(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dc", help="single datacenter (default: all storage DCs)")
    ap.add_argument("--min-vram", type=int, default=24)
    ap.add_argument("--top", type=int, default=5, help="rows shown per DC")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    key = os.environ.get("RUNPOD_API_KEY")
    if not key:
        print("RUNPOD_API_KEY unset. Run:\n"
              "  set -a; . ~/.hermes/.env; set +a",
              file=sys.stderr)
        return 1

    dcs = [args.dc] if args.dc else STORAGE_DCS
    result = {dc: [r for r in query_dc(key, dc) if r[1] >= args.min_vram]
              for dc in dcs}

    if args.json:
        print(json.dumps(
            {dc: [{"price": p, "vram": v, "gpu": n, "stock": s}
                  for p, v, n, s in rows]
             for dc, rows in result.items()}, indent=2))
        return 0

    print(f"{'DC':10} {'$/hr':>6} {'VRAM':>5}  {'GPU':<24} stock"
          f"   [>={args.min_vram}GB, volume-capable DCs]")
    print("-" * 70)

    empty = []
    for dc, rows in result.items():
        if not rows:
            empty.append(dc)
            continue
        for p, v, n, s in rows[:args.top]:
            print(f"{dc:10} {p:6.2f} {v:4}G  {n:<24} {s}")
        print()

    if empty:
        print("NO STOCK — never create a volume in these: " + ", ".join(empty))

    print("\nA volume is locked to its datacenter permanently. Create one ONLY")
    print("in a region listed above with stock. `Low` is normal and workable;")
    print("absent is disqualifying. If the user will screen-record the UI,")
    print("weight proximity to them next (see rented-gpu-operations.md 4.2).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
