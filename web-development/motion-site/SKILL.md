---
name: motion-site
description: "Use when building a scroll-animated motion website from AI video."
version: 1.0.0
author: Hermes Agent (pipeline from @zeuuss_01's "$35K Motion-Website Playbook", rebuilt on Replicate)
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [web, scroll-animation, gsap, lenis, replicate, seedance, flux, landing-page, motion]
    related_skills: [replicate-api-generation, motion-graphics, diorama-3d-site, social-post-extraction]
---

# Motion site (scroll-scrubbed AI video landing pages)

## Overview
A landing page where each section is a short AI-generated clip. The clip is turned into a frame sequence and
painted onto a sticky canvas, so **scrolling plays the video**, with headline copy, glass cards and a CTA on top.
It's the "motion website" format from the Higgsfield + Claude Code playbook (`references/source-post.md`),
rebuilt so every generative step runs on **Replicate** (user decision 2026-10-03). The output is plain HTML/CSS/JS
with gsap, ScrollTrigger and lenis vendored, no build step, and it deploys anywhere.

Pipeline: brand kit + brief → `plan.json` → **stills** (flux-2-pro / nano-banana-pro) → **clips** (seedance-1-lite
image-to-video, optional end frame) → `frames.py` (WebP sequences + posters) → `site.json` copy → `qa.mjs` → deploy.

## When to Use
- "Motion website", "scroll animation site", "animated landing page", an Apple-style scroll-scrubbed product page,
  or a demo site for a business pitch (SaaS, e-commerce, local service).
- The user sends a Higgsfield / "Vibe Motion" / motion-website-generator post and wants the same result.
- **Not for:**
  - a real-time 3D object the visitor can touch → `diorama-3d-site`
  - a rendered MP4 → `motion-graphics`

## Procedure
1. **Brief first.** Get the brand kit (logo, 2–3 colours with hex, fonts, 1–3 reference images, a short business
   description), the audience and the CTA. For a pitch demo, invent a fictional brand and label it "Example data".
2. **Scaffold** the site:
   ```bash
   S=~/.hermes/skills/web-development/motion-site
   bash $S/scripts/new_site.sh ~/sites/<name>
   ```
   This copies the page template, `plan.json` and the vendored gsap 3.15 / lenis 1.3. The runtime lives at
   `~/.hermes/data/motion-site/runtime`.
3. **Plan** 3–5 video sections in `plan.json`:
   - one `still` prompt (the first frame) and one `motion` prompt per section, plus an optional `end_still`;
   - a shared `style` string;
   - `brand_refs` with `use_brand_refs: true` on sections that must show the real product or logo;
   - text-heavy sections (pricing, proof, FAQ, contact) are `"type": "block"` entries in `site.json`, with no video.

   Show the user the plan with the cost line from step 4 **before spending**.
4. **Dry run, then a test of one, then the batch:**
   ```bash
   python3 $S/scripts/gen.py plan.json --dry-run                          # every request + estimate, $0
   python3 $S/scripts/gen.py plan.json --only hero --stage stills --max-usd 0.2   # LOOK at assets/stills/hero.png
   python3 $S/scripts/gen.py plan.json --only hero --max-usd 0.5          # first clip
   python3 $S/scripts/gen.py plan.json --max-usd <estimate + 25%>         # the rest
   ```
   `gen.py` is resumable: prediction ids go to `assets/ledger.json` before polling. It refuses to spend without
   `--max-usd` and stops before any job that would cross the cap.
5. **Frames:** `python3 $S/scripts/frames.py .` turns each clip into desktop (1600 px) and mobile (720 px) WebP
   sequences plus a poster. It writes `assets/frames.json` and warns when a section goes over ~5 MB desktop or
   ~2 MB mobile.
6. **Copy and brand** in `site.json`:
   - `brand.vars` holds the colours, fonts, tint, grain and vignette;
   - each section has an eyebrow, a title (`\n` = line break), body, cards and button;
   - `length` is the scroll pacing (vh of scroll per clip; 260–340 reads well);
   - `align` is `right` or `center`, and `particles: true` adds drifting motes;
   - `focus: [x, y]` / `focus_mobile: [x, y]` (0..1) set where the frame sits. `fit` / `fit_mobile`: `cover`
     (default, fills the screen and crops) or `contain` (the whole frame is visible on the page bg).
     **Wide (21:9) clips on phones: use `fit_mobile: "contain"`.** A cover crop on a portrait screen showed one person
     and upscaled 640 px frames to a 1170 px-wide display, which the user saw as "cut off and low quality". With contain,
     frames need `--mobile-width 1170` (iPhone 3× DPR) to look sharp; put the copy in the page-bg space above the clip,
     and set `brand.vars.bg` to the image's own dark edge colour so it reads as one picture.
   - **Hero title over a dark edge of the clip.** This is a per-section choice, not a site default. Use it only
     where a section puts a title or headline over footage that has a natural dark side, like the first production site's hero
     (2026-10-03). Sections without overlaid copy, or with bright edge-to-edge footage, keep plain `cover` and
     no fade. When it applies:
     - phones: position the copy inside the clip's band. With contain + focus_mobile [.5,.5] the band is
       `top: calc(50% - (100vw/ratio)/2)`, height `100vw/ratio`. Fit the headline to the dark column in JS.
     - add `edge_fade: {"side":"left","solid":.17,"fade":.28,"color":"<bg>"}` on THAT section only. It turns the
       AI clip's noisy dark edge (dim figures, compression grain) into clean solid black behind the text. A
       translucent CSS scrim did not hide those artifacts. Measure the dark column's width per image (column
       luma) before setting `solid`/`fade`.
     - very wide (21:9) heroes leave only ~165 px of height on a phone, so the title ends up small. For a
       strong mobile hero, generate a separate 9:16 clip for phones (see "Phone-specific hero clip").
   - **Phone-specific hero clip** (per section, opt-in; first used 2026-10-03, $0.24 total):
     1. In plan.json, add a section `"<id>_m"` with `"aspect_ratio": "9:16"`, `"refs": ["brand/<photo>.jpg"]` and
        `"camera_fixed": true`. Ask the still model (flux-2-pro) to recompose the reference vertically with the SAME
        dark area the desktop title uses. The first site put the left 40% in deep shadow with the group on the right.
        Keep the title on the same side on every device: the user rejected a top-band layout ("I wanted it on the
        left side where the picture darkens"). Run `--stage stills` first (~$0.06), check faces, shirt text and the
        dark column's luma, then make the clip (~$0.18).
     2. `frames.py . --only <id>_m --mobile-width 864 --q 70 --max-frames 72`. Clips named `*_m` get phone frames
        only. 1170 wide at 96 frames was 13 MB; 864 at 72 frames was 6.7 MB.
     3. In site.json on the parent section, set `"mobile_clip": "<id>_m"`, `"fit_mobile": "cover"`, `"focus_mobile"`
        toward the dark side, and `"edge_fade_mobile": null` if the clip's own edge is already black. Use a soft CSS
        radial scrim behind the title rather than a hard fade over people. Desktop is unchanged.
     4. Check the clip's camera. Without `camera_fixed`, Seedance tilted up into bright sky after ~1 s and lost the
        dark area. With `camera_fixed: true`, the left 20% stayed below luma 30 for the whole clip.
     5. **Check people count and identity in every recomposed still.** The "dark left 40%" recomposition squeezed
        the group and DUPLICATED a person (two women in the same shirt on the left); the user rejected it. Pushing
        composition hard in a ref-recompose prompt invites duplicates. The live fix was the first, looser
        recomposition plus a strong top-left radial CSS scrim behind the title.
   - **Load weight:** a scroll hero doesn't need the full 5 s clip. `frames.py --trim 3 --fps 12` (36 frames)
     plus `"length": 220` took the first site from 9.2 MB to 2.6 MB on desktop and from 6.7 MB to 3.2 MB on the
     9:16 phone clip, with no visible scrub stutter. Start every hero at `--trim 3 --fps 12`; go up only if the
     user asks for a longer move.
   - **User-supplied first frame:** copy their image to `assets/stills/<id>.png` and `gen.py` skips the still
     (pays for the clip only). Seedance ignores `aspect_ratio` when given an image; the clip keeps the image's ratio.
   - **Custom kinetic headline:** a small per-site script (`<site>/fx.js`, 2026-10-03): per-letter drop-in, rainbow
     gradient sweep through background-clipped text, a rule drawing in, words rising in. Everything is scrubbed to
     the section's scroll and paired with a left scrim. Hook it with `"fx": "<name>"` on the section.
7. **QA, then look:** `node $S/scripts/qa.mjs .` takes desktop and mobile screenshots at 5/50/95% of every
   section. It also reports console errors, horizontal overflow, page weight and a **scrub check** (does the canvas
   change as you scroll?). Open `qa/sheet_desktop.jpg` and `qa/sheet_mobile.jpg` with vision before calling it done.
   Fix, re-run, repeat.
8. **Deploy:** the folder is static.
   - Vercel: `vercel deploy --prod`; follow the Vercel notes in memory for new projects.
   - Netlify Drop: drag the folder.
   - GitHub Pages: push and enable.

   Send the live URL plus `?` QA shortcuts if there are any.

## The six effects (all in `motion-site.css` / `site.js`, tuned per brand via `site.json`)
| Effect | How | Knob |
|---|---|---|
| Film grain | animated SVG fractal-noise overlay | `brand.vars.grain` (0–.15) |
| Particles | seeded drifting motes on a per-section canvas | `particles: true` or a CSS colour |
| Vignette | radial gradient over the stage | `brand.vars.vignette` |
| Glass cards | `backdrop-filter` blur cards | `cards: [{big, small}]` |
| Colour tint | multiply-blended brand tint over the footage | `brand.vars.tint` |
| Scroll pacing | Lenis lerp + ScrollTrigger scrub + section `length` | `pacing.lerp`, `pacing.scrub`, `length` |

`prefers-reduced-motion` shows posters only. On phones the 720 px sequence loads.

## Models and cost (live Replicate prices, read 2026-10-03; re-check before big runs)
| Step | Default | Price | Alternatives (all verified to exist) |
|---|---|---|---|
| Still / keyframe | `black-forest-labs/flux-2-pro` | ~$0.015/MP in+out (budget ~$0.06) | `google/nano-banana-pro` $0.15 at 2K (more photoreal, `image_input` refs) |
| Clip (image→video) | `bytedance/seedance-1-lite` 720p | $0.036/s (5 s = $0.18) | `seedance-1-pro` $0.06/s at 720p; `kwaivgi/kling-v2.1` $0.05/s std or $0.09/s pro, with `end_image`; `google/veo-3.1-fast` $0.10/s |

Typical 3-clip site: 3 stills + 3 × 5 s clips ≈ **$0.72** on the defaults (from `gen.py --dry-run`). Add 25% for
rerolls. Higgsfield's own pricing is credit-based, so a like-for-like comparison isn't meaningful.

## What we did NOT get from the source
- The post publishes no skill file, code, prompts or repo. Its setup steps exist only as screenshots
  (transcribed in `references/source-post.md`).
- Every price, "$35K", "$38,400/month" and "63% prefer video" figure is the author's marketing and unverified.
  Never repeat them to a client as fact.
- "Opus 4.8 / Fable 5" and Higgsfield's MCP and Vibe Motion are not used here.

## Common Pitfalls
1. **Overwriting `img.onload` on the first frame.** The loader counts frames through `onload`; replacing it on
   frame 0 stalled every section after the first. QA caught it as `pour: STATIC`. Use
   `addEventListener('load', …, {once: true})`.
2. **`mix-blend-mode: difference` on the nav** turned the wordmark blue over warm footage. Use plain ink over a
   soft top scrim.
3. **Frame weight.** Canvas scrubbing preloads every frame. 144 frames × 1600 px WebP at q72 is about 4–6 MB per
   section. Keep `--max-frames` ≤ 144, and the mobile set ≤ 2 MB.
4. **Image-to-video ignores text in the frame.** Generated stills must be text-free (the style string says so).
   All type is HTML, which keeps it crisp, translatable and accessible.
5. **The clip must not cut.** "Single continuous shot, no cuts" is appended to every motion prompt. Check the
   middle frames of each clip anyway, because a hidden cut reads as a jump when scrolled slowly.
6. **Leave room for copy.** Ask for negative space on the side where the headline sits ("leave clean negative
   space on the left third").
7. **Never spend without `--max-usd`.** Run the test of one before the batch, and show the cost table first.

## Verification Checklist
- [ ] `gen.py --dry-run` estimate shown to the user and approved
- [ ] every still looked at before its clip was generated
- [ ] `frames.py`: no section over budget
- [ ] `qa.mjs`: `QA: PASS` (every section `moves`, no console errors, no overflow)
- [ ] `qa/sheet_desktop.jpg` + `qa/sheet_mobile.jpg` checked by eye: copy legible, nothing clipped, nav readable
- [ ] illustrative numbers labelled "Example data"
- [ ] deployed URL opens on a phone

## Files
- `scripts/new_site.sh`: scaffold + vendor
- `scripts/gen.py`: Replicate stills → clips, resumable, spend cap
- `scripts/frames.py`: clips → WebP sequences + posters
- `scripts/qa.mjs`: headless QA
- `scripts/smoke_test.sh`: free end-to-end test
- `templates/site/`: `index.html`, `site.js`, `motion-site.css`, `site.json`
- `templates/plan.json`
- `references/source-post.md`: the original playbook, with its setup screenshots transcribed
