# CryoFM2 site config — example-hpc (validated EXAMPLE, sanitized)

This is a filled example of `site_config.template.md`. It was filled from a probe, a container build, a weights fetch and
a GPU validation on a Slurm HPC site with A100-SXM4 40 GB and H100 94 GB nodes (validated 2026-10-08). The measured
values, job ids, digests, card and driver are real. Paths, account, partitions, node names and user names are replaced
with placeholders (`<HOME>`, `<account>`, `<partition_a100>`, …). Do **not** use this file as your config: copy the
template to `site_config.local.md` (git-ignored) and fill it on your own host. The measured numbers are summarised in
`references/09_evidence_and_benchmarks.md`; `state:` of a mode is only what a GPU log proves.

```yaml
host:            example-hpc                 # Slurm cluster: login nodes (no GPU) + CPU partitions (staging, build) + A100 and H100 GPU nodes
date_validated:  2026-10-08
state:           VALIDATED (A100; H100 untested)
activation:      source <HOME>/structbio/activate.sh      # puts <HOME>/structbio/apps/bin (cfm, cfm-relion) on PATH
                 # inside every Slurm job too: jobs are submitted with --export=NONE. No `set -u` after sourcing it.

runtime:
  route:         container (Apptainer 1.5.4)
  image:         <HOME>/structbio/containers/cryofm2.sif        # 4 580 081 664 B
  image_sha256:  5170640312574b14c9bd07e7a86c329c68dfa25730731107818b66bce4d896b4
  image_def:     <HOME>/structbio/containers/cryofm2.def         # python:3.10.19-slim-bookworm @ sha256:23f63358…; apt libgl1 libglib2.0-0
  source:        ByteDance-Seed/cryofm main 64486814723010bd200525cda2fa463a25ba1339 (2026-03-03, no tags)
                 trimmed git archive cryofm_6448681_trimmed.tar.gz
                 sha256 0f2e942a3e7b313d6662a68c0f73ce9d46839e618a102d5cb2d21e9e785f5438 (website/assets/images removed)
  lock:          requirements.lock.txt   # uv pip compile --generate-hashes --exclude-newer 2026-03-04; 113 wheels
  stack:         python 3.10.19 · torch 2.10.0+cu128 · diffusers 0.36.0 · mmengine 0.10.7 · mmcv-lite 2.2.0 · accelerate 1.12.0
                 lightning 2.6.1 · numpy 1.26.4 · mrcfile 1.5.4 · starfile 0.5.13 · safetensors 0.7.0 · scipy 1.15.3 · opencv-python 4.11.0.86
                 (live check 2026-10-08: `apptainer exec --no-mount hostfs cryofm2.sif python -c "import cryofm, torch…"`)
  in_image:      /usr/local/bin/cfm, /usr/local/bin/accelerate, /opt/cryofm (source incl. relion/relion_wrapper.py), /opt/cryofm/pip-freeze.txt
  image_env:     PYTHONNOUSERSITE=1 MPLBACKEND=Agg HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 WANDB_MODE=disabled CRYOFM_SRC=/opt/cryofm
  not_in_image:  weights (external), CryoFM1 weights (never fetched), natten / flash_attn (CryoFM1 HDiT only; CryoFM2 does not need them)
  build:         job 27771682 (CPU build partition, 6 m 46 s) via a build sbatch; two failed attempts
                 (27767838 hash-mode extras → --no-deps; 27768152 libGL.so.1 → apt libgl1) are recorded in the install notes

launcher:        <HOME>/structbio/apps/bin/cfm   (mode 0750; cfm-relion -> cfm symlink)
  behaviour: |
    - exits 127 if the image is missing; exits 1 early if `--model-dir <x>` has no model.safetensors + config.yaml
      (message points at the fetch script)
    - `--model-dir pretrain|emhancer|emready` and `cryofm2-pretrain|…` resolve to <HOME>/structbio/cryofm_cache/cryofm-v2/cryofm2-<name>;
      `--model-dir=<x>` form also resolved; any other value is passed through unchanged as a path
    - invoked as `cfm-relion`: runs `python /opt/cryofm/relion/relion_wrapper.py "$@"`, resolving CRYOFM_MODEL_DIR shorthand the same way
    - --nv only when /dev/nvidiactl or /dev/nvidia0 exists (override: CFM_FORCE_NV=1 / CFM_NO_NV=1) → `cfm --help` works on CPU nodes
    - apptainer exec [--nv] --no-mount hostfs -B <shared filesystem> -B $RUNTMP:/rwcache  (RUNTMP = ${TMPDIR:-/tmp}/cfm-$USER-$$, removed on exit)
      --env MPLCONFIGDIR=/rwcache/mpl HF_HOME=/rwcache/hf TRITON_CACHE_DIR=/rwcache/triton TORCHINDUCTOR_CACHE_DIR=/rwcache/inductor
      XDG_CACHE_HOME=/rwcache/xdg PYTHONNOUSERSITE=1
    - --no-mount hostfs is required on this site (the host overlays /opt); only $HOME, $PWD, the shared filesystem and the
      apptainer.conf bind paths (node-local and shared scratch) are visible inside: give absolute paths under those trees
    - the launcher does not touch argv otherwise: `--num_processes N` after the subcommand reaches upstream `cfm` unchanged

weights:
  dir:           <HOME>/structbio/cryofm_cache/cryofm-v2        # 1.9 GiB; pin file ../weights.pin.json (verified 2026-10-08)
  revision:      4e308f7f028af46ca2c7ee5af81e29775bc370dd           # huggingface.co/ByteDance-Seed/cryofm-v2 main, apache-2.0, not gated
  files: |
    cryofm2-pretrain/model.safetensors  672 397 148 B  sha256 8f10dc552fceedae8a3c574e9b9d259de7d1f5047f4f2107d9309fae9512f413
    cryofm2-emhancer/model.safetensors  672 409 268 B  sha256 96576420fe03fc93088b40fdb1e7f785d100e6ed49833050c961670bdfaee163
    cryofm2-emready/model.safetensors   672 409 268 B  sha256 77c1fa590eaee1906e8470d3659c981855a92fcf4e6a7817b48f0069cd6d2bca
    <variant>/config.yaml (1148 / 1240 / 1237 B), root config.yaml (674 B, variant manifest read by no code), README.md
  verify:        bash <install dir>/fetch_cryofm2_weights.sh verify     # sha256 (LFS) + git blob ids; rc 0 = all ok
  fetch:         bash <install dir>/fetch_cryofm2_weights.sh            # login node OK (plain HTTPS, resumable)
  cryofm-v1:     not installed (would need natten for HDiT; out of scope)

compute:
  driver:        615.71.09 (GPU node, 2026-10-08)   # torch 2.10.0+cu128 needs ≥ 525; A100 cc 8.0 supports bf16
  cards:
    - {name: "NVIDIA A100-SXM4-40GB", partition: <partition_a100>, per_gpu: "18 CPUs / 120G", state: VALIDATED}
    - {name: "NVIDIA H100 94 GB",     partition: <partition_h100>, per_gpu: "16 CPUs / 160G", state: UNTESTED}
  cpu_nodes:     login, staging, CPU and build partitions — `cfm --help`, module `--help`, inspect/check scripts only;
                 the wrapper prints `UserWarning: CUDA is not available … Disabling autocast` there (harmless)

scheduler:
  type:          slurm
  account:       <account>        # GPU budget checked with the site's accounting command
  submit:        sbatch --export=NONE -A <account> -p <partition_a100> -N 1 -n 1 --gpus=1 --cpus-per-task=18 --mem=120G -t 01:00:00
  job_template:  templates/slurm_cfm.sbatch.template     # pattern = the smoke job script (ran rc 0 as job 27772096); never submitted as-is
  tmpdir:        <node-local scratch>/$USER/cfm-$SLURM_JOB_ID (node-local; the launcher derives /rwcache from TMPDIR)
  outputs:       <shared scratch>/$USER/… (purged after ~14 days) or a project path on the shared filesystem; never under $HOME (1M-inode quota)

validation:   # job 27772096, A100 partition, COMPLETED 0:0, 8 m 32 s wall
  fixture:       EMD-11638 (mouse apoferritin, 1.22 Å) primary + both half maps, 256³ @ 0.5332 Å, origin 0 →
                 <install dir>/fixture_emd11638/ (gzipped, SHA256SUMS); resamples to 92³ at ≈1.484 Å → 8 patches → 2 batches
  denoise:       {state: VALIDATED, cmd: "cfm denoise -i1 h1 -i2 h2 -o OUT --model-dir pretrain --op denoise --norm-grad --use-lamb-w --bf16 --seed 0",
                  wall_s: 251, outputs: "emd_11638_half_map_1_external_reconstruct.mrc, …_2_…, avg_external_reconstruct.mrc", grid: "256³ @ 0.5332, origin 0"}
  emhancer:      {state: VALIDATED, cmd: "cfm enhance -i map -o OUT --model-dir emhancer --output-tag 1 --bf16 --seed 0", wall_s: 121}
  emready:       {state: VALIDATED, cmd: "cfm enhance -i map -o OUT --model-dir emready --output-tag 0 --cfg-weight 0.5 --bf16 --seed 0", wall_s: 119}
  peak_gpu_mib:  21443   # nvidia-smi memory.used at 2 Hz, device level, batch 4 + bf16 (docs table says 21G)
  per_batch_s:   ≈54 (denoise, 200 steps, 4 patches) · ≈50 (enhance, CFG = 2 forwards/step)
  lowpass_cc:    # job 27772406 (CPU staging partition), lowpass_cc.py: CC vs input low-passed to 3.5 / 6 Å; mask = top-25 % voxels of the 8 Å map
    half_avg_input: 0.993 / 0.999       denoise avg: 0.986 / 0.997       denoise half1: 0.987 / 0.997
    emhancer: 0.952 / 0.796             emready: 0.705 / 0.806           axis-permuted control: 0.34–0.42
    denoised-halves FSC per shell equals the input halves' (1.000 → 0.999 down to 3.0 Å): the two outputs are NOT independent
  raw_cc_note:   whole-spectrum CC vs the 0.53 Å input is only ≈0.30 because the output is band-limited at ≈3 Å (expected, not a defect)
  help_capture:  2026-10-08, CPU staging node: `cfm --help`, `cfm denoise --help`, `cfm enhance --help`,
                 `python -m cryofm.projects.cryofm2.{uncond,cond}_sampling --help` all rc 0 and identical to references/03
  relion_wrapper_help: `python /opt/cryofm/relion/relion_wrapper.py --help` on a CPU node → endless accelerate self-relaunch,
                 SIGKILL by `timeout`, squashfuse torn down ("Transport endpoint is not connected"). Never do this (lessons.md)

untested:   # do not claim these; ask before a first run and record the result here
  - --op inpaint / denoise inpaint with a real RELION particle STAR (back-projection memory, --fmask-threshold)
  - --op non-uniform (host RAM ≈ 64 MiB per patch per process for the wavelet stacks)
  - cfm enhance with -i1/-i2 (conditional posterior sampling) and -i + -i1/-i2
  - --mask-path + --bbox, --spectral-mixing, --fsc-weighting, --num-timesteps ≠ 200, --batch-size ≠ 4
  - --num_processes > 1 (accelerate multi-GPU inside the container; --fsc-weighting barrier hazard)
  - cfm-relion inside relion_refine_mpi (no RELION installed on this site); H100

guidance:
  default_denoise: "cfm denoise -i1 /abs/h1.mrc -i2 /abs/h2.mrc -o /abs/NEW --model-dir pretrain --op denoise --norm-grad --use-lamb-w --bf16 --seed 0"
  default_enhance: "cfm enhance -i /abs/map.mrc -o /abs/NEW --model-dir emhancer --output-tag 1 --bf16   |   --model-dir emready --output-tag 0 --cfg-weight 0.5 --bf16"
  batch_size:    "4 on A100 40 GB (21.4 GB measured); drop to 2 only if a bigger box or non-uniform OOMs; the FAQ table is per GPU"
  sizing:        "patches = (ceil((S-64)/32)+1)^3 with S = even round(box·apix/1.5); batches = ceil(patches/4); ≈54 s per batch per half on A100"
  after_run:     "python3 scripts/check_cfm_output.py OUT --input /abs/h1.mrc ; restore_origin.py if the input NSTART/ORIGIN was non-zero"

agent_rules:
  - Check context first: hostname; echo ${SLURM_JOB_ID:-no-slurm-job}; squeue --me; the site's budget and quota commands
  - Login nodes: edit, read small logs, prepare inputs, submit. No sampling, no long Apptainer runs there.
  - ASK before spending GPU allocation (every submission), multi-hour jobs, downloading weights, deleting installs/containers/weights/results.
  - Before: verify input paths and headers (inspect_map.py), fresh output path, partition, walltime. During: squeue --me, run.log. After: record command, job id, rc, outputs.

ledger: |
  Real runs use the annika-log layout where it exists: `annika_log.py new <project> <short_name>` -> Job_NNN_<short_name>/ with the sbatch in scripts/,
  stdout/stderr in log/, a NEW -o directory under output/, parameters.json (mode, op, model, batch, steps, seed, image sha256, job id, rc),
  decisions.md (the user's GPU go-ahead), then `annika_log.py close`.

evidence:
  install:    the site's install report and install folder (SOURCE.txt, build/smoke sbatch, fetch script, lowpass_cc.py, lock file, fixture)
  logs:       cryofm2_smoke_27772096.txt, cryofm2_lowpass_cc_27772406.txt, cryofm2_build.log, cryofm2_weights.log (site log folder)
  outputs:    <shared scratch>/$USER/cryofm2_smoke/27772096/{denoise,emhancer,emready,in}/ (scratch, may be purged)
  evidence_folder: the maintainer's archive, not bundled (references/01 §3)

expires_when: the image sha256, the launcher, the weights or their sha256, the driver, or the partitions change, or after 2027-01-06
              (90 days) — re-probe and drop state to PROBED until a GPU fixture passes again.
```
