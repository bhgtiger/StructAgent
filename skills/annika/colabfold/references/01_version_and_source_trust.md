# Version and source trust

Pinned target: sokrypton/ColabFold v1.6.2, commit c7d1772352cc9619df25c6d36cb0f218c0c6610e, released 2026-07-14.

At collection, main was one notebook/README commit ahead; core batch/input/search/utils modules and pyproject had no diff from the release tag.

Authority order:
1. installed v1.6.2 executable plus captured help and public fixture;
2. pinned source and package manifest;
3. official CI and README/wiki/release notes;
4. Mirdita et al. 2022 for rationale/historical evidence;
5. issue tracker for dated failure signals.

v1.6.2 highlights: fixes paired/unpaired complex-search crash, adds use-pallas and compile-mode, removes TensorFlow, and improves CUDA 12/13 plus ARM64 Docker. Do not transplant those options to older releases.