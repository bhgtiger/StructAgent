# 05 — Core Workflows

Each recipe = a YAML + a command. Only flags from `03_cli_reference.md` are used.
Default model is Boltz-2. Confirm the host is VALIDATED (probe) before running.

## 1. Single protein (auto MSA)

```yaml
version: 1
sequences:
  - protein: { id: A, sequence: MVK... }
```
```bash
boltz predict prot.yaml --use_msa_server --out_dir results
```

## 2. Complex / multimer

```yaml
version: 1
sequences:
  - protein: { id: A, sequence: AAA... }
  - protein: { id: B, sequence: BBB... }   # use id: [A, B] for identical copies
```
```bash
boltz predict complex.yaml --use_msa_server --out_dir results
```
Check `iptm` / `pair_chains_iptm` for the interface (see 07).

## 3. Protein + ligand (docking)

```yaml
version: 1
sequences:
  - protein: { id: A, sequence: MVK... }
  - ligand:  { id: L, smiles: 'CC(=O)Oc1ccccc1C(=O)O' }
```
```bash
boltz predict pl.yaml --use_msa_server --use_potentials --out_dir results
```
`--use_potentials` improves physical plausibility of poses. Judge with
`ligand_iptm`. For affinity, see `06_affinity_workflow.md`.

## 4. Custom MSA (offline / private)

Single protein: `msa: ./seq.a3m` in the YAML, then **no** `--use_msa_server`:
```bash
boltz predict prot.yaml --out_dir results
```
Multiple proteins needing pairing: use a CSV with `sequence`,`key` columns
instead of a3m (rows sharing a key are aligned). You cannot mix custom and auto
MSAs in one input.

## 5. Single-sequence mode (no MSA available)

`msa: empty` → Boltz warns predictions will be suboptimal. Use sparingly.

## 6. Templates / pocket / contact (Boltz-2)

Add `templates:` or `constraints:` blocks (see `04_input_yaml_schema.md`).
`force: true` on a template requires `threshold`. Pocket/contact `max_distance`
is 4–20 Å (default 6).

## 7. Higher quality / diversity

AF3-like heavier run (slower):
```bash
boltz predict in.yaml --use_msa_server --recycling_steps 10 --diffusion_samples 25 --out_dir results
```
For reproducibility add `--seed 42`. Lower `--step_scale` → more diverse samples.

## 8. Batch / virtual screen

- **Directory input:** point `boltz predict DIR` at a folder of `.yaml` files; all
  are processed. Multi-GPU via `--devices N`.
- **Screen one target × many ligands:** reuse the protein MSA so you don't re-hit
  the MSA server for every ligand. Generate the protein MSA once (or run one
  input with `--use_msa_server` and reuse the cached `.a3m`), then write one YAML
  per ligand referencing that MSA (no `--use_msa_server`). Mind affinity ligand
  size limits (06). There is no single official "screen" command — compose it.
- **Caching:** without `--override`, Boltz reuses processed files/predictions in
  the out_dir. Use `--override` when you change parameters but keep the out_dir.

## 9. Output format

`--output_format mmcif` (default) or `pdb`. Per-token pLDDT is stored in the
structure (B-factors). See `07_outputs_and_confidence.md`.
