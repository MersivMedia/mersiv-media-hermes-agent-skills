#!/usr/bin/env python3
"""Turn the three perf batches into one markdown table set (local).

  perf_report.py <batch-A> <batch-B> <batch-C>

Reads each batch's sidecars (render + upscale). Everything printed is a
measured number from those files; nothing is estimated except the "per 5 s
clip" totals, which are plain sums of measured parts and say so.
"""
import json
import sys
from pathlib import Path

DATA = Path.home() / ".hermes/data/ref-character-replacement/batches"
REPLICATE = {"768p": 0.40, "2K": 0.65}


def load(b):
    rs, us = {}, {}
    for p in (DATA / b / "sidecars").glob("*.json"):
        d = json.loads(p.read_text())
        (rs if "params" in d else us)[p.stem] = d
    return rs, us


def peak(d):
    v = d.get("peak_vram_mib") or {}
    return max(v.values()) if v else None


def main():
    A, B, C = sys.argv[1:4]
    ra, ua = load(A); rb, ub = load(B); rc, uc = load(C)
    print(f"# Refswap perf session\n\nGPU: {next(iter(ra.values()), {}).get('gpu')}  "
          f"rate: ${next(iter(ra.values()), {}).get('gpu_rate_per_hr')}/hr\n")

    print("## Render (warm, 5 s clip, turbo)\n")
    print("| Job | Res | Steps | Sage | Exec s | s/step | Audio decode s | Cost | Peak VRAM MiB |")
    print("|---|---|---|---|---|---|---|---|---|")
    for tag, rs in (("A", ra), ("B", rb), ("C", rc)):
        for k in sorted(rs):
            d = rs[k]; p = d["params"]; t = d["timing"]
            print(f"| {tag}.{d['job']} | {p['w']}x{p['h']} | {p['steps']} | {d.get('sage')} | {t['exec_s']} | "
                  f"{t['median_step_s']} | {t.get('audio_decode_s')} | ${d['cost_usd']} | {peak(d)} |")
    first = min(ra.values(), key=lambda d: d["finished"]) if ra else None
    if first:
        print(f"\nFirst render of the session ({first['job']}) includes model load; "
              f"compare its exec time with the later ones before quoting a per-clip cost.\n")

    print("## Upscale (SeedVR2 7B sharp, same final size from each start)\n")
    print("| From | To | Factor | Exec s | Cost | Peak VRAM MiB | Layout |")
    print("|---|---|---|---|---|---|---|")
    for us in (ua, uc):
        for k in sorted(us):
            d = us[k]
            print(f"| {d['src_res']}p | {d['label']} ({d.get('target_wh')}) | {d['target_h']/d['src_res']:.1f}x | "
                  f"{d['exec_s']} | ${d['cost_usd']} | {peak(d)} | {d.get('layout')} |")

    print("\n## Per 5 s clip, measured parts summed\n")
    print("| Pipeline | Render | Upscale | Total | Replicate |")
    print("|---|---|---|---|---|")
    for res in (480, 768):
        rj = next((d for d in ra.values() if d["params"]["res"] == res and d["params"]["steps"] == 4), None)
        if not rj:
            continue
        print(f"| {res}p, no upscale | ${rj['cost_usd']} | - | ${rj['cost_usd']} | ${REPLICATE['768p']} (768p) |")
        for lab in ("2k", "4k"):
            u = ua.get(f"{rj['stem']}_{lab}")
            if u and u["status"] == "ok":
                tot = round(rj["cost_usd"] + u["cost_usd"], 3)
                rep = f"${REPLICATE['2K']} (2K)" if lab == "2k" else "n/a (no 4K)"
                print(f"| {res}p -> {lab} | ${rj['cost_usd']} | ${u['cost_usd']} | ${tot} | {rep} |")

    s3 = next((d for d in ra.values() if d["params"]["steps"] == 3), None)
    s4 = next((d for d in ra.values() if d["params"]["steps"] == 4 and d["params"]["res"] == 768), None)
    if s3 and s4:
        print(f"\n## 3 vs 4 turbo steps (768p)\n\n4 steps: {s4['timing']['exec_s']} s, "
              f"3 steps: {s3['timing']['exec_s']} s. Quality: compare "
              f"`{s4['stem']}` against `{s3['stem']}` frame by frame; not scored automatically.")
    sb = next(iter(rb.values()), None)
    if sb and s4:
        print(f"\n## SageAttention (768p, 4 steps)\n\noff: {s4['timing']['median_step_s']} s/step, "
              f"on: {sb['timing']['median_step_s']} s/step. Only valid if the render log confirmed sage loaded.")

    ren = sorted(rc.values(), key=lambda d: d["finished"])
    ups = list(uc.values())
    if len(ren) >= 2 and ups:
        serial_sum = sum(d["timing"]["exec_s"] for d in ren) + sum(u["exec_s"] for u in ups)
        t_start = min(d["finished"] for d in ren)
        print(f"\n## Shared-GPU lanes\n\nSum of individual exec times: {round(serial_sum)} s. "
              f"Wall time for the whole phase is in the batch log; if wall is close to the sum, "
              f"overlap bought nothing. Peak VRAM across both lanes: "
              f"{max([peak(d) or 0 for d in ren] + [peak(u) or 0 for u in ups])} MiB.")


if __name__ == "__main__":
    main()
