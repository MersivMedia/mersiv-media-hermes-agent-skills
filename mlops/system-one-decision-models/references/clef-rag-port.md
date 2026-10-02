# clef-rag port: what was done and how it was verified

Repo: github.com/MersivMedia/clef-rag (~/clef-rag), public, MIT, v0.1.0. Upstream: MersivMedia/jev-rag-retrieval @ 92c18be.
Sibling: github.com/MersivMedia/clef-finetune (~/clef-finetune), Apache-2.0.

## Files that changed beyond the mechanical rename
- `clef_rag/clef/client.py`: rewritten.
  - BACKENDS = workers-ai / self-hosted / local, plus MODELS and WORKERS_AI_PRICE.
  - `ClefConfig.resolve()` returns `{backend, model, url, api_key, ready, missing, request_budget, price_per_million, cache_model}`.
  - `ClefConfig.price()`.
  - `_unwrap()` handles the Workers AI envelope.
  - Errors parse both the Cloudflare `errors[]` shape and `{error:{type,message}}`.
- `clef_rag/clef/local.py`:
  - `LocalClef` imports `joint_schema_model.py` from the release dir.
  - `PINNED_REVISIONS` holds the HF commit shas.
  - `decode_images`, `RequestError` (maps to HTTP 422).
  - `_LocalTransport` is an httpx transport that lazy-loads the engine via `asyncio.to_thread`.
- `clef_rag/clef/serve.py`: `make_handler(engine, name, api_key)` and `serve()`. CLI: `clef-rag serve [model] --host --port --device --dtype --max-length --name --revision --api-key-env`.
- `pipeline.py`, `eval/runner.py`, `scripts/backfill_rank_gate.py`: `clef_config.price_per_million` became `clef_config.price()`.
- `.env.example` + `templates/env.example`:
  - Clef section: CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID, CLEF_BASE_URL, CLEF_API_KEY.
  - Kept AI_GATEWAY_API_KEY under embeddings and OPENROUTER_API_KEY under the rerank baseline.
- `pyproject.toml`: added the `serve` extra (`torch>=2.6`, `transformers>=5.10.2`, `huggingface_hub`, `safetensors`, `pillow`, `torchvision`, `accelerate`).
- Tests:
  - conftest's fake replies inside the Workers AI envelope and records URLs.
  - New tests: auto order, model validation, envelope + error envelope, self-hosted optional key, the 64-question cap, cache per model.
  - `tests/test_local_backend.py` covers local + serve + auth. It is skipped unless torch and `CLEF_RAG_TEST_TINY_RELEASE` are present.
- CI: a new `local-backend` job installs CPU torch, `.[serve,dev]` and clef-finetune from git, runs `clef-finetune make-tiny /tmp/clef-tiny`, then the local tests with `CLEF_FINETUNE_JSM=vendored`.

## Verification recipe (no GPU, no keys)
1. Hermetic suite: `uv venv .venv && uv pip install -e ".[qdrant,chroma,langchain,pdf,dev]"`, then `pytest -o addopts="" -q -W ignore`. Result: 187 passed, 2 skipped.
2. Torch venv: `.venv-serve` (gitignored) with `.[serve,dev]`. Then `CLEF_RAG_TEST_TINY_RELEASE=<tiny> pytest tests/test_local_backend.py`. Result: 6 passed.
3. Real process:
   - Start `clef-rag serve <tiny> --device cpu --dtype float32 --max-length 4096 --port N`.
   - `curl /health`, then POST `/v1/systemone`.
   - `CLEF_BASE_URL=... clef-rag init --embedder hash:64`, then `check` / `ingest` / `query` all go through end to end.
4. `uvx ruff check clef_rag tests --select F,E9`.
5. Push, then `gh run list` until all jobs are green (unit 3.10/3.12/3.13, local-backend, pgvector).

## Open items handed to the user
- First live Workers AI call: needs CLOUDFLARE_API_TOKEN + ACCOUNT_ID, and costs a fraction of a cent (`CLEF_RAG_LIVE=1 pytest tests/test_live.py`).
- Rerun the upstream benchmarks with clef / clef-flash and retune thresholds. Estimate the cost first.
- Packed multi-passage classification (64 questions per forward pass) to cut the ~32 requests per query.
