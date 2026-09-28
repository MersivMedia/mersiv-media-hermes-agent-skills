#!/usr/bin/env python3
"""Auto-stop (runs ON THE POD in tmux).

Batch sessions (/root/batch_session exists):
  when no batch_runner is alive, no upscale ticket is pending or in flight,
  and every lane's queue has been empty for IDLE_S, write /root/STOP_REQUESTED.
  The LOCAL watcher (autostop_watch.sh) sees it, syncs results off the pod,
  touches /root/SYNCED, and stops the pod. The EU-NL-1 volume has no S3
  endpoint, so results are unreachable from outside once the pod is down:
  sync must happen first. Backstop: if nothing has synced BACKSTOP_S after the
  request, the pod stops itself (outputs stay on the volume).
Manual browser sessions (no batch ever ran):
  stop after MANUAL_IDLE_S of empty queues.
Self-stop uses the pod's own RUNPOD_POD_ID / RUNPOD_API_KEY from PID 1's
environment; bootstrap records whether that is available.
"""
import glob
import json
import os
import subprocess
import time
import urllib.error
import urllib.request

IDLE_S = int(os.environ.get("AUTOSTOP_IDLE_S", 180))
# Absolute cap from autostop start, any mode. Pod-side, so it works even if
# this box / the local watcher is down. Nothing legit runs this long.
HARD_CAP_S = int(os.environ.get("AUTOSTOP_HARD_CAP_S", 7200))
REST = os.environ.get("AUTOSTOP_REST", "https://rest.runpod.io/v1")   # override = tests only
# rest.runpod.io 403s Python's default "Python-urllib/x" User-Agent (Cloudflare).
# Verified 2026-09-28 from this box: default UA -> 403, curl UA -> 200. So any
# self-stop the pod attempted that day was refused (the pod log was on /root and
# was wiped, so whether it actually tried is inferred, not seen).
UA = "curl/8.5.0"
BACKSTOP_S = int(os.environ.get("AUTOSTOP_BACKSTOP_S", 1200))
MANUAL_IDLE_S = int(os.environ.get("AUTOSTOP_MANUAL_IDLE_S", 3600))
LANES = [x for x in os.environ.get("LANE_PORTS", "8189").split(",") if x]
# Persistent log (the volume) so a post-mortem survives the stop; /root is
# container disk and is wiped when the pod stops, which destroyed the evidence.
LOG = os.environ.get("AUTOSTOP_LOG") or "/workspace/refswap_logs/autostop_%s.log" % os.environ.get("RUNPOD_POD_ID", "pod")


def log(msg):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(time.strftime("%H:%M:%S ") + msg + "\n")


def pid1_env():
    try:
        raw = open("/proc/1/environ", "rb").read().split(b"\0")
        return dict(x.decode(errors="ignore").split("=", 1) for x in raw if b"=" in x)
    except OSError:
        return {}


def queues_empty():
    for port in LANES:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/queue", timeout=10) as r:
                q = json.load(r)
            if q.get("queue_running") or q.get("queue_pending"):
                return False
        except Exception:
            pass          # a lane that is down is not doing work
    return True


def batch_busy():
    if os.path.exists("/root/SESSION_HOLD"):      # perf_session between phases
        return True
    runners = subprocess.run(["pgrep", "-f", "[b]atch_runner.py"], capture_output=True).returncode == 0
    tickets = glob.glob("/workspace/batches/*/upscale_queue/*.json") + \
        glob.glob("/workspace/batches/*/upscale_queue/*.working")
    return runners or bool(tickets)


def creds():
    env = pid1_env()
    return (os.environ.get("RUNPOD_POD_ID") or env.get("RUNPOD_POD_ID"),
            os.environ.get("RUNPOD_API_KEY") or env.get("RUNPOD_API_KEY"))


def api(method, path, key):
    req = urllib.request.Request(f"{REST}{path}", method=method, data=b"" if method == "POST" else None,
                                 headers={"Authorization": f"Bearer {key}", "User-Agent": UA,
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()[:300]
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300]
    except Exception as e:
        return 0, str(e).encode()[:300]


def check():
    """Bring-up proof that self-stop can authenticate: a real authenticated GET
    of this pod through the same code path self_stop uses. Prints OK/FAIL."""
    pod, key = creds()
    if not (pod and key):
        print("[autostop] self-stop check FAIL: no RUNPOD_POD_ID/RUNPOD_API_KEY"); return False
    code, body = api("GET", f"/pods/{pod}", key)
    good = code == 200
    print(f"[autostop] self-stop check {'OK' if good else 'FAIL'}: GET /pods/{pod} -> {code}"
          + ("" if good else f" {body[:120]!r}"))
    return good


def self_stop(reason):
    pod, key = creds()
    log(f"SELF-STOP ({reason}) pod={pod} key={'yes' if key else 'no'}")
    if pod and key:
        code, body = api("POST", f"/pods/{pod}/stop", key)
        log(f"  REST stop -> {code} {body[:120]!r}")
        if 200 <= code < 300:
            return True
    # fallback: runpodctl ships in RunPod images and authenticates from env
    try:
        r = subprocess.run(["runpodctl", "stop", "pod", pod or ""], capture_output=True, text=True, timeout=60)
        log(f"  runpodctl stop -> rc={r.returncode} {(r.stdout + r.stderr)[:160]!r}")
        return r.returncode == 0
    except Exception as e:
        log(f"  runpodctl unavailable: {e}")
    return False


def main():
    idle_since = None
    t_start = time.time()
    log(f"autostop up: lanes={LANES} idle={IDLE_S}s backstop={BACKSTOP_S}s "
        f"manual={MANUAL_IDLE_S}s hard_cap={HARD_CAP_S}s")
    while True:
        time.sleep(int(os.environ.get("AUTOSTOP_TICK_S", 30)))
        if time.time() - t_start >= HARD_CAP_S:
            self_stop(f"hard cap {HARD_CAP_S}s")      # retried every tick until it works
            continue
        batch_mode = os.path.exists("/root/batch_session")
        idle = queues_empty() and not (batch_mode and batch_busy())
        now = time.time()
        idle_since = (idle_since or now) if idle else None
        if os.path.exists("/root/STOP_REQUESTED"):
            if not idle:                               # new work arrived: cancel
                os.remove("/root/STOP_REQUESTED")
                log("new work, stop request cancelled")
                continue
            req_t = os.path.getmtime("/root/STOP_REQUESTED")
            synced = os.path.exists("/root/SYNCED") and os.path.getmtime("/root/SYNCED") >= req_t
            if not synced and now - req_t > BACKSTOP_S:
                self_stop("backstop: nothing synced")
            continue
        if idle_since and batch_mode and now - idle_since >= IDLE_S:
            open("/root/STOP_REQUESTED", "w").write(str(now))
            log("batch work finished: STOP_REQUESTED")
        elif idle_since and not batch_mode and now - idle_since >= MANUAL_IDLE_S:
            self_stop(f"manual session idle {MANUAL_IDLE_S}s")


if __name__ == "__main__":
    import sys
    if "--check" in sys.argv:
        sys.exit(0 if check() else 1)
    main()
