# Inputs, planning, execution, and outputs

## Release and tutorial guidance — checked 2026-09-07

[ColabFold 1.6.2](https://github.com/sokrypton/ColabFold/releases/tag/v1.6.2)
adds optional `--use-pallas` Evoformer kernels for NVIDIA compute capability
8.0+ and `--compile-mode` (`fast`, default `tuned`, `full`).
For repeated or long predictions, establish the actual GPU/JAX combination and
inspect live help before choosing them. Compare startup/compile time separately
from prediction time on a representative approved fixture; published speedups
are not host guarantees. This release also fixes paired/unpaired local-search
crashes on complexes, so record the search version before diagnosing that error.

The [stable README](https://github.com/sokrypton/ColabFold/blob/v1.6.2/README.md)
now explains `JAX_COMPILATION_CACHE_DIR` and shape grouping. For repeated jobs,
use a writable persistent cache and record GPU, driver, JAX and input shapes;
changed shapes or software can require recompilation. Choose the local-search,
GPU-search or remote-MSA tutorial according to database availability and the
approved data destination. A local A3M still needs a separate template-network
check.

The [current README](https://github.com/sokrypton/ColabFold/blob/c35de0221f4d297a39edf4cf292ba2832e321edc/README.md)
also links an
[AlphaFold3/OpenFold3 notebook](https://github.com/sokrypton/ColabFold/blob/c35de0221f4d297a39edf4cf292ba2832e321edc/AlphaFold3_of3.ipynb).
For that request, inspect the notebook's backend, dependencies, inputs and
network actions in a separate workflow; do not translate its settings into
AF2 `colabfold_batch` flags or claim AF3 inference is validated here.
Existing AF3 JSON/MSA export examples also do not establish AF3 inference.

## Inputs

ColabFold v1.6.2 accepts FASTA/FA/FAA, A3M, CSV/TSV with required `id` and `sequence` plus optional alignment/template paths, and directories of supported inputs. PDB/mmCIF-derived chain sequences may be accepted by source workflows. Confirm exact behavior from captured live help/source before relying on less common forms.

Use colon-separated protein sequences to describe chains in a protein complex. Keep ligands, nucleic acids, CCD/SMILES, and AlphaFold3 JSON outside this AlphaFold2 workflow.

## MSA route

- Remote MMseqs modes can send sequence data to the configured host URL.
- `single_sequence` avoids remote MSA generation but removes evolutionary information.
- A supplied A3M avoids MSA generation, but `--templates` can still query a server.
- Local `colabfold_search` needs prepared MMseqs2 databases plus substantial disk/RAM.

State the chosen route, data destination, confidentiality decision, and likely scientific tradeoff before presenting a command.

## Command plan checklist

Include the configured launcher/version, input type, monomer/complex classification, MSA and template route, model type and validation scope, parameter/cache path, result directory, scheduler/GPU resources, expected network/download behavior, risky flags excluded, and a NOT-RUN label until the user approves.

A minimal shape is:

```text
<launcher> <input> <fresh-results-dir> \
  --model-type <captured-live-help value> \
  --msa-mode <approved mode>
```

Do not invent flags. Capture `colabfold_batch --help` on the configured runtime when exact syntax/defaults matter.

## Execution

Use the active project's provenance convention. Preserve the input hash, config snapshot, exact command/job script, stdout/stderr, scheduler receipt, runtime/container/weight version, and result manifest. Submit exactly one approved job. Do not reuse a result directory silently.

For Slurm, use the site config's partition, GRES, time, launcher, and required environment/module wrapper. Never transplant one cluster's directives to another.

## Expected result families

Depending on options/model/version, expect `config.json`, `cite.bibtex`, job A3M, unrelaxed/relaxed structures, score JSON, PAE JSON/plots, pLDDT plots, and coverage plots. Treat the actual tree as authority and report missing/extra files. Score JSON commonly contains pLDDT, PAE, max PAE, pTM, ipTM, and optional metrics, but fields vary.

Use `scripts/summarize_colabfold_output.py` for a read-only inventory and metric summary. Preserve original JSON/PDB files for audit.
