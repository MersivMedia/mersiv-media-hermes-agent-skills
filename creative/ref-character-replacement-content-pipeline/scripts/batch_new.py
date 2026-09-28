#!/usr/bin/env python3
"""Create a batch folder + manifest (local). Nothing is spent here.

  batch_new.py <batch-slug> --sources a.mp4 b.mp4 --refs x.png y.png \\
      [--pairs 1:1,1:2,2:1] [--replace-bg 0] [--audio auto] [--res 768] \\
      [--turbo 1] [--duration 0] [--upscale ""] [--instruction "..."]

--pairs: source#:ref# (1-based). Default: every source x every ref.
Per-row edits: open manifest.csv afterwards; it's the source of truth.
Prints the pairing table to show the user BEFORE any GPU spend.
"""
import argparse
import csv
import datetime as dt
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path.home() / ".hermes/data/ref-character-replacement/batches"
FIELDS = ["job", "source", "reference", "replace_bg", "audio", "duration", "turbo", "steps",
          "res", "upscale", "seed", "instruction"]


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "x"


def has_audio(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                          "stream=index", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout
    return bool(out.strip())


def duration(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batch")
    ap.add_argument("--sources", nargs="+", required=True)
    ap.add_argument("--refs", nargs="+", required=True)
    ap.add_argument("--pairs", default="")
    ap.add_argument("--replace-bg", default="0")
    ap.add_argument("--audio", default="auto", choices=["auto", "source", "generated", "off"])
    ap.add_argument("--res", default="768")
    ap.add_argument("--turbo", default="1")
    ap.add_argument("--steps", default="")
    ap.add_argument("--duration", type=float, default=0, help="0 = min(15, source length)")
    ap.add_argument("--upscale", default="", help='e.g. "1440;2160"')
    ap.add_argument("--seed", default="4242")
    ap.add_argument("--instruction", default="")
    a = ap.parse_args()

    name = a.batch if re.match(r"\d{4}-\d{2}-\d{2}_", a.batch) else f"{dt.date.today()}_{slugify(a.batch)}"
    B = ROOT / name
    if (B / "manifest.csv").exists():
        raise SystemExit(f"{B} already has a manifest; edit it or pick a new name")
    (B / "sources").mkdir(parents=True, exist_ok=True)
    (B / "refs").mkdir(exist_ok=True)

    def stage(paths, sub, prefix):
        out, seen = [], set()
        for p in map(Path, paths):
            if not p.is_file():
                raise SystemExit(f"not a file: {p}")
            base = f"{prefix}_{slugify(re.sub(r'^(src|ref)_', '', p.stem))}"
            n, k = base, 2
            while n in seen:
                n, k = f"{base}-{k}", k + 1
            seen.add(n)
            dst = B / sub / f"{n}{p.suffix.lower()}"
            shutil.copyfile(p, dst)
            out.append(dst)
        return out

    srcs = stage(a.sources, "sources", "src")
    refs = stage(a.refs, "refs", "ref")
    if a.pairs:
        pairs = [tuple(int(x) for x in pr.split(":")) for pr in a.pairs.split(",")]
    else:
        pairs = [(i + 1, j + 1) for i in range(len(srcs)) for j in range(len(refs))]

    rows = []
    for k, (si, ri) in enumerate(pairs, 1):
        s, r = srcs[si - 1], refs[ri - 1]
        audio = a.audio if a.audio != "auto" else ("source" if has_audio(s) else "generated")
        d = min(15.0, duration(s)) if not a.duration else min(a.duration, duration(s), 15.0)
        rows.append({"job": f"J{k:02d}", "source": s.name, "reference": r.name,
                     "replace_bg": a.replace_bg, "audio": audio, "duration": f"{d:.2f}",
                     "turbo": a.turbo, "steps": a.steps, "res": a.res, "upscale": a.upscale,
                     "seed": a.seed, "instruction": a.instruction})
    with open(B / "manifest.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader(); w.writerows(rows)

    print(f"batch: {B}")
    print(f"{'job':<4} {'source':<28} {'reference':<26} {'bg':<3} {'audio':<9} {'dur':>5} {'res':>4} up")
    for r in rows:
        print(f"{r['job']:<4} {r['source']:<28} {r['reference']:<26} {r['replace_bg']:<3} "
              f"{r['audio']:<9} {r['duration']:>5} {r['res']:>4} {r['upscale'] or '-'}")
    json.dump({"batch": name, "jobs": len(rows)}, open(B / "batch.json", "w"))


if __name__ == "__main__":
    main()
