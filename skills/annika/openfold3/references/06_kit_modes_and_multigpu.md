# 06 — Kit modes, `big` and multi-GPU (`openfold3_ob0`)

Pins: `anthropics/uplifting-biomolecular-modeling` @ `f4f62fa` (Apache-2.0, "unmaintained reference release"), kit directory
`openfold3_ob0/` = OpenFold3 **0.5.0** + OpenBind-0 (package `openfold3_ob0_opt` 0.8.18.1 [live]). Paths below are relative to
that directory (`common/` = the shared core). Labels: **[source]** kit code (`opt/openfold3_ob0_opt/*.py`), **[docs]** kit
README / CHANGES / STOCK / `configs/*.env`, **[paper]** Anthropic report (2026-09-17), **[live]** captured on a real install
(CPU node unless stated), **[measured]** a Slurm HPC site with A100-SXM4 40 GB and H100 94 GB nodes (validated 2026-09-22;
single-sequence inputs of 13–995 polymer residues = 52–995 model tokens, one seed × 5 samples, no templates; full numbers in
[09_validation_and_benchmarks.md](09_validation_and_benchmarks.md)). Flags, variables, exit codes:
[03_cli_reference.md](03_cli_reference.md) §6–8. Commands are templates (`# template — not run`).

## 1. Which kit

| | `openfold3_ob0/` — **default** | `openfold3/` — legacy |
|---|---|---|
| Upstream + weights | 0.5.0 + OpenBind-0 `of3-ob-2025-06-30-174k.pt` | 0.4.1 + preview-2 `of3-p2-155k.pt` |
| Checkpoint / mode variables | `OPENFOLD3_OB0_CKPT` / `OPENFOLD3_OB0_OPT` | `OPENFOLD3_CKPT` / `OPENFOLD3_OPT` |
| Extra options | `--z-dtype`, `--conf-dtype`, `--use-tf32`, `--inference-ckpt-name`; `install --ccd/--wheel/--src` | none of these; `install --weights` only; `--upstream-fix OF3-001` (templates) |
| README `big` headline (H100 80 GB) | up to 5 000 tokens on one GPU | up to 6 000 tokens |
| Use for | all new work | reproducing preview-2 results only |

Each kit checks its own upstream install file for file (`stock/check_pins.py`, rc 3 otherwise), so each needs its own
environment or image; preview-2 weights do not load on ≥ 0.5.0. Modes, gates (1 401 / 4 500), card files and exit codes have
the same design in both [source]. Everything below is `openfold3_ob0`.

## 2. The four modes

Precedence: `--mode`, else `OPENFOLD3_OB0_OPT`, else **`fast`** (the kit default); a `--mode` that disagrees with an exported
`OPENFOLD3_OB0_OPT` → rc 2 [live]. A mode is all of its levers (the kit's word for one switchable optimization): a lever that
cannot install, or a run that ends with a requested lever unavailable (`partial`), is rc 3 — never a quiet subset [source].

| Mode | What changes vs stock (`CHANGES.md`, `modes.py`) | Numerics | Kit / report claim | Site [measured] |
|---|---|---|---|---|
| `off` | Nothing. Upstream `run_openfold predict` in a clean subprocess (kit variable families stripped, no kit directory on `PYTHONPATH`) on the kit's **stock configuration** `stock_cueq_bf16_notune_predict.yml`: cuEquivariance + Triton triangle kernels, DS4Sci off, `bf16-mixed`, chunk 1024, tuner off. Plus pin and weights checks. Not upstream's shipped preset (Triton only, `32-true`, tuner on) | stock | baseline | bare `run_openfold predict` (shipped preset) took 57.2 / 45.4 s vs `off` 53.3 / 41.8 s on ubiquitin (A100 / H100) |
| `exact` | Placement, scheduling, caching: `fast_init`, `paircache`, `templ_distinct`, sampler CUDA graphs up to 512 polymer tokens (`cuda_graphs`, `graphs_strict`), `atom_hoist`, `castcache`, `apb_hoist`, memory release (`post_release`, `postfwd_mem`), host-side `loader_workers`, `fastjson`, `writer_overlap`, `hostfeat`, `ckpt_mmap`. Bit-exact kernels (`exactln`, `triatt_exact`, `trimul_exact`, `transition_exact`) serve a call class only where proven bit-identical (in-process `torch.equal`, or the core's vouched table); elsewhere the stock call runs. Hand-off and confidence stay upstream's fp32. Base YAML: the stock configuration | same algorithm; **byte-identical to `off` only with `--det 1`** | "identical outputs, faster" [docs]. Report: smaller, inconsistent forward gains, once slower than default [paper] | wall 1.12–1.40× (A100) / 1.11–1.37× (H100); peak 0.98–1.20× of `off` up to 632 residues, 0.76–0.87× at 995 |
| `fast` | `exact`'s levers minus the bit-exact kernels, plus fused Triton pair cells (`trimul_v4`, `triatt_block`, `pair_transition`), flash attention in trunk and diffusion transformer (`apb_trunk`, `dit_attn`, `dit_glue`), fused atom attention (`atom_window`), `token_agg`, `templ_embed`, `ln_provider`, a trunk CUDA graph up to 1 024 tokens (`trunk_graph`), bf16 diffusion roll-out at every size (`rollout_bf16`; an optional `OPENFOLD3_OB0_OPT_ROLLOUT_MIN_TOKENS` threshold returns smaller inputs to fp32), bf16 trunk hand-off (`z_dtype`) and confidence phase (`conf_dtype`), `tuner_guard`, `alloc_expandable`. Base YAML: the stock configuration; no sampler-graph cap | bf16 re-association and fused-kernel rounding: coordinates and confidences move | "within stock's seed-to-seed variation" [docs]. Report (H100 80 GB, precomputed MSAs, 10 recycles): forward geomean 4.93×; FoldBench-Lite acceptable top-1 56.6 % vs 58.2 % default [paper] | wall 1.24–2.13× / 1.21–1.83×; peak 0.40–0.55× of `off` from 508 residues (above `off` on the smallest inputs). **Fidelity not calibrated**: top-model CA RMSD vs `off` up to 29 Å on low-confidence single-sequence inputs |
| `big` | Below the item gate (1 401 polymer tokens): **exactly `fast`**, graphs included. At or above it: row-block pair stack streamed from a pinned host snapshot, row-block inputs, recycling and templates, chunked confidence heads from 2 048 tokens; drops `fast`'s graphs and caches. Base YAML `big_bf16_c16_predict.yml`: chunk 16, tuner off, third-party pair kernels off, `bf16-mixed` | as `fast` | "lowest peak GPU memory … up to 5,000 tokens on one GPU" (README) [docs]. Report: 6 000 on one GPU, 17 000 on two (two-GPU value from one-recycle probes: what fits, not a run time) [paper] | equal to `fast` at every tested size; nothing at or above the gate was run |

Startup dominates small calls: every call spends ≈ 45 s starting Python and loading the 2.3 GB checkpoint, in every mode
(kit README "Where the gain is") [docs]. Put many queries and seeds in one call to see the gain.

## 3. `--det 0|1`

- `0` (default) or `1`; else rc 2 (`--det must be one of (0, 1)`) [live]. `pred` and `check`, every mode including `off`.
- `1` applies one recipe (`det.py`): `CUBLAS_WORKSPACE_CONFIG=:4096:8` exported before CUDA starts, `OF3_DETERMINISTIC=1`,
  `torch.use_deterministic_algorithms(True)`, cuDNN deterministic with benchmark off, and `OF3_GRAPHS_STRICT=1` on graphed
  calls. Under `off` the stock child gets it through a start-up `sitecustomize` (`det_site/`). Runner YAML and seeds do not
  change (`off`/`exact` keep the same stock file).
- `exact --det 1` equals `off --det 1` byte for byte [docs]; the site confirmed 60/60 model/confidence file pairs at 13 and
  508 polymer residues on both cards [measured]. Plain `off` is not reproducible run to run, and ordinary `exact` does not
  match it (they share non-deterministic kernels).
- `fast` and `big` use different arithmetic: never expect `off`'s bytes from them, with or without `--det 1`. The kit records
  `big` as run-to-run bitwise under `--det 1` [source, not tested here]; `big --n_gpu P` matches single-GPU runs only within
  tolerance [paper].
- Cost [measured, first runs incl. cold caches]: `off --det 1` 0.73–0.80× the speed of `off`; `exact --det 1` 0.92–1.05×
  (1.19–1.44× faster than `off --det 1`). Use `--det 1` for identity audits and reference runs, not throughput.

## 4. `big`: gates, row blocks, host streaming

| Gate (polymer tokens) | Default [source `modes.py`] | Override | At or above the gate |
|---|---|---|---|
| Item gate `OF3O_MIN_TOKENS` | **1 401** (`OF3O_GATE_BY_CARD` A100 = H100 = 1401; other cards `OF3O_GATE_DEFAULT` = 1401) | `<int>`, or `none` = always engaged | offload port engages: row blocks + host streaming |
| Confidence gate `CONF_MIN_TOKENS` | 2 048 (constant) | — | `confhead`, `conf_chunked`: PAE/PDE heads per row block; the [S,N,N,64] logits never exist |
| Reach gate `OPENFOLD3_OB0_OPT_REACH_GATE` | 4 500 (A100 = H100 = default) | `<int>`, or `none` = never | full-N² fused pair cells step aside (`reason=reach_gate`); row-block statements serve the trunk |

**Polymer tokens** (`inputs.py`): residues of the protein, RNA and DNA chains × the number of `chain_ids`, per query. Ligand
atoms are model tokens but are **not counted**, so the count is a lower bound. Two copies of a 700-residue chain = 1 400 →
below the gate; three copies of a 500-residue chain = 1 500 → engaged.

How the item gate decides:
- **Per item.** A query set that straddles the gate runs as two sequential passes into the same output directory, below-gate
  items first; the top-level `experiment_config.json` / `model_config.json` then describe the engaged pass.
- **No count → engaged** (fail-safe for memory): a ligand-only query (count 0), an unreadable JSON, `check`, `warm`, and the
  env route (§9).
- The default is "the largest input whose `fast` peak leaves ≥ 15 % of the card free, + 1", sized on 80 GB cards. The live
  line reads e.g. `of3o_gate=aside:lt_min min_tokens=1401(card:A100)` [measured].

**At or above the gate** (`CHANGES.md` "big"): `trimul_hostsnap` streams triangle multiplication in row blocks from a pinned
host snapshot of z; `triatt_lean`, `trans_inplace`, `input_rows`, `recycle_rows`, `cond_once`, `templ_host` (template pair
features on the host), `bigln_guard`; `host_pool` is one pinned host pool (budget `OF3O_PIN_BUDGET_GB=600`; a buffer over it
becomes pageable, counted). It drops `cuda_graphs`, `graphs_strict`, `paircache`, `atom_hoist`, `dit_glue`, `castcache` and
`trunk_graph`, so each step is slower than `fast`: **`big` trades speed for memory.**

**Host RAM.** The pair snapshot alone is N² × 128 channels × 2–4 bytes, about 6–13 GB at 5 000 tokens (arithmetic); templates
and pools come on top. Request generous host memory; there is no measured host-RAM figure [unverified].

**Cards below 80 GB.** The gates are not scaled to memory. On a 40 GB A100, `fast` below 1 401 polymer tokens could run out of memory
before `big` engages, especially with MSAs [unverified]. Peak memory does not follow the polymer count alone: at the site
[measured] `fast` peaked at 13 662 MiB at 995 residues, but upstream's `query_protein_ligand*` examples (4 × 158 residues =
632, plus ligands) peaked at 36 346–39 924 MiB under `off`/`exact` on the A100 40 GB, against 14 910–17 472 MiB under `fast`.
Lowering `OF3O_MIN_TOKENS` is an **untested** override: validate it before relying on it.

## 5. `--n_gpu 2|4|8` — one prediction across P GPUs of one host

**Rules** [source `modes.py`, `tp.py`; refusals live]:
- P ∈ {2, 4, 8}, and only under `--mode big`. Another value (`n_gpu=3 is not a GPU count this kit runs`), or P > 1 under
  `exact`/`fast`/`off` (`n_gpu>1 requires --mode big`) → rc 2 [live].
- Fewer visible GPUs than P → rc 3 at `pred` (visibility: `CUDA_VISIBLE_DEVICES`, else `nvidia-smi -L`). `check` does not count
  GPUs (`check --mode big --n_gpu 2` → rc 0 on a GPU-less node [live]); `warm` ignores `--n_gpu`.
- `OPENFOLD3_OB0_OPT_N_GPU` supplies the default.

**How it runs.** The `pred` process is a **launcher**: it spawns P rank processes, one GPU each via `CUDA_VISIBLE_DEVICES`,
joined in one NCCL group over a loopback rendezvous (`OF3TP_ADDR`, `OF3TP_PORT`) — one host only, no multi-node mode. Rank 0
featurises and broadcasts (`OF3TP_DATA_FORM=rank0_bcast` default); the ranks' input digests must agree (`feats_ranks_differ`
refuses). Each rank holds a row shard of z through the pair stack, MSA module, template embedder, diffusion conditioning and
confidence heads. `sample_loop` runs one diffusion sample per pass, so device memory does not depend on
`--num-diffusion-samples`. Numerics are `fast`-class: sharded reductions reorder sums, never bitwise equal to one GPU.

**Outputs.** Rank 0 writes the normal tree `<output-dir>/<query>/seed_<s>/…`; every rank's log goes to
`<output-dir>/_tp/rank<r>.log`; copies from ranks > 0 go to `_tp/rank<r>/`, are compared with rank 0 and removed; the pinned
runner YAML is `<output-dir>/tp_predict.yml`. **Structure first:** each sample's `model.cif` is written when the sampler
returns (pLDDT column 0.00) and overwritten after the confidence pass (`OF3TP_STRUCTURE_FIRST=0` restores stock's order); a
model left without confidences → `incomplete`, rc 1. The launcher logs `launch … backend=nccl gpus=… card_bytes=… chunk=…`
and, last, `census … ranks_identical=… outputs_identical=… smi_peak_mib[…]`.

**Chunk plan** (`tp.CHUNK_PLAN`, sized on 80 GB cards), from the **sum of polymer residues in the whole query file** — send one
large query per call:

| Polymer residues | ≤ 2 500 | ≤ 4 000 | ≤ 6 500 | above |
|---|---|---|---|---|
| Chunk | 128 | 64 | 32 | 16 |

- Halved, down to 16, until every rank owns at least one 16-row block. `OF3TP_CHUNK=<n>` overrides it.
- A card below 79 GB (`tp.MIN_CARD_BYTES`) prints `NOTE chunk plan table (CHUNK_PLAN) is for >=79 GB cards; using it on <m> GB
  … may OOM` — a note, not a refusal (a 40 GB A100 gets it). Cards of 94 GB or more get no note and no larger plan.

**Served unsharded through the *stock* route on one GPU** (named; rc of that stock call): a query with `pocket_constraint`
(`fallbacks=tp:pocket_unsharded=1`), or one too small for a 16-row block per rank (`tp:small_n_unsharded=1`). A large pocket
query can therefore run out of memory as stock on one card.

**The launcher pins onto the YAML:** the chunk, all five chunk tuners off, the Triton / cuEquivariance / DS4Sci / LMA pair
kernels off, host offload of the trunk MSA and template modules off. **Resources:** one node, **one task**, P GPUs, CPUs for P
ranks plus loaders, generous host RAM. Do not start P tasks (`srun -n P`): the kit spawns its own ranks.

```bash
# template — not run. <KIT> = "bash <kit_dir>/openfold3_ob0/run.sh" or "apptainer run --nv <image>.sif" (absolute paths)
#SBATCH --nodes=1 --ntasks=1 --gpus-per-node=<P> --cpus-per-task=<n_cpu> --mem=<host_ram> --partition=<gpu_partition>
unset OPENFOLD3_OB0_OPT
export MODEL_OPT_JIT_ROOT=<node_local_dir>/jit TMPDIR=<node_local_dir>/tmp OPENFOLD3_OB0_CKPT=<weights_dir>/of3-ob-2025-06-30-174k.pt
<KIT> pred --config <card> --mode big --n_gpu <P> --query-json <abs>/big_query.json \
  --output-dir <abs>/out_big_x<P> --use-msa-server false
rc=$?; echo "rc=$rc"                          # no set -e: rc 3 and 5 are results
```

**Evidence:** `configs/a100.env` and `registry.py` record `big --n_gpu 2` as tested on A100-SXM4-80GB; the report's two-GPU
figure is a probe; for P = 4 and 8 no test record was found [unverified]; the measured site ran no multi-GPU job.

## 6. `--config <card>` and unlisted cards

`--config a100|h100|h200|b200|b300` sources `configs/<card>.env` on `pred`, `check` and `warm` (missing file → rc 2 [live];
`install` refuses `--config`, rc 2 [live]). The files carry **deployment settings only** (no mode, no lever switch), fill
only unset variables, and import the package and run the core pin gate (rc 3 on failure). They differ from each other only in
`MODEL_OPT_TARGET_GPU` [source]. Variables they set: [03_cli_reference.md](03_cli_reference.md) §7.

| Card file | cc | Kit test record [source `registry.py`] | Differences (from the file's own list) |
|---|---|---|---|
| `h100` | 9.0 | every lever (`TESTED_SM = sm90`) | reference |
| `a100` (80 and 40 GB) | 8.0 | `A100_TESTED` on A100-SXM4-80GB: exact, fast, big, `big --n_gpu 2`; no A100 record for `writer_overlap`, `hostfeat`, `ckpt_mmap`, `trimul_provider`, `trimul_form` | own launch tiles; under `exact` a transition kernel not proven on this stack runs the module's own code (named). The 40 GB part runs the same code: nothing is sized to its memory except the tp NOTE |
| `h200` | 9.0 | outside the tested set | same cells as H100 (tables are keyed by cc, not memory) |
| `b200`, `b300` | 10.0, 10.3 | outside the tested set | own launch tiles; a Triton build failure falls back to safe settings, named |

- **H100 94 GB (e.g. H100 NVL):** `--config h100` (cc 9.0, the tested class). Gates and chunk plan are the 80 GB values; the
  extra memory is unused headroom. Validated at the site up to 995 residues only.
- **Unlisted card with cc ≥ 8.0** (e.g. sm86/sm89 workstation cards): levers still engage; a lever with no record for the card
  is named `card_support=uncertified:<sm>` [source `opt_core/arch.py`]; a cell with no table row runs the stock statement,
  counted as `fallback:<reason>`. Any card file works (gates are 1 401 / 4 500 everywhere); expect a
  `MODEL_OPT_TARGET_GPU=… but this box is …` note. Below 32 GB you are under upstream's documented floor. All unvalidated.
- **cc < 8.0:** every kit mode → rc 3 (`… below sm80`). `--mode off` runs wherever upstream runs.
- **No `--config`:** `MODEL_OPT_TARGET_GPU` is unset (gates use the same defaults) and `TRITON_CACHE_DIR` is not keyed, so
  Triton falls back to `~/.triton/cache`. Always pass `--config`, or export the cache variables yourself.

## 7. Reading the run log (stderr lines start `[openfold3_ob0-opt…]`)

| Line | Meaning | Action |
|---|---|---|
| `DRY-RUN mode=<m> … gpu=… levers_requested=…` | `check` passed its gates; nothing applied to a model. Adds `refused=<reason>` and rc 3 on failure | rc 0 with `gpu=none` is no GPU proof. With a checkpoint named, `check` still re-hashes it and rewrites the digest memo |
| `ACTIVE mode=<m> line=<l>: <switches> @ <hook chain> openfold3=0.5.0 gpu=… levers_requested=… precision=… graph=… conf_dtype=… z_dtype=… n_gpu=… sharding=… compile=none` (+ `of3o_gate=`, `levers_off=`, `notes=` when they apply) | the mode engaged, with each gate's decision | read `gpu=`, `of3o_gate=` (for `big`) and `notes=` |
| `stock subprocess: …` / `NOT ACTIVE: <reason>` | `--mode off` instead of ACTIVE / the mode could not engage, rc 3 (never a fallback to stock) | — / fix the named cause (§8) |
| `LEVER name=<l> state=on … tier=exact\|tolerance` | lever installed; `tier` is its numerics class | — |
| `LEVER … state=off reason=not_in_line` / `reason=of3o_gate gate=aside:lt_min n_tokens=<n> min_tokens=1401` | not part of this mode / `big` below the item gate [measured] | normal |
| `LEVER … reason=reach_gate` / `reason=levers_off` | reach gate / `MODEL_OPT_LEVERS_OFF` | confirm it was intended |
| `… served=<n> fallback=<m> fallback:<reason>=<k>` | per-call census; calls a lever cannot serve (shape, dtype, layout) ran the stock statement | normal, not an error |
| `[opt_core] CELLS … NAMED_FALLBACK:… served=sdpa:auto` | a call class outside the measured table ran PyTorch SDPA [measured on A100] | report only; outputs unaffected |
| `WEIGHTS pinned …` / `WARNING: WEIGHTS unknown … proceeding` | checkpoint sha256 vs the pin | unknown weights **still run**: stop and check |
| `TEMPLATES DECLARED …` / `TEMPLATES DROPPED …` | template census | DROPPED → rc 5 |
| `pred --mode <m>: exit rule -> <rc> (ok; structures 5/5; templates_dropped=0; partial=False; …)` | the verdict; grep for `exit rule ->` (LEVER census lines follow it) [live] | branch on it |

## 8. Exit 3 — causes and fixes

rc 3 is a result, not a crash: never run the kit under `set -e`. All exit codes: [03_cli_reference.md](03_cli_reference.md) §8;
symptoms: [10_troubleshooting.md](10_troubleshooting.md).

| Named cause | Fix |
|---|---|
| openfold3 not at the pin, file for file (other version, editable checkout, edited file); `reason=package_missing`, core pin gate, `reason=core_missing` | reinstall the pinned stack (`run.sh install`) with the same `python`, or rebuild the image |
| Env route: hook not live at interpreter start (`.pth` absent, stale, or only on `PYTHONPATH`) | install the package into that interpreter, or use `run.sh pred --mode …` |
| An undeclared `OPENFOLD3_OB0_OPT*` name or value — refused in **every** Python process of the environment [live] | unset the typo |
| Conflicting switches, e.g. `--z-dtype bf16 --conf-dtype fp32` [live]; a lever named in `MODEL_OPT_LEVERS_OFF` that cannot leave alone | pass both dtypes as fp32 (§11); unset the switch |
| GPU compute capability < 8.0 | `--mode off`, or another card |
| **Partial line** (`levers_unavailable`): outputs may already be written | the run is not "<mode>": read the LEVER lines; re-run, or exclude the lever deliberately with `MODEL_OPT_LEVERS_OFF` |
| `--n_gpu P`: fewer visible GPUs, ranks that joined ≠ P (`n_gpu_mismatch`) | request P GPUs on one node, as one task |
| `--mode off` with a runner YAML that turns DS4Sci on, on a stack without DeepSpeed's `evoformer_attn` op (`STACK REFUSED`) | drop the key (§10) |

## 9. Env route: `OPENFOLD3_OB0_OPT` in a plain `run_openfold`

`run.sh install` (`pip install -e opt`) puts `openfold3_ob0_opt_autoload.pth` into site-packages. Export
`OPENFOLD3_OB0_OPT=<mode>` and a plain `run_openfold predict` in that environment runs the kit mode (ACTIVE line [live];
`fast` predictions rc 0 on both cards [measured]). Unlike `run.sh pred` [source] it has no kit runner YAML (`fast` forces
`bf16-mixed` but keeps your or upstream's kernel flags), no token count (graph gate `n_tok_unknown`; `big` engages the offload
port **at every size**) and no exit rule (upstream's rc; no `incomplete` / rc 5 checks).
- Use it only for `fast` on an unchanged stock command line; prefer `run.sh pred` for `off`, `exact`, `big` and `--det`.
- The same exported variable silently turns a "stock" baseline into a kit run: unset it for baselines.
- Wrappers that run `apptainer --cleanenv` must forward `OPENFOLD3_OB0_OPT*`, `OF3TP_*`, `OF3O_*`, `MODEL_OPT_*` by prefix [live].

```bash
# template — not run
export MODEL_OPT_JIT_ROOT=<node_local_dir>/jit OPENFOLD3_OB0_CKPT=<weights_dir>/of3-ob-2025-06-30-174k.pt
. <kit_dir>/openfold3_ob0/configs/<card>.env    # keys the Triton cache only because MODEL_OPT_JIT_ROOT is set
OPENFOLD3_OB0_OPT=fast run_openfold predict --query-json q.json --output-dir out \
  --inference-ckpt-path "$OPENFOLD3_OB0_CKPT" --use-msa-server false
```

## 10. `--runner-yaml` overlays with modes

`--runner-yaml` can be repeated; files merge in order, the later file wins. The composed file goes to a temp directory, never
into the outputs, and one `note:` line names every override [source `cli.row_yaml`, live].

| Mode | Base configuration | Your overlay |
|---|---|---|
| `off` | kit stock configuration | your keys win. Naming `shipped_predict.yml` makes upstream's shipped preset the base (= bare `run_openfold`). A DS4Sci key stays on and needs DeepSpeed's `evoformer_attn` op (else rc 3) |
| `exact`, `fast` | stock configuration | the mode's file wins on every key it writes (kernel flags, precision, chunk); a DS4Sci key is overridden to off and named on the `note:` line [live, `check --mode fast`]. Other keys pass through: recycles, seeds, templates, MSA, outputs |
| `big` (1 GPU) | `big_bf16_c16_predict.yml` at or above the gate; the `fast` file below it | as for `fast` |
| `big --n_gpu P` | your overlay composed once, then the launcher's pins | pinned keys win |

Upstream also deep-merges `$OPENFOLD_CACHE/runner.yml` under every run. The kit defaults `OPENFOLD_CACHE` to the checkpoint's
directory, so a `runner.yml` placed next to the weights applies to every call (stderr names it). Example overlay key (the
report's 10 recycles; upstream default 3): `model_update.custom.architecture.shared.num_recycles: 10` (full YAML:
[05_core_workflows.md](05_core_workflows.md) §9).

## 11. Dtype pair rule, lever switches, `--no-compile`

- `--z-dtype` sets the trunk → roll-out hand-off of `s_input`, `s`, `z`; `--conf-dtype` the confidence phase; each
  `bf16|fp32`. Mode words: bf16/bf16 on `fast`/`big`, fp32/fp32 (= upstream 0.5.0) on `exact`. A flag or preset environment
  value wins and ACTIVE shows `source=env`.
- **Pair rule:** `z bf16` with `conf fp32` is refused, rc 3 [live] (`…CONF_DTYPE=fp32 needs …Z_DTYPE=fp32`), because
  upstream's confidence cast follows the hand-off dtype. For fp32 confidences on `fast`/`big`, pass `--z-dtype fp32
  --conf-dtype fp32`. `z_dtype` moves coordinates; `conf_dtype` alone moves only confidences. fp32/fp32 does not turn `fast`
  into `exact`: the fused kernels stay.
- `MODEL_OPT_LEVERS_OFF=<lever>[,…]` runs a mode without the named levers (`levers_off=` on ACTIVE); for ablation or debugging,
  not production. Partners leave together: `cuda_graphs`→`graphs_strict`, `conf_dtype`→`z_dtype`,
  `triatt_block`→`triatt_provider`, `trimul_v4`→`trimul_provider`, `trimul_exact`→`trimul_form`, `conf_chunked`→`confhead`.
  `graphs_strict`, `big`'s offload units and the `--n_gpu` levers cannot leave alone (refused by name). `--mode off` ignores
  the variable [source].
- `--graphs-max-tokens N|always|0|off` caps sampler CUDA-graph capture: `exact` defaults to 512 polymer tokens, `fast` has no
  cap. A cap gives back reserved memory for a few percent of speed.
- `--no-compile` is accepted and does nothing (`compile=none`): no mode uses `torch.compile`.

## 12. JIT compilation, `warm`, caches

- **First call.** A kit mode compiles Triton kernels (≈ 20 s) and runs a one-time kernel self-check (seconds on H100, up to
  ≈ 30 s on A100) [docs]. At the site the first `fast` call cost +22–39 s; `exact`, and `big` below the gate (run after
  `fast`), cost about 0–1 s [measured].
- **`run.sh warm --config <card> --mode <m> --out <dir> [--tiling <t>[,<t>…]]`** runs one public barnase–barstar prediction
  (`1to1` = 199 tokens, default, … `6to6` = 1 194; a comma list meets several size classes in one process) with MSA server
  off, templates off, 1 seed, 1 sample. `warm --mode off` → rc 2 [live].
- **Cache root `MODEL_OPT_JIT_ROOT`.** If unset, `run.sh` uses a private `${TMPDIR:-/tmp}/model_opt_jit-uid<uid>` (mode
  0700; refused if another user owns it, it is group/other-writable, or a symlink). The card file keys caches under
  `<root>/<stack key>/` (e.g. `torch2.10.0-cu128-sm80` vs `…-sm90`), so one root serves several cards. An image with a JIT
  tar uses or seeds from `/opt/jit_cache` (`jit cache: <dir> (<origin>)` line); a read-only preset root is seeded only when
  `MODEL_OPT_STACK_KEY` is preset and that subtree has ≤ 5 000 files. Placement (node-local; 668–1 013 files, 40–65 MB per
  job [measured]): [02_install_and_environment.md](02_install_and_environment.md).

## 13. Security and trust

The kit assumes trusted inputs, trusted weights, and a single-user machine or container (top-level README) [docs].
- **`.pth` autoload hook:** every Python process in the kit environment imports `openfold3_ob0_opt._autoload`; with no mode it
  installs nothing, with a mode it patches upstream in memory at `import openfold3` or exits 3, and an undeclared
  `OPENFOLD3_OB0_OPT*` name exits 3 in **any** Python process [live]. Uninstalling the kit removes it.
- **`sitecustomize` chain:** each kit hook executes the next one named by `OF3T_KIT_LEVERS`, `OF3O_KIT_LEVERS`,
  `OPENFOLD3_OB0_OPT_CONFHEAD_CHAIN` or `OPENFOLD3_OB0_OPT_PAIR_CHAIN`. Whoever controls those variables or `PYTHONPATH`
  controls what runs: never set them by hand or take them from an untrusted job script; keep the kit tree private.
- **Weights are pickles** (`torch.load`): use only the pinned OpenBind-0 file (sha256 `bd43301c…8e29e4`,
  [07_msa_templates_weights.md](07_msa_templates_weights.md)); for other bytes the kit only warns. Caches are digest-checked
  and must be private. Containers run as root; the only sockets are the `--n_gpu` loopback rendezvous.

## 14. What is not validated at the measured site

`big` at ≥ 1 401 polymer tokens (kit evidence: H100 80 GB, README 5 000 tokens) · `--n_gpu` of any P (kit: A100-80GB record
for P = 2, report probe; none found for 4, 8) · `fast` fidelity (report: seed-spread guard, FoldBench-Lite; site: not
calibrated) · H200 / B200 / B300 / other cc ≥ 8 cards (outside the kit's tested set) · A100 40 GB with MSAs near the gate ·
templates and MSA inputs · `fast` / `big --det 1` run-to-run identity · the env route with `exact` / `big` / `--det` · the
0.4.1 kit · ROCm, MPS, CPU (the kit is CUDA-only, cc ≥ 8.0).

## 15. Choose a mode

Decision tree and per-mode summary: [11_decision_trees.md](11_decision_trees.md) §3. In short: `exact` for production,
`exact --det 1` (reference `off --det 1`) for byte identity, `off` for a baseline, `fast` for throughput after a seed-spread
check, `big` for any query at or above 1 401 polymer tokens (the size its gate is built for; below that it *is* `fast`),
`big --n_gpu 2|4|8` when one GPU is not enough (one host, one task). On 40 GB cards ≥ 1 401 tokens is untested (§4). Always pass `--mode`, `--use-msa-server false` unless the server was approved, `unset
OPENFOLD3_OB0_OPT`, and branch on rc 0/1/2/3/5.
