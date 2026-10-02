"""Live spoiler + preview-link probe for a deployed arcade game.

Usage:
  ~/.venvs/cdp/bin/python check_preview.py https://<name>.vercel.app <prize>,<words> [shot.png]

Checks, in an emulated 390x844 phone viewport:
  1. the start overlay (#overlay-start) contains none of the comma-separated prize words
  2. /?preview=prize shows the win dialog (#win without .hidden)
Saves a screenshot of the preview page if a path is given. Exit 1 on failure.
Adjust the selectors if the game uses different ids.
"""
import base64, json, os, subprocess, sys, tempfile, time, urllib.request
import websocket

CHROME = os.path.expanduser('~/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome')
url, words = sys.argv[1].rstrip('/'), [w.strip().lower() for w in sys.argv[2].split(',') if w.strip()]
shot = sys.argv[3] if len(sys.argv) > 3 else None
p = subprocess.Popen([CHROME, '--headless=new', '--remote-debugging-port=9334', '--remote-allow-origins=*',
                      '--no-sandbox', f'--user-data-dir={tempfile.mkdtemp()}', 'about:blank'],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ok = True
try:
    for _ in range(50):
        try:
            page = next(t for t in json.load(urllib.request.urlopen('http://127.0.0.1:9334/json')) if t['type'] == 'page'); break
        except Exception:
            time.sleep(0.2)
    ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=30); n = [0]
    def cmd(m, **kw):
        n[0] += 1; ws.send(json.dumps({'id': n[0], 'method': m, 'params': kw}))
        while True:
            r = json.loads(ws.recv())
            if r.get('id') == n[0]: return r.get('result', {})
    ev = lambda e: cmd('Runtime.evaluate', expression=e, returnByValue=True)['result'].get('value')
    cmd('Emulation.setDeviceMetricsOverride', width=390, height=844, deviceScaleFactor=2, mobile=True)
    cmd('Page.navigate', url=f'{url}/?v={time.time()}'); time.sleep(3)
    start = (ev('(document.getElementById("overlay-start")||{}).innerText||""') or '').lower()
    leaks = [w for w in words if w in start]
    print('start overlay:', repr(start[:120])); print('prize words leaked:', leaks or 'none')
    ok &= not leaks
    cmd('Page.navigate', url=f'{url}/?preview=prize'); time.sleep(3)
    win = ev('!!document.getElementById("win") && !document.getElementById("win").classList.contains("hidden")')
    print('preview shows win:', win); ok &= bool(win)
    if shot:
        open(shot, 'wb').write(base64.b64decode(cmd('Page.captureScreenshot')['data'])); print('screenshot', shot)
finally:
    p.kill()
sys.exit(0 if ok else 1)
