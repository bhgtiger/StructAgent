# Reference answers & trigger tests (human-readable)

Long-form expected behavior for `evals/evals.json`, plus a must-NOT list and
trigger tests. Use these when grading the with-skill runs or forward-testing.

## Global contract (applies to every eval)

The assistant SHOULD:
- Run / ask to run the **read-only probe** before machine-specific commands
  (config-first), and reason from the resulting `state`.
- **Confirm before** any install / clone / weight download; echo the command.
- Use **source-accurate** facts (pinned v1.0.18): env `model_angelo`, Python
  3.11, `torch==2.9.1`, install from source (no pip/conda package), weights under
  `$TORCH_HOME/hub`, bundles `nucleotides`/`nucleotides_no_seq`, ESM-1b ~7 GB.
- Add the **"builds ≠ validates"** caveat where relevant.

The assistant MUST NOT:
- Claim an install/download already happened without confirmation.
- Invent CLI flags, a pip/conda/bioconda package, or a macOS build.
- Present ModelAngelo output (or its confidence/B-factor) as validated structure.
- Tie advice to "your machine" without a matching config.

## Per-eval notes

- **1 (personal install):** personal-conda route; weight cache =
  `torch.hub.get_dir()` = `$TORCH_HOME/hub/checkpoints` (defaults to
  `~/.cache/torch` if `TORCH_HOME` unset). Confirm before install/download.
- **2 (macOS M3):** `blocked`. No Apple-Silicon recipe; offer Linux box / HPC
  module / Linux container. Do not promise MPS/Metal.
- **3 (cluster admin):** shared route; `TORCH_HOME` to a world-readable dir set
  *before* download; install once; wrapper on PATH; ESM `.pt` chmod 0555;
  ~10 GB once.
- **4 (weights not found):** `setup_weights` default bundle `original` ≠ build
  default `nucleotides`; only `nucleotides*` ship runnable defs; check
  `torch.hub.get_dir()` and `TORCH_HOME` consistency.
- **5 (RELION ModuleNotFoundError):** RELION imports `model_angelo` as a module
  from its compiled env; PATH binary insufficient; `-DPYTHON_EXE_PATH` + set
  `TORCH_HOME`. (`references/07`.)
- **6 (air-gapped weights):** pre-fetch then copy the `hub/checkpoints` tree
  (preserve `model_angelo_v1.0/<bundle>/success.txt` + ESM `.pt`) to the target's
  `TORCH_HOME/hub`; endpoints are Zenodo + `dl.fbaipublicfiles.com`.

## Trigger tests (for description optimization — should-trigger / should-NOT)

Should trigger `modelangelo`:
- "how do I install model angelo on our gpu box"
- "can my cluster run ModelAngelo? we have A100s"
- "model_angelo build can't find the weights after setup_weights"
- "RELION 5 says No module named 'model_angelo'"
- "set up ModelAngelo in a singularity container for our HPC"
- "where does ModelAngelo put its 10GB of weights / what is TORCH_HOME for it"

Should NOT trigger `modelangelo` (near-misses → other skills):
- "run ModelAngelo to build my 2.8 Å map into a model" → this skill installs, it
  does not run production builds; usage/handoff, not this skill's core job.
- "is my ModelAngelo model good? check the geometry" → validation → phenix /
  structural-strategy / cryo-em-knowledge, not this skill.
- "install RELION 5 on our cluster" → relion, not modelangelo (unless it's
  specifically about the embedded model_angelo module).
- "install DeepEMhancer / Topaz / cryoSPARC" → their own skills.
- "what does the ModelAngelo paper say about accuracy below 4 Å" →
  cryo-em-knowledge / paper lookup, not an install task.
