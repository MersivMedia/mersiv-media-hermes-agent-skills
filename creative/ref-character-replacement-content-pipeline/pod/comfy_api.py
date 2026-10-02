"""Shared ComfyUI client for the refswap pod scripts (stdlib + optional websocket-client).

- ui_to_api(): UI workflow -> API prompt, converted against the server's live
  /object_info so widget order always matches the loaded node schema.
  Handles V3 nested dropdowns (COMFY_DYNAMICCOMBO_V3, keys "parent.child") and
  VHS dict-valued widgets. Skips bypassed/muted nodes and notes/reroutes.
- run(): queue a prompt and wait. When websocket-client is importable it also
  records per-node wall time and per-step sampler timestamps, which is what
  lets the perf session separate model-load time from warm sampling speed.
"""
from __future__ import annotations

import json
import time
import urllib.request
import uuid

NON_EXEC = ("MarkdownNote", "Note", "Reroute", "PrimitiveNode")
WIDGET_TYPES = ("INT", "FLOAT", "STRING", "BOOLEAN", "COMBO")
SEED_CONTROLS = ("fixed", "randomize", "increment", "decrement")


class Comfy:
    def __init__(self, host: str):
        self.host = host.rstrip("/")

    def get(self, path: str, timeout: int = 60):
        with urllib.request.urlopen(self.host + path, timeout=timeout) as r:
            return json.load(r)

    def post(self, path: str, body: dict, timeout: int = 60):
        req = urllib.request.Request(self.host + path, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"POST {path} -> HTTP {e.code}: {e.read().decode()[:3000]}")

    def alive(self) -> bool:
        try:
            self.get("/system_stats", timeout=5)
            return True
        except Exception:
            return False

    def queue_depth(self) -> int:
        q = self.get("/queue", timeout=10)
        return len(q.get("queue_running", [])) + len(q.get("queue_pending", []))

    # ------------------------------------------------------------------ convert
    def ui_to_api(self, ui: dict, info: dict | None = None) -> dict:
        info = info or self.get("/object_info", timeout=120)
        links = {l[0]: l for l in ui["links"]}
        api = {}
        for n in ui["nodes"]:
            t = n["type"]
            if n.get("mode") in (2, 4) or t in NON_EXEC:
                continue
            if t not in info:
                raise RuntimeError(f"node type not on server: {t} (id {n['id']})")
            spec = info[t]["input"]
            order = list((spec.get("required") or {}).items()) + list((spec.get("optional") or {}).items())
            inputs = {}
            wv = n.get("widgets_values")
            if isinstance(wv, dict):                       # VHS: widgets by name
                names = dict(order)
                inputs.update({k: v for k, v in wv.items() if k in names})
            else:
                vals, pos = list(wv or []), [0]

                def consume(items, prefix=""):
                    for name, s in items:
                        typ = s[0]
                        opts = s[1] if len(s) > 1 else {}
                        if typ == "COMFY_DYNAMICCOMBO_V3":
                            if pos[0] >= len(vals):
                                return
                            val = vals[pos[0]]; pos[0] += 1
                            inputs[prefix + name] = val
                            chosen = next((o for o in opts.get("options", []) if o.get("key") == val), None)
                            sub = ((chosen or {}).get("inputs") or {}).get("required") or {}
                            consume(list(sub.items()), prefix + name + ".")
                            continue
                        if not (isinstance(typ, list) or typ in WIDGET_TYPES):
                            continue
                        if pos[0] >= len(vals):
                            return
                        inputs[prefix + name] = vals[pos[0]]; pos[0] += 1
                        if typ == "INT" and pos[0] < len(vals) and vals[pos[0]] in SEED_CONTROLS:
                            pos[0] += 1
                consume(order)
            for inp in n.get("inputs", []):
                if inp.get("link") is not None:
                    l = links[inp["link"]]
                    inputs[inp["name"]] = [str(l[1]), l[2]]
            api[str(n["id"])] = {"class_type": t, "inputs": inputs}
        return api

    # ---------------------------------------------------------------------- run
    def run(self, api: dict, timeout: int = 3600) -> dict:
        """Queue and wait. Returns {status, prompt_id, seconds, outputs, error,
        node_seconds{id:{class,seconds}}, cached[], step_times[]}."""
        cid = str(uuid.uuid4())
        ws = None
        try:
            import websocket  # websocket-client, installed by bootstrap
            ws = websocket.create_connection(
                self.host.replace("http", "ws", 1) + f"/ws?clientId={cid}", timeout=15)
            ws.settimeout(5)            # short recv timeout; silence is handled in the loop
        except Exception:
            ws = None
        pid = self.post("/prompt", {"prompt": api, "client_id": cid})["prompt_id"]
        t0 = time.time()
        node_seconds, cached, step_times = {}, [], []
        cur, cur_t = None, None

        def close_node(now):
            if cur is not None:
                cls = api.get(cur, {}).get("class_type", "?")
                prev = node_seconds.get(cur, {}).get("seconds", 0.0)
                node_seconds[cur] = {"class": cls, "seconds": round(prev + now - cur_t, 2)}

        done = False
        last_hist = time.time()
        while not done and time.time() - t0 < timeout:
            if ws is not None:
                # A recv TIMEOUT is silence, not a dead socket. The 15 s connect
                # timeout also applies to recv, and the Director's Claude call is
                # silent for longer than that: on 2026-09-28 every render dropped
                # to HTTP polling there, so no node/step events arrived and the
                # whole render was billed to H3PromptDirector (median_step empty).
                try:
                    raw = ws.recv()
                except Exception as ex:
                    raw = None
                    if "Timeout" in type(ex).__name__ or isinstance(ex, TimeoutError):
                        if time.time() - last_hist > 30:       # safety net: missed final event
                            last_hist = time.time()
                            if pid in self.get(f"/history/{pid}"):
                                done = True
                        continue
                    try:
                        ws.close()
                    except Exception:
                        pass
                    ws = None
                if isinstance(raw, str):
                    m = json.loads(raw)
                    d = m.get("data") or {}
                    if d.get("prompt_id") not in (None, pid):
                        continue
                    now = time.time()
                    if m["type"] == "executing":
                        close_node(now)
                        cur, cur_t = d.get("node"), now
                        if cur is None:
                            done = True
                    elif m["type"] == "execution_cached":
                        cached = list(d.get("nodes") or [])
                    elif m["type"] == "progress":
                        step_times.append([round(now - t0, 2), d.get("value"), d.get("max"), d.get("node")])
                    elif m["type"] in ("execution_error", "execution_interrupted"):
                        close_node(now)
                        done = True
                    continue
            time.sleep(5)
            if pid in self.get(f"/history/{pid}"):
                done = True
        close_node(time.time())
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass

        res = {"prompt_id": pid, "seconds": round(time.time() - t0, 1), "outputs": [],
               "node_seconds": node_seconds, "cached": cached, "step_times": step_times,
               "status": "timeout", "error": None, "text": []}
        for _ in range(24):                      # history can lag the ws by a moment
            h = self.get(f"/history/{pid}")
            if pid in h:
                break
            time.sleep(5)
        else:
            return res
        e = h[pid]
        st = e.get("status") or {}
        # Execution-only time from ComfyUI's own timestamps (ms). Excludes time
        # spent queued behind the other lane's prompts in the serial layout.
        ts = {m[0]: m[1].get("timestamp") for m in st.get("messages", []) if isinstance(m[1], dict)}
        end = ts.get("execution_success") or ts.get("execution_error") or ts.get("execution_interrupted")
        if ts.get("execution_start") and end:
            res["exec_seconds"] = round((end - ts["execution_start"]) / 1000.0, 1)
            res["exec_start_epoch"] = ts["execution_start"] / 1000.0
            res["exec_end_epoch"] = end / 1000.0
        if st.get("status_str") == "error":
            res["status"] = "error"
            for m in st.get("messages", []):
                if m[0] == "execution_error":
                    d = m[1]
                    res["error"] = (f"node {d.get('node_id')} {d.get('node_type')}: "
                                    f"{d.get('exception_message', '')[:2000]}")
            return res
        res["status"] = "ok"
        for nd in (e.get("outputs") or {}).values():
            for k in ("videos", "gifs", "images"):
                for it in nd.get(k) or []:
                    res["outputs"].append(it)
            for txt in nd.get("text") or []:
                res["text"].append(txt if isinstance(txt, str) else json.dumps(txt))
        return res


def pick_output(outputs: list, root, prefix: str | None = None):
    """The saved mp4 from a history outputs list, as an existing Path, or None.

    History also lists LOADED videos (type "input", e.g. a load-node preview)
    and temp previews. Taking outputs[-1] blindly picked the input clip on
    2026-09-28 and crashed the upscale lane (FileNotFoundError in output/).
    Only type=="output" counts; a prefix match wins; the file must exist."""
    from pathlib import Path
    cands = [o for o in outputs if str(o.get("filename", "")).endswith(".mp4")
             and o.get("type", "output") == "output"]
    if prefix:
        want = prefix.rsplit("/", 1)[-1]
        pref = [o for o in cands if str(o["filename"]).startswith(want)]
        cands = pref or cands
    for o in reversed(cands):
        p = Path(root) / "output" / o.get("subfolder", "") / o["filename"]
        if p.exists():
            return p
    return None


def median_step_seconds(step_times: list, sampler_node: str | None = None) -> float | None:
    """Median seconds per sampler step from progress events, ignoring the
    first interval (it includes model initialisation)."""
    pts = [p for p in step_times if sampler_node is None or str(p[3]) == str(sampler_node)]
    gaps = [b[0] - a[0] for a, b in zip(pts, pts[1:]) if b[1] == a[1] + 1]
    if len(gaps) > 1:
        gaps = gaps[1:]
    if not gaps:
        return None
    gaps.sort()
    return round(gaps[len(gaps) // 2], 2)
