# NOT-RUN command outline

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
DO NOT EXECUTE — planning shape only
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Static source inspection only: CryoAtom2 v2.1.0 commit 10fd7f4be3722d6a1ea6646c69e93476014184ab. This is not a tested command. Bracketed pieces are illustrative placeholders, not shell syntax to copy.

~~~text
DO NOT EXECUTE

cryoatom build \
  --map-path <MAP_PATH> \
  [--protein-sequence-path <PROTEIN_FASTA>] \
  [--rna-sequence-path <RNA_FASTA>] \
  [--dna-sequence-path <DNA_FASTA>] \
  --output-dir <FRESH_ISOLATED_OUTPUT_DIR> \
  [--device <SUPPORTED_DEVICE>] \
  [--mask-path <MASK_MAP>] \
  [--protein-fasta-path <PROTEIN_FASTA_DATABASE>] \
  [--na-fasta-path <NA_FASTA_DATABASE>] \
  [--refine-backbone-path <BACKBONE_PDB_OR_MMCIF>] \
  [--keep-intermediate-results] \
  [--config-path <REVIEWED_JSON_CONFIG>]

DO NOT EXECUTE
~~~

## Must be true before a later human-approved execution job

- A supported Linux/NVIDIA/CUDA host has been verified.
- The exact tagged release and public disposable fixture are approved.
- Weight/dependency licenses and network/privacy behavior are reviewed.
- The output path is isolated and disposable; no existing result directory is reused.
- Any config change has fixture-based justification.
- The user understands that output confidence is not experimental truth.

This template does not authorize replacing placeholders, running a command, or creating a directory.