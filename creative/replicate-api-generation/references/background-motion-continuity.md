# Background motion continuity across H3 shots (measured 2026-09-30, sizzle reel "Pass It On")

The user reviews at frame level and flagged all of these after the cuts themselves were fixed.
Measure them with optical flow before delivery. Pixel-difference motion alone misses direction.

## Pitfalls seen
1. **Background freezes as the shot approaches `last_frame_image`.** 15 s opening shot: sideways motion on the road
   was 4-7 during the descent, then about 0.1 for the last 4 s (cabs parked) until the final still. Likely cause:
   H3 converges on the exact still and freezes the scene to match it. Prompt fix under test: say that traffic,
   wipers and splashes keep moving through the last frame. Fallback: end the shot earlier and let the next clip
   carry the motion.
2. **Traffic direction reverses at a shared-keyframe seam.** Shot B starts from shot A's last frame but
   generates its own traffic, so the flying cars flipped direction for about 1 s, then flipped again. Fix: measure A's
   final direction and name it in B's prompt ("all flying cars and trains keep moving right to left and never
   reverse").
3. **H3 inserts hard cuts inside long shots.** A frame-diff spike above 2.2x the local median + 3 marks one.
   Suspected trigger: "[Shot 1]" prefixes plus timecoded "0-2 s: ... 2-4 s: ..." segments read as a multi-shot
   storyboard. For long takes, use one continuous sentence plus "single unbroken take, no cuts". A dissolve hides
   the cut but is still visible to this user, so re-render instead.
4. **Pauses at shot joins** (motion sags to about 3.5 near a seam, a frozen starfield). Merging adjacent shots into
   one longer generation removes the join entirely.

## Measurement (2 GB box: the `~/.venvs/cdp` venv has opencv-python-headless)
- Direction: Farneback flow at 480x270. Per 0.25 s, take the median horizontal flow of the fastest 10% of pixels
  outside the centre column, minus the global median (camera pan). The sign gives the direction.
  Script: `~/.hermes/data/sizzle-reel/diag_flow.py`. Split into bands (sky vehicles in the top 35%, a train in the
  middle band) with `diag_dir2.py`, since one global number mixes vehicles that move differently.
- **Caveat:** subtracting the global median removes a pan but not a tilt, dive or parallax. On the forest-dive
  re-render the sky-vehicle band read right-to-left throughout (fixed), while the train band read left-to-right
  for ~1 s during the camera's tilt into the dive. That can be real or a parallax artefact. Before reporting
  "direction fixed" or "still flips", check by eye on a strip of every 4th frame (1/6 s) over the first ~1.3 s.
- Frozen street: the 95th percentile of |dx| in the lower third (road), outside the centre, per 0.5 s. Rain is
  vertical, so dx isolates cars. Script: `diag_cabs.py`. Look at the LAST 1–2 s specifically; the clip median
  hides a freeze at the end.
- The combined per-clip gate is `~/.hermes/data/sizzle-reel/qc_round2.py <ids>`: seam PSNR against the keyframes,
  inserted cuts, still spans, road flow for the opening, band direction for traffic shots, and a 5x2 strip.
  It builds strips with ffmpeg `select='not(mod(n\,STEP))',scale=384:216,tile=5x2` and decodes keyframes with
  ffmpeg too, so it runs in any venv that has cv2 and numpy (no PIL needed).

## Measured outcomes of the prompt fixes (round 2, reel v6, $4.16 for 3 re-renders)
| Defect | Prompt change | Result |
|---|---|---|
| Street frozen near the last frame (15 s opening) | "cabs, wipers, splashes and pedestrians all still moving at full speed in the very last frame" | **Fixed.** Road flow 3–6 through the catch; last-1 s p95 dx 3.13 (was ~0.1) |
| H3-inserted hard cut in a long take | No "[Shot 1]", no timecoded segments; one sentence opening "This is a single unbroken take with no cuts, no scene changes and no pauses" | **Fixed.** 12 s reef→throat→space→planet take: zero inserted cuts |
| Pause + jolt at the throat/space join | Merge both into the one 12 s take | **Fixed.** A ~0.6 s ease remains where the take converges on its last frame; leave margin |
| Traffic reversing at a seam | "every flying car and the train keep moving right to left, exactly as in <Picture 1>, never reverse" | **Partly fixed.** Sky cars held direction; the train still ran the wrong way ~0.5 s during the camera tilt. Next time keep the conflicting vehicle OUT of frame in the new shot rather than asking H3 to match its direction |

## Cut-scan false positives (look before "fixing")
The spike detector (frame diff > 2.2x local median + 3) also fires on: **lightning** (sky goes white for 2–3 frames
while the camera keeps moving), intentional rapid-change outfit swaps, and crash zooms. Check a 1/12 s frame grid
around every flagged time before adding a dissolve or quoting a re-render.

## Order of operations when the user reports a defect
1. Measure the exact complaint for free (flow direction, road flow over the last seconds, the motion curve around
   the named moment, a cut scan) and confirm or refute each point with numbers.
2. Quote re-renders per defect, with the prompt change aimed at the measured cause. Merge shots where a join is
   the problem.
3. After rendering, re-run the same measurement before assembling. Report "fixed / not fixed / ambiguous" per
   defect, and never call an ambiguous one fixed.
