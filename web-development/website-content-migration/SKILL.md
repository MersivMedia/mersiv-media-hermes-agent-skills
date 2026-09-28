---
name: website-content-migration
description: Rebuild a live site — crawl CMS, keep links and images.
version: 1.0.0
author: hermes-curator
license: MIT
tags: [migration, wordpress, scraping, rebuild, redesign, cms, content-extraction]
metadata:
  hermes:
    tags: [migration, wordpress, scraping, rebuild, redesign, cms, content-extraction]
    related_skills: []
---

# Website Content Migration

Rebuilding someone's existing website. The design work is the easy half; the
half that goes wrong is **getting all of their content out**, including the
parts that do not look like content.

## When to Use

- "Crawl this site and make a nicer version of it"
- Migrating off WordPress / Squarespace / Wix to a static or React front end
- Re-theming a site whose content must survive intact
- Any task whose acceptance test is "is everything still here?"

## 1. Find the structured source before you scrape HTML

Check the platform first. Hand-parsing rendered HTML when a clean API exists
wastes effort and loses fidelity.

```bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 \
(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
curl -sL -A "$UA" https://site.example/ -o home.html
grep -oiE '<meta name="generator"[^>]*>' home.html
```

WordPress exposes everything without auth:

```
/wp-json/wp/v2/pages?per_page=100
/wp-json/wp/v2/posts?per_page=100
/wp-json/wp/v2/categories?per_page=100
/wp-json/wp/v2/media?per_page=100
```

Always send a desktop User-Agent. Default `curl` and `Python-urllib` UAs get
403'd by many hosts.

## 2. THE CENTRAL PITFALL — text extraction destroys links and images

Get this wrong and it costs several rounds of user corrections. It did.

The instinct is to clean each field down to readable text:

```python
# WRONG — silently discards every href and src in the body
text = html.unescape(re.sub('<[^>]+>', ' ', post['content']['rendered']))
```

`content.rendered` is **HTML**, and the things users care most about live in
the *attributes* just deleted:

| What looks like plain text | What was actually in the markup |
|---|---|
| "Download the Membership Application here" | `<a href=".../Membership-Application.pdf">` |
| "Download the Club Bylaws" | `<a href=".../Bylaws-Approved.pdf">` |
| "September Wire" ×79 | 79 distinct PDF URLs |
| A board member's name | `<img src=".../Dottie.jpg">` directly above it |

A text-only extractor produces a site that *reads* complete and is functionally
gutted — dead "Download…" lines, missing portraits, an archive linking to
nothing. The user finds these one at a time, and each is a separate correction.

**Extract three streams from every body, not one:**

```python
text  = re.sub('<[^>]+>', ' ', body)                       # prose
links = re.findall(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', body, re.S)
imgs  = re.findall(r'<img[^>]+src="([^"]+)"', body)
```

**Verification gate — run before declaring extraction done:**

```bash
# Every document the old site offered must appear in your dataset
grep -oE 'href="[^"]*\.(pdf|docx?|xlsx?|zip)"' original.html | sort -u | wc -l
# Compare with the count in your JSON. A mismatch is a dropped feature.
```

Ask of each page: *does this offer anything downloadable, clickable, or visual
that pure text would not capture?* Applications, bylaws, newsletters, menus,
portraits, logos, maps, calendars.

## 3. Parse in document order when structure is positional

Content whose meaning comes from *adjacency* — a photo above a name, a date
label before a link — cannot be recovered by matching each element type
separately. Interleave into one ordered token stream:

```python
# Single pass. Put the RICHER alternative FIRST or the bare-text branch
# swallows the anchors before the link branch ever sees them.
pat = re.compile(r'<a\b[^>]*href="([^"]+\.pdf)"[^>]*>(.*?)</a>'
                 r'|(?<=>)([^<>]{2,60})(?=<)', re.S | re.I)

label = None
for m in pat.finditer(body):
    if m.group(1):                       # a PDF link
        if label:
            issues.append({"label": label, "url": m.group(1)})
            label = None
    else:                                # a text node — maybe a date heading
        t = m.group(3).strip()
        if re.match(r'^([A-Za-z]+)[,\s]+(20\d\d)$', t):
            label = t
```

Two real failures from getting this wrong:

- **Regex alternation order.** With the bare-text branch first, every anchor was
  consumed as text and *zero* PDF links were found — while the run still
  reported success.
- **Keying off the wrong anchor.** Dating newsletters from section headings
  collapsed all 79 issues into one year. The real date label sat immediately
  before each link. Sanity-check derived fields: if 79 items span a single year,
  the parse is wrong.

Blind pairing also *invents* data. Zipping alternating paragraphs into
name/role pairs produced a phantom 17th board member out of committee text.
Print the parsed result and eyeball it against the live page.

## 4. Reorganise — usually the actual ask

"Make a nicer version" means the information architecture, not just the CSS.
Look for structure the old CMS failed to express:

- **A single junk-drawer category.** 81 of 82 posts under "Past Activities", ten
  to a page, is unbrowsable. Derive real facets from titles:

```python
THEMES = [
    ("Luncheons",      r"luncheon|lunch|brunch|tea\b|dinner"),
    ("Travel & Tours", r"tour|trip|travel|cruise|visit|day at"),
    ("Holidays",       r"holiday|christmas|halloween|thanksgiving|valentine"),
    ("Fundraisers",    r"fundrais|charity|donat|auction|raffle|marketplace"),
]
```

- **Pagination hiding a decade.** Group by year, show counts, add live search.
- **Dropdown-buried pages.** Promote them to top-level nav.
- Keep a link back to each original post; it is cheap and reassures the owner
  that nothing was lost.

## 5. Images — decide hosting explicitly, then say what breaks

Ask rather than assume. For a CDN-hosted archive (e.g. `i0.wp.com`),
hotlinking is instant and stays in sync — fine while the source site stays up.

Normalise URLs during extraction:

```python
src = re.sub(r'\?.*$', '', src)                     # strip ?resize=640%2C678
src = re.sub(r'-\d+x\d+(\.\w+)$', r'\1', src)       # prefer the full-size file
```

Then state the tradeoff in the README and in the handoff: *if the original site
is retired, these images go dark.*

## 6. Verify against the live originals, not your own JSON

Your dataset agreeing with itself proves nothing. Check the URLs resolve and
return the right content type:

```bash
while read u; do
  curl -sL -o /dev/null -w "  %{http_code} %{content_type}  $(basename "$u")\n" \
    --max-time 20 "$u"
done < urls.txt
# want: 200 application/pdf ... / 200 image/jpeg ...
```

Then confirm the content reached the shipped bundle:

```bash
node -e "
const {readFileSync,readdirSync}=require('fs');
const js=readdirSync('dist/assets').filter(f=>f.endsWith('.js'))
  .map(f=>readFileSync('dist/assets/'+f,'utf8')).join('');
for (const [k,v] of Object.entries({board:'Dottie.jpg', pdf:'Bylaws'}))
  console.log((js.includes(v)?'OK  ':'MISS')+' '+k);
console.log('pdfs bundled:', (js.match(/uploads\/[^\"]*\.pdf/g)||[]).length);
"
```

Beware false negatives here: minified object keys lose their quotes, so
grepping `'"photo":"https'` reports 0 while `photo:` reports 16. Confirm any
"MISS" by printing surrounding context before acting on it.

## 7. Deployment

For Vercel specifics — `BLOCKED` deployments, `seatBlock`,
`COMMIT_AUTHOR_REQUIRED`, `TEAM_ACCESS_REQUIRED`, 302-on-preview from
`ssoProtection`, and confirming git auto-deploy — see
`references/vercel-deployment-state.md`. Those are account/project *state*
failures that no build-config change fixes, and they are easy to lose an hour to.

Three that always apply:

- **Set the git identity before the first commit.** Vercel refuses to deploy
  commits whose author is not a team member, and an agent's default synthetic
  identity (`agent@local`) triggers this on every push:
  ```bash
  git config user.name  "<GitHub account name>"
  git config user.email "<the Vercel account email>"
  ```
- **SPA deep links need a rewrite**, verified on a *nested* route:
  ```json
  { "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }] }
  ```
- **Never commit the extraction cache or a token.** Audit before first push:
  ```bash
  git diff --cached | grep -nEi '(vcp_|ghp_|sk-ant-)[A-Za-z0-9_-]{20,}'
  git ls-files | grep -E 'node_modules|^dist/|\.env$'
  ```

## 8. Never claim a step you did not verify

Two corrections in this session traced to reporting intent as fact:

- "Pushed to GitHub" — the chained command committed and deployed but never ran
  `git push`. Check `git status -sb` says *not* `[ahead N]`.
- "Both PDFs linked / photos hotlinked" in the first pass — the extractor had
  dropped every `href` and `src`, and the user found each gap individually.

Before reporting a step done, run the check that would fail if it were not:
`git rev-parse origin/main`, an HTTP status on the live URL, a grep of the
built bundle. The user is the last line of QA, not the first.

## Checklist

- [ ] Structured source (REST API) used where available, desktop UA sent
- [ ] Links, images AND text extracted from every body — not text alone
- [ ] Downloadable-file count matches the original site
- [ ] Positional content parsed in document order; result printed and eyeballed
- [ ] Derived fields sanity-checked (date ranges, counts, no phantom entries)
- [ ] Image hosting decided with the user; tradeoff written down
- [ ] Every PDF/image URL verified live with its content type
- [ ] Content confirmed present in the built bundle
- [ ] Git identity set to the deploy account's email before first commit
- [ ] `git status -sb` confirms the push landed — not `[ahead N]`
- [ ] Deep links verified on a nested route
- [ ] Secret audit clean before first push
