# 09 — Troubleshooting (sourced + safe defaults)

> Diagnose from config first (ref 02). If Topaz is not installed, most "errors" are
> really "not installed yet" — go to Install. Never auto-run installers or jobs.

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
confirmation**. Never install silently. [sourced: docs/source/installation/*, README]

### "Install fails / wrong Python"
- Topaz supports **Python 3.8–3.13**. If the active interpreter is outside that (e.g.
  3.14), create a dedicated conda/venv at 3.10 first. The probe flags
  `in_topaz_supported_range=false`.
- Use a fresh env to avoid dependency conflicts (torch, numpy, h5py, scikit-learn, scipy).

## Device / GPU
### "CudaWarning: ... Falling back to CPU"
Expected when `--device >= 0` but no usable CUDA GPU (e.g. Apple Silicon, or torch is a
CPU build). Topaz then runs on CPU. To select CPU cleanly and silence it: **`-d -1`**.
Source: `topaz/cuda.py set_device()`.

### "Can Topaz use my Mac / M-series GPU (MPS)?"
**No.** Topaz v0.3.20 has no MPS path; it uses CUDA or CPU only (ref 02). PyTorch's MPS
flag is irrelevant to Topaz. On Apple Silicon, Topaz is **CPU-only** — use `-d -1`, expect
slow training, and prefer CUDA/cloud for heavy training.

### "Topaz is slow"
On CPU this is expected for `train`/`extract` on many micrographs. Mitigations: downsample
more (`-s`), use the bundled `resnet16` instead of training, raise `--num-workers`, or move
training to an NVIDIA GPU/HPC/cloud. Denoise/convert are the most CPU-friendly.

### "Out of GPU memory"
Reduce batch size / patch size; downsample; for `denoise3d` reduce patch or use a single
GPU (`-d 0`) instead of `-2`.

## Data / formats
### "No coordinates found / image_name mismatch"
`image_name` must be the basename **without extension** and must match the image list.
Coordinate tables are **tab-delimited** with header `image_name x_coord y_coord` (ref 04).

### "Particles in the wrong place after export"
Almost always a **downsample scaling** mismatch. If you picked on downsampled images,
upscale coordinates with `topaz convert` before exporting to STAR (ref 04). State the factor.

## Process / behavior
### "topaz --help is slow / hangs"
It imports torch on startup. The probe wraps it with a timeout and notes it; use
`--no-topaz-exec` for filesystem-only detection.

## When unsure
Label **[unverified]**, point to the trust ladder, and prefer capturing live behavior
once Topaz is installed. Community Discussions (dated) are P1 and must be cross-checked.
