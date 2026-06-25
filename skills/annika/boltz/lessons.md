# Lessons — boltz skill

Append things learned the hard way. Newest first. Keep each entry short:
symptom → cause → fix, with the source/host.

## 2026-06-23 — initial build (volta, boltz 2.2.1)
- cuEquivariance kernels RUN on RTX 2080 Ti (compute capability 7.5 / Turing).
  Do not add `--no_kernels` reflexively here — it only costs speed. Reserve it for
  GPUs that actually throw a cuequivariance error.
- Docs vs live `--help` disagree on several defaults; **live wins**:
  `--max_parallel_samples` is `None` (docs said 5); `--subsample_msa` is `True`
  (docs table said False); `--write_full_pae` help reads "Default True" while the
  docs table says False. The `--checkpoint`/`--affinity_checkpoint` help strings
  still say "Boltz-1" though the default model is Boltz-2.
- With default flags, a run emits `plddt`/`pae`/`pde` npz plus the structure +
  confidence JSON. `chains_ptm`/`pair_chains_iptm` are keyed by **integer** chain
  index, not chain letter.
- Affinity ligand limits live in `data/parse/schema.py` (>128 atoms rejected,
  >56 warns), not `main.py`.
- Weights (~7.6 GB) cache in `~/.boltz`: `boltz2_conf.ckpt`, `boltz2_aff.ckpt`,
  `mols/` + `mols.tar`. Set `$BOLTZ_CACHE` (absolute) to share across users.

<!-- Pending Merge (from distill-session) goes below this line -->
