// Text-mode spike for an ElevenLabs agent, run from Node 22+ (global WebSocket, no SDK needed).
// Proves: signed-URL auth, text_only override, dynamic variables, voice-tag markup, client tool calls, real cost.
// Usage: ELEVENLABS_API_KEY=... AGENT_ID=agent_... TURNS='["hi","..."]' VARS='{"k":"v"}' node elevenlabs-text-spike.mjs
// Run it through a wrapper that loads .env, so the key never lands in argv or output.
const KEY = process.env.ELEVENLABS_API_KEY;
const agentId = process.env.AGENT_ID;
const userTurns = JSON.parse(process.env.TURNS || '["Hi! Where do we start?"]');
const dynamicVariables = JSON.parse(process.env.VARS || "{}");
const TAG = process.env.VOICE_TAG || ""; // e.g. "German": counts replies containing <German>…</German>

const r = await fetch(`https://api.elevenlabs.io/v1/convai/conversation/get-signed-url?agent_id=${agentId}`, {
  headers: { "xi-api-key": KEY },
});
if (!r.ok) throw new Error("signed url " + r.status + " " + (await r.text()));
const { signed_url } = await r.json();

const ws = new WebSocket(signed_url);
const send = (o) => ws.send(JSON.stringify(o));
let turn = 0, convId = "", agentTurns = 0, tagged = 0, tools = 0, idle = null;

ws.onopen = () =>
  send({
    type: "conversation_initiation_client_data",
    // Requires platform_settings.overrides.conversation_config_override.conversation.text_only = true on the agent
    conversation_config_override: { conversation: { text_only: true } },
    dynamic_variables: dynamicVariables,
  });

function next() {
  if (turn >= userTurns.length) return setTimeout(() => ws.close(), 500);
  const t = userTurns[turn++];
  console.log("\nUSER:", t);
  send({ type: "user_message", text: t });
}

ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.type === "conversation_initiation_metadata") {
    convId = m.conversation_initiation_metadata_event?.conversation_id;
    console.log("conversation:", convId);
    setTimeout(next, 300);
  } else if (m.type === "ping") {
    send({ type: "pong", event_id: m.ping_event.event_id });
  } else if (m.type === "agent_response") {
    const text = m.agent_response_event.agent_response;
    console.log("AGENT:", text);
    agentTurns++;
    if (TAG && new RegExp(`<${TAG}>[^<]+</${TAG}>`).test(text)) tagged++;
    clearTimeout(idle);
    idle = setTimeout(next, 2500); // agent may send several responses per turn; advance after quiet
  } else if (m.type === "client_tool_call") {
    tools++;
    console.log("TOOL:", m.client_tool_call.tool_name, JSON.stringify(m.client_tool_call.parameters));
  }
};

ws.onclose = async () => {
  console.log(`\nagent turns: ${agentTurns}, tagged: ${tagged}, tool calls: ${tools}`);
  await new Promise((res) => setTimeout(res, 8000)); // let the conversation record settle
  const d = await (await fetch(`https://api.elevenlabs.io/v1/convai/conversations/${convId}`, {
    headers: { "xi-api-key": KEY },
  })).json();
  console.log("status:", d.status, "secs:", d.metadata?.call_duration_secs, "text_only:", d.metadata?.text_only,
    "cost_fiat USD:", d.metadata?.cost_fiat, "llm:", d.metadata?.charging?.llm_price, "platform:", d.metadata?.charging?.platform_price);
};
