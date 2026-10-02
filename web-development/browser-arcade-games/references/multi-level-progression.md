# Multi-level progression (levels, per-level copy, finale)

Learned turning a one-level Pac-Man gift game into 3 levels + finale. The user
added levels mid-project, and each level brought its own joke-button messages,
win text and failure rules.

## Data model
- `const MAZES = [L1, L2, L3]`, `let MAZE = MAZES[0]`, `let level = 1`.
  COLS/ROWS stay constant across levels, so the canvas size never changes.
- **Share the middle band** (ghost house, door, tunnel row, spawn points) across
  every maze. Then HOUSE_EXIT / HOUSE_CENTER / PLAYER_START, tunnel detection
  and the ghost release logic work unchanged. Only the top and bottom sections
  differ. Build the new mazes from mirrored left halves (see `scripts/maze_workshop.py`).
- Per-level theme `{fill, edge, door}` for wall colors. `renderWalls()` reads
  `LEVEL_THEMES[level-1]`, so each level looks like a new place for free.
- Per-level copy lives in tables keyed by level: `WIN_TEXT[]`, `LEVEL_CARDS[]`
  (start-card title), `PRANK_TEXTS[level].first/.second`.

## Three reset functions (keep them distinct)
| fn | used by | effect |
|---|---|---|
| `loadLevel(n)` | everything | sets MAZE, renderWalls, resetBoard, then buildHomeDist (after the grid exists), resetActors, HUD level number |
| `resetGame()` | level-1 losses, friend-zone endings | loadLevel(1), score=0, levelStartScore=0, lives=3 |
| `restartLevel()` | START/TRY AGAIN, L2/L3 out-of-lives, L2/L3 first joke press | full board + 3 lives, `score = levelStartScore` |
| `goToLevel(n)` | win-screen "LEVEL N" button | loadLevel(n), levelStartScore=score, lives=3, show level card, fire `onLevelStart` hook (prank.js re-arms its button) |

`startGame()` must call `restartLevel()`, not `resetGame()`. Otherwise START on
the level-2 card silently drops the player back to level 1.

## User's difficulty rule (encode by default for gift/"let her win" games)
- Losing all lives on level 1 → full reset. **On level 2+ → restart THAT level**
  with 3 lives, never back to level 1 ("we don't want it to be overly difficult
  for her to win/see the outcome").
- Only deliberate bad behavior (the 2nd joke-button press) sends the player
  back to level 1.
- Remember the joke-button stage across a lives-out restart
  (`stageBeforeDoom`), and re-arm it to stage 1 on each new level.

## Win screens and finale
- One win dialog reused per level: `showWin(lv)` sets the text and the next-level
  button label (`LEVEL ${lv+1}`), and hides the button on the last level.
- Last level: after ~6.5s, `explodeToFinale()` adds a `boom` CSS class to the card
  (scale up + brightness, then collapse), plays a low sawtooth sweep + sparkle
  SFX, and bursts ~260 pixel hearts from the card center plus 2 aftershocks on a
  fullscreen canvas. At ~1.3s it swaps to a `#finale` overlay (flash, bear,
  heartbeat-pulsing headline, small "To be continued..." fading in at 2.4s)
  with a gentle endless heart rain.
- `setTimeout(showWin, 900)` → `setTimeout(() => showWin(level), 900)` once showWin takes an argument.

## Shortcut links (the user asks for these; build them in)
Parse in boot, after the rAF starts:
- `?level=N` → `goToLevel(N)` (that level's START card)
- `?win=N` → `loadLevel(N)`, hide the start overlay, `setState('win')`, `showWin(N)` (win=last flows into the finale)
- `?preview=finale` → straight to the explosion + finale
- keep old links working (`?preview=prize` = `?win=1`)
Hand them over as a list: start + win for each level, plus the finale. Warn
that they are live skip links.

## Testing
- `.test/levels_test.py`-style harness: one PASS/FAIL line per rule, ending in
  `FAILURES: none`. Cover every level transition, all per-level messages, where each
  failure path lands (level + lives + score), the finale, and every shortcut.
- Driving a win via the hook: first park the ghosts
  (`g.state="house"; g.release=999`), then call `eatAll()`. The last heart
  under the player gets eaten on the next frame, so a ghost can't kill you mid-win.
- **Test pitfall:** snapshot `levelStartScore`, not `score`, as the expected
  value after a restart. The loop adds points in the ~2s between START and the
  snapshot, which made correct code look broken.
- A full 3-level run takes ~5 min. Write the log to a file and grep it:
  `... > log 2>&1; grep -c ^PASS log; grep -E 'FAIL|JS errors' log`. That keeps
  it under the 600s foreground cap.
