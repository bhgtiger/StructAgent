# Fixtures

**Status: a tiny, CPU-runnable smoke fixture is expected here.** Topaz 0.3.20 is installed
and validated end-to-end (see the validated GPU smoke chain),
so execution is supported now. A small synthetic fixture lets the skill prove the
`preprocess → convert → denoise → train → extract` chain runs on any machine without
touching the user's real (often private) data.

## What the smoke fixture is — tiny, synthetic, public
Mirror the validated smoke run: a handful of small synthetic micrographs plus a short
coordinate table. None of this is real cryo-EM data, so it is safe to ship.

- **Micrographs:** ~4 synthetic single-channel MRCs (the validated run used three for
  training + one for testing, 512×512, Gaussian-blob "particles" on noise). [smoke]
- **Coordinate table:** a tab-separated text file with header `image_name<TAB>x_coord<TAB>y_coord`,
  e.g. a 2–3 line minimum:

  ```
  image_name	x_coord	y_coord
  mic_0001	235	330
  mic_0001	80	75
  ```

  This is the `coord` format Topaz reads for `--train-targets` and that `convert` turns into
  other formats. [validated topaz 0.3.20 — captured: topaz.convert.help.txt]
- These can be generated on the fly (numpy + mrcfile) rather than vendored as binaries
  (the validated run synthesized them this way). [smoke]

## How it runs — CPU for portability, GPU optional
The fixture is meant to run on **CPU for portability** so the smoke test works anywhere:

- CPU: pass `-d -1` on `train`/`extract`/`segment`/`denoise`. (For `preprocess`/`normalize`
  the default device is already `-1` = CPU.) [validated topaz 0.3.20 — captured:
  topaz.train.help.txt, topaz.extract.help.txt, topaz.preprocess.help.txt, topaz.normalize.help.txt]
- GPU: optional. If the env probe reports an NVIDIA GPU with a usable CUDA torch, pass
  `-d 0` (the `train`/`extract`/`denoise` default is `0`). The validated chain ran on GPU
  with `-d 0`. [smoke]
- If the probe reports Apple Silicon / no NVIDIA GPU, Topaz runs CPU-only (no MPS path in
  Topaz at 58fe5237 → `topaz_mps_supported = False`); use `-d -1`. [sourced 0.3.20 @ 58fe5237]

### Validated smoke chain (the oracle to reproduce)
From the validated GPU smoke run [smoke]:

1. `topaz preprocess -s 4 -d 0 -o proc/ <mic>` — downsample ×4 + normalize.
2. `topaz convert --to star -o coords.star coords.txt` — coord → STAR.
3. `topaz denoise -d 0 -o denoised/ <mic>` — auto-loads the bundled pretrained `unet`
   model when `-m` is omitted.
4. `mkdir -p model && topaz train -d 0 --train-images train_mics/ --train-targets train_coords.txt
   --test-images test_mics/ --test-targets test_coords.txt -n 30 -r 8 --num-epochs 1
   --method PN --save-prefix model/topaz_smoke -o train.log.txt`
   → checkpoint `model/topaz_smoke_epoch1.sav` (naming `<save-prefix>_epoch{N}.sav`).
5. `topaz extract -m model/topaz_smoke_epoch1.sav -r 8 -d 0 -o extracted.txt <mic>`
   → output columns `image_name  x_coord  y_coord  score`.

To run this fixture on a CPU-only machine, swap every `-d 0` for `-d -1`.

### Fixture setup note — `--save-prefix` parent dir gotcha
`topaz train --save-prefix DIR/...` does **not** create the parent directory; create it first
(e.g. `mkdir -p model/`) or training fails to write the checkpoint. See `references/09_troubleshooting.md`.
[smoke]

## Hard rules
- **No private/unpublished micrographs.** Use tiny, public/synthetic data only. No data is
  moved out of the user's project.
- Keep each fixture < a few MB; record provenance (synthesis script or repo path + commit)
  and the expected output for each fixture.
- Cite the source for any non-synthetic input.
