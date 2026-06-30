# 03 — CLI and Web-Service Surface

Two delivery modes with **different inputs, defaults, and limits**. Always
establish which one the user means before planning.

Baseline for the CLI: `Namdinator_Generic.sh` @ `5814c947`. The option string in
source is `getopts "hp:m:n:c:b:g:e:t:f:s:r:lxi"` — i.e. `p m n c b g e t f s r`
take arguments; `h l x i` are switches. **No live `-h` was captured** — verify
exact help text on a real host.

## Local CLI flags

Canonical example (README): `./Namdinator_Generic.sh -p input.pdb -m map.mrc -r 3.5 -x`

| Flag | Arg? | Default | Meaning / caution |
|---|---|---|---|
| `-p` | yes | — (req) | Input model. Source path = standard **PDB**. Web also takes `.cif`/`.pdb.gz`; **local CIF/GZ unverified**. |
| `-m` | yes | — (req) | Input map: `.mrc`, `.ccp4`, `.map`, `.situs`. |
| `-r` | yes | — (req) | Map resolution (Å). Used for CC and Phenix real-space refinement. |
| `-e` | yes | `2000` | Minimization steps. Increase if atoms move too fast / unstable. |
| `-g` | yes | `0.3` | G-scale / map-force scaling. Higher pulls harder, can destabilize. |
| `-b` | yes | `20` | B-factor applied via Phenix pdbtools (org repo). |
| `-t` | yes | `300` | Initial temperature (K). |
| `-f` | yes | `300` | Final temperature (K). |
| `-s` | yes | `20000` | Simulation steps. Help suggests `20000–500000` for large changes; **web caps 200000**. |
| `-c` | yes | `5` | Phenix real-space-refinement macrocycles. |
| `-n` | yes | `lscpu` count | Processor count. **Linux-specific default**; set explicitly off Linux. |
| `-x` | no | off | Add coordinate Phenix real-space refinement → `last_frame_rsr.pdb`. Recommended by README/manual for many cryo-EM cases. Phenix is required even without `-x`; this branch adds a `PHENIXMASTERDIR`/`phenix_env.sh` requirement. |
| `-l` | no | off | Keep HETATM for AutoPSF/simulation. Help warns it **often fails** and does not work well with `-x`. |
| `-i` | no | off | GBIS implicit solvent. Slightly better geometry possibly, but **~7× slower**. |
| `-h` | no | — | Help. May require environment setup first; capture live. |

Command-planning rules:
- Ask local vs. web every time.
- Require a roughly pre-fitted model + map + resolution.
- Warn that non-ATOM records are removed by default (ref 04, SKILL §6).
- For crystallographic maps, require P1 expansion first (ref 04).
- Do not recommend execution from macOS without a Linux-compatible runtime.
- Do not promise reproducibility from a single run; MDFF is stochastic.

## Web-service form surface

Snapshots 2026-06-30. Form action `https://namdinator.au.dk/assets/scripts/prepare.php`,
`POST`, `multipart/form-data`. **Observed UI only — the form was never submitted
and the backend contract is unknown. Do not build an API caller from this.**

| Field | Type | Defaults / limits | Meaning |
|---|---|---|---|
| `pdb_file` | file | `.pdb`, `.cif`, `.pdb.gz`; one file | Upload model. |
| `pdb_file_fetch` | text | pattern `[A-Za-z0-9_]{4,4}` | Fetch model by PDB ID. |
| `map_file` | file | `.ccp4`, `.map`, `.mrc`, `.map.gz`; one file | Upload map. |
| `map_file_fetch` | text | pattern `[A-Za-z0-9_]{4,8}` | Fetch map by EMDB ID. |
| `map_res` | number | min 0, max 50, step 0.01, **required** | Map resolution. |
| `start_temp` | number | default **298**, 0–1000 | Start temperature (K). |
| `final_temp` | number | default **298**, 0–1000 | Final temperature (K). |
| `g_scale` | number | default 0.3, 0–100, step 0.01 | MDFF map-force scaling. |
| `minim_steps` | number | default 2000, 0–5000 | Minimization steps. |
| `sim_steps` | number | default 20000, 0–**200000** | MDFF simulation steps. |
| `phenix_rsr_cycles` | number | default 5, 0–5 | Phenix real-space-refinement cycles. |
| `water_molecules` | radio | values 1/0 (HTML has conflicting `checked`) | Labeled "Implicit Solvent (GBIS)", Include/Exclude. **Verify live before relying on it.** |

The upload JS rejects filenames containing spaces or characters such as `(`,
`)`, `#`, `&`. Recommend simple ASCII filenames.

## CLI vs. web — differences to flag

- Temperatures: CLI 300 K vs. web 298 K defaults.
- Simulation-step ceiling: web hard-caps at 200000; the CLI help suggests up to
  500000 for hard cases — so very long runs are a **local-only** option.
- Minimization ceiling: web caps at 5000.
- Privacy: web uploads are stored 14 days server-side (ref 09); local is not.
- Field name `water_molecules` vs. label "Implicit Solvent (GBIS)" — treat as
  historical naming; do not assert behavior without a live check.
