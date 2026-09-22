# Lessons — openfold3 skill

Append things learned the hard way. Newest first. Keep each entry short: date, lesson (symptom → cause → fix), evidence
pointer to the owning reference. Never add host names, user names, accounts, partitions or local paths: this file ships
in the public package.

## 2026-09-22 — initial build (OpenFold3 v0.5.0 + OpenBind-0, kit `openfold3_ob0` @ `f4f62fa`; Slurm HPC site, A100-SXM4 40 GB + H100 94 GB)

- **2026-09-22** — v0.5.0 `predict` never downloads weights, although its `--help` says it "will attempt to download":
  a missing checkpoint raises `cowardly refusing to perform inference` (rc 1). Fetch first with
  `setup_openfold --config setup.json` or `run.sh install --weights DIR`, then check the sha256. Evidence:
  [03 §9 trap 4](references/03_cli_reference.md), [02 "Weights and CCD"](references/02_install_and_environment.md).
- **2026-09-22** — `setup_openfold --non-interactive` ignores `$OPENFOLD_CACHE` and fills `~/.openfold3`; in a `--config`
  JSON an omitted `param_directory` also falls back to `~/.openfold3`, so set both paths. It never writes `runner.yml`,
  but a `runner.yml` you place in `$OPENFOLD_CACHE` is deep-merged into every predict. Evidence:
  [03 §4](references/03_cli_reference.md), [02 "Weights and CCD"](references/02_install_and_environment.md).
- **2026-09-22** — Bare `run_openfold --help` depends on the host: on a GPU node the bundled `cutlass_library` takes over
  `--help` and prints only `--disable-cutlass-package-imports`. Capture `run_openfold predict --help`, on a CPU node of
  the same image. Evidence: [03 §9 trap 5](references/03_cli_reference.md) [live].
- **2026-09-22** — Booleans take a value (`--use-msa-server false`); a bare flag is rc 2. The kit accepts only the hyphen
  spelling (`run.sh pred --use_msa_server false` is rc 2), and upstream `--use_tf32` is underscore-only. Evidence:
  [03 §9 traps 1 and 3](references/03_cli_reference.md) [live].
- **2026-09-22** — The MSA server is ON unless `--use-msa-server false` is passed, in stock and kit alike. Only protein
  sequences are sent; query-level `use_msas: false` does not stop submission; template-hit PDB ids go to RCSB even with
  `--use-templates false`; in server mode an RNA chain without MSA files gets no MSA features. Evidence:
  [07 §2](references/07_msa_templates_weights.md) [source].
- **2026-09-22** — An exported `OPENFOLD3_OB0_OPT` arms the kit inside a plain `run_openfold predict`, so a "stock"
  baseline silently becomes a kit run; a `--mode` that disagrees with it is rc 2. `unset OPENFOLD3_OB0_OPT` before every
  kit or baseline call. Evidence: [03 §9 traps 9–10](references/03_cli_reference.md), [06 §9](references/06_kit_modes_and_multigpu.md) [live].
- **2026-09-22** — `exact --det 1` equals `off --det 1` byte for byte (60/60 model/confidence file pairs at 13 and 508
  polymer residues, both cards); ordinary `exact` does not. Use `--det 1` for audits, not throughput. Evidence:
  [09 "Measured on one site"](references/09_validation_and_benchmarks.md), [06 §3](references/06_kit_modes_and_multigpu.md) [measured].
- **2026-09-22** — `fast` fidelity is not calibrated: top-model CA RMSD vs `off` reached 29.4 Å (A100) / 29.9 Å (H100) on
  low-confidence single-sequence inputs; on the H100 input the top ranking scores differed by only 0.003. Rank within
  one mode only; run the seed-spread check before trusting `fast`. Evidence: [09](references/09_validation_and_benchmarks.md),
  [08 "Interpretation guardrails"](references/08_outputs_and_confidence.md) [measured].
- **2026-09-22** — Stock rc 0 can hide failed queries: upstream catches OOM and per-query errors, logs them to
  `logs/predict_err_rank<r>.log` and counts them in `summary.txt`. The kit reports a short count as rc 1 `incomplete`;
  its verdict is the `exit rule ->` line, which is not the last stderr line (LEVER census lines follow). Check every
  tree with `scripts/summarize_openfold3_output.py`. Evidence: [10 triage](references/10_troubleshooting.md),
  [08 "Kit trees and the completeness rule"](references/08_outputs_and_confidence.md) [source, live].
- **2026-09-22** — `run.sh check` rc 0 with `gpu=none` on a CPU node is only a dry run of pins, weights and mode, and it is
  not side-effect free: it re-hashes the 2.3 GB checkpoint, rewrites `$XDG_CACHE_HOME/openfold3_ob0_opt/weights_digests.json`
  and may create a JIT root. Run it on the GPU node and tell the user. Evidence:
  [03 §6](references/03_cli_reference.md), [06 §7](references/06_kit_modes_and_multigpu.md) [live].
- **2026-09-22** — JIT caches held 668–1 013 files / 40–65 MB per job and the first `fast` call cost +22–39 s. Keep them
  node-local, never in an inode-limited home. Under `apptainer --cleanenv`, forward kit variables by prefix
  (`OPENFOLD3_OB0_OPT*`, `OF3TP_*`, `OF3O_*`, `MODEL_OPT_*`): a fixed forward list dropped 21 kit variables. Evidence:
  [02 Route 3](references/02_install_and_environment.md), [10 "Containers, paths and caches"](references/10_troubleshooting.md) [measured].
- **2026-09-22** — The kit Dockerfile builds DeepSpeed's DS4Sci op for sm_90 only; the validated site rebuilt it for
  `8.0;9.0` to serve A100 and H100 from one image. DS4Sci is off in the stock configuration and in every mode, and
  `exact`/`fast`/`big` override a DS4Sci runner-YAML key to off. Evidence:
  [02 "DS4Sci arch"](references/02_install_and_environment.md), [06 §10](references/06_kit_modes_and_multigpu.md) [source, live].

<!-- Pending Merge (from distill-session) goes below this line -->
