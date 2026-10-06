# Faceless-video production notes (French space channel, episodes 1–2)

These notes sit next to the cut-sync rules because they come up in the same production pass. The main
channel style guide is `viral-youtube-video/references/fr-space-style.md`. It is user-owned, so these notes
were written here instead.

## Heavy renders go to a rented CPU pod (user's standing rule)
- The user's words, after a 2-hour local estimate: "You should always rent the fast cpu server for this
  stuff". Don't ask first.
- Pod: RunPod `cpu3c-16-32` (~$0.48/hr). One script does everything: create the pod, ship inputs, render,
  pull outputs back, terminate via an exit `trap`.
- Worked example: `<episode>/edit/pod_finish.sh "<id>:<from>:<to> ..."`.
- Cost reality: the render itself took 24–35 s. Boot, apt and the chrome copy dominate, so a batch billed
  $0.05–0.63. Estimate per pod session, and batch every re-render into one session.
- After teardown, report the real balance difference.

## Script length at the narrator's real pace
- A first draft written "by feel" came out at 1,229 words (6.6 min) against the 1,750-word target for a
  ~186 wpm voice.
- Draft long from the start: `script_check.py --lang fr --target 1750 --wpm 186`.
- Fix loop-gap failures with a real mini-question inside a long explanation ("how was it measured?",
  "why iron?"), not with filler.

## Fact pass after the checker passes
- Compare every sentence with `facts.md`, and soften wording that claims more than the source. Examples
  from episode 2:
  - "presque la Lune" → "une demi-Lune"
  - "arrêtée" → "interrompue"
  - certainty → "peut"
- Add any new figure to `facts.md` with its source before the voiceover.

## Review doc for an owner who doesn't read the narration language
- Script: `~/.hermes/data/yt-arbitrage/fr-space/make_review.py <ep_dir> "<FR title>" "<EN title>"`.
- Inputs:
  - `en.json`: one faithful English translation per voiced paragraph, in order. The script asserts the
    counts match.
  - `q_en.json` (optional): loop id → English question.
- Output: French paragraph, English in italics, then the Visual / Question / Answered lines.
- Upload with md2gdoc, then verify by exporting the Doc as text/plain.

## Thumbnails in code, $0
- Build them with Pillow from the episode's own images, using Inter Black with a stroke.
- Render a stacked sheet plus a 320x180 phone preview, and run a vision critique on both.
- Failures caught on episode 1:
  - text over the probe;
  - an invented red "warning light";
  - the subject too small at phone size;
  - an overclaiming headline.
- Iterate until clean, then upload 3 for Test & Compare.

## Parallel research for a slate of episodes
- Use 3 leaf subagents, one or two episodes each.
- Each subagent writes into its episode folder:
  - `facts.md`: claim, value, status, source;
  - `archive.md`: Commons licence plus credit line;
  - `packaging.md` and `outline.md` in French, with English glosses;
  - `sources/` and `refs/`.
- Check their output yourself before reporting:
  - Grep the saved sources for the key claims.
  - Check refs open and aren't tiny.
  - Recompute any cost estimate. One helper assumed 14 render-hours, which inflated E6 about 2×.
  - Fetch key images missing from Commons straight from the agency (ESO, ESA) and confirm the credit line
    on its page.
