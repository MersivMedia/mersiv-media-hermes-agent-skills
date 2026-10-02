# ElevenLabs Agents (ElevenAgents): facts for app PRDs and build-outs

Checked against the live docs and API on 2026-10-01, during the Travel Language Tutor PRD and its first build spike. Re-check prices, model lists and SDK versions before quoting them; all of them change.

## Fetching the docs

Every docs page is also served as markdown: append `.md` to the page path, e.g. `https://elevenlabs.io/docs/eleven-agents/customization/voice/multi-voice-support.md`. The index is `https://elevenlabs.io/docs/llms.txt`; the full dump is `llms-full.txt`. API reference pages follow `https://elevenlabs.io/docs/api-reference/<area>/<op>.md` (agents/create, tools/create, conversations/get, conversations/get-signed-url, webhooks/create, voices/voice-library/share).
- Fetch with `curl -sL` when `web_extract` is unavailable (for example a search-only backend such as ddgs). Save pages to files and grep them.
- `agents/create.md` is about 180 KB. Pull single type sections out with an awk/regex on `### <TypeName>` into a file, then `read_file` the line ranges. Tool-output relevance screening hides schema lines in long greps; read ranges are never screened.

## Capabilities that shape an architecture

| Feature | Fact | Doc path |
|---|---|---|
| Multi-voice | The agent switches voices mid-reply with XML-style tags `<Label>…</Label>`. `tts.supported_voices[]` = {label, voice_id, language, model_family, description}. Max 10 voices, no nested tags, labels are case-sensitive. "Language tutoring" is a listed use. | customization/voice/multi-voice-support |
| Dynamic variables | `{{var}}` placeholders in the prompt, first message and tool params. Declare defaults in `agent.dynamic_variables.dynamic_variable_placeholders`; pass real values per session. System vars include `system__is_text_only`. | customization/personalization/dynamic-variables |
| Text-only (chat) mode | One agent serves chat and voice. Turn it on per session with the override `conversation.text_only`, which must be allowed in `platform_settings.overrides.conversation_config_override.conversation.text_only=true`. The SDK must handle `agent_response`, or chat shows nothing. | guides/chat-mode |
| Client tools | `type: client`, created via `POST /v1/convai/tools`, attached by `prompt.tool_ids`. `expects_response:false` = fire-and-forget (the agent doesn't wait). The handler name in the SDK's `clientTools` must match the tool name. | customization/tools/client-tools |
| Post-call webhook | Workspace webhook (`POST /v1/workspace/webhooks`, HMAC settings, returns the secret), attached per agent via `platform_settings.workspace_overrides.webhooks.{post_call_webhook_id, events:["transcript"]}`. | workflows/post-call-webhooks |
| Auth | `platform_settings.auth.enable_auth=true`. The server calls `GET /v1/convai/conversation/get-signed-url?agent_id=` (WebSocket; the SDK uses this for text) or `/conversation/token` (WebRTC; the SDK uses this for voice). The key never reaches the client. | customization/authentication |
| Conversation record | `GET /v1/convai/conversations/{id}` → `metadata.call_duration_secs`, `metadata.cost_fiat` (USD), `metadata.charging` (llm vs platform split), `transcript[].tool_calls[].{tool_name, params_as_json}`. Use it for budget accounting and memory reconciliation. | api-reference/conversations/get |
| Guardrails | `platform_settings.guardrails.content.config.{sexual,violence,harassment,self_harm,profanity,...}.is_enabled`, all **false** by default on a new agent. Read them with `GET /v1/convai/agents/{id}`. | api-reference/agents/create |
| Limits | `conversation.max_duration_seconds` (default 600), `turn.turn_timeout` (1–30 s), `turn.turn_eagerness` patient/normal/eager. | customization/conversation-flow |
| LLM choice | `prompt.llm` enum includes claude-haiku-4-5, claude-sonnet-*, gpt-*, gemini-*. | customization/llm |

## Build recipe (verified working, 2026-10-01)

1. Keep the agent as code in the repo (`agent/agent.json` + `agent/prompt.md`) with an idempotent `sync-agent` script. The script upserts tools by name (`GET /v1/convai/tools`, then PATCH or POST), then upserts the agent by name (`GET /v1/convai/agents?search=`, then PATCH `/v1/convai/agents/{id}` or POST `/v1/convai/agents/create`), and writes the id to `agent/agent-id.txt`.
2. **Library voices must be in the account first.** An agent referencing a Voice Library id fails with `voice_not_found`. Add each one with `POST /v1/voices/add/{public_owner_id}/{voice_id}` and body `{new_name}`. Find `public_owner_id` from `/v1/shared-voices?search=`. Ask the user before adding: it changes their account's My Voices.
3. Find candidate native voices with `GET /v1/shared-voices?gender=female&language=de&accent=standard&use_cases=conversational&sort=usage_character_count_1y` (accent values seen: `mexican`, `parisian`, `american`, `standard`). Skip results with `live_moderation_enabled: true` when the content may be adult.
4. **English agents must use TTS `eleven_flash_v2` or a turbo v2 model** (400: "English Agents must use turbo or flash v2"). Set `model_family: "flash"` on each supported voice; the target-language voices still work through multi-voice tags.
5. **Spike in text mode from Node 22 before building any UI.** Node 22 has a global `WebSocket`, so no SDK is needed:
   - get a signed URL;
   - send `{type:"conversation_initiation_client_data", conversation_config_override:{conversation:{text_only:true}}, dynamic_variables:{...}}`;
   - wait for `conversation_initiation_metadata` (it holds the conversation_id);
   - answer `ping` with `{type:"pong", event_id}`;
   - send `{type:"user_message", text}`;
   - read `agent_response` and `client_tool_call`.

   Then GET the conversation for its cost. Check that the voice tags appear and the tools fire with sensible params.
6. Run secrets through a small wrapper script (`.withenv.sh` that reads `.env` and execs the command, gitignored) so keys never appear in argv or output.

## SDKs and platforms

- `@elevenlabs/react` 1.16 re-exports `@elevenlabs/client` 1.26. It provides `ConversationProvider`, the granular hooks (`useConversationControls`, `useConversationStatus`, `useConversationMode`, `useConversationClientTool`), and `startSession({signedUrl|conversationToken, dynamicVariables, overrides, userId, textOnly})`. `sendUserMessage`, `sendContextualUpdate` and `sendUserActivity` are on the controls.
- `@elevenlabs/react-native` needs Expo development builds (LiveKit WebRTC) and doesn't run in Expo Go. A Swift SDK also exists.
- Default plan for an iPhone user: a Next.js PWA on Vercel first, native later only on a concrete trigger.

## Pricing and measured costs

- Voice: **$0.08/min** list (elevenlabs.io/pricing/api). The pay-as-you-go tier can't clone voices (`can_use_instant_voice_cloning: false` in `/v1/user/subscription`).
- **Text-only mode is not free.** Measured: 3 chat turns on claude-haiku-4-5 with a ~3 KB prompt cost $0.024 (LLM $0.015 for 12k input tokens + platform $0.003 per `text_message`). That's roughly $0.008/message, so 50 messages/day ≈ $0.40. Count chat toward any monthly budget cap and keep the injected prompt small.

## Open-topic / adult content

- When the user wants the learner free to ask for anything (slang, swearing, sexual vocabulary): put it in the prompt explicitly as "she picks the topic; teach it straight, rate how crude it is, no moralizing", keep a single hard line on minors (also an ElevenLabs Use Policy prohibition), and add a `crude` register to the tool enum.
- Then **test it live** with deliberately crude requests through the text spike. Haiku 4.5 complied fully. Default guardrails were all off, so nothing at the platform level blocked it.

## Grok voice (xAI) as an alternative, compared 2026-10-01

- `grok-voice-think-fast-2.0` speech-to-speech is $0.08/min (docs.x.ai/developers/pricing.md), the same as ElevenLabs.
- It uses **one voice per session**, with no mid-reply voice switching. For a language tutor that means the English coach voice would also say the target-language phrases, so ElevenLabs multi-voice wins.
- Custom voice cloning is free in the console (US only, not Illinois); the API endpoint is Enterprise-only.
- Raw WebSocket only (`wss://api.x.ai/v1/realtime`); ephemeral tokens are available for browsers.
- Docs index: `https://docs.x.ai/llms.txt`; pages as `.md`.

## Voice-clone accent trap

A voice keeps the accent of its training audio (help article 19631995406481). An English speaker's clone will speak German with an English accent. For a tutor, use the clone for English coaching and native Voice Library voices for the target-language phrases via multi-voice tags. Say this up front whenever the user asks for "my voice".
