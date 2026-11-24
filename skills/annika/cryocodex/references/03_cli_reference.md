# 03 — CLI reference (source code at `a35e73a`; live `--help` not yet captured)

Take flags only from this file. §3 is the **allowlist**, §4 the **never-emit** list. Live help text will be pasted
into §6 after the first host runs the runbook (R3, R6, R9).

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
6. `exec conda run --no-capture-output -n <env> python predict.py -m <ckpt> "$@"` (`predict.sh:94`).

So `./predict.sh --version` and any call with a typo in an option **download the weights first** when they are missing.

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
| `-g <index>` | `--gpu` | str, `"0"` | written to `CUDA_VISIBLE_DEVICES`; one index; under Slurm `-g "${CUDA_VISIBLE_DEVICES:-0}"` (derived) |
| `--no_logo True` / `False` | — | bool, `False` | hide the banner |
| `--version` | — | action | prints `CryoCodex v1.0.0` (after the launcher's download step, §1) |
| `-h`, `-h advanced` | `--help` | — | §1–2 |
| hidden `-m` | `--model_path` | str, `<clone>/model_state_dicts/CryoCodex.pth` | `help=argparse.SUPPRESS`; always set by the launcher — don't pass it |

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
| `-m …` through `predict.sh` | the launcher already passes `-m`; which one wins is unverified |
| `-g 0,1`, `-g cpu`, `--device`, `--cpu` | one GPU only, CUDA only; no such options |
| `CUDA_VISIBLE_DEVICES=3 ./predict.sh …` (without `-g 3`) | overwritten by the `-g` default `"0"` |
| `-b 0` / negative; `-s 0`, negative or > 44 | division by zero / range error / uncovered voxels |
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
| `-h advanced` | "Full option list" | omits the hidden `-m` |

## 6. Live help capture

Not captured yet. After runbook R3/R6/R9 on a host, paste `./predict.sh -h`, `./predict.sh -h advanced`,
`./predict.sh --version` and one argparse error verbatim here with host, date and exit codes, and move the matching
rows from "derived/source" to "verified".
