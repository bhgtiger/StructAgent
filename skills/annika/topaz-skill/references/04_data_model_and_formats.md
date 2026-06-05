# 04 — Data model & formats (sourced v0.3.20)

## Coordinate table (Topaz native)
- Tab-delimited; columns `image_name`, `x_coord`, `y_coord` (+ `z_coord` 3D); predictions add `score`.
- **Origin: top-left** of the image (README). `image_name` = basename **without extension**.
- Source: `topaz/training.py` (`x_coord`/`y_coord`/offset handling), README "File formats".

## Image file list (training input)
- Tab-delimited header `image_name  path`; maps names → paths.

## Supported formats
- **MRC** micrographs & tomograms (`topaz/mrc.py`).
- Coordinate interchange via `topaz convert` (auto by extension):
  - Topaz table (`.txt`/`.tab`)
  - RELION `.star`
  - EMAN `.box`
  - EMAN2 `.json`
  - `convert` can also up/down-scale coordinates and filter by score.
- Models: `.sav` (pickled torch modules; `torch.save`).

## Pretrained models (BUNDLED in the package — no download)
- Detectors (picking): `resnet8`/`resnet16` × `u32`/`u64` → `topaz/pretrained/detector/*.sav`.
  `extract`/`segment` default to `resnet16` (= `resnet16_u64.sav`).
- 2D denoise: `unet`(L2), `unet-small`, `fcnn`, `affine`, `unet-v0.2.1` → `topaz/pretrained/denoise/`.
- 3D denoise: `unet-3d`, `unet-3d-10a`, `unet-3d-20a`.
- Loaded via `load_state_dict_from_pkg(..., map_location='cpu')` → CPU-safe, then `.cuda()` if used.

## Coordinate scaling caveat
If micrographs were downsampled (`preprocess`/`downsample -s N`) before picking, the
predicted coordinates are in **downsampled** pixels. Scale back to original pixels with
`topaz convert` before exporting to STAR/RELION/CryoSPARC: **`-x/--up-scale <factor>`**
UP-scales, **`-s/--down-scale <factor>`** DOWN-scales (distinct flags; `convert.py:37-38`).
Converting **to** star/box also needs `--image-ext` (default `.mrc`) and, for box, `--boxsize`.
Getting the scale factor wrong silently misplaces particles — always state the assumed scale.

## Outputs per command (sourced)
| Command | Output |
|---|---|
| `preprocess`/`downsample`/`normalize` | processed images in `--destdir` |
| `train` | `<prefix>_epoch{N}.sav` + metrics (stdout/stderr) |
| `segment` | per-image log-likelihood-ratio maps in `--destdir` |
| `extract` | coordinate table `image_name x_coord y_coord score` |
| `denoise`/`denoise3d` | denoised MRC in `--destdir` |

## Interop
- RELION: `docs/source/relion.md`, `relion_run_topaz/` scripts.
- CryoSPARC: `docs/source/cryosparc.md`.

> Validate exact column order / output filenames against tiny fixtures + live behavior
> before relying on them. Project-level detail: `references/data_model/formats_from_source.md`.
