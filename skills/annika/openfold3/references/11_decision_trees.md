# 11 — Decision Trees

Fast routing: follow the arrows; details are in the referenced files. Any branch that installs, downloads, sends
sequences off the host or uses a GPU needs explicit per-action consent (`00_scope_and_trust.md`). Measured numbers come
from one Slurm HPC site with A100-SXM4 40 GB and H100 94 GB nodes (validated 2026-09-22). That ladder was
single-sequence, template-free, 1 seed × 5 samples, 13–995 polymer residues = 52–995 model tokens
(`09_validation_and_benchmarks.md`).

## 1. Stock CLI or kit?

```
Target is Linux x86-64 + NVIDIA compute capability >= 8.0 + driver >= 570?
 ├─ no  -> stock upstream only (pip / pixi / Docker). CPU, Apple MPS, ROCm, cc < 8.0 are
 │         exploratory and not validated here (02)
 └─ yes
     ├─ need align-msa-server, train, an upstream flag the kit does not register,
     │  or an openfold3 version other than 0.5.0            -> stock run_openfold (03 §2-3)
     ├─ need upstream's shipped configuration exactly (32-true, Triton kernels, chunk tuner)
     │                                                       -> bare run_openfold predict, or kit
     │                                                          `--mode off --runner-yaml opt/openfold3_ob0_opt/shipped_predict.yml`
     └─ otherwise                                           -> kit run.sh pred --mode <m> (sections 2-3)
```

- **Kit `off` is not bare stock.** `off` runs the kit's stock configuration: upstream `predict` with cuEquivariance
  triangle kernels, `bf16-mixed` and the chunk tuner off. Bare `run_openfold predict` runs the shipped settings
  (kit `STOCK.md`) **[docs]**.
- **Upstream files are never edited.** The pin check enforces it on every route; kit modes other than `off` patch
  upstream in memory at import (`06_kit_modes_and_multigpu.md` §13).
- **Runner-YAML overlays work on both routes.** Under the kit, the mode's execution keys win, and every override is
  printed.

## 2. Which kit?

```
Which weights must the results come from?
 ├─ OpenBind-0 (of3-ob-2025-06-30-174k.pt, upstream default since 0.5.0) -> openfold3_ob0/  (recommended)
 ├─ preview-2 (of3-p2-155k.pt), to reproduce earlier results             -> openfold3/ (0.4.1 kit, legacy)
 └─ another checkpoint (fine-tune, experiment)                            -> it runs, labelled
        `WARNING: WEIGHTS unknown … proceeding`; the kit's identity/speed evidence is for the pinned
        checkpoint only [inferred] -> validate on your inputs, or use stock
```

- **Weights are not interchangeable.** Preview-2 weights do not load in ≥ 0.5.0, and OpenBind-0 needs ≥ 0.5.0.
- **Variables and `install` flags differ per kit** (`OPENFOLD3_OB0_*` vs `OPENFOLD3_*`; the 0.4.1 `install` takes only
  `--weights`): `06_kit_modes_and_multigpu.md` §1.

## 3. Which mode?

Always pass `--mode`. With no `--mode` and no `OPENFOLD3_OB0_OPT`, the kit runs **`fast`**, which is not the
conservative choice. Lever-level detail: `06_kit_modes_and_multigpu.md`.

```
What do you need?
 ├─ a stock baseline, or "is the kit the problem?"          -> --mode off
 ├─ the default for production: same algorithm as stock     -> --mode exact
 ├─ byte-identical to stock (audit, regression, publication)-> --mode exact --det 1   (and off --det 1 as reference)
 ├─ throughput (screens, many queries)                      -> --mode fast  (after the seed-spread check, 09)
 ├─ input >= 1 401 polymer tokens, or fast ran out of memory -> --mode big  (engages at >= 1 401 polymer tokens;
 │                                                              below that it is fast and will not help)
 └─ one GPU is not enough                                   -> --mode big --n_gpu 2|4|8 (one host)
```

| Mode | Numerics | Warm wall vs `off` **[measured]** | Peak memory | Caveat |
|---|---|---|---|---|
| `off` | kit stock configuration | 1× | 24 844–25 053 MiB at 995 tokens; 36 346–36 539 MiB at ~737 tokens (632-residue protein–ligand) | Reference only |
| `exact` | same algorithm; not byte-equal to `off` at `--det 0` | 1.12–1.40× (A100), 1.11–1.37× (H100) | 0.98–1.20× of `off` up to 632 residues; 0.76–0.87× at 995 | CUDA graphs only up to 512 polymer tokens |
| `exact --det 1` | byte-identical to `off --det 1` (60/60 file pairs) | 0.92–1.05× of plain `off` (`off --det 1`: 0.73–0.80×) | as `exact` | These first det calls include cold-cache effects |
| `fast` | bf16 and fused kernels: small differences | 1.24–2.13× (A100), 1.21–1.83× (H100) | 13 662–13 701 MiB at 995 tokens; 14 489–17 472 MiB at ~737 | Fidelity **not** calibrated against stock seed spread |
| `big` | as `fast` | equals `fast` below the gate | row blocks and host streaming from 1 401 polymer tokens | Above the gate and `--n_gpu` untested here; ~5 000 tokens on one H100 80 GB **[docs]** |

## 4. Which MSA route?

```
Are the sequences unpublished, confidential or under agreement?
 ├─ yes -> never the public server
 │    ├─ precomputed MSAs (your databases or pipeline) -> main/paired_msa_file_paths + --use-msa-server false (07 §4)
 │    ├─ your own MMseqs2/ColabFold server             -> runner YAML msa_computation_settings.server_url +
 │    │                                                   --use-msa-server true (user approves that server); template-hit
 │    │                                                   PDB ids still go to RCSB (07 §1-2)
 │    └─ neither                                        -> single-sequence (--use-msa-server false); say accuracy is lower
 └─ no (public)
      ├─ smoke test or pipeline check only             -> single-sequence
      └─ real prediction: did the user approve the public server for these sequences?
           ├─ no  -> ask; meanwhile single-sequence or precomputed
           └─ yes
                ├─ GPU nodes reach api.colabfold.com -> --use-msa-server true
                └─ they do not                       -> run_openfold align-msa-server on a networked CPU node,
                                                         then predict offline with --use-msa-server false (05 workflow 7)
```

- **Omitting the flag sends sequences.** The server is on by default. Query-level `use_msas: false` does **not** stop
  submission: only `--use-msa-server false` keeps sequences on the host (07 §2).
- **Only protein chains go to the server.** RNA gets an MSA only from precomputed files; DNA never has one. Server
  mode also sends template-hit PDB ids to RCSB (07 §2).
- **A throttled or unreachable server can wait forever while holding a GPU.** Precompute MSAs for batches
  (`10_troubleshooting.md`).

## 5. Which card (by the largest query)?

Estimate tokens with `04_input_query_format.md` ("Token count") or `scripts/make_query.py --validate`. Memory is set
by the largest query in the call. It does not track token count alone: the ~737-token protein–ligand input peaked
higher in `off`/`exact` than the 995-token protein assembly **[measured]**.

| Largest query | 40 GB card (A100) | 80/94 GB card (H100 class) | Evidence |
|---|---|---|---|
| ≤ ~500 tokens | any mode | any mode | peak ≤ 20 932 MiB at 508 tokens **[measured]** |
| ~500–1 000 | `fast` preferred. `off`/`exact` ran, but peaked at up to 39 924 of 40 960 MiB on the ~737-token protein–ligand input | any mode | **[measured]** |
| ~1 000–1 400 | `fast` only, after a test | any mode, after a test | untested |
| 1 401–~5 000 | untested; not recommended **[inferred: gates sized on 80 GB cards]**. 40 GB only: a consented test with `--config a100 --mode big` and generous host RAM, then `--mode big --n_gpu 2\|4\|8` on one node (chunk-plan NOTE expected) | `big` (its gate counts polymer tokens only: 06 §4) | 80/94 GB: **[docs]** (kit README, H100 80 GB); 40 GB: [inferred] |
| > ~5 000 | — | `big --n_gpu P` on one multi-GPU host | **[docs]**. 17 000 tokens on two H100s is a report probe, not a capacity promise |

- **Measured bounds are single-sequence and template-free.** MSAs, templates, many ligand atoms and more samples all
  add memory. Treat the measured bounds as optimistic for production inputs.
- **`--config` names the card class, not the memory.** Use `a100` for A100 40/80 GB and `h100` for H100 80/94 GB, plus
  `h200`, `b200` or `b300`. A mismatch with the visible card is reported, not refused.
- **The kit's gates were sized on 80 GB cards.** This covers `big`'s 1 401 gate and the `--n_gpu` chunk plan. On 40 GB,
  lowering `OF3O_MIN_TOKENS` is possible **[docs]** but unvalidated.
- **Cost.** H100 was faster at every size measured (995 tokens `fast`: 52.7 s vs 69.0 s whole call). Put small queries
  on the cheaper card; put ligand-rich queries above ~700 tokens, and every `off`/`exact` run of that size, on 80/94 GB.

## 6. Seeds and samples

```
Purpose?
 ├─ smoke test / fixture          -> defaults: seed 42 x 5 samples (--num-diffusion-samples default 5)
 ├─ one routine prediction        -> 1 seed x 5 samples; rank by sample_ranking_score (08)
 ├─ hard target (complex interface, ligand pose, antibody-antigen, low ipTM)
 │                                -> 5 seeds x 5 samples (AF3 and OF3-preview2 evaluation practice [paper]);
 │                                   many more seeds can still help interfaces [paper]; discuss GPU cost first
 ├─ reproducibility               -> explicit seed list (runner YAML experiment_settings.seeds) + --det 1
 └─ comparing modes or hosts      -> identical flags => identical seeds; compare against stock's seed spread
```

- Outputs = queries × seeds × samples. Put every seed in **one call**, so the ≈ 45 s start-up is paid once.
- `--num-model-seeds N` draws N seeds from start seed 42, so the directories are not `seed_42/` **[source]**.
- Prefer more seeds over more samples. Memory grows with samples in the confidence stage; #71 (2025-12) hit OOM with
  100. Kit `big --n_gpu` loops one sample per pass **[source]**.

## 7. Failure routing (rc → next step)

```
rc 0  -> still verify completeness (summary.txt / scripts/summarize_openfold3_output.py);
         stock rc 0 can hide failed queries (10, triage)
rc 1  -> kit failed or incomplete; read <out>/logs/predict_err_rank0.log: OOM -> OOM ladder (10);
         input error -> fix the query (04)
rc 2  -> usage: boolean without a value, flag spelling, --mode vs OPENFOLD3_OB0_OPT, kit without a checkpoint (03 §8-9)
rc 3  -> NOT ACTIVE: read the reason (06 §8); pins / package / hook / card -> STOP and re-probe (section 8)
rc 5  -> TEMPLATES DROPPED: the user chooses: provide structures offline | remove template keys |
         accept with --allow-template-drop (recorded)
hang  -> MSA server unreachable or throttled -> cancel, precompute MSAs (10, MSA table)
```

## 8. When to stop and re-probe

Re-run `scripts/openfold3_env_probe.py` and refresh `configs/site_config.local.md` (made from
`configs/site_config.template.md`) before the next command when:
- a new session starts, or the target host or node type differs from the one probed;
- the image, environment, kit commit, upstream version or wrapper changed, or you just installed or updated anything;
- the driver changed, or the visible card is not the class that `--config` names;
- rc 3 appears on a host that was VALIDATED (pins, package, hook, core gate);
- `WEIGHTS unknown` appears where the probe recorded `pinned`, or `ckpt_root`/`OPENFOLD_CACHE` changed;
- the only `check` so far ran on a CPU node (`gpu=none`); that proves nothing about the GPU;
- the same failure survives two targeted fixes. Stop guessing, collect evidence (10, "What to capture") and report.

## 9. When to escalate to the user (ask; do not decide)

| Situation | Ask about |
|---|---|
| Any sequence would reach the public MSA server (the default) | Explicit approval per dataset. Recommend `false` for anything unpublished |
| Install, image build or pull, `setup_openfold`, `run.sh install`, weights/CCD download | Per-action consent (2.3 GB checkpoint, 63 MB CCD) |
| GPU submissions: many queries, > 1 seed × 5 samples on large inputs, 80/94 GB cards, `--n_gpu`, long walltimes | Cost, queue and budget |
| rc 5 templates dropped | Provide structures, remove keys, or accept the drop |
| Input beyond the size range validated on this host; `big` above its gate; `--n_gpu` | Run a test first; state that it is untested |
| `fast` results that will be published or compared without the seed-spread check | Trade-off; offer `exact` or `exact --det 1` |
| Non-pinned or legacy checkpoint | Confirm intent and labelling |
| A "fix" that edits `stock/`, applies a community patch, disables SSL verification or changes site-wide config | Refuse, or get explicit approval |
| Deleting caches, outputs or old MSAs; moving caches out of home | Confirmation before any deletion |
| Single-sequence or low-confidence results used for scientific conclusions | Flag the limitation; propose an MSA-backed rerun |
| Licence or terms questions (OpenBind-0: Apache-2.0 per its announcement, "not stated by upstream for the parameters" per the kit's `stock/PINS.json`; preview weights are gated) | The user decides; give both sources, not legal advice |
