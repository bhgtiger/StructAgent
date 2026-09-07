# Merizo domain segmentation handoff

Source review **2026-09-07**, not a live run. The latest
[release](https://github.com/psipred/Merizo/releases/tag/v1.0.0) is v1.0.0
(2023-10-13). The following details refer to inspected main
[41d12fb](https://github.com/psipred/Merizo/blob/41d12fb84e6e8fdb586c2c859d12161dc7bb5bfd/predict.py),
not automatically to that older tag. Resolve the target's installed revision
and help before constructing a command.

The [README examples](https://github.com/psipred/Merizo/blob/41d12fb84e6e8fdb586c2c859d12161dc7bb5bfd/README.md)
cover standard and iterative segmentation. Use them with these handoff checks:

- The input parser expects PDB and selects chain A by default. Set/check the
  actual protein chain through --pdb_chain; preserve the original chain and
  residue mapping during format conversion. Protein-domain segmentation is not
  nucleic-acid segmentation.
- Iteration is useful for long/AlphaFold models. Current implementation
  resegments domains larger than 200 residues when its iteration path is
  entered; the copied help says “under” that threshold. Consult source when
  help and behavior conflict. No generic confidence threshold proves a domain
  boundary is physically correct.
- --plddt_filter consumes a numeric value and reads the PDB B-factor field.
  Do not copy the README example that omits its value, and do not interpret
  experimental displacement parameters as AlphaFold confidence.
- In the summary, commas separate domains and underscores join discontinuous
  parts of one domain. Preserve that grouping. Saved .pdb2 files encode domain
  indices in occupancy and retain B-factors; index zero is a non-domain region.

Validate residue coverage and original numbering before fitting domain copies.
Inspect proposed boundaries against density and connectivity. A non-domain
assignment alone does not justify deleting residues. Transfer fitted transforms
back to the complete model, retain a new output filename, and inspect linkers
before flexible fitting.
