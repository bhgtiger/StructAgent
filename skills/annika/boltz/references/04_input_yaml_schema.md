# 04 — Input YAML Schema

Grounded in `docs/prediction.md` and `data/parse/schema.py` at v2.2.1. YAML is
preferred; FASTA is deprecated and can't express modifications, bonds, pocket
conditioning, or affinity.

## Top-level shape

```yaml
version: 1            # recommended
sequences:            # required: one entry per unique chain/molecule
  - protein: { ... }
  - dna: { ... }
  - rna: { ... }
  - ligand: { ... }
constraints:          # optional
  - bond: { ... }
  - pocket: { ... }
  - contact: { ... }
templates:            # optional (Boltz-2)
  - cif: ...
properties:           # optional (Boltz-2)
  - affinity: { binder: CHAIN_ID }
```

## Sequences

Each entry is one **unique** chain/molecule. Use a list `id: [A, B]` for multiple
identical copies.

**protein / dna / rna** — require `id` and `sequence`.
```yaml
- protein:
    id: A
    sequence: MVK...
    msa: ./path/seq.a3m       # protein only; see MSA rules below
    modifications:            # optional; protein/dna/rna
      - position: 5           # residue index, 1-based
        ccd: SEP              # CCD of the modified residue (CCD ligands only)
    cyclic: false             # optional; polymers only (not ligands)
```

**ligand** — require `id` and **exactly one** of `smiles` or `ccd` (not both).
```yaml
- ligand:
    id: L
    smiles: 'CC(=O)Oc1ccccc1C(=O)O'
# or
- ligand:
    id: L
    ccd: ATP
```

### MSA rules (protein only) — these are easy to get wrong

- **Auto MSA:** omit `msa` and run with `--use_msa_server` (posts the sequence to
  the ColabFold/MMseqs2 server — privacy!).
- **Custom MSA, single protein:** `msa: ./file.a3m`.
- **Custom MSA, multiple proteins:** use a **CSV** (not a3m) with columns
  `sequence` and `key`; rows sharing a `key` are mutually aligned (pairing).
- **Single-sequence mode:** `msa: empty` — Boltz prints a "predictions will be
  suboptimal" warning. Use only when you truly have no MSA.
- **You cannot mix** custom and auto-generated MSAs in the same input.

## Constraints (optional)

```yaml
constraints:
  - bond:                                   # covalent bond; CCD ligands & canonical residues only
      atom1: [CHAIN_ID, RES_IDX, ATOM_NAME] # RES_IDX 1-based (1 for a ligand); ATOM_NAME = standardized CIF name
      atom2: [CHAIN_ID, RES_IDX, ATOM_NAME]
  - pocket:                                 # Boltz-2
      binder: CHAIN_ID                      # the chain that binds (ligand/protein/NA)
      contacts: [[CHAIN_ID, RES_IDX_or_ATOM], ...]
      max_distance: 6                       # Å; default 6. Docs recommend 4–20, but this is NOT range-enforced in code
      force: false                          # true -> enforce via potential
  - contact:                                # Boltz-2
      token1: [CHAIN_ID, RES_IDX_or_ATOM]
      token2: [CHAIN_ID, RES_IDX_or_ATOM]
      max_distance: 6
      force: false
```

`RES_IDX_or_ATOM`: residue index for polymers, atom name for a ligand chain.

## Templates (optional, Boltz-2)

```yaml
templates:
  - cif: ./tmpl.cif                          # minimal: Boltz finds best-matching chains
  - cif: ./tmpl.cif
    chain_id: [A, B]                         # restrict which YAML chains use this template
    template_id: [X, Y]                      # optional explicit mapping to template chains
  - pdb: ./tmpl.pdb                          # PDB ok; subchains become A1,A2,B1,...
    chain_id: [A]
    force: true                              # enforce backbone via potential
    threshold: 5.0                           # REQUIRED when force: true (Å allowed deviation)
```

Rule: `force: true` **requires** `threshold`.

## Properties — affinity (optional, Boltz-2)

```yaml
properties:
  - affinity:
      binder: L          # the ligand chain id to score
```

Hard limits (enforced/warned in `schema.py`): exactly **one** ligand binder, must
be a **ligand** chain (not protein/DNA/RNA), single copy, single residue. The
size check is applied to the RDKit ligand after `RemoveHs` (effectively a
heavy-atom count): **>128 → rejected**, **>56 → reliability warning**. See
`06_affinity_workflow.md`.

## Worked example (complex + ligands)

```yaml
version: 1
sequences:
  - protein:
      id: [A, B]
      sequence: MVTPEGNVSLVDESLLVGVTDED...   # truncated
      msa: ./examples/msa/seq1.a3m
  - ligand:
      id: [C, D]
      ccd: SAH
  - ligand:
      id: [E, F]
      smiles: 'N[C@@H](Cc1ccc(O)cc1)C(=O)O'
```

## FASTA (deprecated)

`>CHAIN_ID|ENTITY_TYPE|MSA_PATH` then the sequence line. `ENTITY_TYPE` ∈
`protein|dna|rna|smiles|ccd`. `empty` MSA keyword = single-sequence. No
modifications, bonds, pocket, or affinity. Prefer YAML.
