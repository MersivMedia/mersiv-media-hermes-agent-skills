"""State-driven gameplay-rule test for a grid-maze arcade game (Pac-Man style).

Drives game internals over CDP (top-level let/const/functions in a classic
<script> are visible to Runtime.evaluate). It checks rules that are hard to hit
by real play:
  1. a power pickup frightens EVERY enemy, including boxed ones and ones
     released mid-power, and touching a frightened enemy eats it
  2. the lives HUD shows a label plus one icon per life, with lost lives dimmed
  3. losing the last life routes to the out-of-lives ending (optional)

Usage:
  ~/.venvs/cdp/bin/python gameplay_rules_test.py <url> <out_dir> [--lives-ending yes|no]

Expected game globals (rename below if yours differ):
  ghosts[] with .state in {active,house,leaving,eaten,entering}, .fright, .release
  player {x,y}, frighten(), checkCollisions(), resetActors(), setState(s),
  lives, updateHud(), state, score, frightTimer
  DOM: .lives-wrap, #lives .life(.gone)
  Out-of-lives ending (optional): window.__prank.state, #friends-q, #yes-btn,
  #no-btn, #final-text, #final-again
"""
import base64, json, os, subprocess, sys, tempfile, time, urllib.request
import websocket

URL, OUT = sys.argv[1], sys.argv[2]
ENDING = sys.argv[sys.argv.index('--lives-ending') + 1] if '--lives-ending' in sys.argv else None
os.makedirs(OUT, exist_ok=True)
CHROME = os.path.expanduser('~/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome')
PORT = 9337
p = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={PORT}', '--remote-allow-origins=*',
                      '--no-sandbox', f'--user-data-dir={tempfile.mkdtemp()}', 'about:blank'],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
fails = []


def check(label, ok):
    print(('PASS ' if ok else 'FAIL ') + label)
    if not ok:
        fails.append(label)


try:
    for _ in range(50):
        try:
            tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json')); break
        except Exception:
            time.sleep(0.2)
    ws = websocket.create_connection([t for t in tabs if t['type'] == 'page'][0]['webSocketDebuggerUrl'])
    mid = [0]; errors = []

    def cmd(method, **params):
        mid[0] += 1; ws.send(json.dumps({'id': mid[0], 'method': method, 'params': params}))
        while True:
            m = json.loads(ws.recv())
            if m.get('method') == 'Runtime.exceptionThrown':
                errors.append(m['params']['exceptionDetails'].get('exception', {}).get('description'))
            if m.get('id') == mid[0]:
                return m.get('result', {})

    def ev(expr):
        return cmd('Runtime.evaluate', expression=expr, returnByValue=True, awaitPromise=True).get('result', {}).get('value')

    def vis(sel):
        return ev(f'(()=>{{const e=document.querySelector({json.dumps(sel)}); if(!e) return false; const r=e.getBoundingClientRect();'
                  f' return r.width>0 && r.height>0 && getComputedStyle(e).visibility!=="hidden" && !e.closest(".hidden")}})()')

    def shot(name):
        open(f'{OUT}/{name}.png', 'wb').write(base64.b64decode(cmd('Page.captureScreenshot', format='png')['data']))

    cmd('Runtime.enable'); cmd('Page.enable')
    cmd('Emulation.setDeviceMetricsOverride', width=390, height=844, deviceScaleFactor=2, mobile=True)
    cmd('Page.navigate', url=URL); time.sleep(2)

    # 1. lives HUD
    total = ev('document.querySelectorAll("#lives .life").length')
    check(f'lives HUD has label + {total} icons', 'LIVES' in (ev('document.querySelector(".lives-wrap")?.innerText') or '') and total >= 1)

    # 2. power pickup covers boxed + released enemies
    ev('document.getElementById("start-btn")?.click()'); time.sleep(2.4)
    ev('frighten()')
    check('frighten() marks every non-eaten enemy (incl. boxed)',
          ev('ghosts.every(g => g.fright || g.state==="eaten" || g.state==="entering")'))
    ev('ghosts.forEach(g => { if (g.state==="house") g.release = 0; })'); time.sleep(1.8)
    check('released-mid-power enemies are still frightened', ev('ghosts.filter(g=>g.state==="active").every(g=>g.fright)'))
    i = ev('ghosts.findIndex((g,k)=>k>0 && g.fright && g.state==="active")')
    s0 = ev('score')
    ev(f'(()=>{{const g=ghosts[{i}]; player.x=g.x; player.y=g.y; checkCollisions(); return 1}})()')
    check('touching a released frightened enemy eats it', ev(f'ghosts[{i}].state')=='eaten' and ev('state')=='play' and ev('score')>s0)
    ev('resetActors(); setState("play"); frighten()')
    h = ev('ghosts.findIndex(g=>g.state==="house")')
    if h is not None and h >= 0:
        ev(f'(()=>{{const g=ghosts[{h}]; player.x=g.x; player.y=g.y; checkCollisions(); return 1}})()')
        check('frightened enemy inside the box is eatable', ev(f'ghosts[{h}].state')=='entering' and ev('state')=='play')
    shot('rules-fright')

    # 3. out-of-lives ending
    if ENDING:
        ev('frightTimer=0; ghosts.forEach(g=>g.fright=false); lives=1; updateHud(); resetActors(); setState("play")')
        check('HUD dims lost lives', ev('document.querySelectorAll("#lives .life:not(.gone)").length') == 1)
        ev('(()=>{const g=ghosts.find(g=>g.state==="active"); player.x=g.x; player.y=g.y; checkCollisions(); return 1})()')
        for _ in range(60):
            if ev('window.__prank && __prank.state') == 'asking': break
            time.sleep(0.25)
        check('last life -> friends question', vis('#yes-btn') and vis('#no-btn'))
        print('   question:', ev('document.getElementById("friends-q")?.innerText'))
        ev(f'document.getElementById("{"yes" if ENDING=="yes" else "no"}-btn").click()'); time.sleep(0.8)
        print('   final text:', ev('document.getElementById("final-text").innerText'))
        check('try-again button only on YES', vis('#final-again') == (ENDING == 'yes'))
        if ENDING == 'yes':
            ev('document.getElementById("final-again").click()'); time.sleep(0.6)
            check('TRY AGAIN = full reset to start screen', ev('state')=='start' and vis('#overlay-start .card')
                  and ev('document.querySelectorAll("#lives .life:not(.gone)").length') == total)
        shot(f'rules-ending-{ENDING}')
    check('no JS errors', not errors)
    if errors:
        print(errors)
finally:
    p.kill()
sys.exit(1 if fails else 0)
