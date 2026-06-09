# 06 — Interoperability (RELION / cryoSPARC)

cryoDRGN consumes upstream refinements from RELION (`.star`) and cryoSPARC (`.cs`)
and can write selections back out. The import, inspect, and export/write-back
flags below are **`[VALIDATED: cryoDRGN 4.2.1]`** against captured live `-h`
(captured 2026-06-06 on a Linux + NVIDIA GPU host): `cryodrgn.parse_pose_star.help.txt`,
`cryodrgn.parse_ctf_star.help.txt`, `cryodrgn.parse_pose_csparc.help.txt`,
`cryodrgn.parse_ctf_csparc.help.txt`, `cryodrgn.parse_star.help.txt`,
`cryodrgn_utils.view_header.help.txt`, `cryodrgn_utils.view_cs_header.help.txt`,
`cryodrgn_utils.view_mrcs.help.txt`, `cryodrgn_utils.write_star.help.txt`,
`cryodrgn_utils.write_cs.help.txt`, `cryodrgn_utils.filter_cs.help.txt`,
`cryodrgn_utils.filter_star.help.txt`, `cryodrgn_utils.filter_mrcs.help.txt`,
`cryodrgn_utils.filter_pkl.help.txt`, `cryodrgn_utils.parse_relion.help.txt`,
`cryodrgn_utils.flip_hand.help.txt`.

## Import (upstream → cryoDRGN)

| From | Command | Output flag | Produces |
|---|---|---|---|
| RELION `.star` poses | `cryodrgn parse_pose_star` | `--outpkl PKL` (`-o` alias) | `pose.pkl` |
| RELION `.star` CTF | `cryodrgn parse_ctf_star` | `-o O` | `ctf.pkl` |
| cryoSPARC `.cs` poses | `cryodrgn parse_pose_csparc` | `-D D` (required) + `-o PKL` | `pose.pkl` |
| cryoSPARC `.cs` CTF | `cryodrgn parse_ctf_csparc` | `-o O` | `ctf.pkl` |
| RELION `.star` (CTF + poses, one pass) | `cryodrgn parse_star` | `--ctf CTF` and/or `--poses POSES` | `ctf.pkl` / `pose.pkl` |
| RELION **v5 tomography** tilt-series → 2D coords | `cryodrgn_utils parse_relion` | `-o OUTPUT` (default `particles_2d.star`) | expanded 2D `.star` |

> `cryodrgn parse_star` is the unified single-pass RELION parser; it reads one
> input `.star` and writes CTF and/or poses with `--ctf`/`--poses`. The earlier
> "RELION (general) → `cryodrgn_utils parse_relion`" row was **wrong**:
> `parse_relion` is a RELION-**v5 TOMOGRAM → 2D particle-coordinate** helper
> (`-t tomograms.star -p particles.star --tilt-dim W H`), not a general `.star`
> parser. (`[src: cryodrgn.parse_star.help.txt, cryodrgn_utils.parse_relion.help.txt]`)

```text
# [VALIDATED: cryoDRGN 4.2.1] [config-state: <ready|partial|...>] [run-with-confirmation]
# RELION import. parse_pose_star: positional input .star; output is --outpkl PKL (-o alias).
# -D and --Apix are OPTIONAL overrides only (used when the .star lacks box/pixel size or
# stores translations in Angstroms); -D / --Apix are the ORIGINAL/consensus image params.
cryodrgn parse_pose_star <particles.star> -o <outdir>/pose.pkl [-D <orig_box>] [--Apix <apix>]
cryodrgn parse_ctf_star  <particles.star> -o <outdir>/ctf.pkl  [-D <orig_box>] [--Apix <apix>]

# Or do both in one pass with the unified parser:
cryodrgn parse_star <particles.star> --ctf <outdir>/ctf.pkl --poses <outdir>/pose.pkl \
                    [-D <orig_box>] [--Apix <apix>]
```

```text
# [VALIDATED: cryoDRGN 4.2.1] [config-state: <ready|partial|...>] [run-with-confirmation]
# cryoSPARC import. parse_pose_csparc: -D (the consensus/original refinement box size)
# is REQUIRED; add --abinit or --hetrefine to match the source job type. No --Apix here.
cryodrgn parse_pose_csparc <particles.cs> -D <orig_box> -o <outdir>/pose.pkl [--abinit | --hetrefine]
# parse_ctf_csparc: -o required; -D / --Apix optional overrides; --png to plot the CTF.
cryodrgn parse_ctf_csparc  <particles.cs> -o <outdir>/ctf.pkl [-D <orig_box>] [--Apix <apix>]
```

Common gotchas (see also `09_troubleshooting.md`):

- Broken relative paths to `.mrcs` inside a `.star`/`.cs` → pass `--datadir <dir>`
  (supported on the write/inspect utilities; `parse_*` read the embedded paths).
- `-D`/`--Apix` overrides must be the **original** image parameters
  (pre-downsample), or shifts/CTF scale wrong. For `parse_pose_csparc`, `-D` is
  required and is the consensus refinement box size.
- `parse_ctf_star` expects standard `_rln*` CTF fields (`04_data_model_and_formats.md`).

## Inspect headers/metadata (`cryodrgn_utils`)

All three inspectors take a **positional** input only (plus `view_mrcs` extras):

```text
# [VALIDATED: cryoDRGN 4.2.1] [config-state: <ready|partial|...>]
cryodrgn_utils view_header    <file.mrc|file.mrcs>   # header of a .mrc map or .mrcs stack (positional only)
cryodrgn_utils view_cs_header <particles.cs>         # first row of a cryoSPARC .cs (positional only)
cryodrgn_utils view_mrcs      <stack.mrcs>           # view a stack; positional accepts .mrc/.mrcs/.star/.cs/.txt
#   view_mrcs options: --datadir DIR (for .star/.cs), --invert, --ind PKL (subset), -o O (save image)
```

## Export / write back (cryoDRGN → upstream)

| Utility | Purpose |
|---|---|
| `cryodrgn_utils write_star` | Create a RELION `.star` from a particle stack. Positional `particles` (`.mrcs`, `.txt`, or `.star`); `-o OUTFILE/--outfile`; `--ctf` **required** for `.mrcs`/`.txt` inputs, optional/unneeded when filtering an existing `.star`; optional `--poses`, `--ind`, `--datadir`, `--full-path`, `--relion30` (RELION 3.0 format; default 3.1). |
| `cryodrgn_utils write_cs` | **Deprecated since v3.4.1; now a thin delegate to `filter_cs`** — its `main()` prints a deprecation WARNING then calls `filter_cs`. Its positional accepts only a `.cs` (the `--help` "create from a stack" description is stale), so in practice it just *filters* an existing `.cs` by `--ind` and ignores `--ctf`/`--datadir`/`--poses`. Use `filter_cs` instead. |
| `cryodrgn_utils filter_cs` | **Only filters an existing `.cs`** by indices: positional `particles` must be a `.cs`; `--ind IND` (required), `-o/--output`. Neither `filter_cs` nor `write_cs` builds a `.cs` from a `.mrcs`/`.star` — that `.cs` is produced by cryoSPARC itself. |
| `cryodrgn_utils filter_star` | Subset a `.star` by indices: `--ind IND` (required), `-o O`; `--et` if the `.star` includes tilts; `--micrograph-files`/`-m` to split output into one `.star` per micrograph (then `-o` is a directory). |
| `cryodrgn_utils filter_mrcs` | Subset a stack by indices: positional `.mrcs`/`.txt`/`.star`/`.cs`; `--ind IND` (required), `--outfile/-o`. |
| `cryodrgn_utils filter_pkl` | Subset a cryoDRGN `.pkl` (e.g. `pose.pkl`/`ctf.pkl`): `--ind IND` **or** `--first N`, `-o/--output`. |

```text
# [VALIDATED: cryoDRGN 4.2.1] [config-state: <ready|partial|...>] [run-with-confirmation]
# Subset a .star by an indices.pkl (e.g. particles kept after `cryodrgn filter`):
cryodrgn_utils filter_star <particles.star> --ind <indices.pkl> -o <outdir>/kept.star

# Filter an EXISTING .cs by indices (filter_cs only filters; input must be a .cs):
cryodrgn_utils filter_cs   <particles.cs>   --ind <indices.pkl> -o <outdir>/kept.cs

# Write a RELION .star FROM a stack. --ctf is required for a .mrcs/.txt input;
# when the input is already a .star you can just filter it and no CTF is needed:
cryodrgn_utils write_star  <particles.mrcs> -o <outdir>/out.star --ctf <ctf.pkl> \
                           [--poses <pose.pkl>] [--ind <indices.pkl>]
cryodrgn_utils write_star  <particles.star> -o <outdir>/kept.star --ind <indices.pkl>

# `write_cs` is a DEPRECATED alias that just warns and delegates to filter_cs (filters a .cs):
cryodrgn_utils write_cs    <particles.cs> --ind <indices.pkl> -o <outdir>/kept.cs
```

> Round-tripping selections back to RELION/cryoSPARC can break a project if column
> conventions differ, so **confirm before round-tripping selections back to
> RELION/cryoSPARC on a real project**. `write_cs` is deprecated since v3.4.1: it emits a
> warning and delegates to `filter_cs`, so it only *filters* an existing `.cs` by `--ind`.
> Use `filter_cs` directly. To create a `.cs` from a raw `.mrcs`/`.star` stack, export from
> cryoSPARC itself — no cryoDRGN util builds one.

**CryoSPARC-orchestrated adapter format.** If the workflow starts and ends inside cryoSPARC (for example, cryoSPARC particles → cryoDRGN latent analysis → class selections or volumes returned to cryoSPARC), keep the adapter contract in the cryoSPARC skill: `cryosparc/references/29_external_tool_bridge_format.md` plus `23_external_jobs.md`. This cryoDRGN skill remains the source of truth for cryoDRGN CLI commands, `.cs`/`.star` parsing, filtering constraints, and cryoDRGN-side validation. Preserve/filter the original cryoSPARC `.cs` when writing selections back; do not pretend cryoDRGN can synthesize a new cryoSPARC particle dataset from arbitrary stacks.

## Handedness across tools

cryoEM tools differ in handedness conventions. `cryodrgn_utils flip_hand` flips a
volume's handedness — positional `input` (`.mrc`), output via `--outmrc/-o` (default
writes `<name>_flipped.mrc`). `cryodrgn analyze` and `cryodrgn eval_vol` both expose
`--flip` (flip handedness of output volumes) and `--invert` (invert contrast). If a
cryoDRGN map is mirrored vs your RELION/cryoSPARC reference, this is usually a
handedness convention difference, not a reconstruction error (`09_troubleshooting.md`).
(`[VALIDATED: cryoDRGN 4.2.1 — cryodrgn_utils.flip_hand.help.txt, cryodrgn.analyze.help.txt, cryodrgn.eval_vol.help.txt]`)
