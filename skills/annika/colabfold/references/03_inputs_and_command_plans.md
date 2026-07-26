# Inputs and unexecuted command plans

Current source parses:
- FASTA, FA, FAA: each record is a job;
- A3M: uses the supplied alignment;
- CSV/TSV: required id and sequence, optional a3mpath and templatepath;
- PDB/mmCIF: derive protein chains and may be used as an initial guess;
- directories: FASTA/A3M/PDB/mmCIF-like files, with a source caveat that FASTA-like files in a directory use only their first record.

For protein complexes, colon-separated protein sequences denote chains. Do not claim ligand, DNA, RNA, CCD, or SMILES support for the v0 AlphaFold2 workflow; source documents these under AF3 JSON conversion, which is out of scope.

A safe plan labels itself NOT RUN and includes:
1. v1.6.2 source baseline;
2. input form and monomer/complex classification;
3. MSA route and whether it would transmit sequence data;
4. model/parameter rationale without certainty claims;
5. expected result directory and compute prerequisites;
6. explicit statement that no command has been run.

Never include overwrite-existing-results. Never add zip without explaining that source deletes most original result files after successful archive creation.