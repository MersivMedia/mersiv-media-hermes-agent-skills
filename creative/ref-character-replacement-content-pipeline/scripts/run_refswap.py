#!/usr/bin/env python3
"""Convert the UI workflow to API format via the live server and queue it.

The UI->API conversion is done against /object_info rather than by hand, so
widget order always matches the node schema actually loaded on the server.
Usage: run_refswap.py <workflow.json> <replace_background:0|1> "<instruction>" [duration]
"""
import json
import sys
import time
import urllib.request
import uuid

HOST = "http://127.0.0.1:8189"


def get(path):
    with urllib.request.urlopen(HOST + path, timeout=60) as r:
        return json.load(r)


def post(path, body):
    req = urllib.request.Request(HOST + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code}: {e.read().decode()[:3000]}")


wf_path, replace_bg, instruction = sys.argv[1], sys.argv[2] == "1", sys.argv[3]
duration = float(sys.argv[4]) if len(sys.argv) > 4 else 5.0

ui = json.load(open(wf_path))
info = get("/object_info")
links = {l[0]: l for l in ui["links"]}
api = {}

for n in ui["nodes"]:
    t = n["type"]
    if n.get("mode") in (2, 4) or t in ("MarkdownNote", "Note", "Reroute"):
        continue
    if t not in info:
        raise SystemExit(f"node type not on server: {t} (id {n['id']})")
    spec = info[t]["input"]
    order = list((spec.get("required") or {}).items()) + list((spec.get("optional") or {}).items())
    linked = {}
    for inp in n.get("inputs", []):
        if inp.get("link") is not None:
            l = links[inp["link"]]
            linked[inp["name"]] = [str(l[1]), l[2]]
    wv = n.get("widgets_values")
    inputs = {}
    if isinstance(wv, dict):
        # VHS nodes store widgets by name
        for k, v in wv.items():
            if k in dict(order):
                inputs[k] = v
    else:
        wv = list(wv or [])
        i = 0
        for name, s in order:
            typ = s[0]
            is_widget = isinstance(typ, list) or typ in ("INT", "FLOAT", "STRING", "BOOLEAN", "COMBO")
            if not is_widget:
                continue
            if i >= len(wv):
                break
            inputs[name] = wv[i]
            i += 1
            # seed-style INTs carry a trailing "control_after_generate" widget
            if typ == "INT" and i < len(wv) and wv[i] in ("fixed", "randomize", "increment", "decrement"):
                i += 1
    inputs.update(linked)
    api[str(n["id"])] = {"class_type": t, "inputs": inputs}

# ---- per-run overrides ------------------------------------------------------
for nid, n in api.items():
    t = n["class_type"]
    if t == "H3PromptDirector":
        n["inputs"]["instruction"] = instruction
        # Only drop the literal if the checkbox link actually made it across;
        # otherwise pin it explicitly so validation never sees it missing.
        if not isinstance(n["inputs"].get("replace_background"), list):
            n["inputs"]["replace_background"] = replace_bg
    if t == "PrimitiveBoolean" and "background" in (next(x for x in ui["nodes"] if str(x["id"]) == nid).get("title", "")):
        n["inputs"]["value"] = replace_bg
    if t == "PrimitiveFloat" and "Duration" in (next(x for x in ui["nodes"] if str(x["id"]) == nid).get("title", "")):
        n["inputs"]["value"] = duration

json.dump(api, open("/root/last_api.json", "w"), indent=1)
cid = str(uuid.uuid4())
resp = post("/prompt", {"prompt": api, "client_id": cid})
pid = resp["prompt_id"]
print(f"queued prompt_id={pid} replace_bg={replace_bg} duration={duration}", flush=True)

t0 = time.time()
while True:
    time.sleep(8)
    h = get(f"/history/{pid}")
    if pid in h:
        e = h[pid]
        st = e.get("status", {})
        el = time.time() - t0
        if st.get("status_str") == "error" or not st.get("completed", True):
            for m in st.get("messages", []):
                if m[0] == "execution_error":
                    d = m[1]
                    print(f"ERROR after {el:.0f}s in node {d.get('node_id')} {d.get('node_type')}: "
                          f"{d.get('exception_message','')[:1500]}")
            raise SystemExit(1)
        outs = []
        for nd in (e.get("outputs") or {}).values():
            for key in ("videos", "gifs", "images"):
                for item in nd.get(key) or []:
                    outs.append(f"{item.get('subfolder','')}/{item['filename']}")
            for txt in nd.get("text") or []:
                open("/root/last_prompt.txt", "w").write(txt if isinstance(txt, str) else json.dumps(txt))
        print(f"DONE in {el:.0f}s  outputs={outs}")
        break
    if time.time() - t0 > 3000:
        raise SystemExit("TIMEOUT waiting for history")
