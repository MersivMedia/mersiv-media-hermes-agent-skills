# ElevenLabs Agents API notes (verified Oct 2026)

Base: `https://api.elevenlabs.io`, header `xi-api-key`. Full doc index: `https://elevenlabs.io/docs/llms.txt`; any doc page has a `.md` twin (append `.md` to the URL) which is far easier to grep than the HTML.

## Endpoints used

| Purpose | Call |
|---|---|
| Create agent | `POST /v1/convai/agents/create` |
| Update agent | `PATCH /v1/convai/agents/{agent_id}` |
| Create/update tool | `POST /v1/convai/tools` / `PATCH /v1/convai/tools/{id}`; list `GET /v1/convai/tools` |
| Text chat auth | `GET /v1/convai/conversation/get-signed-url?agent_id=…` → `{signed_url}` (WebSocket) |
| Voice auth | `GET /v1/convai/conversation/token?agent_id=…` → `{token}` (WebRTC) |
| Conversation detail | `GET /v1/convai/conversations/{id}` |
| List | `GET /v1/convai/conversations?agent_id=…&page_size=…` (`user_id` filter exists but the summary rows did not echo `user_id`) |
| Add library voice | `POST /v1/voices/add/{public_user_id}/{voice_id}` body `{new_name}` |
| TTS | `POST /v1/text-to-speech/{voice_id}?output_format=mp3_44100_64` body `{text, model_id, language_code, voice_settings:{stability, similarity_boost, speed}}` |

## Agent config essentials

- `conversation_config.agent.prompt`: `{prompt, llm, tool_ids:[…]}`; `{{var}}` placeholders become dynamic variables. Provide `dynamic_variable_placeholders` defaults or creation can fail on unknown vars.
- `conversation_config.tts`: `{voice_id, model_id: "eleven_flash_v2", supported_voices:[{label, voice_id, description, model_family:"flash"}]}`. Label = the XML tag name the LLM uses (`<German>…</German>`). Max 10 voices including default.
- `platform_settings.overrides.conversation_config_override`: each field the client may override must be enabled here, e.g. `conversation: {text_only: true, max_duration_seconds: true}`, `agent: {first_message: true, language: true}`. Unenabled overrides are rejected at session start.
- `platform_settings.auth.enable_auth: true` → clients need a signed URL / token from your server.
- Client tools: `type: "client"`, `expects_response: true` lets the tool result feed back into the LLM. Param schema uses ElevenLabs JSON-schema variant (`type`, `description`, `enum` per property; object `required` list).
- Guardrails live under `platform_settings.guardrails`. Check they are off when the content policy is open.

## Raw WebSocket protocol (Node 22 has a global WebSocket)

1. Open `signed_url`. First send:
   `{type:"conversation_initiation_client_data", conversation_config_override:{conversation:{text_only:true}}, dynamic_variables:{…}, user_id:"…"}`
2. Receive `conversation_initiation_metadata` (has `conversation_id`).
3. Send `{type:"user_message", text}`.
4. Receive `agent_response` (full text), `agent_chat_response_part` (stream), `client_tool_call` `{tool_name, tool_call_id, parameters}`. Reply with `{type:"client_tool_result", tool_call_id, result, is_error:false}`.
5. Answer `ping` with `{type:"pong", event_id}` or the socket dies.
6. Idle text sessions do not send re-engagement messages; they just sit until closed (close code 1005 on client close).

## Conversation payload fields

- `status`: initiated / in-progress / processing / done / failed. Cost is final only at `done`.
- `metadata.cost_fiat` (USD), `metadata.call_duration_secs`, `metadata.start_time_unix_secs`, `metadata.text_only`, `metadata.charging.llm_usage` (per-model token prices).
- `transcript[]`: `{role, message, time_in_call_secs, tool_calls:[{request_id, tool_name, params_as_json}]}`. Use for back-filling tool calls the browser missed. `multivoice_message` may be null in text mode; the voice tags stay in `message`.
- `user_id` and `conversation_initiation_client_data.dynamic_variables` are echoed back.

## SDK

- `@elevenlabs/client` `Conversation.startSession({signedUrl | conversationToken, connectionType:"webrtc", textOnly, dynamicVariables, overrides, userId, clientTools:{name: async(params)=>string}, onMessage, onAgentChatResponsePart, onStatusChange, onModeChange, onConversationMetadata})`. `textOnly:true` returns a `TextConversation`.
- `@elevenlabs/react` 1.x only re-exports the client; using the client directly avoids pulling livekit twice.
- SDK `overrides` (client 1.26) maps only `agent.{prompt,firstMessage,language}`, `tts.{voiceId,…}`, `conversation.textOnly`, plus `userId`. **No `maxDurationSeconds` override in the SDK.** Enforce per-session limits with a client countdown that calls `endSession()`, and keep the agent-level `max_duration_seconds` as the hard backstop.
- Voice mode with no first message: if the agent's `first_message` is empty and the user stays silent, the conversation completes with **0 transcript turns** (billed, but nothing logged). Send a per-session `overrides.agent.firstMessage` (greeting adapted to progress, voice tags allowed) and enable `agent.first_message` in the agent's override settings.
- Model ids verified working on an English multi-voice agent: `eleven_flash_v2` (voices `model_family:"flash"`) and `eleven_v4_turbo` (voices `model_family:"v4_turbo"`). `eleven_flash_v2_5` is rejected ("English Agents must use turbo or flash v2").
- Round-trip check for audio output: drive a voice conversation over the WebSocket with a typed `user_message`, collect `audio` events (pcm_16000 by default), wrap as WAV, then `POST /v1/speech-to-text` (`model_id=scribe_v2`) to confirm the target-language words were actually spoken.
