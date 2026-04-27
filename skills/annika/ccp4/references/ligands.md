# Ligand restraints with AceDRG

## Wrapper interface (`scripts/run_acedrg.sh`)

```bash
bash scripts/run_acedrg.sh [--dry-run] [--force] \
  --resname LIG \
  --out-prefix LIG \
  ( --smiles "CC(=O)O" | --smiles-file ligand.smi | --mol ligand.mol | --mmcif ligand.cif )
```

Required:

- exactly one input mode (`--smiles`, `--smiles-file`, `--mol`, `--mmcif`);
- `--resname` (1–3 uppercase alphanumeric characters);
- `--out-prefix` (used for AceDRG's output file basename).

The wrapper:

- sources the CCP4 setup;
- validates the residue code regex `^[A-Z0-9]{1,3}$`;
- checks `$CLIBD_MON` for an existing monomer with the same code; if found, prints a `[WARN]` with the existing path and refuses to overwrite outputs unless `--force`;
- calls `acedrg` with the chosen input mode;
- writes everything (resolved command, input file copy, stdout, stderr, generated `.cif` and `.pdb`) into `ccp4_runs/acedrg_<timestamp>/`.

## Residue-code rules

- 1–3 characters, uppercase letters and digits only — this matches both PDB and mmCIF conventions.
- The four-character mmCIF-only codes (e.g. `A1ABC`) are deliberately **not** supported in v1: they require explicit mmCIF output and are easy to misuse with downstream tools that still expect three-letter codes. If a user needs a 4-letter code, run `acedrg` directly through `run_ccp4.sh` and own the consequences.
- Codes already present in `$CLIBD_MON` (e.g. `ATP`, `NAD`, `HEM`) are a hazard: AceDRG will happily produce a CIF with the same code, and downstream tools may load whichever the search path finds first. The wrapper warns; the user picks a unique code if needed.

## Charge and protonation

AceDRG infers protonation and charge from the input. The wrapper records the input file (or SMILES string) verbatim in the run directory so the assumption is auditable. If the user has strong opinions on tautomer or charge state, they should preprocess with their tool of choice (RDKit, OpenBabel, …) and pass `--mol` / `--mmcif` rather than trying to coax SMILES into the right state.

## Using the restraint with Refmac5

```bash
bash scripts/run_refmac5.sh --dry-run \
  --xyzin model.pdb --hklin data.mtz \
  --xyzout out.pdb --hklout out.mtz \
  --preset xray_default \
  --labin "FP=F SIGFP=SIGF FREE=FreeR_flag" \
  --libin ccp4_runs/acedrg_<timestamp>/LIG.cif
```

If the residue code in `model.pdb` does not match `--resname`, Refmac will abort. That is the correct behaviour; do not edit the PDB to make it match without understanding why they diverged.

## Boundary

Phenix's `phenix.elbow` solves the same problem and lives in the `phenix` skill. Choosing between AceDRG and eLBOW is a strategy question — `structural-strategy/references/refinement.md` is the right place for the decision tree. This skill only executes AceDRG when the user asks for it explicitly.

## Upstream documentation

- AceDRG task reference: <https://cloud.ccp4.ac.uk/manuals/html-taskref/doc.task.MakeLigand.html>
- CCP4 monomer library notes: <https://www.ccp4.ac.uk/html/>
