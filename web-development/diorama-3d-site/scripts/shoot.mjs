// shoot.mjs — headless QA screenshots of a built diorama page (no GPU needed: SwiftShader WebGL; pixels are right,
// fps is not meaningful here — check fps on a real GPU or the user's phone).
//   node shoot.mjs <dist_dir> <page_path e.g. examples/demo/> <out_dir> [--stops 0,0.4,0.85] [--mobile]
// Serves dist with python3 http.server, waits for window.__ready, scrolls via window.__lenis, screenshots each stop,
// prints console errors and a canvas "is anything drawn" check (non-background pixel ratio).
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import net from 'node:net';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const H = process.env.HOME;
let chromium;
for (const p of [path.join(H, '.hermes/data/motion-site/runtime/node_modules/playwright-core'),
                 path.join(H, '.hermes/data/motion-graphics/runtime/node_modules/playwright-core')]) {
  try { ({ chromium } = require(p)); break; } catch {}
}
const [dist, pagePath, outDir, ...rest] = process.argv.slice(2);
const opt = (k, d) => { const i = rest.indexOf('--' + k); return i >= 0 ? rest[i + 1] : d; };
const stops = opt('stops', '0,0.4,0.85').split(',').map(Number);
const mobile = rest.includes('--mobile');
fs.mkdirSync(outDir, { recursive: true });
const port = await new Promise(r => { const s = net.createServer().listen(0, () => { const p = s.address().port; s.close(() => r(p)); }); });
const srv = spawn('python3', ['-m', 'http.server', String(port), '--bind', '127.0.0.1'], { cwd: dist, stdio: 'ignore' });
await new Promise(r => setTimeout(r, 900));
const cache = path.join(H, '.cache/ms-playwright');
const exe = fs.readdirSync(cache).filter(d => d.startsWith('chromium_headless_shell')).sort().reverse()
  .flatMap(d => ['chrome-headless-shell-linux64', 'chrome-linux64'].map(s => path.join(cache, d, s, 'chrome-headless-shell'))).find(p => fs.existsSync(p));
const browser = await chromium.launch({ executablePath: exe, args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const errors = [];
const vp = mobile ? { width: 390, height: 844 } : { width: 1280, height: 800 };
const ctx = await browser.newContext({ viewport: vp, isMobile: mobile, hasTouch: mobile });
const page = await ctx.newPage();
page.setDefaultTimeout(180000);                       // software WebGL frames can take seconds each
page.on('console', m => { if (m.type() === 'error' && !/favicon/.test(m.text())) errors.push(m.text().slice(0, 220)); });
page.on('pageerror', e => errors.push('pageerror ' + e.message.slice(0, 220)));
const lite = rest.includes('--full') ? '' : (pagePath.includes('?') ? '&lite' : '?lite');
const url = `http://127.0.0.1:${port}/${pagePath}${lite}`;
const res = { url, gl: null, shots: [], drawn: [] };
try {
  await page.goto(url, { waitUntil: 'load', timeout: 120000 });
  await page.waitForFunction(() => window.__ready === true, null, { timeout: 180000 });
  res.gl = await page.evaluate(() => { const g = document.createElement('canvas').getContext('webgl2'); const e = g?.getExtension('WEBGL_debug_renderer_info'); return e ? g.getParameter(e.UNMASKED_RENDERER_WEBGL) : (g ? 'webgl2' : 'none'); });
  await page.mouse.move(vp.width * 0.6, vp.height * 0.4, { steps: 5 });
  for (const [i, s] of stops.entries()) {
    await page.evaluate(v => { const y = v * (document.documentElement.scrollHeight - innerHeight); window.__lenis ? window.__lenis.scrollTo(y, { immediate: true }) : scrollTo(0, y); }, s);
    await page.waitForTimeout(4000);                                   // let damped camera settle (software GL is slow)
    const f = path.join(outDir, `${mobile ? 'm' : 'd'}${i}_${Math.round(s * 100)}.png`);
    await page.screenshot({ path: f, animations: 'allow', caret: 'initial', timeout: 180000 });
    res.shots.push(f);
  }
} catch (e) { errors.push('shoot: ' + e.message.slice(0, 300)); }
await browser.close(); srv.kill();
// "anything drawn": fraction of pixels in the centre third that differ from the corner background colour
const py = spawn('python3', ['-c', `
import sys
from PIL import Image
for f in sys.argv[1:]:
    im = Image.open(f).convert('RGB'); w, h = im.size
    bg = im.getpixel((w - 3, h // 2))
    c = im.crop((w // 3, h // 4, 2 * w // 3, 3 * h // 4)).resize((120, 120))
    px = list(c.getdata()); d = sum(1 for p in px if sum(abs(a - b) for a, b in zip(p, bg)) > 40)
    print(f"{f}: {d / len(px):.0%} of centre differs from background")
`, ...res.shots], { stdio: ['ignore', 'inherit', 'inherit'] });
await new Promise(r => py.on('exit', r));
console.log(JSON.stringify({ url: res.url, gl: res.gl, shots: res.shots.length, errors: errors.slice(0, 10) }, null, 1));
console.log(errors.length ? 'SHOOT: ERRORS' : 'SHOOT: OK');
