# Lessons (running log)

## 2026-06-06 — validated against installed Topaz 0.3.20 (execution-capable)
- **Topaz 0.3.20 is now INSTALLED and VALIDATED end-to-end on Linux + NVIDIA.** Live `--help`
  was captured for every subcommand (on a Linux + NVIDIA GPU host, driver
  535 / CUDA 12.2) as `topaz.<cmd>.help.txt` and `topaz --version` reports
  **0.3.20** (`_version.txt`). GPU smoke runs (preprocess, denoise, train, extract, convert)
  passed.
- **Posture upgraded from config-first/no-execute (v0) to validated, execution-capable.** On a
  machine the probe classifies `valid`/`ready`, the skill MAY emit concrete commands with the
  user's real paths AND run real jobs **after explicit user confirmation**. The old no-execute
  ban, the "this host is blocked", and the "every template is placeholder/NOT validated" framing
  are dropped. Safety that stays: no blind installs of system-level deps, private data stays
  local, confirm before running on real data.
- **Version bumped `0.0.1 → 1.0.0`** in SKILL.md (frontmatter `name: topaz-skill` unchanged;
  `metadata.topaz_pin` unchanged). CLI/flag/default/format claims are now labeled
  `[validated topaz 0.3.20 — captured: topaz.<cmd>.help.txt]`.

### Corrected CLI ground truth (from captured live help — supersedes earlier source-only guesses)
- **extract**: `-t/--threshold` default is **-6** (log-likelihood; "-6 ≈ p>=0.0025"), NOT 0.5 and
  not a score quantile. `-r/--radius` has **no default** (supply it, or auto-tune with `--targets`
  + `--min-radius 5`/`--max-radius 100`/`--step-radius 5`). `-m/--model` default **resnet16**
  (`-m none` if inputs are already segmented). `-s/--down-scale`, `-x/--up-scale` (default 1),
  `--dims {2,3}` (default 2; 3 for tomograms), `--per-micrograph`, `--suffix`,
  `--format {coord,csv,star,json,box}` (default coord); positional `paths` (can stream from stdin).
  Smoke: output columns are `image_name  x_coord  y_coord  score`. [validated topaz 0.3.20 — captured: topaz.extract.help.txt][smoke]
- **train**: `--method` default is **GE-binomial** (choices PN, GE-KL, GE-binomial, PU), NOT PN.
  `-r/--radius` default **3**, `--num-epochs` default **10**, `-m/--model` default **resnet8**,
  `--units` default 32, `-d/--device` default **0**. One of `-n/--num-particles` or `--pi` is
  required. Also `-k/--k-fold`, `--minibatch-size 256`, `--minibatch-balance 0.0625`,
  `--epoch-size 1000`, `--learning-rate 0.0002`, `-s/--patch-size 96`, `-p/--patch-padding 48`,
  `--save-prefix`, `-o/--output` (train/test curve). Smoke: checkpoints are named
  `<save-prefix>_epoch{N}.sav` (e.g. `model/topaz_smoke_epoch1.sav`). [validated topaz 0.3.20 — captured: topaz.train.help.txt][smoke]
- **preprocess / normalize**: `-s/--scale` (default **1**, NOT 4), `--affine`, `--sample`
  (default 10 — there is NO `--pixel-sampling` flag), `--niters` (default **100**, NOT 200),
  `-a/--alpha 900`, `-b/--beta 1`, `--metadata`, `-d/--device` default **-1** for BOTH commands,
  `-t/--num-workers` (NOTE: `-t` here is num-workers, **not** threshold), `-j/--num-threads`,
  `-o/--destdir`, `--format {mrc,tiff,png}` (default mrc). No `--seed`. [validated topaz 0.3.20 — captured: topaz.preprocess.help.txt, topaz.normalize.help.txt]
- **downsample**: ONLY `-s/--scale` (default **4**), `-o/--output`, `-v`; positional is a single
  `file` (not a glob); no device flag. [validated topaz 0.3.20 — captured: topaz.downsample.help.txt]
- **denoise** (2D): `-m/--model` accepts MULTIPLE, default **unet**; pretrained names are
  `unet, unet-small, fcnn, affine` (and older `unet-v0.2.1`) — note **fcnn**, not "fcnet" (fcnet
  is only an `--arch` training choice). `-o/--output` is a DIRECTORY, `-d/--device` default **0**.
  Training-mode flags: `-a/--dir-a`, `-b/--dir-b`, `--hdf`, `--method {noise2noise,masked}`,
  `--arch`, `--optim {adam,adagrad,sgd}` (default adagrad), `--lr 0.001`, `--criteria {L0,L1,L2}`
  (default L2), `-c/--crop 800`, `--num-epochs 100`, `-s/--patch-size 1024`, `-p/--patch-padding
  500`. Also `--lowpass`, `--gaussian`, `--inv-gaussian`, `--deconvolve`, `--stack`. Smoke:
  `-m` omitted auto-loaded bundled `unet_L2_v0.2.2.sav` on GPU. [validated topaz 0.3.20 — captured: topaz.denoise.help.txt][smoke]
- **denoise3d**: `-m/--model` default **unet-3d** (unet-3d, unet-3d-10a, unet-3d-20a, or a path);
  `-d/--device` default **-2 (multi-GPU)** (>=0 single GPU, -1 CPU); `-a/--even-train-path`,
  `-b/--odd-train-path`, `--N-train 1000`, `--N-test 200`, `-c/--crop 96`, `--base-kernel-width 11`,
  `--num-epochs 500`, `-g/--gaussian`, `-s/--patch-size 96`, `-p/--patch-padding 48`. [validated topaz 0.3.20 — captured: topaz.denoise3d.help.txt]
- **segment**: `-m/--model` default **resnet16** (2D), `-o/--destdir`, `-d/--device` (GPU if
  available), `-p/--patch-size` (default None = whole image), `-j`, `-v`; positional `paths`. [validated topaz 0.3.20 — captured: topaz.segment.help.txt]
- **convert**: `-o/--output` (default **stdout**), `--from {auto,coord,csv,star,box}`,
  `--to {auto,coord,csv,star,json,box}` (for JSON/BOX the OUTPUT must be a DIRECTORY).
  `-t/--threshold` filters by score, `-s/--down-scale` & `-x/--up-scale` (default 1).
  `--image-ext` default **.mrc**, REQUIRED for converting TO star and box; `--boxsize` REQUIRED
  for box. Metadata flags `--voltage`, `--detector-pixel-size`, `--magnification`,
  `--amplitude-contrast`; `--invert-y` (+ `--imagedir`); positional `files` (multiple
  concatenated). Smoke: `topaz convert --to star -o coords.star coords.txt` worked. [validated topaz 0.3.20 — captured: topaz.convert.help.txt][smoke]
- **split**: positional single `file`; `-o/--output` (a DIRECTORY); `--format {auto,coord,star}`
  (NOT csv/box); `--suffix`; `-t/--threshold`. [validated topaz 0.3.20 — captured: topaz.split.help.txt]
- **particle_stack**: positional single `file` (coordinates), NOT "<COORDS> <MICROGRAPHS>".
  `--image-root`, `-o/--output` (stack file), `--size` (box), `--threshold` (default -inf),
  `--resize`, `--image-ext` (default .mrc), `--metadata` (.star CTF). [validated topaz 0.3.20 — captured: topaz.particle_stack.help.txt]
- **train_test_split**: positional single `file`; `--image-dir`, `--image-ext` (auto),
  `--format {auto,coord,csv,star,box}`, `-n/--number` = number of images into the TEST set
  (there is NO `--test-split FRAC` flag), `--seed 0`. [validated topaz 0.3.20 — captured: topaz.train_test_split.help.txt]
- **precision_recall_curve**: `--predicted`, `--targets`, `-r/--assignment-radius` (REQUIRED),
  `--images {target,predicted,union}` (default target). [validated topaz 0.3.20 — captured: topaz.precision_recall_curve.help.txt]
- **scale_coordinates** (Deprecated): `-s/--scale` default 0.25, `-o/--output`, positional file. [validated topaz 0.3.20 — captured: topaz.scale_coordinates.help.txt]
- **Top-level groups** (exactly): Particle picking {train, segment, extract,
  precision_recall_curve}; Image processing {downsample, normalize, preprocess, denoise,
  denoise3d}; File utilities {convert, split, particle_stack, train_test_split}; GUI {gui};
  [Deprecated] {scale_coordinates, boxes_to_coordinates, star_to_coordinates,
  coordinates_to_star, coordinates_to_boxes, coordinates_to_eman2_json, star_particles_threshold}. [validated topaz 0.3.20 — captured: topaz.help.txt]

### Smoke gotchas to carry into 09_troubleshooting
- **`train --save-prefix DIR/...` requires DIR to already exist** — Topaz does NOT create the
  parent directory. `mkdir -p` it first. [smoke]
- **Default PyPI torch is now CUDA-13 (cu130) and reports `cuda=False` on a CUDA-12 driver.**
  Pin a cu12x build (e.g. `torch==2.9.1+cu128`) in the Topaz env. [smoke]

## 2026-06-05 — original v0 build, grounded on Topaz v0.3.20 @ 58fe5237 (source-only)
- **Device/MPS settled by source, not inference.** `topaz/cuda.py set_device()` consults only
  `torch.cuda`; zero `mps`/`backends.mps` references in `topaz/`. → `topaz_mps_supported=false`,
  confirmed `False` by the probe. **General per-platform fact (probe-driven):** if the
  probe reports Apple Silicon / no NVIDIA GPU, Topaz runs **CPU-only** — pass `-d -1`. This is not
  a "this machine is blocked" verdict; the probe computes support per host. [sourced 0.3.20 @ 58fe5237: topaz/cuda.py]
- **`--device` defaults differ per command** (train/extract/segment/denoise = 0, preprocess/
  normalize = -1, denoise3d = -2). On CPU-only machines recommend `-d -1` to avoid the
  `CudaWarning` fallback. [validated topaz 0.3.20 — captured: per-command help]
- **Pretrained models are bundled** in the wheel (`topaz/pretrained/…`, loaded
  `map_location='cpu'`) — no download for the standard detectors/denoisers; smoke confirmed
  denoise auto-loading `unet_L2_v0.2.2.sav`. [sourced 0.3.20 @ 58fe5237][smoke]
- **Python range 3.8–3.13** (`setup.py:45` `>=3.8,<=3.13`; README says 3.8–3.12 tested).
  *Historical, host-specific note:* the original dev machine ran Python 3.14.5, which is outside
  this range; that was a property of that one host, **not** a skill-wide constraint. Any install
  must go into a dedicated conda/venv at ≤3.13. [sourced 0.3.20 @ 58fe5237: setup.py:45]
- **PyPI name is `topaz-em`**, import is `topaz`, CLI is `topaz`, license **GPLv3**. Install:
  `conda install topaz -c tbepler -c pytorch` (CUDA: add `pytorch-cuda=11.8 … -c nvidia`), or
  `pip install topaz-em` — then pin a cu12x torch on CUDA-12 drivers (see gotcha above).

## Resolved decisions
- **Install vs detect:** the skill detects/reports via the read-only probe and may, after
  explicit user confirmation, run real jobs — it does **not** perform blind installs of
  system-level deps. (Closes the earlier "should the skill ever install Topaz?" question.)
- **First-slice scope:** resolved by the validated posture. On a `valid`/`ready` host the skill
  emits concrete commands with the user's real paths and can run real jobs after confirmation;
  no artificial fixture-only/no-execute slice. (Closes the earlier "v1 first slice" question.)
- **Installed skill folder name:** `topaz-skill` (frontmatter `name`) vs dev folder
  `topaz_skill`. Confirm with `openclaw skills check` before install.

## DONE — verified against the installed binary
- Live `topaz --version` (0.3.20) and `topaz <cmd> --help` were captured for every subcommand
  (`topaz.<cmd>.help.txt`). Earlier "reconcile with live / to verify" items are
  resolved; the corrected facts above reflect the captured help.
- `extract`/`train` output filenames and column order confirmed on the GPU smoke fixture:
  extract columns `image_name  x_coord  y_coord  score`; train checkpoints
  `<save-prefix>_epoch{N}.sav`. [smoke]
