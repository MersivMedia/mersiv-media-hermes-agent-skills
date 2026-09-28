#!/usr/bin/env python3
"""Upload pipeline outputs to Drive: Ref Character Replacement/<run label>/.

Usage: deliver_drive.py "<run label>" file1.mp4 [file2.mp4 ...]
Reuses the root folder if it already exists. Prints the folder link and
each uploaded file's name/size/id, then verifies by listing the folder.
"""
import json, os, subprocess, sys

GAPI = [sys.executable, os.path.expanduser(
    os.environ.get("HERMES_HOME", "~/.hermes") + "/skills/productivity/google-workspace/scripts/google_api.py")]
ROOT_NAME = "Ref Character Replacement"
FOLDER_MIME = "application/vnd.google-apps.folder"


def gapi(*args):
    r = subprocess.run(GAPI + list(args), capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"google_api {args[:2]} failed: {r.stderr.strip()[:400]}")
    return json.loads(r.stdout)


def find_folder(name, parent=None):
    q = f"name = '{name}' and mimeType = '{FOLDER_MIME}' and trashed = false"
    if parent:
        q += f" and '{parent}' in parents"
    try:
        res = gapi("drive", "search", q, "--raw-query")
    except SystemExit:
        return None
    items = res if isinstance(res, list) else res.get("files", [])
    return items[0]["id"] if items else None


label, files = sys.argv[1], sys.argv[2:]
missing = [f for f in files if not os.path.isfile(f)]
if missing:
    sys.exit(f"missing files: {missing}")

root = find_folder(ROOT_NAME) or gapi("drive", "create-folder", ROOT_NAME)["id"]
run = find_folder(label, root) or gapi("drive", "create-folder", label, "--parent", root)["id"]

for f in files:
    d = gapi("drive", "upload", f, "--parent", run)
    print(f"uploaded {d.get('name')}  local={os.path.getsize(f)}B  id={d.get('id')}")

listing = find_children = gapi("drive", "search", f"'{run}' in parents and trashed = false", "--raw-query")
items = listing if isinstance(listing, list) else listing.get("files", [])
print(f"folder now holds {len(items)} file(s): {sorted(i.get('name') for i in items)}")
print(f"FOLDER: https://drive.google.com/drive/folders/{run}")
