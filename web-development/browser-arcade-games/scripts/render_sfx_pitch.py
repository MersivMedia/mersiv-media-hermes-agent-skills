"""Render a WebAudio SFX function offline (HEAD vs working copy) and estimate its pitch.

Usage:
  ~/.venvs/cdp/bin/python render_sfx_pitch.py <game_dir> <js_file> <start_marker> <end_marker> <call> [out_dir]

  start_marker/end_marker: substrings bracketing the SFX function (and its constants)
  in <js_file>. Anything the function needs (e.g. noise helpers) must fall inside
  that range or be stubbed below.
  call: JS that triggers it, e.g. "evilLaugh(0, 7)".

Example (gift game):
  render_sfx_pitch.py ~/<game> prank.js 'function noise(' 'const prankSfx' 'evilLaugh(0, 7)'

Prints f0 estimates at 0.1s windows for old vs new, and writes laugh-old.wav / laugh-new.wav.
Needs headless Chromium + websocket-client (see SKILL.md Prerequisites).
"""
import json, os, struct, subprocess, sys, tempfile, time, urllib.request, wave
import websocket

game_dir, js_file, start_m, end_m, call = sys.argv[1:6]
out_dir = sys.argv[6] if len(sys.argv) > 6 else os.path.join(game_dir, '.test', 'shots')
os.makedirs(out_dir, exist_ok=True)
CHROME = os.environ.get('CHROME', os.path.expanduser('~/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome'))
SR = 44100

old_src = subprocess.run(['git', 'show', f'HEAD:{js_file}'], cwd=game_dir, capture_output=True, text=True).stdout
new_src = open(os.path.join(game_dir, js_file)).read()

port = 9338
p = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={port}', '--remote-allow-origins=*',
                      '--no-sandbox', f'--user-data-dir={tempfile.mkdtemp()}', 'about:blank'],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            page = next(t for t in json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json')) if t['type'] == 'page')
            break
        except Exception:
            time.sleep(0.2)
    ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=60)
    n = [0]

    def cmd(m, **kw):
        n[0] += 1
        ws.send(json.dumps({'id': n[0], 'method': m, 'params': kw}))
        while True:
            r = json.loads(ws.recv())
            if r.get('id') == n[0]:
                return r.get('result', {})

    def render(src):
        body = src[src.index(start_m):src.index(end_m)]
        js = f'''(async () => {{
          const oc = new OfflineAudioContext(1, {SR} * 3, {SR});
          const audio = () => oc, muted = false;
          {body}
          {call};
          const buf = await oc.startRendering();
          return Array.from(buf.getChannelData(0));
        }})()'''
        r = cmd('Runtime.evaluate', expression=js, awaitPromise=True, returnByValue=True)
        if 'exceptionDetails' in r:
            sys.exit(f"render error: {r['exceptionDetails']}")
        return r['result']['value']

    def f0(seg, lo=50, hi=400):
        best, bl = 0, 0
        for lag in range(SR // hi, SR // lo):
            c = sum(seg[i] * seg[i + lag] for i in range(0, len(seg) - lag, 2))
            if c > best:
                best, bl = c, lag
        return SR / bl if bl else 0

    for label, src in (('old', old_src), ('new', new_src)):
        s = render(src)
        with wave.open(os.path.join(out_dir, f'sfx-{label}.wav'), 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            peak = max(1e-9, max(abs(x) for x in s))
            w.writeframes(b''.join(struct.pack('<h', int(x / peak * 30000)) for x in s))
        est = []
        for k in range(1, 20):
            st = int(k * 0.1 * SR)
            seg = s[st:st + int(0.06 * SR)]
            if max((abs(x) for x in seg), default=0) > 0.02:
                est.append(round(f0(seg)))
        print(f'{label}: f0 per 0.1s window (voiced only): {est}')
finally:
    p.kill()
