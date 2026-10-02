# Pricing and model notes (checked 2026-10-01; re-verify, promos expire)

Sources: https://elevenlabs.io/pricing/agents, https://elevenlabs.io/pricing/api, https://elevenlabs.io/docs/overview/capabilities/text-to-speech/eleven-v4, https://docs.x.ai/developers/pricing.md

## ElevenLabs Agents

- Voice call minutes: $0.08/min on every plan (included minutes vary by plan); burst over concurrency $0.16/min. 95% discount on silence >10 s. Billed on connection time, so close sessions promptly.
- Text-only messages: $0.003 per message, plus LLM pass-through.
- LLM pass-through measured: Claude Haiku 4.5, 2-turn text exchange ≈ 10.7K input tokens (no cache hits) → $0.019 total, ≈ $0.008/message. A long system prompt + lesson material dominates cost.
- The TTS model choice does NOT change the per-minute agent price.

## Standalone TTS (phrase audio, per 1K chars)

| Model | List | Note |
|---|---|---|
| Flash / Turbo v2.5 | $0.04 | has `speed` → supports slow replay |
| Eleven v4 Turbo (`eleven_v4_turbo`) | $0.04 | promo $0.011 until 2026-10-12; real-time variant |
| Eleven v4 (`eleven_v4`) | $0.08 | promo $0.022 until 2026-10-12 |

Phrase audio is tiny: cache each clip after first generation; 500 phrases x 2 speeds ≈ $1-2.

## Eleven v4 behavior that matters for tutors

- Cross-language: a cloned voice speaking another language comes out fluent and native (no carried-over accent). Older models carried the source accent. So a v4 clone of the owner can coach in English AND model target-language phrases.
- No Style/Speed sliders, no SSML. Only Stability + Similarity.
- VERIFIED: an English multi-voice agent accepts `eleven_v4_turbo` (supported voices need `model_family: "v4_turbo"`). The live round-trip spoke German correctly (STT transcript matched). The user chose v4 Turbo for the agent; phrase-card TTS stays on Flash v2.5 for the slow-replay speed setting.
- Measured voice cost on v4 Turbo: 31 s ≈ $0.017, 13 s ≈ $0.007 (`cost_fiat`).
- Voice cloning needs at least the Starter plan; pay-as-you-go accounts can't clone.

## Grok voice (xAI) comparison

- `grok-voice-think-fast-2.0` ≈ $0.08/min, same as ElevenLabs.
- One voice per session: no mid-sentence native voice switching, so an English-sounding voice would model foreign phrases. That's the deciding factor for language tutors.
- Raw WebSocket client only (no official React-style SDK); custom voices free in console (US only).
- User decided to stay on ElevenLabs.

## Other options evaluated

- Pronunciation scoring: Azure Pronunciation Assessment supports de-DE, fr-FR, es-ES, es-MX at phoneme level; Speechace lacks German. User cut scoring from v1 as too much extra development.
- Open model for later: `facebook/wav2vec2-xlsr-53-espeak-cv-ft` (phoneme recognition).
- Reference app: github.com/challenga-org/openlanguage (MIT Expo tutor; no memory/scoring).
