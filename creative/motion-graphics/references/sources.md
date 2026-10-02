# Sources and further reading

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
