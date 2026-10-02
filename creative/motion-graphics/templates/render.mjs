// render.mjs — walk time, call window.seek(t), pipe frames into ffmpeg.
// Usage:
//   node render.mjs --w 1080 --h 1920 --fps 60 --dur 15 --sub 4 --out out/silent.mp4
//   node render.mjs --w 1080 --h 1920 --stills 0.5,1,2.5 --outdir out/stills     (PNG stills, for critique)
//   node render.mjs ... --from 4 --to 6 --out out/part.mp4                         (re-render only a range)
// --sub N renders N subframes per output frame and blends them (motion blur). --sub 1 = no blur.
// Serves the project folder over a local HTTP server (ES modules + fetch don't work over file://).
import { createServer } from 'node:http';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { existsSync, readdirSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { extname, join, resolve, dirname } from 'node:path';
import { homedir } from 'node:os';
import { createRequire } from 'node:module';

const argv = process.argv.slice(2);
const arg = (k, d) => { const i = argv.indexOf('--' + k); return i >= 0 ? argv[i + 1] : d; };
const num = (k, d) => Number(arg(k, d));
const W = num('w', 1080), H = num('h', 1920), FPS = num('fps', 60), SUB = num('sub', 4);
const PAGE = arg('page', 'index.html'), ROOT = resolve(arg('root', '.'));
const OUT = arg('out', 'out/silent.mp4'), STILLS = arg('stills', null), OUTDIR = arg('outdir', 'out/stills');

// playwright-core from the project, or from the skill's shared runtime
function loadPlaywright() {
  const tries = [process.cwd(), process.env.MOTION_RUNTIME, join(homedir(), '.hermes/data/motion-graphics/runtime')];
  for (const base of tries.filter(Boolean)) {
    for (const name of ['playwright', 'playwright-core']) {
      try { return createRequire(join(base, 'package.json'))(name); } catch {}
    }
  }
  throw new Error('playwright not found: npm i -D playwright-core (or set MOTION_RUNTIME)');
}
function chromePath() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  const cache = join(homedir(), '.cache/ms-playwright');
  if (!existsSync(cache)) return undefined;
  const dirs = readdirSync(cache).sort().reverse();
  for (const d of dirs.filter((x) => x.startsWith('chromium_headless_shell-'))) {
    const p = join(cache, d, 'chrome-linux64/chrome-headless-shell'); if (existsSync(p)) return p;
    const p2 = join(cache, d, 'chrome-headless-shell-linux64/chrome-headless-shell'); if (existsSync(p2)) return p2;
  }
  for (const d of dirs.filter((x) => x.startsWith('chromium-'))) {
    const p = join(cache, d, 'chrome-linux64/chrome'); if (existsSync(p)) return p;
  }
  return undefined;                                   // let playwright use its own default
}

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.ttf': 'font/ttf',
  '.otf': 'font/otf', '.css': 'text/css', '.wav': 'audio/wav', '.mp4': 'video/mp4', '.webp': 'image/webp' };
const server = createServer(async (req, res) => {
  try {
    const p = resolve(ROOT, '.' + decodeURIComponent(new URL(req.url, 'http://x').pathname));
    if (!p.startsWith(ROOT)) throw new Error('outside root');
    const body = await readFile(p);
    res.writeHead(200, { 'content-type': MIME[extname(p)] || 'application/octet-stream' }); res.end(body);
  } catch { res.writeHead(404); res.end(); }
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const url = `http://127.0.0.1:${server.address().port}/${PAGE}?w=${W}&h=${H}`;

const { chromium } = loadPlaywright();
const browser = await chromium.launch({ executablePath: chromePath(), args: ['--no-sandbox', '--force-color-profile=srgb'] });
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
page.on('pageerror', (e) => { console.error('page error:', e.message); process.exitCode = 1; });
await page.goto(url);
await page.waitForFunction(() => typeof window.seek === 'function');
await page.evaluate(() => window.ready || true);
await page.evaluate(() => document.fonts.ready);
const DUR = num('dur', await page.evaluate(() => (window.FILM && window.FILM.dur) || 15));
const FROM = num('from', 0), TO = num('to', DUR);

// Grab the canvas as PNG bytes. Exact pixel size, no browser chrome, no viewport cropping.
const grab = async (t) => {
  const b64 = await page.evaluate(async (t) => {
    window.seek(t);
    const c = document.querySelector('canvas');
    const blob = await new Promise((r) => c.toBlob(r, 'image/png'));
    const buf = new Uint8Array(await blob.arrayBuffer());
    let s = ''; for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
    return btoa(s);
  }, t);
  return Buffer.from(b64, 'base64');
};

if (STILLS) {
  await mkdir(OUTDIR, { recursive: true });
  for (const t of STILLS.split(',').map(Number)) {
    const f = join(OUTDIR, `t${t.toFixed(2).padStart(6, '0')}.png`);
    await writeFile(f, await grab(t)); console.log('still', f);
  }
} else {
  await mkdir(dirname(OUT), { recursive: true });
  const vf = SUB > 1 ? `tmix=frames=${SUB},select='eq(mod(n\\,${SUB})\\,${SUB - 1})',setpts=N/${FPS}/TB` : 'null';
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS * SUB), '-i', '-',
    '-vf', vf, '-r', String(FPS), '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', '-pix_fmt', 'yuv420p',
    '-movflags', '+faststart', OUT], { stdio: ['pipe', 'inherit', 'inherit'] });
  const total = Math.round((TO - FROM) * FPS * SUB), t0 = Date.now();
  for (let i = 0; i < total; i++) {
    const png = await grab(FROM + i / (FPS * SUB));
    if (!ff.stdin.write(png)) await new Promise((r) => ff.stdin.once('drain', r));
    if (i % (FPS * SUB) === 0) console.log(`rendered ${(i / (FPS * SUB)).toFixed(0)}s / ${(TO - FROM)}s  (${((Date.now() - t0) / 1000).toFixed(0)}s elapsed)`);
  }
  ff.stdin.end();
  const code = await new Promise((r) => ff.on('close', r));
  if (code !== 0) { console.error('ffmpeg failed'); process.exitCode = 1; } else console.log('wrote', OUT);
}
await browser.close(); server.close();
