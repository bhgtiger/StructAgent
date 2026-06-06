# 05 — Core workflows

The commands here are **VALIDATED against cryoDRGN 4.2.1** (captured live `--help`
on a Linux + NVIDIA GPU host, 2026-06-06; GPU smoke log in the validation run).
On a host whose probe reports `config_state: ready` (cryoDRGN installed, Linux +
NVIDIA), the skill **may emit concrete commands with the user's real paths and run
real jobs after explicit user confirmation** (`SKILL.md` §4). The `<...>` placeholders
below are just slots for the user's real paths; replace them and confirm before
launching anything that touches real data or compute. Each block carries a
`[config-state: <ready|partial|blocked|absent|stale|unknown>]` tag (filled from
`configs/site_config.local.md`) and a `[VALIDATED: cryoDRGN 4.2.1]` tag citing the
captured help file where the flags were confirmed. Commands that read/write real
data or use the GPU are also tagged `[run-with-confirmation]`.

## A. Heterogeneous reconstruction with consensus poses (cryoDRGN "1")

Use when you already have a homogeneous/consensus refinement (e.g. a C1 RELION or
cryoSPARC refinement) and want to explore heterogeneity around those poses.

```text
Pipeline:  particles + consensus poses/CTF
   1. downsample            → particles.128.mrcs (pilot), later particles.256.mrcs
   2. parse poses + CTF     → pose.pkl, ctf.pkl       (-D = ORIGINAL box size!)
   3. (optional) backproject sanity check
   4. train_vae  (pilot D=128, small zdim, ~25 epochs)
   5. analyze    (epoch N, 1-based)   [auto-runs at end of train_vae]
   6. filter junk particles (interactive) → indices.pkl
   7. high-res train_vae on D=256 with --ind indices.pkl
   8. analyze / eval_vol / trajectories
```

### 1. Downsample

```text
# [config-state: <current>] [VALIDATED: cryoDRGN 4.2.1 — cryodrgn.downsample.help.txt] [run-with-confirmation]
cryodrgn downsample <particles.mrcs> -D 128 -o <outdir>/particles.128.mrcs
# larger datasets: add --chunk 10000 ; .star/.cs inputs with broken paths: add --datadir <dir>
cryodrgn downsample <particles.mrcs> -D 256 -o <outdir>/particles.256.mrcs
```

Output flag is `-o OUTFILE` (alias `--outfile`); `-D` is the new (even) box size.
With `--chunk N` the output is split into `particles.256.0.mrcs`,
`particles.256.1.mrcs`, … plus a `particles.256.txt` index that references them all
(per the `cryodrgn.downsample.help.txt` example). Other useful flags:
`-b/--batch-size` (default 5000), `--max-threads` (default 16), `--ind PKL`,
`--is-vol`, `--outdir`, `--datadir`.

### 2. Parse poses and CTF (-D is the ORIGINAL/consensus box size)

```text
# [config-state: <current>] [VALIDATED: cryoDRGN 4.2.1 — cryodrgn.parse_pose_star.help.txt, cryodrgn.parse_ctf_star.help.txt, cryodrgn.parse_pose_csparc.help.txt, cryodrgn.parse_ctf_csparc.help.txt] [run-with-confirmation]
# RELION .star:
cryodrgn parse_pose_star <particles.star> --outpkl <outdir>/pose.pkl
cryodrgn parse_ctf_star  <particles.star> -o <outdir>/ctf.pkl
# cryoSPARC .cs (note the -D box size of the consensus refinement):
cryodrgn parse_pose_csparc <particles.cs> -D <orig_box> -o <outdir>/pose.pkl
cryodrgn parse_ctf_csparc  <particles.cs> -o <outdir>/ctf.pkl
```

Validated flag details (each from the captured help):

- `parse_pose_star`: positional `input` (.star); output is `--outpkl PKL` with
  `-o` as an alias. `-D` and `--Apix` are **optional overrides** for missing box
  size / pixel size only (use `--Apix` when translations are in Angstroms) —
  cryoDRGN reads them from the .star header otherwise.
- `parse_ctf_star`: positional `star`; output `-o O`. Optional overrides
  `-D --Apix --kv --cs -w --ps`, plus `--png` to plot the CTF.
- `parse_pose_csparc`: positional `input` (.cs); `-D` is **required** (box size of
  the consensus reconstruction) and output is `-o PKL`. Add `--abinit` if the .cs
  is from ab-initio, `--hetrefine` if from a heterogeneous refinement (default is
  homogeneous). There is no `--Apix` for this command.
- `parse_ctf_csparc`: positional `cs`; output `-o O`. `-D` and `--Apix` are
  optional overrides (no longer required), plus `--png`.

### 3. Optional backprojection sanity check

```text
# [config-state: <current>] [VALIDATED: cryoDRGN 4.2.1 — cryodrgn.backproject_voxel.help.txt] [run-with-confirmation]
# Quick check that poses/CTF parsed sensibly before training (first 10k images).
cryodrgn backproject_voxel <particles.128.mrcs> --poses <poses.pkl> --ctf <ctf.pkl> --outdir <outdir>/bp --first 10000
```

The output directory flag is `--outdir OUTDIR` (alias `-o`); `--poses` is required,
`--ctf` optional (phase-flips images). By default the command writes both half-maps
and an FSC, so `<outdir>/bp/` contains `backproject.mrc`, `half_map_a.mrc`,
`half_map_b.mrc`, `fsc-plot.png`, and `fsc-vals.txt` (validated end-to-end in the
smoke log). `--first N` reconstructs a quick subset; suppress half-maps/FSC with
`--no-half-maps` / `--no-fsc-vals`; `--lazy` reduces memory; `--ind PKL` filters;
`--datadir` is generally needed for `.star`/`.cs` inputs.

Note on sign: `--uninvert-data` means **do NOT invert the data sign** — it *disables*
cryoDRGN's default sign inversion. cryoDRGN inverts by default (EM particles are
dark-on-light). If a reconstruction comes out inverted relative to your already-
correct-convention data, toggling this flag changes whether inversion is applied;
do not add it as a blanket "fix inverted maps" step.

### 4. Pilot training (D=128, small zdim)

```text
# [config-state: <current>] [VALIDATED: cryoDRGN 4.2.1 — cryodrgn.train_vae.help.txt] [run-with-confirmation]
cryodrgn train_vae <particles.128.mrcs> --poses <poses.pkl> --ctf <ctf.pkl> --zdim 8 -n 25 -o <outdir>/00_cryodrgn128
```

Validated defaults (from `cryodrgn.train_vae.help.txt` and the smoke `run.log`):
`--zdim` is **required** (latent dimension); `-b/--batch-size` default **16**
(CONFIRMED — the README differs but the live help and run.log agree on 16);
`-n/--num-epochs` default **20**; `--lr` default **0.0001**; encoder/decoder
default to dim **1024** and **3** layers (`--enc-dim/--dec-dim 1024`,
`--enc-layers/--dec-layers 3`); `--encode-mode resid`; `--pe-type gaussian`.
Mixed-precision (AMP) is **on by default** — pass `--no-amp` to disable it.
Use `--uninvert-data` only for data that should *not* be sign-inverted. For very
large datasets, pilot on a subset via `--ind`. (Note: the deprecated
`abinit_het_old`/`abinit_homo_old` default to enc/dec dim 256, not 1024 — do not
generalize the 1024 default to them.)

Workdir contents after training (validated): `config.yaml`, `run.log`,
`weights.pkl`, `weights.N.pkl`, `z.pkl`, `z.N.pkl`, and `analyze.N/` (analysis
auto-runs on the final epoch unless `--no-analysis`).

### 5. Analyze (1-based epoch)

```text
# [config-state: <current>] [VALIDATED: cryoDRGN 4.2.1 — cryodrgn.analyze.help.txt] [run-with-confirmation]
cryodrgn analyze <outdir>/00_cryodrgn128 25
# runs PCA + UMAP, generates k-means volumes (default --ksample 20), PC traversals
# (default --pc 2), and a template Jupyter notebook.
```

Positionals are `workdir epoch` (epoch is 1-based, matching `z.N.pkl` /
`weights.N.pkl`). Defaults: `--ksample 20` (k-means samples), `--pc 2` (PC
traversals), `--n-per-pc 10`, `--vol-start-index 1`. Output goes to
`[workdir]/analyze.[epoch]` by default (override with `-o/--outdir`). Volume
post-processing options include `--Apix`, `--low-pass`, `--crop`, `-d/--downsample`,
`--flip`, `--invert`, and `--device`. Note that `train_vae` already auto-runs
`analyze` on its final epoch (unless `--no-analysis`), so a separate `analyze` call
is mainly needed for non-final epochs or different sampling parameters.

### 6. Filter junk particles (interactive)

`cryodrgn filter <workdir>` opens an interactive 2-D scatter selection UI and
**requires `cryodrgn analyze` to have been run first** for the chosen epoch. On a
`ready` host it may be launched after explicit user confirmation. It writes the
selection to `indices.pkl`. Flags (from `cryodrgn.filter.help.txt`): `--force/-f`
(save without prompting), `--sel-dir SEL_DIR` (directory to save into),
`--epoch/-e EPOCH` (defaults to the last available epoch), `--kmeans/-k KMEANS`
(which k-means clustering to use), `--plot-inds PLOT_INDS` (pre-plot existing
indices).

```text
# [config-state: <current>] [VALIDATED: cryoDRGN 4.2.1 — cryodrgn.filter.help.txt] [run-with-confirmation]
cryodrgn filter <outdir>/00_cryodrgn128 --epoch 25 -f
```

The web dashboard is the browser-based counterpart: `cryodrgn dashboard
[<workdir>]` launches a local server (default host `127.0.0.1`, default `--port`
5050) with a particle explorer, pairwise/3-D latent panels, and a command builder.
Use `--no-browser` to skip auto-opening a tab and `-p/--port` to change the port
(from `cryodrgn.dashboard.help.txt`). Same precondition and confirmation policy as
`filter`.

### 7. High-resolution training on kept particles

```text
# [config-state: <current>] [VALIDATED: cryoDRGN 4.2.1 — cryodrgn.train_vae.help.txt] [run-with-confirmation]
cryodrgn train_vae <particles.256.mrcs> --poses <poses.pkl> --ctf <ctf.pkl> --zdim 8 -n 25 -o <outdir>/01_cryodrgn256 --ind <indices.pkl>
# multi-GPU for large boxes (D=256); select GPUs via CUDA_VISIBLE_DEVICES:
#   CUDA_VISIBLE_DEVICES=0,3 cryodrgn train_vae ... --multigpu
```

`--ind indices.pkl` filters the stack to the kept particles (validated). `--multigpu`
"Parallelize[s] training across all detected GPUs" (validated wording); restrict
which GPUs are visible with `CUDA_VISIBLE_DEVICES`.

### Continue / extend training

```text
# [config-state: <current>] [VALIDATED: cryoDRGN 4.2.1 — cryodrgn.train_vae.help.txt] [run-with-confirmation]
# Resume from a checkpoint to train longer (weights.N.pkl is 1-based).
cryodrgn train_vae <particles.256.mrcs> --poses <poses.pkl> --ctf <ctf.pkl> --zdim 8 -n 50 -o <outdir>/01_cryodrgn256 --load <outdir>/01_cryodrgn256/weights.25.pkl
# `--load latest` is also accepted to resume from the most recent checkpoint:
cryodrgn train_vae <particles.256.mrcs> --poses <poses.pkl> --ctf <ctf.pkl> --zdim 8 -n 50 -o <outdir>/01_cryodrgn256 --load latest
```

`--load` accepts either an explicit `weights.N.pkl` path or the literal value
`latest` (per the `cryodrgn.train_vae.help.txt` restart example).

### 8. Volumes and trajectories

```text
# [config-state: <current>] [VALIDATED: cryoDRGN 4.2.1 — cryodrgn.eval_vol.help.txt, cryodrgn.pc_traversal.help.txt, cryodrgn.graph_traversal.help.txt, cryodrgn.direct_traversal.help.txt] [run-with-confirmation]
# Single volume at a chosen z (length of -z must equal zdim):
cryodrgn eval_vol <workdir>/weights.pkl -c <workdir>/config.yaml -z <z...> -o <outdir>/vol.mrc
# Trajectory between two z endpoints:
cryodrgn eval_vol <workdir>/weights.pkl -c <workdir>/config.yaml --z-start <z0...> --z-end <z1...> -n 20 -o <outdir>/trajectory
# Trajectory z-value generators write a .txt of z-values you can feed back via --zfile:
cryodrgn pc_traversal <workdir>/z.pkl --pc 1 -o <outdir>/pc.txt
cryodrgn graph_traversal <workdir>/z.pkl --anchors <i> <j> --outtxt <outdir>/z-path.txt --outind <outdir>/z-path.ind.txt
cryodrgn direct_traversal <workdir>/z.pkl --anchors <i> <j> -n 20 --outtxt <outdir>/z-path.txt
# Then render volumes along the generated path:
cryodrgn eval_vol <workdir>/weights.pkl -c <workdir>/config.yaml --zfile <outdir>/z-path.txt -o <outdir>/traj
```

Validated flag details:

- `eval_vol`: positional `weights`; config flag is `-c YAML` (alias `--config`) —
  point it at the training `config.yaml`; output `-o`; `-z` for a single z (length
  must equal zdim); `--z-start/--z-end` + `-n` for a linear path; `--zfile` to read
  z-values from a `.txt`; `--vol-start-index` default 1.
- `pc_traversal`: positional is the **zfile** (`z.pkl`); `--pc` is 1-based (default
  all PCs); `-n` samples (default 10); output `-o/--outdir` writes `pc<i>.txt`
  files.
- `graph_traversal`: positional zfile; `--anchors` takes anchor indices as integers
  or `.txt` file(s); `--outtxt/-o` writes the path z-values (default `z-path.txt`)
  and `--outind` writes the path indices.
- `direct_traversal`: positional zfile; `--anchors` (ints or `.txt`), `-n` points
  between anchors (default 6), `--outtxt/-o` for output, `--loop` to close the path.

(These replace the older skill text that showed `graph_traversal ... -o graph.txt`
and a `--zfile` chaining shorthand; use the real `--outtxt`/`--outind`/`--zfile`
flags above.)

## B. Ab initio reconstruction (cryoDRGN-AI) — no consensus poses

Use when you do **not** have reliable consensus poses. `abinit` runs pose search;
`--poses` is not required. Arguments otherwise resemble `train_vae`.

```text
# [config-state: <current>] [VALIDATED: cryoDRGN 4.2.1 — cryodrgn.abinit.help.txt] [run-with-confirmation]
# Heterogeneous ab initio; first few epochs do pose search, then continue.
cryodrgn abinit <particles.mrcs> --ctf <ctf.pkl> --zdim 8 -n 50 -o <outdir>/001_abinit
```

`abinit` requires `--zdim` and `-o`; `--ctf` is optional, `-n/--num-epochs` defaults
to 30. Deprecated cryoDRGN2 paths remain as `abinit_het_old` / `abinit_homo_old`.
For global pose optimization, prefer `abinit` (cryoDRGN-AI). Choosing between A and B
is in `10_decision_trees.md`.

## C. Subtomogram (cryoDRGN-ET) — validated tilt flags

For cryo-ET / heterogeneous subtomogram averaging, cryoDRGN-ET tilt handling is real
and validated against 4.2.1. In `train_vae` the tilt path uses
`--encode-mode tilt` together with `--ntilts` (number of tilts to encode, default
10), `--random-tilts` (randomize tilt order to the encoder), `-d/--dose-per-tilt`
(electrons/Å² per tilt) and `-a/--angle-per-tilt` (degrees, default 3). The captured
example is:

```text
# [config-state: <current>] [VALIDATED: cryoDRGN 4.2.1 — cryodrgn.train_vae.help.txt] [run-with-confirmation]
cryodrgn train_vae <particles_from_M.star> --datadir <particleseries> -o <outdir>/et \
    --ctf <ctf.pkl> --poses <pose.pkl> \
    --encode-mode tilt --dose-per-tilt 2.93 --zdim 12 --num-epochs 50 --beta .025
```

`backproject_voxel` has its own tilt group (`cryodrgn.backproject_voxel.help.txt`):
`--tilt` (treat data as a tilt series), `--ntilts` (default 10), `--force-ntilts`
(keep only particles with ≥ `--ntilts` tilts), `-d/--dose-per-tilt`,
`-a/--angle-per-tilt` (default 3). See `10_decision_trees.md` and the user guide's
cryoDRGN-ET section for when to use these.

Caveat: the `--tilt-deg` flag belongs to the deprecated `abinit_het_old`/
`abinit_homo_old` (their "Tilt series" group, default 45), **not** to `train_vae` —
do not pass `--tilt-deg` to `train_vae`.

## Performance expectation (cite with version context, do not over-generalize)

README reports, for a 100k-particle dataset on **1 V100 GPU**: ~12 min/epoch at
D=128 and ~47 min/epoch at D=256 (`[src: README.md @ 4.2.1, lines 324–325]`). Do not
extrapolate to other GPUs/dataset sizes without that context. As an existence proof
only (not a benchmark), the validation smoke ran `train_vae`/`backproject_voxel`/
`analyze` end-to-end on a Linux + NVIDIA GPU host with an NVIDIA GPU on a tiny 5-particle D=256
set (`[src: the validation run]`); that confirms the pipeline
executes but says nothing about epoch timing at scale.
