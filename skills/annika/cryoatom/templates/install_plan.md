# CryoAtom2 install plan — template

Fill this in, show it to the user, and get confirmation **per step**. Nothing
here authorises a download, a build, or a run.

Full detail: `references/02_install_routes.md`.

## 1. Target and gates (paste real output)

```bash
uname -sm
python3 -V
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv   # on a GPU node
df -h <INSTALL_DIR> ; df -i <INSTALL_DIR>                              # space AND inodes
python3 scripts/cryoatom_env_probe.py --route <ROUTE> --scheduler auto
```

| Gate | Value observed | Pass? |
|---|---|---|
| Linux x86-64 | | |
| NVIDIA GPU ≥ 14 GiB VRAM (direct or via a queue) | | |
| Driver supports CUDA 11.8 | | |
| ~10 GiB free + inode headroom | | |
| Outbound HTTPS (github, yanglab.qd.sdu.edu.cn, dl.fbaipublicfiles.com, conda) | | |
| Container runtime, or conda for the native route | | |

If a gate fails, stop here and report it. Do not work around it.

## 2. Route decision

- [ ] A — Apptainer/Singularity image (recommended on HPC)
- [ ] B — native conda environment
- [ ] C — Docker/Podman
- [ ] D — site module / preinstalled

Reason for this choice:

## 3. Layout decision

| Item | Path | On which filesystem, and why |
|---|---|---|
| Image or conda env | | |
| Weight cache (~5.5 GiB, 6 files) | | |
| Launcher (on PATH) | | |
| Outputs | | scratch, never home |
| Logs | | |
| Build sandbox (`APPTAINER_TMPDIR`) | | node-local scratch |

## 4. Steps, each needing its own confirmation

| # | Step | Command | Cost | Confirmed? |
|---|---|---|---|---|
| 1 | Build/pull image **or** create conda env | | ~45 min, ~5 GiB | |
| 2 | Stage weights | `bash scripts/stage_cryoatom_weights.sh --cache <CACHE> weights` | ~5.5 GiB download | |
| 3 | Pin + verify weights | `… verify` | ~5.5 GiB read | |
| 4 | Native route only: link weights into the package | `… link --site-packages <SP>` | | |
| 5 | Install the launcher | `install -m 0755 scripts/cryoatom_launcher.sh <BINDIR>/cryoatom` | | |
| 6 | Light checks | `cryoatom --version` ; `cryoatom build -h` | seconds, no GPU | |
| 7 | Fetch the public fixture | `… fixture` | ~124 MB | |
| 8 | Fixture run on a GPU | rendered from `templates/smoke_cryoatom.sbatch.template` | 1 GPU, ~10 min | |
| 9 | Record the site config | `scripts/cryoatom_env_probe.py … --record-fixture --output <CONFIG>` | | |

Run `bash scripts/stage_cryoatom_weights.sh --cache <CACHE> plan` first — it
prints exactly what would be downloaded and writes nothing.

## 5. Decisions that must be explicit, not assumed

- **Weight licensing.** Repository code is MIT; the CryoAtom checkpoints, ESM-2,
  and RNA-FM weights carry separate terms that were not established here.
  Staging them into a group-readable cache is redistribution to that group.
- **TLS.** No `--no-check-certificate`, ever. If TLS fails, diagnose it.
- **Pins.** If the conda solve fails on
  `pytorch=2.1.0=py3.9_cuda11.8_cudnn8.7.0_0`, report an upstream
  reproducibility failure. Do not relax the pin.
- **Revision.** This package pins commit `856e250` (version 2.1.1, untagged
  master snapshot). Installing anything else means updating the config, the
  `.def`, and re-verifying the flag surface.

## 6. Verification record

| Check | Result |
|---|---|
| `cryoatom --version` | |
| `cryoatom build -h` matches `references/03_cli_and_outputs.md` | |
| Weight verify (sha256) | |
| Image SHA-256 (record it; a rebuild changes it by design) | |
| Fixture: job id, GPU, elapsed, atoms/chains from `summarize_cryoatom_output.py` | |
| Final config state | ready / probed / blocked |
