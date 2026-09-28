#!/usr/bin/env python3
"""Pull a batch's results off the pod, build side-by-sides, file on Drive.

  batch_sync.py <batch-name> [--no-drive] [--no-compare]

Drive layout: Ref Character Replacement/<batch>/{inputs,renders,upscaled,compare}
plus manifest.csv, results.csv, upscale_results.csv and a Google Sheet
"<batch> results" (one row per job, file links). Re-runnable: already-uploaded
files are skipped by name.
"""
import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

SK = Path(__file__).resolve().parent.parent
DATA = Path.home() / ".hermes/data/ref-character-replacement"
GAPI = [sys.executable, str(Path.home() / ".hermes/skills/productivity/google-workspace/scripts/google_api.py")]
ROOT_NAME = "Ref Character Replacement"
FOLDER = "application/vnd.google-apps.folder"


def gapi(*args):
    r = subprocess.run(GAPI + list(args), capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"google_api {args[:2]}: {r.stderr.strip()[:400]}")
    return json.loads(r.stdout) if r.stdout.strip() else {}


def items(res):
    return res if isinstance(res, list) else res.get("files", [])


def folder(name, parent=None):
    q = f"name = '{name}' and mimeType = '{FOLDER}' and trashed = false"
    if parent:
        q += f" and '{parent}' in parents"
    found = items(gapi("drive", "search", q, "--raw-query"))
    if found:
        return found[0]["id"]
    args = ["drive", "create-folder", name] + (["--parent", parent] if parent else [])
    return gapi(*args)["id"]


def children(fid):
    return {i["name"]: i for i in items(gapi("drive", "search", f"'{fid}' in parents and trashed = false",
                                             "--raw-query"))}


def upload_dir(local: Path, fid, pattern="*"):
    have = children(fid)
    out = {}
    for p in sorted(local.glob(pattern)):
        if not p.is_file():
            continue
        if p.name in have:
            out[p.name] = have[p.name].get("id")
            continue
        d = gapi("drive", "upload", str(p), "--parent", fid)
        out[p.name] = d.get("id")
        print(f"  up {local.name}/{p.name}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batch")
    ap.add_argument("--no-drive", action="store_true")
    ap.add_argument("--no-compare", action="store_true")
    a = ap.parse_args()
    B = DATA / "batches" / a.batch
    ip, port = (DATA / "pod_ssh").read_text().split()
    e = f"ssh -p {port} -o StrictHostKeyChecking=no -o ConnectTimeout=20 -i {Path.home()}/.ssh/id_ed25519"
    for sub in ("renders", "upscaled", "sidecars"):
        (B / sub).mkdir(exist_ok=True)
    # tar over ssh (the RunPod image has no rsync). Pull only results; the
    # remote side lists what exists so a missing upscaled/ dir isn't an error.
    remote = (f"cd /workspace/batches/{a.batch} && "
              "tar -czf - $(ls -d renders upscaled sidecars results.csv upscale_results.csv 2>/dev/null)")
    ssh = e.split() + [f"root@{ip}", remote]
    p1 = subprocess.Popen(ssh, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    r = subprocess.run(["tar", "-C", str(B), "-xzf", "-"], stdin=p1.stdout, capture_output=True, text=True)
    p1.stdout.close()
    err = p1.stderr.read().decode(errors="ignore")
    if p1.wait() != 0 or r.returncode != 0:
        sys.exit(f"pull failed: ssh={p1.returncode} {err[-400:]} tar={r.returncode} {r.stderr[-300:]}")
    renders = sorted((B / "renders").glob("*.mp4"))
    print(f"pulled: {len(renders)} renders, {len(list((B / 'upscaled').glob('*.mp4')))} upscales")

    # ---- side-by-sides: source (as trimmed) | reference | result ------------
    if not a.no_compare:
        (B / "compare").mkdir(exist_ok=True)
        for rp in renders:
            sc_path = B / "sidecars" / f"{rp.stem}.json"
            out = B / "compare" / f"{rp.stem}_compare.mp4"
            if out.exists() or not sc_path.exists():
                continue
            sc = json.loads(sc_path.read_text())
            src = B / "sources" / sc["params"]["source"]
            ref = B / "refs" / sc["params"]["reference"]
            subprocess.run(["bash", str(SK / "scripts/make_compare.sh"), str(src), str(ref), str(rp), str(out)],
                           check=True, capture_output=True)
            print(f"  compare {out.name}")

    if a.no_drive:
        return
    root = folder(ROOT_NAME)
    bf = folder(a.batch, root)
    ids = {}
    for sub, local in (("inputs", None), ("renders", B / "renders"), ("upscaled", B / "upscaled"),
                       ("compare", B / "compare")):
        fid = folder(sub, bf)
        if sub == "inputs":
            ids.update(upload_dir(B / "sources", fid))
            ids.update(upload_dir(B / "refs", fid))
        elif local.exists():
            ids.update(upload_dir(local, fid, "*.mp4"))
    ids.update(upload_dir(B, bf, "*.csv"))

    # ---- results sheet --------------------------------------------------------
    link = lambda n: f"https://drive.google.com/file/d/{ids[n]}/view" if ids.get(n) else ""  # noqa: E731
    header = ["job", "source", "reference", "bg", "audio", "res", "steps", "exec_s", "cost_usd",
              "status", "render", "compare", "upscales"]
    rows = [header]
    for sp in sorted((B / "sidecars").glob("J*_*.json")):
        sc = json.loads(sp.read_text())
        if "params" not in sc:
            continue                       # upscale sidecar
        p = sc["params"]
        ups = sorted(x.name for x in (B / "upscaled").glob(f"{sc['stem']}_*.mp4"))
        rows.append([sc["job"], p["source"], p["reference"], int(p["replace_bg"]), p["audio"], p["res"],
                     p["steps"], sc["timing"]["exec_s"], sc["cost_usd"], sc["status"],
                     link(f"{sc['stem']}.mp4"), link(f"{sc['stem']}_compare.mp4"),
                     " ".join(link(u) for u in ups)])
    title = f"{a.batch} results"
    sheet_id = (json.loads((B / "sheet.json").read_text())["id"] if (B / "sheet.json").exists() else None)
    if not sheet_id:
        s = gapi("sheets", "create", "--title", title)
        sheet_id = s.get("spreadsheetId") or s.get("id")
        (B / "sheet.json").write_text(json.dumps({"id": sheet_id}))
        # google_api.py has no `drive move`; do it with the Drive API directly
        sys.path.insert(0, str(Path(GAPI[1]).parent))
        from google_api import build_service  # noqa: E402
        drv = build_service("drive", "v3")
        prev = ",".join(drv.files().get(fileId=sheet_id, fields="parents").execute().get("parents", []))
        drv.files().update(fileId=sheet_id, addParents=bf, removeParents=prev, fields="id").execute()
    gapi("sheets", "update", sheet_id, "Sheet1!A1", "--values", json.dumps(rows))
    print(f"SHEET: https://docs.google.com/spreadsheets/d/{sheet_id}/edit")
    print(f"FOLDER: https://drive.google.com/drive/folders/{bf}")


if __name__ == "__main__":
    main()
