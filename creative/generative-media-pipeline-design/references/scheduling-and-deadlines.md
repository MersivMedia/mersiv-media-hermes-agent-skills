# Scheduling, deadlines and the speculative render queue

The live-layer scheduling problem: with N parallel render slots and measured
provider latency, does the next clip exist before the current one ends, for a
whole run? Everything here was derived by simulation against measured numbers,
and it changed the **story configuration**, not the code.

## Simulate the schedule BEFORE building the live layer

Write the discrete-event simulator before the player, the queue integration or
the socket layer. It is cheap, it runs in milliseconds, and its first useful
output is usually a failure you would otherwise have discovered in front of an
audience.

Feed it measured constants only:

```
INFERENCE = (5.6, 6.1)   # per 5s clip, from renders/*/shots.json
OVERHEAD  = (1.5, 3.0)   # submit + poll + fetch, refs cached
```

Then sweep the parameter you think is load-bearing and print a verdict column
(`HOLDS` / `cutaways cover it` / `BUFFER COLLAPSES`) rather than raw floats.

## The finding: parallelism cannot buy time that does not exist

Original configuration — head of 3 shots (15s), voting closing at 60% of the
head — produced **9/9 missed tail deadlines at every slot count from 1 to 8.**
Adding render slots never helped, and the reason is structural:

```
tail runway   6.0s        (the 40% of the head remaining after the vote)
tail render   7.1-9.1s    (5.6-6.1 inference + 1.5-3.0 overhead)
```

**A just-in-time tail cannot begin before the vote it depends on.** No amount
of concurrency shortens a dependency chain. When a sweep shows a metric flat
across every slot count, stop tuning the scheduler — the constraint is upstream
in the timeline, and the fix is parametric.

| head_shots | vote closes at | tail runway | tail misses |
|---|---|---|---|
| 3 | 60% | 6.0s | 9/9 |
| 3 | 40% | 9.0s | 2.1/9 |
| **4** | **40%** | **12.0s** | **0/9** |

Two parameters set the entire live budget:

- **`vote_close_frac`** — the fraction of the head after which voting closes.
  The tail's runway is everything after it. This is the single most
  load-bearing number in the system.
- **`head_shots`** — total head duration. More head means more runway.

Write both into the story/config file **with the derivation inline**, or a
later pass will "optimize" them back toward a longer voting window and silently
reintroduce a guaranteed miss on every beat.

## Model the head budget correctly

An early version of the simulator charged branch-head rendering against the
*current* scene and reported ~50% head misses. That is wrong: branch heads for
beat N render during beat N-1's full scene (head + tail) — which is the entire
point of speculating. The first beat is the exception, since nothing precedes
it; it is pre-rendered offline before curtain-up and excluded from the deadline
count.

Getting this wrong makes the architecture look broken when it is fine. When a
simulator reports failure, verify the model before changing the system.

## Concurrency is the budget, and it is real

Measured on a hosted queue endpoint, four concurrent 5s clips:

```
serial      22.2s wall per clip     0.22x realtime   buffer collapses
4 parallel   4.6s wall for four     4.32x realtime   3.5x speedup
```

Threads are correct despite the GIL — every job is a network call that releases
it. Verify the provider genuinely parallelises before designing around it; a
provider that serialises internally will show a ~1.0x speedup.

Slot sweep on the corrected configuration: **3 slots is the floor, 4 is the
operating point**, and adding more changes nothing.

## Find the gap between inference and wall time

A 5.6s inference was taking 22.2s of wall time. The cause was not the provider:
the same reference plates were being **re-uploaded on every shot**, 16.9MB each
time. Reference assets are identical across every shot of every scene.

Cache uploads **by content hash, not by path** — a regenerated plate keeps its
filename, and a path-keyed cache would serve a stale URL for new pixels.

```
cold  3.3s
warm  0.047s      71x
```

Always account for the difference between inference time and wall time before
concluding you need more slots. Transfer, queue wait and re-upload hide there,
and they are usually cheaper to fix than capacity.

## Queue semantics that matter

A queue that renders speculative branch work ahead of the clip playing in
twelve seconds is worse than no queue. Requirements:

- **Explicit priority classes** — `CRITICAL` (canon, playing imminently),
  `TAIL` (canon, slightly further out), `SPECULATIVE` (branch heads, ~half
  discarded), `PREFETCH` (cheap abandonable layer). Earliest deadline first
  *within* a class.
- **Prune by branch id across the beat**, not "the other option". Cancelling
  only the immediate loser orphans its subtree; a planner doing this grew from
  76 to 200 live jobs. Prune against the whole canon path.
- **Promote on vote.** The winner's tail moves to `CRITICAL` the moment the
  vote resolves.
- **Drop expired speculative work, never expired canon work.** Speculative work
  past its deadline is *useless* and is occupying a slot the next clip needs.
  Late canon work is merely *late* — it is still the only thing that can play.
- **Surface failures, never swallow them.** A job that throws must reach the
  caller so the cutaway path can engage.

## Test the queue with a fake clock

Queue logic is timing-dependent, which makes it exactly the code that rots
under real-provider tests. Inject the clock, use instant fake renders, and
assert behaviour deterministically:

- a `CRITICAL` job submitted last still runs first
- earliest-deadline-first holds within a priority class
- a vote prunes the whole losing branch and leaves other beats untouched
- promotion overrides an earlier deadline
- expired speculative work is dropped while late canon work is retained
- a throwing job is reported, not swallowed
- N slow jobs on N slots overlap in wall time

Keep provider-latency measurement separate from queue-logic tests. The former
is a measurement to record; the latter is a suite to keep green.

## Honest framing of the result

A 0% miss rate from a simulator is a *simulated* result. Say so. The model
covers render waves, vote timing and slot contention; it does not model
provider outages, rate limits, or a queue backing up across beats. That is
precisely why the cutaway fallback exists — the schedule holding on paper is an
argument for building the pipeline, not evidence that it will never stall.
