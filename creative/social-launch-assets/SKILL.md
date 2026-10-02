---
name: social-launch-assets
description: Launch posts and infographics for a shipped project.
version: 1.0.0
author: Mersiv Media + Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [linkedin, social-media, infographic, launch, html-render, copywriting]
    category: creative
    related_skills: [generated-asset-verification, humanizer, marketing-skills, baoyu-infographic]
---

# Social Launch Assets Skill

Turn a shipped project (repo, tool, result) into a LinkedIn/X post and a
matching infographic. Covers the copy, a code-rendered HTML infographic with
exact numbers, and an optional AI-illustrated variant. It does not cover
brand videos (see `brand-youtube-pipeline`) or ad campaigns.

## When to Use

- "Write a LinkedIn / social post about <project>".
- "I need an infographic to accompany the post."
- Announcing measured results (savings %, benchmark scores) where the
  numbers must be exactly right.

## Prerequisites

- The project's README / results page as the only source of numbers.
- Headless Chromium for rendering: Playwright's `chrome-headless-shell`
  (under `~/.cache/ms-playwright/chromium_headless_shell-*/`).
- Good fonts installed in `~/.fonts` (Inter, JetBrains Mono from their
  GitHub releases, then `fc-cache -f`). DejaVu/Liberation look generic.
- `image_generate` for the illustrated variant; PIL for text repair.

## Quick Reference

| Deliverable | Spec |
|---|---|
| LinkedIn feed image | 4:5, 1080×1350, render at 2× (2160×2700) |
| X short post | ≤280 chars, one number, the link |
| Stories | 9:16 (the raw `image_generate` portrait) |
| Render | `scripts/render_html.sh in.html out.png 1080 1350` |
| Starter | `templates/infographic-4x5.html` (dark navy + one accent) |

## Procedure

1. **Copy first, from verified numbers only.** Pull every figure from the
   README/RESULTS, not memory. Shape that worked for this user:
   - hook line naming the problem in plain words ("My agent was paying
     frontier-model prices to answer yes/no questions");
   - what it is in 2 sentences;
   - one `→` bullet per feature: **why I built it** (the pain) + the
     number;
   - "starts in shadow mode" style safety line; link; "numbers from my own
     install, methods in the repo".

   Write in first person as the user. Add a short X version. Below the
   post (not in it), list the qualifiers people will ask about (test tasks
   vs live, list-price estimate). Run the humanizer rules: no hype words,
   no "not X but Y".

   **No absolute dollar amounts in public posts or graphics.** This user
   asked to remove them ("remove the parts that are actual dollar amounts")
   from the infographic, then from the post. Use relative figures: % change,
   before/after as 100% vs 61%, "N× more saved than spent", counts ("1,148
   decisions", "one pass over 95 skills"), "a fraction of the price". Dollar
   figures can stay in the repo's RESULTS page.

   **Audit every claim before handing over, including the mechanism
   sentences, not just the numbers.** The user asked "is hermes agent
   really doing this?" about "every model call re-sends the whole
   conversation … you pay for them again each time". Check how-it-works
   claims against the host's source and the user's config (file:line), and
   say which parts are true, overstated, or estimates. Round ranges to the
   conservative end (73–85× → "roughly 70×"). Checklist and verified agent
   cost facts: `references/claim-audit.md`.
2. **Ask three things in one `clarify`:** method (code-rendered /
   AI-illustrated / both), shape (4:5 recommended for LinkedIn), look.
   Recommend code-rendered whenever exact numbers carry the message: image
   models garble digits and small text. This user chose "both, and I'll
   pick".
3. **Code-rendered version:** copy `templates/infographic-4x5.html`, swap
   content. Layout that read well: tag line → hook headline → hero number
   with a before/after bar → 3-stat strip → 4-node "how it works" flow → 6
   feature cards (icon, name, stat, one line; highlight the 2 headline
   features) → footer with repo URL + one caveat line. Render with the
   script, then inspect the PNG with vision for clipping, orphans, footer.
4. **AI-illustrated version:** keep generated text to ~4 short strings plus
   one-word or two-word card labels; spell each out as `exactly "..."`. Use
   `upscale: true`. Read every label back with vision; repair any
   misspelling in post (step 5) rather than re-rolling repeatedly.
5. **Post-fixes** (details in `references/ai-image-text-repair.md`):
   - paint over a garbled label with the card's median background and
     composite correct text, matched to a neighbour label's ink box
     (height, width, baseline) and ink density;
   - reframe 9:16 → 4:5 by scaling to full height and feathering the edges
     into a per-row background colour field plus a light vignette. A flat
     pad shows visible letterbox bars.
6. **Deliver to Drive** (user is on iPhone): upload all variants into a
   named folder under `GDRIVE_OUTPUT_IMAGES`, give the folder link, and
   recommend one variant with a reason (code = claims + shareable; AI =
   scroll-stopper for X/Stories). Say plainly about any hand repair.
   For revisions, **replace the file in place** (Drive v3
   `PATCH /upload/drive/v3/files/<id>?uploadType=media`, looking up the id by
   name + parent folder), so the name and any shared link survive.
7. **Keep post and graphic in sync.** When a figure or wording changes in
   one, change it in the other in the same turn, or say which one is now
   out of step and offer the matching edit (the user said "yes update the
   post as well"). List the old → new changes in a small table.

## Pitfalls

- **`chrome --headless=new --window-size=W,H` gives a viewport ~87px
  shorter than H** (browser chrome is reserved), so the bottom of a
  full-height poster (footer) silently disappears from the screenshot while
  the layout is fine. Use `chrome-headless-shell`, which gives the exact
  viewport. Diagnose by injecting `document.title=innerWidth+'x'+innerHeight`
  and `--dump-dom`.
- Put the footer in flow (`body{display:flex;flex-direction:column}` +
  `.foot{margin-top:auto}`), not `position:absolute; bottom`, so overflow is
  visible instead of overlapping cards.
- Glue the last two words of stat captions with `&nbsp;` to avoid orphans.
- Inter is wider than most image-model lettering; a replacement label at
  matching height may not fit the card. Render at matching height, then
  resize horizontally to the neighbour's letter width (≤ ~15% squeeze, or it
  looks compressed).
- Never put numbers in the AI version that aren't in the README.

## Verification

- Every number in post + graphic traced to the README/RESULTS, and every
  mechanism sentence checked against the host's code and config
  (`references/claim-audit.md`).
- No absolute dollar amounts in the post or the graphic (grep the HTML for
  `\$[\d]`), and the post and graphic use the same figures.
- Rendered PNG is exactly 2× the design size; vision check shows footer,
  no clipping, no orphans.
- AI variant: every label read back and spelled correctly.
- Drive upload returned file ids and sizes; folder link given.
