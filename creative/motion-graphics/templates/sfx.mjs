// sfx.mjs — synthesize UI sound effects on the film's timeline. Deterministic (seeded noise).
// Usage: node sfx.mjs cues.json out/sfx.wav [--dur 15]
//   cues.json: [{"t":0.5,"type":"click"}, {"t":1.0,"type":"whoosh","gain":0.8}, ...]
// Voices: click, pop, thump, whoosh, tick, riser, chime. Output: 48 kHz 16-bit mono WAV.
// Adapted from @0xMovez's course (2026-09-27); voices beyond the original four added here.
import { readFileSync, writeFileSync } from 'node:fs';

const [, , cuesPath, outPath] = process.argv;
const di = process.argv.indexOf('--dur');
const SR = 48000, cues = JSON.parse(readFileSync(cuesPath, 'utf8'));
const end = di > 0 ? Number(process.argv[di + 1]) : Math.max(0, ...cues.map((c) => c.t)) + 2;
const buf = new Float32Array(Math.ceil(end * SR));

let s = 42; const noise = () => (s = (s * 1664525 + 1013904223) >>> 0) / 2147483648 - 1;
const TAU = 2 * Math.PI;
const VOICES = {
  click:  [0.05, (t) => Math.sin(TAU * 1800 * t) * Math.exp(-t * 90) * 0.5],
  tick:   [0.03, (t) => Math.sin(TAU * 3200 * t) * Math.exp(-t * 160) * 0.35],
  pop:    [0.15, (t) => Math.sin(TAU * (600 + 900 * t) * t) * Math.exp(-t * 30) * 0.4],
  thump:  [0.50, (t) => Math.sin(TAU * (90 - 60 * t) * t) * Math.exp(-t * 9) * 0.9],
  whoosh: [0.35, (t) => noise() * Math.sin(Math.PI * Math.min(1, t / 0.35)) * 0.25],
  riser:  [1.00, (t) => (noise() * 0.15 + Math.sin(TAU * (200 + 800 * t * t) * t) * 0.1) * t],
  chime:  [1.20, (t) => [1, 2.01, 3.03].reduce((a, h, i) => a + Math.sin(TAU * 880 * h * t) * Math.exp(-t * (3 + i * 2)) / (i + 1), 0) * 0.25],
};
for (const c of cues) {
  const v = VOICES[c.type]; if (!v) throw new Error(`unknown sfx type ${c.type}`);
  const [len, fn] = v, start = Math.floor(c.t * SR), gain = c.gain ?? 1;
  for (let i = 0; i < len * SR && start + i < buf.length; i++) buf[start + i] += fn(i / SR) * gain;
}

const n = buf.length, b = Buffer.alloc(44 + n * 2);
b.write('RIFF', 0); b.writeUInt32LE(36 + n * 2, 4); b.write('WAVEfmt ', 8);
b.writeUInt32LE(16, 16); b.writeUInt16LE(1, 20); b.writeUInt16LE(1, 22);
b.writeUInt32LE(SR, 24); b.writeUInt32LE(SR * 2, 28); b.writeUInt16LE(2, 32); b.writeUInt16LE(16, 34);
b.write('data', 36); b.writeUInt32LE(n * 2, 40);
for (let i = 0; i < n; i++) b.writeInt16LE(Math.round(Math.max(-1, Math.min(1, buf[i])) * 32767), 44 + i * 2);
writeFileSync(outPath, b);
console.log(`wrote ${outPath}: ${cues.length} cues, ${end.toFixed(2)}s`);
