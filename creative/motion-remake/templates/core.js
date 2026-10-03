/* core.js — shared, deterministic helpers for a frame-locked remake.
   Everything is a PURE function of the global frame F (FPS from project.json). No timers, no Date, no Math.random.
   Shot files register with SHOT({id, f0, f1, render(lf, F)}) returning an HTML string for the W x H #stage.
   Brand tokens, old-brand hues and assets come from project.json (loaded by index.html before any shot runs).
   Adapted from howseen-ai/claude-motion-design remake/core.js (MIT); brand-specific parts made configurable. */
(function () {
  const P = window.PROJECT;                       // set by index.html from project.json
  const FPS = P.fps, W = P.w, H = P.h;
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const lerp = (a, b, t) => a + (b - a) * t;
  const inv = (a, b, x) => clamp((x - a) / (b - a));

  // ---- easings (exact 0/1 at the ends)
  const ends = f => t => t <= 0 ? 0 : t >= 1 ? 1 : f(t);
  const E = {
    lin: ends(t => t),
    inQ: ends(t => t * t), outQ: ends(t => 1 - (1 - t) * (1 - t)), ioQ: ends(t => t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2),
    inC: ends(t => t * t * t), outC: ends(t => 1 - Math.pow(1 - t, 3)), ioC: ends(t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
    outQuart: ends(t => 1 - Math.pow(1 - t, 4)), ioQuart: ends(t => t < .5 ? 8 * t ** 4 : 1 - Math.pow(-2 * t + 2, 4) / 2),
    outExpo: ends(t => 1 - Math.pow(2, -10 * t)),
    ioExpo: ends(t => t < .5 ? Math.pow(2, 20 * t - 10) / 2 : (2 - Math.pow(2, -20 * t + 10)) / 2),
    outBack: ends(t => { const c = 1.70158, c3 = c + 1; return 1 + c3 * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); }),
  };
  // closed-form damped spring 0 -> 1, tau in FRAMES, f Hz, z damping ratio
  const spring = (tau, f = 2.2, z = 0.55) => {
    if (tau <= 0) return 0; const t = tau / FPS, w = 2 * Math.PI * f, wd = w * Math.sqrt(1 - z * z);
    return 1 - Math.exp(-z * w * t) * (Math.cos(wd * t) + (z * w / wd) * Math.sin(wd * t));
  };
  // kf(F, [[f, v], ...], ease | [eases]) piecewise, holds ends. Per-frame keyframe tables measured from REF go here.
  function kf(F, keys, ease = E.ioC) {
    if (F <= keys[0][0]) return keys[0][1];
    for (let i = 1; i < keys.length; i++) if (F <= keys[i][0]) {
      const [f0, v0] = keys[i - 1], [f1, v1] = keys[i];
      const e = Array.isArray(ease) ? (ease[i - 1] || E.ioC) : ease;
      return lerp(v0, v1, e((F - f0) / (f1 - f0)));
    }
    return keys[keys.length - 1][1];
  }
  // samples(F, f0, arr): interpolate inside a per-frame array MEASURED from REF frames (numpy), starting at frame f0
  function samples(F, f0, arr) {
    const x = F - f0; if (x <= 0) return arr[0]; if (x >= arr.length - 1) return arr[arr.length - 1];
    const i = Math.floor(x), t = x - i; return lerp(arr[i], arr[i + 1], t);
  }
  const rand = (n, s = 1) => { const x = Math.sin(n * 127.1 + s * 311.7) * 43758.5453; return x - Math.floor(x); };

  const T = P.tokens;                             // brand tokens: bg, ink, sub, line, soft, a1, a2, grad, font ...
  const A = n => 'assets/' + n;

  // ---- camera: wraps inner HTML, scale around origin + translate, optional blur
  function camera(inner, { s = 1, tx = 0, ty = 0, ox = W / 2, oy = H / 2, blur = 0, op = 1 } = {}) {
    const filt = blur > 0.01 ? `filter:blur(${blur.toFixed(2)}px);` : '';
    return `<div style="position:absolute;inset:0;transform-origin:${ox}px ${oy}px;transform:translate(${tx}px,${ty}px) scale(${s});opacity:${op};${filt}">${inner}</div>`;
  }
  // directional motion blur defs (use as filter:url(#id))
  const mblurDefs = (id, dx, dy) => `<svg width="0" height="0" style="position:absolute"><filter id="${id}" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="${Math.abs(dx).toFixed(2)} ${Math.abs(dy).toFixed(2)}"/></filter></svg>`;
  // generic arrow cursor, tip at (x,y). REF cursors are often NOT the macOS arrow: draw REF's shape when it differs.
  function cursor(x, y, { press = 0, scale = 1, op = 1 } = {}) {
    const s = scale * (1 - 0.12 * press);
    return `<svg style="position:absolute;left:${x}px;top:${y}px;transform-origin:0 0;transform:scale(${s});opacity:${op};overflow:visible;z-index:50" width="28" height="40" viewBox="0 0 28 40"><path d="M2 2 L2 31 L9.5 24 L14.5 36 L19 34 L14 22.5 L24 22.5 Z" fill="#000" stroke="#fff" stroke-width="2" stroke-linejoin="round"/></svg>`;
  }
  const typed = (s, n) => s.slice(0, Math.max(0, Math.floor(n)));        // typing: drive n from REF char counts
  function words(s, t, { stagger = 0.12, dur = 0.35, y = 14, blur = 6, color = null, accent = [] } = {}) {
    return s.split(' ').map((w, i) => {
      const e = E.outC(clamp((t - i * stagger) / dur));
      const col = accent.includes(i) ? `background:${T.grad};-webkit-background-clip:text;background-clip:text;color:transparent;` : (color ? `color:${color};` : '');
      return `<span style="display:inline-block;opacity:${e};transform:translateY(${(1 - e) * y}px);filter:blur(${(1 - e) * blur}px);${col}">${w}</span>`;
    }).join('<span style="display:inline-block;width:.28em"></span>');
  }
  const gtext = s => `<span style="background:${T.grad};-webkit-background-clip:text;background-clip:text;color:transparent">${s}</span>`;
  // brand mark: the logo file used as a mask, so any fill works
  const mark = (size, fill = T.ink) => `<div style="width:${size}px;height:${size}px;background:${fill};-webkit-mask:url(${A(P.mark)}) center/contain no-repeat;mask:url(${A(P.mark)}) center/contain no-repeat"></div>`;
  const appIcon = (size, { grad = T.grad } = {}) => `<div style="width:${size}px;height:${size}px;border-radius:${size * .24}px;background:${grad};display:flex;align-items:center;justify-content:center">${mark(size * .62, '#fff')}</div>`;
  const img = (n, size, extra = '') => `<img src="${A(n)}" style="width:${size}px;height:${size}px;object-fit:contain;${extra}">`;
  function pixelDissolve(x, y, w, h, t, { cell = 24, colors = [T.a1, T.a2 || T.a1], seed = 3 } = {}) {
    const cols = Math.ceil(w / cell), rows = Math.ceil(h / cell); let out = '';
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      const k = r * cols + c, th = rand(k, seed);
      if (!(t > th * 0.8 && t < th * 0.8 + 0.35)) continue;
      out += `<div style="position:absolute;left:${x + c * cell}px;top:${y + r * cell}px;width:${cell}px;height:${cell}px;background:${colors[k % colors.length]};opacity:${(0.35 + 0.65 * rand(k, seed + 1)).toFixed(2)}"></div>`;
    }
    return out;
  }
  // text placed by its ink edge (what you measure on REF frames), with font fitted to a width
  const _m = document.createElement('canvas').getContext('2d');
  function fitFont(text, maxW, weight = 600, maxPx = 200, family = T.font) {
    let px = maxPx; for (; px > 8; px -= 1) { _m.font = `${weight} ${px}px ${family}`; if (_m.measureText(text).width <= maxW) break; } return px;
  }
  function inkBox(text, px, weight = 600, family = T.font) {
    _m.font = `${weight} ${px}px ${family}`; const m = _m.measureText(text);
    return { left: m.actualBoundingBoxLeft, w: m.actualBoundingBoxLeft + m.actualBoundingBoxRight, asc: m.actualBoundingBoxAscent, desc: m.actualBoundingBoxDescent };
  }
  const mixHex = (a, b, t) => { const p = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16)); const x = p(a), y = p(b);
    return '#' + x.map((v, i) => Math.round(lerp(v, y[i], t)).toString(16).padStart(2, '0')).join(''); };

  // ---- palette filter: re-hue any leftover OLD-brand colour in the final HTML to the new brand
  // project.json "oldHues": [[fromDeg, toDeg, newHueDeg], ...], e.g. reds/oranges -> sky: [[330,360,199],[0,45,199]]
  function hexToRgb(h) { h = h.replace('#', ''); if (h.length === 3) h = h.split('').map(c => c + c).join(''); const n = parseInt(h, 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; }
  function rgbToHsl(r, g, b) { r /= 255; g /= 255; b /= 255; const mx = Math.max(r, g, b), mn = Math.min(r, g, b); let h = 0, s = 0; const l = (mx + mn) / 2; if (mx !== mn) { const d = mx - mn; s = l > .5 ? d / (2 - mx - mn) : d / (mx + mn); h = mx === r ? (g - b) / d + (g < b ? 6 : 0) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4; h /= 6; } return [h * 360, s, l]; }
  function hslToHex(h, s, l) { h /= 360; const f = n => { const k = (n + h * 12) % 12, a = s * Math.min(l, 1 - l); const c = l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1)); return Math.round(c * 255).toString(16).padStart(2, '0'); }; return '#' + f(0) + f(8) + f(4); }
  const OLD = P.oldHues || [];
  function paletteFilter(html) {
    if (!OLD.length) return html;
    return html.replace(/#[0-9a-fA-F]{6}\b/g, m => {
      const [r, g, b] = hexToRgb(m), [h, s, l] = rgbToHsl(r, g, b);
      if (s > 0.35) for (const [a, z, nh] of OLD) if (h >= a && h < z) return hslToHex(nh, Math.min(s, .9), l);
      return m;
    });
  }

  // ---- registry + seek (t in seconds -> frame F)
  const SHOTS = [];
  window.SHOT = def => { SHOTS.push(def); SHOTS.sort((a, b) => a.f0 - b.f0); };
  window.CORE = { FPS, W, H, clamp, lerp, inv, E, spring, kf, samples, rand, T, A, camera, mblurDefs, cursor, typed, words, gtext,
    mark, appIcon, img, pixelDissolve, fitFont, inkBox, mixHex, paletteFilter };
  window.seek = t => {
    const F = Math.round(t * FPS + 1e-6), st = document.getElementById('stage');
    const s = SHOTS.find(x => F >= x.f0 && F < x.f1);
    let html;
    if (s) { try { html = s.render(F - s.f0, F); } catch (e) { html = `<div style="color:red;font:30px monospace;padding:40px">${s.id} error: ${e}</div>`; console.error(s.id, e); } }
    else html = `<div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font:40px monospace;color:#bbb">F${F} — no shot</div>`;
    st.innerHTML = paletteFilter(html);
    return F;
  };
})();
