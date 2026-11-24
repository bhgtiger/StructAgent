# CryoCodex site config — <host> (private, host-local; copy to configs/site_config.local.md and fill from the probe)
# configs/site_config.local.md is git-ignored: it holds real paths and accounts. Never commit or publish it.
# scripts/cryocodex_env_probe.py reads the top-level keys below and weights.sha256.

host:            <cluster / workstation name; node types; GPU models>
date_probed:     <YYYY-MM-DD>
date_validated:  <YYYY-MM-DD or empty>
state:           UNCONFIGURED | PROBED | VALIDATED      # VALIDATED only after the runbook's R11 + R12 passed on THIS host
home:            </abs/path/to/CryoCodex>                # the clone; the probe uses it when --home is not given
env:             cryocodex_env                           # conda env name (CRYOCODEX_ENV if not the default)
env_prefix:      </abs/path/to/env or empty>             # site route: env by path (probe --env-prefix reads this)
launcher:        </abs/path/to/site launcher or empty>   # site route: wrapper around predict.py (references/02 section 2b)
conda_exe:       </abs/path/to/bin/conda>                # if conda is not on PATH as an executable
site_env_cmd:    <what makes conda visible in a batch job, e.g. "source /abs/miniconda3/etc/profile.d/conda.sh">
pythonnousersite: <yes: export PYTHONNOUSERSITE=1 for installs and runs (the launcher sets it); note any ~/.local packages>

clone:
  commit:        a35e73a72f9cbc2b13cf6f8d95cf963cb704ca17   # v1.0.0; change only after re-review (references/maintenance.md)
  installed:     <date; README route; any deviation, e.g. torch from the cu124 index>
  stack:         <python, torch (+CUDA build), torchvision, mrcfile, numba, numpy, scipy, timm versions (runbook R5)>

weights:
  path:          <home>/model_state_dicts/CryoCodex.pth
  bytes:         470938660                               # server HEAD 2026-11-24
  sha256:        <from probe --hash / runbook R8; reference value on the first validated host: dfb814c63ed2dbdca99d0e3803e408d88775217a48d72a4fbb60618f8feda380>
  safe_load:     <weights_only=True load passed? yes/no (runbook R8)>
  obtained:      <date; downloaded by predict.sh | curl by hand | copied from another host (which)>

compute:
  driver:        <nvidia driver>
  cards:         [{name: <GPU>, vram_gb: <n>, batch_tested: <n>, peak_gpu_mib: <n>, state: VALIDATED | UNTESTED}]
  cpu_only_nodes: <login/CPU nodes: only -h, header inspection, command drafting>

scheduler:
  type:          slurm | none | other
  account:       <account, or "none needed">
  submit:        <sbatch flags for one GPU, e.g. --gpus=1 or --gres=gpu:1 (builder --gres)>
  gpu_fencing:   <yes (cgroups: the job sees one GPU as 0) | no (nvidia-smi lists all cards; CUDA_VISIBLE_DEVICES = global index)>
  gpu_selection: <runbook R16c result: does -g "${CUDA_VISIBLE_DEVICES:-0}" land on the assigned GPU?>
  network_on_compute_nodes: <yes/no (weights must be pre-placed if no)>
  outputs:       <where outputs may live>

validation:    # fill from the runbook; keep dates, wall times, peak memory, deviations
  fixture:       EMD-10387 (150^3 @ 1.043 A)
  R11_default:   {state: UNTESTED}      # expected (derived): 4 maps, 1.0 A, crop 48..156 per axis
  R12_keep_rev:  {state: UNTESTED}      # expected (derived): 150^3 at 1.043 A, NSTART 0
  R13_normal:    {state: UNTESTED}
  R15_cropcheck_no_tty: {state: UNTESTED}
  R16_gpu_selection:    {state: UNTESTED}
  peak_host_rss_gb: <n>
  wall_s:        <n>

untested:
  - --crop_check True interactively through conda run (R15d)
  - maps with ORIGIN and NSTART both non-zero
  - stride other than 12; batch other than the tested one
  - Scipion plugin route (not in v0)

expires_when:  <clone commit / weights / env / driver change, or 90 days after date_validated>
