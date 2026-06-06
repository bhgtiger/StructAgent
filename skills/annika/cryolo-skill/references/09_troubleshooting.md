# 09 · Troubleshooting

The official troubleshooting page (<https://cryolo.readthedocs.io/en/stable/troubleshooting.html>)
is listed in the source map but its **contents are not captured**, so the page's exact
error→fix table remains a **GAP**. Troubleshooting here is therefore **config-grounded**:
read the per-machine probe report first, reason from captured install requirements and the
live `--help`, and never mutate the environment without explicit confirmation. The notes
below that are tagged **VALIDATED against crYOLO 1.9.9** come from the captured help and the
GPU smoke run (see `references/08_validation_and_benchmarks.md`), not from the upstream page.

## Always start at the config report

Before troubleshooting anything machine-specific, apply the config gate (`SKILL.md §0`)
and read `configs/site_config.local.md`. Most "won't run / no GPU" reports are answered by
`support_assessment` and `gpu` fields, not by guesswork. The probe verdict
(`supported` / `partial` / `blocked`) is computed **per host**; the notes below interpret
those verdicts, they do not assume any one machine.

## "crYOLO is slow / not using the GPU"

Reason from captured facts (install docs: crYOLO needs an NVIDIA GPU + CUDA Toolkit +
cuDNN — ref 02), using the probe fields:

1. **`os.is_macos: true` → the probe reports `blocked`.** crYOLO does not officially
   support macOS; there is no NVIDIA-GPU path on that platform (Apple GPU / Metal / MPS ≠
   CUDA). This is a true per-platform fact surfaced by the probe verdict, not a statement
   about any specific machine. The fix is not a tweak — it is "run on a supported Linux +
   NVIDIA host". Do not suggest Metal/MPS workarounds; crYOLO has no such backend.
2. **`gpu.nvidia_smi: missing` on Linux → the probe reports `partial`.** No NVIDIA GPU is
   visible, so GPU acceleration is unavailable. Confirm hardware/driver presence before any
   GPU-specific advice.
3. **`gpu.nvidia_smi: present` but still slow → now partially tunable.** Several real knobs
   exist (all VALIDATED against crYOLO 1.9.9, captured help: `cryolo_predict.py.help.txt`):
   - `-t / --threshold` (default `0.3`) — too low picks junk, too high drops particles;
     adjust per dataset.
   - `--input_size` in the config (default `1024`, captured help: `cryolo_gui.config.help.txt`)
     — the shorter image dimension is downscaled to this; larger values are slower.
   - `-f / --filter` choice (`NONE` / `LOWPASS` / `JANNI`, default `LOWPASS`, captured help:
     `cryolo_gui.config.help.txt`) — `JANNI` neural denoising is heavier than `LOWPASS`.
   - `-pbs / --prediction_batch_size` (default `3`) — larger uses more GPU memory; see OOM
     note below.
   - `-nc / --num_cpu` (default `-1` = all CPUs) — controls CPU threads used during
     filtering / filament tracing, relevant when CPU-side filtering dominates.

   Remaining genuine dependency issue: a **driver / CUDA / cuDNN mismatch** can still leave
   the GPU idle or erroring. The validated stack where crYOLO 1.9.9 ran end-to-end on GPU
   was **TensorFlow 1.15.5 / CUDA 12.2 / driver 535 on an NVIDIA GPU**
   (the validation run). Surface the env vars the probe already read
   (`CUDA_HOME`, `CUDA_VISIBLE_DEVICES`, `LD_LIBRARY_PATH`) and cite the CUDA/cuDNN
   dependency; do not invent a specific "known issue" the captured sources do not show.

## GPU selection and out-of-memory (OOM)

VALIDATED against crYOLO 1.9.9 (captured help: `cryolo_predict.py.help.txt`):

- `-g / --gpu` selects which GPU(s) to use; multiple are space-separated. If unset, crYOLO
  uses **GPU 0** by default.
- `--gpu_fraction` (default `1.0`, range 0.0–1.0) limits the fraction of each GPU's memory
  crYOLO may use during prediction.
- `-pbs / --prediction_batch_size` (default `3`) sets how many images are predicted per
  batch; the help states **smaller values might resolve memory issues**. Lower this first
  when prediction hits an OOM.

## "`--otf` had no effect"

VALIDATED against crYOLO 1.9.9 (smoke evidence: `work/cryolo/predict.log`). `--otf`
(on-the-fly filtering, no filtered images written to disk) is **silently ignored when the
config's filter is `NONE`**. The smoke run logged:

> You specified the --otf option. However, filtering is not configured in your config line,
> therefore crYOLO will ignore --otf.

If you need `--otf` to do anything, set `-f / --filter` to `LOWPASS` or `JANNI` in the
config (it defaults to `LOWPASS`); with `--filter NONE` there is nothing to filter, so the
flag is a no-op. This is expected behavior, not an error.

## Environment variables — read, do not mutate

- The probe reports an allowlist (`CUDA_HOME`, `CUDA_PATH`, `CUDA_VISIBLE_DEVICES`,
  `LD_LIBRARY_PATH`, `CONDA_PREFIX`, `CONDA_DEFAULT_ENV`, `VIRTUAL_ENV`, `CUDNN_PATH`).
- You may **discuss** these and cite the CUDA/cuDNN dependency. You may **not** export,
  edit, or persist any environment variable, or modify `~/.bashrc` / conda activation,
  without explicit user confirmation. Reading is always fine; mutation requires sign-off.

## "crYOLO is not installed / command not found"

- If `cryolo.installed: false`, crYOLO is not on `PATH` / not in the active env. The skill
  **does not install system-level dependencies without confirmation** — it can explain that
  installation is needed, that the official conda/pip install path applies (ref 02,
  ref 07), and that crYOLO's license governs use.
- You may point to the **official install route generically** (a dedicated conda environment
  per the crYOLO docs, or pip into a clean env) and offer to run it **only after explicit
  user confirmation**. Do not paste a verbatim "verified" install command line: the exact
  pinned install commands are not captured here, so describe the official path rather than
  asserting an unverified one.

## "Which config / filter / threshold should I use?"

These are configurable parameters with documented **defaults** — not arbitrary example
values. VALIDATED against crYOLO 1.9.9 (captured help: `cryolo_gui.config.help.txt`,
`cryolo_predict.py.help.txt`):

- `--low_pass_cutoff` **default `0.1`** — the LOWPASS filter cutoff frequency.
- `-t / --threshold` **default `0.3`** — prediction confidence threshold (0–1; higher is
  more conservative).
- `boxsize` is a **positional config argument** (`config_out_path boxsize`); the integer is
  the **box size** in pixels (smoke used `160`; the docs example uses `220`). It maps into
  `model.anchors` in the written JSON (VALIDATION_SUMMARY line 22; `config_cryolo.json`).
- `-f / --filter` **default `LOWPASS`** (choices `NONE` / `LOWPASS` / `JANNI`);
  `-a / --architecture` **default `PhosaurusNet`**; `--input_size` **default `1024`**;
  `-nm / --norm` **default `STANDARD`**.

So the right guidance is: start from these defaults, then tune `-t` for the picking
precision/recall trade-off, pick `-f` for the noise level, and set `boxsize` to your
particle's box size. Dataset-specific *optimal* values still depend on the data and are
not prescribable from the captured sources alone.

## Escalation / capture path

When a troubleshooting answer needs facts beyond what is already captured:

1. Re-run the probe (state may be stale) and re-read `site_config.local.md`.
2. The live `--help` for every crYOLO subcommand is **already captured** (the `*.help.txt`
   files) and is the authority for flags, defaults, and
   subcommands — consult it before answering, and cite the filename. The upstream
   troubleshooting *page* itself is still uncaptured; if a question needs it, capture that
   page (URL + date) into `references/` before quoting it.
3. Give a specific, cited fix labeled to the validated version (crYOLO 1.9.9). On a probe
   verdict of `supported` / `partial`, the skill MAY emit concrete commands with the user's
   real paths and run real jobs **after explicit user confirmation** (see `SKILL.md` and
   `references/07_safety_license_privacy.md`).
