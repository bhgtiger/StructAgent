---
name: cryocodex
description: "Config-first assistant for CryoCodex (YangLab-SDU/CryoCodex v1.0.0, ./predict.sh): one network that turns a single cryo-EM map into an enhanced map, local-quality score maps for the input and the enhanced map, and a binary molecular mask. Use to install, configure, understand, plan or run CryoCodex: correct predict.sh or site-launcher commands (fast vs normal mode, True/False values, -b/-s/-g, --keep_size, --reverse_interpolation, --crop_check), map-header checks, what the four outputs mean (predicted local SSIM, not local resolution; 1 A grid), weights download and sha256, Slurm/GPU selection, troubleshooting, Colab privacy, refreshing this skill. VALIDATED 2026-11-24 on a Linux Slurm cluster (README install and a shared launcher; the fixture reproduces the authors' result). Probes first; installs, the 471 MB weights download and GPU jobs need confirmation. Triggers: cryocodex, CryoCodex, predict.sh -i -o, cryocodex_in_score, cryocodex_in_mask, map enhancement with local quality and mask."
---

# CryoCodex

CryoCodex (Cheng, Su & Yang, Shandong University; repo `YangLab-SDU/CryoCodex`, code MIT) is a 3D U-Net with a
multi-scale vector-quantised codebook that post-processes **one** cryo-EM map in a single pass and writes four maps:
an enhanced map, a local-quality score map of the input, one of the enhanced map, and a binary molecular mask. It is
a shell launcher `./predict.sh` inside a git clone that runs `predict.py` through `conda run`; there is no PyPI or
conda package and no training code. Shared installs often wrap `predict.py` in a site launcher instead (02 §2b).

## Status of this skill — read first

Source review **2026-11-24**: pinned to tag `v1.0.0` = commit `a35e73a72f9cbc2b13cf6f8d95cf963cb704ca17` (= `main` on
that date), weights `CryoCodex.pth` 470,938,660 B, bioRxiv preprint v1 (not peer reviewed).

**First live validation 2026-11-24** on one Linux Slurm cluster (Ubuntu 24.04, NVIDIA drivers 595.99 and 580.178; RTX 2070 SUPER
8 GB and RTX 2080 Ti 11 GB nodes, one node without per-job GPU fencing): [references/validation_runbook.md](references/validation_runbook.md)
R0–R18 all PASS (R4 needed site workarounds: shared conda cache, user-site packages; R7 passed once the weights
server came back after a ~50-min outage), for
both the README route (`predict.sh` + `conda run`) and a shared site launcher (bit-identical outputs on the same GPU
model; float-level differences between GPU models). The fixture
EMD-10387 reproduces the authors' published result (Pearson 1.000). Weights sha256 recorded there:
`dfb814c63ed2dbdca99d0e3803e408d88775217a48d72a4fbb60618f8feda380` (not published by the authors).
What was observed is marked **verified** in the references; everything else (other GPUs, drivers and OSes, the
Scipion route, maps with both ORIGIN and NSTART non-zero, strides other than 12/46, batches > 9 on larger cards,
a human at `--crop_check`) stays *sourced*/*derived*. **A verdict does not transfer between hosts**: each new host is
probed, and becomes VALIDATED only after its own runbook fixture run. Refresh procedure:
[references/maintenance.md](references/maintenance.md).

## The one rule: probe before you act

The machine running this agent is not assumed to be the CryoCodex runtime (CUDA GPU on Linux).

```bash
python3 scripts/cryocodex_env_probe.py --home /abs/path/to/CryoCodex            # read-only, stdlib, no downloads
python3 scripts/cryocodex_env_probe.py --home /abs/path/to/CryoCodex --env-check --json   # also imports torch inside the env
python3 scripts/cryocodex_env_probe.py --home /abs/path/to/CryoCodex --hash      # ask first: reads the 471 MB checkpoint
# shared install with a site launcher and a prefix env (no predict.sh / conda run):
python3 scripts/cryocodex_env_probe.py --home /abs/CryoCodex --env-prefix /abs/envs/cryocodex --launcher /abs/cryocodex.sh --env-check
```

| State | Meaning | You MAY | You MUST NOT |
|---|---|---|---|
| **UNCONFIGURED** | no probe this session | explain; inspect map headers (`scripts/inspect_map.py`); draft commands labelled `# template — not run here` | say a machine can run it; run `predict.sh` (except `-h`); install or download |
| **PROBED** | fresh probe of this host (verdict `READY_TO_VALIDATE`, `PARTIAL`, `NOT_INSTALLED` or `BLOCKED`) | real paths in commands; readiness verdict; install plan; `./predict.sh -h` and `-h advanced` | run inference or trigger the weights download before the user confirms that exact action |
| **VALIDATED** | the runbook's fixture run passed on this host and is recorded in `configs/site_config.local.md` | after per-job confirmation, run jobs with safeguards (fresh `-o`, absolute paths, log file, rc, `scripts/check_outputs.py`) | claim behaviour beyond what was run there |

The probe never prints VALIDATED. A verdict goes stale when the host, GPU/driver, env, clone commit or weights change.
Site config: copy [configs/site_config.template.md](configs/site_config.template.md) to `configs/site_config.local.md`
(git-ignored) and fill it from the probe and the runbook.

## Hard safety rails

- **Boolean options need a value.** `--normal`, `--reverse_interpolation`, `--keep_size`, `--crop_check`, `--no_logo`
  take `True` or `False` (`parse_bool`, `predict.py:37-43`); a bare `--normal` is `error: argument --normal: expected
  one argument`, exit 2 (verified). Emit the README spelling with `True`/`False`.
- **`--version` is not harmless.** `predict.sh` answers only `-h` before its checks; `--version`, every run, and every run
  that later fails argparse first **download 471 MB of weights** if `model_state_dicts/CryoCodex.pth` is missing
  (`predict.sh:50-94`; verified: 53 s for the download on the validation host). If the lab server is unreachable
  (it was, for ~50 min) this takes ~7 min (3 × ~2 min connect timeouts) before `ERROR: Failed to download the model
  weights …`, exit 1 (verified). Warn first, or place the checkpoint.
- **`--crop_check True` is interactive only.** With stdin closed it raises `RuntimeError: Crop inspection needs terminal
  input.` (exit 1, `round_1_check/` PNGs left); with stdin open but silent it waits forever (both verified;
  `crop_check.py:415-450`). Never in Slurm, `nohup`, cron or scripted runs. It and `--keep_size True` are fast-mode only
  (`--normal True` → `parser.error`, exit 2).
- **CUDA only, first visible device; `-g` overrides the scheduler.** Compute is `cuda:0`; `-g` (default `"0"`) is written
  into `CUDA_VISIBLE_DEVICES` (`predict.py:82`, `:194`). Verified on a Slurm node without GPU fencing: allocated GPU 1,
  no `-g` → the run used **GPU 0** (another job's card); with `-g "${CUDA_VISIBLE_DEVICES:-0}"` → GPU 1. Always pass it
  under a scheduler (the Slurm template and a good site launcher do). No CPU, Apple-Silicon or multi-GPU path.
- **Keep the user site out (`PYTHONNOUSERSITE=1`).** Conda envs do not isolate `~/.local/lib/pythonX.Y/site-packages`.
  Observed: the README `pip install -r requirements.txt` **uninstalled numba, llvmlite and scipy from the user's
  `~/.local`** (packages other tools there relied on; restored by hand), and at run time `~/.local` numba/scipy
  shadowed the env's. Export
  `PYTHONNOUSERSITE=1` for the install and every run; the probe's `--env-check` reports shadowed packages.
- **Weights are unpickled.** No checksum is published; `predict.sh` only tests "non-empty"; `predict.py:47` loads with
  `torch.load(..., weights_only=False)`. Compare size (470,938,660 B) and sha256 (above; probe `--hash`); the runbook (R8)
  test-loads with `weights_only=True` (passes for the reference file; it also holds optimizer state).
- **Outputs are on a 1.0 Å grid by default**, cropped to the molecule in fast mode. `--keep_size True` refills to the
  *1 Å regridded* box (156³ for a 150³ map at 1.043 Å — verified); add `--reverse_interpolation True` for the input grid
  (150³ at 1.043 Å, verified). Placement is in NXSTART/NYSTART/NZSTART with header ORIGIN = 0.
- **Score maps are predicted local SSIM** against a model-simulated map, negatives clipped to 0, no upper clamp — after
  `--reverse_interpolation True` thousands of voxels exceed 1 (max 1.14 observed). **Not local resolution, FSC or
  Q-score.** The saved mask is **binary** (≥ 0.5).
- **Input names**: the path must end in lower-case `mrc` or `map` (`grid_utils.py:215`); `.ccp4`, `.MRC`, `.mrc.gz`
  are rejected (`.ccp4`, `.MRC`, `.map.gz` verified; `.mrc.gz` by the same rule) — rename/decompress. Non-orthogonal cells print `# Input grid is not orthogonal. EXIT.` and
  exit with **status 0 and no outputs** (verified): judge every run by `scripts/check_outputs.py`, not its rc.
- **Stride 1–44.** `-s 46` left all-zero planes inside the molecule (verified). `-b` ≥ 1; `-b 9` peaked at 7,328 MiB
  (7.2 GiB) of GPU memory on both test maps and `-b 18` ran out of memory on an 8 GB card (verified). Existing outputs with the same `-n`
  are overwritten silently: use a fresh `-o`.
- **Privacy.** With the weights in place a full run opened no network connection (verified with strace). The README's
  Colab "Online inference" uploads the user's map to a Google Colab VM: never suggest it for unpublished or proprietary maps.
- **Weights terms are unpublished.** Code is MIT; nothing states terms for `CryoCodex.pth`. Say "no terms published";
  never call the weights MIT, free for commercial use, or redistributable.
- **Ask before every install, the weights download and every GPU job**, one at a time.

## Reference routing

| You need to… | Read |
|---|---|
| Scope, trust ladder, claims never to make, licences | [references/00_scope_and_trust.md](references/00_scope_and_trust.md) |
| Pins (commit, weights + sha256, paper), what was verified live, how to cite | [references/01_source_map.md](references/01_source_map.md) |
| Probe states, README install, shared/site-launcher install, env vars, weights placement, measured resources | [references/02_config_session_and_environment.md](references/02_config_session_and_environment.md) |
| Every option, default, alias, allowlist / never-emit list, launcher behaviour, live help and messages | [references/03_cli_reference.md](references/03_cli_reference.md) |
| Input acceptance, resampling, normalisation, crop, tiling, the four outputs and their headers | [references/04_data_model_and_formats.md](references/04_data_model_and_formats.md) |
| Standard runs, measured sizing, Slurm, provenance, what to show the user before a job | [references/05_core_workflows.md](references/05_core_workflows.md) |
| ChimeraX colouring, using the mask/scores elsewhere, Scipion plugin (deferred), Colab | [references/06_interoperability.md](references/06_interoperability.md) |
| Egress, pickled weights, licences, privacy wording | [references/07_safety_license_privacy.md](references/07_safety_license_privacy.md) |
| Paper claims, training data, benchmarks, reproduction of a published result | [references/08_validation_and_benchmarks.md](references/08_validation_and_benchmarks.md) |
| Symptom → cause → fix (verified messages) | [references/09_troubleshooting.md](references/09_troubleshooting.md) |
| Quick choices: mode, flags, batch size, which map to feed, when not to use it | [references/10_decision_trees.md](references/10_decision_trees.md) |
| Validate a new GPU host (copy-pasteable steps R0–R20, first-run results) | [references/validation_runbook.md](references/validation_runbook.md) |
| Refresh from upstream | [references/maintenance.md](references/maintenance.md) |

## Quick orientation

```bash
# template — not run here. README install (from inside the clone; ~5.7 GB env incl. CUDA wheels, ~3 min pip):
git clone https://github.com/YangLab-SDU/CryoCodex.git && cd CryoCodex && git checkout v1.0.0
conda create -y -n cryocodex_env python=3.11
PYTHONNOUSERSITE=1 conda run --no-capture-output -n cryocodex_env python -m pip install -r requirements.txt
chmod +x predict.sh

# template — not run here. Default fast mode, outputs on the 1 A grid (a run without weights downloads 471 MB first):
export PYTHONNOUSERSITE=1
/abs/CryoCodex/predict.sh -i /abs/map.mrc -o /abs/out_cryocodex_run1
# outputs on the input voxel size and box:
/abs/CryoCodex/predict.sh -i /abs/map.mrc -o /abs/out_run2 --reverse_interpolation True --keep_size True
# GPU with < 8 GB free:
/abs/CryoCodex/predict.sh -i /abs/map.mrc -o /abs/out_run3 -b 4
```

`scripts/build_cryocodex_command.py` writes these (or the same options for a site launcher, `--launcher`) and refuses
the traps above. Outputs in `-o`: `cryocodex.mrc` (enhanced), `cryocodex_out_score.mrc`, `cryocodex_in_score.mrc`,
`cryocodex_in_mask.mrc` (prefix = `-n`), float32.

**Before a run**: `python3 scripts/inspect_map.py /abs/map.mrc` (name/extension gate, orthogonal cell, voxel size,
1 Å regridded box, window count and host-RAM estimate). **After**: `python3 scripts/check_outputs.py /abs/out --input
/abs/map.mrc [--keep-size] [--reverse-interpolation] [--normal] [--stats] [--log run.log]` (four files, same grid,
expected voxel size and box, placement, mask binary, score range, known failure lines).

## Scripts and templates

All scripts are stdlib Python ≥ 3.9, print `--help`, and write nothing unless asked.

- `scripts/cryocodex_env_probe.py` — read-only host probe and verdict (OS/arch, GPU, conda, env, clone commit, weights
  size/hash, user-site shadowing; `--env-prefix`/`--launcher` for shared installs).
- `scripts/inspect_map.py` — MRC header inspector + CryoCodex geometry (gates, 1 Å box, windows, RAM estimate).
- `scripts/build_cryocodex_command.py` — correct command builder; refuses the traps; `--slurm` uses the scheduler GPU;
  `--sbatch` fills the Slurm template (`--gres gpu:1`, `--launcher`, unset account/mem disabled).
- `scripts/check_outputs.py` — post-run completeness, header and (opt-in) value checks of the four outputs; log scan.
- `scripts/mrcheader.py` — shared stdlib MRC header reader and geometry rules (imported by the scripts above).
- `templates/run_plan.md` — what to show the user before a job; `templates/slurm_cryocodex.sbatch.template` — guarded
  one-GPU job (ran end to end on the validation cluster); `templates/site_launcher.sh.template` — shared-install launcher.
- `tests/validate_static.py` — offline self-test (allowlist, geometry, synthetic maps, Slurm jobs against fakes, probe
  verdicts incl. the launcher route); `tests/trigger_tests.md` — manual trigger/behaviour evals.

## House notes

- Works under Claude Code, Codex (`agents/openai.yaml`) and other agents that read SKILL.md. Record hard-won lessons in
  [lessons.md](lessons.md); preserve `lessons.md` and `configs/site_config.local.md` when updating.
- Independent, unofficial resource; not affiliated with the CryoCodex authors. Ships no CryoCodex code or weights.
  Cite the preprint per [01](references/01_source_map.md).
- Take flags only from [03](references/03_cli_reference.md). Anything else is **[unverified]**.
