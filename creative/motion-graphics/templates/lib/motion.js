// lib/motion.js — closed-form motion primitives. Every function is a pure function of time,
// so window.seek(t) stays deterministic and any frame renders without simulating the ones before it.
// Adapted from @0xMovez, "How to build motion design studio with Opus 5.5" (2026-09-27).

export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a, b, u) => a + (b - a) * u;
export const mix = (a, b, u) => a + (b - a) * clamp(u);

// Closed-form damped spring from 0 to 1, started at t = 0. k = stiffness, d = damping (mass 1).
// Underdamped overshoots slightly, critical/overdamped never overshoots.
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

// Spring presets (stiffness, damping). Snappy for UI edges, heavy for big type and logos.
export const SPRINGS = {
  snappy:  [320, 30],   // buttons, toggles, leading edges
  default: [170, 26],   // cards, containers, camera
  heavy:   [90, 20],    // big type, 3D objects, logo lockups (no visible overshoot)
  playful: [200, 12],   // mascots, stickers (visible overshoot)
};
export const sp = (t, name = 'default') => spring(t, ...SPRINGS[name]);

// A value that changes target several times: sum one spring per change, each from its own start.
// keys: [[time, value], ...] sorted by time. Continuous motion, still a pure function of t.
export function track(t, keys, k = 170, d = 26) {
  let v = keys[0][1];
  for (let i = 1; i < keys.length; i++) v += (keys[i][1] - keys[i - 1][1]) * spring(t - keys[i][0], k, d);
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

// Seamless loop: wrap time so the last frame equals the first.
export const loopT = (t, dur) => ((t % dur) + dur) % dur;

// Seeded PRNG (mulberry32). Never Math.random: renders must be identical every run.
export function rng(seed) {
  return () => {
    seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
    let x = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x;
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
  };
}

// Beat grid helpers. beats = parsed beats.json ({bpm, beats, downbeats, hits}).
export const beatAt = (beats, i) => beats.beats[Math.min(i, beats.beats.length - 1)];
export const sinceBeat = (t, beats) => {           // seconds since the most recent beat
  let last = 0; for (const b of beats.beats) { if (b > t) break; last = b; } return t - last;
};
export const pulse = (t, beats, decay = 8) => Math.exp(-sinceBeat(t, beats) * decay);  // 1 on the beat, decays

// Layout: write scenes against these, not fixed pixels, so 9:16, 1:1 and 16:9 reframe instead of crop.
export function layout(W, H) {
  const m = Math.min(W, H);
  return {
    W, H, m, cx: W / 2, cy: H / 2,
    portrait: H > W * 1.2, landscape: W > H * 1.2,
    u: (x) => x * m / 1080,                       // design unit: 1080 on the short side
    safe: { x: m * 0.08, y: m * 0.08 },           // keep type out of the edges (no corner labels)
  };
}
