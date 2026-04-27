# Validation Strategies

## Metric Panel (always report these)

### Primary metrics
- **CC_mask** — overall map-model correlation
- **MolProbity score** — combined geometry assessment
- **Ramachandran** — % favored, % outliers
- **Rotamer outliers** — % outliers
- **Clashscore** — steric clashes per 1000 atoms
- **Cβ deviations** — backbone geometry check
- At ~4 Å, **EMRinger** is a primary side-chain/density validation metric; target >1.0 when applicable. CaBLAM is essential for AlphaFold-derived models.

### Per-residue metrics (for debugging)
- **CaBLAM** — more informative than Ramachandran for cryo-EM backbone
- **EMRinger** — sidechain-density agreement
- **Q-score** — atom resolvability (per-atom)
- **Real-space CC per residue** — local fit quality

### Metal-specific
- Bond distances to coordinating atoms
- L-M-L angles (tetrahedral: 109.5°, octahedral: 90°/180°)
- CheckMyMetal validation if available

## Interpreting Metrics

### "Good" is resolution-dependent
- Don't compare 3Å metrics to 2Å standards
- Rotamer outliers at >3Å: many are real conformations (density is ambiguous)
- Clashscore: higher tolerance at lower resolution (atoms are less well-placed)

### Red flags
- Rama outliers > 1% at any resolution → something is wrong
- Cβ deviations > 0 → backbone geometry error, fix before continuing
- CC_mask dropping between refinement rounds → overfitting or bad restraints
- MolProbity improving while CC drops → overfitting to geometry, ignoring density

### CaBLAM vs Ramachandran
- Use CaBLAM as primary backbone validator for cryo-EM (from EMDataResource 2019 challenge)
- Ramachandran alone misses some backbone errors that CaBLAM catches
- Both should be checked, but CaBLAM is more reliable at medium resolution

## Validation Workflow

### After every major step
1. Run `phenix.molprobity` (or equivalent)
2. Compare metrics to previous step — they should improve or stay stable
3. If metrics worsened, investigate before continuing

### Before declaring "done"
1. Full MolProbity report
2. Visual inspection of worst regions (highest B-factor, lowest local CC)
3. Check all ligand/metal sites individually
4. Verify no cis-peptides were introduced accidentally
5. Check known problem areas flagged during building

### Common traps

- **Post-ISOLDE side-chain angle outliers at ~4 Å:** expect some ASN/GLN/HIS side-chain angle outliers (>4σ) from AMBER-vs-CCP4 geometry-library differences. Phenix RSR usually cleans these up; do not over-interpret them as structural signal at this resolution.
- **Over-refined waters** at >3Å → don't model them
- **Waters at >3.5 Å** → generally do not model waters unless there is exceptional independent evidence.
- **Perfect scores** at low resolution → suspicious, check for overfitting
- **Ignoring map quality** → bad map = bad model, regardless of MolProbity
- **Fixing outliers that are real** → some outliers reflect true conformations, verify with density
- **Local DNA auto-weighting overfitting** → for small duplex windows, CC can rise while geometry collapses (clashscore >600). Treat as INVALID even if CC improves. Use explicit conservative weighting + geometry-first acceptance criteria
- **Servalcat box/origin mismatch** → Servalcat outputs may be in a trimmed/shifted frame. For density checks, use the original EM map in the model's frame, or apply shiftback/origin correction

## Novel-claim diagnostic bundle

For novel structural claims (channeling intermediates, unusual ligand sites, uncommon chemistry), run and report a pre-publication diagnostic bundle:
1. Half-map FSC via `phenix.mtriage` (non-negotiable).
2. Per-atom ligand CC split by chemical group to identify weak fragments honestly.
3. Ligand B-factor parity versus a 5 Å shell to detect frozen-B artefacts.
4. Formal channel profile via HOLE/CAVER; straight-line distance probes are not enough for channeling claims.
5. Orientation-control per-atom CC on unrefined seeds for alternative poses.
6. Ensure ligand refinement includes ADP (`...+adp`) before interpreting ligand B-factors.
