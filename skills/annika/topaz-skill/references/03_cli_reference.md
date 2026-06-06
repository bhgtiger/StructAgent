# 03 — CLI reference (VALIDATED against Topaz 0.3.20)

Invocation: `topaz <command> [options]`. Global `topaz --version`, `topaz --help`.
`@file.txt` expands to its lines (long arg lists).

> Every flag, default, format, and subcommand below is **[validated topaz 0.3.20 —
> captured: topaz.<cmd>.help.txt]** — confirmed against the live `topaz <cmd> --help`
> captured from Topaz 0.3.20 (`topaz.<cmd>.help.txt`). Source-only facts
> (e.g. MPS absence, device dispatch) are tagged `[sourced 0.3.20 @ 58fe5237]`; behaviors
> proven by GPU smoke runs are tagged `[smoke]`.
> On a host the probe reports as `valid`/`ready`, the skill MAY emit concrete commands with
> the user's real paths and run them **after explicit user confirmation** (see "Concrete-command
> rule" below). Safety still applies: no blind installs, private data stays local.

## Commands by group
Exact top-level groups [validated topaz 0.3.20 — captured: topaz.help.txt]:
**Particle picking:** `train`, `segment`, `extract`, `precision_recall_curve`
**Image processing:** `downsample`, `normalize`, `preprocess`, `denoise`, `denoise3d`
**File utilities:** `convert`, `split`, `particle_stack`, `train_test_split`
**GUI:** `gui` (opens the Topaz GUI in a web browser)
**[Deprecated]** (prefer `convert`): `scale_coordinates`, `boxes_to_coordinates`,
`star_to_coordinates`, `coordinates_to_star`, `coordinates_to_boxes`,
`coordinates_to_eman2_json`, `star_particles_threshold`

## `--device` semantics (CUDA-or-CPU only — see ref 02)
`>=0` → that CUDA GPU index; `<0` → CPU. There is **no MPS code path**
[sourced 0.3.20 @ 58fe5237: zero `mps` refs in `topaz/`; `topaz_mps_supported=False` in the
probe report]. Defaults differ per command [validated topaz 0.3.20 — evidence noted per row]:
| Command | `--device` default | evidence |
|---|---|---|
| `train` | `0` (GPU 0; `-1` forces CPU) | topaz.train.help.txt prints `(default: 0)` |
| `segment` | GPU if available (`<0` = CPU) | topaz.segment.help.txt prints `(default: GPU if available)` |
| `extract` | GPU if available (`<0` = CPU) | topaz.extract.help.txt prints **no** numeric default; value per source + smoke |
| `denoise` | `0` (GPU 0; `-1` forces CPU) | topaz.denoise.help.txt prints `(default: 0)` |
| `denoise3d` | `-2` (multi-GPU; `>=0` single GPU, `-1` CPU) | topaz.denoise3d.help.txt |
| `preprocess` | `-1` (CPU; `>=0` selects GPU) | topaz.preprocess.help.txt |
| `normalize` | `-1` (CPU; `>=0` selects GPU) | topaz.normalize.help.txt |

If the probe reports Apple Silicon / no NVIDIA GPU, Topaz runs **CPU-only** — pass **`-d -1`**
to avoid the CudaWarning. (`downsample` has no device flag; it always runs on CPU.)

## Key flags (all VALIDATED against captured help)

### `train` [captured: topaz.train.help.txt]
- `--train-images` / `--train-targets` **required** (file lists, or a directory of images).
  Optional `--test-images` / `--test-targets`.
- `-n/--num-particles` **OR** `--pi` is **required** (set the expected particles/micrograph,
  or the positive fraction directly).
- `-r/--radius` default **3** (px around each center counted positive).
- `--method {PN, GE-KL, GE-binomial, PU}` default **GE-binomial**.
- `-m/--model` default **resnet8**; `--units` default **32**. `--pretrained`/`--no-pretrained`
  (default pretrained ON; warm-starts from a bundled model when arch+units match, e.g.
  resnet8 with 64 units).
- `-k/--k-fold` cross-validation (with `--fold`, `--cross-validation-seed 42`).
- `--minibatch-size` 256, `--minibatch-balance` 0.0625, `--epoch-size` 1000,
  `--num-epochs` default **10**, `--learning-rate` 0.0002.
- `-s/--patch-size` 96, `-p/--patch-padding` 48.
- `--save-prefix` writes a checkpoint per epoch; `-o/--output` writes the **train/test curve**.
- `-d/--device` default **0**; `--num-workers 0`, `-j/--num-threads 0`.
- `--format {auto,coord,csv,star,box}`, `--image-ext`, `--describe` (print model, no train).
- Output [smoke]: per-epoch checkpoints named `<save-prefix>_epoch{N}.sav`
  (e.g. `model/topaz_smoke_epoch1.sav`). **GOTCHA** [smoke]: `--save-prefix DIR/...` requires
  `DIR` to **already exist** — Topaz does not create the parent dir (see 09_troubleshooting).

### `segment` [captured: topaz.segment.help.txt]
- positional `paths` (image files).
- `-m/--model` default **resnet16 (2D)** (bundled).
- `-o/--destdir` (output directory).
- `-d/--device` default **GPU if available**; `-p/--patch-size` default **None** (whole image);
  `-j/--num-threads 0`; `-v`.
- Output: per-image log-likelihood-ratio maps.

### `extract` [captured: topaz.extract.help.txt]
- positional `paths` (image files; **can be streamed from stdin**).
- `-m/--model` default **resnet16**; set `-m none` if inputs are already segmented
  (log-likelihood-ratio maps).
- `-r/--radius` — region radius; **NO default** (must be supplied, or tuned via `--targets`).
- `-t/--threshold` default **-6** — this is a **log-likelihood score threshold**
  ("-6 is p>=0.0025"), **NOT 0.5 and NOT a score quantile**.
- Radius tuning: `--targets` (maximizes AUPRC) with `--min-radius 5`, `--max-radius 100`,
  `--step-radius 5`; `--assignment-radius` (default = extraction radius); `--only-validate`.
- `-s/--down-scale` and `-x/--up-scale` (both default **1**).
- `--dims {2,3}` default **2** (micrographs); set **3** for tomograms.
- `-o/--output` (file to write); `--per-micrograph` (one file per micrograph) with optional
  `--suffix`; `--format {coord,csv,star,json,box}` default **coord**.
- `-d/--device` default **0**; `--num-workers 0`, `-j/--num-threads 0`, `-p/--patch-size 0`
  (no patching), `--batch-size 1`; `-v`.
- Output columns [smoke]: `image_name  x_coord  y_coord  score`.

### `denoise` (2D) [captured: topaz.denoise.help.txt]
- positional `micrographs`.
- `-m/--model` accepts **multiple** (outputs averaged), default **unet**. Pretrained `-m`
  names: **`unet, unet-small, fcnn, affine`** (note it is **fcnn**, not "fcnet"); older
  version via `unet-v0.2.1`. If `-m` is omitted, Topaz auto-loads a bundled pretrained model
  [smoke: loaded `unet_L2_v0.2.2.sav` on GPU].
- `-o/--output` is a **directory** (denoised micrographs). `--suffix` (default `.denoised`
  when no output dir), `--format` default **mrc**, `--normalize`, `--stack` (denoise an MRC
  stack rather than a list).
- `-d/--device` default **0**.
- Pre-filters: `--lowpass`, `--gaussian` (default 0), `--inv-gaussian` (default 0),
  `--deconvolve` (+ `--deconv-patch 1`), `--pixel-cutoff 0`.
- Training mode: `-a/--dir-a`, `-b/--dir-b`, `--hdf`, `--preload`, `--holdout 0.1`,
  `--method {noise2noise,masked}` (default noise2noise),
  `--arch {unet,unet-small,unet2,unet3,fcnet,fcnet2,affine}` (default unet — note the
  `--arch` choices include `fcnet`, distinct from the `-m` pretrained name `fcnn`),
  `--optim {adam,adagrad,sgd}` default **adagrad**, `--lr 0.001`,
  `--criteria {L0,L1,L2}` default **L2**, `-c/--crop 800`, `-s/--patch-size 1024`,
  `-p/--patch-padding 500`, `--batch-size 4`, `--num-epochs 100`, `--num-workers 16`,
  `--save-prefix`, `--save-interval 10`.

### `denoise3d` [captured: topaz.denoise3d.help.txt]
- positional `volumes`.
- `-m/--model` default **unet-3d** (options `unet-3d, unet-3d-10a, unet-3d-20a`, or a model path).
- `-o/--output` (directory for denoised volumes), `--suffix`.
- `-d/--device` default **-2 (multi-GPU)**; `>=0` single GPU, `-1` CPU.
- Training: `-a/--even-train-path`, `-b/--odd-train-path`, `--N-train 1000`, `--N-test 200`,
  `-c/--crop 96`, `--base-kernel-width 11`, `--optim {adam,adagrad,sgd}` (adagrad),
  `--lr 0.001`, `--criteria {L1,L2}` (L2), `--momentum 0.8`, `--batch-size 10`,
  `--num-epochs 500`, `-w/--weight_decay 0`, `--save-prefix`, `--save-interval 10`.
- Post/patching: `-g/--gaussian` (postprocessing std, 0 = none), `-s/--patch-size 96`,
  `-p/--patch-padding 48`; `--num-workers 1`, `-j/--num-threads 0`.

### `preprocess` / `downsample` / `normalize`
`preprocess` = `downsample` + `normalize` in one step [captured: topaz.preprocess.help.txt]:
- positional `files`.
- `-s/--scale` default **1** (downsample factor — **not 4**).
- `--affine` (standard (x-mu)/std normalization instead of GMM).
- `--sample` default **10** (pixel sampling factor for the model fit — there is **no
  `--pixel-sampling` flag**).
- `--niters` default **100** (max EM iterations — **not 200**); `-a/--alpha 900`, `-b/--beta 1`.
- `--metadata` (save per-micrograph parameters). There is **no `--seed`** flag.
- `-d/--device` default **-1** (CPU; `>=0` selects GPU).
- `-t/--num-workers` default 0 — **note `-t` here is num-workers, NOT a threshold**;
  `-j/--num-threads 0`.
- `-o/--destdir` (output directory); `--format` choices `mrc,tiff,png` (comma-separated for
  multiple) default **mrc**; `-v`.

`downsample` [captured: topaz.downsample.help.txt] is minimal — **only** `-s/--scale`
(default **4**), `-o/--output`, `-v`, and a **single positional `file`** (no `-d`, no glob).

`normalize` [captured: topaz.normalize.help.txt] has the **same flag set as `preprocess`**
(2-component GMM): `-s/--scale 1`, `--affine`, `--sample 10`, `--niters 100`, `-a 900`,
`-b 1`, `--metadata`, `-d/--device` default **-1 (CPU)**, `-t/--num-workers`, `-j/--num-threads`,
`-o/--destdir`, `--format` (mrc/tiff/png, default mrc), `-v`.

### `convert` [captured: topaz.convert.help.txt]
Converts coordinate files between formats; can threshold by score and up/down-scale coords.
Replaces the deprecated per-format converters.
- positional `files` (multiple inputs are **concatenated** into one output).
- `-o/--output` default **stdout**. For `--to json` or `--to box` the OUTPUT must be a
  **directory** (with optional `--suffix`).
- `--from {auto,coord,csv,star,box}` (input format; default auto by extension).
- `--to {auto,coord,csv,star,json,box}` (output format; default auto by extension).
- `-t/--threshold` (filter particles by score), `-s/--down-scale 1`, `-x/--up-scale 1`.
- `--image-ext` default **.mrc** — **required** when converting **to star or box** (and to
  find images when `--invert-y` is set).
- `--boxsize` — **required** when converting **to box**.
- Metadata flags: `--voltage`, `--detector-pixel-size`, `--magnification`,
  `--amplitude-contrast`.
- `--invert-y` (mirror y-axis; requires `--imagedir`); `-v/--verbose 0`.
- Smoke-proven [smoke]: `topaz convert --to star -o coords.star coords.txt` works.

### `split` [captured: topaz.split.help.txt]
Split a multi-micrograph coordinate file into one file per micrograph.
- positional single `file`; `-o/--output` is a **directory**.
- `--format {auto,coord,star}` (input format; outputs written in the same format — **no
  csv/box here**); `--suffix`; `-t/--threshold`.

### `particle_stack` [captured: topaz.particle_stack.help.txt]
Extract an MRC particle stack from a coordinates table.
- positional single `file` (the **coordinates** file).
- `--image-root` (root dir of micrographs), `-o/--output` (stack file), `--size` (box size),
  `--threshold` default **-inf**, `--resize` (downsample particles, default off),
  `--image-ext` default **.mrc**, `--metadata` (.star with per-micrograph CTF).

### `train_test_split` [captured: topaz.train_test_split.help.txt]
Split labeled micrographs into train/test sets.
- positional single `file`; `--image-dir`, `--image-ext` (auto-detect),
  `--format {auto,coord,csv,star,box}`.
- `-n/--number` = **number of images put into the TEST set** (there is **no `--test-split
  FRAC` flag**); `--seed 0`.

### `precision_recall_curve` [captured: topaz.precision_recall_curve.help.txt]
- `--predicted` (predicted coords + scores), `--targets` (target coords),
  `-r/--assignment-radius` **required**, `--images {target,predicted,union}` default **target**.

### `scale_coordinates` (Deprecated) [captured: topaz.scale_coordinates.help.txt]
- positional `file`; `-s/--scale` default **0.25**, `-o/--output`. Prefer `convert -s/-x`.

## Concrete-command rule
On a host the probe reports as `valid`/`ready`, emit **real commands with the user's actual
paths** (no placeholders). Cite the captured help filename for each non-obvious flag/default,
and **run only after explicit user confirmation**. Example (substitute the user's paths):
```
topaz preprocess -s 4 -d 0 -o proc/ raw/*.mrc          # captured: topaz.preprocess.help.txt
topaz train -m resnet8 --train-images train_mics/ --train-targets train_coords.txt \
            -n 100 -r 8 --num-epochs 10 -d 0 \
            --save-prefix model/run1 -o train_curve.txt # captured: topaz.train.help.txt
topaz extract -m model/run1_epoch10.sav -r 8 -t -6 \
              -o particles.txt -d 0 proc/*.mrc          # captured: topaz.extract.help.txt
topaz denoise -d -1 -o denoised/ raw/*.mrc              # -d -1 on CPU / Apple Silicon
```
Notes that prevent silent mistakes:
- `extract` default `-t/--threshold` is **-6** (log-likelihood), not 0.5 — be explicit if the
  user expects a probability/quantile.
- `train --save-prefix DIR/...` requires `DIR` to already exist (`mkdir -p model/` first) [smoke].
- Pin a **cu12x** PyTorch build (e.g. `torch==2.9.1+cu128`) — the default PyPI torch is now
  CUDA-13 (cu130) and reports `cuda=False` on a CUDA-12 driver [smoke]
  (see 09_troubleshooting).
