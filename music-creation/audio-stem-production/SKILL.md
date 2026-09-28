---
name: audio-stem-production
description: Stem-split, restyle, and remux audio with ffmpeg.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [audio, ffmpeg, stems, remix, mixing, sidechain, replicate]
    related_skills: [ai-cover-songs, wan2gp-yue2-covers, replicate-api-generation]
---

# Audio Stem Production

## When to Use

Any job that takes an existing recording apart and puts it back together:
remixes, restyles, vocal isolation, backing-track swaps, mashups, cleanup.

Triggers: "remix this", "keep the original vocals", "change the production",
"isolate the vocal", "make an instrumental", "swap the beat".

This skill owns the **technique** — stem surgery and ffmpeg mixing. For which
generative model to call, see `ai-cover-songs` (Replicate routes) and
`wan2gp-yue2-covers` (rented GPU, full regeneration).

## Route selection — ask one question first

**"Do you want to keep the original vocal performance?"** The answer picks the
architecture, and getting it wrong wastes the whole run.

| Answer | Approach |
|---|---|
| **Yes** | Stem-split → restyle instrumental → remux original vocal (below) |
| **Yes, and it must sound good** | Stem-split → **synthesize locally** → remux. See "Local synthesis" |
| No, new singer | RVC voice conversion — `ai-cover-songs` Route A |
| No, regenerate all | YuE2 / minimax — `wan2gp-yue2-covers` |

**"Remix it but keep the vocals" is NOT a cover-model job.** Score-conditioned
and text-conditioned generators synthesize a new singer by construction. If the
user wants the actual performance preserved, the vocal must survive as a stem
and be re-laid over new production. This misroute is easy to make because both
requests sound like "cover this song".

## Check output fidelity before promising a route

Verifying that a model *accepts* audio is not the same as verifying what it
*emits*. MusicGen-family models — `sakemin/musicgen-remixer`, `musicgen-chord`,
`ardianfe/music-gen-fn-200e`, `meta/musicgen` — output **32000 Hz / ~48 kbps**.
That is the architecture's native rate, not a tunable setting.

```
source material     44100 Hz / 192+ kbps
musicgen output     32000 Hz /  48 kbps    <- nothing above 16 kHz survives
```

It sounds dull and smeared: no air, soft hats, mushy low end. Layering a clean
44.1 kHz vocal on top makes the mismatch *more* audible, not less. A user
rejected exactly this output with "that doesn't sound good at all" — correctly.

```bash
ffprobe -v error -show_entries stream=sample_rate,bit_rate -of default=nw=1 out.mp3
```

**Replicate has no high-fidelity instrumental restyle model.** Checked live:
`ace-step` and `riffusion` take no audio input at all; the rest are the same
32 kHz MusicGen family. For a genre change at full quality, use local synthesis
below or a rented GPU. Say this plainly rather than shipping a 32 kHz bed.

## The preserve-vocals pipeline

Verified end to end. Full transcript with real commands, costs and timings:
`references/remix-pipeline.md`. Runnable: `scripts/remix.sh`.

```
source audio
   │
   ├─ htdemucs ──► vocals / bass / drums / other
   │                  │           └──────┬──────┘
   │                  │        sum to one instrumental bed
   │                  │                  │
   │                  │           restyle (musicgen-remixer)
   │                  │                  │
   └──────────────────┴──► sidechain mix ──► limiter ──► master
```

Two decisions that materially improve the result:

**Feed the remixer a summed bed, not one stem.** Bass + drums + other gives the
model full harmonic context. A single stem produces thin, unanchored output.

**Duck the instrumental under the vocal** rather than just raising the vocal
level. Sidechain compression keyed off the vocal keeps it forward without
crushing headroom.

```bash
ffmpeg -i new_inst.mp3 -i vocals.mp3 -filter_complex "
[0:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[inst];
[1:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,
     volume=1.6,highpass=f=90[voc];
[voc]asplit=2[voc_mix][voc_key];
[inst][voc_key]sidechaincompress=threshold=0.05:ratio=4:attack=5:release=180:makeup=1[ducked];
[ducked][voc_mix]amix=inputs=2:duration=longest:normalize=0,
alimiter=level_in=1:level_out=0.92:limit=0.95,aformat=sample_fmts=s16p
" -acodec libmp3lame -b:a 320k out.mp3 -y
```

`highpass=f=90` on the vocal clears room for the sub-bass. `normalize=0` on
`amix` is essential — the default halves every input's gain.

## Always preview before the full render

Cut ~30 s, run the whole chain on it, and let the user judge. Costs cents,
catches a wrong creative direction before the full track is paid for. Matches
the user's standing "single test before batch" rule.

**Choose the section by musical structure, not by peak RMS.** Picking the
loudest ten seconds is a machine's answer. A preview that skips the song's
recognisable opening gets the response "you missed the whole intro" even when
the production is fine. Default to the **opening** — it is what the user hears
first and can judge against memory. Use the energy scan to understand the
arrangement's shape, not to pick the clip.

## Local synthesis — full fidelity, no model

When a restyle model's output quality is the blocker, build the new production
directly. Everything stays at 44.1 kHz and nothing costs money beyond the one
stem separation. `numpy` + `scipy` in a venv is the whole toolchain.

Working generators — 808 with pitch-drop envelope, kick, snare, hats, riser —
plus the analysis code are in `scripts/trap_synth.py`; the method is written up
in `references/local-synthesis.md`.

The part that makes it sound like the song rather than a loop: **derive tempo
and pitch from the stems**.

```python
# tempo: positive spectral flux on the drum stem, autocorrelated
env = np.maximum(0, np.diff(rms_frames, prepend=rms_frames[0]))
ac  = np.correlate(env, env, mode='full')[len(env)-1:]
bpm = 60.0 * fps / (np.argmax(ac[lo:hi]) + lo)      # search 70-180 BPM

# bass: dominant FFT bin per beat, low-passed, folded to the sub octave
```

Guess the tempo and the drums fight the record. A detected 129.2 BPM against an
assumed 140 is an obvious, unfixable-in-the-mix wobble.

Two practical rules:

- **Normalise every synth stem before mixing.** Raw generator output peaks at
  0 dBFS and clips the moment anything is summed. Set explicit targets —
  808 −3, kick −4, snare −8, hats −14, riser −12 dBFS.
- **Keep the original drums underneath**, high-passed around 220 Hz at low
  level. The synthesized kit supplies weight; the real kit supplies groove.

Engineered drops are just automation: filter sweep in, a beat of near-silence
(ramp the buses to ~4%), then the 808 and kick on the downbeat.

## ffmpeg forensics

### Strip cover art first

Embedded artwork appears as an `mjpeg` video stream and silently breaks stream
mapping and downstream filters.

```bash
ffprobe -v error -show_entries stream=codec_name -of csv=p=0 in.mp3
# mp3
# mjpeg          <-- strip it
ffmpeg -i in.mp3 -map 0:a:0 -vn -acodec libmp3lame -b:a 192k clean.mp3 -y
```

### Finding the loudest section

`volumedetect` writes to stderr at **info** level, so `-v error` suppresses the
very numbers being parsed. Use `-hide_banner` instead.

```bash
for t in $(seq 0 10 180); do
  v=$(ffmpeg -hide_banner -ss $t -t 10 -i clean.mp3 -af volumedetect -f null - 2>&1 \
      | grep -oP 'mean_volume: \K[-0-9.]+')
  printf "  %3ds  %6s dB\n" "$t" "$v"
done
```

`astats` with `metadata=1` reports **cumulative** averages, not per-block —
the numbers drift monotonically and look like a fade. Measure each segment
independently with `-ss`/`-t` instead.

## Prompting a restyle model

Instrumentation and production detail beat vibe words. Vague genre adjectives
produce generic output.

```
weak    "trippy bass heavy trap with heavy drops"

strong  "dark psychedelic trap, 140 BPM half-time, distorted 808 sub bass with
         long pitch glides, hard clipped kick, crisp triplet hi-hat rolls,
         rimshot snare on three, warped detuned synth leads drenched in reverb,
         granular pitch-bent textures, heavy sidechain pumping, cavernous low
         end, sparse menacing verses building into wide explosive drops"
```

Include: BPM and feel, the defining bass sound, drum articulation, texture
treatment, and the dynamic arc.

**Set expectations about drops.** Chord-following remixers stay harmonically
tied to the source, so they produce *energy* changes but not engineered
transitions. A riser → silence → 808 moment is an ffmpeg post step, not
something the model authors.

## Getting the source audio

Prefer a file the user supplies, or a direct URL. If they share a Google Drive
link, fetch it with the existing OAuth credentials rather than asking them to
re-upload — see `references/remix-pipeline.md` for the token-refresh snippet.
Extract the file id from `/file/d/<ID>/view` and pull it with
`GET https://www.googleapis.com/drive/v3/files/<ID>?alt=media`.

Some hosts refuse automated download from datacenter IPs and ask for account
cookies. That is an access control: ask the user for the file instead of
routing around it with proxies or scraper frontends. Owning a downloader
licence does not change the answer — the licence is the user's and the block
is on the IP, so the clean path is for them to fetch it on their own
connection and hand the file over. Do not spend several rounds trying player
clients; check once, then ask.

**When testing whether a tool upgrade fixes something, confirm the upgrade
actually applied.** PEP 668 silently blocks `pip install --upgrade` on this
box, so a "newer version still fails" conclusion can be a re-test of the
identical build. Install into a venv and print the version before retrying.

## Rights

- Ask before spending, not after, when the source is a commercial release.
- Personal remix is one thing; distribution or monetisation needs clearance
  from the rights holders. Say it once, plainly, then move on.
- Never scrape lyrics to fill an input. Have the user paste them, write
  original lines, or use public-domain material.
- Check generative-model licences — several music weights are **CC BY-NC**,
  making any output non-commercial regardless of the source rights.

## Pitfalls

- **Routing a "keep the vocals" request to a generation model.** The single
  most expensive mistake in this class.
- **Recommending a model without checking its output sample rate.** Accepting
  audio ≠ emitting quality audio. MusicGen family is 32 kHz, full stop.
- **Picking the preview clip by loudness.** Use the song's opening unless the
  user asked otherwise.
- **Assuming a tempo instead of detecting it.** Synthesized drums at the wrong
  BPM cannot be fixed in the mix.
- **Mixing un-normalised synth stems.** They peak at 0 dBFS and clip on sum.
- **Cover art breaking stream mapping.** Strip before anything else.
- **`-v error` hiding volumedetect output.** Use `-hide_banner`.
- **`astats` cumulative averages** misread as per-block energy.
- **`amix` without `normalize=0`** halves every input.
- **Raising vocal gain instead of ducking the bed** — clips the master.
- **Rendering the full track before a preview.** Always sample first.
- **`Prefer: wait=N` on Replicate caps at 60.** Anything larger returns
  `{"detail": "..."}` with no prediction created. For longer jobs submit
  async and poll; run the poll loop as a background process, since a
  foreground terminal call is capped at 600 s.
- Replicate output URLs expire; download immediately and deliver the file.

## Related

- `ai-cover-songs` — Replicate model routes and verified version hashes
- `wan2gp-yue2-covers` — full regeneration on a rented GPU
- `runpod-pods` — GPU rental mechanics

## Support files

- `references/remix-pipeline.md` — verified transcript, commands, costs
- `references/local-synthesis.md` — deriving tempo/pitch and building a bed
- `scripts/remix.sh` — the preserve-vocals pipeline
- `scripts/trap_synth.py` — tempo/bass analysis + 808, kick, snare, hats, riser
