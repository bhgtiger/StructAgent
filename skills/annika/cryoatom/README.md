# Portable CryoAtom2 skill

A host-agnostic Claude Code skill for **CryoAtom2** (automatic atomic model
building for proteins, RNA, DNA and protein–nucleic-acid complexes from cryo-EM
maps), packaged so it can be installed and configured on any machine.

It carries **no host facts** — no hostname, account, partition, home path, or
image hash. Everything machine-specific lives in an external *site config* that
the shipped probe generates on the target machine.

```
cryoatom/                      <- the skill package (copy this directory)
  SKILL.md
  references/                  scope, configuration, install routes, CLI,
                               versions, evidence, safety, operations
  templates/                   site config skeleton, install/readiness/run
                               plans, Slurm job templates
  scripts/                     probe, weight checker, weight staging,
                               launcher, template renderer, output
                               summarizer, package validator
  install/cryoatom.def         pinned Apptainer recipe (commit + tree verified)
  examples/                    trigger tests, eval cases, fixture contract
```

## 1. Install the skill

```bash
# for one user, all projects  (copy the CONTENTS, so an existing skill dir is
# replaced rather than nested inside itself)
mkdir -p ~/.claude/skills/cryoatom
cp -a cryoatom/. ~/.claude/skills/cryoatom/

# or for one project
mkdir -p <project>/.claude/skills/cryoatom
cp -a cryoatom/. <project>/.claude/skills/cryoatom/
```

Verify the package is intact (static checks plus the scripts' self-tests):

```bash
python3 ~/.claude/skills/cryoatom/scripts/validate_skill.py
# -> {"valid": true, "errors": []}
```

If you already have a host-pinned `cryoatom` skill installed, keep only one:
this portable one covers the same ground and reaches the same conclusions once a
site config exists for that machine.

## 2. Configure it for this machine

```bash
python3 ~/.claude/skills/cryoatom/scripts/cryoatom_env_probe.py \
  --profile my-machine \
  --route container \
  --image /path/to/cryoatom.sif \
  --launcher ~/bin/cryoatom \
  --weights-cache /path/to/cryoatom_cache \
  --scheduler auto --account <ACCOUNT> --gpu-partition <GPU_PARTITION> \
  --scratch-root /path/to/scratch \
  --live-version \
  --output ~/.config/cryoatom-skill/site-config.json
```

The probe is read-only unless `--output` is given, and it never runs a
prediction. It prints a state — `ready`, `probed`, `stale`, `blocked`, or
`unknown` — with the reasons behind it. The skill will not make a
machine-specific claim beyond what that state supports.

Re-check any time:

```bash
python3 scripts/cryoatom_env_probe.py --validate-config ~/.config/cryoatom-skill/site-config.json
```

Keep the config outside the package (the probe writes it mode `0600`) so
copying or archiving the skill cannot leak your paths, account, or partitions.

## 3. If CryoAtom2 is not installed yet

Ask Claude to install it, or follow `cryoatom/references/02_install_routes.md`
directly. Four routes are covered — Apptainer/Singularity image (recommended on
HPC), native conda, Docker/Podman (`install/Dockerfile`), and a site module —
plus:

- gates to check before choosing (Linux, NVIDIA ≥14 GiB VRAM, CUDA 11.8 driver,
  space **and inodes**, outbound HTTPS);
- `install/cryoatom.def`, which pins the upstream commit *and* tree hash, pins
  the base image by digest, compiles `getp` from source, and fails the build if
  weights leak into the image;
- weight staging over verified TLS with byte-size checks and SHA-256 pinning:
  ```bash
  bash scripts/stage_cryoatom_weights.sh --cache <CACHE> plan     # writes nothing
  bash scripts/stage_cryoatom_weights.sh --cache <CACHE> weights  # ~5.1 GiB
  bash scripts/stage_cryoatom_weights.sh --cache <CACHE> verify
  ```
- a public fixture run (EMD-33198 / 7XHT) that must pass before the config can
  reach `ready`.

## 4. Run something

```bash
install -m 0755 scripts/cryoatom_launcher.sh ~/bin/cryoatom
cryoatom --version            # works on a login node, opens no checkpoint
cryoatom build -h

python3 scripts/render_job_template.py templates/run_cryoatom.sbatch.template \
  --set JOB_NAME=my_run --set MAP=/data/map.mrc --set OUTPUT_DIR=<SCRATCH>/my_run \
  --output ~/run_cryoatom.sbatch
sbatch ~/run_cryoatom.sbatch

python3 scripts/summarize_cryoatom_output.py <SCRATCH>/my_run
```

The launcher works with Apptainer, Singularity, Docker/Podman, or a native conda
install, and preflights all six weight files before every `build` — but never
before `--version` or `build -h`, which stay usable with no cache staged.

## 5. What the skill will not do

- Run, download, build, or submit anything without explicit per-action confirmation.
- Reuse an existing output directory (CryoAtom replaces files under it and
  deletes intermediates — reuse silently mixes runs).
- Bypass TLS, relax the pinned dependency set, or invent CLI flags.
- Upload maps or sequences to Colab or any other service.
- Claim a predicted model is validated, or call CryoAtom2's RNA/DNA support
  peer reviewed (v1 is peer-reviewed and protein-focused; v2's claims are from
  an unreviewed preprint).
- Carry one machine's validation to another.

## Pinned revision

CryoAtom2 **2.1.1, commit `856e250df7b784b854b892f1b619d32d51188cef`, tree
`0058c0c6…`** — an untagged master snapshot. No repository tag names this code
(`v2.1.0` is *behind* it), so the commit is the only honest pin. To install a
different revision, update the config, `install/cryoatom.def`, and re-verify the
flag surface in `references/03_cli_and_outputs.md`.
