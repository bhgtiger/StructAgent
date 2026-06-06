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
Label convention used across the references:
- **[sourced 0.3.20 @ 58fe5237: <path>]** claim: traced to pinned source at the pinned
  commit (e.g. MPS absence, device dispatch, `python_requires`) (ref 01).
- **[validated topaz 0.3.20 — captured: topaz.<cmd>.help.txt]** claim: a CLI flag, default,
  subcommand, or file-format fact confirmed EXACTLY by captured live `--help` for 0.3.20
  (`topaz.<cmd>.help.txt`).
- **[smoke]** claim: an output-layout / runtime-behavior fact proven by an actual GPU run
  during the validated GPU smoke chain.
- **[paper]** claim: a method/assumption claim from a publication.

Captured-live help for Topaz **0.3.20** EXISTS (one
`topaz.<cmd>.help.txt` per subcommand; `_version.txt` records `0.3.20`) AND GPU smoke runs
reproduced the documented outputs (see "Validated runs" below).
The core commands ARE validated now — emit concrete commands with the user's real paths
and run them after explicit confirmation on a machine the probe classes `valid`/`ready`.

The fallback **"NOT validated against a local binary"** is reserved for the **per-host
uninstalled case only**: i.e. when `scripts/topaz_env_probe.py` reports Topaz is not
installed / `validation_status != valid` on the current machine. It is NOT a blanket
posture for the skill.

## Validated runs (0.3.20, Linux + NVIDIA GPU host, 2026-06-06)
End-to-end smoke chain on Linux + NVIDIA (an NVIDIA GPU, torch 2.9.1+cu128, cuda=True),
3 train + 1 test synthetic micrographs:
- **preprocess** — `topaz preprocess -s 4 -d 0 -o proc/ <mic>` (downsample + normalize). **[smoke]**
- **convert** — `topaz convert --to star -o coords.star coords.txt`. **[smoke]**
- **denoise (pretrained)** — `topaz denoise -d 0 -o denoised/ <mic>`; loaded bundled
  pretrained `unet_L2_v0.2.2.sav` on GPU when `-m` omitted. **[smoke]**
- **train** — `topaz train -d 0 --train-images train_mics/ --train-targets train_coords.txt
  --test-images test_mics/ --test-targets test_coords.txt -n 30 -r 8 --num-epochs 1
  --method PN --save-prefix model/topaz_smoke -o train.log.txt` → checkpoint
  `model/topaz_smoke_epoch1.sav` (naming `<save-prefix>_epoch{N}.sav`). **[smoke]**
- **extract** — `topaz extract -m model/topaz_smoke_epoch1.sav -r 8 -d 0 -o extracted.txt
  <mic>` → output columns `image_name  x_coord  y_coord  score`. **[smoke]**

Gotcha confirmed: `train --save-prefix DIR/...` requires `DIR` to already exist — Topaz does
NOT create the parent directory (see ref 09). **[smoke]**

## Benchmark-claim guardrail
Never present runtime/accuracy numbers without: (1) a source, (2) the Topaz version,
(3) the dataset/hardware context. **Per-platform fact (not a this-machine claim):**
Topaz has no MPS code path (zero `mps` references in `topaz/` at 58fe5237;
`topaz_mps_supported=False` in the probe report), so on Apple Silicon the GPU is unused and
Topaz runs CPU-only — Apple-Silicon timing therefore ≠ CUDA timing. If the probe reports
Apple Silicon / no NVIDIA GPU, pass `-d -1` (CPU). **[sourced 0.3.20 @ 58fe5237: topaz/]** (ref 02).
