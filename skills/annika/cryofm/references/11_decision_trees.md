# 11 — Decision trees

## 1. Which command?

```
What do you have?
├─ two half maps (same box, same pixel)
│   ├─ goal: cleaner map, keep the data in charge          → cfm denoise --op denoise            (§1 of 05)
│   ├─ preferred orientation / missing views + RELION STAR  → cfm denoise --op denoise inpaint --data-starfile-path  (§2)
│   ├─ strongly varying local resolution / periphery        → cfm denoise --op non-uniform         (§3)
│   ├─ goal: sharpened-looking or model-like map, still tied to the data
│   │                                                      → cfm enhance -i1 -i2 [-i map] --model-dir emhancer|emready --op … (§5)
│   └─ inside a RELION Refine3D                            → cfm-relion / relion_wrapper.py        (07)
├─ one map only (primary / sharpened / post-processed)
│   ├─ want LocScale/DeepEMhancer look                     → cfm enhance … emhancer --output-tag 1
│   ├─ want model-simulated (EMReady) look                 → cfm enhance … emready --output-tag 0 --cfg-weight 0.5
│   └─ want denoising with a data term                     → not possible; get the half maps
├─ particle poses only in cryoSPARC                        → export halves (map_half_A/B) for denoise; STAR via pyem for inpaint (07 §6)
└─ tomogram / subtomogram average / helical / > 576 Å box  → out of the training distribution; explain, do not promise
```

Say explicitly which of these ran on the current host (validated site: §1 and §4 of 05; the rest untested).

## 2. Which model directory?

| Command | `--model-dir` | Extra flags | Wrong pairing fails how |
|---|---|---|---|
| `cfm denoise`, `cfm-relion` | `cryofm2-pretrain` | — | emhancer/emready dir → conv `RuntimeError … expected input[4, 2, 64, 64, 64] to have 3 channels, but got 2` at the first batch |
| `cfm enhance` EMhancer style | `cryofm2-emhancer` | `--output-tag 1` (default), `--cfg-weight 1.5–3.0` (default 2.0) | pretrain dir → `ValueError("class_embedding needs to be initialized in order to use class conditioning")` |
| `cfm enhance` EMReady style | `cryofm2-emready` | `--output-tag 0 --cfg-weight 0.5` (**both explicit**) | emhancer ↔ emready swap or wrong tag: **silent**, wrong style |

Never point `--model-dir` at the HF repo root (`AttributeError: 'ConfigDict' object has no attribute 'z_scale'`).

## 3. Which `--op`?

| Symptom in the map | `--op` | Needs | Do not |
|---|---|---|---|
| isotropic noise, resolution-limited | `denoise` | halves | — |
| streaking / smeared along an axis, poor 3DFSC sphericity, known pose bias | `denoise inpaint` | halves + particle STAR with poses | repeat `--op`; forget `--data-starfile-path` (→ `TypeError … NoneType` in `starfile`) |
| fill unobserved Fourier regions without touching observed ones | `inpaint` | same | expect denoising (none) |
| core sharp, periphery/micelle noisy | `non-uniform` | halves (+ RAM) | combine with `denoise` (denoise wins); `--fsc-weighting` |
| any | — | `--norm-grad --use-lamb-w` on every likelihood run | — |

## 4. Batch size, card, memory (per GPU)

| GPU memory | likelihood runs (`denoise`, enhance+halves) | pure `enhance -i` |
|---|---|---|
| 40 GB A100 (validated site) | `--batch-size 4 --bf16` (21.4 GB measured) | 4 (7.3 GB) or 8 |
| 24 GB | 4 with `--bf16` (21 G docs) — tight; 2 to be safe | 8 |
| 16 GB | **2** (11 G with bf16; maintainer's advice), 1 if `non-uniform`/inpaint | 4 |
| 8–12 GB | 1 (6.9 G) | 2 |

`--num_processes` never reduces per-GPU memory. `non-uniform` adds ~64 MiB host RAM per patch; `inpaint`
back-projection adds GPU memory with the particle box. Expect fewer than the table's gigabytes only for small boxes.
Validated site's card choice: the A100 was validated and billed cheaper than the H100 (untested there).

## 5. Steps, λ, seed

- Keep `--num-timesteps 200` (paper and default). If you change it use a divisor of 1000 (100, 125, 250, 500).
  Preview runs: 50 or 100. More than 200 showed no systematic gain in the paper's ablation and degrades ill-posed
  missing-cone cases.
- `--lamb-base 1000.0` is the only documented value; larger = closer to the data, smaller = more prior. In
  `cfm enhance` posterior mode it acts ≈(1 + CFG)× stronger [derived]. No tuning rule exists upstream; tune on one
  map against the deposited model, not against the output FSC.
- `--seed N` for reproducible `cfm denoise` runs (same seed also re-seeds every batch); `cfm enhance` cannot be seeded
  — compare its outputs statistically.

## 6. Before submitting (Slurm sites)

1. On the node: `hostname; echo ${SLURM_JOB_ID:-no-slurm-job}; squeue --me` and the site's budget command (GPU budget left).
2. `python3 scripts/cryofm_env_probe.py` → VALIDATED-CANDIDATE and matching site config, else stop.
3. `python3 scripts/inspect_map.py` on every input → PASS gates; note NSTART/ORIGIN.
4. `python3 scripts/build_cfm_command.py … --sbatch` → review the job file; walltime from patches × ~1 min / 4.
5. Ask the user; `sbatch --export=NONE job.sbatch`; report the job id and the exact command.
6. After: `check_cfm_output.py`, `restore_origin.py` if needed, ledger entry.

## 7. Re-probe triggers

Different node type (login/staging/GPU), a changed image or weights sha256, a new driver, a new upstream commit or
HF revision, more than 90 days since the recorded validation, or any error that the troubleshooting table does not
explain. Never carry a verdict from one machine to another.

## 8. Escalate (stop and tell the user) when

- the request needs a path that is untested here (RELION loop, multi-GPU, inpaint with real poses) and the user
  wants a production result rather than a first test;
- the inputs fail a geometry gate the code cannot fix (odd cube, box < 96 Å, mismatched half maps, primary map vs
  half-map grids) — propose the preprocessing instead of improvising inside CryoFM;
- the user intends to deposit or publish CryoFM2 outputs as half maps or as the primary map;
- a map or STAR must leave the host (the default path has no egress; there is no reason to upload anything);
- the budget is at stake: multi-hour jobs on > 400³ boxes, `non-uniform` on big boxes, or any job the user has not approved.
