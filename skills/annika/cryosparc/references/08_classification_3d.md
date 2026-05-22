# Topic 08 — 3D Classification

## Scope
Discrete heterogeneity workflows in cryoSPARC: when 3D Classification is the right branch, what it needs from upstream, which settings actually matter, how to read class volumes and histograms without overclaiming, and how to escalate to other jobs when classes do not separate cleanly. Global refinement branch logic lives in `07_refinement.md`; symmetry strategy in `19_symmetry.md`; local refinement in `09_local_refinement.md`; continuous heterogeneity (3DVA / 3DFlex) in `26_continuous_heterogeneity.md`; mask construction in `20_masks.md`; FSC and sharpening in `10_postprocessing.md`.

## Decision surface — which discrete-heterogeneity job to use

| Job | Primary question | When it is the right call |
|---|---|---|
| **3D Classification** | What discrete states exist *given* good consensus poses? | Bulk consensus is solid; question is class separation, not pose updates; differences are at the scale of ligand binding, domain rearrangement, or compositional change. |
| **Heterogeneous Refinement** | Which of N initial volumes best matches each particle, with limited pose updates? | Small pose updates are essential to separate states; pseudosymmetry rescue with identical starting volumes; cleanup branch when consensus is mixed; one class blurred in 3D Classification despite plausible identity. |
| **3D Variability Analysis (3DVA)** | What are the principal motion axes given fixed poses? | Motion is continuous; you want interpretable axes, optional clustering, and intermediate reconstructions. |
| **3D Flexible Refinement (3DFlex)** | What is a nonlinear motion model and a motion-corrected canonical map? | Continuous motion with a deformable model; particle-aware reconstruction of the canonical state. |
| **Local Refinement** | Can a fixed region of the particle be aligned independently for sharpness? | Identity is settled; the question is pose refinement on a local region, not class separation. |

Practical rule:
- if **poses are good but class identity is unknown** → start with 3D Classification;
- if **poses need to update per class** → Heterogeneous Refinement;
- if **motion is continuous** → 3DVA or 3DFlex;
- if **you only want a sharper subregion of a settled state** → Local Refinement.

3D Classification is unique in that it does *no* pose updates during classification (3D classification without alignment). That is its strength when poses are trusted, and its weakness when they are not.

## Prerequisites for a useful run
3D Classification amplifies whatever is upstream; it is rarely a fix for upstream problems.

- **Clean particle stack.** Run 2D classification and at least one cleanup branch (Heterogeneous Refinement with junk volumes, Subset Particles by Statistic on per-particle scale) before pushing into 3D Classification. Junk in, junk classes out.
- **Trusted consensus poses.** `alignments3D` must be populated and come from a job that converged cleanly — Homogeneous, NU, or a prior local refinement. Ab-initio poses alone are not stable enough to anchor classification.
- **A consensus map that matches the question.** If the consensus was refined with the *wrong* assumption (e.g., C4 imposed on a pseudosymmetric C1 channel), 3D Classification inherits that bias. Re-run consensus in the right symmetry before classifying.
- **Solvent mask covering the full particle.** From v5.0, if a solvent mask is not provided, 3D Classification generates one from the consensus by default and auto-expands it to contain any focus mask. On older versions, supply a solvent mask explicitly when using a focus mask.
- **Focus mask, only if the moving region is truly local.** A tight focus mask helps when motion is confined to a clearly bounded region; it actively hurts when motion couples to a larger domain (see failure patterns).
- **Half-set split discipline.** 3D Classification's per-class FSC filtering depends on the gold-standard split. Preserve the input split (`alignments3D/split`) when looping through Refinement → Reference Based Motion Correction → Refinement → Classification, so half-sets do not silently re-mix. v4.2 added `Force re-do FSC split` for cases where the split must be re-derived (e.g., on symmetry-expanded stacks).
- **When upstream refinement is not good enough.** If the consensus is anisotropic, lacks side-chain density at the global resolution it reports, or has wrong handedness, do not classify yet. Fix the consensus first.

## Core workflow for discrete heterogeneity
1. **Confirm the question.** Sample-identity (different particles entirely), compositional (ligand/cofactor/subunit present vs absent), or conformational (same composition, different shape). The first two are usually 3D Classification or Heterogeneous Refinement; the third may be 3DVA / 3DFlex instead.
2. **Build the consensus.** Take a curated stack through Homogeneous / NU Refinement (Topic 07). Save the consensus volume; you will reuse it.
3. **Run 3D Classification on the consensus stack** with a modest class count (3–6 typical for a first pass) at a filter resolution matched to the scale of the expected difference.
4. **Inspect outputs end-to-end.** Class volumes, class flow diagram, per-iteration occupancy histograms, mean class ESS, real-space slices, difference-from-consensus projections.
5. **Validate via reconstruction.** Where classes look promising but volumes are weakly differentiated, run **Heterogeneous Reconstruction Only** (v4.4+) on the `particles_all_classes` output with `Force hard classification` on to get per-class reconstructions that are not weighted-backprojection blends.
6. **Branch.** Select the class(es) of interest; refine each against its *own* class-specific volume (not the mixed consensus); locally refine subregions where the biology demands it.
7. **If classes are unclear**, escalate: Heterogeneous Refinement with identical starting volumes (small pose updates often separate states that fixed-pose classification cannot), or, if behavior looks continuous, 3DVA / 3DFlex.

## Class count
- **Modest count for first exposure**: 3–6 classes is usually enough to expose whether discrete structure exists at all. Class flow at low count is informative; collapse with too many classes is harder to read.
- **Larger counts (10–50+) become cheap** because 3D Classification skips alignment. Use them when the question is "expose all heterogeneity for selection", not "find the one biological state".
- **Very large counts (≥100)** are routine for sorting datasets at scale and are typically followed by Regroup 3D Classes to consolidate similar volumes into a smaller set of superclasses.
- **Match counts to the question.** Two-state apo vs liganded does not need 50 classes; complex assemblies with many compositional variants do.

## Filter / target resolution
The single most consequential parameter to choose deliberately.

- The job classifies under a low-pass filter set by this parameter. From v4.5 it is `Filter resolution` and must be set explicitly; older versions used `Target resolution`, defaulting to 6 Å.
- **Match the resolution to the scale of expected heterogeneity** (useful starting heuristic from the official tutorial):
  - 3–6 Å for small ligand presence/absence,
  - 6–10 Å for inter-domain conformational change,
  - >10 Å for presence/absence of an entire domain or binding partner.
- **Too fine** (numerically too small Å) lets noise drive classification; classes look crunchy and unstable across runs.
- **Too coarse** collapses subtly different states.
- The output class volumes are produced at the box and pixel size implied by the filter resolution. To view classes at the original extracted box size, run Heterogeneous Reconstruction Only on the per-class particles.

## Force hard classification
- Turns off weighted back-projection; each particle commits to its single best class for the per-class reconstruction.
- **Reach for it** when classes all look similar and ESS stays high — the soft assignment is averaging the classes together. Hard classification often sharply separates state-specific features that were previously smeared.
- **Cost**: per-class reconstructions use only their own particles, so they are noisier. Use Heterogeneous Reconstruction Only downstream if you want a different reconstruction box or symmetry on the hard-assigned subsets.

## ESS, class similarity, latent mixing, PCA initialization
- **Class ESS** measures how diffusely a particle is assigned across classes. A per-particle ESS of 1 means full commitment to a single class. The job's mean class ESS should drop as classification progresses; if it stays high near the number of classes through final F-EM iterations, classes are not really separating.
- **Class similarity** controls how aggressively the optimizer pushes classes apart early on. Lower effective similarity / harder separation encourages diversity but raises overfit risk; the defaults are tuned for typical cases.
- **Latent mixing coefficients (v5.0, off by default)** apply a prior over class posteriors based on current class sizes — particles that match two classes equally well prefer the larger class. Turn on when classes drift to nearly uniform occupancy; it typically produces more diverse class sizes.
- **PCA initialization** seeds classes from subset reconstructions clustered along principal components. It can help expose subtle differences but does not rescue weak upstream signal or pose bias. Use roughly 3–5 reconstructions per output class as a rule of thumb if you tune the underlying initialization.
- **Initial volumes mode** allows seeding with user-supplied maps; the number of initial volumes must match the class count.

## O-EM, full-batch EM, and convergence
- 3D Classification alternates Online EM (O-EM) on minibatches and Full-batch EM (F-EM). Larger batch sizes give smoother estimates per O-EM step; smaller batches give more updates per epoch.
- The **primary convergence criterion** is the percentage of particles switching classes; the **secondary criterion** (default on from v4.5) is the RMS density change between iterations, weighted by class size. Either crossing the threshold stops F-EM.
- If F-EM stops with many particles still switching but volumes barely changing, the secondary criterion is doing useful work — extending iterations rarely buys real signal in this regime.
- If ESS stays high through F-EM, escalate (more epochs, harder classification, better upstream refinement, or a different job) rather than letting more iterations grind.

## Solvent mask vs focus mask
- The **solvent mask** defines what counts as signal. Generous, soft-edged, covers the whole density. From v5.0 it is auto-generated from the consensus if not supplied, and auto-expanded to contain any focus mask.
- The **focus mask** restricts which voxels drive class assignment. Use it when the expected difference is geographically localized (one ligand site, one subunit on a multimer).
- **Focus mask must lie within the solvent mask.** v4.1.2 fixed mishandling of this; v5.0 made the auto-expansion robust.
- A focus mask that is too tight collapses real continuous motion of the surrounding region into noise classes. A focus mask that is too generous reduces the localization benefit and is essentially solvent-mask classification.
- Both masks should be **soft-edged**, constructed from a mildly blurred volume to avoid speckle-driven boundaries, and on the same grid as the particles. Mask construction discipline lives in `20_masks.md`.

## Interpreting outputs
3D Classification outputs more than just per-class volumes; reading them in isolation is the most common interpretation error.

- **Class volumes (v4.5+ as a Volumes group)** are filtered per-class FSC by default (v4.4+) and use weighted back-projection across particles unless `Force hard classification` is on. Two classes can show nearly identical volumes while the underlying particle subsets differ substantially.
- **Per-class particle outputs** are the real ground truth for what was separated. Reconstruct each class independently (Heterogeneous Reconstruction Only with `Force hard classification`) when the displayed class volumes look weakly distinguishable.
- **Class flow diagram and occupancy histograms** show how particles move between classes per iteration. A clean run settles into stable occupancies a few iterations before stopping. Rapid reshuffling across F-EM iterations often reflects per-particle scale issues (v4.1+ optimizes scales by default at the start of the job; older runs need an upstream refinement with per-particle scale on).
- **Mean class ESS** trajectory is diagnostic. ESS near 1 at the end means classes are committing; ESS near the class count means the run hardly separated anything.
- **Difference-from-consensus projections** (v4.0+) highlight where each class differs from the global average — useful for spotting localized changes that low-contrast class volumes might hide.
- **Rejected-particle outputs (v5.0+)** collect particles with zero or negative per-particle scale (empty/inverted contrast). Worth reviewing; rarely rescue.

## Symmetry, symmetry expansion, and one-ASU classification
Symmetry strategy lives in `19_symmetry.md`; the pieces specific to 3D Classification:

- **Do not impose symmetry blindly.** If asymmetric occupancy at symmetry-related sites is biologically possible (one ligand on a tetrameric channel, one cofactor in an icosahedral capsid), classification with imposed symmetry erases the very feature you are looking for.
- **Pseudosymmetry rescue (TRPV5 pattern):** keep the consensus C1 (or refined with symmetry then re-refined in C1), then run Heterogeneous Refinement with identical copies of the consensus volume and `Force hard classification` on. Fixed-pose 3D Classification on its own often cannot separate the symmetry-related states because poses already absorbed the ambiguity.
- **One-ASU focused classification.** After Symmetry Expansion (Topic 19), provide a focus mask covering one asymmetric unit with a generous solvent mask, and classify in C1 (the expansion already represents every symmetry-related copy). This is the right shape for resolving per-site ligand stoichiometry or per-subunit conformations on `Cn`/`Dn` assemblies.
- **Half-set independence after expansion.** Symmetry-expanded particles share image data across copies; `Force re-do FSC split` (v4.2+) is available when a split must be re-derived for already-expanded stacks.
- **Never run global pose-search refinements on symmetry-expanded outputs.** 3D Classification on expanded stacks is acceptable because it does not update poses.

## Common failure patterns

### All classes look the same
Likely causes:
- consensus poses not good enough upstream;
- class signal too subtle for fixed poses (need pose updates → Heterogeneous Refinement);
- class similarity / ESS stays soft and weighted back-projection blurs distinctions;
- filter resolution poorly chosen;
- heterogeneity is actually continuous;
- per-particle scale variability dominates classification.

Try: `Force hard classification`, drop filter resolution if chasing broad motion, fix upstream refinement, switch to Heterogeneous Refinement, or pivot to 3DVA / 3DFlex.

### Residual fake density in one class
Classic symptom in ligand-bound vs apo separations: the apo class retains weak ligand density or a blurred local domain. Class identity is partly right but inherited poses still expect the ligand-bound reference. Best next move: Heterogeneous Refinement with two identical starting volumes so per-class poses can update.

### Good occupancy histograms but uninterpretable volumes
Class posteriors separate particles better than the output volumes visually suggest, because of weighted back-projection blending. Reconstruct each class downstream (Heterogeneous Reconstruction Only with hard classification) and refine class-specific volumes before judging.

### Classes look worse after re-refinement
Re-aligning the per-class subsets to a single consensus undoes the separation. This usually means the discrete classes contain a continuous distribution — re-alignment finds the average pose for both ends of the motion. Pivot to 3DVA / 3DFlex rather than iterating rigid class/refine loops.

### Over-tight focus mask
Symptoms: classes look noisy inside the masked region, the rest of the particle is identical across classes, ESS stays high. Either the mask cuts into coupled density, or the motion of interest is global. Loosen the focus mask, or drop it and classify on the solvent mask alone.

### Continuous heterogeneity masquerading as discrete
Symptoms: re-running 3D Classification produces classes that look like steps along a continuous axis; cluster identity is unstable across runs; 3DVA on the same particles shows a clear axis. Stop forcing discreteness.

### Pose / consensus bias
Symptoms: classes are repeatable but each carries a faint copy of the consensus reference (faint ligand in the apo class, smeared asymmetric feature in a pseudosymmetric assembly). The poses themselves are biased. Fixes: re-run consensus in the appropriate symmetry, run Heterogeneous Refinement to allow small per-class pose updates, or refine each class-specific volume independently before judging.

### Empty / inverted-contrast particles
Per-particle scale ≤ 0 means the particle does not match the consensus at all. From v5.0, these are surfaced as a Rejected Particles output. Earlier versions absorb them into low-scale classes that look like junk; subset by per-particle scale upstream.

## Version-aware highlights
Grounded in the release-note sources, in workflow order:

- **v3.3** — 3D Classification (without alignment) introduced.
- **v4.0** — major rework: focus and solvent mask inputs, FSC-based per-class filtering, new convergence criteria (class switching + RMS density change), revamped diagnostic plots, fix for failure when intermediate plotting was disabled.
- **v4.1** — per-particle scale optimization built in by default; class flow matrix and Δ columns in diagnostics; option to re-order classes by size at end of run.
- **v4.1.2** — solvent-mask generation from consensus fixed when only a focus mask is supplied.
- **v4.2** — `Force re-do FSC split` parameter added; fixed `KeyError` with CTF fields when output-every-iteration was enabled; fixed extraneous `alignments3D` entry in `particles_all_classes` that confused `csparc2star.py`; class-reordering failure with intermediate output fixed.
- **v4.4** — Heterogeneous Reconstruction Only added (the canonical downstream tool for class validation and re-reconstruction); 3D Classification now filters the consensus volume by its FSC and outputs the result; revamped class tile figure; Regroup 3D Classes added for consolidating large class sets.
- **v4.5** — `Target resolution` renamed to `Filter resolution`; must be set explicitly; secondary RMS convergence criterion on by default; per-class symmetry enforcement included; class re-ordering off by default; fixed class-reordering failure when class count > 12; fixed one-pixel focus-mask plotting shift.
- **v5.0** — `Use latent mixing coefficients` parameter (off by default) for reducing uniform class sizes; Rejected Particles output surfaces zero/negative per-particle scale particles; solvent mask is auto-generated from consensus by default (controlled by `Generate solvent mask from consensus`, with spherical fallback when off); solvent mask is auto-expanded to fully contain any focus mask; output ordering fixed when class reordering is on; new real-space slice plots with improved contrast.

## Advisor defaults
When a user asks "what should I try first?":

1. Confirm the consensus is genuinely good (side-chain density at reported resolution, isotropic FSC, no preferred orientation).
2. Confirm the question is discrete (not motion along an axis), and the right granularity for the question is class separation (not pose updates).
3. Start with 3–6 classes at a filter resolution matched to the scale of expected heterogeneity (>10 Å for whole-domain presence/absence, 6–10 Å for inter-domain rearrangement, 3–6 Å for ligand sites).
4. Use the auto-generated solvent mask from consensus (or a known-good static mask); add a focus mask only when the motion of interest is truly local.
5. Keep `Force hard classification` ready if classes collapse; enable `Use latent mixing coefficients` (v5.0+) if classes drift to uniform occupancy.
6. Validate suspicious classes with Heterogeneous Reconstruction Only + hard classification before drawing conclusions from the displayed volumes.
7. If classes look right but maps stay blurry → Heterogeneous Refinement with identical starting volumes.
8. If behavior looks continuous → pivot to 3DVA / 3DFlex.
9. If the question is "which subunit is different" on a symmetric particle → Symmetry Expansion + one-ASU focused 3D Classification (C1).
10. Reconstruct selected classes against their *own* reference, not the mixed consensus, before downstream local refinement or postprocessing.

## Cross-links
- `07_refinement.md` — consensus refinement choices that feed 3D Classification.
- `09_local_refinement.md` — downstream local refinement of selected classes.
- `10_postprocessing.md` — reading FSC for per-class refinements without overclaiming.
- `19_symmetry.md` — symmetry expansion, pseudosymmetry rescue, symmetry-relaxation choices.
- `20_masks.md` — solvent and focus mask construction.
- `26_continuous_heterogeneity.md` — when to leave discrete classification behind for 3DVA / 3DFlex.
- `orientation_and_preferred_views.md` — diagnosing pose-anisotropy bias upstream of classification.
- `particle_set_operations.md` — splitting, merging, balancing half-sets across classification loops.

## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

- `docs/per_page/processing-data__all-job-types-in-cryosparc__variability__job-3d-classification-beta.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-refinement__job-heterogeneous-refinement.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-refinement__job-heterogeneous-reconstruction-only.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__variability__job-regroup-3d-classes.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__variability__job-reference-based-auto-select-3d-beta.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__utilities__job-symmetry-expansion.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__utilities__job-split-volumes-group.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__utilities__job-select-volume.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__particle-curation__job-subset-particles-by-statistic.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__post-processing__job-validation-fsc.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-3d-classification.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__case-study-discrete-and-continuous-heterogeneity-in-fanac1-empiar-11631-and-11632.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__case-study-pseudosymmetry-in-trpv5-and-calmodulin-empiar-10256.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__case-study-end-to-end-processing-of-encapsulated-ferritin-empiar-10716.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-3d-variability-analysis-part-one.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-3d-variability-analysis-part-two.md`
- `videos/notes/05_fanac1_and_discrete_heterogeneity.notes.md`
- `videos/notes/06_fanac1_and_continuous_heterogeneity.notes.md`
- `videos/notes/03_trpv5_and_symmetry_breaking.notes.md`
- `videos/notes/04_encapsulated_ferritin_and_non_point_group_symmetry.notes.md`
- `docs/forum_threads/digests/forum_3d-classification.md`
- `docs/forum_threads/digests/forum_3d-var.md`
- `docs/forum_threads/digests/forum_particle-curation.md`
- `docs/forum_threads/digests/forum_3d-reconstruction.md`
- `reference/release_notes/markdown/v4.0.md`
- `reference/release_notes/markdown/v4.1.md`
- `reference/release_notes/markdown/v4.2.md`
- `reference/release_notes/markdown/v4.3.md`
- `reference/release_notes/markdown/v4.4.md`
- `reference/release_notes/markdown/v4.5.md`
- `reference/release_notes/markdown/v4.6.md`
- `reference/release_notes/markdown/v5.0.md`