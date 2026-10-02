# Claim audit for launch posts

Launch copy mixes three kinds of claims. Check each kind differently before
handing over. This user reviews claims closely and asked directly: "make sure
all of the claims are true. Is hermes agent really doing this?"

## Checklist

| Claim type | Example | How to check |
|---|---|---|
| Measured number | "cut cost by 39%" | Trace it to the RESULTS row (run, n, correctness in both arms) |
| Derived estimate | "saved 75× what it cost" | Recompute the range from its inputs. State "list price, not a bill". Round to the conservative end |
| Mechanism ("how things work") | "every call re-sends the whole conversation" | Read the host's source and the user's config. Cite file:line. Note mitigations the sentence leaves out |
| Proportion | "went back for only 2%" | Recompute (21/1,215 = 1.7%). Check whether the denominator mixes shadow-only and live items, and use a verb that covers both ("flagged") |

Report per claim: true / overstated (give a reworded sentence) / estimate
(give the range). Put qualifiers below the post, not inside it.

## Verified facts: agent context cost (Hermes, Sept 2026)

- **Full re-send is true.** `agent/conversation_loop.py` (~line 2238)
  rebuilds `api_messages` from every stored message before each model call,
  old tool outputs included. Model APIs are stateless, so every agent does
  this. Each tool step inside a task is its own model call.
- **"Pay again each time" is overstated.**
  - Prompt caching is on (`prompt_caching.cache_ttl: 5m` in config.yaml;
    markers in `agent/prompt_caching.py`). Cached prefix reads bill at about
    0.1× the input price.
  - After 5 idle minutes the cache expires, and the next call pays to write
    the whole history again. Jermes trims only when the cache is cold, so a
    trim never invalidates a warm cache.
- **The built-in compressor** summarises older turns at
  `compression.threshold: 0.5` of the context window. History grows large
  before anything shrinks it, but not forever.

Accurate wording that was offered:

> Every model call re-sends the whole conversation, old logs and file reads
> included. Caching makes the repeats cheaper, but you still pay for all of
> it on every call, and full price again whenever the cache expires.
