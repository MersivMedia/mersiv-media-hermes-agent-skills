# Sources and further reading

## Source 2 (v2.0.0): Raphaël Aubry / Howseen

"i made 10+ motion videos with opus 5.5 in 3 days. here's the whole pipeline (open source)", X Article,
https://x.com/raphaelaubryy/status/2104502744010629269 (read via fxtwitter 2026-10-02), and its repo
https://github.com/howseen-ai/claude-motion-design (MIT, Copyright 2026 Howseen AI (Raphaël Aubry);
read at commit 3d90d349ef3fdde9b7e89de4df4a2159c9e8697f, 2026-10-02).

Taken and adapted (rewritten for this box: Node renderer, no imageio_ffmpeg, no Mac paths):
- 180° shutter subframes, cut-aware; draft mode; per-beat stills; frame-count check; BT.709 TV-range encode;
  pops + one-frame-flash detector; loop check in position AND velocity; WEBGL=1 SwiftShader flags;
  deterministic Chromium flags; adaptive subframes; poster in frame 0; parallel time chunks; render lock
  -> render.mjs, qc.py, poster0.sh, chunks.sh
- Drop by band energy, 20 ms zoom, song offset; SFX on measured peak; two-pass loudnorm; VO ducking -> drop.py, mix.py
- Camera in log zoom with beat/bar punches; floods clearing the farthest corner; masked word rise; exact-end easings;
  spring presets (k/d); loop spring tails; micro drift -> lib/motion.js
- Director's brief, facts.md, "Example data" labels, true captions, anti-AI-look rules, seekable third-party libs,
  separate read-only critic, fresh-agent restatement test, preview HUD -> BRIEF.md, facts.md, STUDIO_RULES.md, index.html
- Mixkit SFX/music crawl, svgl logos (+ simple-icons fallback), picsum (Unsplash) photos -> assets.py
- Remake mode -> separate skill `motion-remake` (core.js, analyse/stub/render/sync/qa ported to Node + Linux fonts,
  brand made configurable via project.json; remake_audio.py added).

Not taken: Howseen brand palette/fonts/file library, Mac/Claude Code sandbox specifics, 21st.dev MCP client
(needs a personal key, 2 free retrievals/day), YouTube meme downloading (this box's IP is blocked by YouTube).
The article's numbers (render times, "5 versions", views) are the author's own and unverified here.

Asset sources checked from this box 2026-10-02 (HTTP 200): mixkit.co SFX tag pages + assets.mixkit.co SFX previews,
mixkit.co music genre pages, api.svgl.app, cdn.jsdelivr.net simple-icons.

## Source 1 (v1.0.0): @0xMovez
Primary source for this skill: @0xMovez (Movez), "How to build motion design studio with Opus 5.5 (Full-course)",
X Article published 2026-09-27, https://x.com/0xmovez/status/2104216919033192746 (article id 2104196832637210624).
Read via the fxtwitter API on 2026-10-02. The article's claims about other creators' runs (view counts, hours,
model-call counts, "one-shot") are second-hand and unverified here.

## Repos the article recommends

- Music video, subagent pattern (ANIMATION_GUIDE.md, STORYBOARD.md, src/ch/): https://github.com/JohnHeibel/PDoomVideo
- Starter: https://github.com/JohnHeibel/ClaudeAnimationBase
- Node canvas, hand-drawn rigs + synthesized sound (Claude plugin): https://github.com/buildwithhanif/claude-animation-skill
- Framework, HTML + GSAP: https://github.com/heygen-com/hyperframes
- Framework, React: https://www.remotion.dev/docs/ai/skills
- Long form: https://github.com/WinterArc21/Battle-of-Austerlitz-Film
- Prompt library: https://github.com/guanmo-ai/awesome-ai-motion
- Dataset of Opus 5.5 videos ("brief contagion" analysis): https://github.com/athemeroy/awesome-opus-5-5-videos

## Route B: frameworks instead of the raw seek(t) engine

The article reports Opus picks the zero-dependency route (one index.html + seek(t) + headless capture + ffmpeg)
even when frameworks are installed; ask for a framework explicitly if wanted.

```
# Remotion (React): best for series, templates, data-driven videos
npx create-video@latest launch-film && cd launch-film
npx skills add remotion-dev/skills
npx remotion studio                 # live timeline preview
npx remotion render Main out/launch.mp4

# HyperFrames (HTML + GSAP): best when you think in web pages
npx hyperframes init my-video && cd my-video
npx hyperframes skills update
npx hyperframes preview && npx hyperframes render
```

Remotion has its own licence terms for companies; check before commercial client work.

## Embedded example posts (tweet ids, for looking up the originals)

- One-liner résumé reel, max effort: 2103315922098470926; same prompt on xhigh: 2103875898349088830
- TypingMind brand reel (Tony Dinh): 2103703135902740699; Pocketsflow talking mascot (achxvi): 2103918792845963545
- Reference-based TikTok piece (Pleometric): 2102572941699354900; Rexan Wong analysis: 2103707054108299437
- UI morph XML spec (@twoclipping): 2103273003555402193; MakerMap (@verbove): 2103483957266268381
- Cartoon video editor (NFT_Chen): 2102681172367323300
- Steve Jobs film, Node-synthesized score at 120 BPM (@oozn): 2103482545111232946; "Small print" (Vox): 2102531681450119426
- Claude Pop music video + 9,500-char brief (Donald): 2102801274173587569, 2102801469976248500; PC-98 re-run: 2103082510607610023
- Launch-day piece with cleanup rounds: 2102436464323661880; watercolor short, 163 calls: 2103465246014746943
- 38-second product film offered as a paid service: 2104014659615392078
