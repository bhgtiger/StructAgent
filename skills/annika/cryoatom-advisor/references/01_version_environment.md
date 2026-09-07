# Version and environment boundary

## Pin

Static CLI, output, and default-configuration claims in this skill are pinned to CryoAtom2 v2.1.0 commit 10fd7f4be3722d6a1ea6646c69e93476014184ab.

Checked **2026-09-07**: [v2.1.0](https://github.com/YangLab-SDU/CryoAtom/releases/tag/v2.1.0),
released **2026-03-17**, remains the newest published release. Master
`856e250df7b784b854b892f1b619d32d51188cef` reports 2.1.1 without a release
tag and changes weight acquisition. Do not blend these pins. The release adds
multi-GPU inference and HMM-search fixes; this advisor has not tested those
features on a host. See [maintenance](maintenance.md).

## Scientific version distinction

- CryoAtom v1: peer-reviewed, protein-focused method evidence.
- CryoAtom2: protein, RNA, DNA, and protein-nucleic-acid claims from an unpinned, unreviewed preprint.

Never call CryoAtom2 RNA/DNA claims peer reviewed, and do not transfer a v1 result or limitation to a specific v2.1.0 runtime claim.

## Documented environment

The released v2.1.0 environment is Linux-oriented and specifies Python 3.9, CUDA 11.8, PyTorch 2.1.0, and at least 14 GB GPU memory for inference.

## Target environment

This portable advisor contains no facts about the current machine. Assess a
supplied target report against the pinned requirements. An Apple Silicon
machine is not a validated NVIDIA/CUDA execution target; Docker presence or
unified memory does not establish support. Do not infer whether Conda or other
software is installed from a historical workstation description.

## Required next gate

A later execution phase needs a specifically approved Linux/NVIDIA host, exact release, public fixture, output-isolation protocol, and license/privacy review.
