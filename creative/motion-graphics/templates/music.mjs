// music.mjs — synthesize an original backing track on the film's beat grid, and write beats.json.
// Use when no track is supplied. Deterministic: same args -> same WAV, byte for byte.
// Usage: node music.mjs --bpm 120 --dur 15 --key A --out audio/music.wav --beats beats.json [--mood bright|dark]
// Layers: four-on-the-floor kick, offbeat hats, root bass, sidechained chord pad. Not a hit record:
// a clean, on-grid bed that sells the cuts. Swap in a real track (beats.py) for anything flagship.
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

const a = process.argv.slice(2), arg = (k, d) => { const i = a.indexOf('--' + k); return i >= 0 ? a[i + 1] : d; };
const BPM = Number(arg('bpm', 120)), DUR = Number(arg('dur', 15)), OUT = arg('out', 'audio/music.wav');
const BEATS = arg('beats', 'beats.json'), KEY = arg('key', 'A'), MOOD = arg('mood', 'bright');
const SR = 48000, N = Math.ceil(DUR * SR), L = new Float32Array(N), R = new Float32Array(N);
const SPB = 60 / BPM, TAU = 2 * Math.PI;
const NOTES = { C: 0, 'C#': 1, D: 2, 'D#': 3, E: 4, F: 5, 'F#': 6, G: 7, 'G#': 8, A: 9, 'A#': 10, B: 11 };
const hz = (semi) => 440 * 2 ** ((semi - 9) / 12);          // semitones from C4
const root = NOTES[KEY] ?? 9;
// i–VI–III–VII (dark) or I–V–vi–IV (bright), one chord per bar
const PROG = MOOD === 'dark' ? [[0, 3, 7], [-4, 0, 3], [3, 7, 10], [-2, 2, 5]] : [[0, 4, 7], [7, 11, 14], [9, 12, 16], [5, 9, 12]];
let s = 7; const noise = () => (s = (s * 1664525 + 1013904223) >>> 0) / 2147483648 - 1;
const add = (i, v, pan = 0) => { if (i >= 0 && i < N) { L[i] += v * (1 - pan) ; R[i] += v * (1 + pan); } };

const beats = [];
for (let b = 0; b * SPB < DUR; b++) {
  const t0 = b * SPB, i0 = Math.floor(t0 * SR); beats.push(+t0.toFixed(3));
  for (let i = 0; i < 0.35 * SR; i++) { const t = i / SR;      // kick
    add(i0 + i, Math.sin(TAU * (50 + 110 * Math.exp(-t * 28)) * t) * Math.exp(-t * 7) * 0.55); }
  const ih = Math.floor((t0 + SPB / 2) * SR);                   // offbeat hat
  for (let i = 0; i < 0.06 * SR; i++) add(ih + i, noise() * Math.exp(-(i / SR) * 70) * 0.09, 0.3);
  const bar = Math.floor(b / 4), chord = PROG[bar % PROG.length];
  const bf = hz(root + chord[0] - 24);                          // bass: root, eighth notes
  for (const off of [0, SPB / 2]) { const ib = Math.floor((t0 + off) * SR);
    for (let i = 0; i < SPB / 2 * SR * 0.9; i++) { const t = i / SR;
      add(ib + i, Math.tanh(Math.sin(TAU * bf * t) * 2) * Math.min(1, t * 200) * Math.exp(-t * 3) * 0.16); } }
  if (b % 4 === 0) {                                            // pad: one chord per bar, sidechained to the kick
    const ip = i0, len = 4 * SPB * SR;
    for (let i = 0; i < len && ip + i < N; i++) { const t = i / SR, beatPh = (t % SPB) / SPB;
      const duck = 0.35 + 0.65 * Math.min(1, beatPh * 4);
      const env = Math.min(1, t * 4) * Math.min(1, (4 * SPB - t) * 6);
      let v = 0; chord.forEach((c, k) => { const f = hz(root + c); v += Math.sin(TAU * f * t + k) + 0.3 * Math.sin(TAU * f * 2.003 * t); });
      add(ip + i, v * env * duck * 0.035, Math.sin(t * 0.7) * 0.4); }
  }
}
// fade out the last half second, normalise to -1 dBFS peak
let peak = 0; for (let i = 0; i < N; i++) { const f = Math.min(1, (N - i) / (0.5 * SR)); L[i] *= f; R[i] *= f; peak = Math.max(peak, Math.abs(L[i]), Math.abs(R[i])); }
const g = peak > 0 ? 0.89 / peak : 1;
const b = Buffer.alloc(44 + N * 4);
b.write('RIFF', 0); b.writeUInt32LE(36 + N * 4, 4); b.write('WAVEfmt ', 8); b.writeUInt32LE(16, 16);
b.writeUInt16LE(1, 20); b.writeUInt16LE(2, 22); b.writeUInt32LE(SR, 24); b.writeUInt32LE(SR * 4, 28);
b.writeUInt16LE(4, 32); b.writeUInt16LE(16, 34); b.write('data', 36); b.writeUInt32LE(N * 4, 40);
for (let i = 0; i < N; i++) { b.writeInt16LE(Math.round(Math.max(-1, Math.min(1, L[i] * g)) * 32767), 44 + i * 4);
  b.writeInt16LE(Math.round(Math.max(-1, Math.min(1, R[i] * g)) * 32767), 46 + i * 4); }
mkdirSync(dirname(OUT), { recursive: true }); writeFileSync(OUT, b);
writeFileSync(BEATS, JSON.stringify({ bpm: BPM, beats, downbeats: beats.filter((_, i) => i % 4 === 0), hits: [], source: 'music.mjs' }, null, 1));
console.log(`wrote ${OUT} (${BPM} BPM, ${DUR}s, key ${KEY} ${MOOD}) and ${BEATS} (${beats.length} beats)`);
