# AI Architecture Pattern Menu

Pick the simplest pattern that solves the problem. Escalation costs compound: every step
down this list adds infrastructure, evaluation burden, and failure modes.

## 1. Deterministic automation (no AI)
**Use when** the rules are stable and enumerable. RPA, scripts, workflow tools.
**Why it matters** — proposing this when it's right is the fastest way to earn technical
credibility. Roughly a third of "AI opportunities" in discovery are actually this.
**Cost profile** — lowest. **Risk** — lowest.

## 2. Single-shot LLM call with structured output
**Use when** classification, extraction, summarization, or reformatting of self-contained
input. Constrained decoding or JSON schema enforcement.
**Watch for** — hallucinated fields on ambiguous input; require a confidence field and
route low-confidence to a human.
**Eval** — labeled test set, field-level accuracy, per-field precision/recall.

## 3. Retrieval-augmented generation (RAG)
**Use when** answers must come from a corpus the model wasn't trained on: policies,
contracts, product docs, ticket history.
**Components** — chunking strategy, embedding model, vector store, retriever, reranker,
generation with citation enforcement.
**Failure modes** — retrieval miss (most common; measure recall@k separately from answer
quality), stale index, chunk boundaries splitting a fact in half.
**Eval** — retrieval recall@k, faithfulness/groundedness, answer relevance, refusal rate.

## 4. Tool-using agent (single agent, bounded tools)
**Use when** the task needs live system state or writes: lookups, ticket creation, CRM
updates, calendar operations.
**Guardrails** — allowlist tools, dry-run mode, approval gate on any write, hard iteration
cap, full audit log of every call.
**Failure modes** — loops, wrong-tool selection, silent partial completion.
**Eval** — task success rate on a fixed scenario suite, tool-selection accuracy, cost/task.

## 5. Multi-agent / orchestrated pipeline
**Use when** genuinely separable subtasks with different tools or context needs.
**Warning** — usually premature. A well-prompted single agent with good tools beats a
multi-agent system at a fraction of the cost and debuggability. Require a specific reason.

## 6. Fine-tuning / adapters
**Use when** you need a consistent format, domain tone, or latency/cost reduction at high
volume — and you already have RAG working and 1k+ quality examples.
**Not for** — teaching facts. That's RAG. This is the single most common client
misconception; address it explicitly in the client PRD.

## 7. Classical ML
**Use when** tabular prediction: churn, demand forecast, pricing, lead scoring, anomaly
detection. Gradient boosting still beats LLMs here on accuracy, cost, and latency.
**Signal** — if the notes mention "predict", "forecast", or "score", this is likely it.

## 8. Speech / vision / document AI
**Use when** the input is audio, images, or scanned PDFs. Transcription, OCR, layout
extraction, visual inspection. Often a preprocessing step feeding patterns 2-4.

## Cross-cutting requirements

Every pattern needs, spelled out in the technical PRD:

- **Human-in-the-loop checkpoint** — what a person reviews, and when that gate relaxes
- **Evaluation harness before build** — the metric and the test set come first
- **Observability** — trace every call, log inputs/outputs, track cost per transaction
- **Fallback path** — what happens when the model is down or unsure
- **Data governance** — PII handling, retention, whether client data touches a vendor,
  training-data opt-out
- **Cost model** — cost per transaction × volume, with a headroom multiplier of 3×
