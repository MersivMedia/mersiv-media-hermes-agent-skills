# Phase 2 — WhisperX via Replicate (canonical pattern)

There is no local `whisper` or `faster_whisper` module on this host. Phase 2 transcribes via Replicate's `victor-upmeet/whisperx` model. This is the pattern `elevenlabs-narrator-revoice/scripts/revoice.py` already uses; this doc is the condensed standalone version for Phase 2 of this pipeline.

## Steps

1. Extract audio from the source video:
   ```bash
   ffmpeg -y -i source-notebooklm.mp4 -vn -acodec libmp3lame -q:a 4 source-audio.mp3
   ```
2. Upload to tmpfiles.org (free public host, no auth):
   ```python
   r = requests.post('https://tmpfiles.org/api/v1/upload',
                     files={'file': open('source-audio.mp3', 'rb')}, timeout=300)
   url = r.json()['data']['url'].replace('tmpfiles.org/', 'tmpfiles.org/dl/')
   ```
3. Resolve latest WhisperX version:
   ```python
   headers = {'Authorization': f'Token {os.environ["REPLICATE_API_TOKEN"]}',
              'Content-Type': 'application/json'}
   version = requests.get('https://api.replicate.com/v1/models/victor-upmeet/whisperx',
                          headers=headers).json()['latest_version']['id']
   ```
4. Submit prediction (single-narrator, English):
   ```python
   payload = {'version': version,
              'input': {'audio_file': url, 'diarization': False,
                        'batch_size': 32, 'language': 'en'}}
   r = requests.post('https://api.replicate.com/v1/predictions',
                     headers=headers, json=payload, timeout=120)
   pred_id = r.json()['id']
   ```
5. Poll every 3s until status in `('succeeded', 'failed', 'canceled')`. Typical 6-9 min source transcribes in 30-90s.
6. Save raw `output` blob at `episodes/{slug}/transcript.json`.

## Output shape

WhisperX returns:
```json
{
  "detected_language": "en",
  "segments": [
    {"start": 0.0, "end": 7.14, "text": "...",
     "words": [{"start": 0.2, "end": 0.5, "word": "Today"}, ...]}
  ]
}
```

Same structure Phase 3's script-rewrite code already expects, with word-level timestamps usable for tight VO-to-visual alignment.

## Pitfalls

- **Do NOT call `import whisper` or `import faster_whisper`** from a Phase 2 script. Neither is installed. The `mlops/models/whisper` skill is reference docs for local Whisper on a GPU box — not applicable here.
- **Background the poller** with `terminal(background=true, notify_on_complete=true)`. WhisperX itself can take 30-90s on a 6-9 min audio file, which is too long to block-poll inside a subagent (eats the delegate_task budget).
- **tmpfiles.org URLs expire** (~1 hour). Submit the Replicate prediction promptly after upload.
- **`language='en'` matters** — without it WhisperX sometimes guesses Korean/Chinese for silent passages (verified hallucination in Ep5 scene 06).
- **Filter language code** — sometimes it returns `"english"` instead of `"en"`. Normalize before persisting if downstream tools care.

## Cost

~$0.001 per minute of audio. A typical 6-9 min episode = ~$0.01. Negligible vs Phase 1 ($0.50) and Phase 6 ($0.30-0.60).
