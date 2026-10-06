---
name: diorama-3d-site
description: "Use when building an interactive 3D (three.js) website or landing page."
version: 1.0.0
author: Hermes Agent (adapts blendi-remade/dioramas, MIT, onto Replicate)
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [web, 3d, three.js, webgl, image-to-3d, replicate, hunyuan3d, landing-page, gsap, lenis]
    related_skills: [motion-site, replicate-api-generation, motion-graphics]
---

# Diorama 3D site (interactive three.js landing pages with AI-generated hero objects)

## Overview
A landing page where **the 3D scene is the page**: one hyper-detailed generated object, real lighting, a camera
choreographed by scroll, and one signature interaction you can touch (press-hold, drag, wipe, crack). Built on the
open-source **Dioramas** engine (github.com/blendi-remade/dioramas, MIT code, CC BY 4.0 example assets). It's
pinned at commit `868539f` (2026-09-29) and has 20 example worlds.

Dioramas generates its assets on fal (Nano Banana 2 + Meshy 7.1). This skill swaps in **Replicate** for both steps,
so it uses the same token as everything else:

prompt → **plate** (object on white, `google/nano-banana-pro`) → **GLB** (`tencent/hunyuan-3d-3.1` with PBR, or
`hyper3d/rodin` Gen-2) → `optimize.sh` (meshopt + WebP) → page on the engine → screenshots → review → revise.

## When to Use
- "3D website", "three.js landing page", "interactive 3D product page", "WebGL hero", an Awwwards-style site, or the
  user links Dioramas or a similar 3D-site repo.
- A product, collectible, gadget, food, architecture or any physical object that's worth turning over.
- **Not for:**
  - scroll-played video (no real 3D) → `motion-site`
  - a rendered MP4 → `motion-graphics`

## Procedure
1. **Brief.** Copy `templates/BRIEF.md` (the Dioramas brief format) and fill in:
   - brand and one-line promise;
   - **signature interaction**: a verb, what the 3D does in response, and the touch equivalent;
   - page sections, each with a distinct camera state;
   - art direction: palette with hex, a Google Fonts pairing, motivated lighting;
   - the asset table;
   - the "Must be true" frames.

   Show it to the user and get an OK.
2. **Scaffold** a project on the pinned engine:
   ```bash
   S=~/.hermes/skills/web-development/diorama-3d-site
   bash $S/scripts/new_diorama.sh ~/sites/<project> <slug>
   ```
   This sparse-clones Dioramas **without its 310 MB of example models** (it keeps one 2 MB sample), then installs
   npm packages. It adds `examples/<slug>/` from our template, `assets/jobs-<slug>.json`, `docs/briefs/<slug>.md`
   and `scripts/optimize-any.mjs`.
3. **Assets: dry run, plates, LOOK, then meshes:**
   ```bash
   python3 $S/scripts/gen3d.py assets/jobs-<slug>.json --dry-run
   python3 $S/scripts/gen3d.py assets/jobs-<slug>.json --stage images --max-usd 0.5
   #   -> open assets/src/*.png with vision: clean object, full object visible, no cast shadow, no text
   python3 $S/scripts/gen3d.py assets/jobs-<slug>.json --stage meshes --max-usd <n x 0.5 + 25%>
   bash $S/scripts/optimize.sh <slug> --tex 2048 --q 88        # assets/raw -> public/models/<slug>/
   ```
   `gen3d.py` keeps a resumable ledger (`assets/ledger3d.json`), refuses to spend without `--max-usd`, and adds
   Dioramas' white-plate suffix to every plate prompt (`raw: true` skips it). `edit_from: [id]` turns a plate into
   an i2i edit of an earlier plate, for a matched set.
4. **Build the page.** Start from `examples/<slug>/main.js`, which already has the boot sequence (loader → load +
   `normalize` → `compile` → start → intro). Then:
   - write a camera state per `[data-cam]` section;
   - add the press-hold interaction and the cursor-driven key light;
   - read `docs/ENGINE.md` (the core API) and one example close to the brief (e.g. `examples/lithos/` for
     press-to-crack, `examples/koi/` for water, `examples/sucre/` for physics);
   - don't edit `src/core/`; copy a function into the page folder instead.
5. **Build + shoot + review:**
   ```bash
   npx vite build && node $S/scripts/shoot.mjs dist "examples/<slug>/" qa --stops 0,0.25,0.5,0.75,1
   node $S/scripts/shoot.mjs dist "examples/<slug>/" qa --mobile
   ```
   This box has no GPU. `shoot.mjs` uses SwiftShader software WebGL and the page's `?lite` QA mode (AO, SMAA and
   grain off, low DPR). Pixels and composition are right; fps and post effects are not. Judge the final look and
   60 fps on a real GPU or the user's phone, from the deployed URL.
6. **Review like an art director.** Use Dioramas' 11-point quality bar, condensed below. Iterate until every
   answer is yes, then deploy `dist/` (Vercel / Netlify / any static host). Credit "Dioramas" in the footer if
   any CC BY example asset is reused.

## Quality bar (from Dioramas docs/ENGINE.md, condensed)
1. **Hero:** would it stop a scroll on Awwwards? Is the hero frame a printable poster?
2. **Lighting:** a motivated key plus rim/fill, real shadows and AO contact. Never flat, grey or "default three.js".
3. **Materials:** the PBR maps are used and an environment map is present; no blown whites, no plastic look.
4. **Composition:** the type and the 3D are designed together, with clear hierarchy and generous space.
5. **Signature interaction:** discoverable within 3 s (hint UI), spectacular in a still, with a touch equivalent.
6. **Scroll:** every section has a distinct camera state, with eased transitions, never jumpy.
7. **Page:** a complete landing page (nav, hero, ≥4 sections of real copy, CTA, footer), no lorem ipsum.
8. **Type:** a Google Fonts pairing unique to this site, with fluid sizes.
9. **Load:** a loader that fits the world, then an intro animation, and `renderer.compile()` before start.
10. **Mobile:** holds at 390×844 with no horizontal scroll.
11. **Health:** no console errors; 60 fps on a desktop GPU.

## Models and cost (live Replicate prices, read 2026-10-03; all IDs and input schemas checked against the API)
| Step | Default | Price | Notes |
|---|---|---|---|
| Plate (object on white) | `google/nano-banana-pro` 2K | $0.15 | `flux-2-pro` ~$0.06 is cheaper; `edit_from` makes matched sets |
| Image → 3D | `tencent/hunyuan-3d-3.1` (official), `enable_pbr: true` | **$0.50 / model** | default 500k faces, we ask for 200k; example run 145 s |
| Image → 3D, alt | `hyper3d/rodin` Gen-2 (official) | $0.40 / output | up to 5 images, PBR, Quad or Raw mesh |
| Cheap preview | `firtoz/trellis` (community) | ~$0.03 | lower fidelity; needs a pinned version hash |

Typical page: 3 hero objects = 3 plates + 3 meshes ≈ **$1.95**, plus rerolls. Dioramas' own number was about
$1.20 per Meshy model on fal; their 65-model collection cost about $90.

## Common Pitfalls
1. **Don't clone the whole repo.** It ships 310 MB of GLBs in plain git; `new_diorama.sh` sparse-checkouts without
   them. On this 2 GB-RAM box a full clone plus build is slow for no benefit.
2. **`optimize.mjs` refuses already-compressed GLBs** ("Please install extension dependency meshopt.decoder"). Use
   our `optimize-any.mjs`, which registers the decoder.
3. **Object covers the copy** when the camera centres it. The template shifts the projection
   (`camera.setViewOffset`) per section with `side`/`lift`, away from the copy column. A smoke test caught this:
   the macaron sat on top of "Made to be looked at." Note the sign: a +y view-offset moves the object UP. Pull
   the camera back on a centred CTA so the object and the copy both fit. Re-check every scroll stop by eye after
   any camera edit.
4. **`worldNav()` is gallery-only.** It looks up the slug in `src/core/worlds.js`; on a standalone site, gate it
   (`?gallery`) or the page throws.
5. **Engine rules from Dioramas' build lessons:**
   - r186 env strength = `scene.environmentIntensity`, not `material.envMapIntensity`;
   - glass needs a `scene.background` or a backdrop;
   - give spot and directional lights a `.target` added to the scene;
   - keep volumetric density at 0.02–0.05;
   - audio only after a user gesture, with a mute toggle.
6. **No GPU here.** Headless shots run on SwiftShader at about one frame per second with the full post stack. A
   full-quality screenshot timed out at 30 s, so `shoot.mjs` defaults to `?lite`. Never report fps from this box.
7. **Generated meshes are single textured meshes at arbitrary scale facing +Z.** Always `normalize()`. Look at the
   plate before paying $0.50 for its mesh: a cast shadow or a cropped edge becomes geometry.
8. **Licences:** engine code is MIT (keep the notice). The example models and images are CC BY 4.0, so credit
   "Dioramas (github.com/blendi-remade/dioramas)" if any are reused. GSAP is under its no-charge standard licence.

## Verification Checklist
- [ ] brief approved before spend; `gen3d.py --dry-run` estimate shown
- [ ] every plate looked at before its mesh was generated
- [ ] `optimize.sh`: page total ≤ ~45 MB, ≤ 1.6M triangles on screen
- [ ] `vite build` clean; `shoot.mjs` → `SHOOT: OK` on desktop and `--mobile`
- [ ] shots checked by eye against the quality bar: object never on top of the copy, the light reads, type legible
- [ ] interaction tested (press-hold) and the touch hint present on mobile
- [ ] deployed URL checked on a real GPU or phone for look and fps

## Files
- `scripts/new_diorama.sh`: pinned sparse clone + page scaffold
- `scripts/gen3d.py`: Replicate plates → GLBs, resumable, spend cap
- `scripts/optimize.sh` + `templates/optimize-any.mjs`: web GLBs
- `scripts/shoot.mjs`: headless QA shots
- `scripts/smoke_test.sh`: free end-to-end test
- `templates/page/`: `index.html`, `main.js`, `style.css`
- `templates/jobs.json`, `templates/BRIEF.md`
