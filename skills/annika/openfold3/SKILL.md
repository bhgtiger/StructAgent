---
name: openfold3
description: >-
  Explains, configures and runs OpenFold3 (aqlaboratory/openfold-3), the open
  AlphaFold3-class cofolding model for protein, RNA, DNA, ligand and ion
  complexes (CLI run_openfold, default weights OpenBind-0), and the Anthropic
  optimization kits (anthropics/uplifting-biomolecular-modeling, run.sh with
  modes off/exact/fast/big). Use to install, configure, understand or run
  OpenFold3 or the OpenFold3 kit; write or validate query JSON; build
  run_openfold predict, setup_openfold or align-msa-server commands; run kit
  run.sh pred/check/warm/install, pick a mode or --n_gpu; read outputs and
  confidence; handle MSA-server privacy and weights; troubleshoot; or refresh
  this skill. Historical validation: OpenFold3 v0.5.0 + OpenBind-0 + kit
  f4f62fa on Linux/NVIDIA A100 40 GB and H100, 2026-09-22. Probes the host
  before host-specific work; installs and predictions need explicit
  authorization. Triggers: openfold, OpenFold 3, of3.
---

# OpenFold3

OpenFold3 (`aqlaboratory/openfold-3`, Apache-2.0) predicts one joint all-atom structure for protein, RNA and DNA chains,
small-molecule ligands and ions, with pLDDT, PAE, pTM and ipTM confidences. Its v0.5.0 CLI is `run_openfold predict`
and its default checkpoint is OpenBind-0. The Anthropic kits (`anthropics/uplifting-biomolecular-modeling` @ `f4f62fa`,
an unmaintained reference release) wrap the pinned upstream wheel unchanged and add speed and memory modes behind
`run.sh pred|check|warm|install`. This skill explains both, writes query JSON, generates commands, reads outputs and
troubleshoots, without inventing flags or overstating what confidences mean. AlphaFold2 / ColabFold (`colabfold_batch`)
and Boltz are other tools: use their skills if installed (StructAgent: `skills/annika/colabfold`, `skills/annika/boltz`);
otherwise say this skill does not cover them and point to their upstream docs. Bare "OpenFold" means OpenFold3 here
(say so in one line). The AlphaFold2-era `aqlaboratory/openfold` (no `-3`; cues: `run_pretrained_openfold.py`,
`finetuning_*.pt` / `initial_training.pt`, `params_model_*`, OpenProteinSet) is out of scope: write no commands for it,
point to its own docs, offer OpenFold3 or the ColabFold skill. If the version is truly ambiguous and the answer would
differ, ask one question.

## Update this skill

Release/source review: **2026-09-22**. Latest upstream release: **v0.5.0** (2026-08-21, commit `c4771653`). The kit at
`f4f62fa` pins v0.5.0 (`openfold3_ob0/`) and 0.4.1 (legacy `openfold3/`). For an update or refresh request, follow
[references/maintenance.md](references/maintenance.md) before anything below. Maintaining the documentation needs no
runtime probe and authorizes no install, download or prediction. The 2026-09-22 GPU validation stays historical
evidence for its own stack, cards and input range.

## The one rule: probe before you act

**The machine running this agent is not assumed to be the OpenFold3 runtime.** What you may do depends on a *current*
probe report, captured this session on the target host (login, CPU and GPU nodes can differ).

```bash
python3 scripts/openfold3_env_probe.py                  # read-only, stdlib, downloads nothing; human-readable
python3 scripts/openfold3_env_probe.py --json           # machine-readable
python3 scripts/openfold3_env_probe.py --kit-dir <kit_dir>/openfold3_ob0 --ckpt <CKPT_PATH>   # a kit checkout (routes A/C)
python3 scripts/openfold3_env_probe.py --kit-cli <WRAPPER_NAME> --ckpt <CKPT_PATH> --sif <IMAGE.sif>  # a wrapper NAME on PATH
python3 scripts/openfold3_env_probe.py --hash --ckpt <CKPT_PATH>                 # opt-in, ask first: reads ~2.3 GB for sha256
python3 scripts/openfold3_env_probe.py --deep --kit-dir <kit_dir>/openfold3_ob0 --card <card>  # opt-in, ask first: MAY create cache files
```

Paths are relative to this skill's directory. `--kit-cli` takes a command name on PATH, not `bash …/run.sh`. If the agent
is not on the target, the user copies this one stdlib-only file there and runs it on each node type (login, CPU, GPU).

| State | Meaning | You MAY | You MUST NOT |
|---|---|---|---|
| **UNCONFIGURED** | No probe report captured this session for the target | Explain OpenFold3, OpenBind-0 and the kits; draft query JSON; write commands labelled `# template — not run`; cite sources | Say a machine can or cannot run it; run `run_openfold` or `run.sh`; install or download anything |
| **PROBED** | A fresh probe report exists for this host | All of the above with the host's real paths, GPU, container and checkpoint; give a readiness verdict and an install plan; run `run_openfold predict --help` and the `run.sh check` dry run after naming its side effects; with consent, run the public GPU fixture (ubiquitin, `--use-msa-server false`), the only prediction allowed here | Install or download weights or CCD without explicit per-action confirmation; run any user input before the fixture passes (VALIDATED) |
| **VALIDATED** | Runnable CLI or kit, pinned checkpoint sha256, full CCD, a GPU with compute capability ≥ 8.0 for kit modes, and a small GPU fixture passed on this host (recorded in the site config) | After explicit per-action confirmation, run predictions with safeguards: fresh absolute output dir, `--use-msa-server false` unless approved, no `set -e`, report rc and completeness | Start private, large, multi-seed or `--n_gpu` jobs without discussing cost, privacy and memory; claim a mode or size range validated beyond what was tested |

- The probe prints `>> HOST VERDICT: <X>` (JSON `verdict.state`). That verdict describes the host, not the session:
  after any probe the session is PROBED. X = `UNCONFIGURED`: nothing installed there (give an install plan from 02);
  `PROBED`: blockers remain; `VALIDATED-CANDIDATE`: ready for the GPU fixture. The probe never reports VALIDATED; only
  the GPU fixture in [02 "Verify after install"](references/02_install_and_environment.md) does.
- A report goes stale when the host, node type, image, environment, driver or session changes: re-probe
  ([11 §8](references/11_decision_trees.md)). Never carry a verdict from one machine to another.
- **Site config.** Copy [configs/site_config.template.md](configs/site_config.template.md) to
  `configs/site_config.local.md` and fill it from the probe. Keep that file out of the public package (git-ignored: it
  holds real paths, accounts and partitions). [configs/site_config.example.md](configs/site_config.example.md) is a
  filled, sanitized example from the validated site, not a config to use.

## Hard safety rails

- **The MSA server is ON by default and sends sequences off the host.** Unset or `true`, `--use-msa-server` sends every
  protein sequence in the JSON to the public ColabFold server (`api.colabfold.com`), and template-hit PDB ids go to
  RCSB. Query-level `use_msas: false` does not stop it; only `--use-msa-server false` does. Write
  `--use-msa-server false` unless the user approved the server for these sequences. Unpublished sequences: precomputed
  MSAs or single-sequence ([07 §2](references/07_msa_templates_weights.md)).
- **Ask before every install, download or submission**, one action at a time: pip/pixi installs, Docker or Apptainer
  builds, `setup_openfold`, `run.sh install` (2.3 GB checkpoint, 63 MB CCD), `run.sh warm`, any `pred`/`predict`, any
  GPU job. One approval never covers the next dataset.
- **Kit rc 3 and rc 5 are results, not crashes.** Never wrap calls in `set -e`. Capture `rc=$?`, grep stderr for
  `exit rule ->`, and report `NOT ACTIVE: <reason>` instead of silently retrying as stock.
- **Exit code is not completeness.** Stock `run_openfold` catches OOM and per-query errors and still exits 0; the kit
  turns a short count into rc 1 (`incomplete`). Check every run with `scripts/summarize_openfold3_output.py` and read
  `summary.txt`.
- **Byte identity only under `--det 1`.** `exact --det 1` equals `off --det 1`; ordinary `exact` does not, and
  `fast`/`big` never do. **`fast` fidelity is uncalibrated** against stock's seed-to-seed spread (top-model CA RMSD vs
  `off` reached ~29 Å on low-confidence single-sequence inputs). Before publishing `fast` results, run the seed-spread
  check ([09](references/09_validation_and_benchmarks.md)).
- **Single-sequence confidence is not MSA confidence.** Runs with `--use-msa-server false` and no MSAs test the software,
  give low confidence on most proteins, and must be reported as single-sequence.
- **Keep JIT and compile caches off inode-limited homes** (668–1 013 files per job measured): node-local
  `MODEL_OPT_JIT_ROOT`, `TRITON_CACHE_DIR`, `TORCH_EXTENSIONS_DIR`, `XDG_CACHE_HOME` and `TMPDIR`.
- **`run.sh check` is neither side-effect free nor a GPU proof.** It re-hashes the checkpoint (2.3 GB read), rewrites
  the weights-digest memo and may create a JIT root. rc 0 with `gpu=none` on a CPU node proves nothing about the GPU.
- **No training, ligand steering or affinity.** `run_openfold train` is out of scope. v0.5.0 has no chemical steering
  (branch only) and no affinity output; `covalent_bonds`, `sdf_file_path` and multiple `ccd_codes` are not implemented.
  Confidence is the model's self-estimate, never proof of a structure or of binding.
- **Pinned weights only.** Use OpenBind-0 with sha256 `bd43301c…8e29e4`; other bytes only print
  `WARNING: WEIGHTS unknown` and run (weights are pickles). Preview-2 weights do not load on ≥ 0.5.0.
- **Don't overstate platforms.** Upstream ships CPU, Apple-MPS and ROCm pixi environments; none is validated here. The
  kit needs Linux x86-64, NVIDIA compute capability ≥ 8.0 and driver ≥ 570; upstream asks for ≥ 32 GB of GPU memory.

## Reference routing: read the one you need

| You need to… | Read |
|---|---|
| Scope, trust ladder, state machine, claims never to make, licences | [references/00_scope_and_trust.md](references/00_scope_and_trust.md) |
| The pinned source, docs page, paper or DOI behind a claim | [references/01_source_map.md](references/01_source_map.md) |
| Install (pip, pixi, Docker; kit routes A/B/C; HPC Apptainer), caches, post-install checks | [references/02_install_and_environment.md](references/02_install_and_environment.md) |
| Exact flags, spellings, defaults, environment variables, exit codes, known traps | [references/03_cli_reference.md](references/03_cli_reference.md) |
| Query JSON fields, ligands, ions, PTMs, pockets, token count, schema errors | [references/04_input_query_format.md](references/04_input_query_format.md) |
| A standard workflow: first contact, monomer to complex, ligand, nucleic acids, batch, MSAs, templates, runner YAML, kit run, Slurm, ledger | [references/05_core_workflows.md](references/05_core_workflows.md) |
| Kit modes, `--det`, `big` gates, `--n_gpu`, log lines, rc 3 causes, JIT | [references/06_kit_modes_and_multigpu.md](references/06_kit_modes_and_multigpu.md) |
| MSA routes and server privacy, precomputed MSAs, templates, weights registry, CCD | [references/07_msa_templates_weights.md](references/07_msa_templates_weights.md) |
| Output tree, confidence keys, top-model ranking, completeness rule | [references/08_outputs_and_confidence.md](references/08_outputs_and_confidence.md) |
| Published benchmarks, report and measured numbers, validating a new host | [references/09_validation_and_benchmarks.md](references/09_validation_and_benchmarks.md) |
| Symptom → cause → check → fix | [references/10_troubleshooting.md](references/10_troubleshooting.md) |
| Quick choices: stock or kit, mode, MSA route, card, seeds, rc routing, re-probe, escalation | [references/11_decision_trees.md](references/11_decision_trees.md) |
| Refresh the skill from new releases, kit commits or docs | [references/maintenance.md](references/maintenance.md) |

## Quick orientation (details in the references)

**Stock or kit.** Stock `run_openfold predict` (v0.5.0) needs no kit. The OB0 kit (`openfold3_ob0/` = 0.5.0 +
OpenBind-0) is an optional speed and memory layer on Linux + NVIDIA compute capability ≥ 8.0. The legacy `openfold3/`
kit (0.4.1 + preview-2 weights) only reproduces old results. Either way the checkpoint must exist first: v0.5.0
`predict` never downloads it and raises "cowardly refusing to perform inference". Fetch it, with consent, through
`setup_openfold --config setup.json` or `run.sh install --weights DIR`
([02 "Weights and CCD"](references/02_install_and_environment.md)).

**Minimal query JSON** (check it with `python3 scripts/make_query.py --validate q.json`):

```json
{"queries": {"ubiquitin": {"chains": [
  {"molecule_type": "protein", "chain_ids": ["A"],
   "sequence": "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG"}]}}}
```

MSA switches (`use_msas`, `use_main_msas`, `use_paired_msas`) go at query level, never inside a chain. A ligand takes
`smiles` or one `ccd_codes`, never both. Unknown query-level keys are silently ignored, so validate every file.

**Minimal commands** (booleans take a value; absolute paths; a new output directory per run):

```bash
# template — not run
# stock: finds the checkpoint through $OPENFOLD_CACHE (default ~/.openfold3) unless --inference-ckpt-path is given
run_openfold predict --query-json /abs/q.json --output-dir /abs/out --use-msa-server false

# kit: <KIT> = "bash <kit_dir>/openfold3_ob0/run.sh", "apptainer run --nv <image>.sif" or a site wrapper
# <card> = a100 | h100 | h200 | b200 | b300: the card CLASS, not memory (A100 40/80 GB -> a100; H100 80/94 GB -> h100)
# install takes no --config/--mode (rc 2): <KIT> install --weights DIR   (consent: 2.3 GB)
unset OPENFOLD3_OB0_OPT      # a value that disagrees with --mode exits 2; any mode but off arms plain run_openfold (bad value: rc 3)
export OPENFOLD3_OB0_CKPT=<weights_dir>/of3-ob-2025-06-30-174k.pt
<KIT> check --config <card> --mode exact                                   # dry run, on the GPU node
<KIT> pred --config <card> --mode exact --query-json /abs/q.json --output-dir /abs/out --use-msa-server false
rc=$?; echo "rc=$rc"                                                       # 0 ok, 1 failed/incomplete, 2 usage, 3 NOT ACTIVE, 5 templates dropped
```

**Choose a mode** ([11 §3](references/11_decision_trees.md)); always pass `--mode`, because without it the kit runs `fast`:
1. `exact` by default: same algorithm as stock, faster. Add `--det 1` (reference: `off --det 1`) when bytes must match.
   On a 40 GB card above ~500 tokens prefer `fast`, or move `exact` to an 80/94 GB card: `exact` peaked at 39.9 of 40 GB
   on a ~737-token protein–ligand input ([11 §5](references/11_decision_trees.md)).
2. `fast` for throughput (about half the peak memory from ~500 tokens), after a seed-spread check; `off` for a baseline.
3. `big` for any query at or above 1 401 polymer tokens (ligand atoms are not counted; `make_query.py --validate` prints
   the count): that is the size its gate is built for, and below it `big` is `fast` and will not help. On a 40 GB card
   ≥ 1 401 tokens is untested: prefer an 80/94 GB card (`--config h100 --mode big`), else a consented test with
   `--config a100 --mode big` and generous host RAM. `--n_gpu 2|4|8` only with `big`, on one host, as one task.

**Outputs.** `<out>/<query>/seed_<s>/<query>_seed_<s>_sample_<k>_{model.cif,confidences.json,confidences_aggregated.json}`
plus `timing.json`; at the top `summary.txt`, `experiment_config.json`, `model_config.json`, `inference_query_set.json`
and `msas/`. Defaults are seed 42 × 5 samples; `--num-model-seeds N` draws other seeds (e.g. `seed_2746317213/`).
Per-atom pLDDT sits in the mmCIF B-factor column. The tree holds sequences, absolute paths and the login name: scrub it
before sharing ([08](references/08_outputs_and_confidence.md)).

**Top model.** Nothing is ranked on disk, and `sample_1` is not the best. Take the highest `sample_ranking_score`
(0.8·ipTM + 0.2·pTM + 0.5·disorder − 100·has_clash) across all seeds of one query, within one run. It is a sorting key,
not a probability; for complexes also read `chain_pair_iptm`. The summarizer ranks samples and checks completeness.

**Common path: protein–ligand on a GPU server** (each step that installs, sends data or uses a GPU needs consent):
1. Probe on the GPU node (above); read the host verdict.
2. Weights, with consent: `run.sh install --weights DIR`, or `setup_openfold --config setup.json` with
   `{"openfold_cache": "/abs/c", "param_directory": "/abs/c", "selected_parameters": "default"}` (set both paths).
3. Query: `templates/queries/protein_ligand_ccd.json`, or `make_query.py --name q --protein @p.fasta --ligand-ccd ATP
   --ligand-ccd MG --out /abs/q.json`. Ions are ligands with one CCD code (there is no `ion` type); novel compounds
   use `--ligand-smiles`.
4. Ask the MSA route: public server approved for these sequences, precomputed MSAs, own server, or single-sequence
   ([11 §4](references/11_decision_trees.md)).
5. The public GPU fixture, then `pred --config <card> --mode exact|fast` (mode by card size, above).
6. `summarize_openfold3_output.py <out> --query-json /abs/q.json --expect-seeds 1 --expect-samples 5 --chains`; read
   the protein–ligand `chain_pair_iptm` and `has_clash`. Report that OpenFold3 gives no affinity.

## Scripts and templates

All scripts are stdlib Python ≥ 3.9 and print `--help`.

- `scripts/openfold3_env_probe.py`: read-only host probe (GPUs, containers, CLIs, packages, checkpoints, kit, caches)
  with a verdict. `python3 scripts/openfold3_env_probe.py --json [--kit-cli NAME] [--ckpt PATH] [--sif PATH]`
- `scripts/make_query.py`: build or validate query JSON, with a token estimate (exit 0 ok, 1 invalid, 2 usage).
  `python3 scripts/make_query.py --name ras --protein @hras.fasta --ligand-ccd GTP --ligand-ccd MG --out ras.json`
- `scripts/summarize_openfold3_output.py`: read-only completeness check and sample ranking per query (exit 0 ok,
  1 incomplete or problems). `python3 scripts/summarize_openfold3_output.py <out> --query-json q.json --expect-seeds 1 --expect-samples 5`
- `templates/queries/`: nine validated public example queries (monomer, heteromer, homomer, modified residue, ligand by
  SMILES and by CCD code, pocket, protein–DNA, precomputed-MSA placeholders) with a README.
- `templates/slurm_predict.sbatch.template`: a guarded generic Slurm job (refusals before GPU work, job-local caches,
  `--use-msa-server false`, rc meanings, structure count, ledger). Fill every placeholder, `bash -n`, submit only with
  consent.

## House notes

- Works under Claude Code and Codex. Claude reads this frontmatter; Codex reads `agents/openai.yaml`. The scripts are
  portable and write nothing unless asked (`make_query.py --out`).
- Record anything learned the hard way in [lessons.md](lessons.md) (date, lesson, evidence pointer). Preserve it and any
  `site_config.local.md` when updating the skill.
- This is an independent, unofficial community resource. It is not affiliated with or endorsed by the OpenFold
  Consortium, the AlQuraishi Lab, the OpenBind Consortium, Google DeepMind (AlphaFold) or Anthropic (authors of the
  uplifting-biomolecular-modeling kits). Product names only identify the software; trademarks belong to their owners.
  The skill ships no OpenFold3 code, kit code or weights. When publishing, cite per
  [01 "How to cite"](references/01_source_map.md).
- Cite pinned sources (`openfold-3@v0.5.0:<path>`, `uplifting-biomolecular-modeling@f4f62fa:<path>`). Live help on the
  target beats docs. Take flags only from [03](references/03_cli_reference.md); anything else stays **[unverified]**
  until captured with live `--help` on the target.
