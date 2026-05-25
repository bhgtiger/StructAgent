# Topic 07 — Consensus / Global Refinement

## Scope
Producing a stable consensus 3D map after ab-initio / heterogeneous cleanup has yielded a coherent particle set: how to pick between Homogeneous, Non-Uniform, and Heterogeneous Refinement; when Reconstruction Only is the right tool; where Global/Local CTF Refinement and Reference Based Motion Correction belong in the workflow; and which symptoms route to local refinement, 3D classification, or continuous-heterogeneity workflows. Picking and 2D cleanup live in `04_picking.md` and `05_extraction_2d.md`. Ab-initio belongs in `06_abinitio.md`. Discrete 3D classification on a fixed consensus belongs in `08_classification_3d.md`. Focused / masked / subtraction-based local refinement lives in `09_local_refinement.md`. FSC reading, sharpening, and local resolution belong in `10_postprocessing.md`. Mask construction lives in `20_masks.md`. Detailed CTF refinement and RBMC parameter guidance lives in `ctf_refinement_and_rbmc.md`.

## Decision surface — which refinement job to run

| Job | Primary question | When it is the right call |
|---|---|---|
| **Homogeneous Refinement** | What is the single consensus map for this particle set? | Safer first global refinement after cleanup — stable baseline before NU assumptions, smaller targets, validating an imported reference. |
| **Non-Uniform Refinement** | Same, but with adaptive regularization for soft / disordered density | Membrane proteins with micelle/nanodisc, small targets with flexible regions, most consensus refinements where the dynamic mask is wanted. |
| **Heterogeneous Refinement** | Which of N starting volumes does each particle best match, with limited pose updates? | Cleanup branch (junk vs signal), state separation (apo vs liganded, conformer split), pseudosymmetry rescue with identical starting volumes. |
| **Homogeneous / Heterogeneous Reconstruction Only** | What does backprojection look like at this box / hand / symmetry / mask? | Hand flipping with pose update, re-boxing without re-aligning, per-class re-reconstruction, custom-mask FSC. |
| **Homogeneous Ab-Initio Refinement (BETA, v5.0+)** | Can SGD with gold-standard half-sets beat EM globally? | Rare rescue when 2D classes look excellent but Homogeneous/NU underperform. Much slower; single homogeneous output. |

Out of scope here but adjacent:
- **Local Refinement** — bulk consensus is good and one region needs sharpening (`09_local_refinement.md`).
- **3D Classification** — poses already strong and the question is "which discrete states are present?" (`08_classification_3d.md`).
- **3DVA / 3DFlex** — the heterogeneity is continuous, not discrete (`26_continuous_heterogeneity.md`).

## Standard workflow after ab-initio / 2D cleanup
The default branch tree most projects converge on, each step a deliberate choice:

1. **Heterogeneous Refinement as cleanup** — wire 2–4 ab-initio volumes (one good, one or more junk) into Heterogeneous Refinement, often with `force hard classification`, on the curated stack. Recover good particles ab-initio sent to junk and reject contaminants ab-initio kept.
2. **Homogeneous Refinement as first consensus** — take the best class to Homogeneous Refinement. The safer first global refinement: deterministic EM, no NU regularization assumptions, stable across particle sizes.
3. **Non-Uniform Refinement as second consensus** — re-run on the same particles + Homogeneous output. NU's adaptive regularization usually equals or beats Homogeneous on membrane proteins, small particles, and anything with disordered surface density. Confirm gains by comparing the corrected FSC and visible map features, not the unmasked number.
4. **Re-extract at full pixel size** before the corrected FSC approaches the cropped-stack Nyquist, then re-refine.
5. **Late-stage correction branch** — Global / Local CTF Refinement and Reference Based Motion Correction once the consensus is solid (below).
6. **Handoff** — local refinement of ROIs (Topic 09), 3D classification (Topic 08), continuous heterogeneity (Topic 26), or postprocessing (Topic 10) depending on the next biological question.

This is the path; the rest of this topic is when to deviate.

## Homogeneous Refinement — the safer first branch
Homogeneous Refinement runs EM with gold-standard half-sets against a single input volume, GSFSC-filtered each iteration. Reach for it first when:
- it is the project's first global refinement and you want a stable baseline before introducing NU assumptions,
- the target is small and NU regularization may pick up noise,
- you intend to use the output as the comparison map for NU, CTF refinement, or RBMC,
- you are validating an imported / EMDB reference and want the simplest possible job.

Setup notes without inventing parameter names:
- **Initial low-pass:** keep coarse (numerically higher Å) when the starting volume is from ab-initio or a heterogeneous-refinement class. Use a finer resolution only when starting from a trusted high-resolution reference.
- **Greyscale re-estimation:** keep on, especially when the reference came from another project or EMDB; mismatched greyscale degrades alignments.
- **Per-particle scale:** keep on. From v5.0, refinements perform per-particle scale optimization by default; the values are useful downstream (Subset Particles by Statistic on `alignments3D/alpha`).
- **Mask:** prefer the dynamic refinement mask (v5.0 onward is robust across resolutions); supply a static mask only when dynamic clearly cuts into real density or a custom FSC region is needed.
- **Symmetry:** start at C1 unless symmetry is well-established. Pseudosymmetric targets (Topic 19) should not be locked into apparent symmetry here.
- **Window:** the default real-space window assumes well-centered particles; tighten only on crowded grids where neighbors leak in.
- **Extra final passes:** useful mainly with symmetry relaxation; otherwise leave at default and let GSFSC convergence stop the job.

Homogeneous Refinement (Legacy) is retained for compatibility but the current job subsumes its features with higher-order CTF support and faster kernels.

## Non-Uniform Refinement — when it helps and when it hurts
NU is Homogeneous plus adaptive cross-validation regularization and adaptive marginalization, all GPU-accelerated. Memory scales roughly as `3 × box³ × 4` bytes; a 12 GB GPU handles up to ~1024³. v4.4 made regularization 7–10× faster (~2× overall); `Low-memory mode` reverts to the pre-v4.4 path when VRAM is tight (notably box ≳ 600 on 11 GB, ≳ 700 on 16 GB, ≳ 882 on 32 GB).

Reach for NU when:
- the target is a membrane protein with micelle / nanodisc / detergent belt,
- the target is small with flexible loops or termini dragging global resolution down,
- Homogeneous converged but the map shows clear surface noise or oversharpened streaks.

Cautions:
- **Overfitting via too-tight masks.** Tight FSC inflates without Corrected following. If Corrected drops sharply where Tight stays high, relax the dynamic-mask threshold (as low as 0.05 in extreme cases) or supply a softer static mask. FSC reading detail is in Topic 10; mask construction in Topic 20.
- **NU can be worse than Homogeneous** on small or unusual targets. v5.0 added a switch to disable the dynamic refinement mask in NU — for some targets this produces better results. Treat as an explicit branch to test, not a default.
- **Per-particle scale:** keep on. Very-low-scale particles are commonly junk or ice-contaminated.
- **Adaptive Marginalization** is on by default and usually helps small / noisy particles; disable only when isolating regression behavior.

If NU underperforms Homogeneous on the same particles + volume, that itself is diagnostic: either the consensus state is mixed (route to Heterogeneous Refinement or 3D Classification), the mask is too tight, or the dataset is unusually noisy at the chosen box.

## Heterogeneous Refinement — cleanup and state separation, not final polish
Heterogeneous Refinement simultaneously classifies particles among N starting volumes and refines each. Treat it as:
- the workhorse **cleanup** branch — wire 1 good + N junk volumes (often with `force hard classification`) to recover good particles ab-initio missed and reject contaminants ab-initio kept,
- the workhorse **state-separation** branch — wire **identical copies of the consensus volume** so that small pose updates per class can do work fixed-pose 3D Classification cannot,
- a **pseudosymmetry rescue** — when a symmetry-imposed consensus has averaged out a symmetry-breaking feature, Heterogeneous Refinement with identical volumes (sometimes combined with symmetry relaxation) can recover the asymmetric state.

Setup notes:
- **Identical starting volumes** is a deliberate strategy, not a misconfiguration. Class identity is decided by particle-side perturbations and pose updates.
- **Force hard classification** — turn on when classes drift toward identical occupancy or you want clear commitment instead of probabilistic blending.
- **Initial models must be on the correct greyscale.** Ab-initio outputs satisfy this; externally imported maps may not.
- **Spherical mask (v4.5+)** — inner/outer diameter controls; defaults are usually fine.
- **Outputs (v4.5+):** the All Volumes output is a volumes-group, ready to drop into Heterogeneous Reconstruction Only or downstream selection.

Common failure modes here:
- **Class collapse** — all classes drift to the same volume. Try `force hard classification`, fewer classes, or seed with deliberately diverse volumes.
- **One class absorbs junk** — fine, that is the cleanup working; remove that class and re-refine the rest.
- **Consensus biased by mixed states** — if the input consensus was refined under the wrong assumption (e.g., C4 on a pseudosymmetric C1 channel), classes may all carry the bias. Re-run consensus in C1, then retry.

If Heterogeneous Refinement finds the right idea but maps stay blurry, the next move is usually 3D Classification (Topic 08) or, if motion is continuous, 3DVA / 3DFlex (Topic 26).

## Reconstruction Only — surgical jobs, not refinements
Reconstruction Only jobs perform backprojection from existing `alignments3D` without alignment iterations. Use them when alignments are already correct and something *about* the reconstruction needs to change.

Common uses:
- **Hand flipping with pose update.** Volume Tools flips the volume only; **Homogeneous Reconstruction Only with `Flip handedness`** updates both the map and the particle pose convention, which is what downstream refinement actually needs.
- **Re-boxing / pixel-size override** without re-refining (useful after Symmetry Expansion, in helical workflows where particles are pre-aligned, or after pixel-size recalibration).
- **Validating class assignments.** Heterogeneous Reconstruction Only takes `particles_all_classes` from a 3D Classification or Heterogeneous Refinement and reconstructs every class at a new box / mask / symmetry. `Force hard classification` here gives per-class reconstructions that ignore the weighted-backprojection blending that can make 3D Classification volumes look more similar than the underlying assignments are.
- **Recomputing FSC with a custom mask** — pair Homogeneous Reconstruction Only with Validation (FSC).
- **Ewald sphere correction**, helical reconstruction with helical-symmetry-aware backprojection, and symmetry breaking (randomization across symmetry-related poses) all live in this family.

Do **not** use Reconstruction Only to "fix" a bad refinement — if the poses are wrong, only re-aligning fixes them.

## Late-stage correction branch — CTF refinement and RBMC
Last-mile improvements that should run **only after a good consensus exists**. They consume a high-quality 3D reference and update per-particle metadata (defocus, higher-order aberrations, per-frame motion + empirical dose weights). Method and parameter detail belong in `ctf_refinement_and_rbmc.md`; this page just places them in the workflow.

Placement rule:
- Consensus is genuinely good (clean map, reasonable FSC) → **Local CTF Refinement** (per-particle defocus; from v5 jointly optimizes per-particle scale) and **Global CTF Refinement** (per-exposure-group beam tilt, trefoil, optionally spherical aberration / tetrafoil / anisotropic magnification) → re-refine to confirm gain.
- Consensus is solid and raw movies + per-particle scale are available → **Reference Based Motion Correction (BETA)** to re-estimate per-particle trajectories and empirical dose weights → re-extract → re-refine.
- **Half-set integrity:** from v4.5 refinement jobs default to using the input particles' existing `alignments3D/split`, which prevents the worst RBMC → refinement half-set contamination loops. Confirm the split is preserved when chaining late-stage jobs.

Running these before consensus quality is achieved typically wastes compute and can mask the real refinement problem.

## Branch logic by symptom
- **Blurry consensus, particles look fine in 2D** → try NU if you ran Homogeneous (or vice versa); if both fail, inspect for mixed states with Heterogeneous Refinement (identical volumes) before reaching for local refinement. As a last rescue, Homogeneous Ab-Initio Refinement (BETA, v5.0+).
- **Mixed states suspected** (ligand bound vs apo, two conformers) → Heterogeneous Refinement with identical or near-identical starting volumes, then re-refine each class; only escalate to 3D Classification (Topic 08) once per-class poses are right.
- **Preferred orientation / anisotropy** → Orientation Diagnostics (cFAR < 0.5 or SCF\* < 0.81 flag bias; tFAR added v5.0 for unimodal distributions) and the cFSC summary plot (refinements emit one every iteration from v4.5); mitigate with Rebalance Orientations, re-picking missing views, or tilted data. Postprocessing cannot create views that were never collected. Detail in `orientation_and_preferred_views.md`.
- **FSC at Nyquist** — from v5.0 refinements throw an explicit Nyquist warning. Re-extract at a smaller pixel size and re-refine; sharpening past Nyquist is meaningless.
- **Wrong hand** — Homogeneous Reconstruction Only with `Flip handedness` (also updates particle poses). Do not flip in Volume Tools alone.
- **Pseudosymmetric blur** — re-run consensus in C1; for symmetry-breaking features inside a symmetric scaffold, combine Heterogeneous Refinement (identical volumes), symmetry relaxation, or symmetry expansion + masked classification (Topic 19, Topic 08).
- **Per-particle scale very low for many particles** — often junk, ice contamination, or wrong state; use Subset Particles by Statistic (`alignments3D/alpha`) to triage, then re-refine the kept set.
- **CTF / motion limits suspected** — only after consensus is good, route to Local + Global CTF Refinement and / or RBMC.
- **Resolution suddenly improves after re-refinement** — suspect half-set contamination (especially after re-extraction or RBMC) before celebrating; confirm `alignments3D/split` is preserved.

## Failure patterns
- **OOM / GPU memory in NU.** `cufftAllocFailed`, `cuMemAlloc failed: out of memory`, or allocation errors that scale with box. Fixes: turn on `Low-memory mode` (NU), reduce box / extract with more Fourier crop, reduce GPU count, move to a higher-VRAM card. Extraction-side memory bugs were addressed in v4.1; v5.0 surfaces lane-resource exhaustion more clearly.
- **Mask over-tightening.** Corrected FSC dips well below Tight; Spherical / Loose stay widely separated; sharp phase-randomization spike at high resolution. Relax the dynamic-mask threshold or supply a softer static mask. Detail in Topic 10 and Topic 20.
- **Half-set split contamination.** Repeated re-refinement after re-extraction or RBMC can re-mix half-sets if `alignments3D/split` is not preserved. From v4.5 the default is to preserve the input split; verify when chaining late-stage jobs. Particle Sets Tool can balance unequal splits; Subset Particles by Statistic (v5.0) can re-split based on `alignments3D/split`.
- **Class collapse in Heterogeneous Refinement.** All classes drift toward the same volume. Fix: `force hard classification`, reduce class count, supply more diverse seeds, or check whether the consensus was biased by an over-imposed symmetry.
- **NU worse than Homogeneous.** Real on small / unusual targets. Report Homogeneous as the consensus, or test v5.0's option to disable the dynamic refinement mask in NU.
- **Consensus biased by mixed states.** Cleanup-branch Heterogeneous Refinement keeps producing classes that share suspicious residual density (e.g., ligand-like blob in apo class). Fix: re-run consensus in C1 if symmetry was imposed, or pivot to Heterogeneous Refinement with identical volumes followed by per-class re-refinement.
- **Imported initial volume produces nonsense.** Greyscale mismatch — keep greyscale re-estimation on. Ab-initio outputs satisfy the greyscale requirement; externally imported maps may not.

## Version-aware highlights
- **v4.0**: Homogeneous Refinement absorbs Legacy features, adds higher-order CTF support and optimized GPU kernels; Global CTF Refinement fits only third-order aberrations (Tilt / Trefoil) by default unless higher orders are explicitly enabled.
- **v4.1**: Extract from Micrographs (GPU) memory regression fixed; Restack Particles introduced to consolidate curated stacks before late-stage refinements.
- **v4.4**: NU regularization 7–10× faster (~2× overall); 16-bit float outputs in motion correction and extraction; Reference Based Motion Correction (BETA) introduced; Orientation Diagnostics (cFAR / SCF\*) replaces standalone 3DFSC for anisotropy assessment; symmetry relaxation in Homogeneous and NU; Symmetry Break option in Homogeneous Reconstruction.
- **v4.5**: refinements emit a cFSC summary plot every iteration; Heterogeneous Refinement supports spherical-mask diameter controls; Volumes-group outputs simplify multi-class handoffs; default preserves `alignments3D/split` across re-refinement loops; Rebalance Orientations added.
- **v4.6**: refinement and 2D I/O up to 2.1× faster; per-job RAM warnings before launch; transparent-hugepage handling improvements (notably for multi-GPU stability).
- **v5.0**: new resolution-scaled dynamic-mask algorithm (Topic 20); Homogeneous Ab-Initio Refinement (BETA) as a half-set-aware rescue; per-particle scale on by default in refinements; explicit Nyquist warning; Local CTF Refinement optimizes defocus + per-particle scale jointly; FSC plot colors standardized; refinements output `mask_refine`, `mask_fsc`, and `mask_fsc_auto` as separate slots; NU can run with no refinement mask via a new switch; tFAR added alongside cFAR for unimodal / bimodal viewing distributions.

## Advisor defaults
If a user asks "I just finished ab-initio cleanup, what next?":
1. **Heterogeneous Refinement** (good + junk volumes, `force hard classification`) to rescue good particles and dump junk.
2. **Homogeneous Refinement** on the best class as the first stable consensus.
3. **Non-Uniform Refinement** on the same particles + Homogeneous output; compare corrected FSC and visible features, not unmasked numbers.
4. **Re-extract at full pixel size** before the corrected FSC approaches the cropped Nyquist, then re-refine.
5. Confirm consensus quality (clean map, no FSC dip at Nyquist, reasonable cFAR), then route to **Local / Global CTF Refinement** and / or **RBMC**.
6. Hand off to local refinement (Topic 09), discrete classification (Topic 08), continuous heterogeneity (Topic 26), or postprocessing (Topic 10).

## Cross-links
- `05_extraction_2d.md` — box size, Fourier crop, Nyquist headroom.
- `06_abinitio.md` — generating the volumes that seed Heterogeneous Refinement and Homogeneous consensus.
- `08_classification_3d.md` — discrete heterogeneity on a fixed consensus.
- `09_local_refinement.md` — focused refinement and particle subtraction.
- `10_postprocessing.md` — FSC reading, sharpening, local resolution, anisotropy interpretation.
- `19_symmetry.md` — imposed symmetry vs C1, symmetry expansion, relaxation.
- `20_masks.md` — dynamic vs static masks, construction, validation.
- `26_continuous_heterogeneity.md` — 3DVA / 3DFlex.
- `ctf_refinement_and_rbmc.md` — detailed CTF refinement and RBMC guidance.
- `orientation_and_preferred_views.md` — diagnosing and mitigating preferred orientation.
- `version_caveats.md` — version-mixed forum advice and known regressions.

## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-refinement.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-refinement__job-homogeneous-refinement.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-refinement__job-homogeneous-refinement-legacy.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-refinement__job-non-uniform-refinement-new.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-refinement__job-non-uniform-refinement-legacy.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-refinement__job-heterogeneous-refinement.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-refinement__job-heterogeneous-reconstruction-only.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-refinement__job-homogeneous-reconstruction-only.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-reconstruction__job-ab-initio-reconstruction.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-reconstruction__job-homogeneous-ab-initio-refinement-beta.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__ctf-refinement__job-global-ctf-refinement.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__ctf-refinement__job-local-ctf-refinement.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__motion-correction__job-reference-based-motion-correction-beta.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__particle-curation__job-rebalance-orientations.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__utilities__job-orientation-diagnostics.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__utilities__job-volume-alignment-tools.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__post-processing__job-validation-fsc.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-dynamic-masking-in-refinements-v5.0.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-ctf-refinement.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-orientation-diagnostics.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__case-study-dktx-bound-trpv1-empiar-10059.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__case-study-discrete-and-continuous-heterogeneity-in-fanac1-empiar-11631-and-11632.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__case-study-pseudosymmetry-in-trpv5-and-calmodulin-empiar-10256.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__case-study-end-to-end-processing-of-encapsulated-ferritin-empiar-10716.md`
- `videos/notes/02_trpv1_and_a_standard_workflow.notes.md`
- `videos/notes/03_trpv5_and_symmetry_breaking.notes.md`
- `videos/notes/05_fanac1_and_discrete_heterogeneity.notes.md`
- `videos/notes/08_reference_based_motion_correction.notes.md`
- `docs/forum_threads/digests/forum_3d-reconstruction.md`
- `docs/forum_threads/digests/forum_3d-classification.md`
- `docs/forum_threads/digests/forum_motion-correction.md`
- `docs/forum_threads/digests/forum_particle-curation.md`
- `docs/forum_threads/digests/forum_troubleshooting.md`
- `17_error_lookup.md`
- `reference/release_notes/markdown/v4.0.md`
- `reference/release_notes/markdown/v4.1.md`
- `reference/release_notes/markdown/v4.2.md`
- `reference/release_notes/markdown/v4.3.md`
- `reference/release_notes/markdown/v4.4.md`
- `reference/release_notes/markdown/v4.5.md`
- `reference/release_notes/markdown/v4.6.md`
- `reference/release_notes/markdown/v5.0.md`
