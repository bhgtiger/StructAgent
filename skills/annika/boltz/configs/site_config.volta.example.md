# Boltz site config — volta (validated EXAMPLE)

Filled from a live probe + fixture on `volta` on 2026-06-23. Shipped as an
*example* of a completed config. The active local copy is `site_config.local.md`
(git-ignored); regenerate it if the env changes.

```yaml
host:            volta
date_probed:     2026-06-23
state:           VALIDATED          # boltz + weights present; fixture passed

boltz:
  env_path:      /soft/anaconda-new/envs/boltz2
  run_prefix:    /soft/anaconda-new/envs/boltz2/bin/boltz
  version:       2.2.1
  python:        3.10.19

compute:
  torch:         2.10.0+cu128
  cuda_build:    12.8
  gpus:          2x NVIDIA GeForce RTX 2080 Ti, 11 GB each
  compute_cap:   7.5                 # Turing
  kernels_ok:    true                # cuEquivariance kernels run; --no_kernels NOT needed
  cpu_only:      false

cache:
  BOLTZ_CACHE:   (unset -> ~/.boltz)
  weights_present: true              # boltz2_conf.ckpt (~2.3G), boltz2_aff.ckpt (~2.1G), mols/ present (~7.6G total)

msa:
  default_strategy: use_msa_server   # for public seqs; use custom MSA for confidential
  msa_server_url:   https://api.colabfold.com
  privacy_note:     "do NOT send unpublished sequences to the public ColabFold server"

notes: |
  Validated with: boltz predict <yaml> --recycling_steps 1 --sampling_steps 25
    --diffusion_samples 1 --output_format pdb --seed 42   (Trp-cage, msa: empty)
  -> exit 0, ~5 s inference on 1 GPU; output tree + confidence JSON as documented.
  11 GB VRAM: fine for small/medium; large complexes may OOM -> lower
  diffusion_samples / max_parallel_samples / sampling_steps or split input.
  Two GPUs available: --devices 2 for batches of inputs.
```
