# 09 — Troubleshooting (validated topaz 0.3.20 + safe defaults)

> Diagnose from config first (ref 02). The environment probe
> (`scripts/topaz_env_probe.py`) computes Topaz support **per host**. Read its verdict
> before assuming anything:
> - If the probe reports Topaz is **not found** on this host, most "errors" are really
>   "not installed yet" — go to Install.
> - If the probe reports `validation_status = valid` / `ready`, Topaz is installed and
>   working here; treat failures as real CLI/data/device problems, not absence.
>
> Never auto-run installers; confirm before running jobs on real data. There is no
> artificial no-execute ban: on a valid host the skill MAY run real jobs after explicit
> user confirmation.

## Install
**Recommended (conda):**
```
conda create -n topaz python=3.10        # 3.8–3.12 supported
conda activate topaz
conda install topaz -c tbepler -c pytorch
# CUDA build (NVIDIA only):
conda install topaz pytorch-cuda=11.8 -c tbepler -c pytorch -c nvidia
```
**Pip (into a venv at a supported Python):**
```
pip3 install topaz-em
```
Always propose, state that it modifies the environment, and **get explicit
confirmation**. Never install silently.
[sourced 0.3.20 @ 58fe5237: README.md:85, docs/source/installation/pip_install.md:14]

### "torch installs but `cuda_avail` is False on an NVIDIA host" (cu13 vs cu12 torch pin)
A real, newly observed failure mode: the **default PyPI `torch` is now a CUDA-13 build
(`cu130`)**. On a host whose driver is CUDA 12.x, that wheel reports `cuda=False`, so Topaz
silently falls back to CPU even though a usable GPU is present. Fix by pinning a **cu12x**
build into the env, e.g.:
```
pip install "torch==2.9.1+cu128" --index-url https://download.pytorch.org/whl/cu128
```
After the pin, the probe's `--check-torch` should report `cuda_usable_here = True`
(observed: `torch 2.9.1+cu128 cuda_avail True 12.8`). The conda CUDA build above
(`pytorch-cuda=11.8`) avoids this by pinning torch's CUDA at install time. [smoke:
default PyPI torch 2.12+cu130 → cuda=False; downgraded to
torch 2.9.1+cu128 → cuda=True]

### "Install fails / wrong Python"
- Topaz supports **Python 3.8–3.13** (`python_requires='>=3.8,<=3.13'`); README states 3.8–3.12
  currently tested. If the active interpreter is outside that (e.g. 3.14), create a dedicated
  conda/venv at 3.10 first. The probe flags `in_topaz_supported_range=false`.
  [sourced 0.3.20 @ 58fe5237: setup.py:45]
- Use a fresh env to avoid dependency conflicts (torch, numpy, h5py, scikit-learn, scipy).

## Device / GPU
### "CudaWarning: ... Falling back to CPU"
Expected when `--device >= 0` but no usable CUDA GPU (e.g. Apple Silicon, or torch is a
CPU/wrong-CUDA build — see the cu13/cu12 pin above). Topaz then runs on CPU. To select CPU
cleanly and silence it: **`-d -1`**. [sourced 0.3.20 @ 58fe5237: topaz/cuda.py set_device()]

### "Can Topaz use my Mac / M-series GPU (MPS)?"
**No MPS path exists** in Topaz 0.3.20 — it uses CUDA or CPU only (zero `mps` references in
`topaz/`; the probe confirms `topaz_mps_supported = False`). PyTorch's MPS flag is irrelevant
to Topaz. So: **if the probe reports Apple Silicon / no NVIDIA GPU, Topaz runs CPU-only** —
pass `-d -1`, expect slow training, and prefer CUDA/HPC/cloud for heavy training.
[sourced 0.3.20 @ 58fe5237: no mps refs in topaz/; the probe reports topaz_mps_supported=False]

### "Topaz is slow"
On CPU this is expected for `train`/`extract` on many micrographs. Mitigations: downsample
more (extract/preprocess `-s/--down-scale` or `-s/--scale`), use the bundled `resnet16`
instead of training (`extract -m resnet16`, the default), raise `--num-workers` (NOTE: for
`normalize`/`preprocess` the num-workers flag is **`-t`**, not threshold), or move training to
an NVIDIA GPU/HPC/cloud. Denoise/convert are the most CPU-friendly.
[validated topaz 0.3.20 — captured: topaz.extract.help.txt, topaz.normalize.help.txt,
topaz.preprocess.help.txt]

### "Out of GPU memory"
Reduce batch size (`train --minibatch-size`, `extract --batch-size`) / patch size
(`-s/--patch-size`, `-p/--patch-padding`); downsample. For `denoise3d` reduce `-s/--patch-size`
or use a **single GPU (`-d 0`)** instead of the default **`-d -2` (multi-GPU)**; `-d -1` is CPU.
[validated topaz 0.3.20 — captured: topaz.train.help.txt, topaz.extract.help.txt,
topaz.denoise3d.help.txt]

## Data / formats
### "No coordinates found / image_name mismatch"
`image_name` must be the basename **without extension** and must match the image list.
Coordinate tables are **tab-delimited** with header `image_name x_coord y_coord` (ref 04).
Extract output columns are `image_name  x_coord  y_coord  score`. [smoke]

### "Particles in the wrong place after export"
Almost always a **downsample scaling** mismatch. If you picked on downsampled images,
re-scale coordinates with `extract -s/--down-scale` / `-x/--up-scale` (default 1) or with
`topaz convert -s/-x` before exporting to STAR (ref 04). State the factor.
[validated topaz 0.3.20 — captured: topaz.extract.help.txt, topaz.convert.help.txt]

### "extract returns far more/fewer picks than expected"
`extract -t/--threshold` is a **log-likelihood score threshold (default -6, i.e. p>=0.0025)**,
NOT a 0–1 probability and NOT a score quantile. Raise it (toward 0 / positive) to keep only
higher-confidence picks; lower it for more picks. `-r/--radius` has **no default** and must be
supplied (or tune it with `--targets` plus `--min-radius 5 / --max-radius 100 / --step-radius 5`).
Set `-m none` only if inputs are already segmented log-likelihood maps. [validated topaz 0.3.20 —
captured: topaz.extract.help.txt]

## Process / behavior
### "train: No such file or directory on --save-prefix"
Topaz does **not** create the parent directory for `--save-prefix`. If you pass
`--save-prefix model/topaz_smoke`, the `model/` directory must already exist, or training
fails. **`mkdir -p` the save-prefix directory first.** Checkpoints are written per epoch as
`<save-prefix>_epoch{N}.sav` (e.g. `model/topaz_smoke_epoch1.sav`). [smoke]

### "topaz --help is slow / hangs"
It imports torch on startup. The probe wraps it with a timeout and notes it; use
`--no-topaz-exec` for filesystem-only detection. [validated topaz 0.3.20 — captured: topaz.help.txt]

## When unsure
Prefer the captured live help (`topaz.<cmd>.help.txt`) (CLI facts here are
VALIDATED against topaz 0.3.20). For behaviors not yet captured, label **[unverified]** and
point to the trust ladder. Community Discussions (dated) are P1 and must be cross-checked.
