# Vector DB adapter pitfalls (checked 2026-09-30)

Versions on PyPI at check time: pinecone 10.0.0 (`pinecone-client` 6.0.0 DEPRECATED),
qdrant-client 1.19.1, chromadb 1.5.9, pymongo 4.18.2, weaviate-client 4.23.1,
pymilvus 3.0.2, pgvector 0.5.0, lancedb 0.39.0, elasticsearch 9.5.1, opensearch-py 3.2.0,
redisvl 0.27.2, turbopuffer 2.10.2, azure-search-documents 12.0.0, langchain-core 1.6.6,
llama-index-core 0.14.25. Re-check with `curl -s https://pypi.org/pypi/<pkg>/json`.

| Store | Gotcha |
|---|---|
| Qdrant | `QdrantClient.search()` is gone in 1.19.1; use `query_points`. Point IDs must be unsigned ints or UUIDs. Filtering fields need payload indexes. Don't bootstrap a collection dimension from an empty batch |
| Chroma | Returns **distances** (lower = better). Collection space defaults to the embedding function's `default_space()`, and the base default is `l2` (`api/collection_configuration.py`). Set `hnsw.space` explicitly and convert to similarity |
| Pinecone | Install `pinecone`, not `pinecone-client`. Per-record metadata limit (40 KB per community answers; confirm on docs.pinecone.io/reference/api/database-limits). Namespaces isolate collections within one index |
| MongoDB Atlas | `insert_many` is not an upsert (duplicate `_id` errors on rerun): use `bulk_write` with `ReplaceOne(upsert=True)`. `$vectorSearch` `filter` only works on fields declared as `type: filter` in the vector index definition |
| pgvector | Verified against `pgvector/pgvector:pg17` (Postgres 17.11, extension 0.8.6). `register_vector` makes `embedding` come back as a pgvector `Vector`: call `.to_list()` before `float()`. Passing numpy arrays needs numpy, so declare it in the `[pgvector]` extra (CI's pgvector-only job failed without it). Compile the portable filter to SQL over `metadata jsonb` with bound parameters, never string-formatting values |
| LangChain bridge | `InMemoryVectorStore` has no `add_embeddings`; `add_documents` re-embeds the bare text with the store's own embedder, so stored vectors silently differ from the pipeline's (heading-prefixed) `embed_text`. Wrap the pipeline's vectors in an `Embeddings` shim (or use the store's add-with-vectors method) and test that stored vector == pipeline vector |
| Qdrant embedded | `QdrantClient(path=...)` works for tests and demos with no server; it prints a harmless `sys.meta_path` ImportError at interpreter shutdown |
| All | Normalise scores to similarity in [0,1] so thresholds are portable; keep the raw score. Need delete, get-by-id, ensure_collection and a capability flags method, not only upsert and query |

Adapter conformance suite to require: round trip, idempotent upsert, stale delete by doc_id,
every filter operator, score normalisation, empty-batch handling. Run local stores in docker-compose and
hosted-only stores (Pinecone, Atlas) nightly behind secrets.
