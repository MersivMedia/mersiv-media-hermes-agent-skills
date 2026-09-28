#!/usr/bin/env python3
"""Retry a single failed character variant by name.

USAGE:
  set -a; source ~/.hermes/.env; set +a
  python3 scripts/retry_character_variant.py 02_wide_brim_three_quarter

Use when generate_character_options.py reports a single ReadTimeout failure
from the gpt-image-2 provider. Retrying just the one variant beats re-running
the full 6-batch.
"""
import os, sys, json, time, urllib.request
from pathlib import Path

# Import VARIANTS + BASE + build_prompt from the sibling script
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from generate_character_options import VARIANTS, build_prompt, submit, poll, download, OUT_DIR  # noqa: E402

TOKEN = os.environ["REPLICATE_API_TOKEN"]

if len(sys.argv) != 2:
    print(f"usage: {sys.argv[0]} <variant_name>")
    print("  variants:", [v["name"] for v in VARIANTS])
    sys.exit(2)

target = sys.argv[1]
v = next((x for x in VARIANTS if x["name"] == target), None)
if not v:
    print(f"unknown variant: {target}")
    print("available:", [x["name"] for x in VARIANTS])
    sys.exit(2)

prompt = build_prompt(v["tag"])
pid = submit(prompt)
print(f"submitted: {pid}", flush=True)
d = poll(pid, time.time() + 480)
if d.get("status") != "succeeded":
    print(f"FAILED: {d.get('error')}")
    sys.exit(1)
url = d["output"] if isinstance(d["output"], str) else d["output"][0]
dest = OUT_DIR / f"{v['name']}.png"
download(url, dest)
print(f"saved: {dest}")
