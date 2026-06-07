# 07 — CryoSPARC & HPC integration (cautions; no auto-writes)

Source: CryoSPARC's DeepEMhancer wrapper docs (`guide.cryosparc.com/.../job-deepemhancer-wrapper`) and general HPC docs (e.g. Biowulf). These are **integration/community** docs — lower trust than pinned source/live help, and **site-specific**. The skill gives **conceptual cautions only** here: it does not auto-create wrapper files, `chmod`, submit `sbatch`/scheduler jobs, run `cryosparcm`, or synthesize module/container commands until a **site config** captures that environment (`references/02`) and the user confirms.

## Non-negotiable cautions

1. **Separate conda environment.** DeepEMhancer must run in its **own** conda environment — **do not install it into, or run it from, CryoSPARC's bundled conda environment.** CryoSPARC does not distribute DeepEMhancer; install it yourself (e.g. `scripts/setup_deepemhancer_env.sh`, `references/09`) into a standalone env.
2. **Executable path symmetry (master ↔ workers).** The **same** `deepemhancer` executable path must resolve identically on the CryoSPARC **master and every worker** that may run the job. A path that exists only on the master (or only on the submitting node) will fail on workers. Record the intended path in the site config and verify it on each node before integrating.
3. **Models reachable on the execution node.** The model directory (or `--deepLearningModelPath`) and its `.hd5` files must exist and be readable on whatever node actually runs DeepEMhancer — not just where you tested interactively.
4. **GPU/driver parity.** Worker nodes that run the job need a compatible NVIDIA GPU + driver + the env's CUDA/TensorFlow stack. Mismatch ⇒ the same TF/CUDA failures as `references/06`; treat as config `blocked` until verified per node.
5. **Optional wrapper script.** CryoSPARC docs describe an optional wrapper script to isolate the environment (e.g. activate the right conda env, then exec `deepemhancer`). The skill may **describe** this concept, but must **not auto-create or `chmod`** such a script without a captured site config and explicit user confirmation.

## What requires a site config before any concrete command

- Scheduler/module/container commands (Slurm `sbatch`, `module load`, Singularity/Apptainer) are **site-specific** and must not be synthesized from Biowulf or other examples. Biowulf's captured help is also **version-skewed (module 0.13)**. Capture the real site environment first.
- The CryoSPARC job's "executable path" and "wrapper path" fields must come from the verified, path-symmetric install — not a guess.

## Conceptual planning block (concept, not a command)

```text
[config-state: ready-or-partial]
# Concept, not a command to run:
#   * Install DeepEMhancer in a conda env SEPARATE from CryoSPARC's.
#   * Ensure `deepemhancer` resolves at the SAME path on master + all workers.
#   * Ensure model .hd5 files are readable on the execution node.
#   * In the CryoSPARC DeepEMhancer job, point the executable (or wrapper) at that path.
# Exact scheduler/module/wrapper lines need a captured SITE config (references/02) first.
```

## Staleness note for HPC/CryoSPARC

Per `references/02`, HPC/CryoSPARC-wrapper planning uses the **tighter 24-hour** staleness window (vs 14 days for general advice). If the site config is older than 24 h — or the node/path/env changed — treat it as `stale` and re-probe on the actual execution node before giving integration advice.
