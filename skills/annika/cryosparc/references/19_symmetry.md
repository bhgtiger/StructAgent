# Topic 19 — Symmetry

## Scope
Strategy for whether and how to impose, relax, expand, or refuse symmetry across the cryoSPARC SPA workflow: ab initio, consensus refinement, 3D classification / heterogeneous refinement, local refinement, reconstruction-only branches, and the handedness branch. Helical symmetry is included only as a specialized branch; deep helical workflow lives in `11_helical.md`. Mask construction for symmetry-aware classification and local refinement lives in `20_masks.md`. Global refinement branch logic lives in `07_refinement.md`, 3D classification mechanics in `08_classification_3d.md`, local refinement in `09_local_refinement.md`, FSC and postprocessing reading in `10_postprocessing.md`, and orientation diagnostics in `orientation_and_preferred_views.md`.

## Decision surface — impose, stay C1, relax, or expand

| Situation | Default move | Why |
|---|---|---|
| Known, well-established point group; consensus map matches | Impose symmetry from ab initio through refinement | Higher effective SNR per asymmetric unit; fewer pose DoF |
| High-symmetry target but ab initio returns a flat "disc" volume | Raise minibatch size, push max resolution finer; impose symmetry only if disc persists and external evidence supports it | Avoids locking symmetry onto a pose-collapse artifact |
| Suspected pseudosymmetry (symmetric shell, asymmetric cargo/ligand) | Stay C1 through consensus; address asymmetry downstream with heterogeneous refinement, classification, or symmetry relaxation | Imposing symmetry early averages the biology away |
| Symmetry-enforced consensus is solid; want best single map | Keep symmetry; do not chase resolution with ad-hoc parameter knobs | Symmetric refinements are already maximally constrained |
| FSC oscillates or repeated weak satellite density appears at symmetry-related sites | Re-run consensus in C1 to test | Most direct symmetry-breaking diagnostic |
| Symmetry-enforced consensus is good and you want detail of one asymmetric unit | Symmetry expand, then C1 local refine on that ASU | More effective particles per ASU, alignment independence per copy |
| Particles plausibly trapped in symmetry-related local minima | Symmetry relaxation (maximization or marginalization) plus extra final passes | Forces alignment to evaluate every symmetry-related pose |
| Continuous variation within a symmetric assembly | Symmetry expand, then 3DVA / 3DFlex on the expanded stack | More signal per ASU for variability methods |
| Helical assembly | Use helical refinement / symmetry search utility; do not import point-group habits | Helical symmetry is a different parameter space (twist, rise) |

## Point-group symmetry in ab initio and refinement
### What "imposing symmetry" means here
Imposing `Cn`, `Dn`, `T`, `O`, or `I` in Homogeneous or Non-Uniform Refinement reuses each particle in `N` symmetry-related poses during back-projection. SNR rises by roughly `N`; mis-imposition averages real density across symmetry-related sites and erases asymmetry.

### Choosing whether to impose at ab initio
The default at ab initio is C1. Highly symmetric targets (T, O, I; high `Cn`/`Dn`) sometimes converge to flat "disc / cake" volumes in C1 because low-resolution projections look uninformative.

Order of escalation before imposing symmetry at ab initio:
1. Raise initial and final minibatch sizes (roughly 1000 is a known recovery move for apoferritin-like C1 / icosahedral cases).
2. Push the maximum resolution finer (lower Å number) so projection differences become informative.
3. Inspect 2D classes and orientation distribution; rebalance if one view dominates.
4. Only then impose the suspected symmetry, and treat it as a hypothesis to revisit at the refinement stage.

For an icosahedral / octahedral shell with internal asymmetric cargo, generally **either** impose the shell's symmetry to stabilize the shell **or** keep C1 to preserve internal asymmetry — but not both at once. The encapsulated-ferritin case is a worked example: ab initio in C1 with `enforce non-negativity` off preserves the internal tetrahedral cargo arrangement; imposing I at ab initio erases it.

### Cn / Dn cautions
- `Cn` aligns the symmetry axis to Z. `Dn` adds a perpendicular dyad.
- Wrong-`n` mistakes (`C3` on a `C4` channel, `D2` on a `C2`) appear as repeated weak satellite densities and/or FSC ringing.
- Pseudo-`Cn` targets where one site differs (ion binding, one inhibitor) average that site away under enforced symmetry.

### Tetrahedral / octahedral / icosahedral cautions
- Use these only with external structural evidence.
- Even when global symmetry is real, asymmetric cargo or modulator binding will be erased unless the asymmetric branch is preserved upstream (TRPV5 / calmodulin, encapsulin / ferritin).
- A "tetrahedral-looking" arrangement of `n` identical subunits is not necessarily a true tetrahedral point group; encapsulated ferritin's four D5 cargo units are tetrahedral-arranged but not in any cryoSPARC-supported point group, and require custom expansion rather than `T`.

### Validation under imposed symmetry
- FSC under enforced symmetry can look high while the asymmetric biological state is invisible. Treat high resolution plus a featureless asymmetric region as a symmetry-imposition red flag, not as success.
- Always inspect the volume for repeated low-density bumps at symmetry-related positions and for features that smear along the symmetry axis.

## Symmetry relaxation in Homogeneous / NU Refinement
Symmetry relaxation modifies the orientation search in Homogeneous and Non-Uniform Refinement so that every particle's symmetry-related poses are explicitly compared. The maximization variant keeps the best symmetry-related pose; the marginalization variant integrates over a neighborhood of symmetry-related modes weighted by posterior probability.

### What question it answers
"Given an otherwise correct alignment, am I trapped in a symmetry-related local minimum because branch-and-bound never compared the symmetry-related copies directly?"

### When relaxation is the right tool
- Pseudosymmetric targets where the bulk is symmetric and a small feature breaks the symmetry (channel + ligand bound at one of `N` sites, scaffold with a single binding partner).
- Symmetry-mismatch complexes where the asymmetric component is too small for cleanup-style heterogeneous refinement to resolve on its own.

### When relaxation is the wrong tool
- The starting map is not actually symmetric — nothing to relax against. Run plain C1.
- The heterogeneity is compositional present / absent, not a symmetry-related pose ambiguity — use 3D classification or heterogeneous refinement.
- The asymmetric feature is too small relative to the dominant symmetric signal — even relaxation cannot find it.

### Practical notes
- Maximization is the cheaper default and usually enough for larger targets / higher SNR.
- Marginalization helps small targets, low SNR, or small masks where many symmetry-related poses score similarly.
- Symmetry relaxation typically needs many more final iterations than a normal refinement; the FSC stopping criterion is a poor guide because pose reassignment between symmetry-related modes does not move FSC.
- Combine with Non-Uniform Refinement when the asymmetric region sits on a disordered scaffold (membrane protein, glycan-heavy surface).

## Symmetry expansion workflows
Symmetry expansion replicates each particle's poses around the point-group (or helical) operators and produces an expanded particle stack whose size is `N × original`. Use it as a setup step for downstream local / variability / classification work, never as a final refinement.

### Prerequisites
- Particles must have valid `alignments3D` from a global refinement.
- Particle poses and the reference volume must already be aligned to cryoSPARC's symmetry-axis conventions. Use Volume Alignment Tools to enforce this if upstream refinement was imposed without explicit alignment, or if the volume came from elsewhere.
- For helical expansion, particles must come from a Helical Refinement that converged on a `(twist, rise)` pair, and that helical refinement should have run with shifts along the helical axis limited.

### What you do with the expanded stack
- **Local Refinement (C1)** focused on a single asymmetric unit using a one-ASU mask. This is the most common downstream use.
- **3D Classification / focused classification** on one ASU to discover occupancy or conformational heterogeneity local to that unit (e.g., one ligand on a tetramer).
- **3DVA / 3DFlex** to discover continuous motion within an asymmetric unit while still using all `N` copies' worth of signal.
- **Heterogeneous Reconstruction Only** in C1 to validate that the expansion produced a reasonable map.

### What you must not do with the expanded stack
- Do not run global pose-search refinements (Ab-Initio, Homogeneous, Heterogeneous, Non-uniform, or Helical Refinement) on expanded particles. Each physical particle is now duplicated `N` times; global alignment treats the copies as independent and double-counts them in FSC.
- Do not interpret the expanded particle count as the "true" particle count for resolution claims; particle / FSC numbers must be read against the pre-expansion count.
- Do not enforce point-group symmetry again downstream (other than rare "local symmetry around a subunit" cases) — the expansion already represents every symmetry-related copy.

### Returning from expanded to non-expanded
If a downstream step (e.g., 3DVA cluster selection) keeps a subset of expanded particles and the next job needs a non-expanded set (for example, a symmetry-enforced refinement), use Remove Duplicate Particles to collapse multiple expanded copies of the same physical particle back to one.

### One-ASU masks
Masks for local refinement on expanded particles must enclose exactly one asymmetric unit plus a comfortable margin, be soft-edged, sit on the same grid as the volume after expansion, and contain no detached noise islands. Full mask discipline lives in `20_masks.md`.

## Symmetry and 3D Classification / Heterogeneous Refinement
### When the question is "is the symmetry real?"
Heterogeneous Refinement with **identical copies** of the consensus volume is the canonical pseudosymmetry rescue. Each class is allowed small pose updates and per-class reconstruction; with `force hard classification` on, the job commits each particle to its best symmetry-related interpretation. This is how the TRPV5 / calmodulin pattern recovers a C1 map from a C4-symmetrized consensus.

### When the question is "is one subunit different?"
Symmetry expansion plus focused 3D Classification on one ASU is the right shape. Provide a focus mask covering one asymmetric unit and a generous solvent mask that contains it. This is the pattern that resolves per-site ligand stoichiometry on `Cn` / `Dn` channels.

### Force-hard-classification rule of thumb
- Turn on when classes drift to identical occupancy, when the goal is whole-particle commitment (apo vs liganded), or when using Heterogeneous Reconstruction Only for per-class validation.
- Leave off when subtle weighting between symmetry-related classes is biologically meaningful and you only intend to inspect, not commit.

### Identical-volume strategy
"Wire `N` identical volumes into Heterogeneous Refinement" is a deliberate pattern, not a misconfiguration. Class identity is decided by particle-side perturbations and pose updates; the trick fails if the inputs are not on the same greyscale or if the consensus was itself refined under the wrong symmetry.

### Symmetry and class output volumes
3D Classification's weighted back-projection can make output class volumes look more similar than the underlying particle assignments are. If classes look right in the histogram but their volumes look identical, reconstruct each class separately with Heterogeneous Reconstruction Only (with `force hard classification` on) before trusting the visual comparison.

## Handedness and mirror ambiguity
Projection images do not pin down 3D chirality. Ab-initio reconstructions and refinements without an external chirality reference can converge to the mirror map. The map is "wrong-hand" when secondary structure (alpha helices) reads left-handed.

### How to flip correctly
- **Homogeneous Reconstruction Only with the "flip handedness" option** is the right tool when downstream refinement will follow. It flips the map **and** updates the particle pose convention so that the new map and the particles agree.
- **Volume Tools** can flip a volume in isolation, but it does **not** update particle poses. Use this only when you need to inspect or hand off a flipped volume and have no plan to refine from those particles.
- For helical samples, flipping hand also requires inverting the sign of the helical twist; otherwise downstream symmetry enforcement uses the wrong screw.

### When to flip
- Decide hand based on an atomic model or a known reference, not on visual preference.
- If unsure, do a single Homogeneous Reconstruction Only with `flip handedness` enabled and compare a downstream refinement of each hand against a reference model.

## Helical symmetry as a specialized branch
Helical symmetry uses `(twist, rise)` (or equivalently pitch, subunits-per-turn, hand). It is not a point group and most point-group intuition does not transfer.

### Shape of the workflow
- Use Helical Refinement, the Symmetry Search Utility, and Average Power Spectra rather than approximating helices with high-`Cn`.
- Enable `Limit shifts along the helical axis` before symmetry expansion so each asymmetric unit is properly centered.
- For helical expansion, the helical refinement must have produced a converged `(twist, rise)` and helical symmetry order.

### Common helical traps
- Helical hand ambiguity: a high-resolution map can still be the wrong hand. Inspect alpha-helix chirality, flip via Homogeneous Reconstruction Only, and invert the twist sign.
- Redundant `(twist, rise)` pairs: doubled twist and rise produce equivalent symmetry but use particles only half as effectively.
- Cyclic point group plus helix: when an n-start helix has additional `Cn`, that point-group symmetry is enforced along the helical axis only, not perpendicular to it.
- Do not extrapolate point-group symmetry relaxation rules onto helical refinement; the helical search has its own twist / rise local-search machinery.

## Preferred orientation, anisotropy, and symmetry
Symmetry **does not** create missing views — it only reuses existing views. A symmetric refinement on an orientation-biased stack still has the same Fourier-space gap; symmetry simply replicates the gap around the symmetry axis. Diagnose orientation bias with Orientation Diagnostics (cFAR, tFAR from v5.0, SCF\*, Relative Signal) and address it with picking / collection mitigation, not by raising symmetry. Mitigation lives in `orientation_and_preferred_views.md`.

When a symmetric target also has preferred orientation, treat the two problems independently: pick more views first, then re-run the symmetric refinement.

## Failure patterns

- **Imposed symmetry hides biology.** Symmetrized consensus looks clean, but the asymmetric ligand / inhibitor / modulator is reduced to fractional density at each symmetry-related site. Re-run consensus in C1 to confirm.
- **C1 map noisy but symmetry biologically plausible.** Usually a sign the C1 refinement is starved (low SNR, small target, hard alignment), not that symmetry is wrong. Try standard recovery moves (better cleanup, larger minibatch for any ab-initio reseeding, NU regularization) before locking symmetry in.
- **Pseudosymmetric blur.** Repeated weak bumps at symmetry-related positions; the biological state breaks the apparent symmetry. Try heterogeneous refinement with identical volumes plus `force hard classification`, then escalate to symmetry relaxation or focused classification.
- **Symmetry-expanded overclaiming.** Reporting `N × particles` as the dataset size, quoting a global FSC from a refinement run on expanded particles, or running global pose search on expanded stacks. All wrong; collapse with Remove Duplicate Particles before any global-pose step.
- **Wrong hand.** Map looks plausible, alpha helices read left-handed. Use Homogeneous Reconstruction Only with hand flipping (not Volume Tools alone), and invert helical twist sign if applicable.
- **Helical wrong rise / twist.** Map reaches moderate resolution under imposed helical parameters, but features smear along the helical axis or FSC ripples persistently. Re-run Symmetry Search Utility, check for doubled-`(twist, rise)` redundancy, and check the hand.
- **Over-tight focus mask in symmetry-expanded local refinement.** Alignment latches onto a noise island, ROI blurs at the mask edge, FSC inflates. Loosen the mask (`20_masks.md`) before adjusting search range.
- **Symmetry relaxation that "did nothing".** Almost always too few extra final passes, or the underlying problem is not pseudosymmetry. Run plain C1 and confirm relaxation is even the right tool.

## Version-aware highlights
- v4.4: regularization speed-up benefits NU and symmetry-relaxed refinements (~2× total runtime); Orientation Diagnostics introduced with cFAR / SCF\*; Regroup 3D and Heterogeneous Reconstruction Only added (useful for symmetry-expanded classification cleanup); symmetry relaxation introduced as a `Symmetry relaxation method` option in Homogeneous and Non-Uniform Refinement.
- v4.5: 3D Classification expands the solvent mask to contain the focus mask reliably; Volume Alignment Tools gains automatic re-centering on a mask centroid, which simplifies one-ASU expansion setup; refinements warn when expanded particles are connected to global pose-search jobs.
- v5.0: standardized FSC plotting with clearer per-mask attribution and phase-randomization markers; Orientation Diagnostics adds tFAR for unimodal / bimodal viewing distributions and outputs raw cFSC data; Sharpening Tools can read `fsc_mask_auto`; refinement jobs default to using existing half-set splits, which prevents accidental half-set mixing through RBMC and symmetry-expansion loops.

## Advisor defaults
1. Default to C1 at ab initio. Impose point-group symmetry only when the target is well-established or C1 reproducibly fails for structural (not biological) reasons.
2. Run the first global refinement in C1 even when symmetry is expected, to confirm imposed symmetry is consistent with the data.
3. For pseudosymmetric or symmetry-mismatch targets, prefer the order: clean upstream cleanup → C1 consensus → heterogeneous refinement with identical volumes → symmetry relaxation if needed → symmetry expansion plus focused classification or local refinement.
4. Use symmetry expansion as a setup step for local refinement, focused classification, or variability — never as a final refinement, and never feed expanded particles into a global pose search.
5. Treat handedness as a one-time decision: flip with Homogeneous Reconstruction Only (not Volume Tools alone), and invert helical twist sign when applicable.
6. Do not treat symmetry as a substitute for orientation coverage; verify with Orientation Diagnostics independently.

## Cross-links
- `06_abinitio.md` — symmetry choices at ab initio, disc-volume rescue, multiple-seed strategy.
- `07_refinement.md` — Homogeneous / NU branch logic, including symmetry relaxation as a parameter.
- `08_classification_3d.md` — focus / solvent mask logic for symmetry-aware classification.
- `09_local_refinement.md` — one-ASU local refinement after symmetry expansion.
- `10_postprocessing.md` — FSC reading under imposed symmetry, mask-tightness diagnostics.
- `11_helical.md` — helical workflow detail.
- `20_masks.md` — one-ASU mask construction, soft edges, noise-island prevention.
- `26_continuous_heterogeneity.md` — 3DVA / 3DFlex on symmetry-expanded particles.
- `orientation_and_preferred_views.md` — anisotropy diagnostics and mitigation.

## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

- `06_abinitio.md`
- `07_refinement.md`
- `08_classification_3d.md`
- `09_local_refinement.md`
- `10_postprocessing.md`
- `20_masks.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__utilities__job-symmetry-expansion.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-refinement__job-homogeneous-refinement.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-refinement__job-non-uniform-refinement-new.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-refinement__job-heterogeneous-refinement.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-refinement__job-homogeneous-reconstruction-only.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-refinement__job-heterogeneous-reconstruction-only.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-reconstruction__job-ab-initio-reconstruction.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__variability__job-3d-classification-beta.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__local-refinement__job-local-refinement-beta.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__local-refinement__job-new-local-refinement-beta.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__utilities__job-orientation-diagnostics.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__utilities__job-volume-alignment-tools.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__helical-reconstruction-beta.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__helical-reconstruction-beta__helical-symmetry-in-cryosparc.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__helical-reconstruction-beta__job-helical-refinement-beta.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__helical-reconstruction-beta__job-symmetry-search-utility-beta.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__helical-reconstruction-beta__job-average-power-spectra.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-symmetry-relaxation.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__case-study-pseudosymmetry-in-trpv5-and-calmodulin-empiar-10256.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__case-study-end-to-end-processing-of-encapsulated-ferritin-empiar-10716.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__case-study-discrete-and-continuous-heterogeneity-in-fanac1-empiar-11631-and-11632.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-3d-classification.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-orientation-diagnostics.md`
- `videos/notes/03_trpv5_and_symmetry_breaking.notes.md`
- `videos/notes/04_encapsulated_ferritin_and_non_point_group_symmetry.notes.md`
- `videos/notes/05_fanac1_and_discrete_heterogeneity.notes.md`
- `docs/forum_threads/digests/forum_3d-reconstruction.md`
- `docs/forum_threads/digests/forum_3d-classification.md`
- `reference/release_notes/markdown/v4.4.md`
- `reference/release_notes/markdown/v4.5.md`
- `reference/release_notes/markdown/v5.0.md`