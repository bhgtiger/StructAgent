# 04 — Data model and file formats

Grounded in captured live `--help` for cryoDRGN 4.2.1 (captured 2026-06-06 on a
Linux + NVIDIA GPU host; the realized #1 source on the trust ladder), the pinned 4.2.1 source, and the
GPU smoke log (the validation run). The internal byte layout of
the `.pkl` artifacts is not enumerated here, but `pose.pkl` / `ctf.pkl` are produced and
consumed *exactly* by the validated `parse_*` / `train_*` / `backproject_voxel` commands
below, so you do not need to inspect their pickle internals to use them correctly.

## Inputs

| Input | Formats | Notes |
|---|---|---|
| Particle image stack | `.mrcs`, `.mrc`, a `.txt` listing multiple `.mrcs`, a RELION `.star`, or a cryoSPARC `.cs` | Positional arg to `downsample`, `train_vae`, `train_nn`, `train_dec`, `abinit`, `backproject_voxel`, `eval_images`. The help string `Input particles (.mrcs, .star, .cs, or .txt)` is identical across these; `downsample` additionally accepts a volume `.mrc` (`--is-vol`). `[VALIDATED: cryoDRGN 4.2.1]` (cryodrgn.downsample.help.txt, cryodrgn.train_vae.help.txt, cryodrgn.train_nn.help.txt, cryodrgn.train_dec.help.txt, cryodrgn.abinit.help.txt, cryodrgn.backproject_voxel.help.txt, cryodrgn.eval_images.help.txt) |
| `--datadir` | folder of `.mrcs` | For `.star`/`.cs` inputs whose `.mrcs` paths are relative, supply `--datadir DATADIR` ("Path prefix to particle stack if loading relative paths from a .star or .cs file"). Available on `downsample`, `train_vae`, `train_nn`, `train_dec`, `abinit`, `backproject_voxel`, `eval_images`. `[VALIDATED: cryoDRGN 4.2.1]` (same help files) |
| Poses | `pose.pkl` | Produced by `parse_pose_star` / `parse_pose_csparc`; passed via `--poses POSES`. Required for `train_vae`/`train_nn`/`train_dec`/`backproject_voxel`; `abinit` searches poses ab initio (no `--poses`). `[VALIDATED: cryoDRGN 4.2.1]` (cryodrgn.parse_pose_star.help.txt, cryodrgn.train_vae.help.txt) |
| CTF parameters | `ctf.pkl` | Produced by `parse_ctf_star` / `parse_ctf_csparc`; passed via `--ctf pkl`. Optional in the help (used for phase-flipping); omit only if images are already phase-flipped. `[VALIDATED: cryoDRGN 4.2.1]` (cryodrgn.parse_ctf_star.help.txt, cryodrgn.train_vae.help.txt) |
| Index filter | `--ind PKL` | Pickle of particle indices to subset a stack (e.g. keep good particles); present on `downsample`, the trainers, `backproject_voxel`, `eval_images`. `[VALIDATED: cryoDRGN 4.2.1]` |

### CTF parsing from a RELION `.star` (`parse_ctf_star`)

`parse_ctf_star` reads the per-particle CTF columns from the `.star` file. The
override flags below let you *supply or override* image parameters that are missing
from (or wrong in) the file — these are the actual CLI flags, listed under
"Optionally provide missing image parameters":

| Flag | Meaning (verbatim from help) |
|---|---|
| `-D D` | Image size in pixels |
| `--Apix APIX` | Angstroms per pixel |
| `--kv KV` | Accelerating voltage (kV) |
| `--cs CS` | Spherical abberation (mm) |
| `-w W` | Amplitude contrast ratio |
| `--ps PS` | Phase shift (deg) |

Output is written with `-o O` ("Output pkl of CTF parameters"); positional is `star`;
`--png PNG` optionally plots the CTF. The underlying RELION columns these map to are the
`_rln*` CTF fields (`_rlnDefocusU`, `_rlnDefocusV`, `_rlnDefocusAngle`, `_rlnVoltage`,
`_rlnSphericalAberration`, `_rlnAmplitudeContrast`, `_rlnPhaseShift`); the flags above are
how you fill them in when absent. `[VALIDATED: cryoDRGN 4.2.1]` (cryodrgn.parse_ctf_star.help.txt)

> **Box-size gotcha:** when parsing poses/CTF, the box-size argument refers to the
> **original / consensus-refinement** box, **not** a downsampled box, so that
> translation shifts parse in the right units. For `parse_pose_star`, `-D` is
> documented as "override box size of reconstruction (pixels)"; for `parse_ctf_star`,
> `-D` is "Image size in pixels". Pass the original pre-downsample value here even if
> you later train on a downsampled stack.
> `[VALIDATED: cryoDRGN 4.2.1]` (cryodrgn.parse_pose_star.help.txt, cryodrgn.parse_ctf_star.help.txt)

## Box-size guidance

- Pilot/sanity: **D = 128** (faster training, particle filtering).
- High-resolution: up to **D = 256** (maximum recommended). Larger inputs should
  be downsampled to 256. `-D` must be **even** (`downsample` help: "New box size in
  pixels, must be even"). `[VALIDATED: cryoDRGN 4.2.1]` (cryodrgn.downsample.help.txt)

## Outputs (a `train_vae` / `abinit` workdir)

Validated against the GPU smoke run (`work/cryodrgn/vae_out`, see
the validation run and the resmoke script): a training workdir
(`-o OUTDIR`) contains the following. `[VALIDATED: cryoDRGN 4.2.1]`

| Artifact | Meaning |
|---|---|
| `config.yaml` | Run configuration as **YAML** (records cryoDRGN `version`, architecture, paths). Consumed by `eval_vol`/`analyze`. |
| `run.log` | Training log (epoch loss, `Use cuda True`, resolved defaults). |
| `weights.pkl` / `weights.N.pkl` | Trained NN weights — final and per-checkpoint epoch `N` (`--checkpoint` interval, default 1). |
| `z.pkl` / `z.N.pkl` | Latent embeddings per particle, **in input order** — final and per-epoch `N`. |
| `pose.pkl` | Refined poses (only when pose SGD `--do-pose-sgd` was used, or for `abinit` which searches poses). |
| `analyze.N/` | Analysis output dir for epoch `N` (PCA/UMAP plots, k-means volumes, PC-traversal volumes, template Jupyter notebooks). |

`train_vae`, `train_dec`, and `abinit` **auto-run `cryodrgn analyze` on the final
training epoch by default**; suppress with `--no-analysis`. (Smoke: `train_vae … -n 1`
produced `vae_out/{config.yaml, run.log, weights.pkl, z.pkl, analyze.1/}`.)
`[VALIDATED: cryoDRGN 4.2.1]` (cryodrgn.train_vae.help.txt: `--no-analysis` = "Do not
automatically run cryodrgn analyze on the final training epoch"; cryodrgn.abinit.help.txt;
cryodrgn.train_dec.help.txt)

### `backproject_voxel --outdir DIR`

Voxel backprojection writes a fixed set of files into the output folder
(`--outdir OUTDIR`, with `-o` as an alias). Half-maps and the FSC curve are produced
**by default**; suppress with `--no-half-maps` / `--no-fsc-vals`. Validated output set
(smoke `work/cryodrgn/bp`): `[VALIDATED: cryoDRGN 4.2.1]`

| Artifact | Meaning |
|---|---|
| `backproject.mrc` | Full reconstruction. |
| `half_map_a.mrc` / `half_map_b.mrc` | Half-map reconstructions (default). |
| `fsc-plot.png` | FSC curve plot (default). |
| `fsc-vals.txt` | Tabulated FSC values (default). |

`backproject_voxel` requires `--poses POSES`; `--ctf pkl` is optional (used for phase
flipping). Note `--uninvert-data` means "Do **not** invert data sign" (i.e. keep the
input sign). `[VALIDATED: cryoDRGN 4.2.1]` (cryodrgn.backproject_voxel.help.txt)

### Other generated volumes

`eval_vol` and `analyze` write `.mrc` density maps from latent coordinates (see
`05_core_workflows.md`).

## Indexing convention (1-based)

cryoDRGN 4.2.1 uses **1-based** epoch/volume indexing. This is stated verbatim in the
live help of every command that takes an `epoch` positional:

> `epoch  Epoch number N to analyze (1-based indexing, corresponding to z.N.pkl, weights.N.pkl)`

so `cryodrgn analyze <workdir> 25` analyzes the 25th epoch → `z.25.pkl`,
`weights.25.pkl`. The same wording appears for `analyze`, `analyze_landscape`,
`cryodrgn_utils make_movies`, `cryodrgn_utils plot_classes`, and
`cryodrgn_utils analyze_convergence`. `[VALIDATED: cryoDRGN 4.2.1]`
(cryodrgn.analyze.help.txt, cryodrgn.analyze_landscape.help.txt,
cryodrgn_utils.make_movies.help.txt, cryodrgn_utils.plot_classes.help.txt,
cryodrgn_utils.analyze_convergence.help.txt)

Volume-generation commands also default `--vol-start-index` to `1`
(`analyze`, `analyze_landscape`, `eval_vol`). `[VALIDATED: cryoDRGN 4.2.1]`

## `config.yaml`

cryoDRGN loads/saves run configuration as **YAML**. `eval_vol` takes the config via
`-c YAML` / `--config YAML` ("CryoDRGN config.yaml file") — the live help literally calls
the argument `YAML`, and the example passes `<workdir>/config.yaml`. On save, cryoDRGN
injects its `version` into the config, useful for detecting which release produced a
workdir. Loading configuration from a legacy `.pkl` is deprecated. `[VALIDATED:
cryoDRGN 4.2.1]` (cryodrgn.eval_vol.help.txt)

## What this skill never ships or fabricates

No `.mrcs`/`.star`/`.cs`/`.pkl`/`.mrc`/`config.yaml` are bundled. Treat all such user
files as **local/private** (see `07_safety_license_privacy.md`); never upload or
fabricate them. Do not move, convert, or delete the user's data without explicit
confirmation.
