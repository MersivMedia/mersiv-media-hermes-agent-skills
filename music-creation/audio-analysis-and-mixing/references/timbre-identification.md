# Identifying instruments from a stem

Spectral balance says a stem is "bass heavy". It does not say whether that bass
is a **sine sub**, an **808**, or a **detuned reese** — and those three demand
completely different words in a generation prompt. When the user asks for
"similar instruments to the original", percentages are not enough. Measure the
timbre.

Worked on the stems of a 130 BPM house track, 44.1 kHz mono, 90 s from 0:30.

## Use the full sample rate

Decode at **44100**, not the 22050 used for tempo work. Telling a drum-machine
hat from a sampled acoustic cymbal depends on content above 11 kHz, which a
22 kHz decode has already discarded.

## The four discriminators

### Kick — pitch glide separates 808 from house kick

Average 30–40 isolated hits, then compare the dominant low-band frequency in
the first ~40 ms against the following ~120 ms.

```python
f1, a1 = avg_spectrum(avg[:int(SR*0.04)],  N=2048)   # attack
f2, a2 = avg_spectrum(avg[int(SR*0.04):int(SR*0.16)], N=2048)  # body
# dominant freq in 30-400 Hz for each
glide = d1 > d2 * 1.25      # True -> 808-style downward pitch envelope
```

Also take a **click/body ratio** — RMS of the 2–8 kHz band over total RMS:

| Reading | Meaning |
|---|---|
| glide down, ratio < 0.06 | 808 / sub kick |
| stable pitch, ratio > 0.06 | layered house kick (sub body + clicky transient) |
| stable pitch, ratio < 0.04 | soft/acoustic kick |

Measured: 75 Hz fundamental, stable pitch, ratio **0.123** → punchy layered
house kick with a hard attack. Explicitly *not* an 808.

### Hats — spectral flatness separates drum machine from acoustic

Flatness is geometric mean over arithmetic mean of the 4–16 kHz magnitudes.

```python
g = np.exp(np.mean(np.log(a[m] + 1e-12)))
flatness = g / np.mean(a[m])
```

| Flatness | Meaning |
|---|---|
| > 0.35 | white-noise source → 808/909 drum-machine hat |
| < 0.35 | metallic resonant partials → sampled or acoustic cymbal |

Measured: centroid 8947 Hz, flatness **0.890** → drum-machine hats. Prompt word
is `white-noise 909 hi-hats`, not `crisp hi-hats`.

The same test on 150–3000 Hz distinguishes a **noise clap/snare** (> 0.3) from
tuned percussion. Measured 0.767 with energy at 156–345 Hz → layered noise
claps, low-tuned.

### Bass — sub/harmonic ratio separates sine from reese

```python
sub  = rms(band(x, 30, 90))
harm = rms(band(x, 200, 1500))
ratio = sub / harm
```

| Ratio | Meaning |
|---|---|
| > 3 | pure sine / 808 sub, few harmonics |
| < 3 | harmonically rich — saw, square, reese |

Measured: 54 Hz fundamental, ratio **7.34**, nothing above 258 Hz → clean sine
sub. This killed a planned `detuned gritty reese growl` prompt line: the source
has no distortion anywhere in the low end, so a reese would clash rather than
match. Trippiness had to come from **pitch-bend and filter modulation of a clean
sub** instead.

### Stabs / chords — partial spacing separates tonal from percussive

Peak-pick the 150–6000 Hz average spectrum. Harmonically spaced partials mean a
sustained tonal instrument; irregular spacing plus flatness 0.3–0.6 means a
percussive synth pluck.

Measured: partials at 312 / 366 / 409 / 463 / 614 Hz (inharmonic), flatness
0.553 → dry plucked synth stabs in the low-mids. No pads anywhere in the track.

## Analysis-script bugs that produce confident nonsense

A first pass reported **0 ms decay for every element** and a **2689 Hz centroid
for a stem that was 37 % sub energy**. Both are impossible and both came from
ordinary coding mistakes, not from the audio. Sanity-check outputs against each
other before reporting.

**Decay measured from the onset index, not the peak.** An onset fires on the
*rise*; the true peak is 5–40 ms later. Searching forward from the onset for the
first sample below `peak * 0.1` finds a sample in the attack itself and returns
0 ms. Fix: locate the real peak inside the first ~80 ms, then measure decay from
there, and smooth with a ~5 ms moving average so zero-crossings do not trigger.

**Fixed onset threshold.** A hardcoded `0.25` of max flux works on drums and
finds almost nothing in a sparse bass stem. Derive it from the band's own
distribution — `np.percentile(flux, 97)` — as the skill already advises for edit
points.

**Spectral centroid dragged upward by empty bins.** Thousands of near-zero HF
bins each contribute a little weight at a high frequency, pulling the mean far
above the audible content. On a sine sub this reported 1854–2689 Hz. Fix: zero
everything below ~2 % of the frame maximum before computing the centroid, and
take the **median** across frames rather than the mean.

Corrected, the same stem read as a 54 Hz sine — consistent with its 37 % sub
energy. Two measurements that contradict each other mean one is broken; resolve
it rather than reporting both with a caveat.

## Turning the readings into prompt words

| Measurement | Prompt phrase |
|---|---|
| 75 Hz, stable pitch, click 0.123 | `punchy layered house kick with clicky attack` |
| sub/harm ratio 7.34, 54 Hz | `deep pure sine sub-bass, no distortion on the low end` |
| flatness 0.890, centroid 8947 Hz | `white-noise drum-machine hi-hats, 909 hats` |
| flatness 0.767, 156–345 Hz | `layered noise claps on the offbeat` |
| inharmonic partials, flatness 0.553 | `dry inharmonic synth pluck stabs, staccato and clipped` |
| no sustained content in any stem | `no pads, no sustained chords` |

The negative assertions matter as much as the positive ones. `no pads` and
`no distortion on the low end` prevent the generator from adding a texture the
source never had.

## Mixing consequence

A measured sub/harmonic ratio of 7.34 at 54 Hz means the original bass owns
30–90 Hz almost completely. If the generated track also supplies a sine sub,
two sines in the same octave phase-cancel and pump unpredictably. Either mute
the original bass stem and let the generated one carry the low end, or
high-pass the new bass above the original's occupied band.

Check the source's empty bands too — this track had a wide gap at 150–400 Hz
(bass 20.8 %, other 7.9 %), which is exactly where a new bass texture can sit
without fighting anything.
