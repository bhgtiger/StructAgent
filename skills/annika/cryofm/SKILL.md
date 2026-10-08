---
name: cryofm
description: "Config-first, VALIDATED assistant for CryoFM2 (ByteDance-Seed/cryofm, CLI cfm): flow-matching prior for cryo-EM maps that denoises, inpaints (anisotropy) and non-uniform-refines half maps by posterior sampling (cfm denoise, cryofm2-pretrain) and restyles maps EMhancer- or EMReady-like (cfm enhance), plus the RELION --external_reconstruct wrapper. Use to install, configure, understand, plan or run CryoFM/CryoFM2: correct cfm commands, denoise vs enhance, --op, --output-tag/--cfg-weight, batch size per GPU, map-header gates (odd box, origin, pixel size), outputs (3 A band limit, origin reset, not gold-standard half maps), RELION hazards, OOM/argparse errors, or refreshing this skill. Validated 2026-10-08 on an A100 40 GB (commit 6448681, weights 4e308f7f); site paths live only in a git-ignored site config. Probes first; GPU jobs, installs and downloads need confirmation. Triggers: cryofm, CryoFM2, cfm denoise, cfm enhance, cryofm2-pretrain, EMhancer, EMReady, flow posterior sampling, external_reconstruct."
---

# CryoFM2

CryoFM2 (`ByteDance-Seed/cryofm`, Apache-2.0, package `cryofm` 0.1.0, CLI `cfm`) is a 3D U-Net flow-matching
prior over cryo-EM density maps, pretrained on EMDB half maps resampled to 1.5 Å/voxel. Two uses:

- **Flow posterior sampling (FPS)** with the unconditional `cryofm2-pretrain` model: `cfm denoise` takes **two half
  maps** and a likelihood operator (`--op denoise`, `denoise inpaint` with particle poses, `non-uniform`) and writes a
  posterior sample per half plus their average. The RELION `--external_reconstruct` wrapper runs the same code inside
  Refine3D.
- **Style enhancement** with a fine-tuned model: `cfm enhance -i map.mrc` restyles one map toward a LocScale-sharpened
  look (`cryofm2-emhancer`, `--output-tag 1`) or a model-simulated look (`cryofm2-emready`, `--output-tag 0
  --cfg-weight 0.5`). With half maps added it becomes conditional posterior sampling.

CryoFM1 (HDiT, `cryofm-v1`, ICLR 2025) is a proof of concept with a different Python API and is **not** part of
the validated install; this skill explains it only when asked. cryoSeed (`unstable` branch) is a research module, not covered beyond
one paragraph in [07](references/07_relion_integration.md).

## Update this skill

Source review: **2026-10-08**. Upstream has **no tags and no releases**; the pin is commit `6448681` (`main`,
2026-03-03) and HF revision `4e308f7f` (weights unchanged since first upload 2025-12-25). The paper is an
**unrefereed bioRxiv v1** (2025-12-29). For a refresh request follow [references/maintenance.md](references/maintenance.md).

## The one rule: probe before you act

The machine running this agent is not assumed to be the CryoFM runtime. What you may do depends on a probe report
captured **this session on the node you will use** (login, CPU and GPU nodes differ).

```bash
python3 scripts/cryofm_env_probe.py                 # read-only, stdlib, downloads nothing
python3 scripts/cryofm_env_probe.py --json
python3 scripts/cryofm_env_probe.py --weights-dir <dir> --sif <image.sif> --hash   # --hash: ask first, reads 2 GB
```

| State | Meaning | You MAY | You MUST NOT |
|---|---|---|---|
| **UNCONFIGURED** | no probe this session | explain; inspect map headers with `scripts/inspect_map.py`; draft commands labelled `# template — not run` | say a machine can run it; run `cfm`; install or download |
| **PROBED** | fresh probe for this host | all of the above with real paths; readiness verdict; install plan; `cfm --help` and module `--help` on a CPU node | run any `cfm denoise`/`enhance` before the user confirms that specific job |
| **VALIDATED** | probe finds launcher + image/env + three pinned weight dirs, and a GPU fixture passed on this host (recorded in the site config) | after explicit per-job confirmation, run jobs with safeguards: GPU node, fresh absolute `-o`, `--log-file-path`, report rc and files | start large/private/multi-GPU jobs without discussing cost, memory and privacy; claim modes validated beyond what was run |

The probe prints `>> HOST VERDICT: <X>`. It never prints VALIDATED; only a GPU fixture does. A verdict goes stale when
host, node type, image, weights or driver change. Site config: copy
[configs/site_config.template.md](configs/site_config.template.md) to `configs/site_config.local.md` (real paths,
git-ignored) and fill it from the probe; [configs/site_config.example.md](configs/site_config.example.md) is the
validated site's config, sanitized — an example, not a config to use.

## Hard safety rails

- **Every likelihood path needs `--norm-grad`.** `cfm denoise` (any `--op`) and `cfm enhance` with `-i1/-i2` hard-fail
  with `AssertionError: Now we only support norm=True for flow` after all preprocessing. Add `--use-lamb-w` too (every
  upstream recipe does). Pure `cfm enhance -i map.mrc` needs neither.
- **`cfm denoise` needs both half maps.** One map alone → `cfm enhance -i` (style, no data term) is the only option.
- **Tag and CFG must match the model.** `cryofm2-emhancer` → `--output-tag 1` (default); `cryofm2-emready` →
  `--output-tag 0 --cfg-weight 0.5` (code defaults are tag 1, CFG 2.0 for *every* model; nothing checks the pairing).
- **`--model-dir` is a variant folder** holding `config.yaml` + `model.safetensors`, never the repo root. Pretrain only
  works with `cfm denoise`/RELION; emhancer/emready only with `cfm enhance`. Treat `config.yaml` as code (full YAML loader).
- **Four documented commands are wrong**; never copy them: quick-start "Anisotropy correction" repeats `--op` (only the
  last wins, so `inpaint` is dropped); both "Add extra control" commands use `cfm denoise` with `--output-tag`
  (rejected: use `cfm enhance -i … -i1 … -i2 …`); the `cfm --help` epilog omits `--norm-grad`. Details in [03 §6](references/03_cli_reference.md).
- **Outputs are not gold-standard half maps.** Each output uses the FSC of *both* inputs (and `non-uniform` the shared
  difference map). FSC between the two outputs is inflated; validate with map-model FSC/CC and visual inspection.
- **Output header: origin reset to (0,0,0), NXSTART 0.** Inputs with a non-zero origin/NSTART no longer overlay
  their output or model in ChimeraX/Phenix. Run `scripts/restore_origin.py` (or ChimeraX `volume #N originIndex`) first.
- **3.0 Å band limit without `--spectral-mixing`.** Maps finer than 1.5 Å/px are Fourier-cropped to the 1.5 Å model
  grid; on-axis content beyond 3.0 Å is gone (corners keep ≈1.73 Å). `--spectral-mixing` pastes the *raw* input back above 3 Å.
- **Geometry gates:** `.mrc`/`.map` only (gunzip `.map.gz`); odd *cubic* boxes fail an assert (pad to even); resampled
  box must be ≥ 64 voxels (≳ 96 Å); non-cubic maps are padded automatically but masks are not.
- **Memory is per GPU and set by `--batch-size`** (docs: 24 G at batch 4, 21 G with `--bf16`, 13/11 G at batch 2,
  7.3/6.9 G at batch 1; pure enhance 9.1/7.3 G at batch 4). `--num_processes` splits patches, it does not lower per-GPU memory.
  Batch size also changes posterior results slightly (one unit-norm gradient per batch).
- **Ask before every GPU job, install or download**, one at a time. Never reuse an output dir (same stems overwrite).
- **No egress on the default path** (static import closure; the validated site's image is offline too), but the paper, docs and card are silent on which
  half maps to feed, processing order, deposition and validation; say "undocumented", do not invent.

## Reference routing

| You need to… | Read |
|---|---|
| Scope, trust ladder, must-not-claim list, licences | [references/00_scope_and_trust.md](references/00_scope_and_trust.md) |
| Pinned sources (SHAs, URLs, paper DOIs), how to cite, where the evidence folder is | [references/01_source_map.md](references/01_source_map.md) |
| Install routes (pip from source, conda, Apptainer recipe), weights download + sha256, env vars, caches | [references/02_install_and_environment.md](references/02_install_and_environment.md) |
| Exact flags (live help), launcher semantics, flag-by-path matrix, exit codes, documented-command errata | [references/03_cli_reference.md](references/03_cli_reference.md) |
| Accepted files, pixel size rule, resampling, box rules, origin, masks, particle STAR, normalisation | [references/04_inputs_and_geometry.md](references/04_inputs_and_geometry.md) |
| Standard workflows: denoise, anisotropy, non-uniform, enhance (both styles), enhance + likelihood, masks, multi-GPU, Slurm, ledger | [references/05_core_workflows.md](references/05_core_workflows.md) |
| Operators and every tuning knob with defaults, ranges, derived caveats | [references/06_operators_and_tuning.md](references/06_operators_and_tuning.md) |
| RELION `--external_reconstruct`: protocol, wrapper, versions, hazards; cryoSeed; cryoSPARC bridge | [references/07_relion_integration.md](references/07_relion_integration.md) |
| Output files, headers, what they are not, validation advice, smoke numbers | [references/08_outputs_and_validation.md](references/08_outputs_and_validation.md) |
| Paper claims by tier, the validated site's record, third-party evaluations | [references/09_evidence_and_benchmarks.md](references/09_evidence_and_benchmarks.md) |
| Symptom → cause → fix (OOM, argparse, channel mismatch, libGL, wrapper recursion, display) | [references/10_troubleshooting.md](references/10_troubleshooting.md) |
| Quick choices: which command, model, op, batch size, card; re-probe; escalation | [references/11_decision_trees.md](references/11_decision_trees.md) |
| Refresh from new commits, HF revisions, docs | [references/maintenance.md](references/maintenance.md) |

## Quick orientation (details in the references)

**Commands that are correct** (absolute paths, a NEW `-o` per run, `--bf16` on A100/H100):

```bash
# template — not run; <MODELS> = folder holding cryofm2-pretrain/ cryofm2-emhancer/ cryofm2-emready/
cfm denoise -i1 /abs/half1.mrc -i2 /abs/half2.mrc -o /abs/out_denoise \
    --model-dir <MODELS>/cryofm2-pretrain --op denoise --norm-grad --use-lamb-w --bf16 --seed 0
cfm denoise -i1 /abs/half1.mrc -i2 /abs/half2.mrc -o /abs/out_aniso \
    --model-dir <MODELS>/cryofm2-pretrain --op denoise inpaint --data-starfile-path /abs/run_data.star \
    --fmask-threshold 10 --norm-grad --use-lamb-w --bf16
cfm denoise -i1 /abs/half1.mrc -i2 /abs/half2.mrc -o /abs/out_nu \
    --model-dir <MODELS>/cryofm2-pretrain --op non-uniform --nbands 64 --norm-grad --use-lamb-w --bf16
cfm enhance -i /abs/map.mrc -o /abs/out_emhancer --model-dir <MODELS>/cryofm2-emhancer --output-tag 1 --bf16
cfm enhance -i /abs/map.mrc -o /abs/out_emready  --model-dir <MODELS>/cryofm2-emready  --output-tag 0 --cfg-weight 0.5 --bf16
cfm enhance -i /abs/map.mrc -i1 /abs/half1.mrc -i2 /abs/half2.mrc -o /abs/out_ctrl \
    --model-dir <MODELS>/cryofm2-emhancer --output-tag 1 --op denoise --norm-grad --use-lamb-w --bf16   # style + data term
cfm denoise --num_processes 4 -i1 /abs/half1.mrc -i2 /abs/half2.mrc -o /abs/out_mgpu \
    --model-dir <MODELS>/cryofm2-pretrain --op denoise --norm-grad --use-lamb-w --bf16   # multi-GPU: underscores, AFTER the subcommand
```

`scripts/build_cfm_command.py` writes these for you and refuses the known traps. `cfm denoise --help` prints only the
launcher stub; real flags come from `python -m cryofm.projects.cryofm2.uncond_sampling --help` (captured in [03](references/03_cli_reference.md)).

**Outputs** in `-o`: `<stem(-i1)>_external_reconstruct.mrc`, `<stem(-i2)>_external_reconstruct.mrc`,
`avg_external_reconstruct.mrc` (denoise); `<stem(-i)>_external_reconstruct.mrc` (enhance). float32, input box and
pixel size, origin 0. Progress bars count patch batches, not ODE steps; each batch runs the full 200 steps.

**Before any run**: `python3 scripts/inspect_map.py half1.mrc half2.mrc` (extension, axis order, odd cube, box
≥ 96 Å, pixel sizes equal, origin, patch count and batch count at 1.5 Å). After: `python3
scripts/check_cfm_output.py <out> --input half1.mrc` then `scripts/restore_origin.py` if the input origin was non-zero.

## On a validated site

The historical validation (2026-10-08, one A100-SXM4 40 GB, Apptainer image at commit 6448681, weights 4e308f7f) is
recorded, sanitized, in [configs/site_config.example.md](configs/site_config.example.md): all three variants ran on the
public EMD-11638 fixture (job 27772096, rc 0, every output finite on the input grid; low-pass CC vs input 0.986–0.997 at
3.5/6 Å for denoise, 0.952/0.796 emhancer, 0.705/0.806 emready; peak 21 443 MiB at batch 4 + `--bf16`; 251 s for two
halves of 8 patches, ≈54 s per batch of 4 patches × 200 steps). It proves nothing about *your* host: probe, then record
your own fixture run in `configs/site_config.local.md`. What a site copy of this skill typically adds (none of it is
bundled here):

- a site launcher that puts `cfm` (and a `cfm-relion` alias for the RELION wrapper) on PATH after an activation script,
  resolves `--model-dir pretrain|emhancer|emready` to the pinned weight folders and adds `--nv` on GPU nodes only
  ([03 §7](references/03_cli_reference.md)) — `scripts/build_cfm_command.py --shorthand` emits that form; otherwise
  give `--models <dir>` and the variant folder is spelled out;
- a filled job script derived from [templates/slurm_cfm.sbatch.template](templates/slurm_cfm.sbatch.template)
  (account, GPU partition, CPU/memory share per GPU — the example site used 18 CPUs / 120 GB per A100 —, node-local
  `TMPDIR`, outputs outside an inode-limited home; jobs started with `--export=NONE` activate inside the job);
- GPU spend approved per submission and logged (an annika-log `Job_NNN_*` folder where that convention exists).

Scale: a 256³ map at 1.0 Å gives 125 patches, 32 batches, ≈30 min per half on an A100. Untested on the validated site
and therefore everywhere: `--op inpaint`/`denoise inpaint` with a real particle STAR, `non-uniform`, `cfm enhance` with
half maps, `--mask-path --bbox`, `--num_processes` > 1, the RELION wrapper end to end, H100. Say so before a first run.

## Scripts and templates

All scripts are stdlib Python ≥ 3.9, print `--help`, and write nothing unless asked.

- `scripts/cryofm_env_probe.py` — read-only host probe with verdict (GPU, apptainer/conda, launcher, image, weights, caches).
- `scripts/inspect_map.py` — MRC header inspector + CryoFM2 geometry (resampled box, patches, batches, gates, origin, pairs).
- `scripts/build_cfm_command.py` — correct command builder (modes denoise/aniso/nonuniform/emhancer/emready/enhance-posterior; refuses traps; `--sbatch` emits a Slurm job).
- `scripts/check_cfm_output.py` — post-run completeness and header check (expected files, grid equality, finite stats, origin warning).
- `scripts/restore_origin.py` — copies NSTART/ORIGIN of the reference input onto a same-grid output into a NEW file.
- `templates/slurm_cfm.sbatch.template` — guarded one-GPU Slurm job with `<PLACEHOLDERS>` (account, partition, site activation,
  node-local TMPDIR, output root, skill dir; refuses unfilled settings; no `set -e`; rc capture; post-check).
- `templates/relion_external_reconstruct.sh` — RELION ≥ 4.0.1 integration template, NOT RUN, with the hazards inline.
- `templates/run_plan.md` — what to show the user before a job is submitted.

## House notes

- Works under Claude Code and Codex (`agents/openai.yaml`). Record hard-won lessons in [lessons.md](lessons.md).
  Preserve `lessons.md` and `configs/site_config.local.md` when updating.
- Independent, unofficial community resource; not affiliated with ByteDance Seed, the RELION, DeepEMhancer, EMReady or
  LocScale authors. Ships no CryoFM code or weights. Cite per [01 "How to cite"](references/01_source_map.md).
- Take flags only from [03](references/03_cli_reference.md) (live `--help` on the target, 2026-10-08). Anything else
  is **[unverified]** until captured live.
