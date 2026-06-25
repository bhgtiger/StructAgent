# 09 — Troubleshooting

Issue-derived leads are lower trust; confirm against source/live before stating
them as fact. Always re-probe the host first (`scripts/boltz_env_probe.py`).

## Install / import

- **`pip install boltz[cuda]` fails / wrong Python:** Boltz needs Python
  `>=3.10,<3.13`. Create a clean env (`scripts/install_boltz.sh --yes --python 3.10`).
- **Torch/CUDA mismatch:** ensure the env's Torch CUDA build matches the driver.
  `scripts/boltz_env_probe.py --deep` reports `torch`, `cuda_build`,
  `cuda_available`. If `cuda_available=false`, you'll fall back to slow CPU.

## Kernel errors (cuEquivariance)

- Symptom: a `cuequivariance` / kernel error at prediction time, typically on
  **older** GPUs.
- Fix: add `--no_kernels` (slightly slower; lower-end-hardware fallback).
- Note: on volta (RTX 2080 Ti, cc 7.5) kernels work — `--no_kernels` not needed.
  Don't add it reflexively; it costs speed.

## Out of memory (CUDA OOM)

VRAM scales with system size. To fit:
- lower `--diffusion_samples` (e.g. 1) and `--max_parallel_samples`;
- lower `--sampling_steps` / `--recycling_steps`;
- split the input or reduce complex size;
- try `--no_kernels` (different memory profile);
- use a bigger-VRAM GPU. No official size→VRAM table exists.

## MSA server (`--use_msa_server`)

- **Network/timeout/rate-limit:** the public ColabFold API can be down or
  throttled. Retry later, or generate a custom MSA offline and reference it in
  the YAML (drop `--use_msa_server`).
- **Auth errors:** set `--msa_server_username/--msa_server_password` (or
  `BOLTZ_MSA_USERNAME/PASSWORD`), or API key via `--api_key_header/--api_key_value`
  (or `MSA_API_KEY_VALUE`). Only one auth method at a time.
- **Privacy:** never send confidential sequences to the public server.

## Input / schema errors

- **Mixed MSA:** can't mix custom and auto MSA in one input — pick one.
- **Ligand both `smiles` and `ccd`:** provide exactly one.
- **`force: true` template without `threshold`:** add `threshold`.
- **Bad bond/contact atom names:** `ATOM_NAME` must be the standardized CIF atom
  name; `RES_IDX` is 1-based (1 for a ligand).
- **SMILES geometry/stereo:** RDKit builds the 3D conformer; bad stereo in →
  bad pose out. Sanity-check the SMILES.

## Affinity errors

- **Rejected ligand:** >128 atoms (heavy + RDKit-kept H) is unsupported. Reduce
  or skip affinity for that ligand.
- **Unreliable but no crash:** binder not a ligand chain, or target is RNA/DNA/
  co-factor — output is not trustworthy; don't report it.
- See `06_affinity_workflow.md`.

## Caching / reruns

- Boltz reuses processed files + existing predictions in the out_dir unless you
  pass `--override`. If results look stale after a parameter change, add
  `--override` (or use a fresh out_dir).
- Weights re-downloading every run → set `$BOLTZ_CACHE` to a persistent absolute
  path.
