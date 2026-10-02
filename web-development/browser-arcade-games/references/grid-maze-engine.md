# Grid-maze engine (Pac-Man style) — proven design

These notes come from the gift-game build (hearts instead of dots, squirrels instead of ghosts). It is a 19x21 maze and uses 16px tiles.

## Maze legend
`#` is a wall, `.` a small collectible, `o` a power collectible, `-` the ghost-house door (passable only by house logic), and space an empty floor. A row open at both edges is a wrap tunnel. 151 collectibles is about right for one level.

## Movement: `advance(entity, dist, decide, once)`
- Positions are floats in tile units. The loop walks toward the next tile boundary, and whenever the entity sits exactly on a tile centre (EPS 1e-4) it snaps and calls `decide(e, x, y)`.
- For the player, `decide` works like this: if the buffered `next` direction is open, take it. Otherwise, stop if the current direction is blocked. An opposite-direction input reverses instantly, outside `advance`.
- Ghosts pass `once=true` and track `cx/cy`, so decisions fire once per tile. Clear `cx/cy` whenever you force a reversal or leave the house.
- Wrap by fixing x after each step: `if x < -0.5: x += COLS; elif x >= COLS-0.5: x -= COLS`. Grid lookups use `((x%C)+C)%C`.
- Speeds, in tiles per second: player 6.2, ghost 5.0, frightened 3.2, tunnel 2.8, eaten 11. Cap dt at 0.05.

## Ghost AI
- The mode schedule is scatter 7 → chase 20 → scatter 7 → chase 20 → scatter 5 → chase forever. The timer pauses while frightened. Every mode switch reverses the active ghosts.
- At each tile a ghost picks, among the non-reverse open directions, the one whose next tile is closest (squared Euclidean) to its target. Tie-break order is up, left, down, right.
- Targets:
  - Ghost 0 targets the player.
  - Ghost 1 targets 4 tiles ahead of the player.
  - Ghost 2 targets the reflection of ghost 0 through the point 2 tiles ahead of the player.
  - Ghost 3 chases the player when more than 8 tiles away and goes to its scatter corner otherwise.
  - Scatter corners sit outside the maze.
- Frightened ghosts pick a random allowed direction.
- Eaten ghosts follow a BFS distance map to the house exit, built once at boot AFTER the grid exists. At the exit they move straight down to the house centre and then run the "leaving" state again.
- House ghosts are released at playTime 0, 2, 6, and 10 seconds. They bob in place until then and leave with a straight x-then-y move.

## Power-up must cover EVERY ghost (user-reported bug)
The classic "only active ghosts turn blue" rule reads as a bug to players. A
squirrel released from the box mid-power killed the player, and the user
rightly called it unfair. The rule is now: **a power pickup frightens every
ghost** except ones already eaten (eyes heading home). Four code sites have to agree:
- `frighten()`: set `fright = true` for states `active`, `house`, and `leaving`, and
  set `reverse` only for `active`. Skip `eaten` and `entering`.
- The house-exit transition (`leaving → active`) must **not** reset `fright`. The
  old `g.fright = false` there is what made released ghosts deadly. The fright
  timer's expiry is the only thing that clears fright.
- `checkCollisions()`: also test ghosts in `house`/`leaving` **when frightened**. If
  one gets eaten in or near the box, send it to `entering` (it respawns in the
  house) rather than `eaten`.
- The respawn transition (`entering → leaving`, eyes reach the house centre) must
  set `g.fright = frightTimer > 0`, **not** `false`. The user's second report: after
  the first fix, an eaten squirrel came back out normal-colored mid-power and
  killed them. Arcade Pac-Man respawns ghosts normal, but players read that as a bug too.
  Rule of thumb: while the power timer runs, every ghost that isn't eyes is blue.
Test: call `frighten()`, set boxed ghosts' `release = 0`, wait about 1.8 s, and
assert every ghost is `active:true`. Respawn test: `frighten(); frightTimer = 7`,
teleport onto ghost 0 + `checkCollisions()`, park the player at (1,1) with
`dir = next = NONE` each poll, wait for `leaving`/`active`, and assert `fright`
is true. Touch it again → `eaten`. Then set `frightTimer = 0.2`, let a respawn
happen after expiry, and assert `fright` is false. Then teleport the player onto a released
ghost, call `checkCollisions()`, and assert the ghost is `eaten`, the game is
still `play`, and the score went up.

## Collisions and scoring
- Collision is a distance check: `dx²+dy² < 0.42`, where dx uses the wrapped distance. Check after the player moves and again after the ghosts move.
- Scores are 10 for a small collectible and 50 for a big one. Eaten ghosts give 200·2^combo, and the combo resets on each power pickup. The power effect lasts 7 seconds, and the ghosts flash during the last 2.
- The game has 3 lives, a 2.0-second READY, and a 1.6-second death animation.

## Player sprite
The chomper is drawn per pixel: a disc of radius about 7 with the mouth wedge masked by angle, and the mouth animates with `|sin(t*14)|`. The death animation opens the mouth wedge up to π.
