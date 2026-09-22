# Reference answers (graders' key)

Concise "good answer" sketches for `evals/evals.json`, grounded in the references. A strong response need not match
the wording, only the substance and the safety behaviour. Commands below are templates, never run. Numbers marked
measured come from one Slurm HPC site with A100-SXM4 40 GB and H100 94 GB nodes (validated 2026-09-22,
single-sequence inputs up to 995 tokens).

## 0 — first-contact-unknown-host

No readiness claim yet: the session is UNCONFIGURED. Ask the user to run, on the target (login and GPU nodes can
differ), `python3 scripts/openfold3_env_probe.py --json` and share it; `--hash`/`--deep` only on request. Probe verdict
`UNCONFIGURED` = nothing installed there (give an install plan, [02](../references/02_install_and_environment.md));
`PROBED` or `VALIDATED-CANDIDATE` = record `state: PROBED`. Next: `run_openfold predict --help` on a CPU node,
checkpoint sha256, `run.sh check --config <card> --mode exact` on a GPU node (it re-hashes 2.3 GB and rewrites the
digest memo; `gpu=none` proves nothing). Fill `configs/site_config.local.md` from the template (git-ignored).
VALIDATED only after the ubiquitin GPU fixture passes, with consent. Commands shown as `# template — not run` with
`--use-msa-server false`. (SKILL.md "The one rule"; [00](../references/00_scope_and_trust.md);
[05 workflow 1](../references/05_core_workflows.md); [11 §8](../references/11_decision_trees.md).)

## 1 — protein-ligand-query-json

```json
{"queries": {
  "hras_gtp_mg": {"chains": [
    {"molecule_type": "protein", "chain_ids": ["A"], "sequence": "MTEYKLVVVG...EIRQH"},
    {"molecule_type": "ligand", "chain_ids": ["B"], "ccd_codes": "GTP"},
    {"molecule_type": "ligand", "chain_ids": ["C"], "ccd_codes": "MG"}]},
  "hras_cmpd1": {"chains": [
    {"molecule_type": "protein", "chain_ids": ["A"], "sequence": "MTEYKLVVVG...EIRQH"},
    {"molecule_type": "ligand", "chain_ids": ["B"], "smiles": "CC(=O)Nc1ccc(O)cc1"}]}}}
```

Full sequence in both entries. Ions are ligands with a one-atom CCD code (no `ion` type); one code per chain; never
`smiles` plus `ccd_codes`. Tokens ≈ 199 and 177. `python3 scripts/make_query.py --validate q.json`, then
`run_openfold predict --query-json /abs/q.json --output-dir /abs/out --use-msa-server false` (template). Output:
structures + confidences, ligand named `LIG0`; no affinity. (04 "Rules first", "Ligands and ions", "Token count";
[05 workflow 4](../references/05_core_workflows.md); `templates/queries/protein_ligand_ccd.json`.)

## 2 — kit-mode-3000-tokens-40gb

~2 950 polymer tokens ≥ 1 401, so `big` (row blocks + host streaming) is the only fitting mode; below the gate it is
`fast`, and ligand atoms are not counted. Gates and chunk plan are sized on 80 GB cards; 1 401–~5 000 tokens is "not
recommended" on 40 GB and untested. Prefer an 80/94 GB node (`--config h100 --mode big`); otherwise a consented test:

```bash
# template — not run
unset OPENFOLD3_OB0_OPT
export OPENFOLD3_OB0_CKPT=<weights_dir>/of3-ob-2025-06-30-174k.pt MODEL_OPT_JIT_ROOT=<node_local_dir>/jit
<KIT> check --config a100 --mode big
<KIT> pred --config a100 --mode big --query-json /abs/q.json --output-dir /abs/out_big --use-msa-server false
rc=$?; echo "rc=$rc"
```

Generous host RAM (pair snapshot ≈ N² × 128 × 2–4 bytes). Next step `--mode big --n_gpu 2|4|8` on one node, one task
(40 GB cards print the chunk-plan NOTE). ([06 §4–6](../references/06_kit_modes_and_multigpu.md);
[11 §5](../references/11_decision_trees.md).)

## 3 — unpublished-sequence-msa-privacy

Defaults send data: `--use-msa-server` unset = true → every protein sequence to `api.colabfold.com`, template-hit PDB
ids to RCSB; `use_msas: false` does not stop it; `align-msa-server` sends too; retention and terms unreviewed. For NDA
sequences: precomputed MSAs (`main_msa_file_paths`/`paired_msa_file_paths` + `--use-msa-server false`), a self-hosted
server (`msa_computation_settings.server_url`, user-approved), or single-sequence (`--use-msa-server false`, lower
accuracy, weakest at interfaces; report it). Outputs hold sequences and the login name: keep private or scrub.
([07 §1–3](../references/07_msa_templates_weights.md); [11 §4](../references/11_decision_trees.md);
[08 "Before sharing outputs"](../references/08_outputs_and_confidence.md).)

## 4 — bare-use-msa-server-flag

`--use-msa-server` is a value-taking BOOLEAN: the bare flag ate `--output-dir` (rc 2; at line end: `requires an
argument`). Docs showing a bare flag are wrong. Fix:
`run_openfold predict --query-json /abs/q.json --output-dir /abs/out --use-msa-server false`; `true` only with approval
(public server). Kit `run.sh pred` accepts only the hyphen spelling. ([03 §2, §9 traps 1–3](../references/03_cli_reference.md).)

## 5 — kit-install-config-rejected

`install` rejects `--config`/`--mode` (rc 2) whatever the README prose says; cards belong to `pred`/`check`/`warm`.
With consent: `bash run.sh install --weights /data/of3_weights` (offline `--ccd`/`--wheel`/`--src`; the 0.4.1 kit has
only `--weights`); it fetches wheel, source and CCD if missing and the 2.3 GB checkpoint if absent. Then
`export OPENFOLD3_OB0_CKPT=/data/of3_weights/of3-ob-2025-06-30-174k.pt` and, on a GPU node,
`bash run.sh check --config a100 --mode exact` (dry run; `gpu=none` is no GPU proof).
([03 §6, trap 7](../references/03_cli_reference.md); [02 Route 2](../references/02_install_and_environment.md).)

## 6 — kit-rc3-rc5-results

rc 3 = `NOT ACTIVE: <reason>`: pins/package/core (reinstall pinned stack or rebuild image), hook not live, partial
line, `--z-dtype bf16 --conf-dtype fp32`, undeclared `OPENFOLD3_OB0_OPT*`, cc < 8.0, fewer GPUs than `--n_gpu`; on a
VALIDATED host, re-probe. rc 5 = `TEMPLATES DROPPED` (offline RCSB fetch): runner YAML `structure_directory` +
`structure_file_format: cif` + `fetch_missing_structures: false`, or remove template keys, or a recorded
`--allow-template-drop`. Drop `set -e`; `rc=$?`; grep `exit rule ->`. A stock retry would hide both (stock exits 0
with templates silently dropped). ([03 §8](../references/03_cli_reference.md);
[06 §8](../references/06_kit_modes_and_multigpu.md); [07 §7](../references/07_msa_templates_weights.md);
[11 §7](../references/11_decision_trees.md).)

## 7 — exit0-missing-queries

Stock catches OOM and per-query errors, writes `logs/predict_err_rank0.log`, counts them in `summary.txt`
("Failed Queries") and exits 0. Check:
`python3 scripts/summarize_openfold3_output.py <out> --query-json q.json --expect-seeds 1 --expect-samples 5` (rc 1 =
incomplete). OOM → ladder (5 samples, `model_update: {presets: [predict, low_mem]}`, kit `fast`, bigger card, split);
input errors → 04 "Common errors". Rerun the fixed queries into a new output dir, or resume the same dir with
`experiment_settings: {skip_existing: true}`. The kit would have said rc 1 `incomplete`.
([10 triage, OOM ladder](../references/10_troubleshooting.md);
[08 "Kit trees and the completeness rule"](../references/08_outputs_and_confidence.md);
[05 workflow 6](../references/05_core_workflows.md).)

## 8 — exact-det-fast-choice

Paper: `--mode exact --det 1`, reference `off --det 1` (byte-identical, 60/60 file pairs measured per card; ~stock
speed); record card, stack and seeds. Plain `exact` is not byte-identical. Screen: `fast` (warm whole call 1.24–2.13×
A100 / 1.21–1.83× H100 vs `off`, measured) after a seed-spread check, since fidelity is uncalibrated (~29 Å top-model
CA RMSD on low-confidence single-sequence inputs); `exact` (1.12–1.40× / 1.11–1.37×) if unsure. One JSON, one call
(≈45 s start-up per call); rank within one mode; poses and confidence, not affinity. Always `--mode`; `unset
OPENFOLD3_OB0_OPT`; no `big` below 1 401. ([11 §3](../references/11_decision_trees.md);
[06 §2–3](../references/06_kit_modes_and_multigpu.md); [09](../references/09_validation_and_benchmarks.md).)

## 9 — single-sequence-confidence

Single-sequence (`/dummy/` MSA paths): low confidence is expected (measured top-model mean pLDDT 31–92; ≈35 at 995
tokens). It shows the software ran, not interface quality, and is not comparable with MSA runs. Rerun with MSAs via an
approved route, several seeds, then judge. `iptm` = 0 for one chain by construction (monomer score = 0.2·pTM +
0.5·disorder). `sample_ranking_score` = 0.8·ipTM + 0.2·pTM + 0.5·disorder − 100·has_clash: a sorting key (−100…1.5),
not a probability. Read `chain_pair_iptm`, inter-chain PAE, `has_clash`; rank across all seeds of one run. pLDDT bands
are AlphaFold conventions. ([08 "Ranking", "Interpretation guardrails"](../references/08_outputs_and_confidence.md);
[07 §3](../references/07_msa_templates_weights.md).)

## 10 — preview2-weights-on-v050

No. Preview-2 (`openfold3-p2-155k`) is registered for `>=0.4,<0.4.4dev0`; 0.5.0 refuses the name, and by path the
version-tensor check is expected to raise (untested). Reproduce with the legacy `openfold3/` kit (0.4.1,
`OPENFOLD3_CKPT`) or an upstream 0.4.x env. New work: `openbind-2025-06-30-174k` → `of3-ob-2025-06-30-174k.pt`,
sha256 `bd43301c…8e29e4` (release note's `-06-03-` is a typo). Different checkpoints are not directly comparable.
([07 §8](../references/07_msa_templates_weights.md); [06 §1](../references/06_kit_modes_and_multigpu.md);
[11 §2](../references/11_decision_trees.md).)

## 11 — affinity-not-supported

No affinity in v0.5.0: structures + pLDDT, PAE/PDE, pTM/ipTM, `chain_pair_iptm`, `bespoke_iptm`, ranking score.
`affinity.yaml` only sets presets and a seed; OpenBind steering is branch-only. Poses for 50 compounds are possible (one
JSON, one call, `--use-msa-server false` unless approved), and protein–ligand ipTM is a pose-confidence self-estimate,
not potency. For affinity: Boltz-2 (boltz skill if installed, else its upstream docs), physics-based methods, assays.
([00 "What OpenFold3 is", "Claims never to make"](../references/00_scope_and_trust.md);
[08](../references/08_outputs_and_confidence.md).)

## 12 — bare-help-cutlass

Not broken by itself: on GPU-visible nodes the bundled `cutlass_library` parses `--help` at import and prints only
`--disable-cutlass-package-imports`; GPU-less nodes print the click group (`align-msa-server`, `predict`, `train`).
Capture `run_openfold predict --help` (on a CPU node of the same image if needed; hijacking of `predict --help` on GPU
nodes is unverified) and compare with 03. Prove the install with the probe, pin check, sha256 and GPU fixture.
([03 trap 5](../references/03_cli_reference.md); [02 "Verify after install"](../references/02_install_and_environment.md).)

## 13 — jit-cache-home-quota

Home writers: `~/.triton` (stock, or kit without `--config`), `~/.cache/torch_extensions`,
`$XDG_CACHE_HOME/openfold3_ob0_opt/` digest memo (also written by `check`), `~/.openfold3`, a kit JIT root under a
home `TMPDIR`. Measured 668–1 013 files / 40–65 MB per job. Per job, node-local `MODEL_OPT_JIT_ROOT`,
`TRITON_CACHE_DIR`, `TORCH_EXTENSIONS_DIR`, `XDG_CACHE_HOME`, `TMPDIR` (+ `CUDA_CACHE_PATH`, `NUMBA_CACHE_DIR`,
`OPT_CORE_VERDICT_DIR`); pass `--config`; forward by prefix under `apptainer --cleanenv`; weights on project storage.
`du -sh` first; filter audits by tool pattern; delete only after confirmation. `--no-compile` is a no-op.
([02 Route 3](../references/02_install_and_environment.md); [06 §12](../references/06_kit_modes_and_multigpu.md);
[10 "Containers, paths and caches"](../references/10_troubleshooting.md).)

## 14 — n-gpu-pocket-constraint

Under `--n_gpu`, a `pocket_constraint` query runs unsharded through the stock route on one GPU
(`tp:pocket_unsharded`); the rc is that stock call's, hence the OOM. Options: single-GPU `--mode big` (no `--n_gpu`;
2 000 ≥ 1 401 polymer tokens engages row blocks; check `of3o_gate` on the ACTIVE line; untested with a pocket), remove
the pocket key to allow sharding (loses the bias), or a bigger card. Multi-GPU = one node, one task, P ∈ {2, 4, 8};
one large query per call (chunk plan sums polymer residues). Nothing multi-GPU validated at the measured site.
([06 §5](../references/06_kit_modes_and_multigpu.md); [10 "Multi-GPU"](../references/10_troubleshooting.md).)

## 15 — refresh-skill-maintenance

Maintenance route only ([maintenance.md](../references/maintenance.md)): no probe, install, download or prediction.
Confirm v0.6.0 exists (release page: date, commit, body). Back up; preserve `lessons.md` and `site_config.local.md`.
Diff the listed files against v0.5.0; update owning references together (03; 04 + `make_query.py` + templates; 07/02;
06; 08 + summarizer; 10/11; 01 and maintenance.md). If the kit does not pin the new tag, say so (it refuses unpinned
versions). Snapshots outside the package; run `tests/validate_static.py` and `quick_validate.py`; rehearse three
requests; privacy-review the diff. The 2026-09-22 validation stays historical; new release = source-reviewed, not
host-validated. (SKILL.md "Update this skill".)

## 16 — missing-checkpoint-no-download

v0.5.0 `predict` never downloads (help text outdated). With consent (~2.3 GB): `setup_openfold --config setup.json`
with `openfold_cache` and `param_directory` both set (also installs the CCD into Biotite; `--non-interactive`
ignores `$OPENFOLD_CACHE`), or `run.sh install --weights DIR`, or `aws s3 cp
s3://openfold3-data/openfold3-parameters/of3-ob-2025-06-30-174k.pt <dir>/ --no-sign-request`. Require sha256
`bd43301c…8e29e4`, 2 287 872 989 bytes. Point predict at it with `--inference-ckpt-path`, or via
`$OPENFOLD_CACHE/ckpt_root` (fix a stale pointer). ([02 "Weights and CCD"](../references/02_install_and_environment.md);
[03 §4, trap 4](../references/03_cli_reference.md); [07 §8](../references/07_msa_templates_weights.md).)

## 17 — openfold-v1-routing

`run_pretrained_openfold.py` and `finetuning_*.pt` belong to the AlphaFold2-era OpenFold (`aqlaboratory/openfold`),
not OpenFold3. This skill covers OpenFold3 only: no command for the older tool; point to its own documentation.
Alternatives: OpenFold3 (`run_openfold predict`, OpenBind-0, probe first) or the AlphaFold2/ColabFold skill if installed
(otherwise its upstream docs).
(SKILL.md intro; [trigger tests, ambiguity policy](../tests/trigger_tests.md).)
