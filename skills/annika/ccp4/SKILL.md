---
name: ccp4
description: Run CCP4 and CCP4-adjacent crystallography tools via CLI for
  explicit tool requests — refmac5, refmacat, servalcat, acedrg, freerflag,
  cad, mtzdump, sftools, pdbset, pdbcur, phaser, molrep, cbuccaneer,
  cnautilus, aimless, pointless, ctruncate, privateer, run ccp4 — or when
  the user names a CCP4 .com / Refmac keyword script. Do NOT trigger on
  generic words like "refine", "fit", "rebuild", "model", or "map"; do not
  trigger on "CCP4" alone unless the user asks to run or check a
  command-line CCP4 tool.
---

# CCP4 (execution-only)

## Failure contract
Skills never guess. Missing model, MTZ, ligand restraint CIF, FreeR column, or column labels → **fail loudly and ask**. Never auto-pick the most recent file in CWD. Never silently generate FreeR flags inside a refinement wrapper. Never invent column labels — `--labin` is required when more than one mapping is plausible.

Strategic decisions ("Refmac5 vs Phenix?", "Buccaneer or Phenix AutoBuild?") belong in `structural-strategy`, not here. Coot scripted runs belong in `coot`. This skill only executes named CCP4 binaries.

## Prerequisites
```bash
CCP4_SETUP="${CCP4_SETUP:-}"
for p in /Applications/ccp4-*/bin/ccp4.setup-sh \
         /opt/xtal/ccp4-*/bin/ccp4.setup-sh \
         "$HOME"/ccp4-*/bin/ccp4.setup-sh; do
  [ -f "$p" ] && CCP4_SETUP="$p" && break
done
source "$CCP4_SETUP"
```
Run `scripts/check_env.sh` to verify before any real run. It reports by capability group (core refinement, MR, autobuild, data reduction, optional helpers) so a missing optional binary does not fail the whole skill.

## Core recipes

### 1. Refmac5 reciprocal-space refinement (X-ray)
Always run an MTZ preflight first; then call `run_refmac5.sh` with explicit `--labin`.

```bash
python scripts/mtz_preflight.py --mtz data.mtz --workflow refmac5

bash scripts/run_refmac5.sh --dry-run \
  --xyzin model.pdb \
  --hklin data.mtz \
  --xyzout refined.pdb \
  --hklout refined.mtz \
  --preset xray_default \
  --labin "FP=F SIGFP=SIGF FREE=FreeR_flag" \
  --ncyc 10
```

If the MTZ has no FreeR column the wrapper refuses to run and prints the exact `freerflag` command to approve. It does not generate flags silently.

### 2. AceDRG ligand restraints
```bash
bash scripts/run_acedrg.sh --dry-run --smiles "CC(=O)O" --resname LIG --out-prefix LIG
bash scripts/run_acedrg.sh --dry-run --mol ligand.mol --resname LIG --out-prefix LIG
```
The wrapper requires explicit input mode (`--smiles`, `--smiles-file`, `--mol`, or `--mmcif`), validates the residue code, and warns if the code already exists in the CCP4 monomer library.

### 3. Free-form CCP4 dispatcher
For tools without a dedicated wrapper (`cad`, `mtzdump`, `sftools`, `pdbset`, `pdbcur`, `pointless`, `aimless`, `ctruncate`, `phaser`, `cbuccaneer`, `cnautilus`, …):

```bash
bash scripts/run_ccp4.sh --dry-run -- mtzdump HKLIN data.mtz
bash scripts/run_ccp4.sh --dry-run --stdin keywords.com -- refmacat HKLIN d.mtz HKLOUT o.mtz
```
The dispatcher sources the CCP4 setup, prints the resolved env, prints the exact command, supports `--dry-run`, will not overwrite outputs unless `--force`, and writes everything (resolved command, stdin, stdout, stderr) into `ccp4_runs/<tool>_<timestamp>/`.

### 4. Generate FreeR flags (explicit only)
FreeR generation is a deliberate, explicit step — never a side-effect of refinement.

```bash
bash scripts/run_ccp4.sh --dry-run --stdin <(printf 'END\n') -- \
  freerflag HKLIN data.mtz HKLOUT data_with_free.mtz
```

## MTZ preflight checklist (`scripts/mtz_preflight.py`)
Run before any wrapper that consumes an MTZ. It checks:
- file exists and is readable;
- required labels for the requested workflow exist (`refmac5`, `phaser`, `buccaneer`, `nautilus`);
- a usable FreeR column for refinement;
- F/SIGF or I/SIGI labels are unambiguous;
- HL or PHI/FOM phase columns for autobuild workflows.

It prefers `gemmi` (structured parser) and falls back to `mtzdump` text parsing.

## Known failure modes
- **CCP4 setup not sourced** — every binary 404s; `check_env.sh` probes versioned paths under `/Applications/ccp4-*/`, `/opt/xtal/ccp4-*/`, and `$HOME/ccp4-*/`.
- **FreeR missing or wrong type** — refinement looks fine but R-free is meaningless; preflight + `run_refmac5.sh` refuse to run.
- **Ambiguous column labels** — multiple `F/SIGF` candidates → wrapper requires explicit `--labin`.
- **Wrong binary names** — Buccaneer is `cbuccaneer`, Nautilus is `cnautilus`; bare `buccaneer`/`nautilus` are not CCP4 CLI binaries.
- **Custom monomer library collisions** — AceDRG happily creates a CIF for a residue code that already exists in `$CLIBD_MON`; downstream tools may load the wrong restraints. Preflight warns.
- **MTZ/PDB cell or space-group mismatch** — preflight compares cell + symmetry when both are supplied.
- **Implicit FreeR generation across tools** — never let a refinement wrapper run `freerflag` for you. Generate flags once, on purpose, and reuse them.

## Deep dives
- `references/install.md` — CCP4 setup script discovery, env vars, and fix guidance.
- `references/refmac5.md` — `run_refmac5.sh` interface, presets, TLS, jelly-body, and Refmac keyword reference pointers.
- `references/mtz_columns.md` — column labels and FreeR conventions; how to read `mtzdump` / `gemmi mtz` output.
- `references/ligands.md` — AceDRG input modes, residue-code rules, and the Servalcat/refmacat boundary.
- `references/boundaries.md` — what this skill owns vs `phenix`, `coot`, `chimerax`, and `structural-strategy`; deferred CCP4 binaries.
- `presets/refmac5_xray_default.com`, `presets/refmac5_xray_jellybody.com`, `presets/refmac5_tls.com` — Refmac5 keyword templates.
- `presets/acedrg_default.txt` — AceDRG default option set.

## Lessons
See `lessons.md`.
