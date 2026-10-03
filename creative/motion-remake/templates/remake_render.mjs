// remake_render.mjs — Playwright renderer for a frame-locked remake (DOM stage, one screenshot per frame).
//   node remake_render.mjs stills  out/G2 F1 F2 ...    -> out/G2/o_fNNNN.png
//   node remake_render.mjs compare out/G2 F1 F2 ...    -> out/G2/c_fNNNN.jpg (REF | OURS, labelled) + out/G2/compare_sheet.jpg
//   node remake_render.mjs full    out/full F0 F1      -> out/full/o_fNNNN.png for F0 <= F < F1
// One OUT dir per agent (out/G1, out/G2...) so parallel runs never collide. <= 15 frames per stills/compare call.
// Serves the project over HTTP itself. Shares the motion-graphics render lock (one render at a time on small boxes;
// MOTION_RENDER_SLOTS=k for k parallel agents/chunks on a bigger machine).
// Adapted from howseen-ai/claude-motion-design remake_render.py (MIT).
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { existsSync, readdirSync, readFileSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { extname, join, resolve } from 'node:path';
import { homedir } from 'node:os';
import { createRequire } from 'node:module';

const [mode, outArg, ...nums] = process.argv.slice(2);
if (!mode || !outArg) { console.error('usage: node remake_render.mjs stills|compare|full OUT F...'); process.exit(2); }
const ROOT = process.cwd(), OUT = resolve(outArg);
const P = JSON.parse(readFileSync(join(ROOT, 'project.json'), 'utf8'));
let frames = nums.map(Number);
if (mode === 'full') frames = Array.from({ length: frames[1] - frames[0] }, (_, i) => frames[0] + i);

// ---- lock (shared with motion-graphics/render.mjs)
const LOCKS = join(homedir(), '.hermes/data/motion-graphics/locks'); mkdirSync(LOCKS, { recursive: true });
const SLOTS = Number(process.env.MOTION_RENDER_SLOTS || 1);
const alive = (pid) => { try { process.kill(pid, 0); return true; } catch { return false; } };
let lockDir = null;
for (let waited = 0; !lockDir; waited += 5) {
  for (let s = 0; s < SLOTS && !lockDir; s++) {
    const d = join(LOCKS, `render.${s}`);
    try { mkdirSync(d); writeFileSync(join(d, 'pid'), String(process.pid)); lockDir = d; }
    catch { try { if (!alive(Number(readFileSync(join(d, 'pid'), 'utf8')))) rmSync(d, { recursive: true, force: true }); } catch {} }
  }
  if (!lockDir) { if (waited % 60 === 0) console.log('waiting for a render slot...'); await new Promise((r) => setTimeout(r, 5000)); }
}
const release = () => { if (lockDir) rmSync(lockDir, { recursive: true, force: true }); lockDir = null; };
process.on('exit', release); process.on('SIGINT', () => { release(); process.exit(130); });

function loadPlaywright() {
  for (const base of [ROOT, process.env.MOTION_RUNTIME, join(homedir(), '.hermes/data/motion-graphics/runtime')].filter(Boolean))
    for (const n of ['playwright', 'playwright-core']) { try { return createRequire(join(base, 'package.json'))(n); } catch {} }
  throw new Error('playwright-core not found (see motion-graphics skill runtime)');
}
function chromePath() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  const cache = join(homedir(), '.cache/ms-playwright'); if (!existsSync(cache)) return undefined;
  for (const d of readdirSync(cache).sort().reverse().filter((x) => x.startsWith('chromium_headless_shell-')))
    for (const p of [join(cache, d, 'chrome-linux64/chrome-headless-shell'), join(cache, d, 'chrome-headless-shell-linux64/chrome-headless-shell')])
      if (existsSync(p)) return p;
  return undefined;
}
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.woff': 'font/woff', '.ttf': 'font/ttf', '.otf': 'font/otf', '.webp': 'image/webp' };
const server = createServer(async (req, res) => {
  try { const p = resolve(ROOT, '.' + decodeURIComponent(new URL(req.url, 'http://x').pathname)); if (!p.startsWith(ROOT)) throw 0;
    res.writeHead(200, { 'content-type': MIME[extname(p).toLowerCase()] || 'application/octet-stream' }); res.end(await readFile(p)); }
  catch { res.writeHead(404); res.end(); }
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const { chromium } = loadPlaywright();
const browser = await chromium.launch({ executablePath: chromePath(), args: ['--no-sandbox', '--font-render-hinting=none',
  '--force-color-profile=srgb', '--run-all-compositor-stages-before-draw', '--disable-threaded-animation', '--hide-scrollbars'] });
const page = await browser.newPage({ viewport: { width: P.w, height: P.h }, deviceScaleFactor: 1 });
const errs = [];
page.on('pageerror', (e) => errs.push(String(e))); page.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text()); });
await page.goto(`http://127.0.0.1:${server.address().port}/index.html`);
await page.waitForFunction(() => window.ready === true, null, { timeout: 120000 });
await page.addStyleTag({ content: '*,*::before,*::after{transition:none!important;animation-play-state:paused!important}' });
await mkdir(OUT, { recursive: true });
const stage = await page.$('#stage');
const t0 = Date.now();
for (const [k, F] of frames.entries()) {
  await page.evaluate((t) => window.seek(t), F / P.fps);
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  await stage.screenshot({ path: join(OUT, `o_f${String(F).padStart(4, '0')}.png`) });
  if (mode === 'full' && k % P.fps === 0) console.log(`frame ${F} (${k}/${frames.length}, ${((Date.now() - t0) / 1000).toFixed(0)}s)`);
}
await browser.close(); server.close(); release();
if (errs.length) { console.error('PAGE ERRORS:\n  ' + errs.slice(0, 10).join('\n  ')); process.exitCode = 1; }

if (mode === 'compare') {                 // REF | OURS tiles + a 2-column sheet, via Python/PIL (same as remake_qa.py)
  const py = `
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
out = Path(sys.argv[1]); fr = [int(x) for x in sys.argv[2:]]
try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
except Exception: font = ImageFont.load_default()
tiles = []
for F in fr:
    ref = Image.open(f"ref/full/f{F:04d}.jpg").convert("RGB").resize((960, 540))
    ours = Image.open(out / f"o_f{F:04d}.png").convert("RGB").resize((960, 540))
    c = Image.new("RGB", (1930, 590), "white"); c.paste(ref, (0, 50)); c.paste(ours, (970, 50))
    d = ImageDraw.Draw(c); d.text((10, 8), f"REF f{F}", fill="red", font=font); d.text((980, 8), f"OURS f{F}", fill="blue", font=font)
    c.save(out / f"c_f{F:04d}.jpg", quality=85); tiles.append(c)
cols = 2; rows = -(-len(tiles) // cols)
sheet = Image.new("RGB", (cols * 965, rows * 295), "white")
for i, t in enumerate(tiles): sheet.paste(t.resize((965, 295)), ((i % cols) * 965, (i // cols) * 295))
sheet.save(out / "compare_sheet.jpg", quality=80)
print("compare ->", out / "compare_sheet.jpg")
`;
  const r = spawnSync(process.env.PYTHON || '/usr/bin/python3', ['-c', py, OUT, ...frames.map(String)], { stdio: 'inherit' });
  if (r.status) process.exitCode = 1;
} else console.log(`${mode}: ${frames.length} frames -> ${OUT} (${((Date.now() - t0) / 1000).toFixed(1)}s)`);
