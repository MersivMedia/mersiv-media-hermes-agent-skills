# The live screening layer

Serving a speculatively-rendered branching film to a shared audience: playback
sync, vote integrity, and actually getting the URL into someone's hands.

Everything here was verified against a running server with real concurrent
WebSocket clients, using a `--demo` mode that replays already-rendered clips so
the whole layer costs nothing to exercise.

> Two of the defects documented below — segments that never play, and votes that
> are never counted — were reported by a **viewer**, after a full suite of
> protocol tests passed. Read §3.1 and §4.1 before building the player.

---

## 1. Build a `--demo` mode before anything else

One flag that swaps the provider render call for "copy an existing clip off
disk". Everything else — playlist writing, state push, vote tally, canon log —
runs identically.

This is not a convenience. The live layer needs dozens of restarts to develop
(port conflicts, lifespan bugs, playlist edge cases), and each one would
otherwise re-render a scene. Reuse the clips you already paid for during M2.

```
srv = Server(story, demo=True)   # pool = renders/*/shot_*.mp4 + cutaways
```

Keep the seam at exactly one function. If demo mode diverges anywhere else, it
stops being a test of the real system.

---

## 2. The server owns the playhead

The single design decision everything else follows from. **A vote is
meaningless if the room is looking at different moments in the story.**

- Clients report nothing that affects state. They receive the authoritative
  position and correct toward it when they drift past a threshold (~2s).
- The playhead is derived from wall-clock time since start, clamped to the
  duration of segments that have actually been *published* — so it can never
  point at media a viewer cannot fetch.
- A late joiner is dropped into the current moment, never the beginning.

```python
def playhead(self, now=None):
    if not self.started_at: return 0.0
    return min((now or time.time()) - self.started_at, self.published_seconds)

def buffer_ahead(self, now=None):
    return self.published_seconds - self.playhead(now)
```

`buffer_ahead` is the health metric for the whole screening. When it approaches
zero the scheduler must publish a cutaway rather than let the playlist run dry.
Measured in a live demo run: playhead 39.5s, published 62.2s, **22.7s ahead** —
the simulated M3 schedule holding in a real process.

---

## 3. HLS with an EVENT playlist, not WebRTC

A shared screening tolerates *uniform* latency but not per-viewer streams.
WebRTC optimises the wrong variable here.

More importantly, an EVENT playlist (no `#EXT-X-ENDLIST` until the screening
finishes) is the speculative model exposed directly to the player: the client
keeps re-fetching the manifest and picks up segments that did not exist when it
connected. The renderer writes the playlist while the player consumes it.

```
#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:6
#EXT-X-MEDIA-SEQUENCE:0
#EXT-X-PLAYLIST-TYPE:EVENT
#EXTINF:5.199,
/segments/seg_0000.ts
#EXT-X-DISCONTINUITY          <- before a cutaway
#EXTINF:5.199,
/segments/seg_0001.ts
```

**Tag cutaways with `#EXT-X-DISCONTINUITY`.** A fallback clip is a different
source and a different encoder run; without the tag players stutter or drop the
stream at the seam.

### 3.1 Rendered clips are NOT HLS segments — remux them

The bug that produced "I'm not seeing any video playback" while every protocol
test passed.

Provider-returned clips are **progressive MP4**: one self-contained movie per
file.

```
$ box structure of a returned clip
ftyp  uuid  moov  free  mdat        <- a complete standalone movie
```

`hls.js` cannot splice a sequence of these into one continuous timeline. It
loads the first, then stalls — which presents as a player that simply never
advances, with no console error loud enough to be obvious. HLS requires either:

- **MPEG-TS segments**, or
- **fMP4** (`moof`+`mdat` fragments) with a shared `#EXT-X-MAP` init segment.

Prefer TS when the playlist grows one clip at a time: it needs no init segment
and no cross-segment signalling, so appending is trivial. The remux is
**stream-copy — no re-encode, ~50 ms**:

```bash
ffmpeg -y -v error -i shot.mp4 -c copy -bsf:v h264_mp4toannexb -f mpegts seg.ts
```

`h264_mp4toannexb` is required: MP4 carries H.264 in AVCC length-prefixed form,
TS needs Annex-B start codes. Serve with `Content-Type: video/mp2t`.

**The testing lesson is the transferable part.** The earlier checks —
`curl` returning 200, correct content type, `ffprobe` reporting h264/aac at
1536×672 for 5.184s — all passed, because the files *were* valid video. Serving
valid video and serving a valid HLS *stream* are different claims, and only the
first was ever tested. When verifying a streaming format, assert the **container
and box structure the protocol requires**, not merely that the media decodes.

### 3.2 Remuxing is not enough — stamp the timestamps too

The *second* round of "it stopped and got stuck". Correct container, still
unplayable past the first segment.

Each provider clip is its own movie, so each one starts at the same
presentation timestamp:

```
seg_0000.ts  first_pts=1.400
seg_0001.ts  first_pts=1.400      <- time jumps BACKWARD at every boundary
seg_0002.ts  first_pts=1.400
```

A player joining these sees the timeline reset each segment and stalls. Stamp
every segment with its running offset in the playlist:

```bash
offset=$(python -c "print(sum_of_prior_segment_durations)")
ffmpeg -y -v error -i shot.mp4 -c copy -bsf:v h264_mp4toannexb \
       -muxdelay 0 -muxpreload 0 -output_ts_offset "$offset" \
       -f mpegts seg.ts
```

```
seg_0000  pts=0.000
seg_0001  pts=5.184        monotonically increasing across the whole run
seg_0002  pts=10.400
```

Verify with `ffprobe -show_entries packet=pts_time -read_intervals "%+#1"` on
consecutive segments — the first PTS must increase. This is cheap and catches
the defect instantly; it is the check that should follow any per-clip remux.

### 3.3 Point a real player at the real URL — as the FIRST check

Three rounds of viewer-reported playback failure were each diagnosed by
inspecting a *layer*: the file decodes, the container is right, the timestamps
increase. Every layer passed while the stream remained unplayable, because the
failure moved.

One command settles it, and should be run before claiming the stream works:

```bash
ffmpeg -v error -i "http://HOST:PORT/stream/index.m3u8" -t 20 -f null -
```

Silence means a real HLS client fetched the manifest, followed the segment
URLs, and decoded a continuous timeline. **If that passes and a browser still
shows nothing, the bug is in the client code, not the media** — which is
exactly how §3.4 was finally located, after two rounds of blaming the stream.

Verify the whole path end-to-end with an independent client first, then bisect
inward. Layer-by-layer verification builds confidence without ever testing the
claim that matters.

### 3.4 A resync loop looks exactly like "no video at all"

Server-authoritative sync was the *careful* part of the design, and it is what
broke playback hardest.

```
state pushes arrive ~2x/second
resync rule: seek whenever |video.currentTime - playhead| > 2s

-> seek, begin buffering, receive next push, seek again
-> a frame never renders; the player buffers forever
```

Correcting drift must be **rare, late, and rate-limited**, because a seek costs
a rebuffer:

```js
if (started && !video.paused && video.readyState >= 3 &&
    now - lastSeek > 10000 && Math.abs(video.currentTime - s.playhead) > 8) {
  lastSeek = now;
  video.currentTime = s.playhead;
}
```

Guard on all four: playback has actually started, is not paused, has enough
data buffered, and a cooldown has elapsed. **A few seconds of drift is
invisible to an audience; a stalled player is not.** Never seek during startup.

Two more client-side essentials for a shared screening:

- **iOS Safari has no MSE for this** — `hls.js` will never initialise. Feature
  detect and fall back to native HLS via `video.src = manifestUrl`.
- **Autoplay is blocked on mobile.** Attach a document-level tap handler that
  calls `play()`, and surface the blocked state in the UI.
- **Expose a `video` status field** in the page showing `manifest ok` /
  `buffering` / `playing` / the actual player error. On a headless host this is
  the only channel through which a viewer can report *where* playback failed
  instead of "it doesn't work" — it converts a vague report into a diagnosis.

---

## 3.5 Serving master-quality clips to phones

Reported as *"video is working better, but it takes a while to load."* The
renderer emits masters and the live path was serving them untouched:

```
source clips    5.6 MB per 5.2s segment   ~9.0 Mbps   1536x672
```

That is 5.6 MB to download before the first frame appears. Re-encode on publish:

```bash
ffmpeg -y -v error -i shot.mp4 \
  -c:v libx264 -preset veryfast -profile:v main \
  -b:v 1800k -maxrate 2000k -bufsize 3000k \
  -g 48 -keyint_min 48 -sc_threshold 0 \
  -vf scale=1280:-2 -c:a aac -b:a 96k -ac 2 \
  -bsf:v h264_mp4toannexb -muxdelay 0 -muxpreload 0 \
  -output_ts_offset "$offset" -f mpegts seg.ts
```

```
after           1.26 MB per 5.2s segment   ~2.0 Mbps   1280 wide
```

A 4.5× cut for **2.7s of CPU per clip** — which fits entirely inside the ~20s
buffer the scheduler already maintains, so it spends latency you already have
rather than latency the viewer feels. `-g 48` forces a keyframe every 2s so the
player can begin decoding partway into a segment instead of waiting for the
next one.

This also stops being merely a fix and becomes architecture: the renderer keeps
producing high-quality masters while the live path serves a mobile-appropriate
encode, and that transcode step is the natural place to add a multi-bitrate
ladder later so a weak connection drops to 800k instead of stalling.

Note the interaction with §3.2 — the re-encode replaces the stream-copy remux,
so `-output_ts_offset` must be carried across or the timestamp defect returns.

## 3.6 Muted autoplay is a policy, not a bug — give it a visible control

*"Not getting any audio."* The `<video>` element carries `muted`, and it has
to: browsers block autoplay outright when sound is enabled, so an unmuted
stream means **no picture either**. Starting muted is the only way playback
begins without a gesture.

Do not try to defeat this. Surface it:

```html
<video id="v" playsinline muted autoplay></video>
<button id="unmute">Tap for sound</button>
```

```js
unmute.addEventListener('pointerdown', ev => {
  ev.preventDefault();
  video.muted = false; video.volume = 1;
  video.play().catch(()=>{});
  unmute.classList.add('hide');
});
```

One deliberate tap trades the gesture for audio. Without a visible affordance a
viewer simply reports "no sound" and has no way to discover the fix — the
muting is invisible to them and looks identical to a broken audio pipeline.

---

Server-side tally, one vote per connection per beat, frozen at close.

- Broadcast the running tally so the room can watch the split — that shared
  tension is most of the product — but compute the winner from the server's own
  record, **never** from a client-reported total.
- A vote arriving a few hundred ms after close is a normal network event, not an
  error. Return `accepted: false` rather than raising.
- Reject unknown choice ids explicitly; don't let a typo create a phantom option
  in the tally.

**Break ties deterministically** (toward the first choice), not randomly. A
screening must be reconstructable from its canon log, and an unrecorded coin
flip makes the log a lie. If you do want randomness, seed it from something
recorded in the log.

Each resolved beat appends an immutable record:

```json
{"beat": "b2_the_hail", "winner": "A", "tally": {"A": 3, "B": 2},
 "voters": 5, "at": 34.0}
```

### 4.1 There are TWO clocks. Gate the vote on the PLAYHEAD, never on publish time

The bug behind "my vote did not seem to be counted", and the more serious of the
two viewer-reported defects because it silently invalidated the schedule model.

A speculative pipeline runs two clocks that differ by the entire buffer:

```
RENDER clock    when a clip is PUBLISHED to the playlist
PLAYHEAD clock  what the audience is currently WATCHING
                lag between them = buffer_ahead, measured 20-26s
```

Opening the vote as soon as the head is published — the obvious implementation —
produces this, observed live:

```
playhead 118.9s   -> vote OPENS for beat b5
b5 head spans     124.4s .. 145.2s of published media

The room is asked to decide a scene that has not started yet and that they
have not seen. By the time b5 reaches the screen, voting closed 8s earlier.
Every tap lands outside the window and is silently rejected.
```

It also means the window was open for ~8s of every ~31s beat, so **~73% of the
time the buttons were disabled** — and a rejected vote looks identical to a
broken button.

Worse than the UX: the scheduling simulation had assumed **viewer time** all
along. "Voting closes at 40% of the head" means 40% of the head *as watched*.
Wiring it to the render clock meant the carefully derived tail runway never
existed in the live path — the server contradicted the model it was built from,
while every unit test still passed.

Correct sequence, expressed in playhead terms:

```
publish head
wait until PLAYHEAD enters the head          <- the missing step
open vote
close at vote_close_frac through the head    (viewer time)
render tail; it must land before the playhead reaches the head's end
```

```python
async def _sleep_until_playhead(self, position: float) -> None:
    """Block until the audience's playhead reaches `position` seconds."""
    while self.screening.playhead() < position:
        await asyncio.sleep(0.25)
        await self.push()
```

Verified after the fix — the vote now opens as the scene appears:

```
playhead 29.2s  b1_arrival   closed
playhead 32.2s  b2_the_hail  OPEN 7.3     <- b2 head spans 31.2 .. 52.0s
```

**Generalisation:** in any speculative or buffered media system, ask of every
timed event *which clock is this on?* Anything the audience reacts to belongs on
the playhead. Anything about resource scheduling belongs on the render clock.
Mixing them produces bugs that are invisible to unit tests, invisible to
protocol tests, and obvious to the first person who watches.

### 4.2 Do not rebuild a control the user is trying to press

Reported as *"my vote was logged but I had to press the button a few times."*
The server was fine; the button was being destroyed under the user's finger.

State pushes arrive ~2×/second, and each one rebuilt the vote controls:

```js
$('opts').innerHTML = '';                 // <- every push, twice a second
(s.choices||[]).forEach(c => { ...append fresh buttons... });
```

A tap landing between the rebuild and the next frame hit a detached node, so
the handler never fired. It registered only when the user happened to press
during the gap — hence pressing several times.

Build interactive controls **once per logical unit** (here, per beat), then
mutate them in place:

```js
if (opts.dataset.beat !== String(s.beat)) {   // rebuild only on beat change
  opts.dataset.beat = String(s.beat);
  ...create buttons once...
}
opts.querySelectorAll('button').forEach(b => {   // update in place
  b.disabled = !s.vote_open;
  b.querySelector('.fill').style.width = pct + '%';
  b.querySelector('.pct').textContent = `${n} · ${pct}%`;
});
```

Two touch-specific fixes that matter on phones:

- **Use `pointerdown`, not `click`.** Mobile `click` waits ~300 ms for a
  possible double-tap — comfortably long enough for the next state push to land
  first.
- **Set `touch-action: manipulation`** so the browser stops waiting on gesture
  disambiguation, and reflect the user's choice **optimistically** in the UI
  rather than waiting for the server round-trip.

**General rule for any live-updating page:** a high-frequency state stream and
interactive controls are in direct conflict. Push frequency is a *rendering*
concern; anything the user touches must have a lifetime longer than the push
interval. This class of bug is invisible on a desktop dev machine with a mouse
and a local socket, and appears immediately on a phone over a real network.

### End-to-end test shape

Unit tests cannot cover this; run real clients against a running server.

```
PASS state pushed: seq 8 -> 8                    unsolicited push, not polling
PASS late joiner at 10.42s of 31.1s published    dropped into the moment
PASS invalid choice rejected by the server
votes accepted: 5/5, tally {A:3, B:2}            split recorded exactly
```

Five tests worth writing: state is *pushed* not polled, a late joiner gets the
current position (and never a playhead beyond published media), invalid choices
are rejected, N concurrent viewers produce an exact server-side tally, and — the
one that would have caught §4.1 — **the vote window opens while its own scene is
within the playhead range**, not merely while it is published.

---

## 5. Broadcast must never block on a slow client

Fan-out sends to every socket and drops whoever fails, per-socket. A dead or
slow viewer cannot be allowed to stall the screening for everyone else.

```python
for ws in list(self._clients):
    try: await ws.send_text(payload)
    except Exception: dead.append(ws)
for ws in dead: await self.drop(ws)
```

Carry a `seq` counter on every state message so clients can dedupe and detect
gaps without the server tracking per-client acknowledgement.

---

## 6. Delivery: verify reachability from OUTSIDE before handing over a URL

A real workflow failure. The server bound `0.0.0.0`, responded 200 on both
loopback *and* the public IP when tested from the box itself, and the user still
got nothing on their phone. The host firewall was dropping the port inbound —
which is invisible to every test run locally, including one that curls the
public IP, because that traffic never traverses the firewall's INPUT path.

**Before telling anyone to open a link:**

1. Confirm the listener is on `0.0.0.0`, not `127.0.0.1` (`ss -ltn`).
2. Check the host firewall's allowed ports, not just whether the process
   answers.
3. Check what is already serving 80/443 — these boxes usually have something.

### Prefer an existing reverse proxy over opening a port

If a TLS-terminating proxy is already running (Caddy, nginx, Traefik), route
through it instead of punching a hole for a custom port. You get:

- HTTPS with a real certificate, no browser warnings
- no firewall exception to remember or clean up
- no odd port for a mobile network to block outright

This matters specifically for phones: iOS increasingly resists plain-HTTP pages
and may silently upgrade `http://host:PORT` to HTTPS, which then fails against a
plain server. A path or subdomain through the existing proxy avoids the whole
class of problem.

Opening the port is the fast fix for a demo; the proxy route is the correct one
for anything a person outside your network is meant to watch.

---

## 7. Scope honestly

A screening server of this shape is one asyncio process holding one story in
memory: no auth, no persistence across restarts, no CDN. That is a reasonable
milestone boundary — the interesting risks are synchronisation and vote
handling, not scale — but say so plainly rather than implying it is
production-ready.

Equally: if you never actually *watched* the viewer page (headless box, browser
tooling unavailable), verify what you can by protocol — status codes, content
types, `ffprobe` on a served segment to confirm real h264/aac — and tell the
user the UI itself is unverified. They will find in ten seconds what no amount
of curl proves.

**This is not a formality.** In this session the honest declaration was made,
the user watched, and within one viewing they found two structural defects
(§3.1, §4.1) that a full green test suite had missed. The unverified-surface
handover is a load-bearing part of the workflow, not an apology attached to the
end of it.
