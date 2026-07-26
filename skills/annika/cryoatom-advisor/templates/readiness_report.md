# CryoAtom readiness report — template

Status: informational draft only. It grants no installation, download, execution, upload, output write, or configuration change.

## Request

- Intended use:
- Requested CryoAtom version:
- Evidence scope: static source inspection / official documentation / paper context

## Version and evidence

- Static implementation pin: CryoAtom2 v2.1.0, commit 10fd7f4be3722d6a1ea6646c69e93476014184ab.
- Runtime verification for this request: not performed.
- v1 evidence: peer-reviewed, protein-focused.
- v2 protein/RNA/DNA evidence: unpinned, unreviewed preprint.

## Host readiness

- OS and architecture:
- Linux/CUDA 11.8/Python 3.9/PyTorch 2.1.0 requirement met? [yes/no/unknown]
- GPU memory at least 14 GB and supported NVIDIA runtime? [yes/no/unknown]
- Conda, nvcc, and NVIDIA runtime present? [yes/no/unknown]
- Verdict: supported / not supported / not yet verified

## Data and output boundary

- Map/FASTA/backbone description only; no file transfer:
- Fresh, isolated disposable output location approved for a future job? [yes/no]
- Weight/dependency licenses reviewed? [yes/no]
- Outbound network/privacy reviewed? [yes/no]
- Cloud/upload proposed? [must be no for this advisor]

## Gates before any execution

1. Explicit user authorization for a new execution job.
2. Supported Linux/NVIDIA host and exact tagged version.
3. Approved public fixture and output-isolation plan.
4. License and privacy/network audit.
5. Human review of a command plan outside this skill.