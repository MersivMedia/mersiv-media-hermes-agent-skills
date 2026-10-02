"""Headless desktop + phone smoke test for a canvas game, run over raw CDP.

Usage: python cdp_game_test.py <url-or-file://> <out_dir> [hook_name]
Requires: websocket-client (venv), Playwright Chromium at CHROME below.
The page is expected to expose window.<hook_name> (default __game) with:
  state (getter), hearts|score (getter), eatAll(), steer(dir)
It also expects #start-btn, #dpad .left, #game (canvas), and #win (a dialog
hidden via the .hidden class). Change the selectors to match the game.
"""
import base64, json, os, subprocess, sys, tempfile, time, urllib.request
import websocket

CHROME = os.path.expanduser('~/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome')
URL, OUT = sys.argv[1], sys.argv[2]
HOOK = sys.argv[3] if len(sys.argv) > 3 else '__game'
PORT = 9333
os.makedirs(OUT, exist_ok=True)
proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={PORT}', '--remote-allow-origins=*',
                         '--no-sandbox', '--autoplay-policy=no-user-gesture-required',
                         f'--user-data-dir={tempfile.mkdtemp()}', '--allow-file-access-from-files', 'about:blank'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
VK = {'ArrowLeft': 37, 'ArrowUp': 38, 'ArrowRight': 39, 'ArrowDown': 40, 'Enter': 13}
try:
    for _ in range(50):
        try:
            page = next(t for t in json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json')) if t['type'] == 'page')
            break
        except Exception:
            time.sleep(0.2)
    ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=30)
    mid, errors = [0], []

    def cmd(method, **params):
        mid[0] += 1
        ws.send(json.dumps({'id': mid[0], 'method': method, 'params': params}))
        while True:
            m = json.loads(ws.recv())
            if m.get('method') == 'Runtime.exceptionThrown':
                errors.append(m['params']['exceptionDetails'].get('exception', {}).get('description'))
            if m.get('id') == mid[0]:
                return m.get('result', m.get('error'))

    def ev(expr):
        r = cmd('Runtime.evaluate', expression=expr, returnByValue=True, awaitPromise=True)
        return r.get('result', {}).get('value', r.get('result', {}).get('description'))

    def shot(name):
        open(f'{OUT}/{name}.png', 'wb').write(base64.b64decode(cmd('Page.captureScreenshot', format='png')['data']))
        print('screenshot', f'{OUT}/{name}.png')

    def key(k):
        for t in ('keyDown', 'keyUp'):
            cmd('Input.dispatchKeyEvent', type=t, key=k, code=k, windowsVirtualKeyCode=VK[k])

    def tap(sel):
        b = json.loads(ev(f'JSON.stringify(document.querySelector("{sel}").getBoundingClientRect())'))
        x, y = b['x'] + b['width'] / 2, b['y'] + b['height'] / 2
        cmd('Input.dispatchTouchEvent', type='touchStart', touchPoints=[{'x': x, 'y': y}])
        cmd('Input.dispatchTouchEvent', type='touchEnd', touchPoints=[])

    def swipe(sel, dx, dy):
        b = json.loads(ev(f'JSON.stringify(document.querySelector("{sel}").getBoundingClientRect())'))
        x, y = b['x'] + b['width'] / 2, b['y'] + b['height'] / 2
        cmd('Input.dispatchTouchEvent', type='touchStart', touchPoints=[{'x': x, 'y': y}])
        for i in range(1, 6):
            cmd('Input.dispatchTouchEvent', type='touchMove', touchPoints=[{'x': x + dx * i / 5, 'y': y + dy * i / 5}])
        cmd('Input.dispatchTouchEvent', type='touchEnd', touchPoints=[])

    H = f'window.{HOOK}'
    cmd('Runtime.enable'); cmd('Page.enable')

    # Desktop
    cmd('Emulation.setDeviceMetricsOverride', width=1280, height=900, deviceScaleFactor=1, mobile=False)
    cmd('Page.navigate', url=URL); time.sleep(2.5)
    shot('1-desktop-start')
    print('dpad on desktop (want none):', ev('getComputedStyle(document.getElementById("dpad")).display'))
    key('Enter'); time.sleep(2.3)
    print('state:', ev(f'{H}.state'), 'count:', ev(f'{H}.hearts'))
    key('ArrowLeft'); time.sleep(1.2); key('ArrowUp'); time.sleep(1.5)
    print('count after keys (want lower):', ev(f'{H}.hearts'))
    shot('2-desktop-play')
    time.sleep(25)
    print('lives after idle (want fewer):', ev('document.getElementById("lives").textContent'))
    ev(f'{H}.eatAll()'); key('ArrowRight'); time.sleep(0.6); key('ArrowLeft'); time.sleep(2.5)
    print('win visible:', ev('!document.getElementById("win").classList.contains("hidden")'))
    shot('3-desktop-win')

    # Phone
    cmd('Emulation.setDeviceMetricsOverride', width=390, height=844, deviceScaleFactor=3, mobile=True)
    cmd('Emulation.setTouchEmulationEnabled', enabled=True, maxTouchPoints=5)
    cmd('Page.navigate', url=URL); time.sleep(2.5)
    print('dpad on phone (want grid):', ev('getComputedStyle(document.getElementById("dpad")).display'))
    print('fits (scrollH<=vh):', ev('document.documentElement.scrollHeight <= innerHeight'))
    shot('4-phone-start')
    tap('#dpad .left'); time.sleep(3.2)
    print('phone state after dpad:', ev(f'{H}.state'), 'count:', ev(f'{H}.hearts'))
    swipe('#game', 0, -50); time.sleep(1.0)
    print('count after swipe:', ev(f'{H}.hearts'), 'scrollY (want 0):', ev('scrollY'))
    shot('5-phone-play')
    print('JS errors:', errors or 'none')
finally:
    proc.kill()
