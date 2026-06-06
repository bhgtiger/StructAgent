# 04 · Data model and file formats

VALIDATED against crYOLO 1.9.9 (captured help: `cryolo_gui.config.help.txt`,
`cryolo_predict.py.help.txt`) and the GPU smoke run on a Linux + NVIDIA GPU host
(the validation run, plus its on-disk artifacts). The config schema and output layout below
are confirmed against the file crYOLO actually wrote (`config_cryolo.json`)
and the prediction output tree (`out/`). Field meanings/defaults are quoted
from the captured `cryolo_gui.py config` help. Genuinely unresolved details are still
marked **GAP** — do not assert those.

## config.json

The recommended way to build a config is the `cryolo_gui.py config` command (ref 03), not
hand-editing — that command is what writes a valid file and is the source of the schema
below.

**Minimal config actually written by the smoke run** (`work/cryolo/config_cryolo.json`,
from `cryolo_gui.py config config_cryolo.json 160 --filter NONE`):

```jsonc
{
  "model": {
    "architecture": "PhosaurusNet",   // -a/--architecture {PhosaurusNet,YOLO,crYOLO}, default PhosaurusNet
    "input_size": 1024,               // --input_size, default 1024 (downsize of shorter edge, not micrograph size)
    "anchors": [160, 160],            // = [boxsize, boxsize]; here from the `config ... 160` positional
    "max_box_per_image": 700,         // default 700
    "norm": "STANDARD"                // -nm/--norm {STANDARD,GMM}, default STANDARD
  },
  "other": {
    "log_path": "logs/"               // --log_path, default logs/
  }
}
```

> **Section → field mapping (RESOLVED for the minimal case).** For a general-model
> picking config crYOLO writes exactly two sections: `model` (`architecture`,
> `input_size`, `anchors`, `max_box_per_image`, `norm`) and `other` (`log_path`). The
> `boxsize` positional maps into **`model.anchors = [boxsize, boxsize]`** (the `160` in the
> smoke command produced `"anchors": [160, 160]`). `max_box_per_image` defaults to **700**.

**Additional sections appear when training fields are supplied.** When you pass training
arguments to `cryolo_gui.py config` the file also gains `train` / `valid` sections. The
field names and their defaults are from `cryolo_gui.config.help.txt`:

```jsonc
{
  "model": {
    "architecture": "PhosaurusNet",
    "input_size": 1024,
    "anchors": [220, 220],
    "max_box_per_image": 700,
    "norm": "STANDARD",
    "filter": []                      // populated by -f/--filter {NONE,LOWPASS,JANNI}, default LOWPASS,
                                      //   plus --low_pass_cutoff (0.1) or JANNI params; exact serialized
                                      //   filter sub-schema: GAP (not written in the NONE smoke run)
  },
  "train": {
    "train_image_folder": "",         // --train_image_folder (empty only when using a general model)
    "train_annot_folder": "",         // --train_annot_folder (box/star annotation folder)
    "train_times": 10,                // --train_times, default 10
    "pretrained_weights": "",         // --pretrained_weights (h5; set for fine-tuning)
    "batch_size": 4,                  // --batch_size, default 4
    "learning_rate": 0.0001,          // --learning_rate, default 0.0001
    "nb_epoch": 200,                  // --nb_epoch, default 200
    "object_scale": 5.0,              // --object_scale, default 5.0
    "no_object_scale": 1.0,           // --no_object_scale, default 1.0
    "coord_scale": 1.0,               // --coord_scale, default 1.0
    "class_scale": 1.0,               // --class_scale, default 1.0 (crYOLO has only "particle")
    "saved_weights_name": "cryolo_model.h5"  // --saved_weights_name, default cryolo_model.h5
  },
  "valid": {
    "valid_image_folder": "",         // --valid_image_folder (default: 20% of training data)
    "valid_annot_folder": ""          // --valid_annot_folder
  },
  "other": { "log_path": "logs/" }
}
```

> The exact JSON key/section into which each `--filter`/JANNI option is serialized was not
> exercised (the smoke run used `--filter NONE`, which wrote no `filter` block). Treat the
> serialized **filter sub-schema as a remaining GAP**; build filter configs via the
> `cryolo_gui.py config -f ...` command rather than hand-editing. `--num_patches` and
> `--overlap_patches` are **DEPRECATED** (see ref 03) and should not appear in new configs.

## Input data

- Prediction takes one or more **input micrograph folders or image files** via
  `-i/--input` (`cryolo_predict.py.help.txt`; ref 03).
- **Micrograph format MRC is supported / CONFIRMED.** The smoke run read `synth_0001.mrc`
  directly with no conversion step (`work/cryolo/predict.log`; VALIDATION_SUMMARY line 35).
  Other input formats accepted by crYOLO were not exercised here — do not enumerate beyond
  MRC without sourcing (**GAP** for non-MRC specifics).
- Training/validation use `train_image_folder` + `train_annot_folder` (and the optional
  `valid_*` pair). The annotation folder holds **box or star files** per the help text
  (`--train_annot_folder`: "annotation files like box or star files"). The exact accepted
  annotation column layout for input was not separately exercised here (**GAP**).

## Output data (after prediction `-o`)

VALIDATED against crYOLO 1.9.9 — subfolders observed on disk under the prediction output
folder (`work/cryolo/out/`, the minimal non-filament smoke run):

| Folder | Contents |
|---|---|
| `EMAN` | `.box` files for detections **above** the selected/default confidence threshold. |
| `STAR` | `.star` files for detections **above** the selected/default threshold; RELION `_rlnCoordinateX/_rlnCoordinateY` columns (confirmed in `out/STAR/synth_0001.star`). |
| `CBOX` | **All** detections, including those below threshold; carries confidence and estimated size (VALIDATION_SUMMARY lines 32-34). |
| `CRYOSPARC` | Native cryoSPARC-style coordinate export. `predict.log` logs "Write cryoSPARC coordinates" and this folder is created. |
| `DISTR` | Confidence/size distribution plots and machine-readable text files. |

Notes:

- `CBOX` is the superset (with confidence + size); `EMAN`/`STAR` are thresholded exports.
- **`CRYOSPARC/` and `DISTR/` are standard subfolders crYOLO creates**, not filament-only.
  Both were present in the minimal non-filament run (they were empty because the single
  detection was deleted as "not fully immersed"). VALIDATION_SUMMARY line 34 calling `DISTR`
  filament/distribution-only is contradicted by the on-disk `out/` tree — state both as
  folders crYOLO always creates under `-o`.
- This means crYOLO **natively writes both a RELION-style STAR export and a cryoSPARC-style
  coordinate export** for every prediction run (interop detail; see ref 06).
- Filament / tomogram output variants (`--filament`, `--tomogram`): not exercised here.
  Their additional/altered outputs are a **GAP** (ref 05 covers the workflows).

## File headers / column layouts

- **STAR (RESOLVED, header).** `out/STAR/synth_0001.star` begins:

  ```
  data_

  loop_
  _rlnCoordinateX #1
  _rlnCoordinateY #2
  ```

  i.e. a standard RELION coordinate STAR with `_rlnCoordinateX`/`_rlnCoordinateY` columns —
  directly importable as RELION coordinates. (The smoke micrograph yielded zero retained
  particles, so no data rows followed the header; the per-row numeric layout under this
  loop was not separately captured — minor **GAP**.)
- **CBOX.** Carries all detections plus confidence and estimated particle size
  (VALIDATION_SUMMARY lines 32-34). The exact column order/headers of `.cbox` were not
  captured in this run (**GAP**).
- **EMAN `.box`.** The classic EMAN box layout; exact columns not separately captured here
  (**GAP**). Use `CBOX`/`STAR` when you need confidence or RELION-ready coordinates.

## Coordinate conventions

- crYOLO's STAR output uses RELION `_rlnCoordinateX` / `_rlnCoordinateY`
  (`out/STAR/synth_0001.star`), so it is structurally **compatible with RELION coordinate
  import** without renaming columns.
- crYOLO also emits a native cryoSPARC coordinate export under `CRYOSPARC/` (above), so
  both major downstream coordinate conventions are produced directly (ref 06).
- **Caution (verify on import):** the absolute origin and y-axis orientation
  (top-left vs bottom-left, possible y-flip) versus a given downstream package were not
  byte-verified against a populated file in this run. When importing into RELION/cryoSPARC,
  do a quick visual sanity check that picks land on particles and are not vertically
  mirrored — this is the classic silent-failure point. (Format/coordinate-frame details
  beyond the confirmed column names remain a verify-on-import item, not a blanket GAP.)

## When asked for exact fields/columns/coordinates

Quote the RESOLVED items above directly (config sections/defaults, the `boxsize →
model.anchors` mapping, `max_box_per_image` default 700, MRC input, the five output
subfolders, the STAR `_rlnCoordinateX/Y` header). For the items still marked **GAP** — the
serialized filter sub-schema, `.cbox`/`.box` column order, the per-row numeric layout, and
filament/tomogram output variants — say "not captured / source gap", point to
`01_source_map.md` and the captured-help files, and offer to capture them; do not fabricate
a schema, column list, or coordinate convention.
