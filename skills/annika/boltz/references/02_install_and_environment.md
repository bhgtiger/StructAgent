# 02 — Install and Environment

Always run `scripts/boltz_env_probe.py` first. Recommend installs from probe
results, not assumptions.

## Install

Recommended (NVIDIA/CUDA):
```bash
pip install boltz[cuda] -U          # Python >=3.10,<3.13
```
CPU/non-CUDA (works, but much slower and not a quality-validated default):
```bash
pip install boltz -U
```

Or via the consent-gated helper (refuses without `--yes`):
```bash
scripts/install_boltz.sh                 # dry-run plan
scripts/install_boltz.sh --yes --env boltz2 --python 3.10
scripts/install_boltz.sh --yes --update  # upgrade in place
```

Core deps pulled in: Torch, RDKit, PyTorch Lightning, NumPy/SciPy, gemmi,
Biopython, pandas, scikit-learn, ChEMBL structure pipeline. The `[cuda]` extra
adds `cuequivariance_ops_cu12`, `cuequivariance_ops_torch_cu12`,
`cuequivariance_torch` (>=0.5.0) for accelerated triangular-update kernels.

## Weights & data cache

- Auto-download on first run to `~/.boltz`, or `$BOLTZ_CACHE` if set
  (must be an **absolute** path).
- Boltz-2 weights observed: `boltz2_conf.ckpt` (~2.3 GB), `boltz2_aff.ckpt`
  (~2.1 GB), plus a `mols/` CCD library (`mols.tar` ~1.9 GB). Budget ~8 GB.
- On a shared cluster, point everyone at one cache to avoid re-downloading:
  `export BOLTZ_CACHE=/shared/boltz_cache`.

## GPU, kernels, precision

- NVIDIA + CUDA is the supported path. Boltz-2 prediction runs in `bf16-mixed`.
- **Kernels:** the cuEquivariance kernels are used by default. On volta
  (RTX 2080 Ti, compute capability **7.5 / Turing**) they run fine — `--no_kernels`
  is NOT needed. On **older** GPUs you may hit a `cuequivariance` error; then add
  `--no_kernels` (slightly slower, lower-end-hardware fallback).
- **VRAM:** scales with total token/atom count. 11 GB (2080 Ti) handles small/
  medium systems; large complexes can OOM. There is no official size→VRAM table —
  if you OOM, reduce `--diffusion_samples`, `--max_parallel_samples`,
  `--sampling_steps`, or the system size, and consider `--no_kernels`.
- **Multi-GPU:** `--devices N` (Lightning/DDP). Useful for batches of inputs.

## CPU / Apple Silicon

`--accelerator cpu` works and prints a slow warning. MPS/Apple-Silicon is not a
validated production path for geometry quality. Treat both as "possible, not
recommended for real work" unless the user has validated it themselves.

## Network & privacy

`--use_msa_server` posts sequences to `https://api.colabfold.com` (or a custom
`--msa_server_url`). For confidential sequences, generate a custom MSA offline
and reference it in the YAML instead. Auth via `--msa_server_username/-password`
(or `BOLTZ_MSA_USERNAME/PASSWORD`), or API key via `--api_key_header/-value`
(or `MSA_API_KEY_VALUE`). Only one auth method at a time.
