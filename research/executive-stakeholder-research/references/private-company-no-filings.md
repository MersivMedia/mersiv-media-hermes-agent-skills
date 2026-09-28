# Researching a private company with no SEC filings

The main skill assumes an issuer with a DEF 14A. When the target is private —
a startup, an agency, a PE-backed operator, a 2-year-old consultancy — there is
no proxy, no Item 5.02, no signature block. This is the substitute source
ladder, ordered by yield-per-request. It also covers the common variant of this
request: **"I have an interview with X and Y at company Z, tell me about them."**

## Source ladder (private company)

| Rank | Source | What it reliably yields |
|---|---|---|
| 1 | ATS job board (Gem / Greenhouse / Lever / Ashby) | Full open-role list, team structure, org build-out, geography split |
| 2 | Built In company page (`builtin.com/company/<slug>`) | Headcount, founding year, HQ, full job list — plain HTML, rarely blocked |
| 3 | Company blog / articles index | **Byline names** — founders and execs absent from any team page |
| 4 | Interviewers' own LinkedIn posts | The role as the hiring team actually describes it, in their words |
| 5 | Search snippets of LinkedIn profiles | Headline, current title, prior employer, education, metro |
| 6 | Company case-studies page | Concrete client outcomes and named client contacts |
| 7 | Regional/trade press + niche newsletters | Partnerships, momentum signals, headcount claims, exec residences |
| 8 | Aggregators (SignalHire, ZoomInfo, RocketReach) | Coworker names and titles — leads only, always `[UNVERIFIED]` |

## Finding the ATS board

The careers page is usually a marketing shell with an embedded iframe. Pull the
real board URL out of the HTML rather than reading the rendered page:

```bash
curl -sL 'https://<company>.com/careers' \
  | grep -oE 'https?://[^"]*(job|lever|greenhouse|ashby|gem)[^"]*' | sort -u
# -> https://jobs.gem.com/<slug>?embed=true
```

## Gem job boards are a client-rendered SPA

`jobs.gem.com/<slug>` returns an empty shell to `curl`; the page body arrives
from JS. Probing `/api/...` paths returns 302/404 and `api.gem.com` returns
`{"message":"Forbidden"}`. Do not burn calls hunting the JSON endpoint.

Do not fall back to `browser_exec` either — in this environment no Chrome
binary is installed (`google-chrome`/`chromium` are absent), so the browser
harness returns `chrome-not-running` and cannot self-launch. Client-rendered
boards must be read through the search index, not a headless browser.

**The working route is the search index.** Gem posting pages are individually
crawled, and search snippets carry substantial chunks of the job description:

```
site:jobs.gem.com <board-slug>
jobs.gem.com <board-slug> "<role title>"
```

Each result URL is a permanent posting (`jobs.gem.com/<slug>/<base64-ish-id>`)
and its snippet often contains the paragraph that matters. In one session this
surfaced the sentence defining how strategists and engineers split work in a
delivery pod — detail that appeared nowhere on the company's own site.

## Reading interviewers without LinkedIn access

Profile pages are login-walled. Two queries get you most of the way:

1. `"<Full Name>" <Company>` — search results echo the LinkedIn headline
   verbatim, which on a self-promoting profile carries title + positioning.
2. `"<Full Name>" <Company> <topic>` — surfaces their *posts*, which are far
   more useful than the profile. A recruiter's posts state the hiring bar in
   plain language; a director's posts reveal what they reward internally.

Watch for **name changes and multiple vanity URLs** for the same person
(maiden/married name, `/in/oldname` still resolving). Confirm identity by
matching company + title across two snippets before merging them into one
profile, and be alert to same-name collisions in other cities.

## Interview-prep output shape

When the ask is interview prep, the deliverable is not an org chart. Structure:

1. **The company** — what it sells, to whom, at what revenue band; verified
   credibility markers (partnerships, certifications, named frameworks);
   funding status (say "no evidence of a raise; appears bootstrapped" rather
   than guessing).
2. **Hiring posture** — the full open-role list read as a signal. Onshore vs
   offshore split, seniority mix, and first-generation roles tell you the
   strategy better than the About page.
3. **Culture in their own words** — quote the values page and the careers
   video transcript directly. Named frameworks (e.g. "Extreme Ownership") are
   literal interview filters; flag them as such.
4. **One section per interviewer** — verified title, background, what they
   post about, and an explicit *read* on what their round will test. Infer the
   round's nature from their function: recruiter = values/process screen;
   functional director = scoping and judgment.
5. **How to play it** — their published thesis in their own vocabulary,
   questions worth asking, and landmines (the things their marketing openly
   attacks are the things you must not sound like).
6. **`[UNVERIFIED]` block** — exact tenures, reporting lines, and funding are
   usually unconfirmable without login access. Name them; do not fill them in.

## Pitfalls specific to private targets

- **Company blog bylines are the real team page.** Sites frequently 404 on
  `/about-us` and `/team` while `/articles` exposes founder names and titles.
- **Two live domains** (e.g. `company.com` and `getcompany.ai`) often coexist
  after a rebrand, with a stale team roster on the older one. Date-check before
  quoting either.
- **Headcount numbers disagree across aggregators** by 2-3x. Give a range and
  cite which source said what rather than picking one.
- **Regional-press pieces about the same company are one PR push.** They repeat
  each other. Read one for facts; the rest add nothing but do confirm the
  company is actively running local PR — itself a signal.
- **Anonymized case studies still carry hard numbers.** Hours saved, volumes
  processed, and percentage reductions are quotable even when the client is
  "Non-Disclosed Company."
- **Founder LinkedIn headlines are a live metrics ticker.** Founders encode
  headcount, client count, and partnerships directly in their headline
  ("Team of 70+ ... | 65+ clients | OpenAI & Anthropic Service Partner").
  These are self-reported and usually well ahead of Built In / Crunchbase
  figures — cite both and give the range. Query
  `"<Founder Name>" <Company> founder` and read the search snippet.
- **`/authors` is the highest-yield page on a private company site.** Where
  `/team` 404s, `site:<domain> authors` enumerates the exec bench with exact
  titles, and each byline page carries a real bio (prior company, exit,
  revenue scaled) that appears nowhere else.
