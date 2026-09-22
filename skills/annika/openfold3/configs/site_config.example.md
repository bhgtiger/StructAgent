# OpenFold3 site config — example-hpc (validated EXAMPLE, sanitized)

This is a filled example of `site_config.template.md`. It was filled from a probe, an install and a GPU validation on a
Slurm HPC site with A100-SXM4 40 GB and H100 94 GB nodes (validated 2026-09-22). The measured values are real. Paths,
account and partitions are replaced with placeholders. Do **not** use this file as your config: copy the template to
`site_config.local.md` (git-ignored) and fill it on your own host. The measured numbers are summarized in
`references/09_validation_and_benchmarks.md`.

```yaml
host:            example-hpc                 # Slurm cluster: login + CPU build nodes + A100 and H100 GPU nodes
date_probed:     2026-09-22
state:           VALIDATED                   # GPU fixture + full mode matrix passed on both cards

runtime:
  route:         container
  container_runtime: apptainer 1.5.3
  image:         /path/to/containers/openfold3-kit.sif      # 9 583 616 000 bytes
  image_sha256:  <sha256 of your .sif>   # the example site's value is not reusable
  image_recipe:  "kit Dockerfile replayed as Bootstrap: docker (no Docker daemon), kit apptainer.def sections merged"
  base_image:    nvidia/cuda:12.8.1-devel-ubuntu22.04@sha256:a99a1860ba8e2916e5c3e73b72ec4c4301653a84586e05bfc9a2aa2d58027e97
  env_prefix:    n/a
  kit_cli:       openfold3-kit      # /path/to/bin/openfold3-kit -> apptainer run ... <sif> "$@" (= run.sh)
  stock_cli:     run_openfold       # /path/to/bin/run_openfold  -> apptainer exec ... <sif> /usr/local/bin/run_openfold "$@"
  in_image_paths: /usr/local/bin/run_openfold, /kit/openfold3_ob0, /kit/common/opt_core,
                  /kit/openfold3_ob0/stock/src/examples/example_inference_inputs/
  openfold3:     0.5.0              # unmodified bundled wheel
  pin_check:     rc 0, 427/427 package files
  kit:           openfold3_ob0
  kit_commit:    f4f62fa6592ae4938d49b1757bea0cfeff9f468e   # anthropics/uplifting-biomolecular-modeling
  stack:         CPython 3.11.5 / torch 2.10.0+cu128 / triton 3.6.0 / deepspeed 0.19.2 / cuequivariance 0.10.0 /
                 pytorch-lightning 2.6.5 / numpy 2.4.6 / rdkit 2025.9.3 / biotite 1.6.0; gcc 11.4.0 + nvcc 12.8.93 in image
  ds4sci_archs:  sm_80 + sm_90      # kit Dockerfile default is 9.0 only; op is OFF in stock config and every mode
  run_flags:     --nv (GPU nodes only) --no-mount hostfs --cleanenv --bind <shared filesystem>

weights:
  OPENFOLD_CACHE: /path/to/openfold3_cache
  checkpoint:    /path/to/openfold3_cache/of3-ob-2025-06-30-174k.pt   # OPENFOLD3_OB0_CKPT (wrapper default)
  bytes:         2287872989
  sha256_verified: yes              # bd43301c011d5f87580d3e8b548658869433e4488399feb03035ba248f8e29e4 (kit "WEIGHTS OK" + sha256sum -c)
  ckpt_root:     present            # 36-byte text pointer to the same directory
  runner_yml_in_cache: none
  ccd_installed: yes                # full components.bcif (63 393 643 B) written into the image's biotite at build time

compute:
  driver:        595.91.07
  cuda_driver_api: "13.2"
  cuda_runtime:  "12.8"
  cards:
    - name:      NVIDIA A100-SXM4-40GB
      vram_gb:   40
      compute_cap: "8.0"
      kit_config: a100
      gpus_per_node: <int>
    - name:      NVIDIA H100 (95 830 MiB)
      vram_gb:   94
      compute_cap: "9.0"
      kit_config: h100
      gpus_per_node: <int>
  cpu_only_nodes: login and build nodes; kit check there -> DRY-RUN ... gpu=none, rc 0 (not a GPU proof)

scheduler:
  type:          slurm
  account:       <site_account>
  gpu_partitions: {a100: <gpu_partition_a100>, h100: <gpu_partition_h100>}
  per_gpu:       {a100: "<cpus> / <mem>", h100: "<cpus> / <mem>"}
  submit_flags:  sbatch --export=NONE -A <site_account> -p <gpu_partition_h100> -N 1 -n 1 --gpus=1 --cpus-per-task=<cpus> --mem=<mem> -t 01:00:00
  build_node:    "<cpu_build_partition>, <n> CPUs, node-local tmp; apptainer build --fakeroot took 27 min"
  job_template:  /path/to/openfold3_predict.sbatch   # local copy of templates/slurm_predict.sbatch.template

caches:
  policy:        node-local, per job, deleted at job end; never in home (inode-limited)
  where_set:     wrappers (refuse any cache path under $HOME) + job script (TMPDIR=/tmp/<job>/tmp)
  MODEL_OPT_JIT_ROOT: ${TMPDIR}/openfold3_kit_jit-uid<uid>
  others: >-
    TRITON_CACHE_DIR / TORCH_EXTENSIONS_DIR = <root>/<stack key>/{triton,torch_extensions}
    (stack keys torch2.10.0-cu128-sm80 / -sm90; stock CLI uses <root>/stock/);
    XDG_CACHE_HOME (weights digest memo), OPT_CORE_VERDICT_DIR, NUMBA_CACHE_DIR, CUDA_CACHE_PATH under <root>;
    APPTAINER_TMPDIR / APPTAINER_CACHEDIR node-local in job scripts
  measured:      668–1 013 files / 40–65 MB per job; first fast call +22–39 s; image carries no pre-filled JIT tar
  home_quota_note: "inode-limited home; a home cache would retain 668-1 013 files per job-sized card/stack cache"

msa:
  default_strategy: single-sequence (--use-msa-server false), always passed explicitly
  server_url:    https://api.colabfold.com (upstream default ON; both wrappers preserve that default)
  wrappers_preserve_upstream_default: true
  privacy_note:  "unpublished sequences never go to the public server; ask before any --use-msa-server true"
  precomputed_msa_tested: no

modes:   # evidence: 12-input ladder 13 -> 995 polymer residues (52 -> 995 model tokens; 9 upstream example queries +
         # 3 public 1BRS assemblies), both cards, single-sequence, no templates, 218/218 calls rc 0, no OOM
  stock_cli:     {state: VALIDATED, evidence: "ubiquitin, rc 0, 5 models; 57.2 s A100 / 45.4 s H100 whole call (shipped preset)"}
  kit_off:       {state: VALIDATED, evidence: "full ladder, both cards"}
  kit_exact:     {state: VALIDATED, evidence: "full ladder; warm wall 1.12-1.40x A100 / 1.11-1.37x H100 vs off"}
  kit_exact_det1: {state: VALIDATED, evidence: "byte-identical to off --det 1: 60/60 model/confidence file pairs, 13-residue (52-token) DNA + 508-residue inputs, both cards"}
  kit_fast:      {state: VALIDATED, evidence: "runs; warm wall 1.24-2.13x / 1.21-1.83x; fidelity NOT calibrated vs stock seed spread"}
  kit_big_below_gate: {state: VALIDATED, evidence: "same confidences and CA RMSD as fast on every tested input (all below the 1 401-polymer-token gate)"}
  kit_big_at_or_above_gate: {state: UNTESTED, evidence: "no input >= 1 401 polymer tokens"}
  kit_big_n_gpu: {state: UNTESTED, evidence: "--n_gpu 2/4/8 not run"}
  stock_cli_with_OPENFOLD3_OB0_OPT: {state: VALIDATED, evidence: "OPENFOLD3_OB0_OPT=fast: rc 0, 5 models, ACTIVE/LEVER lines, stock output tree; env route has no exit rule"}
  templates:     {state: UNTESTED, evidence: "no template-bearing input"}
  msa_server:    {state: UNTESTED, evidence: "all runs --use-msa-server false"}
  max_tokens_tested: {a100: 995, h100: 995}

default_command: |
  openfold3-kit pred --config <a100|h100> --mode exact --use-msa-server false \
      --query-json /abs/path/query.json --output-dir /abs/path/out
  # add --det 1 when byte reproducibility vs stock matters (about stock speed); fast = explicit throughput choice

notes: |
  - 995-token warm calls (wall / forward s): A100 off 136.946/77.81, exact 97.870/45.55, fast 68.975/13.93,
    big 68.579/13.97; H100 off 95.241/47.61, exact 69.347/27.60, fast 52.667/8.74, big 54.051/8.74.
    Peak device memory off -> fast: A100 24 844 -> 13 662 MiB; H100 25 053 -> 13 701 MiB (1 Hz nvidia-smi).
  - fast vs off top-model CA RMSD reached 29.4 / 29.9 A (A100 / H100) on low-confidence single-sequence inputs:
    not an accuracy statement either way. Confidence values here are not representative of MSA-backed runs.
  - rc 3 (NOT ACTIVE / pins) and rc 5 (TEMPLATES DROPPED) are results: job scripts never use set -e around calls.
  - The image is read-only: --output-dir must be on the bound shared filesystem; --query-json must be absolute.
  - If a site overlays host directories into containers (hostfs), shadowing the image's /opt, pass --no-mount hostfs.
  - Wrappers forward OPENFOLD3_OB0_OPT*, OF3TP_*, OF3O_*, MODEL_OPT_*, TRITON_*, CUDA_*, SLURM_* by prefix
    via APPTAINERENV_ under --cleanenv, clearing inherited APPTAINERENV_/SINGULARITYENV_ copies first.
  - A100 40 GB has less headroom than the kit's 80 GB-derived multi-GPU chunk plan. Documented OOM escalation
    fast -> big -> big --n_gpu P is untested here; below the gate big == fast and will not rescue an OOM.
  - Bare `run_openfold --help` printed only --disable-cutlass-package-imports on a GPU node; use `run_openfold predict --help`.
  - Startup + checkpoint load dominate small inputs: 76-token ubiquitin took 34-53 s per warm whole call
    (forward pass only 3-17 s) on either card. Batch queries/seeds per call to amortize it.
  - "libfakeroot internal error: payload not recognized!" during the fakeroot build was harmless.
```
