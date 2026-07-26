# Outputs and confidence

Source writes config.json and cite.bibtex plus job-specific A3M, unrelaxed PDB, score JSON, coverage, PAE, and pLDDT plot artifacts. Score JSON can contain pLDDT, PAE, max PAE, pTM, ipTM, and optional extra metrics, but fields vary by model/workflow.

pLDDT is written into the PDB B-factor column. It is model confidence, not an experimental B-factor. Explain that high pLDDT supports local structural confidence only; it does not prove global correctness, binding, an interaction, or biological state.

For complexes, direct the user to inter-chain PAE and interface-oriented metrics alongside independent evidence. Never generate a biological conclusion from a confidence threshold.

The zip option creates an archive and deletes most original outputs after success. Result-tree parsing is deferred until an installed v1.6.2 public fixture exists.