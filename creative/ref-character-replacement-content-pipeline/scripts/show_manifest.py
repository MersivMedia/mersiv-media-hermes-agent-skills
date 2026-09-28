#!/usr/bin/env python3
"""Print a batch manifest AS IT IS ON DISK (after any per-row edits).
batch_new.py prints its table before perf_session edits rows, which once made a
correct 480/768/3-step manifest read as "all 768p, no upscale".
  show_manifest.py <path/to/manifest.csv>"""
import csv
import sys

rows = list(csv.DictReader(open(sys.argv[1])))
print(f"FINAL {sys.argv[1]}")
print(f"{'job':<4} {'res':>4} {'steps':>5} {'turbo':>5} {'bg':>2} {'audio':<9} {'upscale':<10} seed")
for r in rows:
    print(f"{r['job']:<4} {r['res']:>4} {r.get('steps') or '-':>5} {r['turbo']:>5} {r['replace_bg']:>2} "
          f"{r['audio']:<9} {r.get('upscale') or '-':<10} {r['seed']}")
