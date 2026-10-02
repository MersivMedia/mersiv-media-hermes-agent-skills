#!/usr/bin/env python3
"""Unit tests for the three 2026-09-28 perf-session bugs (no pod, no network).

 1  pick_output ignores history entries typed "input" (the loaded clip) and
    missing files; the upscale lane crashed taking vids[-1].
 2  (shell) batch_status.sh reports WORKER_DEAD for pending tickets + a dead or
    stale worker, so wait_batch stops waiting on orphaned tickets.
 3  Comfy.run survives a websocket recv timeout (silence during the Director's
    Claude call) and still records per-node time and sampler steps.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / "pod"))
import comfy_api  # noqa: E402

P = F = 0


def check(name, cond, detail=""):
    global P, F
    if cond:
        P += 1; print(f"  PASS {name}")
    else:
        F += 1; print(f"  FAIL {name} {detail}")


# ---- 1: pick_output ---------------------------------------------------------
print("== pick_output")
root = Path(tempfile.mkdtemp())
(root / "output/refswap_up/b").mkdir(parents=True)
real = root / "output/refswap_up/b/J01_x_4k_00001_.mp4"; real.write_bytes(b"x")
outs = [{"filename": "J01_x_4k_00001_.mp4", "subfolder": "refswap_up/b", "type": "output"},
        {"filename": "J01_x.mp4", "subfolder": "", "type": "input"}]          # the 09-28 shape
check("skips type=input listed last", comfy_api.pick_output(outs, root, "refswap_up/b/J01_x_4k") == real)
check("None when only an input entry", comfy_api.pick_output(outs[1:], root) is None)
gone = [{"filename": "missing_00001_.mp4", "subfolder": "", "type": "output"}]
check("None when the file is missing (no FileNotFound)", comfy_api.pick_output(gone, root) is None)
temp = [{"filename": "J01_x_4k_00001_.mp4", "subfolder": "refswap_up/b", "type": "temp"}] + outs
check("skips type=temp previews", comfy_api.pick_output(temp, root) == real)
other = root / "output/refswap_up/b/OTHER_00001_.mp4"; other.write_bytes(b"y")
two = [{"filename": "J01_x_4k_00001_.mp4", "subfolder": "refswap_up/b", "type": "output"},
       {"filename": "OTHER_00001_.mp4", "subfolder": "refswap_up/b", "type": "output"}]
check("prefix match beats list order", comfy_api.pick_output(two, root, "refswap_up/b/J01_x_4k") == real)

# ---- 2: batch_status.sh -----------------------------------------------------
print("== batch_status.sh")
T = Path(tempfile.mkdtemp())
q = T / "batches/bt/upscale_queue"; q.mkdir(parents=True)
env = dict(os.environ, REFSWAP_BATCHES=str(T / "batches"), REFSWAP_RUNDIR=str(T))
st = lambda: subprocess.run(["bash", str(SK / "pod/batch_status.sh"), "bt"], env=env,  # noqa: E731
                            capture_output=True, text=True).stdout.strip()
check("no runner, no tickets -> DONE", st() == "DONE", st())
(q / "J01__2160.json.working").write_text("{}")
check("ticket + no worker process -> WORKER_DEAD", st().startswith("WORKER_DEAD tickets=1"), st())
fake = subprocess.Popen(["bash", "-c", "exec -a upscale_worker.py sleep 30"])
time.sleep(0.3)
(T / "upworker.alive").write_text(str(int(time.time())))
check("ticket + live worker + fresh heartbeat -> BUSY", st().startswith("BUSY") and "worker=1" in st(), st())
(T / "upworker.alive").write_text(str(int(time.time()) - 600))
check("ticket + live worker + stale heartbeat (hung) -> WORKER_DEAD", st().startswith("WORKER_DEAD"), st())
fake.kill()

# ---- 3: websocket timeout during a silent node --------------------------------
print("== Comfy.run websocket silence")


class WSTimeout(Exception):
    pass


WSTimeout.__name__ = "WebSocketTimeoutException"


class FakeWS:
    """Replays a render: Director node, then 16+ s of silence (recv timeouts),
    then sampler progress, VAE decode, save, done."""
    def __init__(self, pid_box):
        self.box = pid_box; self.i = 0
        self.script = None

    def settimeout(self, t):
        self.timeout = t

    def _msgs(self):
        pid = self.box["pid"]
        m = lambda typ, **d: json.dumps({"type": typ, "data": dict(d, prompt_id=pid)})  # noqa: E731
        return ([m("execution_cached", nodes=["119"]), m("executing", node="160")]
                + ["TIMEOUT"] * 4                                   # Director calling Claude
                + [m("executing", node="125")]
                + [m("progress", value=v, max=4, node="125") for v in (1, 2, 3, 4)]
                + [m("executing", node="122"), m("executing", node="92"), m("executing", node=None)])

    def recv(self):
        if self.script is None:
            self.script = self._msgs()
        if self.i >= len(self.script):
            raise WSTimeout()
        x = self.script[self.i]; self.i += 1
        if x == "TIMEOUT":
            time.sleep(0.05)
            raise WSTimeout()
        time.sleep(0.02)
        return x

    def close(self):
        pass


box = {}
sys.modules["websocket"] = types.SimpleNamespace(create_connection=lambda *a, **k: FakeWS(box))


class C(comfy_api.Comfy):
    def post(self, path, body, timeout=60):
        box["pid"] = "p1"; return {"prompt_id": "p1"}

    def get(self, path, timeout=60):
        if path.startswith("/history/"):
            return {"p1": {"status": {"status_str": "success", "messages": []},
                           "outputs": {"92": {"videos": [{"filename": "a.mp4", "subfolder": "", "type": "output"}]}}}}
        return {}


api = {k: {"class_type": c} for k, c in
       (("160", "H3PromptDirector"), ("125", "SamplerCustomAdvanced"), ("122", "VAEDecode"), ("92", "SaveVideo"))}
res = C("http://x").run(api, timeout=60)
ns = res["node_seconds"]
check("status ok", res["status"] == "ok", res["status"])
check("sampler node timed (not all billed to Director)", "125" in ns and "122" in ns, list(ns))
check("4 sampler steps recorded", len(res["step_times"]) == 4, res["step_times"])
check("median step computable", comfy_api.median_step_seconds(res["step_times"], "125") is not None)

print(f"RESULT: {P} passed, {F} failed")
sys.exit(1 if F else 0)
