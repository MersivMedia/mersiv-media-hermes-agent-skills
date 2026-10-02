# Pronunciation scoring options for language-learning apps

Checked 2026-10-01. Use when a PRD needs "listen to the learner and correct their pronunciation".

## Why a dedicated scorer

A voice agent's speech recogniser is built to understand the learner despite mistakes, which is the opposite of grading pronunciation. Score each attempt against a known reference phrase with a dedicated service. Then have an LLM turn the per-phoneme scores into one or two plain tips.

## Options

| Option | Languages | Granularity | Notes |
|---|---|---|---|
| Azure Pronunciation Assessment | de-DE, fr-FR, fr-CA, es-ES, es-MX, it-IT, pt-BR/PT, ja, ko, zh, and ~30 locales in total | Phoneme, syllable, word, full text; accuracy, fluency, completeness | **Prosody (intonation) is en-US only.** Locale list is in the MicrosoftDocs `azure-ai-docs` repo at `articles/ai-services/speech-service/includes/language-support/pronunciation-assessment.md`; the rendered page is too large to grep. Pricing not confirmed from the pricing page. |
| SpeechSuper | EN, ZH, KO, JA, DE, FR, ES, and more | Phoneme-level (German demo shows phoneme results) | Commercial; good fallback. |
| Speechace | EN (US/UK), FR (FR/CA), ES (ES/MX) | Phoneme and syllable | **No German.** Plans start at about $40. |
| Self-hosted `facebook/wav2vec2-xlsr-53-espeak-cv-ft` | Multilingual IPA phoneme recogniser | Phoneme sequence; compare with the reference IPA | Apache-2.0. Needs GPU hosting. Reference code: `crazycloud/mispronunciation-detection-diagnosis-wav2vec2-and-llm`. |
| `bootphon/phonemizer` (espeak-ng) | Most languages | Text → IPA | For the reference IPA on phrase cards; run it in an offline build step. |

## iOS Safari recording trap

Safari's MediaRecorder emits AAC/MP4. Scorers want 16 kHz mono PCM/WAV. Capture PCM with an AudioWorklet and encode WAV on the client. Prove this on the user's actual iPhone in the first spike. Also decide whether the agent mic must be muted while a scored attempt is recorded during a live voice session (assume yes until tested).

## Open content sources for casual phrasebooks

- Tatoeba sentences: CC-BY 2.0 FR, so attribution is required (tatoeba.org/en/terms_of_use).
- Wiktionary colloquialism categories, available as JSON via kaikki.org (wiktextract).
- LLMs default to a polite/formal register. Curate the phrasebook per topic with a `register` field and a `region` field (es-ES vs es-MX, de-DE vs de-AT), and get a native-speaker review pass.
- Spaced repetition: `open-spaced-repetition/ts-fsrs` (TypeScript, MIT, maintained).
- Prior art checked: `challenga-org/openlanguage` (MIT Expo iOS tutor with bring-your-own LLM key). It has no memory and no scoring, so it is a reference only.
