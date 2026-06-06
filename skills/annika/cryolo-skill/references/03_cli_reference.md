# 03 · CLI reference — VALIDATED against crYOLO 1.9.9

**Every command, flag, default, and subcommand on this page is VALIDATED against crYOLO
1.9.9** (captured live `--help` from the install: `cryolo 1.9.9 / tensorflow
1.15.5 / keras 2.3.1`, see `_versions.txt`). The captured-help files are the authority;
every claim below cites the exact file it came from. Two of the example command lines were
actually run on GPU during smoke validation — they are marked **SMOKE-RUN** with their log.

These commands are runnable on a machine whose probe verdict is `supported`/`partial`
(`python3 scripts/cryolo_env_probe.py`, `SKILL.md §0`). On such a machine the skill MAY emit
concrete commands with the user's real paths and run real jobs **after explicit user
confirmation** (`07_safety_license_privacy.md`). crYOLO is GPU-only and does not support
macOS — a macOS host will probe as unsupported (a per-platform fact, not a per-machine ban;
see `02_config_session_and_environment.md`).

## Scripts / actions that exist (VALIDATED against crYOLO 1.9.9 — `_versions.txt`, `cryolo_gui.py.help.txt`)

- **`cryolo_gui.py`** — front-end dispatching to sub-commands
  `{config, train, predict, evaluation, boxmanager}`
  (`cryolo_gui.py.help.txt`).
- **`cryolo_predict.py`** — standalone prediction; same flags as `cryolo_gui.py predict`
  (`cryolo_predict.py.help.txt`).
- **`cryolo_train.py`** — standalone training; same flags as `cryolo_gui.py train`
  (`cryolo_train.py.help.txt`).
- **`cryolo_evaluation.py`** — standalone evaluation; same flags as `cryolo_gui.py
  evaluation` (`cryolo_evaluation.py.help.txt`).
- **`janni_denoise.py`** — JANNI denoiser with sub-commands `{config, train, denoise}`;
  this is the neural-network denoiser invoked by `--filter JANNI`
  (`janni_denoise.py.help.txt`).
- Also present on `PATH` (captured in the `which scripts` list of `_versions.txt`, but
  full `--help` not captured here): `cryolo_boxmanager_legacy.py`,
  `cryolo_boxmanager_tools.py`, `cryolo_evaluation_tomo.py`, `napari_boxmanager`.

> The standalone `cryolo_train.py` and `cryolo_evaluation.py` scripts are real and have
> captured `--help` — they are **no longer a gap** (`_versions.txt` `which scripts` list;
> `cryolo_train.py.help.txt`; `cryolo_evaluation.py.help.txt`).

## `cryolo_gui.py config` — generate a config (`cryolo_gui.config.help.txt`)

**Positional arguments are exactly `config_out_path boxsize`** (`cryolo_gui.config.help.txt`,
"General arguments"). The integer is the **box size** — `config_out_path` names the JSON to
create, `boxsize` is "the same box size here as you used in your training data … In case of
the general model fill in your target box size."

```bash
# No filter — SMOKE-RUN exactly as below (config_gen.log; VALIDATION_SUMMARY line 18)
cryolo_gui.py config config_cryolo.json 160 --filter NONE

# Low-pass filter (default filter; cutoff default 0.1)
cryolo_gui.py config config_cryolo.json 220 --filter LOWPASS --low_pass_cutoff 0.1

# JANNI neural-network denoising (needs a JANNI model .h5; download/terms = ref 07)
cryolo_gui.py config config_cryolo.json 220 --filter JANNI --janni_model /path/to/janni_general_model.h5
```

| Token | Default | Meaning (VALIDATED — `cryolo_gui.config.help.txt`) |
|---|---|---|
| `config_out_path` (positional) | — | Name of the configuration JSON to create. |
| `boxsize` (positional) | — | Box size, in pixels. For a general model, your target box size. Maps into `model.anchors` in the JSON (see below). |
| `-a {PhosaurusNet,YOLO,crYOLO}`, `--architecture` | `PhosaurusNet` | Backend network architecture. |
| `--input_size INPUT_SIZE [INPUT_SIZE ...]` | `1024` | Shorter image dimension is downsized to this; rarely changed. Accepts one value, or `H W` separated by whitespace. |
| `-nm {STANDARD,GMM}`, `--norm` | `STANDARD` | Image normalization. `GMM` is experimental (slower; normalizes to ice). |
| `--filtered_output FILTERED_OUTPUT` | `filtered_tmp/` | Output folder for filtered images. |
| `-f {NONE,LOWPASS,JANNI}`, `--filter` | `LOWPASS` | Noise filter applied before training/picking. |
| `--low_pass_cutoff LOW_PASS_CUTOFF` | `0.1` | Low-pass cutoff frequency (used with `LOWPASS`). |
| `--janni_model JANNI_MODEL` | `None` | Path to JANNI model `.h5` (used with `JANNI`). Model download/terms = ref 07. |
| `--janni_overlap JANNI_OVERLAP` | `24` | Overlap of patches in pixels (JANNI only). |
| `--janni_batches JANNI_BATCHES` | `3` | Number of batches (JANNI only). |
| `--pretrained_weights PRETRAINED_WEIGHTS` | (empty) | `.h5` used for initialization when fine-tuning a previous model. |
| `--train_image_folder TRAIN_IMAGE_FOLDER` | (empty) | Training images. Leave empty only when using a general model. |
| `--train_annot_folder TRAIN_ANNOT_FOLDER` | (empty) | Training annotation (box/star) files. Leave empty only for a general model. |
| `--train_times TRAIN_TIMES` | `10` | How often each image is presented per epoch. |
| `--batch_size BATCH_SIZE` | `4` | Images processed in parallel during training. |
| `--learning_rate LEARNING_RATE` | `0.0001` | Training step size. |
| `--nb_epoch NB_EPOCH` | `200` | Maximum number of training epochs. |
| `--object_scale OBJECT_SCALE` | `5.0` | Penalty for missing particles. |
| `--no_object_scale NO_OBJECT_SCALE` | `1.0` | Penalty for picking background. |
| `--coord_scale COORD_SCALE` | `1.0` | Penalty for position errors. |
| `--class_scale CLASS_SCALE` | `1.0` | Irrelevant (crYOLO has only the class "particle"). |
| `--saved_weights_name SAVED_WEIGHTS_NAME` | `cryolo_model.h5` | Path for saving final weights. |
| `--valid_image_folder VALID_IMAGE_FOLDER` | (empty) | Optional explicit validation images (else 20% of training is held out). |
| `--valid_annot_folder VALID_ANNOT_FOLDER` | (empty) | Optional explicit validation box files. |
| `--log_path LOG_PATH` | `logs/` | Path for log saving. |
| `--debug` | (on) | Emit extra training statistics. |
| `--num_patches NUM_PATCHES` | `1` | **DEPRECATED** patch mode. |
| `--overlap_patches OVERLAP_PATCHES` | `200` | **DEPRECATED** (patch-mode overlap). |

> **Config JSON shape produced** (VALIDATED — smoke `config_cryolo.json`): the minimal run
> wrote `{"model": {"architecture","input_size","anchors":[160,160],"max_box_per_image":700,
> "norm"}, "other": {"log_path"}}`. The `boxsize` positional lands in `model.anchors` (here
> `[160,160]`); `max_box_per_image` defaults to `700`; the `train`/`valid` sections are only
> written when training fields are supplied. See `04_data_model_and_formats.md`.

## `cryolo_predict.py` / `cryolo_gui.py predict` — pick particles

Identical flag set in both forms (`cryolo_predict.py.help.txt`, `cryolo_gui.predict.help.txt`).

```bash
# Validated picking — adapted from the SMOKE-RUN command
# (command_predict_20260606-131938.txt). -t shown at its default 0.3.
cryolo_predict.py -c config_cryolo.json -w <general_model.h5> -i mics/ -o out/ -g 0 -t 0.3

# Exactly what ran on GPU during smoke validation
# (command_predict_20260606-131938.txt; used a PhosaurusNet general model and -t 0.2):
cryolo_predict.py -c config_cryolo.json -w /path/to/gmodel_phosnet_201912_N63.h5 -i mics/ -o out/ -g 0 --otf -t 0.2
```

Both `-t 0.3` (the captured default) and `-t 0.2` (the smoke run) are valid; the threshold
is yours to set per dataset, lower = more permissive.

### Required arguments (VALIDATED — `cryolo_predict.py.help.txt`)

| Flag | Meaning |
|---|---|
| `-c CONF`, `--conf` | crYOLO configuration JSON. |
| `-w WEIGHTS`, `--weights` | Trained model `.h5` — from scratch, refined, or a general model. |
| `-i INPUT [INPUT ...]`, `--input` | One or more image folders / images (GUI takes directories only). |
| `-o OUTPUT`, `--output` | Output folder; all particle coordinates are written there. |

### Optional arguments (VALIDATED — `cryolo_predict.py.help.txt`)

| Flag | Default | Meaning |
|---|---|---|
| `-t THRESHOLD`, `--threshold` | `0.3` | Confidence threshold in [0,1]; higher = more conservative. |
| `-g GPU [GPU ...]`, `--gpu` | GPU 0 | GPU id(s), whitespace-separated. Requires an NVIDIA GPU (ref 02). |
| `-d DISTANCE`, `--distance` | `0` | Remove particles closer than this (pixels). Not for filament mode. |
| `--minsize MINSIZE` | `None` | Drop particles with estimated diameter below this; mostly for the general model. |
| `--maxsize MAXSIZE` | `None` | Drop particles with estimated diameter above this; mostly for the general model. |
| `-pbs PREDICTION_BATCH_SIZE`, `--prediction_batch_size` | `3` | Images predicted per batch; lower to resolve memory issues. |
| `--gpu_fraction GPU_FRACTION` | `1.0` | Fraction of GPU memory used (0.0–1.0). |
| `-nc NUM_CPU`, `--num_cpu` | `-1` | CPUs for filtering / filament tracing; `-1` = all available. |
| `--norm_margin NORM_MARGIN` | `0.0` | Relative margin size for normalization. |
| `--monitor` | off | Monitor the input folder (for automation); stop by writing `stop.cryolo` there. |
| `--otf` | off | On-the-fly filtering; filtered micrographs are not written to disk (may be slower). |
| `--cleanup` | off | Delete filtered images when done. |
| `--skip` | off | Skip images already picked. |

### Filament options (VALIDATED — `cryolo_predict.py.help.txt`, "Filament options")

| Flag | Default | Meaning |
|---|---|---|
| `--filament` | off | Activate filament mode. |
| `-bd BOX_DISTANCE`, `--box_distance` | `None` | Distance (pixels) between two boxes. |
| `-mn MINIMUM_NUMBER_BOXES`, `--minimum_number_boxes` | `None` | Minimum boxes per filament. |
| `-sm {NONE,LINE_STRAIGHTNESS,RMSD}`, `--straightness_method` | `LINE_STRAIGHTNESS` | Straightness measure used for splitting. |
| `-st STRAIGHTNESS_THRESHOLD`, `--straightness_threshold` | `0.95` | Threshold for the straightness method. |
| `-sr SEARCH_RANGE_FACTOR`, `--search_range_factor` | `1.41` | Connection search range = box size × this factor. |
| `-ad ANGLE_DELTA`, `--angle_delta` | `10` | Angle delta (deg); curvier filaments may need ~20. |
| `--directional_method {PREDICTED,CONVOLUTION}` | (see help) | Direction estimation method. |
| `-fw FILAMENT_WIDTH`, `--filament_width` | `None` | Filament width (pixels); only needed for `CONVOLUTION`. |
| `-mw MASK_WIDTH`, `--mask_width` | `100` | Gaussian mask elongation; only used with `CONVOLUTION`. |
| `--nosplit` | off | **DEPRECATED** — use `--straightness_method NONE` instead. |
| `--nomerging` | off | Do not merge filaments. |

### Tomography options (VALIDATED — `cryolo_predict.py.help.txt`, "Tomography options")

| Flag | Default | Meaning |
|---|---|---|
| `--tomogram` | off | Activate tomography picking mode. |
| `-tsr TRACING_SEARCH_RANGE`, `--tracing_search_range` | `-1` | Search range (pixels); `-1` = 25% of box size. |
| `-tmem TRACING_MEMORY`, `--tracing_memory` | `0` | Max frames a particle may vanish then reappear and still count as the same. |
| `-mn3d MINIMUM_NUMBER_BOXES_3D`, `--minimum_number_boxes_3d` | `2` | (filaments) Minimum boxes per filament. |
| `-tmin TRACING_MIN_LENGTH`, `--tracing_min_length` | `5` | (particles) Minimum trace length to count as a particle. |
| `-twin TRACING_WINDOW_SIZE`, `--tracing_window_size` | `-1` | (filaments) Averaging window; `-1` = box size. |
| `-tedge TRACING_MIN_EDGE_WEIGHT`, `--tracing_min_edge_weight` | `0.4` | (filaments) Edge weight (0–1) for cross-slice overlap. |
| `-tmerge TRACING_MERGE_THRESH`, `--tracing_merge_thresh` | `0.8` | (filaments) Overlap (0–1) above which filaments fully merge. |

### Deprecated / special

| Flag | Default | Meaning |
|---|---|---|
| `-p PATCH`, `--patch` | `None` | **DEPRECATED** — set patches in the config instead. |
| `--write_empty` | off | Write empty box files when no particle is found. |

> **Usage note — `--otf` with `--filter NONE`** (VALIDATED — `predict.log`): when the config
> filter is `NONE`, crYOLO **silently ignores `--otf`** and logs: "You specified the --otf
> option. However, filtering is not configured in your config line, therefore crYOLO will
> ignore --otf." `--otf` only matters when a `LOWPASS`/`JANNI` filter is configured. (This is
> why the smoke command above passed `--otf` yet ran on unfiltered MRC without error.)

> **Output layout under `-o`** (VALIDATED — smoke `out/` tree; see also
> `04_data_model_and_formats.md`): the minimal non-filament run created
> `EMAN/` (`*.box`, thresholded), `STAR/` (`*.star`, thresholded, RELION
> `_rlnCoordinateX`/`_rlnCoordinateY` columns), `CBOX/` (`*.cbox`, **all** detections incl.
> below-threshold, with confidence + size), plus **`CRYOSPARC/` and `DISTR/`** — both folders
> were created even in the minimal run (they were empty here). The log line "Write cryoSPARC
> coordinates" confirms crYOLO natively writes a cryoSPARC-style coordinate export (see
> `06_interoperability.md`). Treat `CRYOSPARC/` and `DISTR/` as folders crYOLO creates; do not
> assume `DISTR/` is filament-only. Micrograph input `.mrc` is read directly (confirmed in
> `predict.log`).

## `cryolo_train.py` / `cryolo_gui.py train` — train a model

Identical flag set in both forms (`cryolo_train.py.help.txt`, `cryolo_gui.train.help.txt`).
Training inputs (image/annotation folders, validation, weights name) come from the **config
JSON** built with `cryolo_gui.py config`, not from train flags.

```bash
# Train from scratch (warmup default 5)
cryolo_train.py -c config_cryolo.json -w 5 -g 0

# Fine-tune a general model (set warmup 0; needs pretrained_weights in the config)
cryolo_train.py -c config_cryolo.json -w 0 --fine_tune -lft 2 -g 0
```

| Flag | Default | Meaning (VALIDATED — `cryolo_train.py.help.txt`) |
|---|---|---|
| `-c CONF`, `--conf` (required) | `None` | Path to the configuration file. |
| `-w WARMUP`, `--warmup` (required) | `5` | Warmup epochs. Set to `0` when fine-tuning. |
| `-g GPU [GPU ...]`, `--gpu` | GPU 0 | GPU id(s), whitespace-separated. |
| `-nc NUM_CPU`, `--num_cpu` | `-1` | CPUs during training; default uses half the available CPUs. |
| `--gpu_fraction GPU_FRACTION` | `1.0` | Fraction of GPU memory used (0.0–1.0). |
| `-e EARLY`, `--early` | `10` | Early-stop patience (epochs without validation-loss improvement). |
| `--fine_tune` | off | Fine-tune mode: only the last layers train; requires `pretrained_weights` in the config (a general model is typical). |
| `-lft LAYERS_FINE_TUNE`, `--layers_fine_tune` | `2` | Layers trained when fine-tuning. |
| `--cleanup` | off | Delete filtered images when done. |
| `--ignore_directions` | off | Skip directional learning for filament training data. |
| `--seed SEED` | `10` | RNG seed (mainly validation-image selection); keep constant across runs. |
| `--warm_restarts` | off | Warm restarts + cosine annealing. |
| `--skip_augmentation` | off | Deactivate data augmentation. |

## `cryolo_evaluation.py` / `cryolo_gui.py evaluation` — evaluate a model

Identical flag set in both forms (`cryolo_evaluation.py.help.txt`,
`cryolo_gui.evaluation.help.txt`).

```bash
# Evaluate using the runfile from the training run's runfiles/ folder
cryolo_evaluation.py -c config_cryolo.json -w cryolo_model.h5 -r runfiles/run_<...>.json -o result_evaluation.html -g 0

# Or evaluate against explicit ground-truth images + boxes (leave -r empty)
cryolo_evaluation.py -c config_cryolo.json -w cryolo_model.h5 -i gt_images/ -b gt_boxes/ -g 0
```

| Flag | Default | Meaning (VALIDATED — `cryolo_evaluation.py.help.txt`) |
|---|---|---|
| `-c CONFIG`, `--config` (required) | `None` | Configuration file (`.json`). |
| `-w WEIGHTS`, `--weights` (required) | `None` | Trained model (`.h5`). |
| `-r RUNFILE`, `--runfile` | `None` | Runfile (`.json`) from the `runfiles/` folder of training; lists the validation images used to evaluate. |
| `-o OUTPUT`, `--output` | `result_evaluation.html` | HTML results file. |
| `-i IMAGES`, `--images` | `None` | Folder of test images (ground truth) — use when `-r` is empty. |
| `-b BOXFILES`, `--boxfiles` | `None` | Folder of ground-truth box files — use when `-r` is empty. |
| `-g GPU`, `--gpu` | `0` | GPU id. |

## `cryolo_gui.py boxmanager` — display boxes

GUI viewer (`cryolo_gui.boxmanager.help.txt`). Requires a display; not headless.

| Flag | Default | Meaning (VALIDATED — `cryolo_gui.boxmanager.help.txt`) |
|---|---|---|
| `-i IMAGE_DIR`, `--image_dir` | `None` | Path to image directory. |
| `-b BOX_DIR`, `--box_dir` | `None` | Path to box directory. |
| `--wildcard WILDCARD` | `None` | Wildcard for selecting specific images (e.g. `*_new_*.mrc`). |

## `janni_denoise.py` — JANNI denoiser (`janni_denoise.py.help.txt`)

Sub-commands `{config, train, denoise}` — create a JANNI config, train JANNI on your data,
or denoise micrographs with a (pre)trained model. This is the denoiser engaged by crYOLO's
`--filter JANNI`. Per-sub-command flags were not captured here; capture live `--help` for the
specific sub-command before scripting it (genuine remaining gap).

## Trust posture

CLI behavior on this page is **VALIDATED against crYOLO 1.9.9**, not live-unverified. On a
`supported`/`partial` machine the skill may emit these commands with the user's real paths and
run them after explicit confirmation. The remaining safety rules — license, privacy, no blind
installs of system-level deps, confirm before running on real data — still apply
(`07_safety_license_privacy.md`). If you run on a different crYOLO version, re-capture
`--help`/`--version` (`python3 scripts/cryolo_env_probe.py`) and reconcile any differences
before trusting a flag for that version.
