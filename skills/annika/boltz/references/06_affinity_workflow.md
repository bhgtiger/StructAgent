# 06 — Affinity Workflow (Boltz-2 only)

Boltz-2 can predict ligand **binding affinity** alongside structure. This is the
single most over-interpreted Boltz output, so be precise.

## How to request it

Add a `properties.affinity.binder` pointing at a **ligand** chain:

```yaml
version: 1
sequences:
  - protein:
      id: A
      sequence: MVK...          # use a real MSA or --use_msa_server
  - ligand:
      id: L
      smiles: 'CC(=O)Oc1ccccc1C(=O)O'
properties:
  - affinity:
      binder: L
```

```bash
boltz predict complex.yaml --use_msa_server --out_dir results
# affinity summary -> results/boltz_results_complex/predictions/complex/affinity_complex.json
```

Relevant flags: `--sampling_steps_affinity` (200), `--diffusion_samples_affinity`
(5), `--affinity_mw_correction` (off), `--affinity_checkpoint`. (`--model boltz2`
is the default; affinity is unavailable for Boltz-1.)

## Constraints (enforced in `schema.py`) — check before promising a run

- Exactly **one** affinity binder per input.
- The binder must be a **ligand** chain (not protein/DNA/RNA).
- No multiple copies of the affinity ligand; no multi-residue ligand.
- **>128 atoms** → **rejected** (error). The count is taken on the RDKit ligand
  after `RemoveHs` (effectively heavy atoms).
- **>56** such atoms → **warning**: outside the training regime, less reliable.
- Targets that are RNA/DNA/co-factor (not protein): won't crash but the docs say
  the output is **unreliable**. Don't report those numbers as meaningful.

## The two numbers — different training, different use

`affinity_<id>.json` contains, for the ensemble and each of two sub-models:

| Field | Meaning | Use it for |
|---|---|---|
| `affinity_probability_binary` | Probability the ligand is a **binder** (0–1) | Hit discovery: binder-vs-decoy triage |
| `affinity_pred_value` | Comparative affinity as **`log10(IC50)`**, IC50 in µM; **lower = stronger** | Hit-to-lead / lead-opt ranking among **active** binders |
| `*_value1/2`, `*_probability_binary1/2` | Same, from each ensemble member | Spread / agreement check |

`affinity_pred_value` is only meaningful when **comparing active molecules** —
it is *not* a reliable absolute affinity for arbitrary inactives.

### Reading `affinity_pred_value` (from the docs)

- IC50 1e-9 M → value ≈ **-3** (strong binder)
- IC50 1e-6 M → value ≈ **0** (moderate)
- IC50 1e-4 M → value ≈ **+2** (weak / decoy)

Convert to pIC50-style kcal/mol with `(6 - value) * 1.364`.

## How to talk about results (don't oversell)

- "Boltz-2 predicts a high binder probability (`affinity_probability_binary`≈X)
  and ranks this ligand stronger than Y (`affinity_pred_value` Xv vs Yv, lower =
  stronger). This is a computational triage signal, not an experimental affinity;
  confirm with assays/FEP."
- Cross-check structural plausibility: a confident `affinity_pred_value` with a
  poor pose (low `ligand_iptm`, bad `complex_plddt`) deserves skepticism. Read
  `07_outputs_and_confidence.md`.
- For screens, reuse the protein MSA across ligands and vary only the ligand —
  see `05_core_workflows.md`. Watch the per-ligand atom limits above.
