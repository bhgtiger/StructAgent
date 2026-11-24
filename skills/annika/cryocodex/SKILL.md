---
name: cryocodex
description: "Config-first assistant for CryoCodex (YangLab-SDU/CryoCodex v1.0.0, ./predict.sh): one network that turns a single cryo-EM map into an enhanced map, local-quality score maps for the input and the enhanced map, and a binary molecular mask. Use to install, configure, understand, plan or run CryoCodex: correct predict.sh commands (fast vs normal mode, True/False option values, -b/-s/-g, --keep_size, --reverse_interpolation, --crop_check), map-header checks, what the four outputs mean (predicted local SSIM, not local resolution; 1 A output grid), weights download and integrity, Slurm/GPU selection, troubleshooting, the Colab privacy caveat, or refreshing this skill. SOURCED from the pinned code and preprint, NOT yet validated on any host. Probes first; installs, the 471 MB weights download and GPU jobs need confirmation. Triggers: cryocodex, CryoCodex, predict.sh -i -o, cryocodex_in_score, cryocodex_in_mask, map enhancement with local quality and mask."
---

# CryoCodex

CryoCodex (Cheng, Su & Yang, Shandong University; repo `YangLab-SDU/CryoCodex`, code MIT) is a 3D U-Net with a
multi-scale vector-quantised codebook that post-processes **one** cryo-EM map in a single pass and writes four maps:
an enhanced map, a local-quality score map of the input, one of the enhanced map, and a binary molecular mask. It is
a shell launcher `./predict.sh` inside a git clone that runs `predict.py` through `conda run`; there is no PyPI or
conda package and no training code.

## Status of this skill — read first

Source review **2026-11-24**: pinned to tag `v1.0.0` = commit `a35e73a72f9cbc2b13cf6f8d95cf963cb704ca17` (= `main` on
that date), weights `CryoCodex.pth` 470,938,660 B (no published checksum), bioRxiv preprint v1 (not peer reviewed).
**Nothing here has been run on a real install yet.** Every command and expected output is *sourced* (code at the pin,
README, preprint), not *validated*. The first host that runs [references/validation_runbook.md](references/validation_runbook.md)
turns facts into VALIDATED; until then say "per the source code" and never "verified". Refresh procedure:
[references/maintenance.md](references/maintenance.md).

## The one rule: probe before you act

The machine running this agent is not assumed to be the CryoCodex runtime (CUDA GPU on Linux).

```bash
python3 scripts/cryocodex_env_probe.py --home /abs/path/to/CryoCodex            # read-only, stdlib, no downloads
python3 scripts/cryocodex_env_probe.py --home /abs/path/to/CryoCodex --env-check --json   # also imports torch inside the env
python3 scripts/cryocodex_env_probe.py --home /abs/path/to/CryoCodex --hash      # ask first: reads the 471 MB checkpoint
```

| State | Meaning | You MAY | You MUST NOT |
|---|---|---|---|
| **UNCONFIGURED** | no probe this session | explain; inspect map headers (`scripts/inspect_map.py`); draft commands labelled `# template — not run` | say a machine can run it; run `predict.sh` (except `-h`); install or download |
| **PROBED** | fresh probe of this host (verdict `READY_TO_VALIDATE`, `PARTIAL`, `NOT_INSTALLED` or `BLOCKED`) | real paths in commands; readiness verdict; install plan; `./predict.sh -h` and `-h advanced` | run inference or trigger the weights download before the user confirms that exact action |
| **VALIDATED** | the runbook's fixture run passed on this host and is recorded in `configs/site_config.local.md` | after per-job confirmation, run jobs with safeguards (fresh `-o`, absolute paths, log file, rc, `scripts/check_outputs.py`) | claim behaviour beyond what was run there |

The probe never prints VALIDATED. A verdict goes stale when the host, GPU/driver, env, clone commit or weights change.
Site config: copy [configs/site_config.template.md](configs/site_config.template.md) to `configs/site_config.local.md`
(git-ignored) and fill it from the probe and the runbook.

## Hard safety rails

- **Boolean options need a value.** `--normal`, `--reverse_interpolation`, `--keep_size`, `--crop_check`, `--no_logo`
  take `True` or `False` (`parse_bool`, `predict.py:37-43`); a bare `--normal` is an argparse error. Emit the README
  spelling with `True`/`False`.
- **`--version` is not harmless.** `predict.sh` answers only `-h` before its checks; `--version`, every run, and every run
  that later fails argparse first **download 471 MB of weights** if `model_state_dicts/CryoCodex.pth` is missing
  (`predict.sh:50-94`). Warn before the first call, or have the user place the checkpoint deliberately.
- **`--crop_check True` is interactive only.** It blocks on terminal input with no timeout and raises
  `RuntimeError: Crop inspection needs terminal input.` on EOF (`crop_check.py:415-450`). Never put it in Slurm, `nohup`,
  cron or scripted runs. It and `--keep_size True` are fast-mode only (`--normal True` → `parser.error`, `predict.py:189-192`).
- **CUDA only, first visible device.** Compute is `torch.device("cuda:0")`; `-g` just writes its value into
  `CUDA_VISIBLE_DEVICES`, overwriting what a scheduler set (`predict.py:82`, `:194`). No CPU, Apple-Silicon or multi-GPU
  path. Under Slurm pass `-g "${CUDA_VISIBLE_DEVICES:-0}"` (derived from the code, not yet observed — runbook R16).
- **Weights are unverified pickles.** No checksum is published; `predict.sh` only tests "non-empty"; `predict.py` loads
  with `torch.load(..., weights_only=False)` (`predict.py:47`), i.e. code inside the file would run. Record the SHA-256
  after the first download (probe `--hash`) and compare across hosts; the runbook (R8) test-loads with `weights_only=True`.
- **Outputs are on a 1.0 Å grid by default**, cropped to the molecule in fast mode. `--keep_size True` refills to the
  *1 Å regridded* box (equals the input box only for 1 Å inputs); `--reverse_interpolation True` resamples back to the
  input voxel size (`predict.py:116-144`). Placement is stored in NXSTART/NYSTART/NZSTART with header ORIGIN = 0.
- **Score maps are predicted local SSIM** against a model-simulated map, negatives clipped to 0, no upper clamp (can
  exceed 1 after resampling) — **not local resolution, FSC or Q-score**. The saved mask is **binary** (≥ 0.5).
- **Input names**: the path must end in lower-case `mrc` or `map` (`grid_utils.py:215`); `.ccp4`, `.MRC`, `.mrc.gz`
  are rejected — rename/decompress. Non-orthogonal cells print `# Input grid is not orthogonal. EXIT.` and stop
  without outputs, probably with exit status 0 (bare `exit()`): judge a run by `scripts/check_outputs.py`, not its rc.
- **Stride 1–44.** Each 48³ window contributes only its inner 44³, so `-s` > 44 leaves zero gaps (code reading;
  notebook and Scipion allow ≤ 48). `-b` ≥ 1; lower `-b` for small GPUs. Existing outputs with the same `-n` are
  overwritten silently: use a fresh `-o`.
- **Privacy.** The CLI's only network call is the weights download. The README's Colab "Online inference" uploads the
  user's map to a Google Colab VM: never suggest it for unpublished or proprietary maps.
- **Weights terms are unpublished.** Code is MIT; nothing states terms for `CryoCodex.pth`. Say "no terms published";
  never call the weights MIT, free for commercial use, or redistributable.
- **Ask before every install, the weights download and every GPU job**, one at a time.

## Reference routing

| You need to… | Read |
|---|---|
| Scope, trust ladder, claims never to make, licences | [references/00_scope_and_trust.md](references/00_scope_and_trust.md) |
| Pins (commit, weights, paper), how to cite, where the evidence pack is | [references/01_source_map.md](references/01_source_map.md) |
| Probe states, install route, env vars, weights placement, platform limits | [references/02_config_session_and_environment.md](references/02_config_session_and_environment.md) |
| Every option, default, alias, allowlist / never-emit list, launcher behaviour, messages | [references/03_cli_reference.md](references/03_cli_reference.md) |
| Input acceptance, resampling, normalisation, crop, tiling, the four outputs and their headers | [references/04_data_model_and_formats.md](references/04_data_model_and_formats.md) |
| Standard runs, sizing, Slurm, provenance, what to show the user before a job | [references/05_core_workflows.md](references/05_core_workflows.md) |
| ChimeraX colouring, using the mask/scores elsewhere, Scipion plugin (deferred), Colab | [references/06_interoperability.md](references/06_interoperability.md) |
| Egress, pickled weights, licences, privacy wording | [references/07_safety_license_privacy.md](references/07_safety_license_privacy.md) |
| Paper claims, training data, benchmarks, what results do and do not mean | [references/08_validation_and_benchmarks.md](references/08_validation_and_benchmarks.md) |
| Symptom → cause → fix | [references/09_troubleshooting.md](references/09_troubleshooting.md) |
| Quick choices: mode, flags, batch size, which map to feed, when not to use it | [references/10_decision_trees.md](references/10_decision_trees.md) |
| First validation on a GPU host (copy-pasteable steps R0–R20) | [references/validation_runbook.md](references/validation_runbook.md) |
| Refresh from upstream | [references/maintenance.md](references/maintenance.md) |

## Quick orientation

```bash
# template — not run. Install exactly as the README (from inside the clone; ~1 GB of wheels):
git clone https://github.com/YangLab-SDU/CryoCodex.git && cd CryoCodex && git checkout v1.0.0
conda create -y -n cryocodex_env python=3.11
conda run --no-capture-output -n cryocodex_env python -m pip install -r requirements.txt
chmod +x predict.sh

# template — not run. Default fast mode, outputs on the 1 A grid (first run downloads 471 MB of weights):
/abs/CryoCodex/predict.sh -i /abs/map.mrc -o /abs/out_cryocodex_run1
# outputs on the input voxel size, ~ the input box (each axis may differ by rounding):
/abs/CryoCodex/predict.sh -i /abs/map.mrc -o /abs/out_run2 --reverse_interpolation True --keep_size True
# smaller GPU:
/abs/CryoCodex/predict.sh -i /abs/map.mrc -o /abs/out_run3 -b 4
```

`scripts/build_cryocodex_command.py` writes these and refuses the traps above. Outputs in `-o`: `cryocodex.mrc`
(enhanced), `cryocodex_out_score.mrc`, `cryocodex_in_score.mrc`, `cryocodex_in_mask.mrc` (prefix = `-n`), float32.

**Before a run**: `python3 scripts/inspect_map.py /abs/map.mrc` (name/extension gate, orthogonal cell, voxel size,
1 Å regridded box, window count and host-RAM estimate). **After**: `python3 scripts/check_outputs.py /abs/out --input
/abs/map.mrc [--keep-size] [--reverse-interpolation] [--stats]` (four files, same grid, expected voxel size and box,
placement, mask binary, score range).

## Scripts and templates

All scripts are stdlib Python ≥ 3.9, print `--help`, and write nothing unless asked.

- `scripts/cryocodex_env_probe.py` — read-only host probe and verdict (OS/arch, GPU, conda, env, clone commit, weights size/hash).
- `scripts/inspect_map.py` — MRC header inspector + CryoCodex geometry (gates, 1 Å box, windows, RAM estimate).
- `scripts/build_cryocodex_command.py` — correct `predict.sh` command builder; refuses the traps; `--slurm` uses the scheduler GPU.
- `scripts/check_outputs.py` — post-run completeness, header and (opt-in) value checks of the four outputs.
- `scripts/mrcheader.py` — shared stdlib MRC header reader and geometry rules (imported by the scripts above).
- `templates/run_plan.md` — what to show the user before a job; `templates/slurm_cryocodex.sbatch.template` — guarded one-GPU job.
- `tests/validate_static.py` — offline self-test (allowlist, geometry, synthetic maps, Slurm job against fakes, probe
  verdicts); `tests/trigger_tests.md` — manual trigger/behaviour evals.

## House notes

- Works under Claude Code and Codex (`agents/openai.yaml`). Record hard-won lessons in [lessons.md](lessons.md);
  preserve `lessons.md` and `configs/site_config.local.md` when updating.
- Independent, unofficial resource; not affiliated with the CryoCodex authors. Ships no CryoCodex code or weights.
  Cite the preprint per [01](references/01_source_map.md).
- Take flags only from [03](references/03_cli_reference.md). Anything else is **[unverified]**.
