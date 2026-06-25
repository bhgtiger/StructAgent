# 08 — Validation and Benchmarks

## Talk about quality honestly

- Boltz-1/Boltz-2 report strong structure and (Boltz-2) affinity results in their
  preprints. Report those as **the authors' claims**, attributed (see
  `01_source_map.md`), not as independently verified guarantees.
- Boltz-2's training/evaluation pipelines are **incomplete upstream** ("coming
  soon"). Don't present a retraining/eval recipe as if it ships.
- Per-prediction quality is what matters operationally: trust the confidence
  fields and the structure, not the headline benchmark.

## What is validated for THIS skill

Captured live on `volta` (boltz 2.2.1, 2026-06-23):
- `boltz --help` / `boltz predict --help` (→ `03_cli_reference.md`).
- A no-MSA fixture (Trp-cage, `msa: empty`, `--output_format pdb`) ran on a
  RTX 2080 Ti (cc 7.5): **exit 0, kernels on, ~5 s inference**, producing the
  output tree and confidence fields in `07_outputs_and_confidence.md`.
- Confirms: kernels work on sm_75 here; the output tree and JSON fields match
  source; the single-sequence warning fires as documented.

This validates the CLI surface and the happy path on this host. It does **not**
validate large-complex behavior, the MSA server path, or affinity numerics — flag
those as needing their own check.

## Pre-execution checklist (before an execution-grade recommendation on a new host)

1. Capture live `boltz --help` and `boltz predict --help`.
2. Record boltz / Python / Torch / CUDA versions, GPU model + compute capability,
   cache path (use `scripts/boltz_env_probe.py --deep`).
3. Run a small fixture without the MSA server (`scripts/verify_boltz.py --fixture`).
4. If advising `--use_msa_server`, run one MSA-server fixture (network/auth).
5. Confirm the output tree + JSON field names on that host.
6. Test `--override` behavior.
7. Trigger one expected error (e.g., oversized affinity ligand) to confirm
   messaging.

## Cheap smoke test (any host)

```bash
python scripts/verify_boltz.py --env <prefix> --fixture
```
PASS = import + help + weights + a tiny prediction that writes a `.pdb`.
