# 04 — Data model & formats (VALIDATED against topaz 0.3.20)

> Format/flag facts here are labeled: `[validated topaz 0.3.20 — captured: topaz.<cmd>.help.txt]`
> for facts confirmed by captured live help, `[sourced 0.3.20 @ 58fe5237: <path>]` for source-only
> facts, and `[smoke]` for output-layout/behavior facts proven by GPU smoke runs
> (captured 2026-06-06 on a Linux + NVIDIA GPU host).

## Coordinate table (Topaz native)
- Tab-delimited; columns `image_name`, `x_coord`, `y_coord` (+ `z_coord` 3D); predictions add `score`.
  The prediction layout `image_name  x_coord  y_coord  score` is **VALIDATED** — `extract`
  produced exactly these columns on GPU [smoke].
- **Origin: top-left** of the image (README). `image_name` = basename **without extension**
  [sourced 0.3.20 @ 58fe5237: topaz/training.py, README "File formats"].

## Image file list (training input)
- Tab-delimited header `image_name  path`; maps names → paths
  [sourced 0.3.20 @ 58fe5237: topaz/training.py, topaz/utils/files.py, README "File formats"].

## Supported formats
- **MRC** micrographs & tomograms (`topaz/mrc.py`) [sourced 0.3.20 @ 58fe5237: topaz/mrc.py].
- Coordinate interchange via `topaz convert` (format auto-detected by extension, or forced
  with `--from`/`--to`) [validated topaz 0.3.20 — captured: topaz.convert.help.txt]:
  - INPUT (`--from {auto,coord,csv,star,box}`): Topaz/coord table (`.txt`/`.tab`),
    `csv`, RELION `.star`, EMAN `.box`. **Note: there is no `json` INPUT format.**
  - OUTPUT (`--to {auto,coord,csv,star,json,box}`): same set **plus** `json`. EMAN2
    `.json` is therefore **OUTPUT-only** — you can write JSON via `--to json` but cannot
    read it back via `--from`. For `--to json` or `--to box` the `-o/--output` must be a
    **directory**, not a single file.
  - `convert` can also up/down-scale coordinates (`-x`/`-s`) and filter by score (`-t`).
- Models: `.sav` (pickled torch modules; `torch.save`) [sourced 0.3.20 @ 58fe5237].

## Pretrained models (BUNDLED in the package — no download)
- Detectors (picking): `resnet8`/`resnet16` × `u32`/`u64` → `topaz/pretrained/detector/*.sav`
  [sourced 0.3.20 @ 58fe5237: topaz/pretrained/detector]. `extract`/`segment` default to
  `resnet16` [validated topaz 0.3.20 — captured: topaz.extract.help.txt, topaz.segment.help.txt].
- 2D denoise (`denoise -m`): `unet`(L2, default), `unet-small`, `fcnn`, `affine`, and the older
  `unet-v0.2.1` [validated topaz 0.3.20 — captured: topaz.denoise.help.txt]. With `-m` omitted,
  `denoise` auto-loads the bundled default; GPU smoke loaded `unet_L2_v0.2.2.sav` [smoke].
  (Note: `-m` model NAMES are `unet/unet-small/fcnn/affine`; the `--arch` *training* choices are
  the distinct set `unet/unet-small/unet2/unet3/fcnet/fcnet2/affine`.)
- 3D denoise (`denoise3d -m`): `unet-3d` (default), `unet-3d-10a`, `unet-3d-20a`
  [validated topaz 0.3.20 — captured: topaz.denoise3d.help.txt].
- Loaded via `load_state_dict_from_pkg(..., map_location='cpu')` → CPU-safe, then `.cuda()` if used
  [sourced 0.3.20 @ 58fe5237: topaz/model/utils.py].

## Coordinate scaling caveat
If micrographs were downsampled (`preprocess`/`downsample -s N`) before picking, the
predicted coordinates are in **downsampled** pixels. Scale back to original pixels with
`topaz convert` before exporting to STAR/RELION/CryoSPARC: **`-x/--up-scale <factor>`**
UP-scales, **`-s/--down-scale <factor>`** DOWN-scales (two distinct flags, both default `1`)
[sourced 0.3.20 @ 58fe5237: convert.py:37-38; validated topaz 0.3.20 — captured: topaz.convert.help.txt].
The same `-s`/`-x` pair also exists on `extract` (apply the scale at pick time instead of via
`convert`) [validated topaz 0.3.20 — captured: topaz.extract.help.txt].
Converting **to** star/box also needs `--image-ext` (default `.mrc`) and, for box, `--boxsize`
[validated topaz 0.3.20 — captured: topaz.convert.help.txt].
Getting the scale factor wrong silently misplaces particles — always state the assumed scale.

## Outputs per command
| Command | Output | Evidence |
|---|---|---|
| `preprocess`/`downsample`/`normalize` | processed images in `--destdir`/`-o` | [validated topaz 0.3.20 — captured: topaz.preprocess.help.txt, topaz.downsample.help.txt, topaz.normalize.help.txt] |
| `train` | checkpoint per epoch `<save-prefix>_epoch{N}.sav` (e.g. `model/topaz_smoke_epoch1.sav`) + train/test curve via `-o` | [smoke] (VALIDATED) |
| `segment` | per-image log-likelihood-ratio maps in `--destdir` | [validated topaz 0.3.20 — captured: topaz.segment.help.txt] |
| `extract` | coordinate table, columns **`image_name  x_coord  y_coord  score`** | [smoke] (VALIDATED) |
| `denoise`/`denoise3d` | denoised MRC in `--output` dir | [validated topaz 0.3.20 — captured: topaz.denoise.help.txt, topaz.denoise3d.help.txt] |

> The `extract` column order and the `train` per-epoch checkpoint naming above are
> **VALIDATED** by GPU smoke runs — `extract` produced `image_name x_coord y_coord score`
> and `train --save-prefix model/topaz_smoke` produced `model/topaz_smoke_epoch1.sav`
> [smoke]. **Gotcha:** `train --save-prefix DIR/...`
> requires `DIR` to already exist — topaz does NOT create the parent directory [smoke];
> see `references/09_troubleshooting.md`.

## Interop
- RELION: `docs/source/relion.md`, `relion_run_topaz/` scripts.
- CryoSPARC: `docs/source/cryosparc.md`.

> Column order (`extract`) and per-epoch checkpoint naming (`train`) are **VALIDATED** by
> GPU smoke runs against topaz 0.3.20 [smoke]; no fixture
> re-validation is required before relying on them. Project-level detail:
> `references/data_model/formats_from_source.md`.
