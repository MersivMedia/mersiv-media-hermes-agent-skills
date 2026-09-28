# Page anatomy: sections, ads, compliance, file layout

Merged in from `Clone Working AI Tool Structure` (2026-09-27). The SKILL.md
covers cloning, content transformation and the API; this is the checklist of
what a finished single-page tool must contain.

## Required sections

Hero, Tool, Features (6), How It Works (3 steps), FAQ (6–8), ads, cookie
consent. Missing FAQ, How It Works or cookie consent was the most common gap
in tools built from scratch.

- **Hero**: tool-specific icon, clear value proposition, gradient design.
- **Tool interface**: input with character limits and validation, loading
  state with tool-specific wording, results with copy button, error feedback.
- **Features**: six benefit cards.
- **How It Works**: three numbered steps specific to the tool.
- **FAQ**: 6–8 tool-specific questions (feeds the FAQPage schema).

## Cookie consent banner

```html
<div id="cookieConsent" style="display: none; position: fixed; bottom: 0; left: 0; right: 0; background: #2d3748; color: white; padding: 15px; z-index: 10000;">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <p>We use cookies to enhance your experience and serve personalized ads.</p>
        <div>
            <button onclick="acceptCookies()">Accept All</button>
            <button onclick="rejectCookies()">Reject All</button>
        </div>
    </div>
</div>
```

For a fuller GDPR/CCPA setup see the `Cookie Consent Integration` skill.

## Ad placement (7 slots)

| # | Position | Size |
|---|---|---|
| 1 | Top banner | 728×90 |
| 2 | Mid content | 728×250 |
| 3 | Features section | 728×250 |
| 4 | FAQ mid | 728×90 |
| 5 | FAQ bottom | 728×250 |
| 6 | Sidebar skyscraper | 160×600 |
| 7 | Sticky bottom | 728×90 |

```html
<div class="ad-slot ad-slot-leaderboard">
    <ins class="adsbygoogle" data-ad-slot="1234567890"></ins>
</div>
```

For the sticky vertical-sidebar variant see `AI Tool Sticky Ads Layout`.

## SEO

- Structured data: WebApplication (features, ratings), FAQPage, HowTo.
- Meta: keyword title, description, Open Graph, Twitter Cards, canonical URL,
  mobile/PWA tags.

## File layout that deploys cleanly

```
new-tool/
├── index.html             # static HTML app, no build step
├── api/tool-endpoint.js   # serverless route, JavaScript only
├── package.json           # minimal: just the OpenAI dependency
├── vercel.json            # simple serverless config
├── privacy-policy.html    # GDPR-compliant
├── terms-of-service.html
├── robots.txt
├── sitemap.xml            # every page, correct domain
└── public/ads.txt         # AdSense verification
```

Legal pages: see `Professional Legal Page Separation`.

## Done means

- [ ] Deploys to Vercel without build errors
- [ ] Every section renders on desktop and mobile
- [ ] Cookie consent accept and reject both work
- [ ] Rate limit enforced (3 requests/day/IP)
- [ ] Ad slots present and AdSense-ready
- [ ] Structured data and meta tags in place
- [ ] API returns real results with a key, a relevant demo without one

## Where the approach fits, and where it failed

Works for document processors, content generators, analysis tools,
translation/format converters and creative generators. Measured in practice:
2–3 hours per tool against 8–12 from scratch.

It failed when the user wanted a fundamentally different UI, real-time
features, external APIs beyond OpenAI, or user accounts/database storage.
Build those properly rather than forcing the template.
