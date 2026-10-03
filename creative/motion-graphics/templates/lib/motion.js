// lib/motion.js — closed-form motion primitives. Every function is a pure function of time,
// so window.seek(t) stays deterministic and any frame renders without simulating the ones before it.
// Sources: @0xMovez course (2026-09-27); Raphaël Aubry / howseen-ai claude-motion-design (MIT, 2026-10-02).

export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a, b, u) => a + (b - a) * u;
export const mix = (a, b, u) => a + (b - a) * clamp(u);
export const inv = (a, b, x) => clamp((x - a) / (b - a));     // where x sits between a and b, 0..1

// ---------- easings (exact 0 and 1 at the ends: solved easings that return 1e-9 at 0 fire guards early)
const ends = (f) => (u) => (u <= 0 ? 0 : u >= 1 ? 1 : f(u));
export const E = {
  linear: ends((u) => u),                                                   // cheap: avoid for motion
  io: ends((u) => (u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2)),   // cubic in-out
  out: ends((u) => 1 - Math.pow(1 - u, 3)),
  in: ends((u) => u * u * u),
  o5: ends((u) => 1 - Math.pow(1 - u, 5)),                                  // quint out, crisp settle
  expo: ends((u) => 1 - Math.pow(2, -10 * u)),
};
// Eased progress of a move that starts at t0 and lasts dur.
export const P = (t, t0, dur, ease = E.io) => ease(clamp((t - t0) / dur));

// ---------- springs
// Closed-form damped spring from 0 to 1, started at t = 0. k = stiffness, d = damping (mass 1).
export function spring(t, k = 170, d = 26) {
  if (t <= 0) return 0;
  const w0 = Math.sqrt(k), z = d / (2 * w0);
  if (z < 1) {
    const wd = w0 * Math.sqrt(1 - z * z);
    return 1 - Math.exp(-z * w0 * t) * (Math.cos(wd * t) + (z * w0 / wd) * Math.sin(wd * t));
  }
  if (z === 1) return 1 - Math.exp(-w0 * t) * (1 + w0 * t);
  const s = Math.sqrt(z * z - 1), r1 = -w0 * (z - s), r2 = -w0 * (z + s);
  return 1 - (r2 * Math.exp(r1 * t) - r1 * Math.exp(r2 * t)) / (r2 - r1);
}
// Same spring described by frequency f (Hz) and damping ratio z. z >= 0.72 reads premium; < 0.5 is cartoon.
export const springFZ = (t, f = 3, z = 0.75) => { const w = 2 * Math.PI * f; return spring(t, w * w, 2 * z * w); };
export const zeta = (k, d) => d / (2 * Math.sqrt(k));                     // damping ratio of a (k, d) pair

// Presets (stiffness, damping) and their damping ratios: snappy 0.84, default 1.0, heavy 1.05, playful 0.42.
export const SPRINGS = {
  snappy:  [320, 30],   // buttons, toggles, leading edges
  default: [170, 26],   // cards, containers, camera
  heavy:   [90, 20],    // big type, 3D objects, logo lockups (no visible overshoot)
  playful: [200, 12],   // mascots, stickers only (visible overshoot)
};
export const sp = (t, name = 'default') => spring(t, ...SPRINGS[name]);

// A value that changes target several times: sum one spring per change, each from its own start.
// keys: [[time, value], ...] sorted by time. Continuous motion, still a pure function of t.
export function track(t, keys, k = 170, d = 26) {
  let v = keys[0][1];
  for (let i = 1; i < keys.length; i++) v += (keys[i][1] - keys[i - 1][1]) * spring(t - keys[i][0], k, d);
  return v;
}
// Loop-safe track: also adds the spring tails of the previous cycles, so the motion entering t = 0
// matches the motion leaving t = dur (velocity, not just position). Last key value must equal the first.
export function loopTrack(t, keys, dur, k = 170, d = 26, cycles = 2) {
  let v = keys[0][1];
  for (let c = 0; c <= cycles; c++)
    for (let i = 1; i < keys.length; i++) v += (keys[i][1] - keys[i - 1][1]) * spring(t + c * dur - keys[i][0], k, d);
  return v;
}

// Tab indicator that stretches: leading edge stiffer than trailing edge.
export function indicator(t, stops, width = 120) {
  const lead = track(t, stops, 320, 30), trail = track(t, stops, 140, 22);
  return { left: Math.min(lead, trail), right: Math.max(lead, trail) + width };
}

// Text inside a morphing box: in after the morph starts, out before the next one.
export function swapAlpha(t, tIn, tOut) {
  return Math.min(clamp((t - tIn - 0.08) / 0.12), clamp((tOut - 0.1 - t) / 0.1));
}

// ---------- time helpers
export const loopT = (t, dur) => ((t % dur) + dur) % dur;               // wrap time for loops
export const cyc = (t, dur, n = 1) => loopT(t * n / dur, 1);             // phase 0..1 of an INTEGER number of cycles per loop
// Micro drift keeps "still" shots alive (no frozen frame anywhere except the final hold).
export const drift = (t, amp = 2, speed = 0.25, seed = 1) =>
  amp * (Math.sin(t * speed * 2 * Math.PI + seed * 1.7) * 0.6 + Math.sin(t * speed * 3.1 + seed * 4.1) * 0.4);

// Seeded PRNG (mulberry32). Never Math.random: renders must be identical every run.
export function rng(seed) {
  return () => {
    seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
    let x = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x;
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
  };
}

// ---------- beat grid. beats = parsed beats.json ({bpm, beats, downbeats, hits, drop?}).
export const beatAt = (beats, i) => beats.beats[Math.min(i, beats.beats.length - 1)];
export const sinceBeat = (t, beats) => {           // seconds since the most recent beat
  let last = -1e9; for (const b of beats.beats) { if (b > t) break; last = b; } return t - last;
};
export const beatIndex = (t, beats) => { let i = -1; for (const b of beats.beats) { if (b > t) break; i++; } return i; };
export const pulse = (t, beats, decay = 8) => Math.exp(-Math.max(0, sinceBeat(t, beats)) * decay);  // 1 on the beat, decays

// ---------- camera
// keys: [[t, zoom, x, y], ...]. Eased segments, zoom interpolated in LOG space (constant perceived speed).
// Beat punches: +punch per beat, +barPunch per downbeat after the drop, exponential decay.
// Rule: never zoom in then out back-to-back; the sign of d(zoom)/dt should hold across a cut.
export function camera(t, keys, { beats = null, drop = Infinity, punch = 0.012, barPunch = 0.03, decay = 9, ease = E.io } = {}) {
  let k = 0; while (k < keys.length - 2 && t >= keys[k + 1][0]) k++;
  const [t0, z0, x0, y0] = keys[k], [t1, z1, x1, y1] = keys[Math.min(k + 1, keys.length - 1)];
  const u = t1 > t0 ? ease(clamp((t - t0) / (t1 - t0))) : 1;
  let s = Math.exp(lerp(Math.log(z0), Math.log(z1), u));
  if (beats) {
    const sb = sinceBeat(t, beats); if (sb >= 0) s *= 1 + punch * Math.exp(-sb * decay);
    if (t >= drop && beats.downbeats) { let last = null; for (const b of beats.downbeats) { if (b > t) break; if (b >= drop) last = b; }
      if (last !== null) s *= 1 + barPunch * Math.exp(-(t - last) * decay); }
  }
  return { s, x: lerp(x0, x1, u), y: lerp(y0, y1, u) };
}
// Apply a camera to a canvas context: the point (x, y) of the world lands at the screen centre.
export function applyCamera(g, cam, L) { g.translate(L.cx, L.cy); g.scale(cam.s, cam.s); g.translate(-cam.x, -cam.y); }

// ---------- transitions
// Colour flood from a source object must clear the FARTHEST corner (x1.05) in ~0.3-0.35 s.
export const floodRadius = (x, y, W, H) => 1.05 * Math.max(Math.hypot(x, y), Math.hypot(W - x, y), Math.hypot(x, H - y), Math.hypot(W - x, H - y));
export function flood(g, t, t0, x, y, W, H, color, dur = 0.32) {
  const r = floodRadius(x, y, W, H) * P(t, t0, dur, E.in);
  if (r <= 0) return; g.fillStyle = color; g.beginPath(); g.arc(x, y, r, 0, 2 * Math.PI); g.fill();
}

// Masked word-by-word rise (canvas). Each word rises from below a clip line with a small rotation.
// opts: font (CSS font string), color, stagger 0.055 s, dur 0.5 s, align 'left'|'center', accent {word: color}.
export function riseWords(g, text, x, y, t, t0, { font, color = '#fff', stagger = 0.055, dur = 0.5, align = 'center', rot = 0.05, accent = {}, out = null } = {}) {
  g.save(); g.font = font; g.textBaseline = 'alphabetic';
  const words = text.split(' '), space = g.measureText(' ').width;
  const widths = words.map((w) => g.measureText(w).width), total = widths.reduce((a, b) => a + b, 0) + space * (words.length - 1);
  const m = g.measureText('Hg'), asc = m.actualBoundingBoxAscent, desc = m.actualBoundingBoxDescent, hgt = asc + desc;
  let cx = align === 'center' ? x - total / 2 : x;
  g.beginPath(); g.rect(cx - hgt, y - asc - hgt * 0.15, total + 2 * hgt, hgt * 1.3); g.clip();   // the mask
  words.forEach((w, i) => {
    const ti = t0 + i * stagger, u = P(t, ti, dur, E.o5);
    const uo = out === null ? 0 : P(t, out + i * stagger * 0.6, dur * 0.7, E.in);
    const dy = (1 - u) * hgt * 1.05 - uo * hgt * 1.05, r = (1 - u) * rot;
    g.save(); g.translate(cx, y + dy); g.rotate(r); g.fillStyle = accent[w] || color; g.fillText(w, 0, 0); g.restore();
    cx += widths[i] + space;
  });
  g.restore();
}

// Fit a font size so text spans at most maxW (measure with canvas, never DOM rects under a camera scale).
export function fitFont(g, text, maxW, tpl, maxPx, minPx = 10) {
  let px = maxPx; for (; px > minPx; px -= 2) { g.font = tpl.replace('{px}', px); if (g.measureText(text).width <= maxW) break; }
  return px;
}

// ---------- layout: write scenes against this, not fixed pixels, so 9:16, 4:5, 1:1 and 16:9 reframe instead of crop.
export function layout(W, H) {
  const m = Math.min(W, H);
  return {
    W, H, m, cx: W / 2, cy: H / 2,
    portrait: H > W * 1.2, landscape: W > H * 1.2,
    u: (x) => x * m / 1080,                       // design unit: 1080 on the short side
    safe: { x: m * 0.08, y: m * 0.08 },           // keep type out of the edges (no corner labels)
    // 9:16 safe zone: put all text inside the centre square so the same storyboard survives 1:1 and 4:5
    core: { x: (W - m) / 2, y: (H - m) / 2, w: m, h: m },
  };
}
