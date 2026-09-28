# Finding OCR That Already Exists

Stage ① of the cascade is the whole cost. Before designing or pricing it, spend
twenty minutes checking whether someone has already run OCR over the corpus and
published the derivatives. When they have, stage ① collapses to bandwidth.

This is not a long shot. Large public archives are routinely mirrored to
Internet Archive, HathiTrust, or a national library, and those mirrors usually
carry **better** derivatives than the originating site.

## The primary host is often the worst source

Government and institutional sites frequently sit behind a bot manager. The
signature is unmistakable once you look for it:

```bash
for u in "https://host/real-document-id" \
         "https://host/collection/browse" \
         "https://host/sitemap.xml"; do
  curl -sL --compressed -A "$DESKTOP_UA" -o /tmp/x -w "%{http_code} %{size_download}\n" "$u"
done
```

Identical `size_download` for a real document, a collection page, and
`sitemap.xml` means you are measuring the challenge page, not the site. Confirm
by grepping the body for the vendor's marker (`bm-verify` for Akamai Bot
Manager, `cf-challenge` for Cloudflare).

Two things follow. The host is not scrapable no matter how the request is
shaped, and **every conclusion drawn from those bytes is void** — including any
conclusion about whether OCR text exists there.

Sending `--compressed` with a full browser header set is still worth one try;
some hosts gate on `Accept-Encoding` alone and this is the cheapest possible
fix. If the challenge persists, move to a mirror rather than escalating.

## Internet Archive: enumerate, then inspect derivatives

Archive.org has a real JSON API, does not bot-wall, and exposes exactly the
fields this skill cares about.

**Enumerate the collection:**

```bash
curl -s "https://archive.org/advancedsearch.php\
?q=collection%3A<collection-id>\
&fl%5B%5D=identifier&fl%5B%5D=title&fl%5B%5D=item_size\
&rows=50&page=1&output=json"
```

`numFound` gives corpus size. Note it counts **items (documents)**, not pages —
do not compare it against a page-count claim without a pages-per-document
estimate.

**Inspect one item's derivatives — this is the decisive call:**

```bash
curl -s "https://archive.org/metadata/<identifier>"
```

| Derivative | Why it matters |
|---|---|
| `_djvu.xml` | **per-word bounding boxes, page-segmented, with DPI** |
| `_djvu.txt` | plain OCR text |
| `_abbyy.gz` | full ABBYY output |
| `.pdf` | original scan |
| `_jp2.zip` | page images — feed these to the VLM repair stage |

`_djvu.xml` is the prize. Its structure:

```xml
<OBJECT height="3301" width="2550">
  <PARAM name="PAGE" value="..._0000.djvu"/>
  <PARAM name="DPI" value="300"/>
  <WORD coords="540,383,744,342,374">Approved</WORD>
```

Page number, word, and pixel coordinates — the exact provenance triple needed
for "cite the source page and highlight the term". Getting this for free
eliminates both the OCR bill *and* the highest-risk design decision in the
pipeline (§4 of the parent skill).

## PITFALL: the download URL needs encoding, and a 404 looks like text

Archive.org filenames often contain spaces and commas, derived from the
original document title:

```
MARBACH, KARL HEINZ_0001_djvu.txt
```

A naive `https://archive.org/download/<id>/<name>` fails on these. Two failure
shapes, both of which wasted time in a real session:

- **`curl` returns `000`** — the unencoded URL never forms a valid request.
  This looks exactly like rate-limiting, and was misdiagnosed as such. Adding
  retries and sleeps did nothing. Encode the filename instead.
- **`curl` returns `200` with a 137 KB body** — archive.org serves a styled
  HTML **404 page** for a bad path. Scoring that body as if it were OCR
  produced a confident "95.8% text quality" figure for documents that had
  returned no text at all.

Correct form — take `server` and `dir` from the metadata response and
percent-encode the filename:

```python
import json, urllib.parse
meta = json.loads(resp)
fn   = next(f['name'] for f in meta['files'] if f.get('format') == 'DjVuTXT')
url  = f"https://{meta['server']}{meta['dir']}/{urllib.parse.quote(fn)}"
```

**The general rule: never score a response body before asserting its HTTP
status and content type.** A quality metric run over error pages returns a
plausible number and is entirely fiction. Assert `200`, then measure.

## Measure OCR quality before trusting it

Sample 5–10 documents and score word-plausibility rather than eyeballing one:

```python
def quality(txt):
    toks = re.findall(r"[A-Za-z][A-Za-z'.-]{1,}", txt)
    good = sum(1 for t in toks
               if (s := t.strip(".'-")) and len(s) >= 2
               and (v := sum(c in 'aeiouAEIOU' for c in s)) > 0
               and v / len(s) >= 0.15
               and not re.search(r'[A-Z]{2,}[a-z][A-Z]', s))
    return good / len(toks), len(toks)
```

Observed on mid-century typewritten government scans: **mean 93%, range
90–97%** across six documents. Report the range and n, not a single figure.

## The quality split that makes confidence routing practical

Mixed OCR quality within one page is not noise — it is structured, and the
structure is useful.

Body prose comes through clean:

> HUMPHREY-SCOTT CODEL MET WITH BREZHNEV AT KREMLIN JULY 2 FOR TWO HOURS.
> BREZHNEV, WHO APPEARED IN GOOD FORM, SPOKE VIGOROUSLY ALONG FAMILIAR LINES…

Margins, routing stamps, handwriting and classification markings do not:

> k him .ttJ/m' / 1 MU.. /•* … ETA712 … FILE. BbOrflflfeOHfc O/SWS

**Typed body text OCRs well; handwritten marginalia and stamps do not.** So the
escalation rule writes itself — route pages whose token-plausibility falls below
threshold, and let clean typescript pass through untouched. That is how
escalation stays near 5% instead of being guessed, which is what keeps the
cascade in §3 cheap.

It also sets expectations honestly: an archive with excellent body OCR may still
have near-zero recall on the handwritten annotations, which are often exactly
what a researcher wants. Say so rather than quoting the headline accuracy.

## Measuring coverage: how complete is the mirror?

"N items" answers nothing about completeness when the claim you are checking is
in pages. Converting requires a pages-per-item estimate, and getting one is
where two traps live.

### Trap 1: metadata facets are contaminated — filter on the ID scheme

The obvious query is the collection's subject tag. Do not trust it. A subject
facet is crowd-editable on most archives, and on one real corpus
`subject:<PROGRAM>` returned 319,198 items — including **television news
broadcasts** at ~3,661 "pages" each:

```
3,659  MSNBCW_20180216_020000_The_Rachel_Maddow_Show
7,261  MSNBCW_20141004_120000_Up_WSteve_Kornacki
```

Those inflated the estimate to **498 million pages** against a corpus claiming
13 million. The nonsense magnitude is what exposed it.

Filter on the corpus's own **document-identifier scheme** instead, which is
assigned by the originating institution and cannot be tagged onto unrelated
media:

```
identifier:CIA-RDP*          ← authoritative
subject:CREST                ← contaminated, 3,519-item title match, TV news
```

**Always sanity-check an extrapolation against the known total before
believing it.** A coverage figure above 100% means the filter is wrong, not
that the mirror is unusually complete.

### Trap 2: paged search silently returns partial results

`advancedsearch.php` with `rows`/`page` drops records without erroring. Observed
in one session: 1,000 items requested, **146 carried `imagecount`**; a second
pass over 18 randomised pages returned 100 of 1,800. Successive estimates from
the same corpus swung **8.63 → 2.37 → 4.00** pages per item — pure sampling
noise that would have been reported as fact.

Use the **scrape API**, which is built for bulk and paginates by cursor:

```bash
curl -s "https://archive.org/services/search/v1/scrape\
?q=identifier%3A<PREFIX>*&fields=imagecount&count=10000"
# then follow the "cursor" field in the response until it is absent
```

Write results to disk and aggregate there — a large JSON body will be truncated
in transit if you try to parse it inline.

That produced a stable census: **24,154 items measured, mean 4.00 ± 0.18 pages
(95% CI)**, versus the ±3-page swing from paged sampling.

### Report the distribution, not just the mean

```
mean 4.00 | median 2 | p90 6 | p99 43 | max 479
1pg=11,856   2-5=9,631   6-20=2,001   21-100=579   100+=87
```

Median 2 with a 479 tail means most documents are single memos and cables. That
shapes chunking, graph density and UI far more than the mean does — and a
handful of bound volumes will wreck a mean-based estimate if the sample is small.

Final coverage on that corpus: **~1.1M pages ≈ 8.5%** of the stated release.
A substantial subset, not the archive — and worth stating in exactly those terms
so the user does not later claim to have ingested "all" of anything.

## Before scoping on a mirror

- [ ] Confirmed the mirror carries OCR **and** coordinates, not text alone
- [ ] Sampled ≥5 documents with HTTP status asserted before scoring
- [ ] Reported quality as mean + range + n
- [ ] Checked item count vs. page count — items ≠ pages
- [ ] Filtered on the **document-ID scheme**, not a subject/collection tag
- [ ] Used the scrape API for the census; paged search truncates silently
- [ ] Extrapolation sanity-checked against the known total (>100% = bad filter)
- [ ] Coverage reported as a measured percentage with n and CI, or explicitly
      as unverified — never implied
