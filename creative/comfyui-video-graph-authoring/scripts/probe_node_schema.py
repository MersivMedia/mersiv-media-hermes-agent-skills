#!/usr/bin/env python3
"""Probe a ComfyUI node's REAL contract before wiring it into a graph.

The recurring failure mode in ComfyUI graph authoring is wiring a plausible
value into a socket that wanted something else. Generic types (MODEL,
CONDITIONING, IMAGE, MASK) accept anything at validation time, so /prompt
returns 200 and the node dies at execution.

This prints types AND tooltips AND raw enum options. Use --raw for anything
you are about to wire: a pretty-printed summary shows a COMBO as the literal
string "COMBO" and hides the options array you actually need.

Usage:
    probe_node_schema.py --node WanSCAILToVideo --raw
    probe_node_schema.py --search scail
    probe_node_schema.py --loaders sam3.1_multiplex_fp16.safetensors
    probe_node_schema.py --folders
"""
import argparse
import json
import sys
import urllib.request


def fetch(host: str, path: str):
    with urllib.request.urlopen(f"{host.rstrip('/')}{path}", timeout=120) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def describe(info: dict, name: str, raw: bool) -> None:
    print(f"== {name}  |  category: {info.get('category')}")
    if info.get("description"):
        print(f"   {info['description'][:300]}")

    for section in ("required", "optional"):
        fields = (info.get("input") or {}).get(section) or {}
        if not fields:
            continue
        print(f"  [{section}]")
        for key, spec in fields.items():
            tooltip = ""
            default = ""
            type_desc = spec

            if isinstance(spec, list) and spec:
                type_desc = spec[0]
                if len(spec) > 1 and isinstance(spec[1], dict):
                    meta = spec[1]
                    if meta.get("tooltip"):
                        tooltip = meta["tooltip"]
                    if "default" in meta:
                        default = f" (default={meta['default']})"
                    # enum options may live here rather than in type_desc
                    if isinstance(meta.get("options"), list):
                        type_desc = meta["options"]

            # A list of strings IS the enum; show it rather than "COMBO".
            if isinstance(type_desc, list):
                shown = ", ".join(str(v) for v in type_desc[:12])
                if len(type_desc) > 12:
                    shown += f", ... (+{len(type_desc) - 12})"
                shown = f"[{shown}]"
            else:
                shown = str(type_desc)

            print(f"    {key:28s} {shown[:90]}{default}")
            if tooltip:
                # Tooltips carry the CONTRACT the type cannot express.
                print(f"      -> {tooltip[:220]}")

    outs = info.get("output") or []
    names = info.get("output_name") or []
    print(f"  [output] {list(zip(names, outs)) if names else outs}")

    if raw:
        print("  [raw]")
        print(json.dumps(info.get("input"), indent=2)[:6000])
    print()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="http://127.0.0.1:8188")
    ap.add_argument("--node", action="append", default=[],
                    help="exact node class name; repeatable")
    ap.add_argument("--search", help="substring match across node class names")
    ap.add_argument("--loaders", metavar="FILENAME",
                    help="find which loader node exposes this model file")
    ap.add_argument("--folders", action="store_true",
                    help="list model folders ComfyUI actually scans")
    ap.add_argument("--raw", action="store_true",
                    help="dump raw input JSON (needed to see enum options)")
    a = ap.parse_args()

    if a.folders:
        print(json.dumps(fetch(a.host, "/models"), indent=2))
        return 0

    oi = fetch(a.host, "/object_info")

    if a.search:
        needle = a.search.lower()
        hits = sorted(k for k in oi if needle in k.lower())
        if not hits:
            print(f"no node matching {a.search!r}")
            return 1
        for k in hits:
            print(f"  {k:40s} {oi[k].get('category')}")
        return 0

    if a.loaders:
        # A model file in an unscanned folder appears in NO loader combo.
        # Empty result here means the file is in the wrong directory.
        found = False
        for node, info in sorted(oi.items()):
            for section in ("required", "optional"):
                for key, spec in ((info.get("input") or {}).get(section) or {}).items():
                    opts = spec[0] if isinstance(spec, list) and spec else None
                    if isinstance(opts, list) and a.loaders in opts:
                        print(f"  {node}.{key}")
                        found = True
        if not found:
            print(f"NOT EXPOSED BY ANY LOADER: {a.loaders}")
            print("  -> wrong model folder, or server needs a restart to rescan")
            return 1
        return 0

    if not a.node:
        ap.error("pass --node, --search, --loaders, or --folders")

    rc = 0
    for name in a.node:
        if name not in oi:
            print(f"!! node not registered: {name}")
            rc = 1
            continue
        describe(oi[name], name, a.raw)
    return rc


if __name__ == "__main__":
    sys.exit(main())
