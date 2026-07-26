# Version and environment boundary

## Pin

Static CLI, output, and default-configuration claims in this skill are pinned to CryoAtom2 v2.1.0 commit 10fd7f4be3722d6a1ea6646c69e93476014184ab. Current master reports v2.1.1 but is unreleased and changes acquisition behavior. Do not blend them.

## Scientific version distinction

- CryoAtom v1: peer-reviewed, protein-focused method evidence.
- CryoAtom2: protein, RNA, DNA, and protein-nucleic-acid claims from an unpinned, unreviewed preprint.

Never call CryoAtom2 RNA/DNA claims peer reviewed, and do not transfer a v1 result or limitation to a specific v2.1.0 runtime claim.

## Documented environment

The released v2.1.0 environment is Linux-oriented and specifies Python 3.9, CUDA 11.8, PyTorch 2.1.0, and at least 14 GB GPU memory for inference.

## Local Mac mini

The local Apple Silicon macOS machine has no Conda, nvcc, or NVIDIA runtime. It is not a validated CryoAtom execution platform. Docker presence or unified memory does not establish support.

## Required next gate

A later execution phase needs a specifically approved Linux/NVIDIA host, exact release, public fixture, output-isolation protocol, and license/privacy review.