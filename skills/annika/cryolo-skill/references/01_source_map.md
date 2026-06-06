# 01 · Source map (what backs each claim)

**This file is the source map for the skill: it records what backs each claim and at
what tier of authority.** If a flag, config key, output folder, support status, or
license term is not traceable to an entry here, treat it as a **source gap** and do not
state it as fact.

There are two authoritative tiers. Higher tier wins on any conflict:

- **Tier 1 — VALIDATED against crYOLO 1.9.9.** Captured live `--help` from a real install
  plus a GPU smoke run on a Linux + NVIDIA GPU host. These directly observed the CLI flags,
  defaults, subcommands, file formats, and output layout. The captured `*.help.txt` files
  and the smoke run's on-disk artifacts back every concrete CLI claim — this tier is the
  allowlist.
- **Tier 2 — SOURCED from docs.** Rendered ReadTheDocs pages + pinned source, used for
  policy facts (platform/GPU support, license, conceptual workflow) and for anything not
  exercised by the smoke run.

The captured help and smoke were produced against the same version the docs are pinned
to (crYOLO 1.9.9), so Tier 1 and Tier 2 describe the same build (see "Installed build").

## Version pin

- Pinned to crYOLO **1.9.9**.
- Installed build that produced Tier 1 evidence reports `cryolo 1.9.9` —
  see "Installed build" below — matching the docs source pin, so all captured `--help`
  is **VALIDATED against crYOLO 1.9.9**.
- Docs: `https://cryolo.readthedocs.io/en/stable/` (rendered).
- Source pin: `MPI-Dortmund/cryolo` tag **`1.9.9`** / commit
  **`30039bde34d65c179541568b0c27f09916ac5652`**, as exposed by the ReadTheDocs
  "Edit on GitHub" links and verified via `git ls-remote` (HEAD = master = tag 1.9.9).
- Latest rendered changelog section captured: **1.9.9**.
- `/stable/` resolved to the above pin **as of 2026-06-05**; re-verify the concrete
  version `/stable/` points to before trusting it later (Audit-A P1-5).

## Installed build (Tier 1 ground truth)

| Component | Value | Source |
|---|---|---|
| crYOLO | **1.9.9** | `_versions.txt`; the validation run |
| TensorFlow | **1.15.5** | `_versions.txt`; the validation run |
| keras | **2.3.1** | `_versions.txt`; the validation run |
| Python env | **py3.8** | the validation run |
| GPU / driver / CUDA | NVIDIA GPU / driver 535 / CUDA 12.2 | the validation run |
| Probe verdict on this host | `status = supported` (Linux + NVIDIA) | the validation run |

This is one validated data point, not a hardcoded machine requirement. The skill's
read-only probe (`scripts/cryolo_env_probe.py`) computes support **per host**; the table
above just records the build the captured help and smoke were taken from.

## Captured live help (Tier 1, VALIDATED against crYOLO 1.9.9)

The captured live-help files (listed below). Every CLI flag/default/subcommand
claim in the skill must match these **exactly**.

| File | Backs |
|---|---|
| `_versions.txt` | Installed build versions + the `which scripts` list of installed entry points |
| `cryolo_gui.py.help.txt` | Front-end subcommands `{config,train,predict,evaluation,boxmanager}` |
| `cryolo_gui.config.help.txt` | Full `config` flag set, positionals, allowed values, defaults |
| `cryolo_gui.train.help.txt` | `train` action flags/defaults (mirror of `cryolo_train.py`) |
| `cryolo_gui.predict.help.txt` | `predict` action flags/defaults (mirror of `cryolo_predict.py`) |
| `cryolo_gui.evaluation.help.txt` | `evaluation` action flags/defaults (mirror of `cryolo_evaluation.py`) |
| `cryolo_gui.boxmanager.help.txt` | `boxmanager` flags |
| `cryolo_predict.py.help.txt` | Standalone predict: full flag set incl. Filament + Tomography groups |
| `cryolo_train.py.help.txt` | Standalone train: full flag set |
| `cryolo_evaluation.py.help.txt` | Standalone evaluation: full flag set |
| `janni_denoise.py.help.txt` | JANNI denoiser subcommands `{config,train,denoise}` |

## Smoke evidence (Tier 1, what actually ran on GPU)

- The validation run — crYOLO section (PASS on GPU).
- Smoke-run artifacts:
  - `config_gen.log` — `cryolo_gui.py config config_cryolo.json 160 --filter NONE`.
  - `config_cryolo.json` — minimal config actually written (see "Installed build" facts below).
  - `logs/cmdlogs/command_predict_20260606-131938.txt` — exact predict command run.
  - `predict.log` — runtime log (model load, `--otf`-ignored note, cryoSPARC write).
  - `out/{EMAN,STAR,CBOX,CRYOSPARC,DISTR}/` — output layout on disk.

## Captured docs pages (Tier 2)

| # | Page | URL | Used for |
|---|---|---|---|
| S1 | Installation | https://cryolo.readthedocs.io/en/stable/installation.html | OS/GPU support, CUDA/cuDNN dependency |
| S2 | License | https://cryolo.readthedocs.io/en/stable/other/license.html | Non-commercial license terms |
| S3 | Tutorials overview | https://cryolo.readthedocs.io/en/stable/tutorials/tutorial_overview.html | Conceptual GUI actions, output folders |
| S4 | Other (config) | https://cryolo.readthedocs.io/en/stable/other/other.html | config.json sections + key fields |
| S5 | Homepage / Troubleshooting / Changes | .../, .../troubleshooting.html, .../changes.html | Navigation; changelog version |

Underlying capture: `sources/web/docs_inventory.md` in this project (fetched
2026-06-05T21:01–21:10Z). All pages fetched 2026-06-05; each has a GitHub source link at
commit `30039bde…`. The skill ships this distilled map, not the raw inventory.

## What is VALIDATED (Tier 1 — quotable as fact, with captured-help citation)

- **Front-end & installed scripts** (VALIDATED against crYOLO 1.9.9; `cryolo_gui.py.help.txt`,
  `_versions.txt`): front-end is `cryolo_gui.py {config,train,predict,evaluation,boxmanager}`.
  Standalone scripts that EXIST on the install: `cryolo_predict.py`, `cryolo_train.py`,
  `cryolo_evaluation.py`, `janni_denoise.py`, `cryolo_boxmanager_legacy.py`,
  `cryolo_boxmanager_tools.py`, `cryolo_evaluation_tomo.py`, `napari_boxmanager`.
- **`config` positionals & defaults** (VALIDATED; `cryolo_gui.config.help.txt`):
  positionals are exactly `config_out_path boxsize`. The integer is the **box size**
  (e.g. `220` in the docs example, `160` in the smoke run). Defaults:
  `-a/--architecture PhosaurusNet` `{PhosaurusNet,YOLO,crYOLO}`;
  `--input_size 1024` (shorter image dim is downscaled to this; accepts `H W`);
  `-nm/--norm STANDARD` `{STANDARD,GMM}`;
  `-f/--filter LOWPASS` `{NONE,LOWPASS,JANNI}`; `--low_pass_cutoff 0.1`;
  `--janni_overlap 24`; `--janni_batches 3`; `--filtered_output filtered_tmp/`;
  `--train_times 10`; `--batch_size 4`; `--learning_rate 0.0001`; `--nb_epoch 200`;
  `--object_scale 5.0`; `--no_object_scale 1.0`; `--coord_scale 1.0`;
  `--class_scale 1.0`; `--saved_weights_name cryolo_model.h5`; `--log_path logs/`.
  `--num_patches` and `--overlap_patches` are **DEPRECATED**.
- **`config_cryolo.json` written shape** (VALIDATED; `work/cryolo/config_cryolo.json`):
  the box size maps into `model.anchors` (`anchors: [160,160]`), `model.max_box_per_image`
  default `700`. Minimal written shape is
  `{"model":{architecture,input_size,anchors,max_box_per_image,norm},"other":{log_path}}`;
  `train`/`valid` sections are only written when training fields are supplied.
- **`predict` flags & defaults** (VALIDATED; `cryolo_predict.py.help.txt`,
  `cryolo_gui.predict.help.txt`): required `-c/--conf`, `-w/--weights`,
  `-i/--input` (one or more folders/images), `-o/--output`. Optional `-t/--threshold`
  default **0.3**; `-g/--gpu` (GPU 0 by default); `-d/--distance 0`;
  `--minsize`/`--maxsize` default None; `-pbs/--prediction_batch_size 3`;
  `--gpu_fraction 1.0`; `-nc/--num_cpu -1`; `--norm_margin 0.0`; `--monitor`; `--otf`;
  `--cleanup`; `--skip`. Filament group: `--filament`, `-bd/--box_distance`,
  `-mn/--minimum_number_boxes`, `-sm/--straightness_method {NONE,LINE_STRAIGHTNESS,RMSD}`
  default `LINE_STRAIGHTNESS`, `-st 0.95`, `-sr 1.41`, `-ad 10`,
  `--directional_method {PREDICTED,CONVOLUTION}`, `-fw/--filament_width`,
  `-mw/--mask_width 100`, `--nosplit` (DEPRECATED), `--nomerging`. Tomography group:
  `--tomogram`, `-tsr -1`, `-tmem 0`, `-mn3d 2`, `-tmin 5`, `-twin -1`, `-tedge 0.4`,
  `-tmerge 0.8`. `-p/--patch` is DEPRECATED; `--write_empty` writes empty box files.
- **`train` flags & defaults** (VALIDATED; `cryolo_train.py.help.txt`,
  `cryolo_gui.train.help.txt`): required `-c/--conf`, `-w/--warmup` (default **5**; set
  `0` when fine-tuning). Optional `-g/--gpu`, `-nc/--num_cpu -1`, `--gpu_fraction 1.0`,
  `-e/--early 10` (early-stop patience), `--fine_tune`, `-lft/--layers_fine_tune 2`,
  `--cleanup`, `--ignore_directions`. Deprecated/special: `--seed 10`, `--warm_restarts`,
  `--skip_augmentation`.
- **`evaluation` flags** (VALIDATED; `cryolo_evaluation.py.help.txt`,
  `cryolo_gui.evaluation.help.txt`): required `-c/--config`, `-w/--weights`. `-r/--runfile`
  (the runfile from the `runfiles/` folder of a training run); `-o/--output` default
  `result_evaluation.html`. Optional `-i/--images`, `-b/--boxfiles` (ground truth),
  `-g/--gpu` default 0.
- **`boxmanager` flags** (VALIDATED; `cryolo_gui.boxmanager.help.txt`): `-i/--image_dir`,
  `-b/--box_dir`, `--wildcard`.
- **JANNI denoiser** (VALIDATED; `janni_denoise.py.help.txt`): `janni_denoise.py
  {config,train,denoise}` — the real denoiser invoked by `--filter JANNI`.
- **Micrograph input format** (VALIDATED; `predict.log`, `VALIDATION_SUMMARY.md` line 35):
  **MRC confirmed** — `synth_0001.mrc` was read directly.
- **Output layout under `-o`** (VALIDATED; `work/cryolo/out/`, `predict.log`,
  `VALIDATION_SUMMARY.md` lines 32–34):
  - `EMAN/*.box` — thresholded picks.
  - `STAR/*.star` — thresholded picks, RELION columns `_rlnCoordinateX` / `_rlnCoordinateY`
    (confirmed in `out/STAR/synth_0001.star`).
  - `CBOX/*.cbox` — **all** detections incl. below-threshold, plus confidence + estimated size.
  - `CRYOSPARC/` and `DISTR/` — both folders are created by crYOLO even in a minimal,
    non-filament run (both were empty in the smoke). State them as folders crYOLO creates;
    do **not** claim `DISTR/` is filament-only (the on-disk tree contradicts
    `VALIDATION_SUMMARY.md` line 34 on this point).
- **cryoSPARC / RELION interop** (VALIDATED; `predict.log`, `out/CRYOSPARC/`, `out/STAR/`):
  `predict.log` shows "Write cryoSPARC coordinates" and a `CRYOSPARC/` dir is produced, so
  crYOLO **natively writes a cryoSPARC-style coordinate export**. STAR output already uses
  RELION `_rlnCoordinateX/Y`. These are confirmable interop facts (supersede the older
  "interop wholly uncaptured/deferred" framing — see `06_interoperability.md`).
- **`--otf` vs `--filter NONE`** (VALIDATED; `predict.log`): `--otf` is **silently ignored**
  when the config filter is `NONE` ("you specified the --otf option. However, filtering is
  not configured … therefore crYOLO will ignore --otf"). Useful troubleshooting note.
- **Validated smoke commands** (VALIDATED; `config_gen.log`,
  `logs/cmdlogs/command_predict_20260606-131938.txt`):
  - `cryolo_gui.py config config_cryolo.json 160 --filter NONE`
  - `cryolo_predict.py -c config_cryolo.json -w <general_model.h5> -i mics/ -o out/ -g 0 --otf -t 0.2`
  - The general model used was `gmodel_phosnet_201912_N63.h5` (a PhosaurusNet general
    model). A general-model `.h5` is a real, named artifact, but do **not** ship it — cite
    license/privacy (`07_safety_license_privacy.md`).

## What is SOURCED (Tier 2 — docs policy facts, with citation)

- **[S1] Platform/GPU support** (verbatim): officially-run OSes Ubuntu 18.04 LTS / Ubuntu
  20.04 / CentOS 7; *"We don't test it but it should run on Windows as well."*; listed
  GPUs all NVIDIA (Titan V, GTX 1080, GTX 1080Ti, RTX 2080 TI, GV 100); *"As the GPU
  accelerated version of tensorflow does not support MacOS, crYOLO does not support it
  either."*; *"crYOLO depends on CUDA Toolkit and the cuDNN library. These will be
  automatically installed during crYOLO installation."* (macOS-unsupported is a TRUE
  per-platform fact; surface it as a probe-driven outcome, not "this machine is blocked".)
- **[S2] License** (verbatim): "SPHIRE-crYOLO Complimentary Science Software License
  Agreement"; "licensed for non-commercial academic and research purposes only … royalty
  free"; "explicitly prohibited to use … for commercial purposes or operational use";
  must not use if you do not agree.
- **[S4] config.json top-level sections**: `model`, `train`, `valid`, `other` (Tier 1
  confirms `model` + `other` are written for a minimal/general-model config; `train`/`valid`
  appear only when training fields are supplied).
- **[S4] config.json key fields**: `architecture`, `input_size`, `anchors`,
  `max_box_per_image`, `norm`, `filter`, `train_image_folder`, `train_annot_folder`,
  `train_times`, `pretrained_weights`, `batch_size`, `learning_rate`, `nb_epoch`,
  `saved_weights_name`, `valid_image_folder`, `valid_annot_folder`, `valid_times`,
  `log_path`.

> Note: the older S3 verbatim CLI examples are now **superseded by Tier 1**. The predict
> example's `-t 0.3` is just the default per `cryolo_predict.py.help.txt`; the config
> example's positional `220` is the **box size** per `cryolo_gui.config.help.txt`. Use the
> validated smoke commands above and the captured help for any concrete CLI claim.

## What is a GAP (NOT captured — do not assert; resolve before claiming)

Most former P0 gaps are now **RESOLVED** by Tier 1 evidence and are recorded above. Only
genuine remaining gaps stay in this table.

| Gap | Priority | Status / resolve by |
|---|---|---|
| BOX/CBOX coordinate **origin / y-flip** convention | P1 | STAR origin partially resolved: STAR uses RELION `_rlnCoordinateX/_rlnCoordinateY` (`out/STAR/synth_0001.star`). Y-flip origin for EMAN `.box` / CBOX is **not** confirmed by the captured artifacts — keep as a **verify-on-import** note (test round-trip against RELION/cryoSPARC). |
| Deeper **filament / tomogram workflow** tuning (recommended parameter values, multi-step recipes) | P1 | Flag level is RESOLVED for predict (full Filament + Tomography groups in `cryolo_predict.py.help.txt`); workflow tuning beyond defaults stays a soft gap — capture dedicated tutorials. |
| General-model **names, download URLs, provenance, model-weight license** | P0/P1 | One named artifact observed (`gmodel_phosnet_201912_N63.h5`, smoke) but its download/provenance/license is not captured — capture official model/download pages (separate from package license). |
| **napari-boxmanager** import/export details | P1 | Partially resolved: `napari_boxmanager` exists as an installed script (`_versions.txt`); its import/export flags/behavior are not captured — capture interoperability docs. |
| **Benchmark / performance** numbers | P1 | Read captured papers (`08_validation_and_benchmarks.md`). |
| **Troubleshooting** specifics (exact errors/fixes) beyond captured | P1 | One confirmed item: `--otf` ignored with `--filter NONE` (`predict.log`). Capture the troubleshooting page in full for the rest. |
| Full TensorFlow / CUDA / driver **compatibility matrix** | P2 | One validated data point: TF 1.15.5 / keras 2.3.1 with crYOLO 1.9.9 on an NVIDIA GPU / driver 535 / CUDA 12.2 (the validation run; `_versions.txt`). A full matrix is still uncaptured. |
| **Windows** support detail beyond "untested, should run" | P2 | Capture if Windows becomes in-scope. |
