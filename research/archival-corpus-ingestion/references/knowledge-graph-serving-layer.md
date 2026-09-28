# Serving an archive: graph model, vectors, and query-scoped 3D

What to do with page records *after* ingestion, when the product is a
searchable/explorable knowledge graph over millions of documents.

Every number here comes from sizing a real 12.2M-page / 934k-document corpus.
The arithmetic is what forces the design — each decision below exists because
the naive version does not fit in a browser, a database, or a budget.

---

## 1. A node is an entity, not a page

The instinct is to model every page-level mention. Don't. Aggregate mentions to
the **(entity, document)** pair and carry the detail on the edge:

```
(Entity {name, type, canonical_id})
   -[:MENTIONS {count: 6, pages: [3,4,7,11,12,19], first_page: 3}]->
(Document {doc_id, title, date, page_count, content_type})
```

If a name appears on six pages of one document, that is **one node and one
edge**, not six of each.

| Model | Edges (12.2M pages, ~5 entities/page) |
|---|---|
| One edge per mention | ~60.9M |
| **Aggregated to (entity, document)** | **~11.7M** |

A ~5.2× reduction, and nothing is lost: `pages[]` still drives citation, so a
result reads *"mentioned 6 times, pages 3–19"* and deep-links each page.

Derivation of the collapse factor: mean pages/document × the fraction of a
document's pages a given entity appears on (~0.4 in practice). Measure both on
your own corpus rather than reusing these.

---

## 2. Co-occurrence is computed, never stored

"Which reports overlap" looks like it wants an edge between every pair of
entities appearing together. Materialising that is fatal:

| Entities/page | Co-occurrence edges |
|---|---|
| 5 | 0.12 billion |
| 8 | 0.34 billion |
| 15 | 1.28 billion |

`n*(n-1)/2` per page, times millions of pages. A billion-edge graph is not
queryable at interactive latency, and most of those edges are noise — two names
on the same routing slip are not meaningfully connected.

Store `MENTIONS` only (~12M edges) and derive overlap as a two-hop traversal
from the **selected** entity:

```cypher
MATCH (e1 {canonical_id: $id})<-[:MENTIONS]-(d)-[:MENTIONS]->(e2)
WHERE e2.canonical_id <> $id
RETURN e2, count(d) AS shared_docs, collect(d.doc_id)[..20] AS examples
ORDER BY shared_docs DESC LIMIT 300
```

Cost is bounded by the degree of one entity, not by the size of the graph.

**General principle:** when a requirement sounds like "show relationships
between everything," check the combinatorics before modelling it as stored
edges. Derived-at-query-time is usually both cheaper and more accurate, because
you can rank and threshold at query time with context the ingest pass lacked.

---

## 3. Entity resolution is a subsystem, not a detail

`Allen Dulles` / `DULLES` / `A. W. Dulles` / `the Director` / `DUL1E5` (OCR
damage) must collapse to one `canonical_id`, or the graph fragments into
thousands of near-duplicates and **every overlap query returns nothing useful**.

Cascade, cheapest first:

```
1. normalise      case, punctuation, honorifics, "LAST, FIRST" -> "FIRST LAST"
2. exact match    on the normalised form
3. fuzzy          Levenshtein <=2 AND same entity type AND overlapping date
                  range  (the date guard stops different people with similar
                  names merging)
4. embedding      cosine similarity on name + surrounding context
5. human review   queue HIGH-DEGREE entities only
```

Two rules that matter more than the algorithm:

- **Triage by degree.** Getting a hub entity wrong corrupts thousands of edges;
  getting an obscure clerk wrong affects three. Human review time goes to the
  hubs, exclusively.
- **Merges must be reversible.** Store the merge *decision*, not just the merged
  result, so a bad merge is undone without re-running extraction.

Coreference ("the Director" → whoever held the post at that document's date)
resolves at **extraction time**, where the model has page context — not later
in a batch job that has thrown the context away.

---

## 4. Vector store: quantisation is not optional

```
18.3M vectors (1.5 chunks/page over 12.2M pages)

  1536d float32   168 GB    needs a large, expensive machine
   768d float32    84 GB    still heavy
   768d int8       21 GB    fits in RAM on a ~$60/mo VPS
```

int8 with rescoring costs a few points of recall and changes the hosting bill
by an order of magnitude. At corpus scale this is the difference between a
viable product and one that cannot be afforded.

Embeddings run on the GPU already rented for transcription — tens of dollars
for a whole corpus, cheaper than API embedding endpoints and avoiding a second
content-filter exposure.

---

## 5. Hybrid retrieval — neither store alone works

```
query ──► embed ──► vector DB: top-k chunks ──► doc_ids
                                                  │
                     graph DB: entities in those docs, their other documents
                                                  │
                     merge ──► cited results + a subgraph for visualisation
```

Semantic search finds documents that use different words; the graph finds what
connects them. Citations come from the chunk payload (`doc_id` + `page`).

---

## 6. The 3D view must be query-scoped

**Nothing renders until the user searches.** There is no "whole graph" view.

```
      1,000 nodes   smooth
     10,000 nodes   fine with instancing
    100,000 nodes   GPU copes, but the user is reading fog
  3,200,000 nodes   impossible
```

Force-directed layout is O(n log n) *per frame* even with Barnes-Hut. But the
binding limit is **human legibility**, not the GPU — at 100k nodes there is no
structure a person can perceive.

Hard cap ~2,000 nodes, allocated per query:

```
    1   the focus entity
  300   top co-occurring entities
  600   top documents
  400   second-degree entities (dimmed, context only)
  699   headroom for click-to-expand
```

Rank documents into their slots by mention count, entity density (documents
rich in *other* entities make better graph hubs), date, page count, and
IDF-style distinctiveness.

### Hub entities need facets, not nodes

Degree distribution in any real archive is brutally long-tailed:

```
an obscure case officer        ~12 documents
a mid-level program           ~400 documents
a major country           ~180,000 documents
the issuing agency itself ~600,000 documents
```

A query on a hub cannot render 180,000 document nodes. Return the entity plus a
**facet panel** — top co-occurring entities, timeline histogram by year, type
filters — and let the user drill (*entity + year + type*) until the result is
small enough to be a graph.

**An over-broad query is a UI state, not an error.** Design narrowing to feel
like exploration rather than failure. This is the single most important
interaction decision in a graph UI over a large corpus.

### Interaction model

```
search an entity
  → focus node, sized by total mentions
  → co-occurring entities orbit, distance/thickness by shared-document count
  → click an entity     : expand its subgraph, respecting the cap
  → click a document    : side panel — title, date, type, page thumbnails
  → click a page        : open the scan at that page  ← the citation payoff
  → timeline scrub      : filter edges by document date, graph re-settles
  → type filter         : PERSON / PLACE / ORG / PROGRAM / EVENT
```

Colour encodes entity type; node size encodes mention count; edge thickness
encodes shared documents. Every visible element must trace to a citable page.

---

## 7. Hosting at this scale

| Component | Size | Typical |
|---|---|---|
| Vector DB self-hosted, 768d int8 | 21 GB | $60/mo |
| Graph DB (community edition), ~12M edges | ~40 GB | $40/mo |
| Object store for original scans | 3.65 TB | $84/mo |
| CDN egress | — | ~$30/mo |
| **Total** | | **~$214/mo** |

A managed vector service alone for 18M vectors runs $300–700/mo. Self-hosting
the vector and graph layers is the difference between a sustainable public
archive and one that dies when the grant ends.

---

## 8. Sizing assumptions to measure, not inherit

Every number above descends from a small number of assumed rates. State them as
assumptions in any deliverable, and measure them before building:

- **Entities per page** (3 / 5 / 8 assumed). Swings graph size ~3×, and changes
  whether co-occurrence is merely large or catastrophic. A transcription
  benchmark reports this directly — run it first.
- **Mention → unique-entity ratio** (~30:1 assumed). Depends entirely on
  resolution quality.
- **Pages-per-document distribution.** Use the real median and tail, not the
  mean.
- **Hub degree distribution.** Determines whether the facet path is an edge case
  or the common path.
- **Resolution quality on OCR-damaged names.** Unknown until tried on real
  degraded text; it is the difference between a connected graph and confetti.
