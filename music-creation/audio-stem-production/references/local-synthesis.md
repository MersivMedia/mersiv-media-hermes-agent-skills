# Local synthesis of a new production bed

When a restyle model's output fidelity is too low (MusicGen family = 32 kHz),
build the production directly instead. Full 44.1 kHz end to end, no per-render
cost, and every parameter is adjustable in seconds.

Toolchain is just `numpy` + `scipy`:

```bash
python3 -m venv aenv
./aenv/bin/pip install -q numpy scipy
```

## Why it beats a generative restyle here

| | musicgen-remixer | local synthesis |
|---|---|---|
| Sample rate | 32000 Hz fixed | 44100 Hz |
| Bitrate | ~48 kbps | 320 kbps |
| Cost per iteration | ~$0.05, ~150 s | free, seconds |
| Control | prompt text only | every parameter |
| Engineered drops | no | yes |
| Musical coherence | follows source chords | must be derived (below) |

The one thing the model gives free is harmonic following. Replace it by
analysing the stems.

## Step 1 — derive tempo from the drum stem

Guessing is the main failure mode. An assumed 140 BPM against a real 129.2
produces drums that audibly fight the record, and no amount of mixing fixes it.

Positive spectral flux, autocorrelated:

```python
sos = butter(4, [60, 4000], btype='band', fs=SR, output='sos')
y   = sosfilt(sos, drums)
hop = 512
env = np.array([np.sqrt(np.mean(y[i*hop:(i+1)*hop]**2))
                for i in range(len(y)//hop)])
env = np.maximum(0, np.diff(env, prepend=env[0]))   # onsets only
env = (env - env.mean()) / (env.std() + 1e-9)

ac  = np.correlate(env, env, mode='full')[len(env)-1:]
fps = SR / hop
lo, hi = int(fps*60/180), int(fps*60/70)            # 70-180 BPM window
bpm = 60.0 * fps / (np.argmax(ac[lo:hi]) + lo)
```

Half-time trap feel is `bpm / 2` — kick on 1, snare on 3 of the original grid.

## Step 2 — track the bassline

Per detected onset, take the dominant low-band FFT bin. This is what makes the
808s move with the song rather than droning one note.

```python
sos = butter(4, 250, btype='low', fs=SR, output='sos')
y   = sosfilt(sos, bass)
seg = y[int(t*SR):int((t+0.25)*SR)] * np.hanning(n)
spec, freqs = np.abs(np.fft.rfft(seg, 8192)), np.fft.rfftfreq(8192, 1/SR)
band = (freqs > 35) & (freqs < 250)
hz   = freqs[band][int(np.argmax(spec[band]))]
```

Then: drop notes below the 45th amplitude percentile (separation artefacts),
thin to roughly one 808 per half-note so it reads as trap rather than rumble,
and fold each pitch into the sub octave (`while hz > 80: hz /= 2`).

## Step 3 — synthesis

The 808 is the only non-obvious one. Its character is the **pitch envelope**:
start ~4x the fundamental and collapse fast.

```python
f = freq * (1 + 3.0 * np.exp(-t * 28))        # the drop
x = np.sin(2*np.pi*np.cumsum(f)/SR)
x += 0.25 * np.sin(2 * phase)                 # audible on phone speakers
x *= env_ad(n, 0.004, dur, curve=3.2)
x  = np.tanh(x * 2.6) * 0.72                  # saturation, not clipping
```

`np.tanh` is the right saturator — it compresses toward ±1 instead of hard
clipping, which is what gives 808s their weight.

Hats: filtered noise, very short AD envelope, on a triplet grid (`BEAT/3`),
accent every third, four-hit roll every fourth bar.

## Step 4 — gain staging

**Normalise every stem before mixing.** Raw generator output sits at 0 dBFS and
clips as soon as anything is summed.

```
808    -3 dBFS      snare  -8 dBFS      riser -12 dBFS
kick   -4 dBFS      hats  -14 dBFS
```

## Step 5 — the mix

Keep the original drums and synths underneath, high-passed and quiet — the
synthesized kit brings weight, the real kit brings groove and swing.

```
i_vocals    highpass 95   vol 1.9    (untouched performance)
808         lowpass 140   vol 1.0
kick/snare/hats                      synthesized, normalised
i_drums     highpass 220  vol 0.30   groove glue
i_other     highpass 300  vol 0.38 + aecho
```

Bus the instrumental, sidechain it off the vocal, then master:

```
equalizer=f=60:t=q:w=0.9:g=3        weight
equalizer=f=320:t=q:w=1.1:g=-2.5    clear the mud
equalizer=f=9000:t=q:w=0.8:g=2      air
alimiter=level_in=1:level_out=0.93:limit=0.96
```

Target about −14 dB mean, −0.5 dB peak.

## Engineered drops

Purely automation, and the thing generative restyle models cannot do:

1. Filtered-noise riser over ~3 s, highpass sweeping 300 Hz → 9 kHz, amplitude
   ramped quadratically.
2. Ramp every bus to ~4% over the last 0.28 s — the near-silence.
3. 808 and kick land together on the downbeat, ~1.15x normal gain.

## Verification

```bash
ffprobe -v error -show_entries stream=sample_rate,bit_rate -of default=nw=1 out.mp3
ffmpeg -hide_banner -i out.mp3 -af volumedetect -f null - 2>&1 | grep volume
```

Confirm 44100 Hz survived the whole chain, and that peak is under 0 dBFS.
