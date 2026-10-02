# Prank sequences, particle FX, and synthesized voice SFX

Techniques from the gift-game build (Pac-Man clone with a joke-button
escalation). They apply to any gift/joke game with gag buttons, fake-out
endings, or celebratory screens.

## Escalating joke button (state machine)

The user's spec: a "Don't Press This Button" button. The first press fakes a
reset, the second press goes to a doom ending, and a YES/NO choice decides
whether the player can come back.

- Put it in `prank.js`, loaded after `game.js`, sharing globals. Add `let frozen = false` to the
  core and gate on it: `if (!frozen) update(dt)` in the rAF loop, plus early
  returns in the keydown, joystick, and continue handlers. Keep drawing while
  frozen so the maze stays visible behind popups.
- Prank states: `armed → resetting → armed2 → zoning → dissolving → doomed →
  asking → (friends | gameover)`. Expose `window.__prank = { state }` for tests
  and mirror the state to `body[data-prank]` for CSS.
- `armed` press: popup + breaking hearts + full `resetGame()` → back to the start
  overlay, with every `.nope` button's label changed to "... AGAIN" (restyled
  yellow). `armed2` press: second popup → dissolve → skull → delayed YES/NO.
- **Placement is a user decision.** The first build put the button under the
  title, and the user moved it to *below TRY AGAIN after losing the first life*.
  Use one `.btn.nope` class on every card that should carry it (the lost-life
  card and the game-over card) and bind all of them with `querySelectorAll`.
- **The endings, as the user finally specified them:**
  - NO → GAME OVER: no buttons, input frozen, only a page refresh restarts.
  - YES → "THE BOSS HAS DECIDED YOU CAN TRY TO PLAY AGAIN" plus a **TRY AGAIN button**
    (the user rejected "refresh the page" hint text). The button must do a
    **complete reset, identical to a fresh page load**: hide final/doom/friends/
    popup, clear the fx and cover canvases and the particle arrays, restore
    canvas visibility, hide the lost/over/win cards, `resetGame()`,
    `setState('start')`, show the start overlay, `frozen = false`, and re-arm
    the prank at stage 1 so the button label reverts. Do NOT jump straight into
    play, and do NOT mark the prank "spent". A first attempt did both, and the
    user corrected it to "reset the game completely".
- **Out of lives reuses the doom ending.** The user replaced the plain game-over card:
  on the last death, go straight to skull + evil laugh → "THE BOSS HAS FRIEND-ZONED YOU!
  DO YOU WANT TO BE FRIENDS?" → NO = GAME OVER, YES = "THE BOSS HAS DECIDED YOU CAN
  TRY AGAIN." plus the full-reset TRY AGAIN button. Implementation: core `gameOver()`
  calls `window.onOutOfLives()` if prank.js defined it (falling back to the old card),
  `dissolve(question, askDelay)` takes the question text, and a
  `doomPath` ('button' | 'lives') selects the YES text. There's no popup before
  it, so use a shorter askDelay (about 1.5 s vs 3 s). Guard re-entry while
  already dissolving/doomed/asking. Give `#friends` a `max-width: min(92vw, 560px)`
  so the longer question wraps on phones.
- Test the loop closes: after TRY AGAIN, assert start screen, score 0, full lives,
  full collectible count, label back to stage 1, then lose a life and press the
  button again and assert the first popup appears.

## Breaking pixel hearts that fall out of a popup

- Use a full-viewport fixed `<canvas id="fx">` with pointer-events none and a DPR-scaled
  transform. It must sit above the popup, so its z-index goes higher.
- Draw a 9x8 heart string-array with a `CRACK[y]` column per row. Just before the
  crack time, draw the crack column dark. At crack time, split into L/R halves
  with opposite kicks and spin, add gravity, and cull when offscreen.
- **Spawn from the box edges (bottom and sides), never inside the box.** The first
  version spawned inside the rect and covered the message text, which vision review caught.

## Dissolve into a pixel skull

- Snapshot the game canvas plus UI into particles (sample every N px and keep the
  colors), then tween each particle toward a target pixel of a 24x28 skull-and-
  crossbones string-array, scaled to the viewport. Fade a `#doom-cover` canvas to
  black behind them. Then swap to a crisp `<canvas id="skull">` with a glow
  pulse. Show the "DO YOU WANT TO BE FRIENDS?" YES/NO block after about 3s via setTimeout.
- Validate the skull art's row lengths with a quick script before rendering.

## Win-screen heart bursts

- Add a separate `<canvas id="win-fx">` inside the win dialog, **z-index below the
  card**, so hearts emerge from behind the box and never cover the bear or text.
- Spawn about 9 per second. Top edge: arc away from center (`vx` sign by side of
  center, `vy` -300..-520). Sides: burst outward. Bottom edge: spill and tumble.
  Use a pop-in scale (0.4 → 1.3 → 1), a sin wobble, gravity of 420, fade over the last 30%
  of life, and 4 pink/red palettes with a highlight pixel.
- **Narrow screens:** the card spans nearly the whole width on a phone, so side
  spawns land offscreen. When `min(leftRoom, rightRoom) < 70px`, spawn only from
  the top and bottom edges.
- Stop the loop when the dialog gets `hidden` (Play Again), and reset a
  `winFxOn` guard so re-entry doesn't stack loops.
- Verify by sampling canvas alpha outside the card rect at two moments and
  checking both counts are > 0 (still spawning), then check the loop flag is false after Play Again.

## Synthesized evil laugh (WebAudio, no assets)

### What failed
A sawtooth through two narrow bandpass filters plus a tiny highpassed noise tick
for the "h". Lowering pitch (0.75) and formants (0.85) made it lower, but the user
still reported "not quite hearing the ha annunciation". Changing pitch does not
fix articulation. If the user says a syllable isn't legible, rebuild the source
model instead of retuning numbers.

### What shipped (mini formant speech synth). User verdict: "MUCH better"
Per syllable, one shared **3-formant bank** (bandpass F1/F2/F3, Q = f/bandwidth,
upper bands gain-compensated) fed by **two sources**:
- Voice: sawtooth plus a sub-octave sawtooth "growl" (about 0.28 level), and 6 Hz vibrato at 2% depth.
- Breath: white noise through the **same formant bank**, so the "h" is already
  shaped like the upcoming vowel. That is what makes it read as "h" + "ah"
  instead of a hiss + a tone.
- "HA" envelope: noise alone for about 65 ms (the aspirated h), then the voice fades in over
  30 ms while the noise drops to a little breathiness under the vowel. The syllable lasts about 0.2 s.
- "MUA": closed-mouth hum (voice through a 320 Hz lowpass only) for about 120 ms, then the
  mouth opens into the bank, with formants gliding from "oo" (300/870/2240) to "ah"
  (730/1090/2440) over 140 ms.
- Knobs in one `LAUGH` object: `pitch` (0.5 ≈ 70–80 Hz, the deep bass the user
  wanted after two "lower" requests), `tract` 0.86 (scales all formants for a bigger
  throat), `growl`, `aspiration` 0.5, `breath` 0.06.
- Spacing 0.25 s between HAs. The echo is a short room slap (0.09 s delay, 0.2 feedback,
  0.35 wet) through a compressor. A long 0.21–0.23 s echo lands exactly on the next "h"
  and masks it.

### Gotchas
- `AudioParam.setValueAtTime` throws RangeError on negative times. Guard every
  `onset - epsilon` when an onset parameter can be 0 (e.g. the MUA syllable has no "h").
- The first aspiration level (2.2) made the "h" LOUDER than the vowel (+2 to +3 dB) and
  noisy. That reads as static, not "h". The measured sweet spot is about -8..-12 dB below the vowel.
- When measuring f0 with a growl layer, floor the search at 60 Hz, or autocorrelation
  locks onto the sub-octave and reports half the pitch.

## Verifying audio you cannot hear

Headless Chrome plays nothing, so never claim a sound "sounds" a certain way. Instead:
- `scripts/render_sfx_pitch.py`: render the function through an `OfflineAudioContext`
  for the HEAD and working versions, write `sfx-old.wav` and `sfx-new.wav`, and print f0 per window.
  This gives a measured before/after ("HA ≈150 → 110 → 70 Hz").
- `scripts/sfx_syllable_check.py <wav> <first> <step>`: per syllable, reports onset-vs-vowel
  dB, onset and vowel harmonicity, the silence gap before each syllable (echo smear),
  and vowel f0. Use it for "I can't hear the X" complaints. It turns legibility into
  numbers you can iterate on before redeploying.
- Still tell the user it hasn't been listened to. Offer a real recorded sample
  (e.g. an ElevenLabs sound effect saved as a small audio asset) as the fallback if
  the synthesized version still doesn't read.
