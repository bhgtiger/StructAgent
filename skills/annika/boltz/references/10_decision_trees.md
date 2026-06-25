# 10 — Decision Trees

Fast routing. Follow the arrows; deeper detail is in the referenced files.

## Which model?

```
Need ligand affinity, templates, contact constraints, or method conditioning?
  └─ yes -> Boltz-2 (default; --model boltz2)
  └─ no  -> still default to Boltz-2 unless you specifically need to reproduce
            Boltz-1 results (--model boltz1)
```
Affinity / templates / contacts / `--method` are **Boltz-2 only**.

## Which MSA strategy?

```
Do you have a precomputed MSA?
  ├─ yes (1 protein)      -> msa: ./file.a3m ; no --use_msa_server
  ├─ yes (>1 protein, pairing) -> custom CSV (sequence,key) ; no --use_msa_server
  └─ no
       ├─ sequence is public / non-sensitive -> --use_msa_server (ColabFold)
       ├─ sequence is confidential           -> build MSA offline, reference it
       └─ truly none & ok with lower quality  -> msa: empty (warns; suboptimal)
```
Never mix custom + auto MSA in one input. See `04` and `02` (privacy).

## Can this host run it? (state machine)

```
Run scripts/boltz_env_probe.py
  ├─ STATE UNCONFIGURED -> no boltz install -> install (consent) then re-probe
  ├─ STATE PROBED       -> boltz present, weights missing -> first run downloads
  │                        weights (~8 GB) -> ok to proceed after confirming
  └─ STATE VALIDATED-CANDIDATE -> boltz + weights present -> verify_boltz.py
                                  (--fixture) -> then run real jobs w/ confirmation
```

## Run won't fit / errors

```
CUDA OOM            -> lower diffusion_samples / max_parallel_samples /
                       sampling_steps; shrink system; bigger GPU       (09)
cuequivariance err  -> --no_kernels (older GPUs)                       (09)
MSA server fails    -> retry / custom MSA / check auth                 (09)
schema error        -> check 04 (one of smiles|ccd; force needs
                       threshold; no mixed MSA)                        (09)
affinity rejected   -> ligand >128 atoms; not a single ligand chain    (06)
```

## Quality settings

```
Default              -> recycling_steps 3, diffusion_samples 1
Want diversity       -> raise diffusion_samples; lower step_scale
AF3-like heavy       -> --recycling_steps 10 --diffusion_samples 25 (slow)
Reproducible         -> --seed N
Better poses (lig)   -> --use_potentials
```

## Affinity yes/no

```
Want binding info?
  ├─ binder/decoy triage      -> affinity_probability_binary           (06)
  ├─ rank ACTIVE analogs      -> affinity_pred_value (log10 IC50; lower=stronger)
  └─ absolute Kd / inactives  -> NOT this; use assays/FEP
```
