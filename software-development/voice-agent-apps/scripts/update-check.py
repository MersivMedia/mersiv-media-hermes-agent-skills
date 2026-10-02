"""Prove silent auto-update on production via CDP (passed 6/6 on the first tutor, Oct 2026).

Opens the app, REDEPLOYS (runs DEPLOY_SCRIPT), then asserts:
  same build -> no reload on wake; new deployment live; typing blocks reload;
  idle -> reloads to new build; still signed in; no reload loop afterwards.
Env: BASE, KEY_FILE (learner key), DEPLOY_SCRIPT (bash, does `vercel deploy --prod`).
Needs websocket-client (venv ~/.venvs/cdp) and a chromium binary (CHROME).
Run in the background: a deploy takes 1-3 min. Does not start any agent sessions.
"""
import json, subprocess, time, urllib.request, os
import websocket

BASE = os.environ["BASE"]
KEY = open(os.environ["KEY_FILE"]).read().strip()
DEPLOY = os.environ["DEPLOY_SCRIPT"]
CHROME = os.environ.get("CHROME", os.path.expanduser("~/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome"))
PROFILE = "/tmp/update-check-profile"

def live_build():
    return json.load(urllib.request.urlopen(f"{BASE}/api/version?t={time.time()}"))["build"]

subprocess.run(["rm", "-rf", PROFILE])
proc = subprocess.Popen([CHROME, "--headless=new", "--remote-debugging-port=9334", "--remote-allow-origins=*",
                         "--no-sandbox", "--disable-gpu", f"--user-data-dir={PROFILE}", "about:blank"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
all_ok = True
def ok(cond, msg):
    global all_ok
    all_ok &= bool(cond)
    print(("PASS  " if cond else "FAIL  ") + msg, flush=True)
try:
    tabs = []
    for _ in range(50):
        try:
            tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9334/json"))
            if tabs: break
        except Exception:
            time.sleep(0.2)
    tab = [t for t in tabs if t["type"] == "page"][0]
    ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=60)
    n = [0]
    def cdp(method, **params):
        n[0] += 1; i = n[0]
        ws.send(json.dumps({"id": i, "method": method, "params": params}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == i: return m.get("result", m.get("error"))
    def js(expr):
        r = cdp("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
        return r.get("result", {}).get("value")
    def wake():
        js("window.dispatchEvent(new Event('focus'))")
    def type_text(t):  # React-controlled textarea: use the native setter + input event
        js("(() => { const el=document.querySelector('textarea'); const set=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set; set.call(el, %s); el.dispatchEvent(new Event('input',{bubbles:true})); })()" % json.dumps(t))

    cdp("Page.enable"); cdp("Runtime.enable")
    cdp("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
    cdp("Page.navigate", url=f"{BASE}/?key={KEY}"); time.sleep(7)
    b0 = live_build()
    js("window.__marker = 'old'")  # survives only if the page does NOT reload
    time.sleep(22); wake(); time.sleep(4)   # wait out the 20s check throttle
    ok(js("window.__marker") == "old", "same build: no reload on wake")

    subprocess.run(["bash", DEPLOY], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=560)
    for _ in range(60):
        if live_build() != b0: break
        time.sleep(5)
    ok(live_build() != b0, "new deployment is live")

    type_text("draft text")
    time.sleep(1); wake(); time.sleep(6)
    ok(js("window.__marker") == "old", "update found while typing: did NOT reload")
    type_text("")
    for _ in range(15):
        time.sleep(1)
        if js("window.__marker") is None: break
    ok(js("window.__marker") is None, "idle: app reloaded itself to the new version")
    time.sleep(5)
    ok(bool(js("!!document.querySelector('textarea')")), "reloaded app is signed in and working")
    js("window.__marker = 'new'")
    time.sleep(22); wake(); time.sleep(6)
    ok(js("window.__marker") == "new", "no reload loop afterwards")
finally:
    proc.kill()
print("ALL PASS" if all_ok else "SOME FAILED")
