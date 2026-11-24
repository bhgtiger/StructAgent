# 03 — CLI reference (source code at `a35e73a`; live help and messages captured 2026-11-24, §6)

Take flags only from this file. §3 is the **allowlist**, §4 the **never-emit** list. §6 holds the live help texts and
error messages from the validation host (runbook R3, R6, R7, R9, R14, R16a). Every step of §1 was observed there.

## 1. How a call flows

`predict.sh` (bash, `set -e`):
1. `-h` / `--help` anywhere in the arguments (not followed by `advanced`) → prints the short help (§2) and exits 0,
   **before** any conda or weights check (`predict.sh:50-55`).
2. Finds conda: `CONDA_EXE`, else `command -v conda`; must be executable → else
   `ERROR: Conda was not found. Install Conda and follow the README installation commands.` exit 1 (`predict.sh:57-63`).
3. `-h advanced` / `--help advanced` → `conda run … python predict.py --help` (needs the env, no weights) (`predict.sh:65-67`).
4. Checks the env with `conda run … python -c 'import sys'` → else
   `ERROR: Cannot use '<env>'. Complete the README installation commands first.` exit 1 (`predict.sh:69-73`).
5. If `model_state_dicts/CryoCodex.pth` is missing or empty → prints
   `Downloading the model weights to '<ckpt>' ...` and downloads 471 MB with `curl -fL --retry 2`; on failure
   `ERROR: Failed to download the model weights from '<URL>'` exit 1 (`predict.sh:75-91`).
6. `exec conda run --no-capture-output -n <env> python predict.py -m <ckpt> "$@"` (`predict.sh:94`). `conda run` passes
   the exit status through and, on failure, appends its own line
   `ERROR conda.cli.main_run:execute(49): \`conda run python …/predict.py -m … <args>\` failed. (See above for error)`
   (conda 23.7). It forwards stdin with `--no-capture-output` (verified).

So `./predict.sh --version` and any call with a typo in an option **download the weights first** when they are missing
(verified; with the lab server unreachable the call takes ~7 min and exits 1).

## 2. Short help (`./predict.sh -h`), verbatim from `predict.sh:18-46`

```text
usage: predict.sh [-h] -i MAP -o DIR

CryoCodex: cryo-EM map enhancement with local quality scores

==============================================================================
options:
  -h           Show every option with '-h advanced'
  -i MAP       Input EM density map (.mrc/.map)
  -o DIR       Directory to save the output maps

==============================================================================
modes:
  CryoCodex runs in one of two modes, picked with '--normal True|False'.
  In either mode, adding '--reverse_interpolation True' resamples the saved
  maps back to the voxel size of the input map; by default they are saved on
  the 1.0 Angstrom grid.

  fast mode (--normal False, the default)
      Crop the background around the molecule away and infer on the remaining
      part only, which makes the run much quicker. Two options belong to this
      mode alone:
          --crop_check True    review the cropped region before the inference
          --keep_size True     fill the cropped away background back in with
                               zeros, so the outputs span the whole input map

  normal mode (--normal True)
      Infer on the whole map, without cropping anything away. Slower, and
      neither --crop_check nor --keep_size applies here.
```
(`$CRYOCODEX_PROG` shows as the name you typed, e.g. `predict.sh`.)

## 3. Options (argparse, `predict.py:161-185`) — allowlist

| Emit exactly | Long / alias | Type, default | Meaning and conditions |
|---|---|---|---|
| `-i <MAP>` | `--in_map_path` | str, **required** | input map; path must end in lower-case `mrc` or `map` |
| `-o <DIR>` | `--out_dir` | str, **required** | output dir; created (`exist_ok=True`); same-name outputs are overwritten — use a fresh dir |
| `--normal True` / `--normal False` | — | bool, `False` | `False` = fast mode (crop background); `True` = whole map |
| `--reverse_interpolation True` / `False` | `-a` | bool, `False` | resample outputs back to the input voxel size (skipped if input is already 1.0 Å) |
| `--keep_size True` / `False` | — | bool, `False` | fast mode only: refill the cropped background with zeros on the 1 Å regridded box |
| `--crop_check True` / `False` | `-c` | bool, `False` | fast mode only, **interactive terminal only**: review crop images, edit bounds |
| `-n <name>` | `--out_name` | str, `cryocodex` | output base name (no `/`) |
| `-s <int>` | `--stride` | int, `12` | sliding-window stride in voxels (1 Å); keep **1–44** (derived: larger leaves gaps) |
| `-b <int>` | `--batch_size` | int, `9` | windows per GPU batch; ≥ 1; lower for small GPUs |
| `-g <index>` | `--gpu` | str, `"0"` | written to `CUDA_VISIBLE_DEVICES`; one index; under a scheduler `-g "${CUDA_VISIBLE_DEVICES:-0}"` (verified: without it a job given GPU 1 ran on GPU 0) |
| `--no_logo True` / `False` | — | bool, `False` | hide the banner |
| `--version` | — | action | prints `CryoCodex v1.0.0` (after the launcher's download step, §1) |
| `-h`, `-h advanced` | `--help` | — | §1–2 |
| hidden `-m` | `--model_path` | str, `<clone>/model_state_dicts/CryoCodex.pth` | `help=argparse.SUPPRESS`; always set by the launcher; a second `-m` from the user wins (verified) — don't pass it |

Booleans: `parse_bool` accepts `true`/`false` in any case, anything else →
`expected True or False, got '<value>'` (`predict.py:37-43`). Emit `True`/`False` (README form).

Mutual exclusions (`predict.py:189-192`), exit 2 via `parser.error`:
`--crop_check is only available in fast mode, so it needs --normal False` and
`--keep_size is only available in fast mode, so it needs --normal False`.

Env-level: `CRYOCODEX_ENV=<env>` (non-default env name), `CONDA_EXE=<path>` (conda not on `PATH`).

## 4. Never emit

| Spelling | Why |
|---|---|
| value-less `--normal`, `--reverse_interpolation`, `--keep_size`, `--crop_check`, `--no_logo`, `-a`, `-c` | argparse requires a value |
| `--normal 1`, `yes`, `on`, `0`, `no`, empty | rejected by `parse_bool` |
| `--normal True` with `--keep_size True` or `--crop_check True` | `parser.error` |
| `--crop_check True` in Slurm / `nohup` / cron / pipes / Scipion / scripts | blocks on `input()` forever, or `RuntimeError: Crop inspection needs terminal input.` on EOF |
| `-a`, `-c`, `--in_map_path`, `--out_dir`, `--out_name`, `--stride`, `--batch_size`, `--gpu` | valid in code but not the README spelling; use the short forms in §3 |
| `-m …` through `predict.sh` | the launcher already passes `-m`; the user's wins (verified), bypassing the clone's checkpoint |
| `-g 0,1`, `-g cpu`, `--device`, `--cpu` | one GPU only, CUDA only; no such options |
| `CUDA_VISIBLE_DEVICES=3 ./predict.sh …` (without `-g 3`) | overwritten by the `-g` default `"0"` |
| `-b 0` / negative; `-s 0`, negative or > 44 | division by zero / range error / uncovered voxels (`-s 46` left all-zero planes, verified) |
| `-b` > 9 on a GPU with ≤ 8 GB | `-b 9` peaks at 7,328 MiB; `-b 18` → `torch.OutOfMemoryError` on an 8 GB card (verified) |
| `-i` ending `.ccp4`, `.MRC`, `.MAP`, `.mrc.gz`, `.map.gz`, `.mrcs` | `RuntimeError: File <path> is not a cryo-em density map file format.` |
| `--half1`, `--half2`, `--mask`, `--resolution`, `--apix`, `--threads`, `--fp16`, `--mode`, `--fast` | do not exist |
| editing `CryoCodex_home` / `activate` / `CryoCodex_env` inside `predict.sh` | pre-release instructions; v1.0.0 resolves these itself |
| `pip install cryocodex` | not a package |

`scripts/build_cryocodex_command.py` enforces §3–§4.

## 5. Where the README and the code disagree (code wins)

| Topic | README | Code |
|---|---|---|
| Weights download | "on the first inference run" (`README.md:143`) | any `predict.sh` call except `-h`, incl. `--version` |
| `--keep_size True` | "outputs span the whole input map" | the 1 Å regridded box; equals the input box only for 1 Å inputs (with `--reverse_interpolation True` the input box is recovered up to rounding) |
| Crop-check images | `out_dir/round_1_check/` | `round_N_check/` per edit round, **deleted** when you continue; key `c` also continues |
| Input formats | `.map` / `.mrc` | suffix test on the path, case-sensitive |
| Stride | (no range) | > 44 leaves gaps (derived); notebook and Scipion allow 1–48 |
| `-h advanced` | "Full option list" | omits the hidden `-m` (verified) |

## 6. Live help and messages (verified 2026-11-24; predict.sh via conda 23.7.4; README env)

`./predict.sh -h` (exit 0, also with conda hidden from `PATH`) printed §2 byte-for-byte.

`./predict.sh -h advanced` (exit 0, no download):
```text
usage: predict.sh [-h] [--version] -i MAP -o DIR [--normal True|False]
                  [--reverse_interpolation True|False]
                  [--crop_check True|False] [--keep_size True|False]
                  [--out_name OUT_NAME] [--stride STRIDE]
                  [--batch_size BATCH_SIZE] [--gpu GPU] [--no_logo True|False]

CryoCodex: cryo-EM map enhancement with local quality scores

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  -i MAP, --in_map_path MAP
                        Input EM density map (.mrc/.map)
  -o DIR, --out_dir DIR
                        Directory to save the output maps
  --normal True|False   Infer on the whole map in normal mode; False (the
                        default) runs fast mode instead, which crops the
                        background away and is much quicker
  --reverse_interpolation True|False, -a True|False
                        Resample the saved maps back to the voxel size of the
                        input map; False (the default) saves them on the 1.0
                        Angstrom grid
  --crop_check True|False, -c True|False
                        Fast mode only: review the cropped region before the
                        inference
  --keep_size True|False
                        Fast mode only: fill the cropped away background back
                        in with zeros, so the outputs span the whole input
                        map; this restores the grid shape at the same voxel
                        size, unlike --reverse_interpolation which changes the
                        voxel size
  --out_name OUT_NAME, -n OUT_NAME
                        Base name of the output maps
  --stride STRIDE, -s STRIDE
                        Sliding-window stride
  --batch_size BATCH_SIZE, -b BATCH_SIZE
                        Number of boxes in one batch
  --gpu GPU, -g GPU     GPU ID to use
  --no_logo True|False  Do not show the logo banner
```

| Call | Output (last lines) | Exit |
|---|---|---|
| `--version` (checkpoint present) | `CryoCodex v1.0.0` | 0 |
| `--version` (no checkpoint, server unreachable) | `Downloading the model weights to '<clone>/model_state_dicts/CryoCodex.pth' ...`, curl progress, 3 × `curl: (28) Failed to connect to yanglab.qd.sdu.edu.cn port 443 after ~134000 ms`, `ERROR: Failed to download the model weights from 'https://yanglab.qd.sdu.edu.cn/CryoCodex/CryoCodex.pth'` | 1 |
| `CRYOCODEX_ENV=missing` | conda: `EnvironmentLocationNotFound: Not a conda environment: <envs_dir>/missing`, then `ERROR: Cannot use 'missing'. Complete the README installation commands first.` | 1 |
| `CONDA_EXE=/nonexistent/conda` | `ERROR: Conda was not found. Install Conda and follow the README installation commands.` | 1 |
| `--normal` (no value) | `predict.sh: error: argument --normal: expected one argument` | 2 |
| `--normal yes` | `predict.sh: error: argument --normal: expected True or False, got 'yes'` | 2 |
| `--normal True --keep_size True` | `predict.sh: error: --keep_size is only available in fast mode, so it needs --normal False` | 2 |
| `--normal True --crop_check True` | `predict.sh: error: --crop_check is only available in fast mode, so it needs --normal False` | 2 |
| no `-i` | `predict.sh: error: the following arguments are required: -i/--in_map_path` | 2 |
| `--no_logo TRUE` + missing file | `TRUE` accepted; `FileNotFoundError: [Errno 2] No such file or directory: '/nonexistent.mrc'` (the `-o` dir is created first) | 1 |
| `-i x.ccp4` / `x.MRC` / `x.map.gz` | `RuntimeError: File <path> is not a cryo-em density map file format.` | 1 |
| non-90° cell | `# Input grid is not orthogonal. EXIT.` — no files | **0** |
| `-m /nonexistent/CryoCodex.pth` | user `-m` wins: `FileNotFoundError: … '/nonexistent/CryoCodex.pth'` after preprocessing | 1 |
| `-g ""` | `RuntimeError: Attempting to deserialize object on a CUDA device but torch.cuda.is_available() is False. If you are running on a CPU-only machine, please use torch.load with map_location=torch.device('cpu') …` | 1 |
| `-b 18` on an 8 GB card | `torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 1.90 GiB. GPU 0 has a total capacity of 7.60 GiB of which 472.38 MiB is free. …` | 1 |
| `--keep_size True`, 1 Å box < 48 | `ValueError: could not broadcast input array from shape (48,48,48) into shape (41,41,41)` (`predict.py:71`) | 1 |

Every failing call through `predict.sh` ends with conda's `ERROR conda.cli.main_run:execute(49): … failed. (See above
for error)` line; through a site launcher (direct python) that line is absent. A successful run prints the banner,
`Improving <map> now, out_name:<n>`, `# Rescale voxel size from [a b c] to [1. 1. 1.]` (when resampling),
`# Mask cropping complete` (fast) or `# Normal mode: keeping the whole map, no background cropping`,
`# Box cutting complete, start inference`, a tqdm bar counting **windows** (175 for EMD-10387 fast, 1000 normal), then
`saving` / `path: <file>` four times; with keep/reverse also `# Filling the cropped away background back in, output grid
is (…)`, `# Interpolating the outputs from the 1.0 Angstrom grid back to the native voxel size […]` and `# Output grid is
now (…) at <voxel> Angstrom`.
