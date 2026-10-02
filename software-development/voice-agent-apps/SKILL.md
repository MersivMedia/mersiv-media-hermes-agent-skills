---
name: voice-agent-apps
description: Build voice-agent apps with memory, dashboards, deploys.
version: 1.0.0
author: MersivMedia + Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [elevenlabs, voice-agent, tutor, nextjs, vercel, memory, dashboard]
    related_skills: [elevenlabs-narrator-revoice, elevenlabs-voice-changer, claude-design, grounded-citations, plan]
---

# Voice Agent Apps Skill

Build small personal or client apps around a hosted conversational voice agent (ElevenLabs Agents first): a chat surface with a talk mode, persistent per-user memory, an owner dashboard, and a Vercel deploy. Covers tutors, coaches and companions. It does not cover video re-voicing (see `elevenlabs-narrator-revoice`) or GPU-hosted speech models.

## When to Use

- "Build an AI agent that talks with X and remembers what it taught them"
- Language tutors, practice partners, coaching bots, voice companions built on ElevenLabs Agents (or Grok voice / OpenAI realtime as alternatives)
- Any app where one agent must serve both typed chat and spoken conversation, with state that lives outside the agent

## Prerequisites

- `ELEVENLABS_API_KEY` (and `VERCEL_TOKEN` for deploy) in `~/.hermes/.env`. Load them with a wrapper script that exports from `.env` without echoing, never in argv.
- Node 22 + Next.js (App Router). `@elevenlabs/client` for the browser SDK (`@elevenlabs/react` just re-exports it).

## Requirements checklist: ask these UP FRONT

The user added each of these mid-build in the first project. Ask them in the first PRD round instead:

1. **UI shape.** Default: simple chat window + one button to switch to hands-free voice mode, a dropdown for the main axis (language/subject), and 3-4 suggestion chips that change as the user progresses. Title text? (e.g. "a personal language tutor"). Style: clean, elegant, few colors, big tap targets, iPhone-first.
2. **Open topics.** If the end user is an adult, they may want anything (slang, swearing, flirting, sexual vocabulary, dark humor). The structured curriculum is only the default when they have no request. Prompt: teach it straight, no refusing/moralizing/disclaimers, rate crudeness, say when it lands vs. gets you in trouble. One hard line: nothing sexual involving minors.
3. **Owner test, then hand-off reset.** The owner wants to test after deploy and then reset so the recipient starts clean. Design progress around "learner periods" (archive, never delete). The reset button lives ONLY in the owner dashboard, which the recipient must not be able to see or even detect. See Architecture.
4. **Owner dashboard.** Progress, cost so far, daily usage, time of day, which languages/modes, session transcripts. Behind a separate admin password.
5. **Budget ceiling.** A monthly cap (e.g. $60), a daily voice-minutes cap, and voice cutoff before the cap so chat keeps working.
6. **Voices.** Standard library voices for prototyping; owner's clone later (needs a paid plan for cloning).
7. **Scope cuts.** Offer heavy extras (e.g. pronunciation scoring via Azure) as optional. The user cut it as "a lot more development we don't need".

Lay the plan out and get sign-off before paid or account-modifying actions (adding voices to the account, creating agents).

## Architecture (default)

- **One agent, two modes.** Text chat = same agent with `conversation.text_only: true` override over a signed WebSocket URL. Voice = WebRTC conversation token. No drift between typed and spoken tutor.
- **Multi-voice.** English coach as default voice, native voices per target language, switched by XML tags the LLM emits (`<German>Hallo</German>`). Strip the tags into styled phrase chips in the UI.
- **Memory lives in your app, not the agent.** Before each session inject a compact learner brief + lesson material via `dynamic_variables`. During the session the agent calls **client tools** (`teach_phrase`, `record_review`) that the browser forwards to your API. After the session, reconcile from `GET /v1/convai/conversations/{id}`: back-fill tool calls the browser missed (dedupe by `request_id`) and record `metadata.cost_fiat`.
- **Spaced repetition:** `ts-fsrs` cards per learned item; suggestion chips are rule-based (review / next / stretch / wildcard), deterministic per (progress, day).
- **Storage:** private Vercel Blob store as a JSON document store with ETag `ifMatch` optimistic concurrency (agents often fire two tool calls at once). Template: `templates/blob-json-store.ts`.
- **Reset = new period.** `meta.json` holds `currentPeriod` + history; all learner/session docs live under `p/<period>/`. "Reset for <name>" starts a new period; the dashboard can still view old ones. Budget sums across ALL periods (testing is real money).
- **Auth:** learner opens a private link `/?key=…` → long-lived HMAC cookie, and the app is served WITH the key still in the URL (no redirect) so "Add to Home Screen" captures it. Owner signs in at `/admin/login`. Admin can also use the app.
- **Delivery = home-screen web app + silent auto-update.** No App Store. The client compares its baked-in `VERCEL_DEPLOYMENT_ID` with a public `/api/version` on wake and reloads only when idle (no voice call, no reply pending, empty input). Template: `templates/use-auto-update.ts`; proof: `scripts/update-check.py`.

## Procedure

1. Research + PRD with citations (`grounded-citations`), publish to Drive with `md2gdoc.py --company`, revise with `--doc-id`.
2. **Spike before UI.** Keep the agent definition in the repo (`agent/agent.json` + `agent/prompt.md`) and push it with an idempotent `scripts/sync-agent.mjs` (tools matched by name, agent by name; writes `agent/agent-id.txt`). Then drive the real agent in text-only mode from Node over the raw WebSocket and confirm: signed-URL auth, dynamic variables, voice tags, tool calls, cost. Details: `references/elevenlabs-agents-api.md`.
3. Test the content policy on the live agent with real requests before claiming it works.
4. Curriculum/content as typed data files; pure logic (chips, brief, cost math, markup parsing) in `lib/` with unit tests.
5. Storage, auth, API routes (session start, tool calls, reconcile, TTS cache), then UI, then dashboard.
6. Deploy to Vercel (remote build), run E2E + screenshots + `scripts/reset-check.mjs` on production, then leave a fresh "owner testing" period. Hand over: the learner link, the admin URL and password, install steps for the recipient's browser, what was verified, and what wasn't (real-iPhone mic is on the owner). Ask public vs private before creating a GitHub repo for a personal app: the default-public rule doesn't fit apps with personal prompts and content.
7. Ship auto-update before hand-off (`templates/use-auto-update.ts`) and prove it with `scripts/update-check.py` (it redeploys; run it in the background).
8. **Build generic from day one.** The owner later wants a public, genericized repo, and the first build did. Keep these in env-driven `lib/config.ts` from the start, not in code:
   - learner name, app title, persona name, icon letter, time zone
   - content policy (`OPEN_TOPICS=standard|adult`)
   - budget

   Also from the start:
   - Write prompts pronoun-neutral.
   - Put owner-only scripts in a gitignored `.local/`.

   Retrofitting this cost a full pass. The procedure (genericize in place, keep the live instance identical via Vercel env, leak gate, fresh-clone verify) is in `references/open-sourcing-a-personal-instance.md`.

## Pitfalls

- English-language agents reject `eleven_flash_v2_5` and other non-English-capable models (`English Agents must use turbo or flash v2`). Accepted: `eleven_flash_v2` (voices `model_family: "flash"`) and `eleven_v4_turbo` (voices `model_family: "v4_turbo"`, verified live). Default to v4 Turbo when the user wants the best voice; it costs the same per minute.
- **Vercel Blob weak ETags.** Private `get()` returns `W/"…"` for docs over ~1KB; `put({ifMatch})` rejects it, so EVERY write to a grown doc fails with "ETag mismatch" while tests on small fresh docs pass. Strip `W/`. Also retry on "conditional request cannot succeed due to a conflicting operation". Both are in `templates/blob-json-store.ts`. Match errors by message, not only `instanceof`.
- **Silent voice sessions log nothing.** An empty agent `first_message` plus a quiet user gives a completed, billed conversation with 0 transcript turns. Send a per-session `overrides.agent.firstMessage`.
- The SDK has no max-duration override; enforce the daily voice cap with a client countdown that ends the session, with the agent's `max_duration_seconds` as backstop.
- Hide the owner surface completely: non-admins get **404** (not 401/403) on `/admin*` and `/api/admin*`, enforced in `proxy.ts` AND in each admin handler. Template: `templates/proxy-two-role-auth.ts`.
- When the learner app detects a new period id from the server, clear the device's cached chat threads. Otherwise a reset leaves old chat visible on her phone.
- **Never redirect away the private-link key.** iOS home-screen web apps don't reliably share the browser's cookies, so an icon saved from the clean `/` opens to the locked page. The first build did this; the owner hit it on day one ("it didn't download the app"). Keep `?key=` in the URL.
- Owners expect a "download". Say up front that it's a home-screen web app, and give install steps for the recipient's actual browser (Safari / Chrome / Firefox differ). See `references/handoff-and-install.md`.
- A `NEXT_PUBLIC_*` value set in `next.config.ts` `env` is inlined into the client bundle. To verify, grep every `/_next/static/**.js` chunk: Next 16 + Turbopack serves them from `/_next/static/immutable/chunks/`, not `/_next/static/chunks/`.
- Version/health endpoints the client polls before auth must be whitelisted in `proxy.ts`, or they quietly return 401 and the feature looks dead.
- The agent correctly reviews instead of re-teaching known items, so E2E assertions on `teach_phrase` must use a topic the learner hasn't started.
- Don't `next build` locally on this small box (OOM, exit 143). Typecheck + vitest locally, build remotely on Vercel. See `references/deploy-and-verify.md`.
- Library voices give `voice_not_found` until added to the account (`POST /v1/voices/add/{public_user_id}/{voice_id}`). This modifies the user's account; ask first.
- Text chat is NOT free: measured ~$0.008/message on Claude Haiku 4.5 (≈10K uncached input tokens for 2 turns) plus $0.003/message platform fee. Count chat toward the budget.
- An older-model voice clone carries the speaker's accent into other languages; Eleven v4 deliberately does not (speaks the target language natively). v4 has no speed setting, so "slow replay" needs Flash/v2.5.
- Voice minute price ($0.08) does not change with the TTS model; only standalone TTS calls do. See `references/pricing-and-models.md`.
- Don't trust the voice agent's ASR for pronunciation grading. It is built to understand mistakes, not score them. Say so in the prompt and PRD.
- When docs pages are huge, write extracted sections to a file and read line ranges; screened tool output can hide the schema lines you need.

## Verification

- Spike script prints: conversation id, agent turns with voice tags, tool calls with params, `cost_fiat`.
- After a session, the conversation's transcript `tool_calls` match the stored learner phrases (no duplicates after reconcile).
- Dashboard numbers reconcile with ElevenLabs `cost_fiat` per conversation.
- On the actual phone: mic permission in voice mode, voice switching audible, reset leaves an empty learner state while old periods stay viewable.

## References

- `references/deploy-and-verify.md`: Vercel provisioning (secrets, private Blob, SSO off), remote-build deploy, prod debugging via a temporary admin diag route, E2E/screenshot/reset verification, and the credential hand-over.
- `references/elevenlabs-agents-api.md`: endpoints, WebSocket protocol, override gating, conversation payload fields, docs access tricks.
- `references/pricing-and-models.md`: agent/TTS pricing, v4 behavior, Grok voice comparison (Oct 2026).
- `references/handoff-and-install.md`: per-browser iPhone home-screen install steps, why the key stays in the URL, what updates reach the recipient automatically, pre-hand-off reset caveats.
- `references/open-sourcing-a-personal-instance.md`: turn a personal deployment into a public generic repo without changing the live instance. Covers config extraction, the topic-policy toggle, the generated icon route, setup scripts, `.local/` owner tooling, leak-gate pitfalls and fresh-clone verification.
- `templates/blob-json-store.ts`: Vercel Blob JSON store with ETag retry (weak-ETag fix included).
- `templates/proxy-two-role-auth.ts`: Next.js 16 proxy for private learner link (key kept in URL) + hidden admin (404) + public `/api/version`.
- `templates/use-auto-update.ts`: silent reload-when-idle on new deployment (wiring for next.config + version route in the header).
- `scripts/reset-check.mjs`: proves the hand-off reset on production (performs a REAL reset).
- `scripts/update-check.py`: CDP proof of auto-update on production (redeploys; 6 assertions).
