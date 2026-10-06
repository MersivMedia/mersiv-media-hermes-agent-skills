# Episode visuals build: worker lessons + verifying the result (French space channel, E2-E6, Oct 2026)

Brief: `~/.hermes/data/yt-arbitrage/fr-space/VISUALS_WORKER_BRIEF.md`. Worked example:
`fr-space/e5-univers-observable/visuals/` (shots.py, spec.py, fill_bars.py, relabel_fr.py, preview.sh, run_clips.sh,
run_pod.sh) and graphics project `~/.hermes/data/motion-graphics/projects/e5-univers-observable-graphics/`.

| Episode | Length | Cues | How built | Replicate | RunPod |
|---|---|---|---|---|---|
| E5 | 9.6 min | 35 | in-session | $2.85 | ~$1.48 over 3 runs |
| E6 | 20 min | 77 | one subagent | $3.30 | $0.23, 1 run |

## Delegating a whole episode
- A 20-min episode fits one `delegate_task` leaf (~72 min, 95 API calls). Put these in its context field, because
  it knows none of them otherwise:
  - the brief path
  - the E5 worked example
  - the spend caps
  - the lessons below
- **Verify the worker's claims yourself before reporting:**
  - **Render log:** `edit/assemble.log` must show `frames total X expected X`, the SYNC line and the FINAL LUFS.
  - **Drive:** the file size from the Drive API (`files().list`, `size` field) must equal the local size.
  - **Pods:** `pod.py list` shows none of yours.
  - **Frames:** ffmpeg 10 spread frames into a contact sheet and give it one vision pass.

## Rendered is not the same as uploaded
The user found E2, E4 and E6 had no video on Drive. E2 and E4 had rendered with `EPISODE OK` but were never
uploaded, and E6 had never been built.

When reporting on all episodes, check every episode's Drive `edit/` folder contents. Don't infer uploads from
render logs.

Drive layout:
- Root: `French Space Channel` (top level of My Drive).
- Each episode: `<Ex Title>/edit/`.
- Upload: `fr-space/upload_ep.py <ep> "<Ex Title>" edit 'edit/<ep>_roughcut.mp4'`. It prints `mismatches: none`
  when the sizes verify.

## Generation QC
- **Pillarboxed stills.** nano-banana-pro sometimes returns black side bars.
  - Detect: per-column std (numpy) on every still.
  - Fix: regenerate, or fill the bars with synthetic sky (median color + 1.5 grain + sparse stars + feathered
    seam; see `fill_bars.py`). Mirror-tiling the sky leaves a visible seam.
- **seedance clips morph often.** 2 of 3 were rejected on E5 and 1 of 3 on E6:
  - fog turned into billowing smoke
  - a galaxy ballooned over static ground
  - a ring swept across a probe

  Check frames 0, 60 and 120 side by side (clips are 1920x1088, 121 frames). On a fail, move the clip to
  `clips/_rejected/`, drop `clip=` from shots.py, and use the still with a slow camera move.
- **Real archive image over an AI still** for real objects. Search the Wikimedia Commons API with a UA. Only take
  public-domain or CC BY files, and record each credit and licence in archive.md.
- **Huge mosaics** (e.g. Hubble heic2501a, 42208x9870, 346 MB): decode with PIL `im.draft('RGB',(w//4,h//4))`
  (~80 MB of RAM), crop inside the jagged tile edges, and keep the camera's zoom clear of them.

## Photo-slot QC
- **Engine quirks:** it applies `--stills` to every slot passed, so preview one slot per call. It also reads stdin,
  so loops need `</dev/null` (a heredoc loop silently lost lines). `preview.sh` + `PREVIEW_LIST` handles both.
- **Odd framing:** plates like two hemispheres on white show white or black corners when zoomed. A deep zoom inside
  one hemisphere made the CMB look like abstract texture. Swap to a better-framed plate (the NASA oval on black).
- **Check every slot at the start, middle and end of its move.**
  - Callouts stay off the subject.
  - Pull-out box targets need the camera recentred on the object inside the box.
- **English text in real images:**
  - Vision-list ALL text, including corners and legends, on full-res half crops.
  - Relabel diagrams to French: mask the bright text in measured boxes, inpaint, redraw in Inter.
  - Drop any number that isn't in facts.md.
  - Object proper names (JADES-GS-z14-0, MoM-z14) may stay.

## Graphics QC
Read rendered text for French number bugs, values showing early, and masks dimming their own labels:
- `{:,.1f}` produced "2 ,5".
- A leftover `.replace()` produced "≈ 1,5 s km".
- "≈ 0,0 s" showed before the animation ran. Reveal a number when its motion lands.
- Masks drawn after the labels dimmed them. Draw the mask first.

## Run mechanics
- **Long jobs** (gen_clips, `pod_episode.sh`) go in a tiny script file, run with
  `terminal(background=true, notify=true)`. Log to `/tmp/vgpack/pod_<ep>.log` with a trailing `DONE rc=$?`.
  Inline pipes and heredocs tripped approval prompts on Telegram.
- **Polling:** `sleep ≤400`, then grep `render:|EPISODE|terminated|DONE`. Don't repeat an identical call more than
  twice; vary it.
- **Timing:** a full episode on one pod is ~31-40 min wall for 10-20 min of film (render ~1900-1960 s).
- **Fixes:** the brief caps pod runs at 3, so batch every fix into one re-render.
