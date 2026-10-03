// render.mjs — walk time, call window.seek(t), encode with ffmpeg.
//
//   node render.mjs --draft                           fast rhythm check: short side 540, 30 fps, no blur, CRF 23
//   node render.mjs --w 1080 --h 1920 --fps 60 --sub 8 --adaptive --out out/silent.mp4      master
//   node render.mjs --stills 0.5,2,4.1 --outdir out/stills                                 PNG stills
//   node render.mjs --beats                           one still per beat (beats.json) -> out/beats/
//   node render.mjs ... --from 4 --to 6 --out out/part.mp4                                 re-render a range
//
// Motion blur: --sub N subframes per output frame spread over --shutter of the frame interval
// (0.5 = 180° film shutter, 1.0 = smeary), centred on the frame time and averaged IN THE PAGE
// (one PNG per output frame, so it costs N seeks, not N PNG encodes). Subframes never straddle a hard cut
// (--cuts 3.2,7.5 or FILM.cuts). --adaptive measures motion per frame: still -> 1 sample, slow -> 4, fast -> N.
// 4 subframes ghost on fast moves: use 8 for slams and whips.
// --scale 2 supersamples (render 2x, Lanczos down): razor-sharp type, cheaper than blur on static text.
// --capture dom: for films built from DOM elements instead of one canvas (screenshots #stage after 2 rAF;
//   blur then uses ffmpeg tmix, fixed N, no adaptive).
// Output: H.264 yuv420p, BT.709 TV range (tagged), +faststart; frame count is verified after encode.
// One render at a time machine-wide (lock in ~/.hermes/data/motion-graphics/locks); MOTION_RENDER_SLOTS=k
// allows k concurrent renders (chunks.sh sets it). Serves the project over HTTP (ES modules + fetch fail on file://).
import { createServer } from 'node:http';
import { readFile, mkdir, writeFile, rm } from 'node:fs/promises';
import { existsSync, readdirSync, mkdirSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { spawn, spawnSync } from 'node:child_process';
import { extname, join, resolve, dirname } from 'node:path';
import { homedir } from 'node:os';
import { createRequire } from 'node:module';

const argv = process.argv.slice(2);
const has = (k) => argv.includes('--' + k);
const arg = (k, d) => { const i = argv.indexOf('--' + k); return i >= 0 && argv[i + 1] !== undefined && !argv[i + 1].startsWith('--') ? argv[i + 1] : d; };
const num = (k, d) => Number(arg(k, d));
const DRAFT = has('draft');
let W = num('w', 1080), H = num('h', 1920);
if (DRAFT) { const f = 540 / Math.min(W, H); W = Math.round(W * f / 2) * 2; H = Math.round(H * f / 2) * 2; }
const FPS = num('fps', DRAFT ? 30 : 60), SUB = DRAFT ? 1 : num('sub', 4), SHUTTER = num('shutter', 0.5);
const SCALE = DRAFT ? 1 : num('scale', 1), ADAPTIVE = has('adaptive'), CAPTURE = arg('capture', 'canvas');
const CRF = num('crf', DRAFT ? 23 : 16), PRESET = arg('preset', DRAFT ? 'veryfast' : 'medium');
const PAGE = arg('page', 'index.html'), ROOT = resolve(arg('root', '.'));
const OUT = arg('out', DRAFT ? 'out/draft.mp4' : 'out/silent.mp4'), STILLS = arg('stills', null);
const OUTDIR = arg('outdir', has('beats') ? 'out/beats' : 'out/stills');

// ---------- machine-wide render lock (small boxes swap to death with two Chromiums encoding at once)
const LOCKS = join(homedir(), '.hermes/data/motion-graphics/locks'); mkdirSync(LOCKS, { recursive: true });
const SLOTS = Number(process.env.MOTION_RENDER_SLOTS || 1);
const alive = (pid) => { try { process.kill(pid, 0); return true; } catch { return false; } };
let lockDir = null;
async function takeLock() {
  if (has('no-lock')) return;
  for (let waited = 0; ; waited += 5) {
    for (let s = 0; s < SLOTS; s++) {
      const d = join(LOCKS, `render.${s}`);
      try { mkdirSync(d); writeFileSync(join(d, 'pid'), String(process.pid)); lockDir = d; return; }
      catch { try { const pid = Number(readFileSync(join(d, 'pid'), 'utf8')); if (!alive(pid)) rmSync(d, { recursive: true, force: true }); } catch {} }
    }
    if (waited % 60 === 0) console.log(`waiting for a render slot (${SLOTS} in use, ${waited}s)...`);
    await new Promise((r) => setTimeout(r, 5000));
  }
}
const releaseLock = () => { if (lockDir) { rmSync(lockDir, { recursive: true, force: true }); lockDir = null; } };
process.on('exit', releaseLock); process.on('SIGINT', () => { releaseLock(); process.exit(130); });

// ---------- browser
function loadPlaywright() {
  const tries = [process.cwd(), process.env.MOTION_RUNTIME, join(homedir(), '.hermes/data/motion-graphics/runtime')];
  for (const base of tries.filter(Boolean)) for (const name of ['playwright', 'playwright-core']) {
    try { return createRequire(join(base, 'package.json'))(name); } catch {}
  }
  throw new Error('playwright not found: npm i -D playwright-core (or set MOTION_RUNTIME)');
}
function chromePath() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  const cache = join(homedir(), '.cache/ms-playwright'); if (!existsSync(cache)) return undefined;
  const dirs = readdirSync(cache).sort().reverse();
  for (const d of dirs.filter((x) => x.startsWith('chromium_headless_shell-')))
    for (const p of [join(cache, d, 'chrome-linux64/chrome-headless-shell'), join(cache, d, 'chrome-headless-shell-linux64/chrome-headless-shell')])
      if (existsSync(p)) return p;
  for (const d of dirs.filter((x) => x.startsWith('chromium-'))) { const p = join(cache, d, 'chrome-linux64/chrome'); if (existsSync(p)) return p; }
  return undefined;
}
// Flags for pixel-identical reruns; WEBGL=1 adds SwiftShader/ANGLE (headless WebGL renders black otherwise).
const FLAGS = ['--no-sandbox', '--force-color-profile=srgb', '--run-all-compositor-stages-before-draw', '--disable-threaded-animation',
  '--disable-checker-imaging', '--font-render-hinting=none', '--autoplay-policy=no-user-gesture-required', '--hide-scrollbars'];
if (process.env.WEBGL) FLAGS.push('--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist');

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.woff': 'font/woff',
  '.ttf': 'font/ttf', '.otf': 'font/otf', '.css': 'text/css', '.wav': 'audio/wav', '.mp3': 'audio/mpeg', '.mp4': 'video/mp4', '.webp': 'image/webp' };
const server = createServer(async (req, res) => {
  try {
    const p = resolve(ROOT, '.' + decodeURIComponent(new URL(req.url, 'http://x').pathname));
    if (!p.startsWith(ROOT)) throw new Error('outside root');
    const body = await readFile(p);
    res.writeHead(200, { 'content-type': MIME[extname(p).toLowerCase()] || 'application/octet-stream' }); res.end(body);
  } catch { res.writeHead(404); res.end(); }
});

await takeLock();
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const RW = CAPTURE === 'canvas' ? W * SCALE : W, RH = CAPTURE === 'canvas' ? H * SCALE : H;   // canvas supersamples via its size
const url = `http://127.0.0.1:${server.address().port}/${PAGE}?w=${RW}&h=${RH}&render=1`;
const { chromium } = loadPlaywright();
const browser = await chromium.launch({ executablePath: chromePath(), args: FLAGS });
const page = await browser.newPage({ viewport: { width: RW, height: RH }, deviceScaleFactor: CAPTURE === 'dom' ? SCALE : 1 });
const errors = [];
page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') errors.push(`console.${m.type()}: ${m.text()}`); });
await page.goto(url);
await page.waitForFunction(() => typeof window.seek === 'function', null, { timeout: 120000 });
await page.evaluate(async () => { await (window.ready || true); await document.fonts.ready; });
// freeze anything on the wall clock: CSS transitions/animations, Web Animations
await page.addStyleTag({ content: '*,*::before,*::after{transition:none!important;animation-play-state:paused!important;caret-color:transparent!important}' });
await page.evaluate(() => document.getAnimations().forEach((a) => a.pause()));
const FILM = await page.evaluate(() => window.FILM || {});
const DUR = num('dur', FILM.dur || 15), FROM = num('from', 0), TO = Math.min(num('to', DUR), DUR);
const CUTS = (arg('cuts', null) ? arg('cuts').split(',').map(Number) : FILM.cuts || []).filter((c) => c > 0);

// ---------- page-side capture helpers
await page.evaluate(({ RW, RH }) => {
  const toB64 = async (canvas) => {
    const blob = await new Promise((r) => canvas.toBlob(r, 'image/png'));
    const buf = new Uint8Array(await blob.arrayBuffer()); let s = '';
    for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
    return btoa(s);
  };
  const src = () => document.querySelector('#c') || document.querySelector('canvas');
  const out = document.createElement('canvas'); out.width = RW; out.height = RH; const og = out.getContext('2d');
  const thumb = document.createElement('canvas'); thumb.width = 96; thumb.height = Math.max(1, Math.round(96 * RH / RW));
  const tg = thumb.getContext('2d', { willReadFrequently: true });
  const small = async (t) => { await window.seek(t); tg.drawImage(src(), 0, 0, thumb.width, thumb.height); return tg.getImageData(0, 0, thumb.width, thumb.height).data; };
  window.__cap = {
    async one(t) { await window.seek(t); return toB64(src()); },
    async motion(a, b) { const x = await small(a), y = await small(b); let d = 0; for (let i = 0; i < x.length; i += 4) d += Math.abs(x[i] - y[i]) + Math.abs(x[i + 1] - y[i + 1]) + Math.abs(x[i + 2] - y[i + 2]); return d / (x.length * 0.75); },
    async blend(times) {
      if (times.length === 1) return this.one(times[0]);
      let acc = null;
      for (const t of times) {
        await window.seek(t);
        const px = src().getContext('2d').getImageData(0, 0, RW, RH).data;
        if (!acc) acc = new Float32Array(px.length);
        for (let i = 0; i < px.length; i++) acc[i] += px[i];
      }
      const img = og.createImageData(RW, RH), n = times.length;
      for (let i = 0; i < acc.length; i++) img.data[i] = acc[i] / n + 0.5;
      og.putImageData(img, 0, 0); return toB64(out);
    },
  };
}, { RW, RH });
const raf2 = () => page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
async function grab(t) {                                                   // one exact frame as PNG bytes
  if (CAPTURE === 'dom') { await page.evaluate((t) => window.seek(t), t); await raf2();
    const el = (await page.$('#stage')) || page; return el.screenshot({ type: 'png' }); }
  return Buffer.from(await page.evaluate((t) => window.__cap.one(t), t), 'base64');
}

// subframe times for output frame i: centred on the frame time, spread over SHUTTER, never across a cut
function subTimes(tc, n) {
  const offs = n === 1 ? [0] : Array.from({ length: n }, (_, j) => (j - (n - 1) / 2) * SHUTTER / (FPS * n));
  return offs.map((o) => {
    let t = Math.min(DUR - 1e-4, Math.max(0, tc + o));
    for (const c of CUTS) if ((t < c) !== (tc < c)) t = tc >= c ? c : c - 1e-4;
    return t;
  });
}

const t0 = Date.now();
if (STILLS || has('beats')) {
  let times = STILLS ? STILLS.split(',').map(Number) : [];
  if (has('beats')) { const b = JSON.parse(readFileSync(join(ROOT, 'beats.json'), 'utf8')); times = b.beats.filter((x) => x < DUR).map((x) => +(x + num('beat-offset', 0.12)).toFixed(3)); }
  await mkdir(OUTDIR, { recursive: true });
  for (const t of times) { const f = join(OUTDIR, `t${t.toFixed(2).padStart(6, '0')}.png`); await writeFile(f, await grab(t)); }
  console.log(`${times.length} stills -> ${OUTDIR}`);
} else {
  await mkdir(dirname(OUT), { recursive: true });
  const vf = [];
  if (CAPTURE === 'dom' && SUB > 1) vf.push(`tmix=frames=${SUB}`, `select='eq(mod(n\\,${SUB})\\,${SUB - 1})'`, `setpts=N/${FPS}/TB`);
  vf.push(`scale=${W}:${H}:flags=lanczos:in_range=pc:out_range=tv:out_color_matrix=bt709`, 'format=yuv420p');
  const inRate = CAPTURE === 'dom' ? FPS * SUB : FPS;
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(inRate), '-i', '-',
    '-vf', vf.join(','), '-r', String(FPS), '-c:v', 'libx264', '-preset', PRESET, '-crf', String(CRF), '-pix_fmt', 'yuv420p',
    '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
    '-movflags', '+faststart', OUT], { stdio: ['pipe', 'inherit', 'inherit'] });
  const n = Math.round((TO - FROM) * FPS); let samples = 0; const hist = {};
  for (let i = 0; i < n; i++) {
    const tc = FROM + i / FPS; let png;
    if (CAPTURE === 'dom') {
      for (const t of subTimes(tc, SUB)) { const b = await grab(t); if (!ff.stdin.write(b)) await new Promise((r) => ff.stdin.once('drain', r)); samples++; }
      continue;
    }
    let k = SUB;
    if (ADAPTIVE && SUB > 1) {
      const [a, b] = [subTimes(tc, 2)[0], subTimes(tc, 2)[1]];
      const m = await page.evaluate(([a, b]) => window.__cap.motion(a, b), [a, b]);
      k = m < 0.15 ? 1 : m < 2 ? Math.min(4, SUB) : SUB;
    }
    hist[k] = (hist[k] || 0) + 1; samples += k;
    png = Buffer.from(await page.evaluate((ts) => window.__cap.blend(ts), subTimes(tc, k)), 'base64');
    if (!ff.stdin.write(png)) await new Promise((r) => ff.stdin.once('drain', r));
    if (i % FPS === 0) console.log(`rendered ${Math.round(i / FPS)}s / ${(TO - FROM).toFixed(1)}s  (${((Date.now() - t0) / 1000).toFixed(0)}s elapsed)`);
  }
  ff.stdin.end();
  const code = await new Promise((r) => ff.on('close', r));
  if (code !== 0) { console.error('ffmpeg failed'); process.exitCode = 1; }
  else {
    const got = spawnSync('ffprobe', ['-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames', '-of', 'csv=p=0', OUT]).stdout.toString().trim();
    const ok = Number(got) === n;
    console.log(`wrote ${OUT}: ${W}x${H} ${FPS}fps ${n} frames (${ok ? 'frame count OK' : 'FRAME COUNT MISMATCH: got ' + got}), ` +
      `${samples} samples${ADAPTIVE ? ' ' + JSON.stringify(hist) : ''}, ${((Date.now() - t0) / 1000).toFixed(1)}s`);
    if (!ok) process.exitCode = 1;
  }
}
if (errors.length) { console.error(`PAGE ERRORS (${errors.length}):\n  ` + errors.slice(0, 8).join('\n  ')); process.exitCode = 1; }
await browser.close(); server.close(); releaseLock();
