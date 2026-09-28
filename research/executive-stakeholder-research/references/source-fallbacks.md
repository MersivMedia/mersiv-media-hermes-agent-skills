# Source Fallbacks & Reliability Ranking

What to do when a people-data source blocks you, and how much to trust what
you do get back.

## Reliability tiers

**Tier 1 — cite freely, no tag.**
- SEC EDGAR filings (DEF 14A, 8-K, 10-K). Legally attested.
- Company press releases on GlobeNewswire / Business Wire / PR Newswire.
- Parent-company statements at merger close.
- Earnings call transcripts (Motley Fool, Seeking Alpha) for verbatim quotes.

**Tier 2 — cite, but attribute to the outlet.**
- Trade press interviews (HousingWire, Builder, industry verticals). Often the
  only place an executive says anything substantive about technology strategy.
- Conference speaker bios (they are company-supplied but not company-controlled).

**Tier 3 — leads only, always `[UNVERIFIED]`.**
- LinkedIn profiles and posts — self-reported; headline award claims especially.
- RocketReach, TheOrg, Equilar, Crunchbase, MarketScreener, TheOfficialBoard.
  These scrape and go stale silently. A title here can be years out of date.
- EIN Presswire / syndicated press-release mirrors — real content, but dates
  and current-status are unreliable.

## When a source blocks you

| Symptom | Cause | Fallback |
|---|---|---|
| `Just a moment... Enable JavaScript` | Cloudflare JS challenge on the IR site | Use EDGAR for filings; use the newswire mirror for press releases; search-result metadata often carries the needed sentence verbatim |
| `HTTP 403` from EDGAR | Missing/generic User-Agent | Send a descriptive UA ("name email") |
| `HTTP 403` from a trade-press or aggregator site | Bot blocking | Try the search-result description text; try another outlet that syndicated the same release |
| Extraction returns a *different* company's content | Guessed a newswire URL slug | Never construct newswire URLs from headlines. Verify the extracted body names your company before quoting |
| Page loads but body is empty | Client-rendered SPA | Look for the same release on a wire service |

**Rule:** an inability to read one source is never a reason to guess. Tag the
item `[UNVERIFIED]` with the reason, or state that it is not disclosed.

## Context-management when reading filings

Proxy statements run 200k+ characters and the leading ~40% is inline-XBRL tag
soup. Never print one whole. Use bounded section windows:

```python
# via scripts/edgar_filings.py
text = extract(proxy_url)
print(section(text, "MANAGEMENT"))            # officer bios
print(section(text, "Director Nominees"))     # board bios
print(section(text, "DIRECTOR COMPENSATION")) # reveals the board chair
```

For 8-Ks, `section(text, "Item 5.02", after=4000)` is usually enough.

For earnings transcripts, extract to a file and grep themes rather than
reading linearly:

```
technolog|AI |artificial|digital|efficien|cycle time|cost sav|automat|SG&A
```

## Non-obvious signals worth extracting

- **Director compensation table** identifies the board chair without any
  section saying "chairman" — the chair draws an extra annual retainer, so
  their total is visibly higher than peers'.
- **Retention bonus agreements in a merger 8-K** identify who the acquirer
  most needed to keep. A single named executive with an eight-figure retention
  package is a stronger signal of operational importance than any title.
- **The signature block** on the most recent 8-K confirms who currently holds
  the CFO or GC seat, post-any-changes.
- **Reporting lines in appointment press releases** ("reporting to X") reveal
  how the company frames a function. IT under Marketing means technology is
  treated as a customer-experience lever, and the CMO holds the budget.
