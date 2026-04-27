# learned.md — isolde

Pending deep-dream capture entries for later cleanup/merge via skill_creator.

## 2026-04-12 — FTCD ISOLDE runs
- ISOLDE 5-min monitored runs work well for post-rigid-fit polishing. CC plateau detection (ΔCC < 0.002 for 2 consecutive 60s windows) reliably stops early (~189s both runs).
- Delete OP3 + OXT atoms before ISOLDE sim start — prevents OpenMM template failures on chain termini.
- Always open a second copy of the map for CC measurement (molmap → measure correlation) — the ISOLDE map copy gets modified by clipper.
- ISOLDE post-fitting produces excellent clashscores (0.08–0.34) and good MolProbity (0.80–1.07) but leaves ASN/GLN/HIS sidechain angle outliers (~16 per model at 4 Å). These are AMBER vs CCP4 geometry library differences — cosmetic at 4 Å, Phenix RSR cleans them up.
- HIS 247 flip was flagged in every chain of both FTCD models — systematic AlphaFold error. Always check Asn/Gln/His flips post-ISOLDE.

