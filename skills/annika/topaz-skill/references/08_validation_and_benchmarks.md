# 08 — Validation & benchmarks (scope claims carefully)

## Papers (method authority; not exact-CLI authority)
- **Bepler et al., "Positive-unlabeled convolutional neural networks for particle
  picking in cryo-electron micrographs," Nature Methods 2019** —
  https://doi.org/10.1038/s41592-019-0575-8. Establishes the PU-learning picking method,
  validation, and assumptions. **[paper]**
- **Topaz-Denoise preprint** — https://doi.org/10.1101/838920. Denoising models/validation.

### Method assumptions / limitations to surface
- Picking uses **positive-unlabeled** learning: a few labeled particles + many unlabeled
  regions. Quality depends on the labeled set being true positives and on the assumed
  fraction of positives (π). Mis-set expected-number-of-particles biases precision/recall.
- Pretrained detectors generalize across many datasets but not all; novel particle shapes
  may need training.
- Benchmarks in papers are **dataset- and version-specific** — do not generalize "best".

## How to answer "is Topaz the best picker?"
Give a qualified, evidence-scoped answer: Topaz is a widely used PU-learning picker that
performs well especially for low-SNR / rare particles; comparisons depend on dataset,
labels, and tuning. Cite the paper; avoid absolute claims. **[paper]/[unverified]** as appropriate.

## In-repo tests (smoke-validation references)
- `test/test_commands_simple.py`, `test/test_example.py`, `test/topaz/test_*.py`
  (`test_main`, `test_mrc`, `test_predict`, `test_denoise`, …), `test/models/*`,
  `test/data_utils/*`. Useful as **fixtures/oracles** for v2 execution validation.

## Skill self-validation (what "validated" means here)
- **[sourced]** claim: traced to pinned source/docs (ref 01).
- **[live]** claim: confirmed against the installed `topaz` (version recorded).
- A command is only "validated" once captured-live help confirms its flags AND a tiny
  fixture run (v2) reproduces the documented output. Until then: "NOT validated against
  a local binary."

## Benchmark-claim guardrail
Never present runtime/accuracy numbers without: (1) a source, (2) the Topaz version,
(3) the dataset/hardware context. Apple-Silicon timing ≠ CUDA timing (Topaz is CPU-only
on Apple Silicon — ref 02).
