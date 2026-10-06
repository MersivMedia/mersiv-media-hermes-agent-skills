# Source notes: "The $35K Motion-Website Playbook with Higgsfield + Claude Code"

Post: https://x.com/zeuuss_01/status/2067204840342630789 · @zeuuss_01 · 2026-06-17 · read 2026-10-03
Full text: 2067204840342630789.md · images: img/ (setup steps exist ONLY as screenshots, transcribed below)

## Claimed pipeline (from the article, unverified)
- Higgsfield "Motion Website Generator" skill (June 2026) + Higgsfield MCP (30+ generative models behind one
  connector) + "Vibe Motion" (code-generating motion-graphics engine).
- Input: brand kit (logo, colors, fonts, references) + short business description.
- Claude plans sections -> generates motion clips via MCP -> extracts every frame -> writes HTML/CSS/JS ->
  assembles a scroll-driven site.
- Systems coordinated: GSAP ScrollTrigger, Lenis smooth-scroll, frame extraction, asset optimisation, layout, copy.
- "Six cinematic effects with zero extra config": film grain, particles, vignette, glass cards, color tints, scroll pacing.
- Iterate in the same chat ("Tighten the hero copy", "Swap section 3 for a pricing block", "Slow the scroll pacing"),
  feed screenshots for precise fixes.
- Deploy: plain HTML/CSS/JS, no proprietary runtime: Netlify Drop (drag folder), Vercel (import & deploy),
  GitHub Pages (push & enable).
- Business angle: 3 niche demo sites first (SaaS, e-commerce, local service); reskin one codebase per client;
  targets Shopify/Amazon sellers, Kickstarter campaigns, local SMBs. Pricing figures are the author's ($6k-35k
  boutique, $2.5k-10k standard, avg $5,280, "up to $38,400/month") — unverified marketing numbers.

## Setup screenshots (transcribed)
### Claude desktop / web
1. Create a Higgsfield account at higgsfield.ai (new accounts ship with free credits; MCP runs on those credits).
2. Settings -> Connectors -> Add custom connector, name it Higgsfield, URL `https://mcp.higgsfield.ai/mcp`.
3. Connect, sign in (OAuth, credentials stay on Higgsfield's side), set read/write to "Always Allow".
### Claude Code
1. `claude mcp add --transport http --scope user higgsfield https://mcp.higgsfield.ai/mcp`
2. OAuth opens on first use; confirm with `claude mcp list` or `/mcp` -> higgsfield connected.
### Build
1. Drop Higgsfield's skill markdown into the workspace (defines triggers, inputs, step-by-step pipeline).
   "Use Opus 4.8 / Fable 5 for the cleanest builds."
2. Hand it a brand kit + brief. Claude plans sections, generates clips via MCP, assembles the scroll site.
3. Iterate in the same chat with plain-language follow-ups + screenshots.
4. Deploy: Netlify Drop / Vercel / GitHub Pages.

## Not in the post
No skill file, repo, prompt text or code is published. The Higgsfield skill markdown itself is not linked.
Our skill rebuilds the pipeline from first principles, with Replicate instead of Higgsfield (user decision 2026-10-03).
