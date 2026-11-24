# 02 — Config session, install route, environment

## 1. Probe first

```bash
python3 scripts/cryocodex_env_probe.py --home /abs/CryoCodex [--env-name cryocodex_env] [--json] [--output probe.md]
python3 scripts/cryocodex_env_probe.py --home /abs/CryoCodex --env-check     # runs python inside the env: imports torch, reports CUDA; no download
python3 scripts/cryocodex_env_probe.py --home /abs/CryoCodex --hash          # ASK FIRST: sha256 of the 471 MB checkpoint
# shared install (section 2b): env by path + site launcher; conda not needed
python3 scripts/cryocodex_env_probe.py --home /abs/CryoCodex --env-prefix /abs/envs/cryocodex --launcher /abs/cryocodex.sh --env-check
```

Run it **on the node that will run CryoCodex** (a login node and a GPU node differ). It checks, read-only:
OS/arch, `nvidia-smi` (GPU, memory, driver), `CUDA_VISIBLE_DEVICES`, conda the way `predict.sh` finds it
(`CONDA_EXE`, else `conda` on `PATH`), whether the env exists (`conda env list --json`), the clone (`git rev-parse
HEAD` vs the pin `a35e73a…`, `predict.sh` executable), the checkpoint (present, size = 470,938,660 B), and with
`--env-check` the package versions **and whether any of them is imported from the user site** (`~/.local`).

| Verdict | Meaning | Next step |
|---|---|---|
| `BLOCKED` | not Linux, no NVIDIA GPU visible, or no executable conda (predict.sh route) | explain; no CryoCodex run possible here (only `-h`, header inspection) |
| `NOT_INSTALLED` | no clone at `--home`, env missing, or the launcher/env python missing | offer the README install (§2) or the site install (§2b), with confirmation |
| `PARTIAL` | installed, but checkpoint missing/wrong size, clone not at the pin, `predict.sh` not executable, `--env-check` not run/failed, or packages shadowed from the user site | name the gap; offer the fix (download with confirmation, `chmod +x`, checkout, `PYTHONNOUSERSITE=1`) |
| `READY_TO_VALIDATE` | everything present, env imports torch with CUDA from the env itself | run [validation_runbook.md](validation_runbook.md) once; then the host may be marked VALIDATED in the site config |

The probe never says VALIDATED. Copy [../configs/site_config.template.md](../configs/site_config.template.md) to
`configs/site_config.local.md` and fill it in.

## 2. Install (README route; verified 2026-11-24 with the additions marked ★)

```bash
git clone https://github.com/YangLab-SDU/CryoCodex.git
cd CryoCodex && git checkout v1.0.0                                    # pin; README itself does not check out a tag
conda env list                                                          # if cryocodex_env exists, pick another name (conda create -y replaces it)
conda create -y -n cryocodex_env python=3.11                            # ★ add -c conda-forge --override-channels if your site avoids the defaults channel
PYTHONNOUSERSITE=1 conda run --no-capture-output -n cryocodex_env python -m pip install -r requirements.txt   # ★ PYTHONNOUSERSITE=1
chmod +x predict.sh                                                     # stored as 100644 in git (git status then shows " M predict.sh")
```

- **★ `PYTHONNOUSERSITE=1` is not optional when the user has packages in `~/.local/lib/python3.11/site-packages`.**
  A conda env is not a virtualenv, so pip treats user-site copies of the same packages as "existing installations"
  and **uninstalls them from `~/.local`** before installing into the env (observed: llvmlite 0.43.0, scipy 1.17.1,
  numba 0.60.0 removed — packages other tools in that user site relied on). If it happened: stop pip, then restore the exact
  versions with `<env>/bin/python -m pip install --user --no-deps <pkg>==<version>`. Check first with
  `ls ~/.local/lib/python3.11/site-packages`.
- Measured: `conda create` 44 s, `pip install` 3:00, env **5.7 GB** (torch 2.5.1 + CUDA 12.4 wheels). Result
  (verified): Python 3.11.18, torch 2.5.1+cu124 (CUDA build 12.4, cuDNN 9.1), torchvision 0.20.1+cu124, mrcfile 1.5.4,
  numba 0.61.2, einops 0.8.1, timm 1.0.24, numexpr 2.10.0, numpy 1.26.4, scipy 1.16.0, tqdm 4.67.1, Pillow 12.3.0,
  `pip check` clean; works with drivers 595.99 (CUDA 13.2) and 580.178. The PyPI torch wheel is fine on a recent driver; the
  notebook's cu124 index is the authors' alternative for older drivers (say it comes from the notebook).
- **★ Shared conda installs**: `conda create` can fail with `PermissionError … <base>/pkgs/cache/*.json` when the
  first package cache belongs to another user. Set a private cache: `export CONDA_PKGS_DIRS=$HOME/.conda/pkgs` (or any
  writable dir). `CONDA_ENVS_DIRS` chooses where `-n` envs go; `predict.sh` finds them as long as the same variable is
  set when it runs.
- **★ Removing a broken env on NFS**: `conda env remove` can leave a skeleton (`.nfs*` busy files) with stale
  `*.dist-info`; the next pip run then skips those packages ("already satisfied") and the env fails with e.g.
  `ImportError: cannot import name 'DropPath' from 'timm.layers' (unknown location)`. Delete the prefix with
  `rm -rf` (after checking nothing still uses it) and recreate.
- Binary wheels for all pins exist only for **CPython 3.11 and 3.12** (scipy needs ≥ 3.11; numpy 1.26.4 has no 3.13
  wheel). README says 3.11; 3.12 is untested.
- Never install into another tool's environment (cryoSPARC, RELION, Scipion).

## 2b. Shared install with a site launcher (verified 2026-11-24)

For several users, keep one clone + checkpoint and one env, and give users a launcher that calls the env's python on
`predict.py` directly — [../templates/site_launcher.sh.template](../templates/site_launcher.sh.template):

- no `conda run`, no `conda activate`, and the env may live anywhere (a prefix path);
- never downloads (fails clearly if the checkpoint is missing);
- exports `PYTHONNOUSERSITE=1` and `PYTHONDONTWRITEBYTECODE=1`;
- appends `-g "$CUDA_VISIBLE_DEVICES"` under a scheduler when the user gave no `-g`.

It takes exactly the `predict.sh` options. On the validation cluster the filled template, the site's own launcher and
the README route gave **bit-identical** outputs on the same GPU model; `-h` / `--version` work (the usage line shows the
launcher's name); with no checkpoint the template stops with `ERROR: CryoCodex weights missing at …` (exit 1). Build the env with the README
commands (`conda create -p <prefix> python=3.11`, then `PYTHONNOUSERSITE=1 <prefix>/bin/python -m pip install -r
requirements.txt`), place the checkpoint, record its sha256, and run the runbook once through the launcher.
Probe it with `--env-prefix <prefix> --launcher <launcher>`; build commands with `build_cryocodex_command.py --launcher`.

## 3. Environment variables and paths

| Name | Read by | Effect |
|---|---|---|
| `CRYOCODEX_ENV` | `predict.sh:8` | conda env name (default `cryocodex_env`) |
| `CONDA_EXE` | `predict.sh:59-63` | conda executable; else `command -v conda`; must be executable (a shell-function-only conda fails: export `CONDA_EXE`) |
| `CUDA_VISIBLE_DEVICES` | overwritten by `predict.py:194` | set to the `-g` value (default `"0"`) before CUDA initialises — **verified**: even `-g ""` takes effect |
| `PYTHONNOUSERSITE` | Python | `1` keeps `~/.local` packages out of the env — set it for pip and for every run (verified shadowing otherwise) |
| `CONDA_PKGS_DIRS`, `CONDA_ENVS_DIRS` | conda | private package cache / env location on shared conda installs |
| `CRYOCODEX_PROG` | internal (`predict.sh:12-13`) | launcher name shown in the usage line; do not set |

- `predict.sh` resolves its own directory, so it can be called by absolute path from anywhere; `-i`/`-o` relative
  paths are relative to the caller's working directory (`predict.sh:6-7`). Prefer absolute paths.
- Checkpoint location is fixed: `<clone>/model_state_dicts/CryoCodex.pth` (`predict.sh:76`); the hidden `-m` is
  always passed by the launcher (`predict.sh:94`). A second `-m` from the user **wins** (argparse keeps the last;
  verified) — do not pass one.

## 4. Weights: download, placement, integrity

- First call of `predict.sh` with anything other than `-h`/`-h advanced` and no non-empty checkpoint runs
  `curl -fL --retry 2 -o <ckpt>.part https://yanglab.qd.sdu.edu.cn/CryoCodex/CryoCodex.pth` and renames it
  (`predict.sh:75-91`; trigger verified, also for `--version`). Needs outbound HTTPS to `yanglab.qd.sdu.edu.cn`.
- **The lab server is intermittently unreachable** (verified: it served a file, then timed out for ~50 min, then
  served the checkpoint again; the download itself took 53 s).
  `predict.sh` then spends ~7 min (3 tries × ~2.2 min) before `ERROR: Failed to download the model weights from
  '<URL>'`, exit 1, no `.part` left. Alternatives: retry later, or copy the file from another install and check it.
- Offline/compute nodes without internet: download once on a node with access (same `curl` line) into
  `model_state_dicts/CryoCodex.pth` of the clone the compute nodes use.
- Integrity: nothing is checked except "non-empty". Compare the size with 470,938,660 B and the sha256 with the value
  recorded on the validation host, `dfb814c63ed2dbdca99d0e3803e408d88775217a48d72a4fbb60618f8feda380` (probe `--hash`;
  this is an observation, not an authors' checksum — a different value means a changed server file: re-validate).
  The runbook (R8) loads it once with `torch.load(..., weights_only=True)` before the first inference because
  `predict.py:47` uses `weights_only=False`; the reference file passes (it also stores optimizer and scheduler state,
  which is why it is 471 MB for 39.5 M parameters).

## 5. Platform and resources

- **Supported (README):** Linux, CUDA-enabled GPU, Python 3.11; "Mainly tested on CentOS 7" (`README.md:113-115`).
  **Verified:** Ubuntu 24.04 (glibc 2.39), drivers 595.99 and 580.178, RTX 2070 SUPER (8 GB, sm_75), RTX 2080 Ti (11 GB, sm_75);
  a site launcher also ran on an RTX 4090 (another map, 41 s).
- **Not supported by the code:** CPU-only, Apple Silicon/MPS, macOS, Windows, AMD — compute is `cuda:0`
  (`predict.py:82`). Say "not supported by the code", not "untested". With no visible GPU the run fails at the checkpoint
  load (`RuntimeError: Attempting to deserialize object on a CUDA device but torch.cuda.is_available() is False…`).
- **GPU memory (verified, device level, `-b 9`):** 7,328 MiB (7.2 GiB) on the 8 GB card for both the 150³ and the 432³
  map (memory followed `-b`, not the map size) and 7,164 MiB on the 11 GB card (150³). `-b 1` → 1,420 MiB; `-b 18` →
  out of memory on the 8 GB card (7.6 GiB usable). The CLI has no automatic batch size and no retry (the notebook has a heuristic of its own).
- **Host RAM (verified, max RSS):** fast mode 1.8 GB (150³ map) and 4.1 GB (432³ map at 0.86 Å); normal mode 3.9 GB
  (150³). These fit ≈ 1.4 GB (Python, torch, CUDA) + 2.2 MB per 48³ window + ~20 B per voxel of the 1 Å grid, the
  estimate `scripts/inspect_map.py` prints (within ~5 % on the three runs). For normal mode on a 432³ map that gives
  ≈ 51 GB (derived; not run).
- **Disk:** env 5.7 GB + 0.47 GB weights + four float32 output maps per run (3.6 MB each for the 150³ fixture crop,
  13.5 MB each on its input grid).
