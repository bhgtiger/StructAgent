# 03 — CLI reference (derived from pinned source)

**Provenance.** Flags, defaults, and choices below derive from pinned source at commit `961f028ca609017990de4473ab368cf1787e8282` — primarily `deepEMhancer/applyProcessVol/cmdParserOptionsDeepEMHancer.py`, with `cmdParser.py`, `config.py`, and `exeDeepEMhancer.py`. They were also **confirmed against a live DeepEMhancer 0.17 install** (the entry point, `tightTarget` default, half-map and model-path behavior all match) on a Linux/GPU host. Still, **the target machine's live `deepemhancer -h` overrides this for that machine**, since the Anaconda channel may carry 0.16. Biowulf's captured help is **version-skewed (module 0.13)** and is a cross-check only — do not treat it as the reference.

Console entry point: `deepemhancer` (`setup.py` → `deepEMhancer.exeDeepEMhancer:commanLineFun`).

## Options (authoritative table)

| Flag(s) | Type / choices | Default | Required | Meaning (from source help) |
|---|---|---|---|---|
| `-i`, `--inputMap` | str | — | **yes** | Input map to process, or half map 1. Should be **unmasked and not sharpened** (use maps directly from refinement, not post-processed). If half map 1, also provide `-i2`. |
| `-o`, `--outputMap` | str | — | **yes** | Output filename for the post-processed map. Must end `.mrc` or `.map`. |
| `-p`, `--processingType` | `wideTarget` \| `tightTarget` \| `highRes` | `tightTarget` | no | Which deep model to use. `wideTarget` is less sharp than `tightTarget`. `highRes` only recommended for overall FSC resolution < 4 Å. The source help says it is "ignored" with normalization mode 2 (`-m/--binaryMask`), **but at runtime a non-default `-p` is *not* silently ignored: `exeDeepEMhancer.py` asserts and the run fails. So do not pass `-p wideTarget`/`-p highRes` with `-m`; omit `-p` or use `-p tightTarget` (see the assertion row below).** |
| `-i2`, `--halfMap2` | str | `None` | no | Half map 2 (use with `-i` = half map 1). |
| `-s`, `--samplingRate` | float | `None` | no | Sampling rate (Å/voxel). If omitted, read from the MRC header. |
| `--noiseStats` | 2 floats: `NOISE_MEAN NOISE_STD` | — | no | **Normalization mode 1.** **Mutually exclusive with `-m/--binaryMask` — supplying both asserts and fails** (the help says "ignored if `--binaryMask` is provided," but the runtime aborts; see assertion section / `references/06`). If neither given, normalization is auto-estimated (may rarely fail/be less accurate). |
| `-m`, `--binaryMask` | str | `None` | no | **Normalization mode 2.** Binary mask (1 protein, 0 not). Forces the masked model; see assertions below. |
| `--deepLearningModelPath` | str (`PATH_TO_MODELS_DIR`) | `None` | no | Directory containing a non-default model, **or a path to an `.hd5` file** containing the model. **This is the real flag** (see conflicts). |
| `--cleaningStrengh` | float | `-1` | no | *(spelled exactly like this in source — "Strengh")* Post-process to remove small connected components ("hide dust"). Max relative size `0<s<1`, or `-1` to deactivate. |
| `-g`, `--gpuIds` | str | `"0"` | no | GPU id(s); comma-separated, e.g. `1,2,3`. **`-1` = CPU only (very slow).** |
| `-b`, `--batch_size` | int | `8` | no | Cubes processed simultaneously. **Lower it on CUDA OOM; raise it for low GPU utilization.** Source warns some inputs crash with >1 GPU — use 1 GPU in that case. |
| `--download` | optional path arg | — | no | Download default models (network + write). The skill performs this **only via `setup_deepemhancer_env.sh --download-models`, with confirmation** (see below). |
| `--version` | — | — | no | Prints `deepEMhancer.__version__`. **Heavyweight** (imports TF). |
| `-h`, `--help` | — | — | no | Help. **Heavyweight** (imports TF). |

Defaults from `config.py`: `BATCH_SIZE = 8`; `DEFAULT_MODEL_DIR = ~/.local/share/deepEMhancerModels/production_checkpoints`.

## Exact-spelling and phantom-flag traps (must preserve)

- **`--cleaningStrengh`** is misspelled in the real CLI (not "Strength"). When you reference or template it, write it **exactly** `--cleaningStrengh`, or it will not parse.
- **`--deepLearningModelDir` is NOT real.** The README example uses it, but no such option exists. The real flag is **`--deepLearningModelPath`**. Flag the README example as stale; never emit `--deepLearningModelDir`.
- **`-c` is a phantom.** The `cmdParser.py` epilog `example_text` shows `deepemhancer -c path/to/deep/learningModel ...`, but **no `-c` option is defined** by the parser. Do not present `-c` as real.
- **`--precomputedModel` is a phantom.** It appears only inside help text ("Supresses --precomputedModel option"; "model is selected using --precomputedModel") and the `exeDeepEMhancer` docstring, but **no such option exists**. Do not present it as real.

When a user pastes a command using any phantom/stale flag, correct it to `--deepLearningModelPath` (for the model-path case) and note the source of the confusion.

## Model-selection & assertion behavior (`exeDeepEMhancer.py`)

These are hard `assert`s — violating them crashes a real run (relevant when planning, and for troubleshooting in `references/06`):

- If `--deepLearningModelPath` points to **an `.hd5` file** (not a directory): `processingType` **must** be `tightTarget`. Error: *"-p option should not be provided if --deepLearningModelPath points to an hd5 file."*
- If `-m/--binaryMask` is provided: `processingType` **must** be `tightTarget`, and the model used is `deepEMhancer_masked.hd5`. Error: *"if binary mask provided, -p option should not be provided."*
- **`--noiseStats` and `-m/--binaryMask` are mutually exclusive.** Providing both raises *"only one of the following options can be provided: noise_stats, binary_mask"* and the run aborts (`processVol.py`). Choose exactly one normalization mode.
- **Output path must NOT already exist.** A real run asserts and aborts with the (confusingly worded) *"Error, output fnameIn already exists"* — and it fires **late**, only after the model is loaded. Pick a fresh `-o`, or remove/rename the old output, before re-running with tweaked flags.
- Otherwise the model file is `deepEMhancer_<processingType>.hd5` inside the model directory.
- Output name **must** end `.mrc` or `.map` (both accepted), though the assertion's error text mentions only `.mrc`.
- Input file must exist (`assert os.path.isfile(inputMap)`).

## Model directory & "models not found" behavior (`cmdParser.py`)

- If `--deepLearningModelPath` is omitted and the default dir does not exist, a **real run creates it** (`os.makedirs(DEFAULT_MODEL_DIR)`) — a side effect; the probe never does this.
- If neither the path is an `.hd5` file nor `<dir>/deepEMhancer_tightTarget.hd5` exists, a real run prints *"Deep learning models not found … Downloading default models with --download or indicate its location with --deepLearningModelPath."* and **`sys.exit(1)`**.
- `-g -1` is converted internally to "no GPU" (CPU).

## The model-download flag (network + write — consent-gated)

The download action does `requests.get(DOWNLOAD_MODEL_URL, stream=True)` to a Zenodo URL (`zenodo.org/record/7432763/...deepEMhancerModels_tf2.zip` for TF≥2, `_tf1.zip` otherwise), writes a ~705 MB zip (`MODEL_DOWNLOAD_EXPECTED_SIZE ≈ 721852*1024`), and unzips it. This is network + filesystem write. **The skill runs it only via `setup_deepemhancer_env.sh --download-models`, after explicit user confirmation and with a target directory** — never as an un-prompted command.

## Example shapes (CLI forms)

```text
# Default tightTarget, single full refinement map:
deepemhancer -i <input.mrc> -o <output.mrc>

# Half maps, highRes model (only if overall FSC < 4 Å):
deepemhancer -p highRes -i <half1.mrc> -i2 <half2.mrc> -o <output.mrc>

# Custom model directory (REAL flag; NOT --deepLearningModelDir):
deepemhancer -i <input.mrc> -o <output.mrc> --deepLearningModelPath <models_dir>
```

Fill placeholders with real paths only after a current, matching config; run via `scripts/run_deepemhancer.sh` and only after the user confirms (`references/05`, `references/00`). See `references/04` for input/model choice.
