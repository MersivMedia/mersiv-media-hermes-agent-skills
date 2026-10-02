# Clef / Clef-flash: verified facts (launched 2026-10-01)

Sources:
- https://developers.cloudflare.com/changelog/post/2026-10-01-clef-workers-ai/
- https://huggingface.co/Cloudflare/clef
- https://huggingface.co/Cloudflare/clef-flash
- https://blog.cloudflare.com/clef-decision-models
- Workers AI model pages: /workers-ai/models/clef/index.md, plus schema-input.json and schema-output.json

Local copies of all of these: `~/.hermes/data/clef-research/`

## Models
| | Clef | Clef-flash |
|---|---|---|
| Backbone | Qwen/Qwen3.8-27B | Qwen/Qwen3.5-9B |
| Workers AI id | `@cf/cloudflare/clef` | `@cf/cloudflare/clef-flash` |
| Price | $0.24 / M input tokens | $0.09 / M input tokens |
| Median / p95 latency (blog) | 209 / 239 ms | 39 / 122 ms |

Jev measured 524 / 536 ms in the same table.

Both models:
- 65,536-token context, with vision (images and video).
- Apache-2.0 license, so tuned versions can be resold commercially.
- transformers class `Qwen3_5ForConditionalGeneration` (model_type qwen3_5). Layers are a hybrid of linear_attention and full_attention.
- Tested by Cloudflare with torch 2.11 and transformers 5.10.2 on 1×H200.

## What the HF repo actually contains
- The merged backbone safetensors.
- `joint_head.safetensors` and `joint_head_config.json`. The 27B config is `{hidden_size 5120, width 1024, routing_layers 2, layers 4, heads 16, feedforward 4096}`, roughly 125M head params (my estimate).
- `joint_schema_model.py`, which defines `encode_record`, `collate_records`, `EvidenceRoutingLayer`, `JointSchemaHead`, `ClefModel`, `load_release_model(path)` and `systemone(model, processor, request)`.
- **Inference only.** No training loop, loss, or optimizer code is released.
- The prompt is a chat template: system prompt, `STATE:` and the schema fields, then `<think>\n\n</think>\n\nJOINT SCHEMA DECISIONS:`. The head reads the question and option token spans.

## Training recipe (blog)
- Backbone frozen.
- Routing head trained jointly with a rank-256 LoRA.
- Loss: label-smoothed CE plus a Brier term.
- Data: synthetic, permuting field order, prompts and schema structure.
- RLCD reinforcement stage (unreleased), with three parts:
  - partial credit for adjacent ordinal choices
  - an exact-record reward
  - a reference penalty
- Cloudflare offers its own RL fine-tuning through a "design partner" program, with self-serve and redeploy-on-Workers-AI planned.

## Workers AI API details (from schema-input/output.json)
- `images`: max 4 items, each a `data:image/...;base64,` URL or `{content_type, base64}`. Limits are 4 MiB and 16 MP each, 8 MiB decoded in total, 13 MiB per request body. No remote URLs.
- There is no `videos` field in the public API. Cloudflare's in-process code accepts video frames.
- `score` criteria: 2 to 10 levels, indexed from 0.
- Responses are wrapped as `{result, success, errors[{code,message}], messages}`.
- Rate limits for Clef are not published (as of 2026-10-02).

## HF revisions pinned by clef-rag (checked 2026-10-02)
- Cloudflare/clef: `2f3de3dd85f379784083b0814d997ab627200f0c`
- Cloudflare/clef-flash: `17f0b0ad64efb65d273590632833508766b2aae6`

## User's repos (Mersiv Media)
- `jev-rag-retrieval`: the source app.
- `clef-rag`: the port, live at github.com/MersivMedia/clef-rag. Details are in `clef-rag-port.md`.
- `clef-finetune`: a separate LoRA toolkit with insurance-claims and compliance starter kits, at ~/clef-finetune, github MersivMedia/clef-finetune. It has been verified on CPU with a tiny model only. `scripts/verify_cpu.sh` runs pytest plus the CLI chain make-tiny → validate → augment → train → resume → eval → merge → reload.
