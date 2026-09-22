# 02 — Install and Environment

Run `scripts/openfold3_env_probe.py` (read-only) first and pick a route from its result, not from assumptions. Every
install, image build or pull, weights or CCD download, and GPU job below needs explicit per-action consent (last section).
Commands are templates unless marked **[live]**. Pins: `openfold-3@v0.5.0` (`c4771653`), kit
`uplifting-biomolecular-modeling@f4f62fa:openfold3_ob0/`.

## Prerequisites

| Item | Stock upstream (v0.5.0) | OB0 kit (`openfold3_ob0/`) |
|---|---|---|
| OS / arch | Linux x86_64 is the production path (`pyproject.toml` classifier POSIX Linux). Pixi also resolves linux-aarch64 and macOS. No Windows. **[source]** | Linux x86-64 only. **[docs]** |
| GPU | "minimum of CUDA 12.1 and 32GB of memory"; "most of our testing … A100s with 40GB" (`docs/source/Installation.md:8`). **[docs]** | NVIDIA compute capability **>= 8.0**; below 8.0 a mode exits 3. **[docs]** |
| Driver | No minimum stated upstream. | **>= 570** (image stack is CUDA 12.8). **[docs]** |
| Python | 3.10–3.13 per the install guide; metadata says `>=3.10` and lists 3.14. **[source]** | CPython 3.11 (tested 3.11.5). Not Ubuntu 22.04's own `python3.11` package (3.11.0rc1). **[docs]** |
| Other accelerators | Pixi `openfold3-base` (CPU; MPS on Apple Silicon) and `openfold3-rocm7` (AMD) exist but are **not a validated production path** here. | NVIDIA only. |
| Disk | Checkpoint 2 287 872 989 B (~2.3 GB); CCD `components.bcif` 63 393 643 B. | Plus the pinned stack (~8.8 GB pip) or an image (~9.6 GB `.sif`, measured). |

Host library floor (kit): `common/opt_core/README.md` lists prebuilt sm_90a extensions that need libstdc++ with
`GLIBCXX_3.4.32` and glibc 2.32. The validated image loaded them without error **[measured]**. On a route C host check
`strings "$(g++ -print-file-name=libstdc++.so.6)" | grep -c GLIBCXX_3.4.32` and `ldd --version`, and read the kit's
`ACTIVE`/`LEVER` lines for kernels named as not loaded **[unverified]**.

## Pick a route

| Situation | Route |
|---|---|
| Slurm / HPC cluster without a Docker daemon, and you want the speed-up modes | Kit route B built as in Route 3 below |
| Workstation with Docker and the NVIDIA container toolkit, and you want the modes | Kit route A (Docker) |
| Your own Python env (no containers), and you want the modes | Kit route C (venv, `STOCK.md` §Stack) |
| Stock OpenFold3 only, NVIDIA | Upstream pixi `openfold3-cuda12`/`-cuda13`, or pip + extras, or the upstream Docker image |
| CPU, Apple Silicon or AMD exploration | Upstream pixi `openfold3-base` / `openfold3-rocm7` (not validated here) |
| Reproducing preview-2 results (`of3-p2-155k.pt`) | Legacy kit `openfold3/` (0.4.1) only. Preview-2 weights do not load in >= 0.5.0 |

## Route 1 — stock upstream (v0.5.0)

```bash
# template — not run
# pip (Python 3.10–3.13); extras pull the attention kernels
pip install openfold3==0.5.0
pip install "openfold3[cuequivariance]==0.5.0"    # cuequivariance(-ops-torch-cu12, -torch) >=0.8, torch>=2.7
pip install nvidia-cutlass && export CUTLASS_PATH=DS_USE_CUTLASS_PYTHON_BINDINGS   # docs' CUTLASS route for DeepSpeed
pip install "openfold3[deepspeed]==0.5.0"          # deepspeed>=0.18.7; its DS4Sci op JIT-builds at first use

# pixi (upstream-recommended; requires-pixi >=0.73.0 at v0.5.0); the env installs the checkout editable, so keep it
git clone --branch v0.5.0 https://github.com/aqlaboratory/openfold-3.git && cd openfold-3
pixi run -e openfold3-cuda12 setup_openfold --config /abs/path/setup.json     # see "Weights and CCD" below
pixi run -e openfold3-cuda12 run_openfold predict --query-json q.json --output-dir out --use-msa-server false

# Docker
docker pull openfoldconsortium/openfold3:stable     # which openfold3 version "stable" holds is [unverified]: check before use
docker build -f docker/Dockerfile.pixi --target devel -t openfold-docker:pixi-devel .   # from the v0.5.0 checkout
```

- Pixi envs at v0.5.0: `openfold3-base`, `openfold3-cuda12`, `openfold3-cuda13`, `openfold3-cuda12-pypi`,
  `openfold3-cuda13-pypi`, `openfold3-rocm7`, `openfold3-msa` (MSA tools only). The `pixi.toml` hardware table says
  "works" for A100 and B300 (x64, cuda12/13) and "to test" for H100. **[source]**
- The docs' `docker build -f Dockerfile …` is stale: v0.5.0 has no root `Dockerfile`. Use `docker/Dockerfile.pixi`
  (targets `devel`, `test`; `--build-arg PIXI_ENV=openfold3-cuda13`). The docs' GHCR tag (`0.4.2`) predates v0.5.0.
  **[source]**
- Pixi activation sets `TRITON_CACHE_DIR` and `TORCH_EXTENSIONS_DIR` to `$CONDA_PREFIX/caches/…`, which is read-only if
  the upstream image is converted for Apptainer; override them after activation **[unverified]**.
- Env vars from the install guide: `CUDA_HOME` (else `nvcc` not found), `CUTLASS_PATH` (else DeepSpeed fails with
  `Unable to JIT load the evoformer_attn op`), `LD_LIBRARY_PATH` / `LIBRARY_PATH` (for `-lcurand`). ROCm users run
  `validate-openfold3-rocm` after installing.

## Weights and CCD — `setup_openfold` (stock routes)

Flags and JSON fields: `03_cli_reference.md` §4. Registry, lookup order and legacy weights: `07_msa_templates_weights.md`
§8–9. `openfold3/setup_openfold.py` at v0.5.0 does, in order **[source]**:
1. Creates `openfold_cache` and `param_directory` (both default to `~/.openfold3`; `--non-interactive` ignores
   `$OPENFOLD_CACHE`).
2. Writes `<openfold_cache>/ckpt_root`, a one-line text file holding the parameter directory.
3. Downloads the selected checkpoint(s) from `s3://openfold3-data/openfold3-parameters/<file>`, skipping files already
   present unless forced.
4. Fetches the full CCD `components.bcif` into **Biotite's own package directory** (`biotite.setup_ccd.OUTPUT_CCD`) when
   stale. In an image, this step belongs in the build.
5. Runs the integration tests only if asked and `pytest` is installed (`openfold3[dev]`; docs: ~5 min on an A100).
6. Saves `<openfold_cache>/setup_config.json`. It never writes `runner.yml`; a `$OPENFOLD_CACHE/runner.yml` you create is
   deep-merged under any `--runner-yaml` in every `predict`.

```json
{"openfold_cache": "/abs/path/openfold3_cache", "param_directory": "/abs/path/openfold3_cache",
 "selected_parameters": "default", "force_download_parameters": false, "run_integration_tests": false}
```
Set both paths: an omitted `param_directory` falls back to `~/.openfold3`, not to `openfold_cache` **[source]**. Manual
download: `aws s3 cp s3://openfold3-data/openfold3-parameters/of3-ob-2025-06-30-174k.pt <dir>/ --no-sign-request`, then
**require** `sha256sum` = `bd43301c011d5f87580d3e8b548658869433e4488399feb03035ba248f8e29e4`. `predict` never downloads: a
missing checkpoint raises "cowardly refusing to perform inference", although its help text says it will try.

## Route 2 — OB0 kit (A Docker, B Apptainer, C venv)

Run these from the directory that holds `openfold3_ob0/` and `common/` (kit README "Setup"):

```bash
# template — not run
# A — Docker (kit-preferred)
docker build -f openfold3_ob0/environment/Dockerfile -t openfold3_ob0-kit:dev .
docker run --rm -it --gpus all -v /weights:/weights -v $PWD/out:/kit/openfold3_ob0/out openfold3_ob0-kit:dev bash
# B — Apptainer: apptainer.def is "Bootstrap: docker-daemon / From: openfold3_ob0-kit:dev", so it needs A's image once
apptainer build openfold3_ob0.sif openfold3_ob0/environment/apptainer.def
mkdir -p out jit; export MODEL_OPT_JIT_ROOT="$PWD/jit"
kit() { apptainer run --nv --bind <weights dir>:/weights --bind "$PWD/out":/kit/openfold3_ob0/out openfold3_ob0.sif "$@"; }
export OPENFOLD3_OB0_CKPT=/weights/of3-ob-2025-06-30-174k.pt && kit install --weights /weights
kit check --config <a100|h100|h200|b200|b300> --mode exact
# A and C continue inside openfold3_ob0/:
bash run.sh install --weights /weights            # 2.3 GB fetch if absent, else sha256 check; read-only dir is fine
export OPENFOLD3_OB0_CKPT=/weights/of3-ob-2025-06-30-174k.pt   # required on every route
bash run.sh check --config <card> --mode exact     # dry run
```

**Route C** is `STOCK.md` §Stack (every step annotated there), needing a CUDA 12.8 toolkit with `nvcc`. Order:
1. `apt-get` build-essential and the X libraries `libxrender1 libxext6 libsm6 libgl1`.
2. `uv venv --seed --managed-python --python 3.11 <venv>`.
3. `export CUDA_HOME=/usr/local/cuda PYTHONHASHSEED=0 CFLAGS=-g0`.
4. `pip install --no-deps -r` on `environment/requirements.lock`, minus its `openfold3==` and `deepspeed==` lines.
5. `python -I stock/install_upstream.py --wheel-only`.
6. Build DeepSpeed 0.19.2 from source with `DS_BUILD_EVOFORMER_ATTN=1 TORCH_CUDA_ARCH_LIST=<cc>` (~13 min on 8 cores).
7. `pip check`, then `bash run.sh install --weights DIR`.

**`run.sh install [--weights DIR] [--ccd FILE] [--wheel FILE] [--src TARBALL]`** **[source]**, in order:
1. `pip install -e ../common/opt_core -e opt` (skipped when already installed from this tree).
2. Places the pinned `openfold3` 0.5.0 wheel and source tree (PyPI / GitHub archive, or `--wheel` / `--src`), each
   sha256-checked against `stock/PINS.json`.
3. `stock/check_pins.py`: the installed package must match the pin file for file (exit 3 otherwise).
4. Places the CCD into Biotite (offline: `--ccd FILE`).
5. With `--weights`, fetches or sha256-checks the checkpoint.

It **rejects `--config` and `--mode`** (exit 2), whatever the README prose suggests; the legacy 0.4.1 kit's install takes
only `--weights`. Offline host: fetch what `PINS.json` names, then `run.sh install --wheel FILE --src TARBALL --ccd FILE`.
`configs/<card>.env` holds deployment parameters only, is sourced by `pred`/`check`/`warm`, and defaults `OPENFOLD_CACHE`
to the checkpoint's directory. Modes and exit codes: `06_kit_modes_and_multigpu.md`, `03_cli_reference.md`.

**DS4Sci arch.** The OB0 Dockerfile compiles DeepSpeed's DS4Sci op with `TORCH_CUDA_ARCH_LIST="9.0"` (H100) only; for one
image serving A100 and H100 edit that line to `"8.0;9.0"` (the legacy kit exposes `--build-arg DS4SCI_ARCHS`). The op is
**off** in the stock configuration and every mode, so the list matters only when a caller's runner YAML sets
`use_deepspeed_evo_attention: true` under stock `run_openfold` or kit `--mode off` (`exact`/`fast`/`big` override the key
to off; `06_kit_modes_and_multigpu.md` §10). **[source]**

## Route 3 — HPC Apptainer pattern (validated on a Slurm site, 2026-09-22)

1. **No Docker daemon → no `docker-daemon` bootstrap.** Write a `.def` that replays the kit Dockerfile:
   - Header `Bootstrap: docker`, `From: nvidia/cuda:12.8.1-devel-ubuntu22.04` pinned by digest.
   - `%files`: a tarball of the kit commit trimmed to `LICENSE NOTICE README.md openfold3_ob0/ common/opt_core/`, unpacked
     to `/kit` with `--strip-components=1`.
   - `%post`: the Dockerfile's `RUN` steps verbatim (apt, python-build-standalone 3.11.5 with its sha256, lock install,
     `install_upstream.py --wheel-only`, the DeepSpeed build with `8.0;9.0`, `pip check`), then
     `cd /kit/openfold3_ob0 && bash run.sh install`, which puts the CCD into the image.
   - Copy `%post`/`%environment`/`%runscript` from the kit's `apptainer.def` (`/opt/culib` libcuda links,
     `PYTHONNOUSERSITE=1`, `TRITON_LIBCUDA_PATH`, `cd /kit/openfold3_ob0 && exec bash run.sh "$@"`) and add the
     Dockerfile `ENV` lines (`CUDA_HOME`, `PYTHONHASHSEED=0`, `CFLAGS=-g0`).
2. **Build on a CPU build node, not a login node**, with `APPTAINER_TMPDIR`, `APPTAINER_CACHEDIR` and `TMPDIR` on
   node-local disk: `apptainer build --fakeroot <img>.sif <def>`. **[measured]** 27 min, ~9.6 GB `.sif`; `libfakeroot internal error: payload not recognized!` lines were harmless.
3. **Run `--nv` only on GPU nodes.** On a CPU node `run.sh check` returns rc 0 with `gpu=none`: a parser and pin check,
   not GPU proof.
4. **Use `--cleanenv` and forward by prefix.** Export `APPTAINERENV_<name>` for every `OPENFOLD3_OB0_OPT*`, `OF3TP_*`,
   `OF3O_*` and `MODEL_OPT_*` variable, plus `OPENFOLD3_OB0_CKPT`, `OPENFOLD_CACHE`, the cache variables below and
   `CUDA_VISIBLE_DEVICES`. Unset inherited `APPTAINERENV_`/`SINGULARITYENV_` copies first. Never use a comma-separated
   `--env`: values such as `MODEL_OPT_LEVERS_OFF` contain commas.
5. **Bind what the job touches, with absolute paths.** The image is read-only: `--output-dir`/`--out` on a bound,
   writable path; `--query-json` as an absolute host path.
6. **Use `--no-mount hostfs` if the site overlays host directories** (for example `/opt`), which shadow the image's
   `/opt/culib` and `/opt/jit_cache`; then bind explicitly.
7. **Keep JIT and compile caches node-local, per job, never in an inode-limited home.**
   - Variables: `MODEL_OPT_JIT_ROOT`, `TRITON_CACHE_DIR`, `TORCH_EXTENSIONS_DIR`, `XDG_CACHE_HOME` (holds the kit's
     `openfold3_ob0_opt/weights_digests.json` memo; unset → `~/.cache`), `CUDA_CACHE_PATH`, `NUMBA_CACHE_DIR`,
     `OPT_CORE_VERDICT_DIR`.
   - **[measured]** 668–1 013 files / 40–65 MB per job; the first `fast` call cost +22–39 s.
   - Unset, the kit uses `${TMPDIR:-/tmp}/model_opt_jit-uid<uid>` and stock Triton uses `~/.triton`.
8. **Two thin wrappers:** a kit CLI (`apptainer run … <sif> "$@"` → `run.sh`) and a stock CLI
   (`apptainer exec … <sif> /usr/local/bin/run_openfold "$@"`). Naming them `openfold3-kit` / `run_openfold` and reading
   the image path from `OPENFOLD3_KIT_SIF` lets the probe recognise them unasked (other names: `--kit-cli NAME`). Each:
   - takes the image path from an env override and exits 127 if the image is missing;
   - defaults `OPENFOLD_CACHE`/`OPENFOLD3_OB0_CKPT` from the site config (caller values win);
   - derives the cache root from a node-local `$TMPDIR`, falling back to `/tmp` when `$TMPDIR` is under `$HOME`;
   - refuses cache paths under `$HOME`, symlinks, or paths not owned and writable by the user; creates them `umask 077`;
   - adds `--nv` only when `/dev/nvidiactl` or `/dev/nvidia0` exists;
   - kit wrapper only: refuses early when the checkpoint is absent, except for `install`;
   - stock wrapper only: selects no mode. `OPENFOLD3_OB0_OPT=<mode>` arms the kit inside plain `run_openfold predict`
     through the installed `.pth` hook, so forward it only when the caller set it;
   - preserves upstream defaults: MSA server ON stays ON, so pass `--use-msa-server false` explicitly.

Job scripts: no `set -e` around calls (kit rc 3 and rc 5 are results); `sbatch --export=NONE` plus explicit exports.
Generic job file: `templates/slurm_predict.sbatch.template`.

## Verify after install (record results in `configs/site_config.local.md`)

| Step | Command (template) | Pass | Proves / does not prove |
|---|---|---|---|
| Pins | `python -I stock/check_pins.py --wheel-vs-source` (inside the env or image, in `openfold3_ob0/`) | rc 0 | Stock is unmodified 0.5.0 (427 files). Not that the GPU works |
| Stack | `python -m pip check`; versions of torch, triton, deepspeed, cuequivariance-torch vs `environment/requirements.lock` | clean / equal | Env consistency |
| Kit dry run | `run.sh check --config <card> --mode exact` | `DRY-RUN mode=exact …`, rc 0 | Mode/pin/digest gates. `gpu=none` on CPU nodes = **no GPU proof**. Re-hashes the checkpoint and rewrites the digest memo |
| Stock help | `run_openfold predict --help > predict_help.txt` | rc 0; options match `03_cli_reference.md` | CLI options. Bare `run_openfold --help` differs between hosts **[live]** |
| Weights | `sha256sum "$OPENFOLD3_OB0_CKPT"`, or `check_pins.py --weights "$OPENFOLD3_OB0_CKPT"` | `bd43301c…8e29e4`, 2 287 872 989 B | Pinned OpenBind-0. A successful predict does **not** prove this: unknown weights only warn |
| GPU fixture | On a GPU node: kit `pred --config <card> --mode exact --query-json <abs>/query_ubiquitin.json --output-dir <abs>/out --use-msa-server false`, and the same query through stock `run_openfold predict` | rc 0; 5 `*_model.cif` under `out/ubiquitin/seed_42/` | End to end on this card. Single-sequence only |

`query_ubiquitin.json` is upstream's public fixture (`examples/example_inference_inputs/`; in the kit image under
`/kit/openfold3_ob0/stock/src/examples/example_inference_inputs/`). Only after the GPU fixture passes may the site config
state become VALIDATED.

## Consent gates (ask before each; never batch approvals)

| Action | Why it needs consent |
|---|---|
| `pip`/`uv`/`pixi`/`apt` installs, `docker build`/`pull`, `apptainer build` | Changes the environment or disk, and uses network |
| `setup_openfold`, `run.sh install` (even without `--weights`: it fetches the wheel, source tree and CCD if missing), `aws s3 cp` | Downloads (2.3 GB weights, 63 MB CCD) |
| `run.sh warm`, any `pred`/`predict`, any GPU job submission | Uses a GPU allocation or budget |
| `--use-msa-server true`, or leaving it unset (the upstream default is true) | Sends protein sequences to `api.colabfold.com` (`07_msa_templates_weights.md`) |
