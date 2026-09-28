# [brand] Narrator Workflow

Reference for re-narrating NotebookLM-source space content videos with the [character] voice.

## Voice casting

- **Narrator** (`TyJfVqGmT0iahaNbUE37`, shortcut `narrator`) — primary narrator. Older gruff theatrical [character] in his 60s. Used for all current content videos.
- **Narrator Alt** (`6zTRy4vPhz1hAPsZhT9A`, shortcut `narrator-alt`) — alt voice, deeper and gravellier, less theatrical. Kept on hand as a backup or for specific content tones.

Both shortcuts live in `~/.hermes/skills/creative/elevenlabs-voice-changer/scripts/voices.json` (shared between voice-changer and narrator-revoice skills).

## Empirically-validated parameters

For a typical 6-minute NotebookLM source (~6000 chars transcript):

- `--voice narrator`
- `--stretch-video` ([character] voice is ~14% slower than NotebookLM hosts; stretch slides proportionally)
- Default chunking (no `--max-chars` override) — yields 3 balanced chunks of ~2000 chars each
- `--language en` if running through STT
- `--text-override path/to/transcript.txt` on re-runs to skip Replicate WhisperX cost

```bash
python ~/.hermes/skills/creative/elevenlabs-narrator-revoice/scripts/revoice.py \
  /tmp/hermes/edit_topicNN/content-with-wordmark.mp4 \
  /tmp/hermes/topicNN-narrated.mp4 \
  --voice narrator \
  --language en \
  --stretch-video \
  --workdir /tmp/hermes/revoice_topicNN \
  --keep-workdir
```

## Full pipeline for a [brand] topic

1. **Content-only video** comes from `creative/notebooklm-brand-edit` (the `content-with-wordmark.mp4` intermediate). NEVER run revoice on a video that already has intro/outro music — TTS will replace those silent regions with nothing.
2. **If only an intro/outro-attached version is available**, trim the first and last 7.082s with ffmpeg `-ss`/`-to` to recover content-only.
3. **Run revoice with `--stretch-video`** as above. Output is a content-only video with new narration and slides timed to match.
4. **Concat intro + narrated + outro** using the 24fps faded variants in `/tmp/hermes/edit_intros/` (intro-24-faded.mp4, outro-24-faded.mp4) with ffmpeg `concat` filter:
   ```bash
   ffmpeg -y \
     -i edit_intros/intro-24-faded.mp4 \
     -i topicNN-narrated.mp4 \
     -i edit_intros/outro-24-faded.mp4 \
     -filter_complex "[0:v][0:a][1:v][1:a][2:v][2:a]concat=n=3:v=1:a=1[v][a]" \
     -map "[v]" -map "[a]" \
     -c:v libx264 -preset fast -crf 18 -c:a aac -b:a 192k \
     topicNN-narrated-final.mp4
   ```
5. **Upload to the topic's Drive folder** under `[brand] > Blogs > NN - Topic Name — Pillar`.

## Cost-saving trick

The Replicate WhisperX call is the only Replicate-billed step. If you're iterating on voice settings, save the transcript from the first run and reuse with `--text-override`:

```bash
# First run: generates transcript.json
revoice.py in.mp4 out-v1.mp4 --voice narrator ...

# Extract clean text for reuse
python3 -c "
import json
d = json.load(open('out-v1.transcript.json'))
text = d.get('text') or ' '.join(s.get('text','').strip() for s in d.get('segments', []))
open('transcript.txt', 'w').write(text.strip() + '\n\n\n\n\n')
"

# Subsequent runs: no Replicate cost, only ElevenLabs TTS
revoice.py in.mp4 out-v2.mp4 --voice narrator --text-override transcript.txt ...
```

Append trailing blank lines to the transcript txt if a human will copy-paste it on mobile (Drive's text preview strips trailing whitespace from rendered selection).
