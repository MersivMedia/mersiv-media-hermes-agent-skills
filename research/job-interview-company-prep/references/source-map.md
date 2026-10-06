# Source map for company and interviewer research (observed Sep 2026)

## Fetch helper (use when web_extract is search-only)

```bash
# fetch.sh <name> <url>  → writes <name>.html and a tag-stripped <name>.txt
curl -sL --max-time 30 -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36" \
  "$2" -o "$1.html" -w "$1 %{http_code} %{size_download}\n"
python3 - "$1" <<'PY'
import re,html,sys
n=sys.argv[1]; s=open(n+'.html',errors='ignore').read()
s=re.sub(r'(?is)<(script|style|noscript|svg).*?</\1>',' ',s)
t=html.unescape(re.sub(r'<[^>]+>',' ',s)); open(n+'.txt','w').write(re.sub(r'\s+',' ',t))
PY
```

Save the script into the company workspace and loop over URLs in one terminal
call. Then slice the `.txt` files by keyword. Don't dump whole pages into
context.

## Usually readable (200 with real content)

| Source | What you get | Notes |
|---|---|---|
| LinkedIn public profile `/in/<slug>/` | Headline, location, follower count, About (truncated), recent posts, reposts and likes, certifications, languages, volunteering, projects | Job titles and dates are hidden behind asterisks for logged-out viewers, so say that rather than guessing. Some profiles return HTTP 999, meaning blocked; fall back to search snippets. |
| LinkedIn company `/company/<slug>` | About section, size band, employee count, specialties, recent posts | |
| LinkedIn post `/posts/<slug>_...-activity-<id>` | Full post text and comments | Executives' posts are the best source of recent metrics and hiring volume. |
| LinkedIn job `/jobs/view/<slug>-<id>` | Full job description | Also shows seniority and the applicant count. |
| JazzHR careers index `<co>.applytojob.com/` | Every open role | Get role links with `href="(https://<co>\.applytojob\.com/apply/[^"]+)"[^>]*>([^<]+)<`. Each `/apply/<id>/<slug>` page is the full job description. A regex with `\.` inside a hostname can trip the terminal approval scanner; approve it, it's harmless. |
| Company site: team, about, services, case studies | Titles, org shape, claims | Treat metric claims such as "top 5 seller" as self-reported. |
| Press releases via `finance.yahoo.com` | Full Business Wire text | Use when inc.com, morningstar or businesswire block or return empty 202s. |
| Vendor docs: developers.asana.com, developer-docs.amazon.com/sp-api, developers.google.com, knowledge.hubspot.com | Endpoint and notification names, quotas, plan gating | Use these to ground PRD integration sections. Some Asana reference slugs 404; the section index page (e.g. `/reference/project-templates`) lists the operations. |

## Usually blocked (403, JS wall, "Just a moment")

Glassdoor (all pages), Indeed company pages, RocketReach, Wiza, inc.com
profiles, ContactOut.

For these, cite the search-result snippet only for what it literally says,
and label it `[UNVERIFIED, snippet only]`. If one of them is load-bearing,
try the `blocked-page-recovery` ladder.

## Checked integration facts (good as of Sep 2026; recheck if old)

- **HubSpot workflow "Send a webhook"** requires the Data Hub Professional or
  Enterprise tier. If the company doesn't have that tier, fall back to a
  Zapier or Make HubSpot trigger.
- **Asana webhooks** begin with a handshake. After that, events are signed
  with the `X-Hook-Secret` shared secret, and deliveries are "compact", so
  the receiver must re-fetch the full resource. Heartbeat events can be
  empty. Projects can be created from project templates using the
  instantiate endpoint.
- **Amazon SP-API notifications:**
  - `LISTINGS_ITEM_ISSUES_CHANGE` fires when a listing's issues are created,
    changed or resolved (inactive, search-suppressed, quality issues).
  - `ACCOUNT_STATUS_CHANGED` fires when an account moves between NORMAL,
    AT_RISK and DEACTIVATED.
  - Other types in the same family: `LISTINGS_ITEM_STATUS_CHANGE`,
    `BRANDED_ITEM_CONTENT_CHANGE`, `ITEM_PRODUCT_TYPE_CHANGE`,
    `PRICING_HEALTH`, `FBA_INVENTORY_AVAILABILITY_CHANGES`.
  - Delivered via SQS or EventBridge. Fetch full issue details with the
    Listings Items API.
- **Google Apps Script limits (Workspace accounts):** 6 minutes per
  execution, 6 hours of trigger runtime per day, 100,000 URL Fetch calls per
  day, 30 simultaneous executions per user. Consumer accounts: 90 minutes of
  triggers and 20,000 URL Fetch calls per day.
- **Amazon Manage Your Experiments (MYE):** A/B tests images, titles,
  bullets, descriptions and A+ Content, including Brand Story, by randomly
  splitting detail-page viewers. It reports units, sales, conversion rate,
  units per unique visitor and sample size. It needs a Professional selling
  account plus the Brand Representative role on a Brand Registry brand.
  Source: `sell.amazon.com/tools/manage-your-experiments`, which fetches
  cleanly. The Seller Central help pages don't.
- **Amazon Marketing Stream:** push-based, hourly traffic and conversion
  metrics for Sponsored Products, Sponsored Brands, display ads and DSP,
  delivered through the Amazon Ads API. Needs AWS setup. Source:
  `advertising.amazon.com/library/guides/amazon-marketing-stream`.
- **Amazon Ads API v3 reporting docs:** advertising.amazon.com/API/docs
  returns almost nothing through curl, since the pages are rendered by
  JavaScript. Cite the guide pages or the `amzn/ads-advanced-tools-docs`
  GitHub discussions instead, and mark rate limits "confirm in discovery".

## Research and model sources

- **arXiv `/abs/<id>` pages fetch cleanly** and give the title and full
  abstract. That is enough to quote effect sizes and CIs.
- **emergentmind.com/topics/<model>** fetches, and lists follow-on papers,
  both positive and negative, with arXiv IDs in its hrefs
  (`/papers/<id>`). It's the fastest way to find an independent evaluation.
- **ai.meta.com blog and publication pages** return 400 through curl. Use
  the GitHub README, the HF model card, the arXiv abstract, and secondary
  write-ups such as MarkTechPost for architecture numbers.
- **creativecommons.org `/licenses/<id>/4.0/legalcode.en`** fetches, so
  quote the NonCommercial definition directly.
