# Source map and evidence hierarchy

Pinned baseline: `sokrypton/ColabFold` v1.6.2, commit `c7d1772352cc9619df25c6d36cb0f218c0c6610e`, released 2026-07-14.

Release/docs checked **2026-09-07**: the explicit
[v1.6.2 release](https://github.com/sokrypton/ColabFold/releases/tag/v1.6.2)
and GitHub release API agree; a cached `/releases/latest` page returned v1.6.1.
Resolve such disagreements from dated direct release data.
Main `c35de0221f4d297a39edf4cf292ba2832e321edc` adds an OpenFold3 notebook,
which is separate from this pinned AF2 CLI. See [maintenance](maintenance.md)
for source discovery and [workflows](workflows.md) for version-specific guidance.

Prefer evidence in this order:

1. captured live executable help and a preserved public fixture on the configured host;
2. pinned v1.6.2 source and package manifest;
3. official CI, README, Wiki, and release notes;
4. Mirdita et al., Nature Methods 2022, for rationale and historical benchmarks;
5. dated upstream issue reports as failure signals, not universal fixes.

Official anchors:

- Repository: `https://github.com/sokrypton/ColabFold`
- Pinned source: `https://github.com/sokrypton/ColabFold/tree/c7d1772352cc9619df25c6d36cb0f218c0c6610e`
- Package/entry points: pinned `pyproject.toml`
- Batch CLI and execution flow: pinned `colabfold/batch.py`
- Input/output helpers: pinned `colabfold/input.py` and `colabfold/utils.py`
- MMseqs client/local search: pinned `colabfold/mmseqs/`
- Method paper: `https://doi.org/10.1038/s41592-022-01488-1`

Record the URL/commit, live help hash, runtime/container identity, and fixture receipt in the external workstation config. Do not ship private host evidence in the portable skill.
