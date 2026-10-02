# Mobile (iPhone) audio for WebAudio games

User report: "on mobile I can't hear the audio even though it's unmuted". The
game's ♪ ON toggle was on and desktop audio worked fine. After the fix below
the user confirmed "audio works now".

## Causes (both apply on iOS)
1. **Ring/silent switch.** Safari puts WebAudio in the "ambient" audio session,
   which the hardware silent switch mutes. `<video>`/music ignore the switch,
   so users expect sound. Most iPhone users leave the switch on silent.
2. **Gesture unlock.** iOS only lets an AudioContext start/resume inside a
   completed user gesture (touchend/click/keydown). A game started by a
   joystick `pointerdown` + drag may never trigger a qualifying gesture, so
   the context stays `suspended` forever.

## Fix that shipped (in `game.js`, around `audio()`)
- `unlockAudio()` called from `touchend`, `pointerup`, `click`, `keydown` listeners
  on `document` (capture, passive). It:
  - creates/resumes the AudioContext;
  - sets `navigator.audioSession.type = 'playback'` when available (Safari 17+).
    That moves the page into the playback session, which ignores the silent switch;
  - on older iOS, starts a looping, near-silent `<audio>` element (tiny generated
    WAV data URI, `playsinline`) inside the same gesture. A playing media element
    also promotes the page to the playback session;
  - plays a 1-sample silent buffer through the context (classic iOS unlock).
- Resume again on `visibilitychange` (visible) and when `actx.onstatechange`
  reports `interrupted`/`suspended` (calls, Siri, app switch).
- Mute toggle: pausing the silent element when muting, `unlockAudio()` when
  unmuting (the tap itself is a valid gesture).

## Verification limits
- Headless Chrome has no silent switch and no `navigator.audioSession`, so the
  core fix cannot be exercised here. What can be tested (emulated phone, CDP):
  context is `none` before any tap, `running` after tapping START **and** after a
  joystick drag+release, oscillators get created during play (wrap
  `AudioContext.prototype.createOscillator` with a counter), mute toggles cleanly.
- Tell the user it's untested on a real iPhone. If sound is still missing, ask
  them to flip the silent switch to ring as a diagnostic, and for their iOS version + browser.
