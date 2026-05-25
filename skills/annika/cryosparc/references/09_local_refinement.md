# Topic 09 — Local Refinement

## Scope
Practical use of Local Refinement (and the paired particle-subtraction workflow) in cryoSPARC: when it is the right move versus other refinement branches, what it needs from upstream, how masks and subtraction interact, what search/prior settings actually matter, and how to read the result without overclaiming sharpness. Deeper mask construction belongs in `20_masks.md`; FSC/sharpening details belong in `10_postprocessing.md`; discrete heterogeneity belongs in `08_classification_3d.md`; continuous motion belongs in `26_continuous_heterogeneity.md`.

## Decision surface — when local refinement is the right move
Local refinement updates poses against a chosen region of the particle instead of the whole density. Reach for it when:
- a consensus refinement is already solid for the bulk of the particle, **and**
- one region is blurred relative to the rest because it moves rigidly with respect to the consensus alignment frame, **and**
- the question is "can I get a cleaner local map of that region?" — not "is this region present?" and not "is this region moving?"

Prefer a different branch when:
- the bulk consensus is still poor → fix the global refinement first (Homogeneous/NU). Local refinement amplifies upstream alignment errors rather than rescuing them.
- the region is *compositionally* heterogeneous (present vs absent, ligand-bound vs apo) → start with **3D Classification** (`08_classification_3d.md`), possibly with a focus mask, before chasing local poses.
- one state seems blurred or biased even after good consensus → try **Heterogeneous Refinement** with two identical starting volumes first; small pose updates per class often beat fixed-pose classification and beat local refinement on a contaminated stack.
- the motion is continuous along an axis (hinge, breathing, rocker) → use **3DVA** for interpretable motion axes or **3DFlex** for a nonlinear motion model (`26_continuous_heterogeneity.md`). Iterating local refinement on continuous motion produces sharper-looking but biologically misleading maps.
- the ROI is too small to align on its own → consider whether symmetry expansion + masked classification, or 3DVA cluster mode, gets you further before forcing local refinement.

A common right ordering: ab initio / NU consensus → 3D classification or heterogeneous refinement to settle identity → local refinement on the cleanest class for the region of interest. Local refinement is rarely a fix for cleanup problems.

## What local refinement needs to succeed
Local refinement is sensitive to its starting conditions. Check these before queueing the job:

- **Starting poses.** Use poses from a refinement that converged cleanly on the same particles — typically Homogeneous, NU, or a prior local refinement. Do not feed in raw ab-initio poses for a final local refinement; ab initio does not obey gold-standard half-sets and the poses are not stable enough to anchor a local search.
- **Starting volume.** Use the volume the poses were aligned to. The cleanest case is the consensus map (or a class-specific refined map) at the same box and pixel size as the particles. A class-specific volume from a heterogeneous refinement is preferred over a consensus volume when the local question is itself class-specific.
- **Class-specific vs consensus volumes.** If you have already separated states (e.g. apo vs liganded), local-refine each class against *its own* reconstructed volume, not the mixed consensus. Re-aligning a per-class subset to a consensus map can drag minority-state poses toward the wrong reference.
- **Low-pass / initial alignment resolution.** Set the initial low-pass below the resolution of the region of interest, not at the consensus global resolution. If the consensus has good 8 Å features in the ROI, an 8 Å initial low-pass is a reasonable starting point; setting it too high risks letting the search escape the correct basin.
- **Inherited per-particle metadata.** Local refinement inherits per-particle CTF, defocus, exposure-group and (if present) per-particle scale from upstream. If you intend to use Local/Global CTF refinement or RBMC outputs, do them upstream of local refinement, not after, so the local job sees the corrected metadata.
- **Particle cleanliness.** A local refinement run on a stack that still contains junk or wrong states will dedicate alignment power to the wrong density. Clean first.

## Fast preflight before queueing
This is the short checklist that catches most wasted local-refinement/subtraction runs:

1. Consensus or class-specific refinement is already good enough to define the ROI.
2. The branch question is pose/local sharpness, not class identity or continuous motion.
3. Particles, starting volume, half maps, focus mask, and subtraction mask are on the same box, pixel size, and origin.
4. The focus mask is soft-edged, generous enough, and free of detached islands.
5. Search range is deliberately small, with Gaussian priors enabled for small ROIs.
6. If particle subtraction is used, the subtraction volume/mask was built from the same consensus or class-specific reference used to define the local question.

## Re-center, re-extract, and keep the grid honest
This is the part most easily skipped and most easily punishes you later.

- **Re-centering.** If the ROI sits well off the box center, the search range and box-edge effects work against you. Re-center on the ROI (typically by recomputing particle origins so the ROI is in the middle of the new box) before extracting at the local-refinement box.
- **Re-extract at a sensible box.** For a small ROI, a smaller, ROI-centered box reduces memory, lets you use a tighter search, and reduces the risk that off-mask density dominates alignment. For a large ROI inside a larger complex, you usually want to keep the full box so the surrounding density can still help anchor poses through subtraction.
- **Match pixel size and box across inputs.** Particles, starting volume, and any mask you supply must agree on pixel size and box size. A mismatched mask is the single most common silent failure — cryoSPARC will run, the result will look almost right, and the alignment will be subtly wrong.
- **Grid consistency for subtraction.** If you subtract density elsewhere in the box, the subtraction mask, the local-refinement mask, the starting volume, and the particles all need to live on the same grid. Masks generated in ChimeraX from a cropped selected region usually come out at the wrong box and must be **resampled onto the original grid** before they are usable (see `videos/notes/10_mask_creation_in_chimerax.notes.md`).
- **Do not re-bin partway through.** Changing pixel size mid-workflow between extraction, subtraction, and local refinement invalidates inherited shifts. If you must re-bin, redo the chain: re-extract, regenerate masks at the new grid, re-run subtraction, then local-refine.

## Masks and subtraction strategy
Masks are central to local refinement, but the choice is narrower and more pragmatic than the general masking topic.

### Three mask roles
Three masks tend to show up around a local-refinement workflow, and they answer different questions:

1. **Solvent / generous mask** — the global "what is signal at all" mask. Used by FSC and (indirectly) sharpening. For local refinement, the focus mask should sit comfortably inside any solvent mask in play.
2. **Focused ROI mask** (the local-refinement alignment mask) — defines what density the alignment is allowed to be scored against. It must:
   - cover the ROI plus a comfortable margin (often dilated by ~5–10 voxels and then soft-padded by ~20),
   - be **soft-edged**, not hard-edged, to avoid sharp Fourier artifacts in alignment,
   - sit on the correct grid and box,
   - contain no detached noise islands (see below).
3. **Complementary subtraction mask** — defines the density to remove from each particle image. Ideally this is the consensus density *minus* the ROI plus a transition zone. The local-refinement mask and the subtraction mask should partition the consensus density cleanly; gaps or overlaps both cause problems.

### Blur-first philosophy
Build mask bases from a Gaussian-blurred copy of the map (a `sdev 2` blur in ChimeraX is a reasonable starting point). Blurring before thresholding suppresses the high-frequency speckle that, once dilated and soft-padded, becomes a noise island that the alignment can latch onto. A pretty boundary on the raw map is not the goal; a *robust* boundary on the blurred map is.

### Noise-island hazards
Floating blobs inside a focus mask are one of the most common failure modes (see "Common failure patterns"). The rule of thumb: if you can drop the threshold and watch new islands of density appear inside the mask volume that are not part of your ROI, your local refinement will probably reconstruct those blobs as if they were real. Re-threshold or re-segment until the mask contains only the ROI.

### Generous vs tight ROI mask
- A **generous** ROI mask (ROI plus surrounding rigid context) usually aligns more stably and is the better default when the ROI is small or when the ROI's relative orientation is well constrained by adjacent rigid density.
- A **tight** ROI mask is occasionally helpful when adjacent density is *itself* moving differently, but it must come with a small search and a Gaussian prior, otherwise it has nothing to anchor against.

### When to pair with particle subtraction
Use Particle Subtraction together with local refinement when:
- the rest of the complex dominates the signal and is genuinely well-resolved against the consensus alignment, so subtracting it leaves the ROI in cleaner per-particle background;
- the surrounding density is heterogeneous and is corrupting the local alignment (e.g. a flexible micelle around a membrane protein partner);
- you intend to follow with 3DVA / 3DFlex on the ROI alone.

Do **not** use particle subtraction when:
- the consensus map is itself low-quality — you will subtract noise and re-imprint it;
- the ROI is heavily coupled to surrounding density that is not yet aligned;
- you are still doing cleanup. Subtraction is a precision tool, not a cleanup tool.

When subtracting, generate the subtraction volume from the *consensus* (or class-specific) map masked to *everything except the ROI plus a transition zone*, on the same grid. Pair: subtraction → local refinement against ROI mask on subtracted particles.

### What belongs in the general masks topic, not here
General threshold/dilation/soft-edge defaults, static vs dynamic mask choice, mask-generation jobs, ChimeraX mask construction recipes, and FSC mask diagnostics belong in `20_masks.md`. This page treats masks as a workflow choice tied to local refinement; the deeper craft of masks is its own surface.

### Mask handoff checklist
Before attaching a mask to Local Refinement or Particle Subtraction:

- Import a mask base as a **map** if Volume Tools still needs to threshold/dilate/soft-pad it; import as a **mask** only if it is already the final soft mask.
- Treat binary-mask warnings as real failures of preparation, not cosmetic messages.
- If the mask was made by Segger, eraser, or `molmap`, confirm it was resampled/onGrid to the target map before Volume Tools.
- Inspect the final mask at the same threshold you will use for the job; a mask that only looks correct at one display threshold is not robust.
- For complementary subtraction/local-refinement masks, inspect them together and verify they partition the density without gaps, overlaps, or floating dust.

## Search / prior strategy
Local refinement search settings matter more here than in global refinement, because the ROI signal is smaller and the search is more easily distracted.

- **Start small, escalate only if needed.** For a small ROI, default to a small rotational and shift search (e.g. a few degrees and 1–3 Å) rather than the global refinement's defaults. Larger searches are not automatically better; they make it easier for the alignment to leave the correct basin.
- **Use Gaussian priors for small ROIs.** Enabling `Use Gaussian prior` with modest priors (e.g. 3°/1 Å) combined with a slightly larger search (e.g. 9°/3 Å) is a standard, well-supported recipe for small targets. The prior anchors poses around the consensus while still allowing useful updates.
- **Initial low-pass below the ROI features.** Set the initial alignment resolution at or just below the resolution at which the ROI shows real features in the consensus map. Too aggressive (too low a resolution) makes everything align to a blob; too sharp (too high a resolution) makes the search noise-driven.
- **Re-centering of rotations and shifts.** Re-centering at each iteration can help when poses are drifting consistently in one direction; leaving it off can help when the alignment is converging stably and you want to preserve consensus poses. Try with and without if results look unstable.
- **Do not chase resolution by widening the search.** A wider search rarely fixes a noisy local map; if the local map looks worse than the consensus inside the ROI, the issue is upstream (mask, particles, starting volume, or branch choice), not search range.

## Symmetry expansion and local questions
Symmetry expansion is a real but narrow tool inside local-refinement workflows.

Use symmetry expansion only when the **biological question is itself a symmetry-breaking local question** — for example, ligand occupancy or local conformation per subunit of a symmetric assembly, where each subunit is treated as an independent observation.

Important guardrails:
- **Do not run global refinement on symmetry-expanded particles.** A global refinement on expanded particles will fight itself, because each particle now exists as multiple copies related by the imposed symmetry. Local refinement against an asymmetric ROI mask is the appropriate downstream branch.
- **Pair expansion with a focused ROI mask covering one asymmetric unit.** Without the mask, the alignment cannot tell which copy of the particle should be moved.
- **Track duplicates carefully.** After expansion, each physical particle contributes multiple rows to the stack. Downstream particle counts, FSC denominators, and any selection job need to be interpreted with that in mind; treating expanded particles as if they were independent inflates apparent statistics and can mislead interpretation.
- **Be cautious before claiming an asymmetric result.** A "symmetry-broken" map from expanded local refinement is more convincing when the asymmetric occupancy or conformation is reproduced from independent subsets of particles, not just from the full expanded stack.

For broader symmetry-imposition decisions (when to impose C-something at all, handedness flips, validation risks), see `19_symmetry.md`.

## Reading the result: what improved vs what only looks sharper
Local refinement makes maps look sharper in the ROI almost by construction. That is not the same as the map being better. Before trusting the result:

- **Compare against the consensus inside the mask.** The honest comparison is consensus-map-restricted-to-ROI versus local-refined-map-restricted-to-ROI, viewed at matched thresholds. A real improvement shows more features and recognizable secondary structure, not just less noise.
- **Be aware that local FSC values can be optimistic.** Local refinement FSC is computed inside the focus mask. A tight mask reduces the effective signal-vs-noise budget the FSC sees and can produce optimistic numbers — the same "too-tight mask" pathology that appears for global FSC also appears here. If the FSC has an unusual shape, suspect the mask before celebrating the resolution. Detailed FSC diagnostics belong in `10_postprocessing.md`.
- **Check the rest of the particle.** If the global core has gotten visibly worse in the local-refined map relative to the consensus, the local search has rotated the particle in a way that improves the masked region at the expense of the rest. That is a sign that the mask or search settings let the alignment "cheat" — usually too much rotational freedom on a small mask, or a noise island inside the mask.
- **Confirm half-map independence is preserved.** Local refinement obeys gold-standard half-sets; this is one of the practical reasons to prefer it over ab-initio-style reconstructions for the final step.
- **A pre/post sharpened comparison is not optional.** A pretty post-sharpening view of a local-refined map is the easiest way to over-claim resolution. Look at the unsharpened map too.

## Common failure patterns

### 1. Floating blobs inside the mask
Symptom: small, often peripheral pieces of density reconstruct as if they were real features, sometimes at higher contrast than expected.
Cause: noise islands inside the focus mask, or a mask built from an unblurred map.
Fix: rebuild the mask from a Gaussian-blurred copy of the map; threshold higher; visually confirm the mask volume contains only the ROI before queueing.

### 2. The class got diluted after re-refinement
Symptom: a clean class from 3D classification or heterogeneous refinement looks less distinct after a local (or global) refinement against the consensus map.
Cause: the per-class subset was re-aligned to a consensus reference that averages over states; minority-state poses get dragged toward the wrong basin.
Fix: local-refine each class against its own per-class volume, not the consensus. If the class survives that, the class is real; if it does not, the discrete-class assumption may be wrong (consider 3DVA / 3DFlex).

### 3. Local refinement worsens the global core
Symptom: the ROI looks better but the rest of the complex looks blurred, doubled, or rotated relative to the consensus.
Cause: too-permissive search on a small mask let the alignment trade off the rest of the particle to satisfy the ROI. Sometimes the focus mask also sits poorly relative to the broader solvent mask, making the apparent gain look better than it is.
Fix: shrink the search, enable Gaussian priors, generously include rigid context in the mask, and confirm the focus mask sits inside the solvent mask.

### 4. ROI too small to align
Symptom: the local refinement either converges to noise, refuses to improve over the consensus, or produces a map that visibly wobbles between iterations.
Cause: the ROI does not carry enough signal on its own to drive an alignment.
Fix: include more rigid context in the mask; use a Gaussian prior to anchor poses; consider whether the right answer is symmetry expansion + local refinement, or 3DVA cluster mode, or no local refinement at all. Resist widening the search — that makes the problem worse.

### 5. Fixed-pose 3D classification might have been the better branch
Symptom: chasing local refinement is producing maps that look subtly mixed (e.g. residual ligand density in an apo-leaning class).
Cause: the problem is class identity, not pose. Local refinement re-aligns; it does not separate states.
Fix: go back to 3D classification (with a focus mask if the difference is local) or heterogeneous refinement with identical starting volumes. Re-run local refinement only after the class identity is settled. See `08_classification_3d.md`.

### 6. The motion is actually continuous
Symptom: repeated local refinements on similar masks produce maps that each look plausible but disagree about the ROI's position; or local refinement on the ROI keeps producing a smeared map.
Cause: the ROI is moving along a continuous axis, not occupying a few discrete states.
Fix: stop forcing it. Run 3DVA against the ROI (with subtraction if helpful) to characterize the motion; consider 3DFlex if the motion is nonlinear. See `26_continuous_heterogeneity.md`.

### 7. Particle subtraction left ghosts or worsened the local map
Symptom: subtracted particles still show the supposedly-subtracted density, or local refinement on subtracted particles is worse than on un-subtracted particles.
Cause: subtraction mask did not cleanly partition the consensus density, consensus map was too low-quality to subtract from, particles or volume were on a different grid, or the subtraction mask had a hard edge.
Fix: rebuild the subtraction mask on the same grid with a soft edge; confirm subtraction → ROI mask partition the consensus density without overlap or gaps; if the consensus map is low-quality, fix the consensus first rather than subtracting against it.

## Troubleshooting and version-aware notes
Keep this short — for error strings see `17_error_lookup.md`, and for the broader debugging mental model see `15_troubleshooting.md`.

- Local Refinement plotting failures in some cases were fixed in **v5.0**; if a recent local-refinement traceback is plot-related, update before deep debugging.
- Since **v4.0**, Local Refinement and Particle Subtraction warn if binary masks are used. Treat that warning seriously: hard-edged masks are often the real problem.
- **v4.5** added better support for re-centering around a mask-defined region through Volume Alignment Tools, which is directly relevant when preparing local-refinement inputs.
- Behavioral wrongness (mask containing noise islands, wrong grid, wrong starting volume, wrong branch choice) is not version-shaped; do not expect an update to help.
- If a local refinement just fails to launch or fails immediately, treat it as a launch/env problem first (see `15_troubleshooting.md`), not as an algorithmic problem.

## Advisor defaults
If a user asks "should I do local refinement here?":
1. Confirm the consensus refinement is genuinely good, and that any cleanup / class separation has already happened.
2. Confirm the question is "sharper local map," not "is this region present" (→ 3D classification) and not "is this region moving" (→ 3DVA/3DFlex).
3. Re-center and re-extract at a sensible box; confirm particles, starting volume, and any mask agree on grid and pixel size.
4. Build the focus mask from a blurred copy of the volume; inspect for noise islands; soft-edge it; confirm it sits inside any solvent mask.
5. Start with a small search and Gaussian priors; widen only if there is direct evidence the prior is too tight.
6. If subtraction is needed, build subtraction and ROI masks together so they partition the density cleanly, on the same grid.
7. For symmetry-breaking local questions, expand symmetry, use a one-asymmetric-unit focus mask, do not global-refine on expanded particles, and interpret duplicates honestly.
8. Compare local map vs consensus inside the mask, look at the unsharpened map, and check the rest of the particle did not get worse.

## Cross-links
- `07_refinement.md` — homogeneous/NU consensus refinement; the upstream that local refinement depends on.
- `08_classification_3d.md` — discrete heterogeneity; what to do if class identity, not pose, is the problem.
- `26_continuous_heterogeneity.md` — 3DVA / 3DFlex; what to do if the motion is continuous.
- `19_symmetry.md` — when to impose symmetry, symmetry expansion validity, handedness.
- `20_masks.md` — mask construction, threshold/dilation/soft-edge defaults, static vs dynamic masks.
- `10_postprocessing.md` — FSC, local resolution, sharpening, and interpretation cautions.
- `15_troubleshooting.md` — debugging mental model.
- `17_error_lookup.md` — error-string lookup.

## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

- `videos/notes/05_fanac1_and_discrete_heterogeneity.notes.md`
- `videos/notes/10_mask_creation_in_chimerax.notes.md`
- `docs/forum_threads/digests/forum_3d-reconstruction.md`
- `docs/forum_threads/digests/forum_3d-classification.md`
- `docs/forum_threads/digests/forum_troubleshooting.md`
- `reference/release_notes/markdown/v4.0.md`
- `reference/release_notes/markdown/v4.5.md`
- `reference/release_notes/markdown/v5.0.md`
