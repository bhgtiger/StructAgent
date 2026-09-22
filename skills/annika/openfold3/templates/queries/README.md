# Example queries (OpenFold3 v0.5.0 JSON)

Small public examples written for this skill (not copies of the upstream `examples/` files). Every file passed
`scripts/make_query.py --validate` AND the installed v0.5.0 Pydantic model + structure builder + tokenizer on CPU (tokens
below = real tokenizer count); `precomputed_msa.json` passed after its placeholder was filled with a real MSA root.
Sequences and pocket residues were checked against the PDBe entries named below. Only `barnase_barstar_1brs.json` carries
inputs that went through GPU predictions (the same sequences as the validated 199-token 1BRS input, which used chain ids
`A1`/`B1`); the upstream examples of the other kinds (monomer, homomer, heteromer, protein–ligand by SMILES and CCD,
pocket, modified DNA, cyclic peptide) ran rc 0 in every mode on the validation site. Field reference:
`references/04_input_query_format.md`.

| File | Query key | Content (public source) | Tokens | Shows |
|---|---|---|---|---|
| `ubiquitin_monomer.json` | `ubiquitin_monomer` | human ubiquitin, 76 aa | 76 | minimal monomer; first smoke test |
| `barnase_barstar_1brs.json` | `barnase_barstar_1brs` | barnase 110 aa (chain A) + barstar 89 aa (chain D), PDB 1BRS | 199 | heterodimer; chain ids chosen to match the PDB entry |
| `homodimer.json` | `hiv1_protease_dimer` | HIV-1 protease 99 aa × 2, PDB 1HHP | 198 | homomer via `"chain_ids": ["A", "B"]` |
| `modified_residue_homodimer_3hvp.json` | `hiv1_protease_aba_3hvp` | HIV-1 protease with ABA at 67 and 95, PDB 3HVP | 218 | `non_canonical_residues` (each ABA = 6 tokens) |
| `protein_ligand_smiles.json` | `t4l_l99a_benzene` | T4 lysozyme L99A (PDB 181L) + benzene `c1ccccc1` | 170 | ligand by SMILES (output residue name `LIG0`) |
| `protein_ligand_pocket.json` | `t4l_l99a_benzene_pocket` | same + `pocket_constraint` on the 11 cavity residues PDBe lists for BNZ in 181L | 170 | pocket constraint (1-based sequence numbers) |
| `protein_ligand_ccd.json` | `hras_gtp_mg` | H-Ras 1–166 (PDB 5P21) + GTP + Mg²⁺ | 199 | ligand and ion by CCD code (5P21 itself holds the analogue GNP) |
| `protein_dna.json` | `engrailed_hd_dna_1hdd` | Engrailed homeodomain × 2 + 21-bp duplex (two strands), PDB 1HDD | 164 | protein–DNA, one `dna` chain per strand |
| `precomputed_msa.json` | `barnase_barstar_msa` | barnase + barstar with `<ABSOLUTE_MSA_ROOT>` placeholders | 199 | precomputed MSA directories (fill before use) |

Use:

```bash
# template — not run; run from the package root and add your kit/site flags
# (references/03_cli_reference.md, references/06_kit_modes_and_multigpu.md)
# absolute paths: required under the kit/apptainer route (its runscript cd's into the read-only image)
python3 scripts/make_query.py --validate templates/queries/ubiquitin_monomer.json
run_openfold predict --query-json "$PWD/templates/queries/ubiquitin_monomer.json" --output-dir <ABS_NEW_OUT_DIR> \
    --use-msa-server false --num-diffusion-samples 5
```

- `--use-msa-server false` keeps sequences on the host (query-only MSA, lower accuracy). The public ColabFold server
  (`--use-msa-server true`, the upstream default) sends the protein sequences off-site: public sequences like these are
  fine to send, unpublished ones need explicit approval.
- `precomputed_msa.json`: replace `<ABSOLUTE_MSA_ROOT>` with an absolute directory holding `barnase/` and `barstar/`,
  each with `.a3m`/`.sto` files named by main-MSA slot, e.g. `uniref90_hits.a3m` (query sequence first; slot names in
  `references/07_msa_templates_weights.md` §4). Validate with `make_query.py --validate` (fails while placeholders remain;
  `--no-path-check` checks everything else), then run with `--use-msa-server false` so the paths are not overwritten.
- Chain `description` strings are metadata only; they document the source inside the JSON (JSON has no comments).
- The query key becomes `<OUT_DIR>/<query key>/seed_<s>/…`; rename keys freely (letters, digits, `.`, `_`, `-`).
