# 08 — Validation and benchmarks

## What the skill may and may not claim

**May claim** (with citation + version/hardware context):

- cryoDRGN performs *heterogeneous* reconstruction by modeling a continuous
  distribution of 3D structures with a neural network (`[src: homepage; README @ 4.2.1]`).
- The documented timing anecdote: 100k particles on **1 V100 GPU**, ~12 min/epoch
  at D=128 and ~47 min/epoch at D=256 (`[src: README.md @ 4.2.1]`). Always attach
  the GPU + dataset-size context; never present as a general benchmark.
- Recommended box sizes: pilot D=128, max D=256 (`[src: README/installation @ 4.2.1]`).

**Must NOT claim**:

- Resolution/FSC numbers, accuracy comparisons, or speedups for a user's dataset.
- That cryoDRGN will "work" or "beat" another method on specific data.
- Any benchmark not already in captured docs/papers — paper digests are **not**
  yet filed (P1 gap, see "Papers" below). If asked to evaluate methods
  quantitatively, say the digests are pending and avoid numbers.

This claim discipline is independent of the execution posture: the skill MAY run
real validation jobs (next section) on a `ready` host after confirmation, but it
still must not invent or extrapolate resolution/accuracy figures for the user's
data.

## In-method validation cryoDRGN provides

On a host where the probe reports `config_state: ready` (cryoDRGN installed,
Linux + NVIDIA GPU; the GPU smoke ran on a Linux + NVIDIA GPU host 2026-06-06,
`[src: the validation run]`), these checks **may be RUN** after explicit user
confirmation, against the user's real paths. On any other host, describe them
instead of running them.

- **Backprojection sanity check** (`backproject_voxel`) before training, with
  half-maps + FSC, to confirm poses/CTF parsed correctly. Half-maps + FSC are the
  DEFAULT output (suppress with `--no-half-maps`/`--no-fsc-vals`); `--outdir DIR`
  (`-o` is an alias), requires `--poses`, optional `--ctf`
  (`[VALIDATED: cryoDRGN 4.2.1; src: cryodrgn.backproject_voxel.help.txt]`).
  Output layout in `DIR/`: `backproject.mrc`, `half_map_a.mrc`, `half_map_b.mrc`,
  `fsc-plot.png`, `fsc-vals.txt` (`[src: VALIDATION_SUMMARY.md; resmoke_cryodrgn.sh]`).
  See `05_core_workflows.md`.
- **FSC** between two volumes (`cryodrgn_utils fsc`). Takes **two positional
  volumes** plus optional `--mask`, `--ref-volume` (cryoSPARC-style plot using a
  reference .mrc to build masks), `--corrected` (phase-randomization resolution
  cutoff in Å), `--plot/-p` (optionally a `.png` name), `--Apix`, and
  `--outtxt/-o` to save `<resolution> <fsc_val>` rows
  (`[VALIDATED: cryoDRGN 4.2.1; src: cryodrgn_utils.fsc.help.txt]`).
  To only plot already-computed FSC text files use `cryodrgn_utils plot_fsc`
  (positional `input [input ...]`, `--Apix/-a`, `--outfile/-o`)
  (`[VALIDATED: cryoDRGN 4.2.1; src: cryodrgn_utils.plot_fsc.help.txt]`).
- **Convergence check**: train one budget then a longer one and compare results;
  inspect loss; `cryodrgn_utils analyze_convergence`. Positionals are
  **`workdir epoch`** (epoch is 1-based, corresponding to `z.N.pkl`/`weights.N.pkl`).
  Rich optional args: `-o/--outdir` (default `[workdir]/convergence.[epoch]`),
  `--epoch-interval`, UMAP controls (`--force-umap-cpu`, `--subset`, `--skip-umap`,
  `--n-epochs-umap`, `--random-seed`, `--random-state`), volume-generation
  (`--Apix`, `--flip`, `--invert`, `-d/--downsample`, `--device`, `--skip-volgen`),
  and mask-generation (`--max-threads`, `--thresh`, `--dilate`, `--dist`)
  (`[VALIDATED: cryoDRGN 4.2.1; src: cryodrgn_utils.analyze_convergence.help.txt]`).
- **Latent-space analysis** (PCA/UMAP, k-means volumes, trajectories) to judge
  whether heterogeneity is real vs. artifactual. `cryodrgn train_vae` auto-runs
  `analyze` on the final epoch unless `--no-analysis`, producing `analyze.N/` in
  the workdir (`[src: VALIDATION_SUMMARY.md]`); see `03_cli_reference.md` and
  `05_core_workflows.md` for `analyze` flags and the workdir layout.

## Fixtures and quicktest

The pinned source ships `tests/quicktest.sh` and `tests/data/` (e.g. the tiny
`hand.mrcs` toy reconstruction and the `relion31.mrcs`/`relion31.star` D=256
fixture) plus a larger `tests/` suite. These pinned tests/data **were run
end-to-end on GPU** on a Linux + NVIDIA GPU host against cryoDRGN 4.2.1
(`[src: the validation run]`): the relion31 fixture went through `downsample`,
`parse_pose_star`, `parse_ctf_star`, `backproject_voxel`, `train_vae`, and
`analyze` with `Use cuda True`. On a host where the probe reports
`config_state: ready`, the quicktest/fixtures **may be run** after explicit user
confirmation; otherwise describe them and do not assert that cryoDRGN "passes
tests" on an unverified host.

```text
# [run-with-confirmation] [VALIDATED: cryoDRGN 4.2.1; src: cryodrgn.train_vae.help.txt] [config-state: ready]
# Illustrative toy reconstruction on the shipped hand.mrcs fixture. Confirm before running.
# Flags below are valid per the captured train_vae help: --zdim is REQUIRED.
cryodrgn train_vae data/hand.mrcs -o output/toy_recon_vae --poses data/hand_rot.pkl --zdim 10 --seed 0 --pe-type gaussian --lr .0001
```

## Skill self-validation (this repo)

`tests/validate_static.py` mechanically checks the skill itself (not cryoDRGN):
references exist, frontmatter/`name` present, the config-state capability table
exists, canonical labels appear on every command template, no
install/download/job token leaks into the probe's command surface, and the probe
imports/compiles. `tests/eval/` holds behavioral eval cases + reference answers.
See `tests/trigger_tests.md`.

> **Label scheme (current):** `tests/validate_static.py` checks the realized
> execution-capable label set — `CANONICAL_LABELS = ["[config-state:", "[VALIDATED: cryoDRGN"]`.
> `[live-unverified]` has been retired (live help is now captured), `[VALIDATED: cryoDRGN 4.2.1]`
> and `[run-with-confirmation]` were added, and `[not-run]` is reserved for
> illustrative/destructive examples. The validator and these docs are in sync — a full run
> reports **10/10 checks passed**. Keep them in lockstep if the label convention changes again.

## Papers (science only — not CLI, not performance claims)

See `01_source_map.md` for the full list (Nature Methods 2021, ICLR 2020, ICCV
2021, Nature Protocols 2023, cryoDRGN-ET 2024, cryoDRGN-AI 2025). Read them with a
paper-reader workflow and file digests *before* making any quantitative claim.
Paper digests are **not yet filed (open P1 gap)** — but this gap is independent of
the execution posture and does not gate running validation jobs on a `ready` host.
