# 02 — Config session, install route, environment

## 1. Probe first

```bash
python3 scripts/cryocodex_env_probe.py --home /abs/CryoCodex [--env-name cryocodex_env] [--json] [--output probe.md]
python3 scripts/cryocodex_env_probe.py --home /abs/CryoCodex --env-check     # runs python inside the env: imports torch, reports CUDA; no download
python3 scripts/cryocodex_env_probe.py --home /abs/CryoCodex --hash          # ASK FIRST: sha256 of the 471 MB checkpoint
```

Run it **on the node that will run CryoCodex** (a login node and a GPU node differ). It checks, read-only:
OS/arch, `nvidia-smi` (GPU, memory, driver), `CUDA_VISIBLE_DEVICES`, conda the way `predict.sh` finds it
(`CONDA_EXE`, else `conda` on `PATH`), whether the env exists (`conda env list --json`), the clone (`git rev-parse
HEAD` vs the pin `a35e73a…`, `predict.sh` executable), and the checkpoint (present, size = 470,938,660 B).

| Verdict | Meaning | Next step |
|---|---|---|
| `BLOCKED` | not Linux, no NVIDIA GPU visible, or no executable conda | explain; no CryoCodex run possible here (only `-h`, header inspection) |
| `NOT_INSTALLED` | no clone at `--home`, or env missing | offer the README install (§2), with confirmation |
| `PARTIAL` | installed, but checkpoint missing/wrong size, clone not at the pin, `predict.sh` not executable, or `--env-check` not run/failed | name the gap; offer the fix (download with confirmation, `chmod +x`, checkout) |
| `READY_TO_VALIDATE` | everything present, env imports torch with CUDA | run [validation_runbook.md](validation_runbook.md) once; then the host may be marked VALIDATED in the site config |

The probe never says VALIDATED. Copy [../configs/site_config.template.md](../configs/site_config.template.md) to
`configs/site_config.local.md` and fill it in.

## 2. Install (README route; template — not run)

```bash
git clone https://github.com/YangLab-SDU/CryoCodex.git
cd CryoCodex && git checkout v1.0.0                                    # pin; README itself does not check out a tag
conda env list                                                          # if cryocodex_env exists, pick another name (conda create -y replaces it)
conda create -y -n cryocodex_env python=3.11
conda run --no-capture-output -n cryocodex_env python -m pip install -r requirements.txt
chmod +x predict.sh                                                     # stored as 100644 in git
```

- `requirements.txt` pins `torch==2.5.1`, `mrcfile==1.5.4`, `numba==0.61.2`, `einops==0.8.1`, `timm==1.0.24`,
  `numexpr==2.10.0`, `numpy==1.26.4`, `scipy==1.16.0`, `tqdm==4.67.1`, `pillow>=10.1,<13` (`requirements.txt:1-12`).
  No index URL → torch comes from PyPI; on Linux x86_64 that wheel (≈ 906 MB) pulls the CUDA 12.4 runtime as
  `nvidia-*-cu12` packages. `torchvision` is added by `timm` (version not pinned). Env size not measured yet (several GB expected with the CUDA wheels).
- Binary wheels for all pins exist only for **CPython 3.11 and 3.12** (scipy needs ≥ 3.11; numpy 1.26.4 has no 3.13
  wheel). README says 3.11; 3.12 is untested.
- The notebook installs differently (uv venv, torch from `https://download.pytorch.org/whl/cu124`,
  `torchvision==0.20.1`). If the PyPI torch does not match the host driver, the cu124 index is the authors' own
  alternative — say it comes from the notebook, not the README.
- Never install into another tool's environment (cryoSPARC, RELION, Scipion).

## 3. Environment variables and paths

| Name | Read by | Effect |
|---|---|---|
| `CRYOCODEX_ENV` | `predict.sh:8` | conda env name (default `cryocodex_env`) |
| `CONDA_EXE` | `predict.sh:59-63` | conda executable; else `command -v conda`; must be executable (a shell-function-only conda fails: export `CONDA_EXE`) |
| `CUDA_VISIBLE_DEVICES` | overwritten by `predict.py:194` | set to the `-g` value (default `"0"`) before CUDA initialises |
| `CRYOCODEX_PROG` | internal (`predict.sh:12-13`) | launcher name shown in the usage line; do not set |

- `predict.sh` resolves its own directory, so it can be called by absolute path from anywhere; `-i`/`-o` relative
  paths are relative to the caller's working directory (`predict.sh:6-7`). Prefer absolute paths.
- Checkpoint location is fixed: `<clone>/model_state_dicts/CryoCodex.pth` (`predict.sh:76`); the hidden `-m` is
  always passed by the launcher (`predict.sh:94`) — do not pass your own `-m` through `predict.sh`.

## 4. Weights: download, placement, integrity

- First call of `predict.sh` with anything other than `-h`/`-h advanced` and no non-empty checkpoint runs
  `curl -fL --retry 2 -o <ckpt>.part https://yanglab.qd.sdu.edu.cn/CryoCodex/CryoCodex.pth` and renames it
  (`predict.sh:75-91`). Size 470,938,660 B (HEAD 2026-11-24). Needs outbound HTTPS to `yanglab.qd.sdu.edu.cn`.
- Offline/compute nodes without internet: download once on a node with access (same `curl` line) into
  `model_state_dicts/CryoCodex.pth` of the clone the compute nodes use.
- Integrity: nothing is checked except "non-empty". After download: compare size with 470,938,660 and record
  `sha256sum` in the site config (probe `--hash`); the runbook (R8) loads it once with `torch.load(...,
  weights_only=True)` before the first inference because `predict.py:47` uses `weights_only=False`.

## 5. Platform and resources

- **Supported (README):** Linux, CUDA-enabled GPU, Python 3.11; "Mainly tested on CentOS 7" (`README.md:113-115`).
- **Not supported by the code:** CPU-only, Apple Silicon/MPS, macOS, Windows, AMD — compute is `cuda:0`
  (`predict.py:82`). Say "not supported by the code", not "untested".
- **GPU memory:** only data point is the preprint's A800 run capped at 8 GB with batch 9 (= default `-b`). Lower `-b`
  for smaller cards ("For GPUs with limited memory, reduce the batch size using `-b`", `README.md:115`); the notebook's
  own heuristic (notebook only; the CLI has none) is `max(1, min(cap, int(9 × free_GiB × 0.9 / 8)))`, cap 9 on cards
  ≤ 8 GiB, else 64.
- **Host RAM (derived):** ≈ 2.2 MB per 48³ window (4 output channels + input, float32, `predict.py:92`); normal mode on a
  big box can need tens of GB — `scripts/inspect_map.py` estimates the window count.
- **Disk:** the env (not measured; several GB) + 0.47 GB weights + four float32 output maps per run.
