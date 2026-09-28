# Structured extraction contract for corpus ingestion

How to make a VLM/LLM return usable structured data across millions of pages,
and how to catch the failures that still get through.

Reference implementation: `MersivMedia/crest-knowledge-graph` (`schema.py`,
`ingest.py`).

---

## The problem

A model asked for JSON will *usually* return JSON. "Usually" is not a contract
at 10⁶–10⁷ pages. Four distinct failure classes appear, and they need different
fixes:

| Failure | Cause | Fix |
|---|---|---|
| `unparseable` | prose, fences, truncation | constrained decoding |
| `schema_invalid` | wrong enum, missing field, out-of-range | constrained decoding + validator |
| `ungrounded` | entity not on the page — hallucination | grounding check |
| `refused` | content filter | open-weight model on own hardware |

Only the first two are syntax. The third is the dangerous one.

---

## 1. Constrained decoding, not prompting

Prompting for JSON is a request. Constrained decoding is a guarantee — the
model cannot emit a token that breaks the schema.

```python
# vLLM (self-hosted)
payload = {"model": MODEL, "messages": [...],
           "guided_json": PAGE_SCHEMA, "temperature": 0}

# OpenAI-compatible hosted
payload["response_format"] = {
    "type": "json_schema",
    "json_schema": {"name": "page", "schema": PAGE_SCHEMA, "strict": True}}
```

This collapses `unparseable` and `schema_invalid` toward zero, leaving the
interesting failures: hallucination, illegibility, missed visual elements.

**Keep the validator running anyway. Guided decoding guarantees shape, not
truth.**

---

## 2. Generate the prompt FROM the schema

Keep one source of truth. If the prompt is written by hand alongside a schema,
they drift — a new enum value gets added to one and not the other, and you
discover it 200,000 pages in.

```python
EXTRACTION_PROMPT = f"""...
Return ONLY a JSON object.

{json.dumps(PAGE_SCHEMA, indent=2)}

Rules:
- entities.type must be one of: {", ".join(ENTITY_TYPES)}
- visual_elements.type must be one of: {", ".join(VISUAL_TYPES)}
..."""
```

---

## 3. Schema fields worth having

Beyond the obvious `transcription` / `entities` / `relations`:

```jsonc
{
  "visual_elements": [            // why you chose vision over OCR
    {"type": "stamp", "text": "CONFIDENTIAL"},
    {"type": "redaction", "extent": "3 lines"},
    {"type": "photograph", "description": "aerial view of facility"}
  ],
  "legibility": 0.0,              // model's own confidence, 0-1
  "classification_markings": []   // domain-specific structure worth isolating
}
```

`legibility` is the hallucination tripwire. Low legibility plus a long
transcription is the signature of a model inventing text on an unreadable page.
Query for exactly that combination and audit against the image.

Also carry provenance per record so citations never need reconstructing:

```jsonc
{"doc_id": "...", "page": 3, "source": "archive.org|wayback",
 "ocr": "abbyy|vlm", "prompt_hash": "f9a2a644b535"}
```

---

## 4. Two gates, not one

```python
validate_page(obj)    # SHAPE: required fields, enum membership, ranges
check_grounding(obj)  # TRUTH: every entity name appears in the transcription
```

Grounding is the cheap deterministic hallucination detector. An entity the model
*knows* but that is not on the page is the worst possible failure for a
citation-backed archive: a plausible fabrication carrying a real citation.

```python
def check_grounding(obj):
    text = (obj.get("transcription") or "").lower()
    if not text:
        return True, []
    ungrounded = []
    for e in obj.get("entities") or []:
        name = (e.get("name") or "").strip()
        parts = [p for p in re.split(r"\s+", name.lower()) if len(p) > 2]
        if parts and not any(p in text for p in parts):
            ungrounded.append(name)
    return (len(ungrounded) == 0), ungrounded
```

Treat it as **advisory**, not an auto-reject: OCR mangles names
(`BRE2HNEV` → Brezhnev), so a genuinely present entity can score as ungrounded.
Flag for review; don't silently drop.

Verified behaviour — an entity list containing `Fidel Castro` against a
transcription reading "Routine supply requisition" is caught, while a correct
record passes both gates.

### Write the validator in stdlib

It runs on the GPU box, in CI, in the replay loop, and inside the agent's
analysis. Pure-stdlib means no dependency negotiation anywhere. A hand-written
validator mirroring the schema is ~80 lines and worth it.

---

## 5. Quarantine as a regression suite

Every failure is persisted with the **raw model output** that produced it:

```python
{"doc_id": ..., "page": ..., "reason": "schema_invalid",
 "detail": "entities[0].type invalid: 'ALIEN'",
 "raw": "<the model's actual output>",
 "prompt_hash": ..., "model": ...}
```

The raw output is the part people forget, and it is the only part that lets you
diagnose *why* rather than *that*. It also makes fixes provable:

```bash
python ingest.py --replay-all
# 287/402 previously-failing pages now pass
```

That is evidence. "This should fix it" is not.

---

## 6. Make the failure report a work queue

A number is not actionable. Group by reason, then by the most common *detail*
string within each reason:

```
status breakdown
  ok                    11,204  ( 94.2%)
  schema_invalid           402  (  3.4%)
  ungrounded               210  (  1.8%)
  unparseable               78  (  0.7%)

most common failure details
  [schema_invalid]
      312x  visual_elements[0].type invalid: 'watermark'
```

That last line diagnoses itself: the model keeps reaching for a category the
enum lacks. Either add `watermark` to `VISUAL_TYPES` or tell the prompt which
existing type covers it — a decision a human makes in seconds once the report
surfaces it.

---

## 7. Version the prompt

```python
def prompt_hash():
    return hashlib.sha256(EXTRACTION_PROMPT.encode()).hexdigest()[:12]
```

Store it on every record. Then success rates compare *across* versions:

```
prompt versions in play
  f9a2a644b535   120,400 pages   94.2% ok
  a31b0c9e7721    80,100 pages   91.8% ok
```

Without this you are assuming improvement. A prompt change that fixes one
failure class frequently degrades another, and you cannot see that trade
without per-version numbers.
