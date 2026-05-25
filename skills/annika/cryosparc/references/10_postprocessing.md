# Topic 10 — Postprocessing

## Scope
What to do — and what *not* to do — after a refinement converges: reading FSCs honestly, sharpening without inventing detail, looking at local resolution and anisotropy as cautions rather than scores, and recognizing when an ugly postprocessing plot is telling you to go upstream rather than polish downstream. Mask construction details belong in `20_masks.md`; refinement branch logic in `07_refinement.md`; local refinement in `09_local_refinement.md`; external job mechanics in `23_external_jobs.md`; deep troubleshooting in `15_troubleshooting.md`.

## Decision surface — what postprocessing can and cannot tell you
Postprocessing is an *interpretation* layer, not a *rescue* layer. It is good at:
- summarizing how well two independent half-maps agree (FSC),
- revealing the high-frequency content present in a map (sharpening),
- showing where in the volume resolution is even or uneven (local resolution),
- showing whether good-looking global numbers hide a directional weakness (orientation diagnostics, cFSC),
- flagging particles whose contribution is empty or inverted (per-particle scale).

It cannot:
- fix wrong alignments — sharpening a misaligned map produces a prettier wrong map;
- separate mixed states — a blurred ligand or smeared domain is a refinement / classification problem, not a B-factor problem;
- compensate for too few particles, preferred orientation, or wrong handedness;
- turn an over-tight mask into a real resolution gain — the masked numbers will look better while the map gets worse;
- meaningfully interpret a map whose consensus refinement was already overfit.

Practical rule: if the postprocessing plot is showing you a structural problem (dip in corrected FSC, sharp anisotropy in cFSC, large patch of bad local resolution at the ROI, Nyquist saturation), the right next move is almost always **upstream** (refinement branch, particle cleanup, extraction box, sample prep), not a different sharpening or mask setting.

## The main postprocessing jobs and what question each one answers
A short retrieval map. Each job has a primary question; using one to answer another job's question is one of the most common interpretation mistakes.

| Job (UI name) | Question it actually answers | Mis-use to avoid |
|---|---|---|
| **Sharpening Tools** | What does the map look like with a chosen B-factor / Guinier-fit B-factor applied, optionally with a custom lowpass? | Treating a more-sharpened version as evidence of more signal. |
| **Validation (FSC)** | What is the gold-standard FSC between supplied half-maps under a supplied (or auto) mask? | Recomputing FSC against an arbitrary tight mask and quoting that as the resolution. |
| **Local Resolution Estimation** | Which voxels are estimated to be at higher or lower resolution, given the same half-maps? | Reading the colored volume as a per-particle quality score or as biological confidence. |
| **Local Filtering** | What does the map look like when each region is filtered to its locally-estimated resolution (optionally with global sharpening)? | Treating a locally-filtered figure as the primary scientific map for FSC/resolution claims. |
| **Orientation Diagnostics** | Is the resolution direction-dependent? cFAR / tFAR / SCF\* / Relative Signal summarize how anisotropic the signal and the alignment-implied sampling are. | Reading the angular plots as a particle-count histogram (they are not — see below). |
| **ResLog Analysis** | How does FSC resolution scale with particle count for this stack? | Quoting a single ResLog point as the dataset's true resolution, or expecting it to diagnose mask / orientation / classification issues. |
| **DeepEMhancer (external)** | What would a learned post-sharpening model produce, mostly for visualization? | Treating the cosmetic output as a primary scientific result. Delegated; see `23_external_jobs.md`. |

Refinement jobs already emit most of these things at every iteration (FSC curves, mask plots, viewing-direction plot, cFSC summary from v4.5+). The standalone jobs above are mostly for *cleaner re-interpretation* with custom inputs (alternate mask, externally generated half-maps, etc.), not for doing something the refinement could not.

## Reading FSC in cryoSPARC without fooling yourself

### The five curves you actually see
cryoSPARC plots up to five FSC curves on the same axes. They differ only in the mask used.

- **No Mask** — raw half-map FSC, structure plus solvent. Drops earliest. Useful as the reference for where to start phase randomization in the corrected curve.
- **Spherical** — soft sphere covering the box. Adds modest masking effect.
- **Loose** — soft mask from thresholded density dilated ~25 Å (1.0) to ~40 Å (0.0). Conservative; usually close to the truth for well-behaved maps.
- **Tight** — same construction with ~6 Å / ~12 Å dilations. Hugs the density.
- **Corrected** — the tight-mask FSC after noise-substitution correction: high-frequency phases of both half-maps are randomized beyond the no-mask resolution, FSC is recomputed under the tight mask, and the correction adjusts for the correlation that mere masking can induce.

cryoSPARC also performs an automatic tightening step at the end of refinement that keeps shrinking the tight mask as long as the corrected FSC keeps improving and stops when it stops. The "auto-tightened" mask is itself emitted as an output (`mask_fsc_auto` from v5.0). v5.0 standardized the FSC plot colors and clearly indicates which mask each curve came from and whether phase randomization was applied.

### Which curve to quote
**Corrected** is the one to interpret resolution from. Quoting the tight-masked or loose-masked number when the corrected number is materially worse is overclaiming. The corrected curve being *lower* than the tight one is not a failure — it is the correction doing its job, showing that some of the tight-mask correlation was a masking artifact.

### Honest reading of curve shape
- A clean refinement has the four masked curves stacked in the order Spherical < Loose < Tight < Corrected at high resolution, with Corrected only modestly below Tight.
- **Big gap between Spherical/Loose and Tight/Corrected** = a lot of correlated signal sits outside the tight mask. Often means the tight mask is too tight or there is real ordered density (e.g. micelle, glycans) that the auto-mask threw away.
- **Corrected drops sharply where Tight stays high** = the tight-mask number was inflated by mask-induced correlation. Trust Corrected, not Tight.
- **Corrected is essentially identical to No Mask** = masking is not buying anything; either the particle fills the box or the mask is meaningless.

### Dips in corrected FSC: three real causes, in order of frequency
The corrected curve sometimes shows a clear dip — a local minimum somewhere between low and high resolution. Three causes recur:

1. **Phase-randomization boundary artifact.** The dip sits exactly at the resolution where phase randomization started. It is mechanical, not a sample problem. Field practice is to leave the dip visible rather than hide it, because its presence is evidence that correction was applied.
2. **Too-tight or hard-edged FSC mask.** A mask that bites into real density (or has a hard edge) inflates the tight FSC and the correction then carves a dip. Symptom: the dip is large, the corrected curve drops well below Tight, and Spherical/Loose stay well separated. Mitigation: relax the dynamic-mask threshold (going as low as ~0.05 in extreme cases), supply a manually built soft mask, or inspect `mask_refine` and `mask_fsc` in the job directory to confirm the mask is not cutting density. Mask construction lives in `20_masks.md`.
3. **Real disordered density at the surface.** Membrane micelles, flexible glycans, flexible termini, and disordered loops legitimately produce a dip in the same region every time, even with a generous mask. This dip will shrink as the structure cleans up but rarely disappears entirely. It is a *sample* statement, not a refinement bug.

A dip below zero is more concerning than a small dip — it points strongly to mask or model-bias problems rather than disorder.

### Half-set independence is not optional
The corrected FSC means nothing if the half-sets are not independent. Two practical pitfalls to watch:

- **Repeated refinement after RBMC / re-extraction can re-mix half-sets** if you do not preserve the upstream split. From v4.5.3 onward refinement jobs default to using the input particles' existing `alignments3D/split`, which fixes the worst version of this for RBMC → refinement loops. If you imported particles, re-bucketed them, or routed them through tools that do not propagate the split, you may end up with half-sets that share particles between A and B. Particle Sets Tool now has an option to balance unequal half-set splits, and Subset Particles by Statistic from v5.0 can re-split based on `alignments3D/split`.
- **Ab-initio outputs are not the right place to make a final resolution claim.** Use them for initialization and cleanup, then run a refinement (homogeneous, NU, helical, local — or v5.0's Homogeneous Ab-Initio Refinement, which does preserve gold-standard independence) before quoting the structure's resolution.

If the corrected FSC suddenly improves after a series of re-refinements, suspect half-set contamination before celebrating.

### Nyquist saturation — a re-extract branch
If the corrected FSC is still well above 0.143 at the Nyquist frequency (1 / 2·pixel_size), you have run out of frequency space and the reported resolution is artificially limited by the box pixel size, not by signal. From v5.0 refinement jobs throw an explicit Nyquist warning recommending re-extracting at a smaller pixel size. The correct response is:

- re-extract particles with a smaller binning (or no Fourier crop),
- re-refine on the new box,
- compare the new corrected curve.

This is a **first-class branch**, not a cosmetic detail. Trying to sharpen, tighten the mask, or use Validation (FSC) to "push past" Nyquist is meaningless; the information is not in the data at that box size. Box / extraction implications are covered in `05_extraction_2d.md`.

## Sharpening: helpful reveal vs fake detail

### What sharpening is doing
Sharpening multiplies the amplitudes of the map by an exponential factor controlled by a negative B-factor, then (typically) applies a lowpass at or beyond the FSC resolution. Lower (more negative) B-factor = more boost at high frequencies.

- **Auto / Guinier B (v4.4+).** Sharpening Tools estimates a B-factor from a Guinier plot of the half-map amplitudes when one is not specified, with options to include mask weights and FSC weights in the fit. This is usually the right starting point for a single-particle map at moderate resolution.
- **Manual B-factor.** Useful when the auto fit produces obviously over-sharpened detail or when comparing maps across the same dataset on a consistent scale.
- **Lowpass / Butterworth (v5.0+).** Sharpening Tools can now sharpen without an FSC filter, applying a custom Butterworth lowpass instead. This is helpful when the FSC weight is itself misleading (anisotropic resolution, mask artifacts) and you want a fixed-cutoff view, and is the cleaner option when comparing several maps on a uniform filter.
- **Mask handling (v5.0+).** Sharpening Tools reads the auto-tightened FSC mask from the input volume group by default and can run without a mask if needed.

### Helpful reveal vs hallucination
Sharpening can legitimately reveal side-chain density, β-strand separation, and clean helix grooves that a Guinier-flat map only hints at. It can also paint plausible-looking high-frequency features on top of noise. Two practical checks:

- **Always look at the unsharpened map.** If a feature only exists once a strong negative B-factor is applied and is invisible at all in the unsharpened or modestly-sharpened map, treat it skeptically. Real signal becomes clearer with sharpening; pure noise becomes louder and looks like dotty side chains.
- **Match-threshold comparison, not eyeballed pretty-picture comparison.** When comparing sharpening choices, set the contour level to the same enclosed volume or the same number of standard deviations. A more-sharpened map at a lower threshold will trivially "show more detail" while displaying more noise.

### Where sharpening will not help
- **Wrong alignments.** Sharpening a misaligned reconstruction produces a sharper but blurred map. The streaks, doubling, and missing density do not go away.
- **Mixed states.** A class with residual ligand or smeared domain density does not become unmixed with a more aggressive B-factor; it just becomes a louder mixture.
- **Anisotropy.** Sharpening is isotropic in this implementation; the direction in which the map is poorly resolved is still poorly resolved afterwards. Trying to compensate by changing the B-factor makes the well-resolved directions noisy without fixing the bad ones.
- **Nyquist-limited maps.** No B-factor can recover frequencies the box does not support. Re-extract first.

### DeepEMhancer and learned post-sharpening
DeepEMhancer (and similar external models) can produce visually striking maps but are *learned cosmetic enhancements* rather than rigorous validations. Treat them as a way to make figures and to guide model-building, not as a replacement for the corrected FSC, the unsharpened map, or careful local-resolution review. Integration details live in `23_external_jobs.md`.

## Local resolution, local filtering, cFSC, anisotropy, and per-particle scale

### Local Resolution Estimation — what it is good for, what it is not
Local Resolution Estimation gives a per-voxel resolution colormap of the consensus (or local-refined) map, computed from the same half-maps used by the global FSC. Good uses:

- spotting **uneven quality**: a flexible domain that is markedly worse than the rigid core; a region adjacent to the focus mask that fell off in quality;
- spotting **mask artifacts**: a rim of artificially-good resolution right at the mask edge typically means the mask hugged too tightly;
- comparing different processing branches on the *same* particles to see whether a local refinement actually improved the ROI rather than redistributing quality.

Misreads to avoid:

- **It is not a per-particle quality score.** Local resolution is a property of the *voxels*, integrating over all particles. Two particles that contribute equally to a voxel get the same credit.
- **It is not a biological-confidence map.** A region can be "high resolution" by FSC and still be wrongly assigned because of mixed conformations; conversely, a moderately-resolved region can be biologically correct.
- **It is not a substitute for inspecting the unsharpened map.** A colorful good-looking local-resolution plot does not mean the underlying density is interpretable.

A v4.6.2 fix corrected a Z-flip in how local-resolution colormaps were displayed in the volume viewer; on older builds, a flipped-looking colormap may be a display artifact rather than a real result, so update before deep interpretation if the version is old.

### Local Filtering — when it is appropriate, when it misleads
Local Filtering pairs with Local Resolution Estimation: it consumes the half-maps plus the local-resolution map (and optionally a refinement mask) and produces a single output map whose every voxel is filtered to its local resolution, with optional global B-factor sharpening on top.

Use it for:
- **figures and model-building displays** of maps where one region is materially better resolved than another (membrane proteins with a sharp core + flexible periphery; flexible appendages on a rigid scaffold);
- **avoiding the over-sharpened look** of a globally Guinier-sharpened map in the regions where the local resolution does not support it.

Treat with caution:
- a locally filtered map is **not** the right input for quoting resolution — quote the corrected FSC of the underlying refinement, not anything derived from the locally filtered output;
- garbage-in, garbage-out: if the local-resolution map is itself unreliable (mask too tight, severe anisotropy, very few particles), the local filtering inherits that. Inspect the local-resolution colormap first.

### cFSC and orientation plots are not particle histograms
This is the single most common misread in this area. Conical FSC plots, the cFSC summary that refinements produce at every iteration (v4.5+), and the angular plots in Orientation Diagnostics are about **signal quality as a function of viewing direction**, not particle counts as a function of viewing direction. The two often correlate (preferred orientation typically yields strong cFSC on the populated views and weak cFSC on the rare ones), but they are different quantities:

- cFSC / cFAR / tFAR / Relative Signal answer "in what direction does my reconstruction actually carry frequencies?"
- the viewing-direction distribution plot answers "where did the particles end up pointing?"

A map can have a flat viewing-direction distribution and still have anisotropic cFSC (e.g. when alignments are wrong in a systematic direction), and vice versa.

### Orientation Diagnostics, briefly
The Orientation Diagnostics job (v4.4+) computes summary anisotropy measures from a refinement's outputs:
- **cFAR** (Conical FSC Area Ratio) — sensitive to anisotropy in both signal and alignment-implied sampling.
- **SCF\*** (Sampling Compensation Factor) — sensitive to anisotropy in alignment-derived sampling.
- **Relative Signal** (v4.5+) — direct identification of underrepresented views via FSCs in toroidal Fourier sections.
- **tFAR** (v5.0+) — a toroidal variant of cFAR that better captures unimodal / bimodal viewing distributions.

Use these when the global corrected FSC looks acceptable but downstream model-building or map appearance suggests directional weakness. The 3DFSC wrapper has been a legacy job since v4.4 — its functionality is rolled into Orientation Diagnostics. If anisotropy is severe, the right next move is **upstream**: rebalance orientations (Rebalance Orientations job, v4.5+), add tilted data, change sample-prep conditions, or accept the limitation — not turn up sharpening to hide it.

For a deeper view on diagnosing and mitigating preferred orientation, see `orientation_and_preferred_views.md`.

### Per-particle scale as an interpretation clue
From v5.0, refinements (Homogeneous, NU, Helical) optimize a per-particle scale alongside poses. Two pieces of this are postprocessing-relevant:

- Particles with **zero or negative scale** are emitted as a separate "Rejected Particles" output. They represent particles whose contribution was empty or inverted (often blank micrographs, severe edge cases, or contrast-inverted imports). Their existence in nontrivial numbers is itself a diagnostic of an upstream problem.
- The distribution of optimized scales is a soft quality measure of the stack: a long tail of low scales suggests heterogeneity in particle quality and is something **Subset Particles by Statistic** (v5.0 update) can act on directly.

Per-particle scale is an interpretation clue, not a primary postprocessing job. It tends to show up here as "why is the corrected FSC not improving despite more particles?" — a long tail of near-zero-scale particles can quietly fail to contribute. Refinement / cleanup context lives in `07_refinement.md`.

### ResLog Analysis — a secondary diagnostic
ResLog Analysis reconstructs the dataset at a sequence of particle-count subsets and reports how FSC resolution scales with N. It is useful as a sanity check on whether the stack is **particle-count limited** (adding particles would still improve resolution) versus **information limited** (collecting more would not help much without a change in sample, picking, or alignment). Treat it as a secondary diagnostic: a flat ResLog curve does not by itself diagnose preferred orientation, mask issues, or classification — it only says "more of the same particles will not buy more resolution". Pair it with Orientation Diagnostics and local resolution before concluding anything about sample limits.

## When plots tell you to go upstream instead of polishing downstream

A compact symptom → likely upstream branch table. Use it when postprocessing is showing you something you do not like.

| Postprocessing symptom | Likely root | Branch to try (not more sharpening) |
|---|---|---|
| Corrected FSC saturates at or near Nyquist; warning fires | Pixel size / box too coarse | Re-extract at smaller pixel size; re-refine. See `05_extraction_2d.md`. |
| Big spherical/loose-vs-tight gap with sharp corrected drop and obvious dip | Mask too tight or too hard | Relax dynamic-mask threshold or supply manual soft mask; check `mask_fsc`. See `20_masks.md`. |
| Recurring dip in corrected FSC around the same shell every run | Real disorder (micelle, glycans, flexible tail) | Accept as sample property; consider local refinement on rigid core; consider symmetry expansion + masked classification if it is a peripheral motif. See `09_local_refinement.md`. |
| Corrected FSC suddenly improves after re-refinement of already-refined particles | Half-set contamination | Restore independent split (Particle Sets Tool, Subset Particles by Statistic v5.0+); rerun from clean particles. |
| Global resolution looks good but cFSC / cFAR / tFAR shows strong anisotropy | Preferred orientation or directional alignment bias | Rebalance Orientations; add tilted data; consider sample-prep change. See `orientation_and_preferred_views.md`. |
| Local Resolution shows ROI much worse than surrounding density | Bulk-anchored alignment is not refining the ROI | Local refinement with a focus mask on the ROI. See `09_local_refinement.md`. |
| Local Resolution shows a "rim of perfect resolution" hugging the mask edge | Mask is too tight or hard-edged | Rebuild mask with proper soft edge. See `20_masks.md`. |
| Map looks pretty after strong sharpening but features disappear at modest B-factors | Possible over-sharpening / noise enhancement | Drop |B|; compare unsharpened; re-check upstream cleanup. |
| Residual blurred ligand / mixed density that no amount of postprocessing clarifies | Mixed states, not a sharpening problem | 3D Classification or Heterogeneous Refinement before re-refining and re-postprocessing. See `08_classification_3d.md` and `07_refinement.md`. |
| A region looks fine in the consensus but breaks under sharpening | Continuous motion under the consensus alignment | 3DVA / 3DFlex on the region. See `26_continuous_heterogeneity.md`. |
| Refinement quotes good resolution but the unsharpened map is essentially featureless | Alignment failure / model bias / wrong handedness | Recheck consensus / handedness; do not postprocess further. See `07_refinement.md` and `19_symmetry.md`. |
| Nontrivial Rejected Particles output (zero/negative scale) | Upstream issue: contrast inversion, blanks, bad import | Inspect rejected micrographs; revisit import / preprocessing. See `02_import.md` and `03_preprocessing.md`. |
| ResLog curve plateaus well before classical heuristics | Stack is information-limited, not count-limited | Look upstream: orientation balance, classification, sample prep — not "collect more of the same". |

When in doubt, **inspect three things together before changing parameters**: the corrected FSC plot, the unsharpened map at a matched threshold, and the local-resolution color view. They almost always agree on whether the problem is mask, sample, or alignment.

## Version-aware notes
Short on purpose — only items that change how to *interpret* postprocessing.

- **v4.4** — Orientation Diagnostics introduced (cFAR / SCF\*; subsumes the legacy 3DFSC wrapper). Sharpening Tools gains Guinier-B estimation with optional mask and FSC weights. Validation (FSC) plots add per-shell square markers for clearer reading. 3D Classification now FSC-filters its consensus volume for downstream use.
- **v4.5** — Orientation Diagnostics adds **Relative Signal**. Refinements emit a cFSC summary plot at every iteration (homo, NU, helical, local), enabling anisotropy tracking during optimization. v4.5.3 defaults refinement jobs to using the input particles' half-set split, materially fixing half-set mixing on RBMC → refinement loops; Particle Sets Tool can balance unequal half-set splits.
- **v4.6** — Local-resolution colormap Z-flip in the volume viewer fixed in v4.6.2; if a pre-v4.6.2 plot looks flipped, update before deeper interpretation.
- **v5.0** — FSC plots standardized across cryoSPARC with a consistent color scheme that indicates the mask and whether phase randomization was applied; FSC `.txt` output format expanded. Refinement jobs **warn at Nyquist** and recommend re-extracting at a smaller pixel size. Refinements output the refinement, FSC, and auto-tightened FSC masks as separate draggable outputs; dynamic masking redesign produces softer masks at lower-resolution structures and a more conservative auto-tightening default. Per-particle scale optimization is on by default in Homogeneous / NU / Helical, with a Rejected Particles output for zero/negative scales. Sharpening Tools can sharpen without an FSC filter using a Butterworth lowpass and can also run without a mask. Orientation Diagnostics adds **tFAR** and exports raw cFSC to `.csv`. Validation (FSC) no longer fails on CPU-only compute facility.

Forum-era recommendations from before these changes (especially around mask thresholds, manual auto-tightening, and 3DFSC) are still conceptually right but may reference older job names and plot layouts.

## Advisor defaults
If a user asks "the refinement finished — what now?":

1. Read **corrected FSC** first; ignore tight-mask numbers if they are materially higher than corrected.
2. Inspect the FSC mask (`mask_fsc` / auto-tightened) if the corrected curve has a sharp dip or big spherical-vs-tight gap; suspect the mask before suspecting the sample.
3. Check whether the resolution is hitting **Nyquist**; if so, re-extract at a smaller pixel size before any other action.
4. Confirm the half-set split is **preserved end-to-end**, particularly if particles passed through RBMC, re-extraction, or external tools.
5. Look at the **unsharpened** map at a matched threshold; only then apply sharpening, starting from Guinier-B auto.
6. Use **Local Resolution Estimation** as a sanity check for uneven quality, not as a per-particle score or a biological-confidence map. Pair with **Local Filtering** for figures, never for quoted resolution.
7. If the global FSC looks good but the map does not, run **Orientation Diagnostics** and read cFAR / tFAR / Relative Signal before tuning sharpening.
8. Treat **DeepEMhancer** output as a visualization aid; quote the corrected FSC of the underlying map.
9. When postprocessing keeps disagreeing with the appearance of the map, the answer is almost always **upstream**: cleanup, classification, local refinement, or sample/data — not a different sharpening B.

## Cross-links
- `07_refinement.md` — homogeneous / NU / heterogeneous refinement branches; where the half-maps, masks, and per-particle scales come from.
- `08_classification_3d.md` — discrete heterogeneity branch when postprocessing is showing mixed states.
- `09_local_refinement.md` — local refinement branch when local resolution highlights an under-resolved ROI.
- `19_symmetry.md` — symmetry imposition, expansion, and handedness, all of which interact with FSC interpretation.
- `20_masks.md` — mask construction details (threshold, dilation, soft edge, dynamic vs static).
- `05_extraction_2d.md` — box size, Fourier crop, and the Nyquist re-extraction branch.
- `23_external_jobs.md` — DeepEMhancer and other external post-processing integrations.
- `26_continuous_heterogeneity.md` — when sharpening / local refinement is fighting continuous motion.
- `15_troubleshooting.md` — debugging mental model for job-level failures.
- `orientation_and_preferred_views.md` — diagnosing preferred orientation and angular coverage.
- `version_caveats.md` — version-specific behavior changes that matter for postprocessing.

## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

- `docs/per_page/processing-data__all-job-types-in-cryosparc__post-processing.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__post-processing__job-sharpening-tools.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__post-processing__job-validation-fsc.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__post-processing__job-local-resolution-estimation.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__post-processing__job-local-filtering.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__post-processing__job-reslog-analysis.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__post-processing__job-deepemhancer-wrapper.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__post-processing__job-threedfsc-wrapper-legacy.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__utilities__job-orientation-diagnostics.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-refinement__job-homogeneous-refinement.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-refinement__job-non-uniform-refinement-new.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-dynamic-masking-in-refinements-v5.0.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-orientation-diagnostics.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-common-cryosparc-plots.md`
- `docs/forum_threads/digests/forum_features-and-functionality.md`
- `docs/forum_threads/digests/forum_3d-reconstruction.md`
- `docs/forum_threads/digests/forum_3d-classification.md`
- `docs/forum_threads/digests/forum_particle-curation.md`
- `docs/forum_threads/digests/forum_cryo-em-data-processing.md`
- `reference/release_notes/markdown/v4.4.md`
- `reference/release_notes/markdown/v4.5.md`
- `reference/release_notes/markdown/v4.6.md`
- `reference/release_notes/markdown/v5.0.md`