---
name: ai-cover-songs
description: Render audio cover songs via Replicate, no GPU needed.
version: 1.0.0
author: Hermes
license: MIT
metadata:
  hermes:
    tags: [music, audio, replicate, cover, rvc, voice-conversion]
    related_skills: [cover-songs, heartmula, replicate-api-generation]
---

# AI Cover Songs (Replicate, no local GPU)

## When to Use

Use when the user wants to **actually render audio** — change a song's genre,
swap the vocalist, or rebuild a track from a YouTube link. Triggers: "make a
cover", "cover song audio", "change the singer", "remix this track", "YuE",
"SheetSage", "ABC notation cover".

For Suno-style prompt/lyric *text* output instead, use the `cover-songs`
skill — the two are complements, not duplicates.

## Decide the route first

Picking wrong wastes money and time.

| Goal | Route | Keeps original recording? |
|---|---|---|
| Same song, different singer | **A — RVC voice conversion** | Yes; instrumental untouched |
| Same song, different genre/arrangement | **B — reference-conditioned generation** | No; regenerates audio |
| Full re-arrangement with editable melody | **C — SheetSage2 → YuE2 score route** | No; score-conditioned |

**Route A is the default.** Cheapest, most reliable, and what most people mean
by "cover".

---

## Verified model IDs

Checked live against the Replicate API. All are **community models and require
a pinned version hash** — omitting it causes a 422.

```
triadmusic/stems-separator:171d8e6a1e4a870b0f17f00c850b3d89d1205848a129d6110a933feaffb2ea6a
zsxkib/realistic-voice-cloning:0a9c7c558af4c0f20667c1bd1260ce32a2879944a0b9e44e1398660c077b1550
minimax/music-01:0254c7e2f54315b667dbae03da7c155822ba29ffe0457be5bc246d564be486bd
sakemin/musicgen-remixer:0b769f28e399c7c30e4f2360691b9b11c294183e9ab2fd9f3398127b556c86d7
```

**Re-verify before every run.** Community versions get superseded, and a stale
hash fails with a 422 that does not say why:

```bash
set -a; . ~/.hermes/.env; set +a
python3 scripts/cover.py --verify
```

`REPLICATE_API_TOKEN` is in `~/.hermes/.env`. Env vars are
**not** inherited by `execute_code` — run from `terminal` with
`set -a; . …/.env; set +a`.

**urllib gets 403 from the Replicate API** (user-agent filtering); `curl`
works. `scripts/cover.py` shells out to curl for this reason.

## Quick start

```bash
set -a; . ~/.hermes/.env; set +a
cd ~/.hermes/skills/music-creation/ai-cover-songs/scripts

python3 cover.py --verify                        # always first
python3 cover.py --route voice \
  --source "https://youtube.com/watch?v=..." \
  --rvc-model Drake --out cover.mp3
```

---

## Route A — voice conversion (recommended)

Replaces the vocal, keeps the original instrumental. One call —
`zsxkib/realistic-voice-cloning` does separation, conversion and remixing
internally, so no separate stem step is needed.

```python
import replicate, os
client = replicate.Client(api_token=os.environ["REPLICATE_API_TOKEN"])

out = client.run(
    "zsxkib/realistic-voice-cloning:<pinned-version>",
    input={
        "song_input": "https://example.com/source.mp3",
        "rvc_model": "CUSTOM",
        "custom_rvc_model_download_url": "https://.../voice.zip",
        "pitch_change": "no-change",     # or male-to-female / female-to-male
        "index_rate": 0.5,               # accent strength of the AI voice
        "protect": 0.33,                 # preserves breath/consonants
        "rms_mix_rate": 0.25,            # 0 = original dynamics, 1 = flat
        "pitch_detection_algorithm": "rmvpe",
        "output_format": "mp3",
    },
)
print(out)   # single URI
```

**Built-in voices** (no training): `Squidward`, `MrKrabs`, `Plankton`, `Drake`,
`Vader`, `Trump`, `Biden`, `Obama`, `Guitar`, `Voilin`. Anything else needs
`rvc_model="CUSTOM"` plus a `.zip` of a trained RVC v2 model.

**Parameter guidance**

- `protect` 0.2–0.4. Lower sounds more like the target but smears consonants;
  raise if the vocal sounds mushy.
- `index_rate` 0.3–0.7. Above 0.7 the accent dominates and artefacts appear.
- `pitch_change` matters across vocal ranges. Leaving `no-change` on a
  male→female swap is the most common cause of a chipmunk result.

---

## Route B — reference-conditioned generation

Regenerates the track in a new style, conditioned on a reference. Use when the
*arrangement* should change, not just the voice.

```python
out = client.run(
    "minimax/music-01:<pinned-version>",
    input={
        "lyrics": "[verse]\nline one\nline two\n\n[chorus]\nhook line",
        "song_file": "https://example.com/reference.mp3",   # >15s, wav/mp3
        "sample_rate": 44100,
        "bitrate": 256000,
    },
)
```

Inputs: `lyrics`, `song_file`, `voice_file`, `instrumental_file`, `voice_id`,
`instrumental_id`. References must exceed **15 seconds**.

**Hard limit: about one minute of output.** For a full song, generate sections
separately and join — expect timbre drift between them.

For instrumentals, `sakemin/musicgen-remixer` takes `music_input` plus a
`prompt` and follows the original chord progression.

---

## Route C — SheetSage2 → YuE2 score route

The "ABC notation" workflow. Real, and the most controllable — but it does not
run on Replicate.

```
source mp3 ──► SheetSage2 ──► score.abc ──► YuE2 (abc + style + lyrics) ──► audio
                     melody_only=True          cot="melody"
```

SheetSage2's `melody_only=True` keeps vocal and instrumental melodies, drops
chord symbols, and writes `cover-score/score.abc`. Its model card documents
passing that to YuE2 as `abc` with `cot="melody"` as the cover path.

**Why generic MIDI→ABC converters fail:** YuE2's parser expects SheetSage2's
native notation and rejects otherwise-valid ABC.

### The blocker

**Neither SheetSage2 nor YuE2-3B is on Replicate.** Verified against the API:

- `fofr/sheetsage` → **404, does not exist**
- `fofr/yue` → exists, but is YuE-s1-7B and **text-only**. Inputs are `lyrics`,
  `genre_description`, `num_segments`, `max_new_tokens`, `seed`,
  `quantization_stage1/2`. **No audio or score input** — it generates new music
  from a text prompt and cannot perform a cover.

Route C therefore needs local hardware:

| Component | Requirement |
|---|---|
| `ComfyUI-FL-YuE2` | NVIDIA GPU with BF16; validated on RTX PRO 6000 Blackwell. **24 GB configs explicitly unvalidated** |
| Model download | ~7.8 GB into `ComfyUI/models/yue2/` |
| SheetSage2 | Separate install; torch 2.8.0 + cu126 |
| Licence | Weights **CC BY-NC 4.0 — non-commercial**, both |

The ComfyUI piano-roll node does **not** transcribe audio — its README states
"MIDI-file import/export and audio transcription are not included". SheetSage2
is a separate step, and inside that repo it appears only in the *training* path.

**If the user has no GPU**, say so plainly and offer Route A or B. Never
fabricate a Replicate endpoint for YuE2.

**If renting**, A100 40GB is the safe floor since 24 GB is unvalidated.
Roughly $1.50–3.50/hr; several covers fit in an hour.

---

## YouTube as a source

`triadmusic/stems-separator` accepts `youtube_url` directly — no local download.

```python
stems = client.run(
    "triadmusic/stems-separator:171d8e6a...",
    input={"youtube_url": url, "format": "mp3", "model_name": "htdemucs"},
)
```

**Output is a dict of stem URLs**, not a mixture:

```python
{"bass": ..., "drums": ..., "other": ..., "piano": ..., "guitar": ..., "vocals": ...}
```

There is **no `mixture` key** — `extraction.get("mixture")` returns `None`.
Use `stems["vocals"]`, or rebuild a backing track:

```bash
ffmpeg -i bass.mp3 -i drums.mp3 -i other.mp3 \
  -filter_complex amix=inputs=3:duration=longest backing.mp3
```

`ryan5453/demucs` (1.9M runs) is the alternative when separation quality
matters more than YouTube convenience.

---

## Cost

| Step | Typical |
|---|---|
| Stem separation | ~$0.02–0.05 |
| RVC voice conversion | ~$0.05–0.15 per song |
| minimax/music-01 | ~$0.10–0.30 per minute |
| Route C on rented GPU | $1.50–3.50/hr plus setup |

**Run one song end to end before batching.** Dry-run, single test, then batch.

---

## Workflow

1. **Ask what should change** — voice or arrangement. Nothing else matters
   until that is answered; it selects the route.
2. **Re-verify version hashes.** Community models move.
3. **Get source audio.** YouTube → stems-separator; direct file → skip.
4. **Run one song.** Listen before spending more.
5. **Deliver the file**, not the URL — Replicate links expire. `curl -L -o
   cover.mp3 "$URL"` and hand over the local path.

## Pitfalls

- **`fofr/yue` cannot do covers.** Text-only. The most common mistake in
  blog-post pipelines for this workflow.
- **`extraction.get("mixture")` is always `None`.** Wrong key.
- **Community models need a pinned version**; official models must not have one.
- **`client.models.predictions.create(model=…)` is for official models only.**
  Community models use `client.run("owner/name:version")`.
- **Reference files under 15 seconds** are rejected by minimax.
- **Replicate output URLs expire** — download immediately.
- **CC BY-NC 4.0** on YuE2 and SheetSage2 weights — non-commercial only. Flag
  if the user mentions release or monetisation.
- **Copyright**: distributing covers of published songs needs mechanical
  licences. Mention once when output is headed for release.

## Related

- `cover-songs` — Suno-ready lyrics and style text, no audio
- `heartmula` — song generation from lyrics and tags
- `replicate-api-generation` — general Replicate REST patterns
