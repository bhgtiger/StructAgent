# 03 — CLI reference (namespace + labeled templates)

cryoDRGN installs two console scripts (`pyproject.toml` `[project.scripts]`):

- `cryodrgn` → `cryodrgn.command_line:main_commands`
- `cryodrgn_utils` → `cryodrgn.command_line:util_commands`

`-h` lists subcommands; `cryodrgn <cmd> -h` / `cryodrgn_utils <cmd> -h` shows a
command's flags. **Flags below are VALIDATED against cryoDRGN 4.2.1 live `--help`**
(the captured `*.help.txt` files, captured 2026-06-06 on a Linux + NVIDIA GPU
host; `_version.txt` records `cryoDRGN 4.2.1 / torch 2.9.1+cu128 / cuda True`).
Each synopsis and template below cites the exact captured help file it was checked
against. Live captured help is the realized #1 source on the trust ladder
(`SKILL.md` §4) for this version.

> Labels recap (`SKILL.md` §4): every emitted template carries a config-state tag
> `[config-state: <ready|partial|blocked|absent|stale|unknown>]` (read from
> `configs/site_config.local.md`, which is generated per-machine by
> `scripts/cryodrgn_env_probe.py`), the validation tag `[VALIDATED: cryoDRGN 4.2.1]`
> naming the captured help file, and `[run-with-confirmation]` for any command that
> touches the user's real data or compute. On a `ready` host the skill MAY emit
> commands with the user's real paths and run them AFTER explicit user confirmation.
> `[not-run]` is reserved only for illustrative/destructive examples that should not
> be auto-run.

## `cryodrgn` subcommands (23, from `command_line.py` @ 4.2.1)

| Command | Purpose (VALIDATED against captured `--help`) |
|---|---|
| `abinit` | "Reconstructing volume(s) from picked cryoEM/ET particles using cryoDRGN-AI" — *ab initio*, heterogeneous (`--zdim` required) or homogeneous, **no input poses required** (`cryodrgn.abinit.help.txt`). |
| `abinit_het_old` | deprecated cryoDRGN2: "Train a heterogeneous NN reconstruction model with hierarchical pose optimization" (`cryodrgn.abinit_het_old.help.txt`). |
| `abinit_homo_old` | deprecated cryoDRGN2: "Homogeneous neural net ab initio reconstruction with hierarchical pose optimization" (`cryodrgn.abinit_homo_old.help.txt`). |
| `analyze` | visualize latent space + generate volumes; PCA/UMAP, PC trajectories, k-means volumes, template notebooks. |
| `analyze_landscape` | conformational-landscape analysis by comparing sampled volumes. |
| `analyze_landscape_full` | more comprehensive/automated landscape analysis. |
| `backproject_voxel` | voxel-based backprojection sanity check + half-maps + FSC. |
| `dashboard` | interactive web dashboard for results. |
| `direct_traversal` | straight-line latent trajectory between anchor z. |
| `downsample` | resize an image stack/volume by clipping Fourier frequencies. |
| `eval_images` | evaluate per-image latent encodings for a trained model. |
| `eval_vol` | evaluate the decoder at specified z to generate volume(s). |
| `filter` | **interactive** particle filtering UI over model variables. |
| `graph_traversal` | shortest-path latent trajectory through data-supported regions. |
| `parse_ctf_csparc` | extract CTF params from a cryoSPARC `.cs` → `ctf.pkl`. |
| `parse_ctf_star` | extract CTF params from a RELION `.star` → `ctf.pkl`. |
| `parse_pose_csparc` | extract poses from a cryoSPARC `.cs` → `pose.pkl`. |
| `parse_pose_star` | extract poses from a RELION `.star` → `pose.pkl`. |
| `parse_star` | unified `.star` parsing: writes BOTH CTF and poses pkls in one pass via `--ctf` / `--poses` (`cryodrgn.parse_star.help.txt`). |
| `pc_traversal` | latent trajectory along principal components. |
| `train_nn` | train a homogeneous NN reconstruction (fixed poses). |
| `train_vae` | **train a VAE for heterogeneous reconstruction with known poses** (the core command). |
| `train_dec` | train the decoder only. |

## `cryodrgn_utils` subcommands (25, from `command_line.py` @ 4.2.1)

```text
analyze_convergence  add_psize     clean         concat_pkls   filter_cs
filter_mrcs          filter_pkl    filter_star   flip_hand     fsc
gen_mask             invert_contrast  make_movies  parse_relion  phase_flip
plot_classes         plot_fsc      select_clusters  select_random  translate_mrcs
view_cs_header       view_header   view_mrcs     write_cs      write_star
```

Notable utils: `flip_hand` (handedness), `fsc`/`plot_fsc` (resolution),
`gen_mask` (masking), `parse_relion` / `write_star` (interop,
`06_interoperability.md`), `view_header`/`view_mrcs` (inspect files), `clean`
(remove intermediate files), `add_psize` (add a pixel size to the header of a
**`.mrc` volume only** — not arbitrary stacks/headers; positional `input` (.mrc),
`--Apix` default 1, `-o O`; `cryodrgn_utils.add_psize.help.txt`).

`write_cs` vs `filter_cs` (VALIDATED against source + live `--help`): **`write_cs` is
deprecated as of v3.4.1 and is now a thin delegate to `filter_cs`.** Its `main()` logs a
deprecation warning and then calls `filter_cs`'s main
(`sources/source/cryodrgn_4.2.1/cryodrgn/commands_utils/write_cs.py`:
`from cryodrgn.commands_utils.filter_cs import main as filter_cs_main`; `main()` → warn →
`filter_cs_main(args)`). Its `--help` *description* line still reads "Create a CryoSparc
`.cs` file from a particle stack," but that text is stale: the positional accepts **only
`.cs`** (`cryodrgn_utils.write_cs.help.txt`: `particles  Input particles (.cs)`), and because
it delegates to `filter_cs` it merely **filters an existing `.cs`** — `filter_cs` requires a
`.cs` input, subsets it by `--ind`, and ignores `--ctf`/`--datadir`/`--poses`
(`cryodrgn_utils.filter_cs.help.txt`). **Use `filter_cs` to filter an existing `.cs`**;
`write_cs` only survives as its deprecated alias. Neither command builds a `.cs` from a
`.mrcs`/`.star` stack — that `.cs` is produced by cryoSPARC itself. (Trust ladder: the
source behavior overrides the stale help-description text.)

## Captured live help synopses (VALIDATED: cryoDRGN 4.2.1)

These `usage:` lines are transcribed from the captured live `--help` for 4.2.1.
Flags, defaults, and positionals match those files exactly.

```text
# VALIDATED vs cryodrgn.downsample.help.txt
usage: cryodrgn downsample [-h] -D D -o OUTFILE [--outdir OUTDIR] [-b BATCH_SIZE]
                           [--is-vol] [--chunk CHUNK] [--datadir DATADIR]
                           [--max-threads MAX_THREADS] [--ind PKL]
                           input
# positional: input (.mrc/.mrcs/.star/.cs/.txt) ; -D new even box size
# -o/--outfile output (.mrc/.mrcs/.star/.txt) ; --outdir places stack elsewhere
# -b/--batch-size default 5000 ; --max-threads default 16 ; --ind filter by indices
```

```text
# VALIDATED vs cryodrgn.train_vae.help.txt
usage: cryodrgn train_vae [-h] -o OUTDIR --zdim ZDIM --poses POSES [--ctf pkl]
                          [--load WEIGHTS.PKL] [--no-analysis] [-n NUM_EPOCHS]
                          [-b BATCH_SIZE] [--lr LR] [--beta BETA] [--no-amp]
                          [--multigpu] [--do-pose-sgd] [--enc-layers QLAYERS]
                          [--enc-dim QDIM] [--encode-mode {conv,resid,mlp,tilt}]
                          [--dec-layers PLAYERS] [--dec-dim PDIM]
                          [--pe-type {...,gaussian,none}] [--window-r WINDOW_R]
                          [--uninvert-data] [--datadir DATADIR] [--lazy] ...
                          particles
# required: particles (.mrcs/.star/.cs/.txt), -o/--outdir, --zdim, --poses
# --ctf optional (omit only for already phase-flipped data)
# defaults: -n/--num-epochs 20, -b/--batch-size 16, --lr 0.0001, --beta 1/zdim,
#           --enc-dim/--dec-dim 1024, --enc-layers/--dec-layers 3,
#           --encode-mode resid, --pe-type gaussian, --window-r 0.85
# --load accepts the literal string "latest" to resume ; tilt opts for cryoDRGN-ET
# Analysis auto-runs on the FINAL epoch unless --no-analysis is given.
```

```text
# VALIDATED vs cryodrgn.analyze.help.txt
usage: cryodrgn analyze [-h] [--device DEVICE] [-o OUTDIR] [--skip-vol]
                        [--skip-umap] [--pc PC] [--n-per-pc N_PER_PC]
                        [--ksample KSAMPLE] [--Apix APIX] [--flip] [--invert]
                        [-d DOWNSAMPLE] [--low-pass LOW_PASS] [--crop CROP]
                        [--vol-start-index VOL_START_INDEX]
                        workdir epoch
# positional: workdir, epoch (1-based; corresponds to z.N.pkl / weights.N.pkl)
# defaults: --ksample 20, --pc 2, --n-per-pc 10, --vol-start-index 1
# --Apix default: infer from ctf.pkl, else 1 ; output default [workdir]/analyze.[epoch]
# (there is NO --Apix-only mode; --low-pass/--crop/--device are post-processing opts)
```

```text
# VALIDATED vs cryodrgn.eval_vol.help.txt
usage: cryodrgn eval_vol [-h] -c YAML -o O [--device DEVICE] [--prefix PREFIX]
                         [-z [Z ...]] [--z-start [...]] [--z-end [...]] [-n N]
                         [--zfile ZFILE] [--Apix APIX] [--flip] [--invert]
                         [-d DOWNSAMPLE] [--low-pass LOW_PASS] [--crop CROP]
                         [--vol-start-index VOL_START_INDEX]
                         weights
# positional: weights (model weights .pkl)
# -c/--config YAML is the config.yaml ; -o output .mrc or directory
# -z one z-value (length must equal zdim) ; --z-start/--z-end -n for a path ; --zfile many
# --prefix default vol_ ; --vol-start-index default 1
```

## Labeled templates (the form you may emit)

These show canonical placeholders. On a `ready` host you may substitute the user's
real paths and run the command AFTER explicit user confirmation; the
`[run-with-confirmation]` tag marks every command that touches real data or compute.
Replace `<current>` in `[config-state: <current>]` with the value from
`configs/site_config.local.md`.

```text
# VALIDATED vs cryodrgn.downsample.help.txt
# [config-state: <current>] [VALIDATED: cryoDRGN 4.2.1] [run-with-confirmation]
# Preprocess: downsample to a pilot box (D=128) then optionally D=256.
cryodrgn downsample <particles.mrcs> -D 128 -o <outdir>/particles.128.mrcs
```

```text
# VALIDATED vs cryodrgn.parse_pose_star.help.txt + cryodrgn.parse_ctf_star.help.txt
# [config-state: <current>] [VALIDATED: cryoDRGN 4.2.1] [run-with-confirmation]
# Parse poses + CTF from RELION (.star). For parse_pose_star, --outpkl is the output
# (-o is an alias); only -D and --Apix are optional overrides. parse_ctf_star uses -o.
cryodrgn parse_pose_star <particles.star> --outpkl <outdir>/pose.pkl
cryodrgn parse_ctf_star  <particles.star> -D <box> --Apix <apix> -o <outdir>/ctf.pkl
# Single-pass alternative (writes both pkls) — VALIDATED vs cryodrgn.parse_star.help.txt:
cryodrgn parse_star <particles.star> --poses <outdir>/pose.pkl --ctf <outdir>/ctf.pkl
```

```text
# VALIDATED vs cryodrgn.backproject_voxel.help.txt
# [config-state: <current>] [VALIDATED: cryoDRGN 4.2.1] [run-with-confirmation]
# Sanity check before training: voxel backprojection of a subset. --outdir is the
# output (-o is an alias); half-maps + FSC are produced by DEFAULT (suppress with
# --no-half-maps / --no-fsc-vals). Note: --uninvert-data means "do NOT invert".
cryodrgn backproject_voxel <particles.128.mrcs> --poses <poses.pkl> --ctf <ctf.pkl> --outdir <outdir>/bp.128 --first 10000
```

```text
# VALIDATED vs cryodrgn.train_vae.help.txt
# [config-state: <current>] [VALIDATED: cryoDRGN 4.2.1] [run-with-confirmation]
# Train heterogeneous VAE with known poses (pilot at D=128, small zdim).
# Required: particles, -o/--outdir, --zdim, --poses. --ctf optional (omit only if
# data is already phase-flipped). Analysis auto-runs on the final epoch (--no-analysis to skip).
cryodrgn train_vae <particles.128.mrcs> --poses <poses.pkl> --ctf <ctf.pkl> --zdim 8 -n 25 -o <outdir>
```

```text
# VALIDATED vs cryodrgn.abinit.help.txt
# [config-state: <current>] [VALIDATED: cryoDRGN 4.2.1] [run-with-confirmation]
# Ab initio (cryoDRGN-AI): no --poses required. Required: -o/--outdir, --zdim, particles.
cryodrgn abinit <particles.mrcs> --ctf <ctf.pkl> --zdim 8 -n 50 -o <outdir>
```

```text
# VALIDATED vs cryodrgn.analyze.help.txt
# [config-state: <current>] [VALIDATED: cryoDRGN 4.2.1] [run-with-confirmation]
# Analyze a trained model at epoch N (positionals: workdir epoch; epoch is 1-based,
# corresponds to z.N.pkl / weights.N.pkl). --Apix defaults to inference from ctf.pkl else 1.
cryodrgn analyze <workdir> <epoch>
```

```text
# VALIDATED vs cryodrgn.eval_vol.help.txt
# [config-state: <current>] [VALIDATED: cryoDRGN 4.2.1] [run-with-confirmation]
# Generate a single volume at a chosen z (length of -z must equal zdim).
# -c/--config is config.yaml ; weights.pkl is the positional.
cryodrgn eval_vol <workdir>/weights.pkl -c <workdir>/config.yaml -z <z...> -o <outdir>/vol.mrc
```

### Ground-truth output layout (from the validation smoke log)

VALIDATED end-to-end (cite the validation run and `resmoke_cryodrgn.sh`):

- `train_vae` / `abinit` workdir: `config.yaml`, `run.log`, `weights.pkl`,
  `weights.N.pkl`, `z.pkl`, `z.N.pkl`, and `analyze.N/` (analysis auto-runs on the
  final epoch unless `--no-analysis`).
- `backproject_voxel --outdir DIR`: `backproject.mrc`, `half_map_a.mrc`,
  `half_map_b.mrc`, `fsc-plot.png`, `fsc-vals.txt`.

See `05_core_workflows.md` for how these chain together and which decisions gate each step.
