---
name: awesome-llm-apps-catalog
description: "Use when the user wants runnable LLM agent/RAG app code."
version: 1.0.0
author: Hermes Agent (catalog of Shubhamsaboo/awesome-llm-apps)
license: Apache-2.0
metadata:
  hermes:
    tags: [agents, rag, mcp, voice, streamlit, agno, google-adk, openai-agents, templates, examples]
    related_skills: [subagent-driven-development, native-mcp, template-based-ai-tool-development, claude-code]
---

# awesome-llm-apps catalog

An index of the ~170 runnable apps in github.com/Shubhamsaboo/awesome-llm-apps (Apache-2.0): agent teams,
single agents, RAG pipelines, MCP agents, voice agents, generative-UI apps, always-on agents, and the Google ADK
/ OpenAI Agents SDK crash courses. These are code projects (mostly Python + Streamlit, often Agno, Google ADK or
the OpenAI Agents SDK), not persona prompts, so they live here as a catalog rather than as skills or subagents.

## When to Use
- "Is there an example/template for a <X> agent / RAG app / MCP agent / voice agent?"
- Starting a new AI tool and wanting a working reference implementation to adapt.
- Learning a framework (ADK, OpenAI Agents SDK, Agno, LangGraph, CrewAI) from a small runnable example.

Not for advice or role-play: for "act as a finance/real-estate/game-design expert" use the agency-agents router
plugin (the catalog's "Overlaps" column names the matching specialist).

## Procedure
1. Search `references/catalog.md` (grep the topic, framework or model name) and shortlist 1–3 apps.
2. Fetch just that folder: `git clone --depth 1 --filter=blob:none --sparse https://github.com/Shubhamsaboo/awesome-llm-apps /tmp/ala && git -C /tmp/ala sparse-checkout set <path>`.
3. Read its README and requirements before running; install into a venv (PEP 668 here), never system pip.
4. Port model calls to the user's stack when adapting (Replicate for generation, Workers AI / Clef for
   decisions), and keep the upstream Apache-2.0 notice in any copied code.
5. This box has ~2 GB RAM and no GPU: skip apps that run local models (ollama, local Llama/DeepSeek) or point
   them at a hosted API.

## Pitfalls
- The catalog is a snapshot (commit 4bf51ab, 2026-09-28); the repo moves fast. Re-run
  `~/agency-agents-tools/build_catalog.py` against a fresh clone to refresh it.
- Model IDs in the apps go stale quickly; check current IDs before running.
- Many apps need several paid API keys (OpenAI, Gemini, Firecrawl, Exa, ElevenLabs). Say which before running.

## References
- `references/catalog.md`: every app with path, one-line description, detected stack and overlapping
  agency-agents specialist.
