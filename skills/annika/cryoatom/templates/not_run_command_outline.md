# NOT-RUN command outline — any host that is not `ready`

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
DO NOT EXECUTE — planning shape only
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Use this whenever the site config reports `probed`, `stale`, `blocked`, or
`unknown`** — including when there is no config at all. For a `ready` host use
`run_command_plan.md`, which produces real, runnable commands after
confirmation.

Flag names below are verified against CryoAtom2 2.1.1 commit
`856e250df7b784b854b892f1b619d32d51188cef`. Nothing else about this command is
tested on the target machine: not the dependency stack, not the weights, not the
GPU, not the runtime. Bracketed pieces are illustrative placeholders, not shell
syntax to copy.

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

## Must be true before any execution on that machine

- A supported Linux/NVIDIA/CUDA host with **≥14 GiB VRAM** has been verified —
  not assumed from Docker presence, unified memory, or the source's `--device
  cpu` path.
- The exact commit is pinned. No repository tag names the 2.1.1 code, so a tag
  is not a sufficient pin.
- All six weight files (`RUNet.pth`, `CryoNet.pth`, `CryoNet_no_seq.pth`,
  `RNA-FM_pretrained.pth`, `esm2_t33_650M_UR50D.pt`, and its
  contact-regression file) are staged and integrity-checked. ESM-2 and RNA-FM
  load **unconditionally**, including in the no-sequence path.
- Weights were fetched over **verified TLS**. Upstream's
  `wget --no-check-certificate` must not be copied.
- Weight/dependency licenses and network/privacy behaviour are reviewed. The
  repository is MIT; the weight licenses are separate and were not established.
- A public disposable fixture run has succeeded on that machine.
- The output path is fresh and isolated; no existing result directory is reused.
- Every input and output path is visible to the runtime (container binds).
- Any `--config-path` change has fixture-based justification.
- The user understands the output confidence field is not experimental truth.

Which of these is missing is exactly what the probe's `reasons` list says. Quote
it rather than guessing.

This template does not authorise replacing the placeholders, running a command,
or creating a directory. To move the machine towards `ready`, go to
`references/02_install_routes.md` and `templates/install_plan.md`.
