"""Generate favicon, home-screen icon and link-preview (og:image) from the game's REAL sprite data.

Template from the gift-game build. Adapt the marked spots per game:
  * the slice markers that cut the sprite block out of game.js
  * which sprite/palette is the icon (here SQUIRRELS[1] = the pink one)
  * the og() layout: title, tagline, a maze lane, hero + enemies, footer line
Pulls sprite arrays straight out of game.js, renders on canvases in headless Chromium,
writes PNG/JPEG into the site root. Run from repo root:  python .test/make_share_assets.py
Needs: Playwright Chromium + a venv with websocket-client.
"""
import base64, json, os, subprocess, tempfile, time, urllib.request
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = os.path.expanduser('~/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome')

src = open(os.path.join(ROOT, 'game.js')).read()
# ADAPT: everything between these two comments must be self-contained sprite consts
sprites = src[src.index('// Squirrel, facing right'):src.index('// Boss')]

PAGE = r'''<!DOCTYPE html><html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Press+Start+2P&family=Nunito:wght@800&display=swap" rel="stylesheet">
</head><body style="margin:0;background:#000">
<script>
const COLS = 19, ROWS = 21;   // sprite block references these
/*SPRITES*/
function px(c, rows, pal, x, y, s, flip) {
  const w = rows[0].length;
  rows.forEach((r, j) => r.split('').forEach((ch, i) => {
    const col = pal[ch]; if (!col) return;
    c.fillStyle = col;
    c.fillRect(x + (flip ? w - 1 - i : i) * s, y + j * s, s, s);
  }));
}
function hero(c, x, y, s, mouth, face) {      // same pixel rule as drawPlayer() in game.js
  c.fillStyle = '#ffd23f';
  for (let j = 0; j < 15; j++) for (let i = 0; i < 15; i++) {
    const dx = i - 7, dy = j - 7;
    if (dx * dx + dy * dy > 51) continue;
    let a = Math.atan2(dy, dx) - face; a = Math.atan2(Math.sin(a), Math.cos(a));
    if (Math.abs(a) < mouth && dx * dx + dy * dy > 1) continue;
    c.fillRect(x + i * s, y + j * s, s, s);
  }
}
function rr(c, x, y, w, h, r) { c.beginPath(); c.roundRect(x, y, w, h, r); }
const iconPal = () => ({ ...SQUIRRELS[1].pal, ...EYES });   // ADAPT: icon character

// round=true for tab favicons; iOS masks apple-touch-icon itself, so give it a full square
function icon(size, round) {
  const cv = document.createElement('canvas'); cv.width = cv.height = size;
  const c = cv.getContext('2d');
  c.fillStyle = '#2a0d45';
  if (round) { rr(c, 0, 0, size, size, size * 0.18); c.fill(); } else c.fillRect(0, 0, size, size);
  const s = Math.floor(size / 16);                  // 14px sprite + 1px margin each side
  const off = Math.floor((size - 14 * s) / 2);
  px(c, SQUIRREL_A, iconPal(), off, off, s, false);
  return cv.toDataURL('image/png');
}

async function og() {
  await document.fonts.load('72px "Press Start 2P"');   // fonts MUST be loaded before fillText
  await document.fonts.load('800 32px Nunito');
  const W = 1200, H = 630;
  const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
  const c = cv.getContext('2d');
  const g = c.createRadialGradient(W / 2, 0, 50, W / 2, 0, 900);
  g.addColorStop(0, '#2a0d45'); g.addColorStop(0.6, '#120724'); g.addColorStop(1, '#08030f');
  c.fillStyle = g; c.fillRect(0, 0, W, H);
  c.strokeStyle = '#ff6fae'; c.lineWidth = 8; rr(c, 14, 14, W - 28, H - 28, 26); c.stroke();

  c.textAlign = 'center';
  c.font = '64px "Press Start 2P"';
  c.fillStyle = '#7a1449'; c.fillText('Heart Maze', W / 2 + 6, 142);
  c.fillStyle = '#ff6fae'; c.fillText('Heart Maze', W / 2, 136);
  c.font = '800 34px Nunito'; c.fillStyle = '#ffd6ec';
  c.fillText("Eat every heart before the ghosts get you!", W / 2, 212);

  const top = 262, laneY = 312, laneH = 150, bot = laneY + laneH;       // maze lane
  c.fillStyle = '#2b0f47'; c.strokeStyle = '#ff6fae'; c.lineWidth = 4;
  rr(c, 60, top, W - 120, laneY - top - 8, 12); c.fill(); c.stroke();
  rr(c, 60, bot + 8, W - 120, 50, 12); c.fill(); c.stroke();

  const s = 6, cy = laneY + laneH / 2;
  px(c, HEART_BIG, HEART_PAL, 84, cy - 4 * s, s, false);
  for (const hx of [190, 262]) px(c, HEART_SMALL, HEART_PAL, hx, cy - 2 * s, s, false);
  hero(c, 330, cy - 7.5 * s, s, 0.62, Math.PI);                              // fleeing left
  SQUIRRELS.forEach((sq, n) =>
    px(c, n % 2 ? SQUIRREL_B : SQUIRREL_A, { ...sq.pal, ...EYES }, 540 + n * 140, cy - 7 * s, s, true));

  // footer: centre the whole "TEXT ♥ TEXT" group by measuring it
  c.font = '22px "Press Start 2P"'; c.fillStyle = '#ffd23f';
  const a = '3 LEVELS', b = '1 SPECIAL PRIZE', gap = 22, hw = 5 * 6;
  const total = c.measureText(a).width + gap + hw + gap + c.measureText(b).width;
  let x0 = (W - total) / 2;
  c.textAlign = 'left';
  c.fillText(a, x0, 580); x0 += c.measureText(a).width + gap;
  px(c, HEART_SMALL, HEART_PAL, x0, 558, 6, false); x0 += hw + gap;
  c.fillStyle = '#ffd23f';               // px() leaves the last sprite colour set: reset before text
  c.fillText(b, x0, 580);
  return cv.toDataURL('image/jpeg', 0.92);  // JPEG: ~88 KB vs ~600 KB PNG; big previews get dropped
}

window.makeAll = async () => ({ fav32: icon(32, true), fav192: icon(192, true), apple: icon(180, false), og: await og() });
</script></body></html>'''.replace('/*SPRITES*/', sprites)

page = os.path.join(ROOT, '.test', 'shots', 'make_assets.html')
os.makedirs(os.path.dirname(page), exist_ok=True)
open(page, 'w').write(PAGE)

port = 9338
prof = tempfile.mkdtemp()
p = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={port}', '--remote-allow-origins=*',
                      '--no-sandbox', f'--user-data-dir={prof}', 'about:blank'],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    tabs = []
    for _ in range(80):
        try:
            tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json'))
            if any(t['type'] == 'page' for t in tabs):
                break
        except Exception:
            pass
        time.sleep(0.2)
    ws = websocket.create_connection([t for t in tabs if t['type'] == 'page'][0]['webSocketDebuggerUrl'])
    n = [0]

    def cdp(method, **params):
        n[0] += 1
        ws.send(json.dumps({'id': n[0], 'method': method, 'params': params}))
        while True:
            m = json.loads(ws.recv())
            if m.get('id') == n[0]:
                return m

    cdp('Page.enable')
    cdp('Page.navigate', url='file://' + page)
    time.sleep(3)
    r = cdp('Runtime.evaluate', expression='makeAll()', awaitPromise=True, returnByValue=True)
    if 'exceptionDetails' in r.get('result', {}):
        raise SystemExit(r['result']['exceptionDetails'])
    out = r['result']['result']['value']
    names = {'fav32': 'favicon-32.png', 'fav192': 'icon-192.png', 'apple': 'apple-touch-icon.png', 'og': 'og-image.jpg'}
    for k, fn in names.items():
        data = base64.b64decode(out[k].split(',', 1)[1])
        open(os.path.join(ROOT, fn), 'wb').write(data)
        print('wrote', fn, len(data), 'bytes')
finally:
    p.kill()
