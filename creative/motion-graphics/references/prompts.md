# Prompt and brief templates

Source: @0xMovez, "How to build motion design studio with Opus 5.5 (Full-course)", X Article, 2026-09-27
(https://x.com/0xmovez/status/2104216919033192746). Templates are lightly adapted for this skill's file
names (render.mjs, music.mjs, qc.sh, lib/motion.js). Fill every [BRACKET].

Pick the lightest level that fits the job:

| Level | Use for | Template |
|---|---|---|
| L1 one-liner | test the engine, a quick reel | §1 |
| L2 brand reel | a product launch / ad from a URL | §2 |
| L3 reference + spec | a specific look, a UI morph loop | §3, §4 |
| L4 director's brief | long films, music videos, multi-session runs | §5 |

## 1. One-liner showreel (tests the engine, never the idea)

```
make a dynamic 15-second motion graphics video that shows what an
incredible motion designer you are, like it's your showreel for a résumé.
go all out.
```

Why it works: "showreel" is a genre with known rules (fast cuts, new technique each shot, best first); making
the model the subject means no product content to get wrong; 15 s fits 6-8 shots in one pass.
Weakness: "brief contagion". Hundreds of people ran this exact prompt and the reels rhyme. Variants:

```
# Longer, with a sound bar
make a dynamic 16:9, 60-second motion graphics showreel that shows your real creative limits.
S-tier sound design, no generic synth pads. Compose an original score and sync every cut to it.

# Anti-slop guardrail
... Avoid frames and text in the corners, the usual giveaways of AI-made video.

# Story instead of techniques
use your showreel energy, but tell a story: the history of [TOPIC] from [START] to today,
surprise me with the storyboard. 45 seconds, vertical 9:16.

# Agency persona
make a 30-second showreel as if you were a niche branding studio for [AUDIENCE].
Create every graphic from scratch. One accent color. Every shot is a different technique.
```

## 2. Brand reel from a URL

```
Make a dynamic 20-second motion graphics video for [PRODUCT] ([URL]), with the energy
of a motion designer's showreel. Go all out.

Assets
- Visit the site. Use real screenshots (Playwright), the real logo, real colors and fonts.
  Save everything to ./assets and list what you found before you animate.
- Never redraw the product UI from imagination. Crop and animate the real thing.

Story (one beat each, 2 to 4 seconds)
1. Hook: the problem in 5 words of huge kinetic type.
2. The product appears, the UI assembles itself piece by piece.
3. Three features, each as a UI moment with a cursor doing a real action.
4. One number that proves it works: [METRIC].
5. Logo lockup + [CTA].

Sound
- Original music, 120 BPM, synthesized in code. UI clicks and whooshes on the beat.

Format: 1080x1920 (9:16) first, then 1:1 and 16:9 from the same timeline.
Before the full render, show me a contact sheet of one frame per beat.
```

Keep one working folder per brand: the second film reuses the renderer, audio and export pipeline.
Voice/mascot upgrade: "the ElevenLabs key is ELEVENLABS_API_KEY in .env" (never paste a real key in a prompt).

## 3. Reference first (name a look, feed a frame)

```
Reference: ./refs/launch.mp4 (and ./refs/frames/*.png)

1. Extract one frame every 0.5s with ffmpeg. Study them.
2. Write ./docs/style_guide.md: palette (hex), type (family, weight, tracking),
   shot lengths, transition types, camera moves, texture/grain, how text enters and exits.
3. Write ./docs/shotlist.md for a [DURATION]s video about [SUBJECT] in THAT style.
   Take the grammar of the reference, never its content, logos or characters.
4. Show me both files. Wait for my OK before any code.
```

- A frame: say what to take (palette, type, grain) and what not to take (subject).
- A library: a folder of the user's own images/past work; write style_guide.md from it first. Nobody else can copy it.
- Specify the look and constraints, not the library, unless a framework is needed for reuse.

## 4. State-list spec (UI morph loop, "one shape, never cut")

```
<inputs>
Ask me for: my product + URL, 8 to 12 UI states that tell its story, the real data shown in
each state, brand colors + fonts + one accent, a royalty-free track near 120 BPM, formats.
</inputs>

<direction>
Product-film UI motion. One container never cuts: every state is the same element changing
size, radius and fill while its content swaps behind a short blur. A cursor drives every change.
Warm neutral canvas, one accent. Springs with at most a tiny overshoot.
Banned: bouncy easing, glows, gradients on UI chrome, particle bursts, dead time.
</direction>

<structure>
120 BPM, 8 bars, something happens on every beat.
logo → CTA button → email field (typed) → loader → success check → dashboard card
→ chart draws itself → tooltip on hover → ⌘K palette → toast → logo.
</structure>

<build>
1. One HTML file, one canvas, window.seek(t). No CSS transitions, no timers, no carried state.
2. Closed-form springs (lib/motion.js). A value with many targets = track(): one spring per change.
3. Text inside a morphing container enters after the morph starts, leaves before the next one (swapAlpha).
4. Tab indicators: leading and trailing edges on different springs so they stretch (indicator).
5. Beat grid from the track (beats.py). Start on a downbeat. UI sounds on measured peaks.
6. Render at 60 fps, 4 subframes per frame, blended for motion blur (render.mjs --sub 4).
</build>

<gotchas>
Never use will-change on anything the camera scales (blurry text).
The last frame must equal the first, cursor position and velocity included (loopT).
</gotchas>

<start>
Ask for the inputs, then show me the state list on the beat grid before writing code.
</start>
```

## 5. Director's brief (overnight / long-form)

The viral long pieces used 9,500 to 19,000-character briefs. They don't describe a video, they hire a crew.

```
You are the director, animator, sound designer and render engineer for a [DURATION] film
made in code. Treat this as a multi-session production. Don't rush to a final render.

## The film in one line
[LOGLINE. What the viewer should feel at the end.]

## References and inputs
- ./refs/ : [video / frames / image library]. Take the grammar, never the content.
- ./audio/track.wav : use it unchanged. Measure beats with beats.py first.
- APIs in .env: [ELEVENLABS_API_KEY, REPLICATE_API_TOKEN, ...]. Budget: [$X]. Be economical.

## Look
[3-5 lines: palette, type, texture, camera language. Banned looks.]

## Character bible (if any)
[Proportions, palette sampled from a sheet, expressions, an identity lock that survives every style change.]

## Beat sheet
0:00-0:02  hook: [the single most striking image]
0:02-0:10  [act 1]
...        a new visual payoff every 3-5 seconds
[END]      the last frame sets up the first frame (loop)

## Text on screen
[When captions/lyrics go huge, when they sit like subtitles. Leave room for them in composition.]

## Workflow, with gates
1. Write docs/style_guide.md and docs/shotlist.md (every shot: frames, camera, text, SFX). Show the shot list.
2. Build stills for every shot. Contact sheet. Critique.
3. Animatic at 960x540 with placeholder audio. Fix pacing before polish.
4. Full animation, polish pass, sound pass, final render.
5. Split work across subagents per chapter. Write docs/ANIMATION_GUIDE.md first
   so every subagent codes in the same style; write docs/STORYBOARD.md after the first pass.

## Critique loop (every shot, at least 3 rounds)
Render 3-5 stills, score 1-10 on: hook, readability at 360px wide, motion, composition,
depth, sound sync, polish. Log scores + 3 biggest problems in docs/review_log.md. Fix. Repeat until all are 8+.

## Deliverables
out/final.mp4 · out/loop_check.mp4 · out/poster.png · out/contact.png · README.md
```

Generate-then-trace (from the 2.1M-view music video): a video model (Seedance) renders base shots for motion
and physics, then the code layer redraws everything on top so only the code-drawn look is visible. See the
`seedance-video` skill for the base-shot step; it is paid, so estimate and get sign-off first.

## 6. Critique pass (paste after every render)

```
Open out/contact.png, out/strip.png and out/phone.png and look at them properly.
Be a harsh motion director, not a proud author.

Score 1-10: hook in first 2s · readability at phone size · motion quality (springs,
no dead frames) · variety (new thing every 2-4s) · composition · brand accuracy · sound sync.

List the 3 biggest problems with timestamps. Hunt specifically for: text overlapping during
swaps, anything sliding instead of easing, corner labels and frame borders, centered-on-gradient
shots, blurry scaled text, a dead beat with nothing happening, a stutter at the loop seam.

Fix them, re-render only the affected seconds (render.mjs --from/--to), show the new contact sheet and new scores.
```

## 7. Spring refactor (one-pass upgrade of an existing film)

```
Replace every easing curve with closed-form springs from lib/motion.js. Tiny overshoot on UI, none on type.
Any value with more than one target uses track().
```
