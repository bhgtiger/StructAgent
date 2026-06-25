# 07 — Outputs and Confidence

Grounded in `data/write/writer.py` (v2.2.1) and **verified by a live run on
volta** (boltz 2.2.1). When docs and observed output differ, the observed tree
wins.

## Output tree (observed live; `--output_format pdb` — default format is mmcif)

```
<out_dir>/boltz_results_<stem>/
├── lightning_logs/version_0/hparams.yaml
├── predictions/<stem>/
│   ├── <stem>_model_0.pdb            # rank-0 structure (.cif if mmcif); per-token pLDDT in B-factors
│   ├── confidence_<stem>_model_0.json
│   ├── plddt_<stem>_model_0.npz
│   ├── pae_<stem>_model_0.npz
│   └── pde_<stem>_model_0.npz
└── processed/
    ├── manifest.json
    └── constraints/  mols/  records/  structures/   # (+ msa/, templates/ when those inputs are used)
```

Notes:
- With `--diffusion_samples N` you get `<stem>_model_0..N-1`, **ranked by
  `confidence_score`** (model_0 = best).
- `.cif` is the default (`--output_format mmcif`); pass `pdb` for `.pdb`.
- This fixture passed **no** `--write_full_*` flags, yet `plddt`, `pae`, and
  `pde` npz were all written. (Live help shows `--write_full_pae` default True and
  `--write_full_pde` default False, so the `write_full_*` flags do **not** cleanly
  gate npz presence in this v2.2.1 build — Boltz-2 emitted pae/pde here anyway.)
  Treat the observed tree as ground truth; if you depend on exact npz contents,
  verify on your host. `--write_embeddings` adds `embeddings_<id>.npz`.
- Affinity adds `affinity_<stem>.json` and a `pre_affinity_<stem>.npz` (see 06).

## confidence_<stem>_model_0.json — fields (verified)

```json
{
  "confidence_score": 0.86,   "ptm": 0.50,   "iptm": 0.0,
  "ligand_iptm": 0.0,         "protein_iptm": 0.0,
  "complex_plddt": 0.96,      "complex_iplddt": 0.96,
  "complex_pde": 0.30,        "complex_ipde": 0.0,
  "chains_ptm":        { "0": 0.50 },
  "pair_chains_iptm":  { "0": { "0": 0.50 } }
}
```

Interpretation:
- `confidence_score` — the ranking score: `0.8*complex_plddt + 0.2*iptm`
  (`ptm` for single chains). Range [0,1], higher better.
- `ptm` / `iptm` — predicted TM overall / at interfaces. `iptm` is 0 for a
  monomer (no interface).
- `ligand_iptm` / `protein_iptm` — ipTM restricted to protein-ligand /
  protein-protein interfaces. Use `ligand_iptm` to judge a docked pose.
- `complex_plddt` / `complex_iplddt` — mean pLDDT (interface-upweighted), [0,1].
- `complex_pde` / `complex_ipde` — mean PDE in **Å**, lower is better.
- `chains_ptm` / `pair_chains_iptm` — **keyed by integer chain index** ("0",
  "1", …), NOT chain letters. Map back to your YAML `id`s by order.

## npz arrays

- `plddt_*.npz` → `plddt` (per-token, [0,1]).
- `pae_*.npz` → `pae` (token×token, Å).
- `pde_*.npz` → `pde` (token×token, Å).
Load with `numpy.load(path)["plddt"|"pae"|"pde"]`.

## Quick quality read

1. Is `confidence_score` reasonable (rough: >0.8 strong, 0.6–0.8 moderate,
   <0.6 weak)? These are guidance bands, not hard cutoffs.
2. For a complex, check `iptm`/`ligand_iptm` for the interface, not just plddt.
3. Look at the pLDDT in the structure B-factors to find low-confidence regions.
4. Don't average away locality: a great global score can hide a wrong loop or a
   misplaced ligand. Inspect the structure.
