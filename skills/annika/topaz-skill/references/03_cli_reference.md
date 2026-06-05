# 03 — CLI reference (sourced v0.3.20; reconcile with live help)

Invocation: `topaz <command> [options]`. Global `topaz --version`, `topaz --help`.
`@file.txt` expands to its lines (long arg lists).

> These are **[sourced v0.3.20]** from `topaz/main.py` + `topaz/commands/*.py`. When
> Topaz is installed, capture `topaz <cmd> --help` (**[live]**, trust-ladder #1) and
> reconcile. Until then, label command answers "NOT validated against a local binary".

## Commands by group
**Particle picking:** `train`, `segment`, `extract`, `precision_recall_curve`
**Image processing:** `downsample`, `normalize`, `preprocess`, `denoise`, `denoise3d`
**File utilities:** `convert`, `split`, `particle_stack`, `train_test_split`
**GUI:** `gui` (opens web GUI)
**[Deprecated]** (prefer `convert`): `scale_coordinates`, `boxes_to_coordinates`,
`star_to_coordinates`, `coordinates_to_star`, `coordinates_to_boxes`,
`coordinates_to_eman2_json`, `star_particles_threshold`

## `--device` semantics (CUDA-or-CPU only — see ref 02)
`>=0` → that CUDA GPU index; `<0` → CPU. No MPS. Defaults differ per command:
| Command | `--device` default |
|---|---|
| `train`, `segment`, `extract`, `denoise` | `0` (GPU 0; falls back to CPU with a warning) |
| `normalize` | `-1` (CPU) |
| `denoise3d` | `-2` (multi-GPU) |
On a CPU-only/Apple-Silicon machine, pass **`-d -1`** to avoid the CudaWarning.

## Key flags (sourced)
### `train`
`-m/--model resnet8` (arch) · `--pretrained`/`--no-pretrained` (default pretrained ON;
warm-starts from bundled model when arch∈{resnet8,resnet16} & units∈{32,64}) ·
`-n/--num-particles`, `--radius`, training-set + test-set list args · `-d/--device 0` ·
`--save-prefix`/`-o`. Output: `<prefix>_epoch{N}.sav` checkpoints + metrics.

### `segment`
`-m/--model resnet16` (bundled default) · `-o/--destdir` · `-d/--device 0` · `-v`.
Output: per-image log-likelihood-ratio maps.

### `extract`
`-m/--model resnet16` (omit/`none` if inputs already segmented) · `-r/--radius` ·
`-t/--threshold 0.5` (score quantile) · `--assignment-radius` · `--min/max/step-radius`
(5/100/5) · `--num-workers 0` · `--targets` · `--only-validate` · `-o/--output` · `-d/--device 0`.
Output: coordinate table `image_name x_coord y_coord score`.

### `denoise` (2D)
`-m/--model unet` (options `unet, unet-small, fcnn, affine, unet-v0.2.1`; multiple → averaged)
· `-o/--destdir` · `-d/--device 0` · patch/normalize options.

### `denoise3d`
`-m/--model unet-3d` (options `unet-3d, unet-3d-10a, unet-3d-20a`, or a model path)
· `-d/--device -2` · patch/Gaussian-filter options.

### `preprocess` / `downsample` / `normalize`
`preprocess`: `-s/--scale 4` · `--num-workers 0` · `--pixel-sampling 100` · `--niters 200`
· `--seed 1` · `-o/--destdir` (required) · `-v`. (`= downsample + normalize`.)
`normalize`: 2-component GMM; `-d/--device -1` (CPU default).

### `convert`
Auto-detects coordinate format by extension; can up/down-scale coords and threshold by
score. Replaces the deprecated per-format converters.

## Placeholder-template rule (v0)
Render commands with **placeholders**, never the user's real paths, e.g.:
```
topaz preprocess -s <SCALE> -o <PROC_DIR> <MICROGRAPHS_GLOB>
topaz train -m resnet8 --train-images <IMAGE_LIST> --train-targets <COORDS> -d <DEVICE> --save-prefix <MODEL_PREFIX>
topaz extract -m <MODEL.sav> -r <RADIUS> -t <THRESHOLD> -o <PARTICLES.txt> -d <DEVICE> <PROC_DIR>/*.mrc
topaz denoise -d -1 -o <DENOISED_DIR> <MICROGRAPHS_GLOB>     # -d -1 on CPU/Apple-Silicon
```
Annotate each placeholder and cite the flag's source. Concrete paths = v1; execution = v2+.
