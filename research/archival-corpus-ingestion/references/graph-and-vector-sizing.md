# Sizing the graph, vector store, and 3D view

What breaks when a corpus-backed knowledge graph meets real numbers. Worked
against 12.2M pages / 934k documents; the ratios transfer.

## 1. Co-occurrence cannot be materialised

"Which entities appear together across reports" is the headline feature of
almost every archive knowledge graph. Implemented naively — link every entity
pair on every page — it explodes:

```
 5 entities/page  ->  10 pairs/page  ->  0.12 billion edges
 8 entities/page  ->  28 pairs/page  ->  0.34 billion edges
15 entities/page  -> 105 pairs/page  ->  1.28 billion edges
```

A billion-edge graph is not queryable at interactive latency, and most of those
edges are noise: two names on the same routing slip are not connected in any
sense a researcher cares about.

**Store mentions; derive overlap at query time.**

```
store:   (Document)-[:MENTIONS]->(Entity)        ~60M edges, linear in corpus
derive:  MATCH (e1 {name:$q})<-[:MENTIONS]-(d)-[:MENTIONS]->(e2)
         RETURN e2, count(d) AS shared ORDER BY shared DESC LIMIT 200
```

Query cost is bounded by the degree of **one** entity, not by the graph. The
same two-hop pattern answers "documents connecting A and B" and "timeline of
program P" without precomputing anything.

Materialise a co-occurrence edge only when it survives a threshold worth
storing (e.g. shared across ≥N documents), and treat it as a cache.

## 2. Vector store: quantise or pay for RAM

```
18.3M vectors @ 1536d float32  ->  168 GB   (incl. ~1.5x HNSW overhead)
18.3M vectors @  768d float32  ->   84 GB
18.3M vectors @  768d int8     ->   21 GB   <- fits a commodity VPS
```

int8 quantisation with rescoring costs a few points of recall and moves the
deployment from "needs a large dedicated box" to "$60/mo VPS". Do it by default
at this scale; measure recall on a held-out query set before assuming the loss
matters.

Chunking drives everything upstream of that: 1 vector/page, ~500-token chunks
(≈1.5/page), and ~250-token chunks (≈3/page) differ by 3x in every downstream
number. Decide chunking before sizing anything.

## 3. Embeddings: self-host on the GPU you already rented

```
bge-small-en-v1.5   384d    ~17 GPU-h   ~$34
bge-base-en-v1.5    768d    ~34 GPU-h   ~$67
e5-large-v2        1024d    ~81 GPU-h  ~$161
```

Versus ~$292 via API for the same corpus. Cheaper, and it avoids a second
content filter on sensitive text (see `content-filtering-archives.md`).

## 4. The 3D view has a hard ceiling

```
  1,000 nodes   smooth
 10,000 nodes   fine with instancing
100,000 nodes   GPU copes — but a human reads fog, not structure
  1M+   nodes   browser dies
```

Force-directed layout is O(n log n) **per frame** with Barnes-Hut. The limit is
not the GPU, it is legibility: past a few thousand nodes nobody can see
anything.

**Never render the whole graph.** Render query-scoped subgraphs with a hard cap
around 2,000 nodes — which is also roughly where human comprehension tops out.
The graph database holds millions; the view shows a neighbourhood.

Pattern: search → top-k documents → entities in those documents → their
immediate neighbours → cap → layout. Expansion happens on click, not upfront.

## 5. Hybrid search: neither store answers alone

```
query -> embed -> vector top-k chunks -> doc_ids
                                           |
                     graph: entities in those docs, their other docs
                                           |
                merge -> cited results + a capped subgraph for the 3D view
```

The vector index finds *passages about* something. The graph finds *what
connects to* something. Requirements of the form "overlaps", "timeline", "who
else appears" are graph traversals and no embedding tuning will answer them.

## 6. Monthly, self-hosted

```
Qdrant (21 GB int8)                  $60
Neo4j community (~60M edges)         $40
object store for source PDFs 3.65TB  $84
CDN egress                           $30
                                    -----
                                    $214/mo
```

Managed vector hosting alone for the same vector count runs ~$300-700/mo.

## 7. The unsolved part: entity resolution

Flagged rather than solved. `Allen Dulles` / `DULLES` / `the Director` /
`DUL1E5` (OCR damage) must collapse to one node, or the graph fragments into
thousands of near-duplicates and every overlap query returns nothing.

This is a real subsystem — blocking, candidate generation, a similarity model,
and a human adjudication path for the hard cases — not a normalisation step.
Budget for it separately, and note that OCR noise makes it materially harder
here than in clean-text domains.

## Sizing inputs to measure before trusting any of the above

- **entities per page** — assumed 3/5/8 above; changes graph size 3x. The
  extraction benchmark reports it directly. Get the real number first.
- **mention-to-unique-entity ratio** — assumed ~30:1. Drives node count.
- **chunks per page** — drives vector count, storage, and embedding cost.
