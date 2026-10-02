# Replicate audio models: covers, voice conversion, separation

The image/video guidance in SKILL.md mostly transfers, but audio has one failure
mode of its own: **a music model's description routinely implies a capability
its input schema does not have.** Verify the schema, never the prose.

---

## The one check that settles capability

For a cover — or any audio-conditioned task — you need **audio in, audio out**.
Most music models are text-to-music and cannot hear a source at all.

```bash
curl -s -H "Authorization: Bearer $REPLICATE_API_TOKEN" \
  "https://api.replicate.com/v1/models/$OWNER/$NAME" \
| python3 -c "
import json,sys
d = json.load(sys.stdin)
v = d.get('latest_version')
p = v['openapi_schema']['components']['schemas']['Input']['properties']
for k,x in p.items():
    mark = '  <-- AUDIO IN' if x.get('format') == 'uri' else ''
    print(f\"{k:28} {x.get('type','?'):8}{mark}\")
"
```

**No `format: uri` input means the model cannot transform your audio**,
whatever the description says.

### The worked trap

`minimax/music-1.5` advertises full four-minute songs with natural vocals, and
has 115k runs. Its complete input list:

```
lyrics *   prompt *   bitrate   sample_rate   audio_format
```

No audio input. It is text-to-music, so a style named in `prompt` yields a *new
song*, not a cover. It reads as the perfect answer and is the wrong one. The
schema dump takes five seconds and is the only thing that catches this.

---

## Model survey (verified live)

### Voice covers — reliable

| Model | Runs | Note |
|---|---|---|
| `zsxkib/realistic-voice-cloning` | 2.16M | Separation, conversion and remix in one call |
| `pseudoram/rvc-v2` | 1.52M | Bare RVC; handle stems yourself |

### Style covers — all compromised

| Model | Audio in | Vocals | Limit |
|---|---|---|---|
| `sakemin/musicgen-remixer` | `music_input` | **No** | Instrumental only; follows original chords |
| `meta/musicgen` | `input_audio` | **No** | Melody-conditioned continuation |
| `minimax/music-01` | `song_file` | Yes | **~60 s output cap** |

### Separation

| Model | Runs | Note |
|---|---|---|
| `ryan5453/demucs` | 1.94M | Best quality |
| `triadmusic/stems-separator` | 2.2k | Accepts `youtube_url` directly |

Output is a **dict of stems** (`bass`, `drums`, `other`, `piano`, `guitar`,
`vocals`). There is no `mixture` key — `stems.get("mixture")` returns `None`.

### Do not exist (404)

```
fofr/sheetsage        zsxkib/diffrhythm
```

`fofr/yue` exists but is YuE-s1-7B and **text-only**: `lyrics`,
`genre_description`, `num_segments`, `max_new_tokens`, `seed`, quantization.
No audio or score input, so it cannot perform a cover — despite being the model
every blog-post "AI cover pipeline" names for exactly that.

---

## No single model does full-length style covers with vocals

Chain instead:

```
1  demucs / stems-separator   source -> vocals + instrumental
2  musicgen-remixer           restyle instrumental (keeps chord progression)
3  realistic-voice-cloning    optional: swap the vocal
4  ffmpeg amix                remux
```

```bash
ffmpeg -i restyled_instrumental.mp3 -i vocals.mp3 \
  -filter_complex amix=inputs=2:duration=longest -c:a libmp3lame out.mp3
```

Full length, genre changed, vocals kept. More moving parts than one call, but
no 60-second ceiling.

---

## Audio-specific API notes

- **Community audio models need a pinned version hash** (422 without one);
  official models must not have one. Most audio models are community.
- `client.models.predictions.create(model=…)` is the **official-model** path.
  Community models use `client.run("owner/name:version")`.
- **Reference clips under 15 s are rejected** by minimax. Build a test clip:
  ```bash
  ffmpeg -stream_loop 3 -i short.ogg -t 24 -acodec libmp3lame test_src.mp3
  ```
- The `/v1/models?query=` **search endpoint 403s** with our token. Discover via
  direct `GET /v1/models/{owner}/{name}`, or the web.
- Output URLs expire — download immediately, and hand the user a local file
  path rather than the link.

---

## Music beds for edits: generate a steady bed, place the hits in code

`stability-ai/stable-audio-2.5` (official, $0.20/file, inputs `prompt`,
`duration` 1–190, `steps` 4–8, `cfg_scale` 1–25, `seed`) is good for trailer
beds. **It does not follow timestamps in the prompt.** A 60 s prompt naming
8 cue times ("drop at 0:06, near-silence at 0:27.5 …") came back at 60 BPM,
with −62 dB dead air at 15 s and 30 s, and no hits near the cues.

What worked (3 calls, $0.60):
1. **Bed:** "continuous … at a steady 120 BPM, one unbroken track with no
   silence and no breaks, … steady energy throughout". Ask for ~4 s more
   than needed, since it can open with silence.
2. **SFX, separate calls:** a 4 s "single huge cinematic trailer impact
   hit … isolated sound effect on silence, no music", and a 4 s "riser
   whoosh that builds for three seconds and ends in a sharp suck-in".
3. **Measure, don't trust:** find the bed's real grid by scoring an onset
   envelope on candidate beat grids (100–140 BPM, 10 ms phase steps). It
   measured **120.2 BPM, first beat at 4.18 s**. Then `atempo` it to the exact
   BPM and trim so the reel starts on a beat. Find the time each SFX peaks
   (the impact peaked at 0.18 s, the riser at 3.96 s), then `adelay` each one
   so its PEAK lands on the cut.
4. Duck the bed under the calm shot, fade it under the end card, then
   `amix normalize=0` and `loudnorm I=-14 TP=-1`. That measured −14.3 LUFS
   with no silent windows.

`librosa` wasn't installed; a numpy spectral-flux onset plus a grid search
was enough. The working mixer is in `templates/relay_assemble.py`.

---

## Decide on the transform first: preserve vs regenerate

Before picking any cover tool, settle which of two different jobs is wanted.
They are not interchangeable and no model does both.

```
PRESERVE the backing track    original instrumental, new singer
                              -> RVC (zsxkib/realistic-voice-cloning)
REGENERATE from the melody    melody/chords carried into a new arrangement
                              -> YuE2 (self-hosted)
```

Ask, or infer from the request: "same song, different singer" is preserve;
"this song as 90s heavy metal" is regenerate. Picking the wrong axis produces
technically-successful output the user rejects on first listen.

---

## When no hosted model covers the task

`https://github.com/deepbeepmeep/Wan2GP` (9.5k stars, active) bundles YuE2 with
a cover workflow that extracts melody and chords from a source song — the
capability Replicate lacks. Docker path (`./run-docker-cuda-deb.sh`) plus
headless batch mode makes renting a GPU about an hour of setup.

**SheetSage2 ships with it** (`sheetsage2/SheetSage2_MERT2_bf16.safetensors` in
the same HF repo), so the audio→score step needs no separate install — which is
the part that makes the hand-rolled ComfyUI route painful.

Measured weights for the int8 path, not estimated:

```
1.52 GB  YuE2 Acoustic (int8)      2.93 GB  YuE2 AR (int8)
0.13 GB  YuE2 VAE                  1.35 GB  SheetSage2
-------
5.93 GB  total  -> a 24 GB card is comfortable
```

**Important:** YuE2 covers *regenerate* the backing track; they do not preserve
the original recording. `defaults/yue2.json` says so outright. If the user
wants the real instrumental with a new vocal, stay on RVC.

Licence: repo is `NOASSERTION`, YuE2 weights are **CC BY-NC 4.0
(non-commercial)** wherever they run. Flag it if release or monetisation comes up.

### Read `defaults/*.json`, not the README

These GPU-app repos add models faster than they document them. `docs/MODELS.md`
had no YuE2 entry at all while `defaults/yue2.json` carried the authoritative
spec — supported modes, the ABC-score input, `save_score`, and the sampling
defaults (120 s, 32 steps, guidance 1.0, top_k 100, top_p 0.95).

```bash
curl -s "https://api.github.com/repos/<owner>/<repo>/contents/defaults" \
| python3 -c "import json,sys; [print(i['name']) for i in json.load(sys.stdin)]"
```

**Do not carry a VRAM figure between wrappers of the same model.** The ComfyUI
YuE2 wrapper warns that 24 GB configs are unvalidated and was developed on an
RTX PRO 6000, which made the model look A100-class; Wan2GP's int8 build of the
*3B* (not 7B) runs the same workflow far lighter. Sizing must come from the
specific distribution's own weight files.

### What the agent can and cannot finish here

Pod creation and install are automatable given a provider API key, but the
cover work happens in a **Gradio UI** the user drives in a browser. Say that
before setting anything up — the honest deliverable is a working link, not a
finished song. Headless queue mode exists but queues are built in the UI first.
