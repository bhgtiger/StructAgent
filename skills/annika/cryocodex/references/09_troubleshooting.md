# 09 — Troubleshooting: symptom → cause → fix

Messages in `code font` are verbatim; rows marked **(seen)** were observed on the validation host on 2026-11-24 (full
texts in [03 §6](03_cli_reference.md)); "(wording unverified)" marks messages nobody has captured yet. Through
`predict.sh` every failure is followed by conda's `ERROR conda.cli.main_run:execute(49): … failed. (See above for
error)` — read the lines **above** it. Run `scripts/check_outputs.py --log` on a finished run: it recognises most of
these lines.

## 1. Launcher and environment

| Symptom | Cause | Fix |
|---|---|---|
| `ERROR: Conda was not found. Install Conda and follow the README installation commands.` (exit 1, seen) | `CONDA_EXE` unset and no executable `conda` on `PATH`; conda present only as a shell function (`predict.sh:57-63`) | `export CONDA_EXE=/abs/path/to/bin/conda` (sourcing `etc/profile.d/conda.sh` sets it); `mamba`/`micromamba` alone are not looked for |
| `ERROR: Cannot use '<env>'. Complete the README installation commands first.` (exit 1, seen; preceded by conda's `EnvironmentLocationNotFound`) | env missing or misnamed (`predict.sh:69-73`) | create it per README, or `CRYOCODEX_ENV=<name> ./predict.sh …` |
| `Permission denied` on `./predict.sh` | git stores it as 100644 | `chmod +x predict.sh` (README step) |
| `Downloading the model weights to '<clone>/model_state_dicts/CryoCodex.pth' ...` on `--version`, a typo'd option, or a "quick test" | every call except `-h` / `-h advanced` reaches the download block (`predict.sh:75-91`; C1) | expected; ask first, or place the file ([02 §4](02_config_session_and_environment.md)) |
| `ERROR: Failed to download the model weights from 'https://yanglab.qd.sdu.edu.cn/CryoCodex/CryoCodex.pth'` after ~7 min of `curl: (28) Failed to connect … port 443` (seen) | no outbound HTTPS (compute node), proxy, or the lab server is down — it is intermittently unreachable (seen); `.part` removed | retry later; download on a node with access (same `curl -fL --retry 2` line) into the clone used by the compute nodes; or copy from another install and compare size + sha256 (02 §4) |
| `curl: command not found` (then exit) | `predict.sh` downloads with curl | install curl or place the weights by hand |
| pip fails on Python 3.12/3.13, or `numpy==1.26.4` has no wheel | README pins need CPython 3.11 (3.12 untested) | recreate the env with `python=3.11` |
| pip pulls a CPU-only or no torch (aarch64, macOS) | PyPI torch 2.5.1 CUDA wheels are Linux x86_64 only | unsupported platform for this skill (BLOCKED/PARTIAL) |
| `PermissionError: [Errno 13] Permission denied: '<base>/pkgs/cache/….json'` from `conda create` (seen) | shared conda install whose package cache belongs to another user | `export CONDA_PKGS_DIRS=<writable dir>` and retry (02 §2) |
| pip prints `Found existing installation: numba …` / `Uninstalling …` while installing into a fresh env (seen) | the packages live in `~/.local/lib/python3.11/site-packages`; pip removes them **from the user site** | stop it; restore with `<env>/bin/python -m pip install --user --no-deps <pkg>==<old version>`; rebuild the env with `PYTHONNOUSERSITE=1` |
| probe `--env-check` lists `USER-SITE: numba,scipy`, or numba/scipy versions differ from the pins only at run time (seen) | `~/.local` packages shadow the env's (conda envs do not isolate the user site) | `export PYTHONNOUSERSITE=1` before `predict.sh` (a site launcher should set it) |
| `ImportError: cannot import name 'DropPath' from 'timm.layers' (unknown location)` (seen) | a half-deleted env: stale `timm-*.dist-info` without code (e.g. `conda env remove` on NFS left `.nfs*` files) made pip skip timm | `rm -rf` the env prefix and recreate; `pip check` + probe `--env-check` |
| `torch.cuda.is_available()` False inside the env (probe `--env-check`) | driver too old for the CUDA 12 runtime of the PyPI torch wheel; or no GPU on this node | run on the GPU node; check the driver with `nvidia-smi`; the notebook's alternative is `torch==2.5.1` from the cu124 index — say it comes from the notebook, not the README |

## 2. Command line

| Symptom | Cause | Fix |
|---|---|---|
| `predict.sh: error: argument --normal: expected one argument` (exit 2, seen) | value-less boolean | `--normal True` / `--normal False` |
| `argument --normal: expected True or False, got 'yes'` (exit 2) | `parse_bool` accepts only true/false, any case (`predict.py:37-43`) | `True` / `False` |
| `--keep_size is only available in fast mode, so it needs --normal False` / `--crop_check is only available in fast mode, so it needs --normal False` (exit 2) | fast-mode options with `--normal True` (`predict.py:189-192`) | drop one of them |
| `predict.sh: error: the following arguments are required: -i/--in_map_path` (and/or `-o/--out_dir`; exit 2, seen) | missing `-i`/`-o` | add them; note this run still downloaded the weights first if they were missing |
| `FileNotFoundError: [Errno 2] No such file or directory: '<map>'` (exit 1, seen) | wrong `-i` path (relative paths resolve against the caller's directory) | absolute path; the `-o` directory was already created (empty) |
| `RuntimeError: File <path> is not a cryo-em density map file format.` | name does not end in lower-case `mrc`/`map` (`.ccp4`, `.MRC`, `.gz`, `.mrcs`) (`grid_utils.py:215`, `:229-230`) | decompress / rename / symlink to `.mrc` |
| `-g 0,1` but only one GPU works | single device by design (`cuda:0`) | one index; one job per GPU |
| a scheduler-assigned GPU is ignored, two jobs land on GPU 0 (seen on a node without GPU fencing) | `-g` (default `"0"`) overwrote `CUDA_VISIBLE_DEVICES` (`predict.py:194`) | `-g "${CUDA_VISIBLE_DEVICES:-0}"` (verified fix) or a site launcher that appends it |

## 3. Input map

| Symptom | Cause | Fix |
|---|---|---|
| `# Input grid is not orthogonal. EXIT.` then nothing, exit status 0 (seen) | CELLB angles not all 90 (`grid_utils.py:160-167`) | not a single-particle-style map; CryoCodex cannot use it. Scripts must check outputs, not only the exit code |
| mrcfile error about the map ID, mode or file size (wording unverified) | corrupt/truncated download, unusual mode, non-MRC file | `python3 scripts/inspect_map.py map.mrc`; re-download; convert to float32 MRC |
| NumPy error early in preprocessing (wording unverified) | no positive voxel (header DMAX ≤ 0) | check the map's sign and content; CryoCodex needs positive density |
| part of the molecule missing in fast-mode outputs | auto-crop missed it (corners outside the inscribed sphere, separated bodies; G33) | `--normal True`, or `--crop_check True` at an interactive terminal |
| `ValueError: could not broadcast input array from shape (48,48,48) into shape (41,41,41)` with `--keep_size True` (seen) | 1 Å box axis < 48: the padded crop does not fit the canvas (`predict.py:71`) | drop `--keep_size` |

## 4. Resources and GPU

| Symptom | Cause | Fix |
|---|---|---|
| `torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 1.90 GiB. GPU 0 has a total capacity of 7.60 GiB …` (seen with `-b 18` on an 8 GB card) | batch too large for the card, or other processes on the GPU | lower `-b` (`-b 9` peaks at 7,328 MiB, `-b 1` at 1,420 MiB); check `nvidia-smi` for other jobs (on unfenced nodes, also whether you are on the GPU you were given); the CLI has no automatic retry |
| process `Killed`, exit 137, oom-kill in `dmesg`/Slurm | host RAM: all windows are held in memory (~2.2 MB each) | more `--mem` (estimate with `inspect_map.py`); fast mode instead of normal; a larger stride reduces windows (e.g. 16–24; effect on quality not documented — the Scipion GPU test uses 24) |
| failure around pinning memory (wording unverified) | very many windows → large pinned allocation (`seg.pin_memory()`, `predict.py:90`) | as above; fewer windows |
| `RuntimeError: Attempting to deserialize object on a CUDA device but torch.cuda.is_available() is False. …` (seen with `-g ""`) | no visible GPU: empty or wrong `-g`/`CUDA_VISIBLE_DEVICES`, login/CPU node, driver problem | `nvidia-smi -L`; correct `-g`; run on the GPU node. "invalid device ordinal" / "no NVIDIA driver" variants: wording unverified |
| `Unable to determine the device handle for GPU<n>: …: Unknown Error` from `nvidia-smi` (seen on one node) | a failing GPU or driver on that node | avoid that node/GPU (`--exclude` / another index); tell the admins |
| slow start before the progress bar | `conda run` start-up, map resampling, numba JIT compilation (G34) | expected: of a 58 s fixture run on the validation host, ~20 s were outside the inference loop (37 s at ~4.7 windows/s) |

## 5. Weights

| Symptom | Cause | Fix |
|---|---|---|
| `Unrecognized checkpoint format in '<path>': expected a dict with a 'model_state_dict' entry, got …` | wrong file at `model_state_dicts/CryoCodex.pth` (`predict.py:48-53`) | re-download; check size 470,938,660 B |
| `Failed to load the checkpoint '<path>' into MMVQUnet (strict=True): …` | truncated/changed checkpoint, or code ≠ v1.0.0 (`predict.py:55-61`) | size + sha256 vs your record; `git checkout v1.0.0` |
| file size ≠ 470,938,660 B, or a `CryoCodex.pth.part` exists | interrupted download (the launcher only tests "non-empty") | delete both and download again (with confirmation) |
| `weights_only=True` test load fails (runbook R8) | the file needs full unpickling | stop; do not run CryoCodex on it until the user decides (ask the authors) |

## 6. Outputs

| Symptom | Cause | Fix |
|---|---|---|
| outputs smaller than the input / 1.0 Å voxel | by design: 1 Å grid, cropped in fast mode | `--keep_size True --reverse_interpolation True` for the input grid ([05 §2](05_core_workflows.md)) |
| `--keep_size True` box ≠ input box | it restores the **1 Å regridded** box (C4) | add `--reverse_interpolation True` |
| outputs do not overlay the input in a viewer | placement only in NXSTART (ORIGIN 0); the viewer may read ORIGIN only | `check_outputs.py --input` overlay check; set the origin in the viewer from NSTART × voxel |
| score maximum > 1 | cubic reverse resampling overshoot; no upper clamp (C11) | expected after `--reverse_interpolation True` (up to 1.14 seen); on the 1 Å grid it would be a finding (report it) |
| mask all 0 / enhanced map all 0 | nothing recognised as molecule (very low resolution, unusual map, wrong sign) | check the input; try `--normal True`; report it |
| planes of zeros inside the outputs | stride > 44 (`-s 46` → planes 46, 47, 92, 93, seen) | `-s` 1–44 (default 12) |
| outermost 2 voxels are 0 | blending margin (seen) | expected |
| `round_1_check/` folders left, no maps, `RuntimeError: Crop inspection needs terminal input.` (exit 1, seen) | `--crop_check True` without a terminal (EOF) | never in batch; rerun without it |
| job hangs after `[Enter] Continue without changes  |  [e] Edit bounds: ` (seen) | `--crop_check True` waiting for input (no timeout) | cancel; rerun without it |
| fast-mode and normal-mode results differ slightly | different window grids (Pearson 0.996 on the fixture, seen) | expected; compare within one mode |
| earlier results changed | same `-o` and `-n` → overwritten silently | a new `-o` per run |
