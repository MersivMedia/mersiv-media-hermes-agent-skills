# Motion LoRA Run Log

Record every training run here. The hyperparameters in SKILL.md are
starting points from published guides, **not** values verified by a run
from this skill. This file is how they become verified.

Append a block per run. Keep failed runs — they carry more information
than successes.

## Template

```
### <run name> — <date>

Goal:            (motion style / character / both)
Approach:        (conditioning-only | motion LoRA | character LoRA | stacked)
Base model:      (LTX-2.5 distilled int8 / Wan 2.2 T2V-A14B / ...)
Trainer:         (musubi-tuner <sha> | ai-toolkit | fal hosted)
GPU:             (L40S 48GB / 4090 24GB / ...)

Dataset:
  clips:         N
  subjects:      how many visibly distinct
  frames/clip:   N at N fps
  resolution:    WxH
  captioning:    one-line description of the strategy

Hyperparameters:
  rank / alpha:  /
  lr:
  steps:
  batch / accum: /
  precision:

Results:
  wall time:
  best checkpoint:        (step N — NOT necessarily the last)
  best strength:
  motion fidelity:        1-5
  prompt adherence:       1-5
  identity bleed:         1-5 (lower is better for a motion LoRA)
  vs no-LoRA baseline:    better / same / worse

Notes:
  What surprised you. What you would change. Any OOM or crash and its fix.
```

## Runs

_(none yet — first run pending)_

## Accumulated findings

Promote anything that holds across two or more runs into SKILL.md as a
pitfall or a corrected default.

- _(empty)_
