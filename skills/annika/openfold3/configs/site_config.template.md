# OpenFold3 site config — TEMPLATE

This template lives in the public package. Keep your copy of it out of the package:

1. Copy this file to `configs/site_config.local.md`. That file must be git-ignored and must never be pushed.
2. Fill it on the target host from a fresh `scripts/openfold3_env_probe.py --json` run, plus the verification table in
   `references/02_install_and_environment.md`.
3. Use one file per host or cluster. For a filled, sanitized reference, see `site_config.example.md`.

This file is the skill's warm-start memory. It lets a new session emit concrete commands without re-deriving the
environment. **It expires.** Re-probe and rewrite it, dropping `state` back to `PROBED` until re-verified, when any of
these happens:
- the image sha256, the venv, `openfold3` version or kit commit changes;
- the driver or CUDA version changes;
- the checkpoint path or its sha256 changes;
- a new card type or partition is added;
- the wrappers change;
- `date_probed` is more than 90 days old.

Never copy a filled file into the public package. It holds real paths, account names and partitions.

State meanings (the state machine of SKILL.md and `references/00_scope_and_trust.md`):

| State | Meaning |
|---|---|
| `UNCONFIGURED` | No probe yet. Give explanations and templates only |
| `PROBED` | Probe ran and the fields below are filled, but the GPU fixture has not passed. Concrete commands are allowed; run nothing without consent |
| `VALIDATED` | The GPU fixture passed on each listed card. May run jobs after explicit per-action confirmation |

The probe's `verdict` describes the host, not this file: `UNCONFIGURED` (no runtime found there), `PROBED` (blockers
remain) and `VALIDATED-CANDIDATE` (runtime + OpenBind-0 checkpoint + GPU route, no blockers) are all recorded here as
`PROBED`. Only a passed GPU fixture moves `state` to `VALIDATED` (`references/00_scope_and_trust.md`).

```yaml
host:            <cluster or hostname>
date_probed:     <YYYY-MM-DD>
state:           <UNCONFIGURED | PROBED | VALIDATED>
probe_version:   <scripts/openfold3_env_probe.py version or date>

runtime:
  route:         <container | venv | docker | pixi>        # container = Apptainer/Singularity .sif
  container_runtime: <e.g. apptainer 1.x | docker 2x.x | none>
  image:         <absolute path to .sif, or docker tag@digest | n/a>
  image_sha256:  <sha256 of the .sif | n/a>
  image_recipe:  "<kit apptainer.def | replayed kit Dockerfile (Bootstrap: docker) | upstream Dockerfile.pixi | n/a>"
  base_image:    <e.g. nvidia/cuda:12.8.1-devel-ubuntu22.04@sha256:... | n/a>
  env_prefix:    <venv / pixi env path | n/a>
  kit_cli:       <wrapper name/path that runs kit run.sh | "bash <kit>/openfold3_ob0/run.sh" | none>
  stock_cli:     <wrapper name/path for run_openfold | "run_openfold" on PATH>
  in_image_paths: <e.g. /usr/local/bin/run_openfold, /kit/openfold3_ob0 | n/a>
  openfold3:     <e.g. 0.5.0>                               # installed version; pin check rc?
  pin_check:     <rc 0, N/N files | not run>
  kit:           <openfold3_ob0 | openfold3 (legacy 0.4.1) | none>
  kit_commit:    <uplifting-biomolecular-modeling commit, e.g. f4f62fa…>
  stack:         <python / torch / triton / deepspeed / cuequivariance versions>
  ds4sci_archs:  <e.g. sm_90 | sm_80+sm_90 | not built>     # op is off in stock config + every kit mode
  run_flags:     <e.g. --nv --cleanenv --no-mount hostfs --bind <fs> | n/a>

weights:
  OPENFOLD_CACHE: <absolute path | (unset -> ~/.openfold3)>
  checkpoint:    <absolute path to of3-ob-2025-06-30-174k.pt>   # value of OPENFOLD3_OB0_CKPT
  bytes:         <expect 2287872989>
  sha256_verified: <yes | no>                               # expect bd43301c011d5f87580d3e8b548658869433e4488399feb03035ba248f8e29e4
  ckpt_root:     <present -> <dir> | absent>
  runner_yml_in_cache: <none | path>                        # deep-merged under any --runner-yaml
  ccd_installed: <yes (full components.bcif in biotite, where) | no>

compute:
  driver:        <e.g. 5xx.xx>                              # kit needs >= 570
  cuda_driver_api: <CUDA version nvidia-smi reports>
  cuda_runtime:  <CUDA of the torch build, e.g. 12.8>
  cards:                                                    # one entry per GPU type
    - name:      <e.g. A100-SXM4 40 GB>
      vram_gb:   <int>
      compute_cap: <e.g. 8.0>                               # kit needs >= 8.0
      kit_config: <a100 | h100 | h200 | b200 | b300 | none>
      gpus_per_node: <int>
  cpu_only_nodes: <which nodes have no GPU; kit check there prints gpu=none>

scheduler:
  type:          <slurm | pbs | lsf | none>
  account:       <site_account placeholder or real value in the local copy>
  gpu_partitions: {<card>: <partition>, ...}
  per_gpu:       {<card>: "<cpus> CPUs / <mem>"}
  submit_flags:  <e.g. sbatch --export=NONE -N 1 -n 1 --gpus=1 -t HH:MM:SS>
  build_node:    <partition/node class used for image builds, CPUs, RAM, node-local tmp size>
  job_template:  <path to local copy of templates/slurm_predict.sbatch.template>

caches:
  policy:        <node-local per job | persistent root at <path> | defaults>
  where_set:     <wrapper | job script | shell profile>
  MODEL_OPT_JIT_ROOT: <path or pattern>
  others:        <TRITON_CACHE_DIR, TORCH_EXTENSIONS_DIR, XDG_CACHE_HOME, CUDA_CACHE_PATH, NUMBA_CACHE_DIR, OPT_CORE_VERDICT_DIR>
  home_quota_note: "<e.g. inode-limited home, never cache there>"

msa:
  default_strategy: <single-sequence (--use-msa-server false) | precomputed | server (public seqs only, approved)>
  server_url:    <https://api.colabfold.com (upstream default ON) | self-hosted URL>
  wrappers_preserve_upstream_default: <true | false>
  privacy_note:  <e.g. "unpublished sequences never go to the public server">
  precomputed_msa_tested: <yes | no>

modes:                                                      # VALIDATED | UNTESTED | FAILED, with evidence pointer
  stock_cli:     {state: <>, evidence: <date, card, input, rc, outputs>}
  kit_off:       {state: <>, evidence: <>}
  kit_exact:     {state: <>, evidence: <>}
  kit_exact_det1: {state: <>, evidence: "<byte-identical to off --det 1? file pairs, tokens, cards>"}
  kit_fast:      {state: <>, evidence: <>}
  kit_big_below_gate: {state: <>, evidence: <>}             # below 1 401 polymer tokens big == fast
  kit_big_at_or_above_gate: {state: <>, evidence: <>}
  kit_big_n_gpu: {state: <>, evidence: <P tested>}
  stock_cli_with_OPENFOLD3_OB0_OPT: {state: <>, evidence: <>}
  templates:     {state: <>, evidence: <>}
  msa_server:    {state: <>, evidence: <>}
  max_tokens_tested: <int per card>

default_command: |
  <the one command this site should emit by default, with placeholders for query/output>

notes: |
  <host-specific facts: mount quirks, OOM ceilings observed, first-call JIT cost,
   measured timings (card + tokens + mode), known refusals, rc 3/5 handling, open items>
```
