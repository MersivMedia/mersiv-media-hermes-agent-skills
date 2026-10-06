// qa.mjs — headless QA for a motion site: screenshots at every section stop (desktop + mobile), console errors,
// frame-scrub check (does the canvas change as you scroll?), page weight. You cannot see the page otherwise.
//   node qa.mjs <site_dir> [--stops 0.05,0.5,0.95] [--out <site_dir>/qa]
// Starts its own static server (python3 -m http.server) on a free port, uses the cached headless shell.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import net from 'node:net';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const RT = process.env.MOTION_SITE_RUNTIME || path.join(process.env.HOME, '.hermes/data/motion-site/runtime');
let chromium;
try { ({ chromium } = require(path.join(RT, 'node_modules/playwright-core'))); }
catch { ({ chromium } = require(path.join(process.env.HOME, '.hermes/data/motion-graphics/runtime/node_modules/playwright-core'))); }

const args = process.argv.slice(2);
const site = path.resolve(args[0] ?? '.');
const opt = (k, d) => { const i = args.indexOf('--' + k); return i >= 0 ? args[i + 1] : d; };
const stops = opt('stops', '0.05,0.5,0.95').split(',').map(Number);
const out = path.resolve(opt('out', path.join(site, 'qa')));
fs.mkdirSync(out, { recursive: true });

const port = await new Promise(r => { const s = net.createServer().listen(0, () => { const p = s.address().port; s.close(() => r(p)); }); });
const srv = spawn('python3', ['-m', 'http.server', String(port), '--bind', '127.0.0.1'], { cwd: site, stdio: 'ignore' });
await new Promise(r => setTimeout(r, 900));
const cache = path.join(process.env.HOME, '.cache/ms-playwright');
const exe = fs.readdirSync(cache).filter(d => d.startsWith('chromium_headless_shell')).sort().reverse()
  .flatMap(d => ['chrome-headless-shell-linux64', 'chrome-linux64'].map(s => path.join(cache, d, s, 'chrome-headless-shell')))
  .find(p => fs.existsSync(p));
if (!exe) throw new Error('no chromium_headless_shell in ~/.cache/ms-playwright (npx playwright install chromium-headless-shell)');
const browser = await chromium.launch({ executablePath: exe, args: ['--no-sandbox', '--disable-gpu-vsync'] });
const report = { url: `http://127.0.0.1:${port}/`, errors: [], shots: [], scrub: {}, bytes: 0 };

async function run(label, opts) {
  const ctx = await browser.newContext(opts);
  const page = await ctx.newPage();
  page.on('console', m => { if (m.type() === 'error') report.errors.push(`[${label}] ${m.text()}`.slice(0, 240)); });
  page.on('pageerror', e => report.errors.push(`[${label}] pageerror ${e.message}`.slice(0, 240)));
  page.on('response', async r => { if (label === 'desktop') { try { report.bytes += (await r.body()).length; } catch {} } });
  await page.goto(report.url, { waitUntil: 'load', timeout: 60000 });
  await page.waitForFunction(() => window.__site?.ready || window.__site?.error, null, { timeout: 60000 });
  const err = await page.evaluate(() => window.__site.error);
  if (err) report.errors.push(`[${label}] site error ${err}`);
  await page.waitForFunction(() => window.__site.progress >= 0.999 || !document.querySelector('canvas'), null, { timeout: 90000 }).catch(() => {});
  await page.waitForTimeout(800);
  const ids = await page.evaluate(() => window.__site.sections);
  for (const [i, id] of ids.entries()) {
    const hashes = [];
    for (const p of stops) {
      await page.evaluate(([i, p]) => window.__site.seek(i, p), [i, p]);
      await page.waitForTimeout(700);
      const f = path.join(out, `${label}_${String(i).padStart(2, '0')}_${id}_${Math.round(p * 100)}.png`);
      await page.screenshot({ path: f });
      report.shots.push(f);
      hashes.push(await page.evaluate(i => { const c = document.querySelectorAll('.scene canvas:not(.particles)')[i];
        if (!c || !c.width) return 'none'; const g = c.getContext('2d'); const d = g.getImageData(c.width >> 1, c.height >> 1, 8, 8).data;
        let s = 0; for (const v of d) s = (s * 31 + v) >>> 0; return String(s); }, i));
    }
    if (label === 'desktop') report.scrub[id] = new Set(hashes).size > 1 ? 'moves' : `STATIC (${hashes[0]})`;
  }
  // overflow check
  const ox = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  if (ox > 1) report.errors.push(`[${label}] horizontal overflow ${ox}px`);
  await ctx.close();
}
try {
  await run('desktop', { viewport: { width: 1440, height: 900 } });
  await run('mobile', { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
} finally { await browser.close(); srv.kill(); }

// contact sheet (ffmpeg tile) for one-glance review
const desk = report.shots.filter(s => path.basename(s).startsWith('desktop'));
const mob = report.shots.filter(s => path.basename(s).startsWith('mobile'));
const sheet = (files, name, w, cols) => {
  const list = path.join(out, `${name}.txt`);
  fs.writeFileSync(list, files.map(f => `file '${f}'`).join('\n'));
  const rows = Math.ceil(files.length / cols);
  spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', list, '-vf', `scale=${w}:-2,tile=${cols}x${rows}:padding=6:color=0x222222`,
    '-frames:v', '1', path.join(out, `${name}.jpg`)], { stdio: 'inherit' }).on('exit', () => fs.rmSync(list));
};
sheet(desk, 'sheet_desktop', 480, stops.length);
sheet(mob, 'sheet_mobile', 200, stops.length * 2);
await new Promise(r => setTimeout(r, 2500));
console.log(JSON.stringify({ shots: report.shots.length, scrub: report.scrub, desktopMB: +(report.bytes / 1e6).toFixed(1), errors: report.errors.slice(0, 12) }, null, 1));
console.log(report.errors.length ? 'QA: ERRORS' : Object.values(report.scrub).some(v => v !== 'moves') ? 'QA: STATIC SECTION' : 'QA: PASS');
