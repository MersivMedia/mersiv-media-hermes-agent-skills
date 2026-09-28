#!/usr/bin/env python3
"""EDGAR helper for executive/board research.

Two modes:

    python3 edgar_filings.py "Example Homes"        # find CIK + list filings
    python3 edgar_filings.py --cik 1561680             # list filings by CIK
    python3 edgar_filings.py --extract <url>           # filing HTML -> plain text

EDGAR requires a descriptive User-Agent or it returns HTTP 403. Set
EDGAR_UA to your own "name email" string; a generic default is used otherwise.

Only stdlib. No API key.
"""

import html
import json
import os
import re
import sys
import urllib.request

UA = os.environ.get("EDGAR_UA", "research-agent contact@example.com")

# Forms that carry governance / personnel content.
GOVERNANCE_FORMS = ("DEF 14A", "DEFA14A", "8-K", "10-K", "S-4")


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=60).read().decode("utf8", "ignore")


def resolve_cik(name: str) -> list:
    """Return [(cik, ticker, title), ...] matching a company name or ticker."""
    data = json.loads(_get("https://www.sec.gov/files/company_tickers.json"))
    needle = name.lower()
    hits = []
    for row in data.values():
        if needle in row["title"].lower() or needle == row["ticker"].lower():
            hits.append((str(row["cik_str"]).zfill(10), row["ticker"], row["title"]))
    return hits


def list_filings(cik: str, since: str = "2024-01-01", forms=GOVERNANCE_FORMS) -> list:
    """Return [(form, date, url), ...] newest first."""
    cik = str(cik).zfill(10)
    data = json.loads(_get(f"https://data.sec.gov/submissions/CIK{cik}.json"))
    recent = data["filings"]["recent"]
    out = []
    for form, date, doc, acc in zip(
        recent["form"], recent["filingDate"],
        recent["primaryDocument"], recent["accessionNumber"],
    ):
        if form in forms and date >= since:
            folder = acc.replace("-", "")
            url = (f"https://www.sec.gov/Archives/edgar/data/"
                   f"{int(cik)}/{folder}/{doc}")
            out.append((form, date, url))
    return out


def extract(url: str) -> str:
    """Strip an EDGAR HTML filing down to readable plain text."""
    t = _get(url)
    t = re.sub(r"<script.*?</script>", " ", t, flags=re.S)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    return re.sub(r"[ \t\xa0]+", " ", t)


def section(text: str, marker: str, before: int = 200, after: int = 12000) -> str:
    """Bounded window around a section heading.

    Proxies are huge and the first chunk is XBRL tag soup — never print the
    whole file into agent context. Use markers like 'MANAGEMENT',
    'Director Nominees', 'DIRECTOR COMPENSATION', 'Item 5.02'.
    """
    i = text.find(marker)
    if i == -1:
        return f"[marker not found: {marker}]"
    return re.sub(r"\s+", " ", text[max(0, i - before):i + after])


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1

    if args[0] == "--extract":
        print(extract(args[1]))
        return 0

    if args[0] == "--cik":
        cik = args[1]
    else:
        hits = resolve_cik(" ".join(args))
        if not hits:
            print(f"No CIK match for {' '.join(args)!r}")
            return 1
        for cik_, ticker, title in hits:
            print(f"CIK {cik_}  {ticker:8}  {title}")
        cik = hits[0][0]
        print(f"\nUsing CIK {cik}\n")

    for form, date, url in list_filings(cik):
        print(f"{form:8} {date}  {url}")
    print("\nNext: --extract the newest DEF 14A, then every 8-K after it "
          "(grep Item 5.02).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
