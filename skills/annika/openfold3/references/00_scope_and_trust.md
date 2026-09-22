# 00 — Scope and Trust

## What OpenFold3 is

OpenFold3 (`aqlaboratory/openfold-3`, Apache-2.0) is an open AlphaFold3-class **cofolding** model. It predicts one joint
all-atom structure for protein, RNA and DNA chains (standard and modified residues), small-molecule ligands (SMILES or
CCD codes) and ions. It uses an MSA module and template embedder, a recycled Pairformer trunk, a diffusion sampler and
confidence heads. The CLI is `run_openfold predict` (v0.5.0, released 2026-08-21, commit `c4771653`). The project aims
to reproduce AlphaFold3. Its own reports say it is not yet at parity on every modality (see `09_validation_and_benchmarks.md`).

**Outputs at v0.5.0: structures (mmCIF by default) plus confidence (pLDDT, PAE/PDE, pTM/ipTM, ranking score). Nothing
else.** There is no affinity head, no binding-energy output and no pose score beyond these confidences
(`openfold-3@v0.5.0:openfold3/core/runners/writer.py`; details in `08_outputs_and_confidence.md`). The runner example `examples/example_runner_yamls/affinity.yaml`
only sets the `predict` + `low_mem` presets and a seed. It was added with a Docker image for an external affinity tool
(upstream PR #102) and does not add an affinity output to OpenFold3. **[source]**

## What OpenBind-0 is

- **Checkpoint:** `openbind-2025-06-30-174k` → file `of3-ob-2025-06-30-174k.pt`. It is the default checkpoint of v0.5.0 and
  loads only on `>=0.5.0` (`openfold3/entry_points/parameters.py`). **[source]**
- **Origin:** trained by the OpenBind Consortium on a near-final OpenFold3 architecture. Training data are PDB entries up to
  30 June 2025 and contain no OpenBind data. The checkpoint was selected for protein–ligand performance
  (announcement, 2026-08-21). **[docs]**
- **Chemical steering:** the announcement describes inference-time chemical steering that improves ligand validity. **That
  code is not in the `v0.5.0` tag or in `main` at `68b9c5e7` (2026-09-22).** It exists only on the development branch
  `feature/stereo-steering-framework`. Do not tell users that v0.5.0 steers ligands. **[source]**
- **Not a target guarantee:** OpenBind's own results vary widely by target, from high success on one protease to below 10 %
  on two polymerases (`09_validation_and_benchmarks.md`). **[docs]**

## What the kits are

`anthropics/uplifting-biomolecular-modeling` @ `f4f62fa` (2026-09-17) is an Apache-2.0 **"not maintained"
reference release** from Anthropic. It accepts no pull requests. It wraps the pinned upstream wheel without editing it and
adds modes `off | exact | fast | big` (`--n_gpu 2|4|8` under `big`) behind `run.sh pred|check|warm|install`.

| Kit | Upstream | Weights | Status in this skill |
|---|---|---|---|
| `openfold3_ob0/` | 0.5.0 (`v0.5.0`, `c4771653`) | OpenBind-0 `of3-ob-2025-06-30-174k.pt` (`OPENFOLD3_OB0_CKPT`) | **Default kit** |
| `openfold3/` | 0.4.1 (`d12f5955`) | preview-2 `of3-p2-155k.pt` (`OPENFOLD3_CKPT`) | Legacy, for reproducing old results only. Preview-2 weights do not work on `>=0.5` |

Details are in `06_kit_modes_and_multigpu.md`. Stock OpenFold3 needs no kit. The kit is an optional speed and memory layer.

## State machine (what you may do)

The machine running the agent is **not assumed** to be the OpenFold3 runtime. Your state depends on having a
**current** probe report (`scripts/openfold3_env_probe.py`) from the actual target host, captured in this session.

| State | Meaning | You MAY | You MUST NOT |
|---|---|---|---|
| **UNCONFIGURED** | No probe report captured this session for the target | Explain OpenFold3, OpenBind-0 and the kits. Draft query JSON. Write command text labelled `# template — not run`. Cite sources | Say a machine can or cannot run it. Run `run_openfold`/`run.sh`. Install or download anything |
| **PROBED** | A fresh probe report exists for this host | All of the above, using the host's **real** paths, GPU, container and checkpoint. Give a readiness verdict and an install/update plan. Run inspection commands: `--help`, and the `run.sh check` dry run (not side-effect free: it re-hashes the 2.3 GB checkpoint, rewrites the weights-digest memo and may create a JIT cache directory, so tell the user). With consent, run the public GPU fixture (ubiquitin, `--use-msa-server false`): the only prediction allowed at PROBED | Install or download weights/CCD without explicit per-action confirmation. Run any user input before the fixture passes (VALIDATED) |
| **VALIDATED** | The probe shows a runnable CLI (stock or kit), a checkpoint with the expected sha256, the CCD installed and a GPU with compute capability ≥ 8.0 for kit modes, and a small GPU fixture has passed on this host (recorded in the site config; `02_install_and_environment.md`) | After **explicit per-action confirmation**, run real predictions with safeguards: fresh output dir, `--use-msa-server false` unless approved, no `set -e`, report the rc | Start private, large, multi-seed or `--n_gpu` jobs without discussing cost, privacy and memory first. Claim a mode or size range is validated beyond what was actually tested |

- The probe's own verdict (printed `>> HOST VERDICT:`, JSON `verdict.state`) describes the host, not the session: `UNCONFIGURED` = no OpenFold3 runtime found there (you
  are PROBED: the readiness verdict is "not installed", give an install plan); `PROBED` = runtime found, blockers remain;
  `VALIDATED-CANDIDATE` = runtime, OpenBind-0 checkpoint and a GPU route with no blockers. Record a candidate as
  `state: PROBED` in the site config. The probe never reports `VALIDATED`: only the GPU fixture passing on this host does.
- A probe report goes stale when the host, container image, environment or session changes. Re-probe then, and never
  carry a verdict from one machine to another.
- `run.sh check` returning rc 0 with `gpu=none` on a GPU-less login node is a dry run. It **is not a GPU proof**.
- A successful prediction is not a weights-digest check. The kit runs an unknown checkpoint with a `WARNING: WEIGHTS unknown`
  line.
- After probing, write or update `configs/site_config.local.md` from `configs/site_config.template.md`.
  A sanitized, validated example is in `configs/site_config.example.md`.

## Source trust ladder (highest first)

1. **Live behaviour on the target host:** `run_openfold predict --help`, the kit usage text, `ACTIVE`/`LEVER`/exit-rule
   lines, and real output trees. This is authoritative for that install only.
2. **Pinned source:** `openfold-3@v0.5.0` (and `0.4.1` for the legacy kit), plus kit `run.sh`,
   `opt/<pkg>/cli.py`, `modes.py` and `stock/PINS.json` at `f4f62fa`.
3. **In-repo docs at the pinned tag:** upstream `README.md`, `docs/source/*.md` and examples; kit `README.md`, `STOCK.md`
   and `CHANGES.md`.
4. **Rendered docs:** ReadTheDocs `stable` (= v0.5.0). `latest` tracks upstream `main`, not the release.
5. **Papers, reports and announcements:** OpenFold3 preview/preview-2 reports, the OpenBind-0 announcement, the
   Anthropic report and AlphaFold3. Use them for methods and claims, never for CLI syntax.
6. **Community:** GitHub issues, cited by number and date. Treat them as leads, never as ground truth.
7. **LLM summaries** (including this skill's prose): navigation only. Re-check against rungs 1–3.

Precedence rules: for upstream flags, the upstream source at the kit-pinned tag wins. For kit flags, `run.sh` and `cli.py`
win over kit README prose. When live help disagrees with the docs, trust live help and name the host it came from.
Known doc-vs-source conflicts include:
- bare `--use-msa-server` in the docs (the flag takes a value);
- chain-level `use_msas` in the docs (the switch belongs at query level);
- help text saying `predict` "will attempt to download" (v0.5.0 raises instead);
- the release-note spelling `openbind-2025-06-03-174k` (the registry key is `-06-30-`);
- kit README prose that every command takes `--config` (`install` rejects it).

The owning references cover each one.

## In scope

Explain OpenFold3, OpenBind-0 and the kits. Probe a host read-only. Write and validate query JSON. Generate
`run_openfold predict`, `setup_openfold`, `align-msa-server` and kit `run.sh pred|check|warm|install` commands. Choose
between stock and kit modes. Plan the MSA route and weights. Read outputs and confidence. Troubleshoot. Maintain this skill
(`maintenance.md`).

## Out of scope

- **Training and fine-tuning** (`run_openfold train`, dataset caches, training recipes). Point to upstream docs only.
- **The PDB and training-data pipeline** (dataset preprocessing, distillation sets). Local MSA database builds are
  pointers only (`07_msa_templates_weights.md`).
- **Validation claims for ROCm (AMD), Apple-Silicon MPS or CPU.** Upstream ships these environments. This skill has not
  validated them. The kits are NVIDIA-only (compute capability ≥ 8.0).
- **Upstream `main` or newer releases under the kit.** The kit refuses any `openfold3` other than its pin (exit 3).
- **Wet-lab conclusions.** Structures and confidences are hypotheses, not measurements.

## Claims never to make

| Do not say | Why / what is true |
|---|---|
| "`fast`/`big` are as accurate as stock" | The report found no significant pooled change, but small losses cannot be ruled out. OpenFold3-p2 Fast with target weighting was −3.4 points, with a CI ending just below zero. Fidelity was not calibrated on the measured site |
| "`exact` output is bit-identical to stock" (unqualified) | Only under `--det 1` on both sides. Stock itself varies run to run at production settings |
| "`big` handles 5 000 / 6 000 / 17 000 tokens" as a promise | These are H100 figures at stated settings. The 17 000 figure came from shortened one-recycle probe runs. Capacity depends on card, input composition and settings |
| "Speed-up X× will hold on your GPU" | Speed-ups are hardware-, size- and batch-specific, and the ≈45 s startup per call dilutes them |
| "pLDDT/ipTM prove the structure or binding" | These are the model's self-estimates. The OpenFold3 reports show that confidence ranking can fail to pick the best sample (their ranked gap to AlphaFold3 exceeds the oracle gap) |
| "OpenBind-0 is validated for your target" | Results vary widely by target. Recommend orthogonal checks |
| "OpenFold3 predicts affinity" / "v0.5.0 steers ligand chemistry" | Neither is true at v0.5.0 |
| "OpenFold3 is a bitwise AlphaFold3 reproduction at parity" | That is a project aim. The reports show AlphaFold3 still ahead on some modalities |
| "`covalent_bonds`, `sdf_file_path`, multiple `ccd_codes` work" | They are in the schema but not implemented or not consumed at v0.5.0 (`04_input_query_format.md`) |
| "The kit is supported / maintained" | It is an unmaintained reference release |

## Privacy, cost and licensing

- **Sequence egress.** `--use-msa-server` falls back to the config default **True** when unset. Protein chain sequences
  then go to the public ColabFold MMseqs2 server (`https://api.colabfold.com`, `colabfold_msa_server.py`). Template hits
  lead to RCSB requests (chain-ID mapping via `data.rcsb.org/graphql`, structure fetches), which reveal hit PDB IDs, not
  your sequence. Require explicit approval for any server use. For unpublished sequences, use precomputed MSAs or
  `--use-msa-server false` (single-sequence, lower accuracy). The server's retention and terms were not reviewed. Details:
  `07_msa_templates_weights.md`.
- **Cost.** Every call pays about 45 s of startup and checkpoint loading in every mode (kit README). Wall time scales with
  tokens × seeds × samples (defaults: 1 seed, 5 samples). The first `fast` call added 22–39 s of JIT compilation at the
  measured site. State the expected GPU hours before long, multi-seed or multi-GPU runs.
- **Licences.**
  - Upstream code: Apache-2.0.
  - Kit code: Apache-2.0 plus `NOTICE`. The kit's `stock/` tree keeps upstream's licence.
  - OpenBind-0 weights: Apache-2.0 per the OpenBind announcement. The kit's `PINS.json` notes that upstream states no
    licence for the parameters.
  - Preview-1/2 weights: Hugging Face `OpenFold/OpenFold3` is behind a contact-information gate and labelled Apache-2.0
    (the preview-2 files are also on the public S3 bucket; legacy, not loadable on `>=0.5`).
  - Training data (AWS open data) and the OpenBind benchmark (Zenodo): CC BY 4.0.
  - Keep each artefact's own terms and do not copy one licence to another. This skill gives no legal advice.
- **Third-party notice.** This skill is an independent, unofficial community resource. It is not affiliated with or
  endorsed by the OpenFold Consortium, the AlQuraishi Lab, the OpenBind Consortium, Google DeepMind (AlphaFold) or
  Anthropic (authors of the uplifting-biomolecular-modeling kits). Product names only identify the software; trademarks
  belong to their owners. The skill ships no OpenFold3 code, kit code or weights. When publishing results, cite per
  `01_source_map.md` "How to cite".
