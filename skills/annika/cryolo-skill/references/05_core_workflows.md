# 05 · Core workflows (VALIDATED against crYOLO 1.9.9)

All commands here are **VALIDATED against crYOLO 1.9.9** — every flag, default, and
positional below matches the captured live `--help` (see filenames cited per command) and,
for the configure→predict path, the GPU smoke run on a Linux + NVIDIA GPU host
(the validation run). Apply the config gate first
(`SKILL.md §0`): run the read-only env probe per machine. On a probe verdict of
`supported`/`partial` the skill MAY emit concrete commands with the user's real paths and
run real jobs **after explicit user confirmation** (and never blindly on the user's real
data). On macOS the probe reports unsupported (crYOLO has no macOS path, ref 02) — that is
a probe-driven per-platform outcome, not a property of any one host.

## Workflow map (from `cryolo_gui.py` actions, S3)

`config → train → predict → evaluation → boxmanager` are the `cryolo_gui.py` actions
(`cryolo_gui.py.help.txt`). Each also exists as a standalone script —
`cryolo_predict.py`, `cryolo_train.py`, `cryolo_evaluation.py`,
plus `janni_denoise.py`, `cryolo_boxmanager_legacy.py`, `cryolo_boxmanager_tools.py`,
`cryolo_evaluation_tomo.py`, and `napari_boxmanager` (`_versions.txt` "which scripts").
The most evidence-backed end-to-end path (run on GPU) is **configure → predict**.

## A. Configure (`cryolo_gui.py config`)

Purpose: write a `config.json` (model architecture, box size, filter, and — if training —
the train/valid folders). VALIDATED against crYOLO 1.9.9
(captured help: `cryolo_gui.config.help.txt`).

Positionals are exactly `config_out_path boxsize`. **The trailing integer is the box
size** (`220` in the docs example, `160` in the smoke run) — resolved, not a gap. Help text:
"You should specify the same box size here as you used in your training data … In case of
the general model fill in your target box size." On disk the box size maps into
`model.anchors` (e.g. `[160,160]`) and `max_box_per_image` defaults to `700`
(`work/cryolo/config_cryolo.json`; ref 04).

Validated smoke command (`config_gen.log`):

```bash
cryolo_gui.py config config_cryolo.json 160 --filter NONE
```

Key defaults (captured `cryolo_gui.config.help.txt`):

- `-a/--architecture` `PhosaurusNet` (choices `{PhosaurusNet,YOLO,crYOLO}`)
- `--input_size` `1024` (downsizes the shorter dimension; rarely changed)
- `-nm/--norm` `STANDARD` (choices `{STANDARD,GMM}`; GMM is experimental)
- `-f/--filter` `LOWPASS` (choices `{NONE,LOWPASS,JANNI}`)
- `--low_pass_cutoff` `0.1`; `--janni_overlap` `24`; `--janni_batches` `3`
- `--filtered_output` `filtered_tmp/`; `--saved_weights_name` `cryolo_model.h5`; `--log_path` `logs/`
- Training-section defaults (written only when training fields are set): `--train_times` `10`,
  `--batch_size` `4`, `--learning_rate` `0.0001`, `--nb_epoch` `200`, `--object_scale` `5.0`,
  `--no_object_scale` `1.0`, `--coord_scale` `1.0`, `--class_scale` `1.0`
- `--num_patches` and `--overlap_patches` are **DEPRECATED**

### Filter selection (resolved from captured defaults)

- `LOWPASS` (default): low-pass filter with `--low_pass_cutoff` (default `0.1`). The robust
  default for ordinary picking.
- `JANNI`: neural-network denoising — requires `--janni_model <.h5>` (default `None`); tune
  with `--janni_overlap` / `--janni_batches`. `janni_denoise.py {config,train,denoise}` is the
  underlying denoiser (`janni_denoise.py.help.txt`).
- `NONE`: disables filtering entirely (used in the smoke run).

The captured help documents *what* each filter does; choosing between LOWPASS and JANNI for a
specific dataset is dataset-dependent tuning — soft guidance, not a captured rule.

## B. Predict with a model (`cryolo_predict.py`)

VALIDATED against crYOLO 1.9.9 (captured help: `cryolo_predict.py.help.txt` /
`cryolo_gui.predict.help.txt`). Run on GPU in the smoke test.

Validated command (the real validated invocation, generalized to typical flags):

```bash
cryolo_predict.py -c config_cryolo.json -w <model.h5> -i mics/ -o out/ -g 0 -t 0.3
```

Smoke run actually executed (`logs/cmdlogs/command_predict_20260606-131938.txt`):

```bash
cryolo_predict.py -c config_cryolo.json -w <general_model.h5> -i mics/ -o out/ -g 0 --otf -t 0.2
```

- Required: `-c/--conf` (config), `-w/--weights` (the model `.h5` — scratch-trained, refined,
  or a general model), `-i/--input` (one or more image folders/images), `-o/--output`.
- `-t/--threshold` default `0.3` (0–1, higher = more conservative); `-g/--gpu` (GPU `0` if
  not set otherwise by the system).
- Other optional: `-d/--distance` `0`, `--minsize`/`--maxsize` `None` (mainly for the general
  model), `-pbs/--prediction_batch_size` `3`, `--gpu_fraction` `1.0`, `-nc/--num_cpu` `-1`,
  `--norm_margin` `0.0`, `--monitor`, `--otf`, `--cleanup`, `--skip`, `--write_empty`.
  `-p/--patch` is **DEPRECATED**.
- Micrograph input format **MRC is confirmed** (the smoke run read `synth_0001.mrc` directly;
  VALIDATION_SUMMARY line 35).
- Probe-driven: requires an NVIDIA GPU (`-g 0`, ref 02). Emit and run only on a
  `supported`/`partial` machine after explicit confirmation.

### Outputs (under `-o`)

VALIDATED on disk (`work/cryolo/out/` tree). crYOLO creates these subfolders under `-o`:

- `EMAN/*.box` — thresholded detections.
- `STAR/*.star` — thresholded, RELION columns `_rlnCoordinateX` / `_rlnCoordinateY`
  (confirmed in `out/STAR/synth_0001.star`).
- `CBOX/*.cbox` — **all** detections including below-threshold, plus confidence and size.
- `CRYOSPARC/` — native cryoSPARC-style coordinate export (`predict.log`: "Write cryoSPARC
  coordinates").
- `DISTR/` — distribution outputs.

Both `CRYOSPARC/` and `DISTR/` are created even in the minimal non-filament smoke run (they
were present but empty). State these as folders crYOLO always creates; do not claim `DISTR/`
is filament-only. The native `CRYOSPARC/` export plus RELION `_rlnCoordinateX/Y` STAR columns
are confirmable interop facts (see ref 06).

Troubleshooting note: `--otf` is silently ignored when the config filter is `NONE`
(`predict.log`: "You specified the --otf option. However, filtering is not configured …
therefore crYOLO will ignore --otf").

### General models

- crYOLO can predict with a **pretrained general model** passed as `-w` (the help notes `-w`
  "can either be a model that you trained from scratch, a refined model or a general model").
  The validated run used a **PhosaurusNet general model file**,
  `gmodel_phosnet_201912_N63.h5` (`command_predict_20260606-131938.txt`; `predict.log`) — so a
  general-model file is a real, named artifact, no longer abstract.
- **Do not package, ship, or download crYOLO/JANNI weights** as part of the skill. Pretrained
  weights may carry usage terms **separate** from the package license — see
  `07_safety_license_privacy.md`. The official download URL and provenance of general models
  remain a soft gap; do not advise a download without sourcing the official page.

## C. Train / refine (`cryolo_train.py`)

VALIDATED against crYOLO 1.9.9 (captured help: `cryolo_train.py.help.txt` /
`cryolo_gui.train.help.txt`). Full train flags are captured — this is no longer a gap.

Train from scratch:

```bash
cryolo_train.py -c config.json -w 5 -g 0
```

Fine-tune a general/previous model (set warmup `0` and `--fine_tune`; the config must point
`pretrained_weights` at the model):

```bash
cryolo_train.py -c config.json -w 0 --fine_tune -g 0
```

- Required: `-c/--conf`; `-w/--warmup` (default `5`; **set to `0` when fine-tuning**).
- Optional: `-g/--gpu`, `-nc/--num_cpu` `-1` (half the CPUs by default), `--gpu_fraction` `1.0`,
  `-e/--early` `10` (early-stop patience), `--fine_tune`, `-lft/--layers_fine_tune` `2`,
  `--cleanup`, `--ignore_directions`.
- Deprecated/special: `--seed` `10`, `--warm_restarts`, `--skip_augmentation`.
- The config must supply `train_image_folder` and `train_annot_folder` (and optionally
  `valid_image_folder` / `valid_annot_folder`; otherwise crYOLO holds out 20% for validation)
  — see `cryolo_gui.config.help.txt` and ref 04. For `--fine_tune`, set `pretrained_weights`
  in the config (typically a general model).

## D. Evaluation (`cryolo_evaluation.py`)

VALIDATED against crYOLO 1.9.9 (captured help: `cryolo_evaluation.py.help.txt` /
`cryolo_gui.evaluation.help.txt`). Evaluates a trained model and writes an **HTML report**.

```bash
# Preferred: evaluate against the runfile produced by training (runfiles/ folder)
cryolo_evaluation.py -c config.json -w model.h5 -r runfiles/<run>.json -o result_evaluation.html -g 0

# Alternative: supply ground-truth images + box files directly
cryolo_evaluation.py -c config.json -w model.h5 -i test_images/ -b test_boxfiles/ -o result_evaluation.html -g 0
```

- Required: `-c/--config`, `-w/--weights`.
- `-r/--runfile`: the runfile from the `runfiles/` folder where training was started (lists
  the validation images). In most cases use this.
- `-o/--output`: default `result_evaluation.html`.
- Optional ground-truth path (leave `-r` empty): `-i/--images`, `-b/--boxfiles`.
- `-g/--gpu`: default `0`.

## E. Visualization (`boxmanager`)

VALIDATED flags against crYOLO 1.9.9 (captured help: `cryolo_gui.boxmanager.help.txt`):

```bash
cryolo_gui.py boxmanager -i IMAGE_DIR -b BOX_DIR [--wildcard "*_new_*.mrc"]
```

- `-i/--image_dir`, `-b/--box_dir`, `--wildcard` (select specific images, e.g. `*_new_*.mrc`).
- A newer napari front-end, `napari_boxmanager`, also exists (`_versions.txt`).
- This launches a GUI: do so **only on explicit user request**, and only on a machine where
  the probe verdict supports it.

## F. Filaments / tomograms

Flag-level VALIDATED against crYOLO 1.9.9 (captured help: `cryolo_predict.py.help.txt`).
Deeper parameter tuning is soft guidance.

- **Filament mode** (predict): `--filament`, with `-bd/--box_distance`,
  `-mn/--minimum_number_boxes`, `-sm/--straightness_method {NONE,LINE_STRAIGHTNESS,RMSD}`
  (default `LINE_STRAIGHTNESS`), `-st/--straightness_threshold` `0.95`,
  `-sr/--search_range_factor` `1.41`, `-ad/--angle_delta` `10`,
  `--directional_method {PREDICTED,CONVOLUTION}`, `-fw/--filament_width`,
  `-mw/--mask_width` `100`, `--nomerging` (`--nosplit` is DEPRECATED).
- **Tomography mode** (predict): `--tomogram`, with `-tsr/--tracing_search_range` `-1`,
  `-tmem/--tracing_memory` `0`, `-mn3d/--minimum_number_boxes_3d` `2`,
  `-tmin/--tracing_min_length` `5`, `-twin/--tracing_window_size` `-1`,
  `-tedge/--tracing_min_edge_weight` `0.4`, `-tmerge/--tracing_merge_thresh` `0.8`.
- A dedicated tomogram evaluator, `cryolo_evaluation_tomo.py`, also exists (`_versions.txt`);
  its flags are not separately captured here.

## Decision: general vs trained model (probe-permitting)

1. No annotations yet, standard particle → consider a **general model** with `predict`
   (source the model file/provenance; do not ship weights).
2. Have annotations, or the general model underperforms → **train** (`cryolo_train.py`,
   warmup `5`) or **fine-tune** a general model (`-w 0 --fine_tune`), then predict with the
   resulting `.h5`. Use `cryolo_evaluation.py` to quantify quality.
3. Confirm the machine is `supported`/`partial` (ref 02) before running; on an unsupported
   probe verdict (e.g. macOS) keep it explanatory only. On a supported machine, emit concrete
   commands with the user's real paths and run only after explicit confirmation.
