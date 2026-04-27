# lessons.md — structural_build

Practical bugs/workarounds and operational lessons encountered while running end-to-end structure_build pipelines.

## Distilled 2026-03-25

- **Wall-clock bottleneck can be operator idle, not compute:** in a multi-step pipeline (ISOLDE → Phenix → renaming), actual compute was ~20 min, but ~90 min was lost by not polling/continuing immediately after a long-running step completed and after an edit failure.
  - Mitigation: set tighter `process` polling timeouts / explicit continuation checkpoints so the next step triggers as soon as the prior tool finishes.
