# 09 — Troubleshooting: symptom → cause → fix

Messages in `code font` are verbatim from the code at `a35e73a`; "(wording unverified)" marks library messages that
nobody has captured yet (runbook R6–R16 will). Nothing here was observed live. Run `scripts/check_outputs.py --log`
on a finished run: it recognises most of these lines.

## 1. Launcher and environment

| Symptom | Cause | Fix |
|---|---|---|
| `ERROR: Conda was not found. Install Conda and follow the README installation commands.` (exit 1) | `CONDA_EXE` unset and no executable `conda` on `PATH`; conda present only as a shell function (`predict.sh:57-63`) | `export CONDA_EXE=/abs/path/to/bin/conda` (sourcing `etc/profile.d/conda.sh` sets it); `mamba`/`micromamba` alone are not looked for |
| `ERROR: Cannot use '<env>'. Complete the README installation commands first.` (exit 1) | env missing or misnamed (`predict.sh:69-73`) | create it per README, or `CRYOCODEX_ENV=<name> ./predict.sh …` |
| `Permission denied` on `./predict.sh` | git stores it as 100644 | `chmod +x predict.sh` (README step) |
| `Downloading the model weights to '<clone>/model_state_dicts/CryoCodex.pth' ...` on `--version`, a typo'd option, or a "quick test" | every call except `-h` / `-h advanced` reaches the download block (`predict.sh:75-91`; C1) | expected; ask first, or place the file ([02 §4](02_config_session_and_environment.md)) |
| `ERROR: Failed to download the model weights from 'https://yanglab.qd.sdu.edu.cn/CryoCodex/CryoCodex.pth'` | no outbound HTTPS (compute node), proxy, server down; `.part` removed | download on a node with access (same `curl -fL --retry 2` line) into the clone used by the compute nodes |
| `curl: command not found` (then exit) | `predict.sh` downloads with curl | install curl or place the weights by hand |
| pip fails on Python 3.12/3.13, or `numpy==1.26.4` has no wheel | README pins need CPython 3.11 (3.12 untested) | recreate the env with `python=3.11` |
| pip pulls a CPU-only or no torch (aarch64, macOS) | PyPI torch 2.5.1 CUDA wheels are Linux x86_64 only | unsupported platform for this skill (BLOCKED/PARTIAL) |
| `torch.cuda.is_available()` False inside the env (probe `--env-check`) | driver too old for the CUDA 12 runtime of the PyPI torch wheel; or no GPU on this node | run on the GPU node; check the driver with `nvidia-smi`; the notebook's alternative is `torch==2.5.1` from the cu124 index — say it comes from the notebook, not the README |

## 2. Command line

| Symptom | Cause | Fix |
|---|---|---|
| argparse "expected one argument" for `--normal` (wording unverified, exit 2) | value-less boolean | `--normal True` / `--normal False` |
| `argument --normal: expected True or False, got 'yes'` (exit 2) | `parse_bool` accepts only true/false, any case (`predict.py:37-43`) | `True` / `False` |
| `--keep_size is only available in fast mode, so it needs --normal False` / `--crop_check is only available in fast mode, so it needs --normal False` (exit 2) | fast-mode options with `--normal True` (`predict.py:189-192`) | drop one of them |
| "the following arguments are required: -i/--in_map_path, -o/--out_dir" (exit 2) | missing `-i`/`-o` | add them; note this run still downloaded the weights first if they were missing |
| `RuntimeError: File <path> is not a cryo-em density map file format.` | name does not end in lower-case `mrc`/`map` (`.ccp4`, `.MRC`, `.gz`, `.mrcs`) (`grid_utils.py:215`, `:229-230`) | decompress / rename / symlink to `.mrc` |
| `-g 0,1` but only one GPU works | single device by design (`cuda:0`) | one index; one job per GPU |
| a scheduler-assigned GPU is ignored, two jobs land on GPU 0 | `-g` (default `"0"`) overwrote `CUDA_VISIBLE_DEVICES` (`predict.py:194`) | `-g "${CUDA_VISIBLE_DEVICES:-0}"` (derived; runbook R16c) |

## 3. Input map

| Symptom | Cause | Fix |
|---|---|---|
| `# Input grid is not orthogonal. EXIT.` then nothing, exit status probably 0 | CELLB angles not all 90 (`grid_utils.py:160-167`) | not a single-particle-style map; CryoCodex cannot use it. Scripts must check outputs, not only the exit code |
| mrcfile error about the map ID, mode or file size (wording unverified) | corrupt/truncated download, unusual mode, non-MRC file | `python3 scripts/inspect_map.py map.mrc`; re-download; convert to float32 MRC |
| NumPy error early in preprocessing (wording unverified) | no positive voxel (header DMAX ≤ 0) | check the map's sign and content; CryoCodex needs positive density |
| part of the molecule missing in fast-mode outputs | auto-crop missed it (corners outside the inscribed sphere, separated bodies; G33) | `--normal True`, or `--crop_check True` at an interactive terminal |
| NumPy broadcast error with `--keep_size True` on a very small map (wording unverified) | 1 Å box axis < 48: padded crop does not fit the canvas (derived; runbook R12b) | drop `--keep_size` |

## 4. Resources and GPU

| Symptom | Cause | Fix |
|---|---|---|
| `torch.OutOfMemoryError: CUDA out of memory` (wording unverified) | batch too large for the card, or other processes on the GPU | lower `-b` (9 fitted 8 GB on an A800); check `nvidia-smi` for other jobs; the CLI has no automatic retry |
| process `Killed`, exit 137, oom-kill in `dmesg`/Slurm | host RAM: all windows are held in memory (~2.2 MB each) | more `--mem` (estimate with `inspect_map.py`); fast mode instead of normal; a larger stride reduces windows (e.g. 16–24; effect on quality not documented — the Scipion GPU test uses 24) |
| failure around pinning memory (wording unverified) | very many windows → large pinned allocation (`seg.pin_memory()`, `predict.py:90`) | as above; fewer windows |
| "no CUDA GPUs are available" / "invalid device ordinal" / "no NVIDIA driver" (wording unverified; runbook R16a) | wrong `-g` index, empty `CUDA_VISIBLE_DEVICES`, login node, driver problem | `nvidia-smi -L`; correct `-g`; run on the GPU node |
| slow start before the progress bar | `conda run` start-up, map resampling, numba JIT compilation (G34) | expected; time the first fixture run |

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
| score maximum > 1 | cubic reverse resampling overshoot; no upper clamp (C11) | expected after `--reverse_interpolation True`; on the 1 Å grid it would be a finding (report it) |
| mask all 0 / enhanced map all 0 | nothing recognised as molecule (very low resolution, unusual map, wrong sign) | check the input; try `--normal True`; report it |
| planes of zeros inside the outputs | stride > 44 | `-s` 1–44 (default 12) |
| outermost 2 voxels are 0 | blending margin (derived) | expected |
| `round_1_check/` folders left, no maps, `RuntimeError: Crop inspection needs terminal input.` | `--crop_check True` without a terminal (EOF) | never in batch; rerun without it |
| job hangs after `[Enter] Continue without changes  |  [e] Edit bounds: ` | `--crop_check True` waiting for input (no timeout) | cancel; rerun without it |
| earlier results changed | same `-o` and `-n` → overwritten silently | a new `-o` per run |
