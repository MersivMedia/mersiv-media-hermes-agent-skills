---
name: browser-arcade-games
description: Build, test, and ship small canvas games for PC and phone.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [game, canvas, pixel-art, mobile, touch, vercel, arcade]
    category: web-development
    related_skills: [github-repo-management, pixel-art, dogfood]
---

# Browser Arcade Games Skill

Builds small single-page arcade clones (Pac-Man, Snake, Breakout-style) as plain
HTML/CSS/JS on a `<canvas>`. No build step and no dependencies. Covers pixel
sprites drawn in code, desktop and mobile controls, a headless test in desktop
and phone modes, then a private GitHub repo plus a Vercel deploy. It does not
cover game engines (Phaser, Unity) or multiplayer.

## When to Use

- The user asks for a "quick web game", a reskinned arcade clone, or a gift or
  joke game with custom text, a prize screen, or characters
- It has to work on both PC and phone
- The deliverable is a live link

## Prerequisites

- Node, for maze/level sanity scripts
- Headless Chromium plus a venv with `websocket-client`, used by `scripts/cdp_game_test.py`
- `gh` authed and a Vercel token. Deploy mechanics live in memory and in the
  `AI Tool Deployment Troubleshooting & Recovery` skill

## How to Run

1. Scaffold 3 files: `index.html`, `style.css`, `game.js`, plus a README and a `.gitignore` for `.test/shots/`.
2. Copy the user's title, rules, and win text **verbatim**. They check exact wording.
   Any copy you add yourself (start card, game-over card, HUD, `aria-label`,
   `<title>`, README) must **not reveal the prize or surprise**. Keep it generic,
   e.g. "Ready to win a special prize?". The user caught "Ready to earn your
   date?" on the start screen spoiling the reveal. Grep for prize words
   before shipping.
3. Build a **preview link** in from the start: `?preview=prize` hides the start
   overlay and calls `showWin()` after boot. The user will want to see the
   end screen without beating the level. Send it with the live link, and warn
   that anyone with that URL can skip ahead, so share only the plain URL.
4. Test locally with `file://` using the script. You don't need an HTTP server,
   because backgrounded servers can hit approval prompts.
5. Look at screenshots with vision (gameplay, win screen, phone layout, and a
   zoomed crop of the sprites).
6. `git init` → `gh repo create <Org>/<name> --private --source . --push` (repos are
   private when the user says private). Then deploy with Vercel in the background
   and clear ssoProtection. Keep git push and `vercel deploy` as **separate**
   commands, because one giant chained one-liner can get rejected by the
   terminal's command parser. For redeploys: `git fetch` → commit → push, then
   run `vercel deploy --prod --yes` in the background with notify.
7. Run the same test script again against the live URL before sending the link.
   Also load `/?preview=prize` and check that the win dialog is visible and the
   start overlay has no prize words
   (`!overlay.innerText.toLowerCase().includes('<prize word>')`).

### Preview link snippet (end of the boot IIFE, after `fit()` and the rAF start)

```js
if (new URLSearchParams(location.search).get('preview') === 'prize') {
  ui.start.classList.add('hidden');
  showWin();
}
```

## Quick Reference

```bash
~/.venvs/cdp/bin/python scripts/cdp_game_test.py "file://$PWD/index.html" .test/shots
~/.venvs/cdp/bin/python scripts/cdp_game_test.py "https://<name>.vercel.app" .test/live
# spoiler check + preview link, against the live site (exit 1 on failure)
~/.venvs/cdp/bin/python scripts/check_preview.py "https://<name>.vercel.app" "<prize>,<words>" .test/preview.png
# measure a synthesized SFX's pitch, HEAD vs working copy (for "make it lower/higher" asks)
~/.venvs/cdp/bin/python scripts/render_sfx_pitch.py <game_dir> prank.js 'function noise(' 'const prankSfx' 'evilLaugh(0, 7)'
# per-syllable legibility: onset "h" level/noisiness, echo smear, f0 (for "I can't hear the HA")
~/.venvs/cdp/bin/python scripts/sfx_syllable_check.py .test/shots/sfx-new.wav 0.6 0.25
# build/validate extra mazes (shared middle band, mirrored halves); --json writes them when all pass
python3 scripts/maze_workshop.py --json .test/mazes.json
# gameplay rules via game internals: power-up covers boxed/released enemies, lives HUD, out-of-lives ending
~/.venvs/cdp/bin/python scripts/gameplay_rules_test.py "file://$PWD/index.html" .test/shots --lives-ending yes
```
The script expects a `window.__game` test hook (see Procedure). Edit the
key/touch steps for the specific game.

## Procedure

### Architecture
- A tile grid with a fixed logical size (e.g. 16px tiles). Render at native
  resolution and scale the canvas with CSS (`image-rendering: pixelated`) through
  a `fit()` function that reserves room for the joystick under the canvas.
- Pixel sprites are string arrays plus a palette map, drawn with `fillRect(1x1)`.
  Mirror half-art for symmetric characters and stamp overlays (heart, paws) on
  top. A 24x26 bear holding a heart and a 14x14 squirrel with a 2-frame run cycle
  both read well.
- Walls go to an offscreen canvas once. Collectibles and actors redraw every frame.
- A state machine: `start → ready → play → dying → (lost | over) → win`. The
  `lost` state is a paused "Ouch! N lives left" card with TRY AGAIN, so the
  player gets a beat after each death and there's a place to hang extra buttons.
- Chiptune SFX use WebAudio oscillators. Add a mute toggle. **iPhone audio needs
  two things from day one**, or the user will hear nothing on their phone even with
  ♪ ON: (1) unlock/resume the AudioContext on `touchend`/`pointerup`/`click`/`keydown`,
  not just `pointerdown`, because a joystick drag doesn't count as a gesture; (2) move
  the page to the playback audio session (`navigator.audioSession.type = 'playback'`,
  plus a looping silent `<audio>` fallback for older iOS) so the ring/silent switch
  doesn't mute it. Recipe + test: `references/mobile-web-audio.md`.
- **HUD legibility:** show lives as a labeled row, `LIVES:` followed by one glowing
  pixel heart (or the game's collectible icon) per life, with lost lives
  faded gray (opacity 0.18, grayscale). The user found bare `●●●` dots unclear.
  Build the heart in CSS from stacked `linear-gradient` blocks on a `--p` pixel
  unit (the first gradient layer paints on top, so the highlight goes first). Put
  an `aria-label` on the container.
- **Power-ups apply to every enemy on the board for the whole timer**, including
  ones still in the spawn box, walking out of it, or respawning after being eaten.
  Players read both arcade-accurate exceptions as bugs (the user reported each one
  separately). Four code sites must agree: `references/grid-maze-engine.md`.
- Grid-maze movement engine, ghost AI, and tunnel wrapping: `references/grid-maze-engine.md`.
- Joke-button/prank sequences, breaking-heart and dissolve particle FX, win-screen
  heart bursts, the synthesized evil laugh, and how to verify audio you can't hear:
  `references/prank-fx-and-audio.md`.
- **Multiple levels + finale:** `references/multi-level-progression.md` covers
  the MAZES table sharing one middle band, per-level themes/copy tables, the
  distinct `loadLevel` / `resetGame` / `restartLevel` / `goToLevel` functions,
  per-level win screens with a "LEVEL N" button, and the heart-explosion finale.
  New mazes: build and validate with `scripts/maze_workshop.py` (mirrored halves,
  BFS reachability, dead ends) before touching the browser.
- **Share assets (tab icon, home-screen icon, link-preview card + caption):** ship
  them before the user shares the link. Render from the game's real sprites with
  `templates/make_share_assets.py` (copy to `.test/`, adapt markers/layout). Tags,
  sizes, the JPEG choice, the fillStyle/font pitfalls, and the crawler check are in
  `references/share-assets-and-link-preview.md`. Keep the prize character out of the preview.
- **Renaming characters:** names often live only in the start card and README
  (sprites carry colors, not names). Keep each name on the same color/AI slot,
  grep old names across html/js/README afterwards, and give the user a
  name→color→behavior table in the plan.
- **Default difficulty for gift games:** losing all lives on level 2+ restarts
  *that* level with fresh lives, never level 1. Only deliberate misbehavior
  (a 2nd joke-button press) sends the player back to the start. The user wants
  the recipient to reach the ending.

### Working with this user on games
- They iterate live, often mid-build: controls swapped, button placement moved,
  a sound "a bit lower". Absorb each correction into the current pass rather
  than restarting, and restate what changed in one line.
- They asked to be told about progress. Post a one-sentence update between
  phases (engine written → tests passing → pushed → live) and name any blocker right away.
- Each feature reply ends with: what's live, how it was tested (real input vs
  hook vs emulated), and what couldn't be verified (audio, real thumb, real GPU).
- For **creative/visual choices** (which character becomes the icon, preview-image
  layout, caption wording), they may ask "tell me what you're going to use before you
  begin". Send a concrete plan with one alternative per choice, change nothing, and
  wait for "go ahead". Afterwards, list any deviations from the approved plan.
- "Make the repo private": check first with `gh repo view --json visibility`. It
  may already be private. A private repo doesn't break Vercel (the Git link uses the
  owner's credential). The live site stays public unless Vercel auth is added.

### Controls (PC and phone, both required)
- Keys: arrows plus WASD. Enter/Space starts. Call `preventDefault` so the page doesn't scroll.
- Phone: a **thumb joystick** under the canvas, NOT a D-pad. The user rejected
  arrow buttons as harder to control. Use a ~132px round base with a ~58px knob,
  pointer events plus setPointerCapture, a 40px knob travel clamp, and a 12px
  dead zone. The dominant axis steers, with 1.25x hysteresis before switching
  axis so diagonal thumbs don't flicker. The knob springs back on release, and
  the first press also starts the game. Also support swipes on the play area. Keep steering on touchmove by resetting the origin
  after each 16px step.
- Show the joystick only when `@media (hover: none) and (pointer: coarse)` matches,
  **or** when the first touch event adds `body.touch`. Update the start-card
  hint text ("Phone: drag the joystick with your thumb") whenever controls change.
- Lock the page: `touch-action: none` on the stage and joystick, a non-passive
  touchmove preventDefault, `user-scalable=no`, `overscroll-behavior: none`, and
  safe-area padding.
- Aim for the whole game (title, rules, HUD, canvas, joystick) to fit a 390x844
  viewport without scrolling. `fit()` reads the joystick's height to reserve room.
- Test the joystick with CDP `Input.dispatchTouchEvent` (touchStart on the knob
  center, several touchMoves 50px+ in one axis, touchEnd) and assert the
  collectible count drops.

### Verification hook
Expose `window.__game = { state, hearts/score, eatAll(), steer(dir) }` so the
harness can reach the win screen without playing the whole level. Either strip
it before release or tell the user it is there, because it lets anyone skip to
the prize from the console.

For gameplay-rule tests (power-ups, collisions, lives), you don't need extra hooks.
Top-level `let`/`const`/functions in a classic (non-module) `<script>` are
reachable from CDP `Runtime.evaluate`, so the test can call `frighten()`, set
`ghosts[i].release = 0`, teleport `player.x/y` onto an enemy and call
`checkCollisions()`, or set `lives = 1`. Report these as "state-driven" tests,
not real play.

## Pitfalls

- **Add-on gags/prank sequences** (joke buttons, popups, end-of-game fakeouts):
  put them in their own file (e.g. `prank.js`) with an explicit state machine,
  plus a `frozen` flag in the core loop that pauses update() and input. Place
  joke buttons where the user specifies (here: under TRY AGAIN after a lost
  life, not on the title screen). Ask/assume a recoverable path exists: the
  user's "YES" ending needed a TRY AGAIN button that resets the game *completely*
  (start screen, full score/lives/collectibles, joke button re-armed to stage 1),
  and only the "NO"/GAME OVER ending is refresh-only. Hint text like "refresh
  the page" was rejected in favor of a real button. Test every state transition
  (including the loop back to stage 1) in the headless script and take screenshots
  at each stage. Particle effects spawned
  inside a text box cover the message: spawn them from the box edges instead.
- **"Make the sound lower" vs "I can't hear the HA":** the first is a pitch
  knob, the second is articulation and needs a better source model (a formant
  bank shared by voice and breath noise). See `references/prank-fx-and-audio.md`
  and measure with `scripts/sfx_syllable_check.py` before redeploying.
- Add a `.vercelignore` for `.test/` and keep screenshot dirs in `.gitignore`
  from the first commit. Otherwise test PNGs end up in the repo and test
  scripts get served publicly.

- **Boot order:** build derived maps (BFS distance to home, etc.) only AFTER the
  grid is initialized. A cold boot threw `Cannot read properties of undefined`
  because `buildHomeDist()` ran before `resetGame()`.
- **`@media (hover:none), (pointer:coarse)` uses OR.** Headless desktop Chrome
  matched it and showed the phone controls on PC. Use `and`, with the `body.touch` fallback.
- **Rename sweeps:** when swapping a control (D-pad → joystick), also update
  `fit()`, the touchmove lock selector, the hint text, the README, and every test
  script's element IDs. Edit test files with a Python `str.replace`, because sed
  keeps missing on escaped quotes inside Python strings.
- Run a maze sanity script before opening a browser: equal row lengths, every
  collectible reachable by BFS from the player start, no dead ends, and the
  ghost-house exit reachable.
- The player moving/eating in a test does not prove the win path. Only the win
  screen being visible proves it.
- Win path verified via the hook ≠ beatable by a human. When reporting, say which
  paths were exercised by real input and which by the hook, and say that phone
  tests were emulated.
- **Spoilers in supporting copy.** The title, rules, and "special prize" wording
  are the user's. Anything you write around them (start-card tagline, alt text,
  README feature list) must not name the reward. Only the win screen may reveal
  it. Check the README too, since the user may share the repo.
- Hand over **two links**: the plain play URL (to share) and the
  `?preview=prize` URL (for the user only). Offer to strip the preview param
  and the console hook before the real share.
- **Multi-level games: ship shortcuts for every level.** The user asked for
  links to each level's start AND win screen: `?level=N`, `?win=N`,
  `?preview=finale`, with old links kept working. Give them as a list in the
  final reply.
- **`startGame()` must restart the current level, not the whole game**, once
  levels exist. Otherwise START on the level-2 card silently drops to level 1.
- When a test compares score after a restart, expect `levelStartScore`, not a
  `score` read a moment after START. Points accrue in the gap, and correct code
  showed up as FAIL.

## Verification

- The script prints no JS errors, `state` goes `start → play`, the collectible
  count drops on keyboard, joystick, and swipe input, idle play loses lives, and
  the win dialog becomes visible with the exact text.
- The joystick is `display:none` on desktop and `block` on emulated phone, and
  `scrollY` stays 0 after a swipe.
- The live URL returns 200 for `/` and `/game.js`, and the repo visibility is
  `PRIVATE` when requested.
- `/?preview=prize` shows the win dialog on first load, and the start overlay
  text contains no prize/reward words.
- Share assets return 200 with image content types, and a `facebookexternalhit`
  UA fetch of `/` shows og:title/description/image (absolute URL).
