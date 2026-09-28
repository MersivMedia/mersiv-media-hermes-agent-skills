#!/usr/bin/env python3
"""Test pod/autostop.py self-stop against a local fake RunPod REST API that
behaves like the real one on the point that broke: it 403s Python's default
urllib User-Agent (verified against rest.runpod.io on 2026-09-28).
No network, no spend."""
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
AUTOSTOP = os.path.join(HERE, "..", "pod", "autostop.py")
calls = []


class Fake(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _go(self):
        ua = self.headers.get("User-Agent", "")
        auth = self.headers.get("Authorization", "")
        calls.append((self.command, self.path, ua))
        if ua.startswith("Python-urllib"):
            code, body = 403, b"error code: 1010"          # what Cloudflare returned
        elif auth != "Bearer testkey":
            code, body = 401, b"bad key"
        else:
            code, body = 200, json.dumps({"id": "p1", "desiredStatus": "RUNNING"}).encode()
        self.send_response(code); self.end_headers(); self.wfile.write(body)

    do_GET = do_POST = _go


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake)
threading.Thread(target=srv.serve_forever, daemon=True).start()
REST = f"http://127.0.0.1:{srv.server_address[1]}/v1"
tmp = tempfile.mkdtemp()
PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    print(f"  {'PASS' if cond else 'FAIL'} {name}" + ("" if cond else f"  ({detail})"))
    PASS += bool(cond); FAIL += (not cond)


def env(**kw):
    e = dict(os.environ, AUTOSTOP_REST=REST, AUTOSTOP_LOG=f"{tmp}/a.log",
             RUNPOD_POD_ID="p1", RUNPOD_API_KEY="testkey", PATH=f"{tmp}/nobin:/usr/bin:/bin")
    e.update(kw); return e


# 0) the fake really reproduces the incident: default UA is refused
import urllib.request, urllib.error
try:
    urllib.request.urlopen(urllib.request.Request(f"{REST}/pods/p1", headers={"Authorization": "Bearer testkey"}))
    check("fake 403s default urllib UA", False, "got 200")
except urllib.error.HTTPError as e:
    check("fake 403s default urllib UA (reproduces incident)", e.code == 403, e.code)

# 1) --check authenticates through the fixed code path
r = subprocess.run([sys.executable, AUTOSTOP, "--check"], env=env(), capture_output=True, text=True)
check("--check OK with fixed UA", r.returncode == 0 and "check OK" in r.stdout, r.stdout + r.stderr)
check("--check sent curl UA", calls and calls[-1][2].startswith("curl/"), calls[-1:])

# 2) --check FAILS loudly with a bad key (bring-up would warn)
r = subprocess.run([sys.executable, AUTOSTOP, "--check"], env=env(RUNPOD_API_KEY="wrong"), capture_output=True, text=True)
check("--check FAIL on bad key, nonzero exit", r.returncode != 0 and "FAIL" in r.stdout, r.stdout)

# 3) hard cap fires and actually POSTs a stop that the API accepts
calls.clear()
p = subprocess.Popen([sys.executable, AUTOSTOP], env=env(AUTOSTOP_HARD_CAP_S="2", AUTOSTOP_TICK_S="1", LANE_PORTS="1"),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(5); p.terminate(); p.wait()
stops = [c for c in calls if c[0] == "POST" and c[1] == "/v1/pods/p1/stop"]
check("hard cap POSTed /pods/p1/stop", len(stops) >= 1, calls)
check("stop call used curl UA (not refused)", stops and stops[0][2].startswith("curl/"), stops[:1])
log = open(f"{tmp}/a.log").read()
check("log records REST stop -> 200", "REST stop -> 200" in log, log[-300:])
check("log written to the persistent path", os.path.exists(f"{tmp}/a.log"))

srv.shutdown()
print(f"RESULT: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
