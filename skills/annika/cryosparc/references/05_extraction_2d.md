# Topic 05 — Extraction and First 2D Classification

## Scope
Once particle picks pass Inspect Picks, the next two jobs decide what every downstream 3D job sees: Extract from Micrographs (which sets pixel size, box size, and per-particle CTF) and 2D Classification (which decides which particles survive the first cleanup). This topic covers the practical knobs of both, plus the cleanup loop they enable. Picking strategy lives in `04_picking.md`; downstream 3D/heterogeneity branches live in `06_abinitio.md`, `07_refinement.md`, and `08_classification_3d.md`. Mask-related guidance for later refinement is in `20_masks.md`.

## Decision surface — default extract → 2D loop
Default SPA flow after picking:

1. Extract from Micrographs at a working box size with a sensible Fourier crop for early speed.
2. First 2D Classification with enough classes to expose junk classes alongside real ones.
3. Select 2D Classes (or Reference Based Auto Select 2D in workflows) to keep coherent classes.
4. If selection still mixes signal and junk, run another 2D pass on the kept particles.
5. Optionally regenerate templates from the kept classes and re-pick + re-extract the full dataset.
6. Hand off to ab initio / heterogeneous refinement once the kept stack looks coherent.

Prefer a different path when:
- **Picks come from Topaz, RELION, or another external source:** an Extract from Micrographs job is required before any 2D/3D job; external picks usually lack per-particle CTF and metadata cryoSPARC expects.
- **Pilot or screening:** crop more aggressively for an early readout, then re-extract full-size once orientations and class identity stabilize.
- **Very small or low-contrast particle:** keep more box around the particle and crop less aggressively; junk discrimination at small particle scale needs more pixels and cleaner noise.
- **Live screening already ran 2D:** still re-extract in the main project so per-particle CTF, exposure grouping, and box size stay consistent for the production branch.

## Extract from Micrographs — when and why
Extraction takes pick locations on aligned/CTF-estimated micrographs and writes actual particle stacks plus metadata used by every downstream job.

Mandatory when:
- Picks come from any non-cryoSPARC source (Topaz Extract output, imported particles, etc.).
- Picks were repositioned (e.g., re-pick with new templates, recentering after a refinement) and a fresh stack is needed.
- Local Motion Correction is not being used; Local Motion Correction does its own extraction, so do not double-extract.

The job is I/O-bound far more than GPU-bound. The CPU and GPU variants run at similar wall-clock speed on typical hardware. Choose based on what is idle, not on a belief that GPU extraction is faster.

### What extraction refreshes
- Per-particle CTF assignment from the patch CTF model.
- Particle blob (the actual image data) at the chosen box and pixel size.
- Exposure group and micrograph linkage that downstream jobs rely on.
- 16-bit float output is supported from v4.4+ and is usually safe; it materially reduces disk usage on large stacks.

### SSD cache, throughput, and storage
- Extraction reads micrographs and writes new particle stacks. On NFS/Lustre, throughput is often the bottleneck — multi-CPU on the CPU job or multi-GPU on the GPU job mostly helps when the filesystem can keep up.
- For the very first pass, work on raw micrographs without SSD caching; caching helps most for jobs that re-read particles many times (2D, ab initio, refinement).
- Particles too close to a micrograph edge are silently dropped during extraction. The job log reports the count; large drops mean the picker put too many particles near the border or the box is too large for the field of view.
- After heavy curation (2D selection, 3D class cleanup), use Restack Particles to consolidate the surviving particles into fewer larger files. This reclaims disk space, speeds up caching, and does not change downstream results.

## Box size — real-space considerations
Box size is the count of pixels per side at extraction. Two rules matter most.

**Pad the box well past the particle diameter.** The particle should fit comfortably inside the box with delocalized CTF signal still captured at the edges. A common starting point is roughly 1.5–2× the particle's longest dimension; tighter boxes save memory and runtime but risk clipping CTF rings or rotational coverage during 2D classification.

**Pick an FFT-friendly size.** The Extract job lists efficient box sizes (32, 36, 40, 42, 48, 56, …, 384, 400, …). These factor into small primes (2, 3, 5, 7), so FFTs run much faster than at arbitrary even sizes. Choose a value at or above your padding requirement, not below it.

Other practical considerations:
- Edge clipping: small particles in a large box waste compute; very large particles in a small box clip CTF signal and bias 2D/3D alignment.
- For elongated particles (rods, filaments, oligomeric assemblies), pad the long axis; if the longest dimension nearly equals the chosen box, rotational coverage in 2D is incomplete.
- For very small particles (sub-100 kDa), bigger boxes help by collecting more CTF-delocalized signal even though the visual particle is tiny; do not crop the box just because the protein is small.
- Box size and Fourier-crop box must both be even numbers, ideally from the efficient list.

## Fourier crop, downsampling, Nyquist
Fourier-cropping during extraction downsamples particles by truncating high-frequency Fourier components. The output box is smaller (fewer pixels per side), the effective pixel size grows (more Å per pixel), and the maximum recoverable resolution — Nyquist — gets coarser (numerically larger, in Å). Real-space cropping/padding (as in Downsample Particles) changes the field of view, not the pixel size.

Advisor guidance:
- **Early-stage coarse crop is fine** when you only need 2D classification and ab initio cleanup. Pixel sizes around 2–3 Å/pixel after crop leave comfortable headroom for typical class resolutions; prefer 1.5–2 Å/pixel for small or low-contrast particles to keep junk vs. signal discriminable.
- **Plan to re-extract full-size** before final refinement or whenever the FSC approaches the Nyquist of the cropped stack. If a refinement reports resolution at or near Nyquist, the box was too small — re-extract larger.
- **Two-output extraction** (CPU job, v4.0+) emits a coarse-binned "Particles small" stack alongside the full-size stack. Use the small set for fast 2D/ab initio; swap the blob slot to the full-size set for refinement, keeping all other metadata.
- **Avoid extreme crop on small particles.** If the protein is small and the crop is aggressive, junk vs. signal becomes nearly indistinguishable in 2D, and good particles end up in junk classes.
- **Downsample Particles** is the right tool to change box size *after* extraction, including padding back up to a larger real-space box when needed for refinement-time framing.

## 2D classification — setup
2D Classification groups particles by in-plane rotation and translation, then averages within each class. The class average has far higher SNR than any single image and is the main early-stage diagnostic of picking quality.

### Number of classes
- For a typical dataset with hundreds of thousands of particles, 50–200 classes is a strong default.
- Sparse particle counts → fewer classes; rich datasets with many views or heterogeneity → more classes.
- Too few classes squeezes junk into "good" classes; too many makes per-class signal too thin to converge and slows the job.
- Increasing class count beyond what the data supports does not magically separate states; ESS and class-empty diagnostics will flag it.

### Resolution knobs
- **Maximum resolution** and **Maximum alignment res** are the main resolution knobs. The default usually does not need adjustment. Lowering maximum resolution reduces high-frequency overfitting and spiky artifacts.
- **Minimum alignment res** is a high-pass during alignment. It helps when large low-frequency background (micelles, ice halos, neighboring particles) dominates alignment; 40–60 Å is a typical range in those cases.

### Uncertainty, batch, and convergence
- **Initial classification uncertainty factor** controls how long the job stays uncertain about class assignments. Raising it gives more iterations before classes lock in; useful when good and bad particles look similar and the classifier collapses too early.
- **Batch size per class** and total iterations interact: bigger batch and more iterations give smoother classification at higher GPU memory and runtime cost. Defaults are good first.
- **Online-EM behavior**: 2D Classification is an EM-style iterative job. Watch class evolution across iterations; if good-looking high-resolution classes appear mid-run and then smear out by the end, sigma annealing is collapsing them — consider raising the uncertainty factor or temporarily switching annealing off for one diagnostic run.
- **Force max over poses/shifts** can sharpen class assignments when overlapping classes refuse to separate; safe to test at default class counts.

### Centering and duplicates
- **Recentering** during extraction is on by default and uses any available 2D or 3D shifts. It usually behaves well but can be derailed when a strong off-target feature (micelle, vesicle, neighbor blob) dominates the shift. If recentering keeps walking off the particle, turn it off and rely on box padding plus a later re-extract.
- The new 2D Classification implementation (v4.4+) removes duplicates after classification using a minimum separation distance. Disable this in-job step and use a standalone Remove Duplicate Particles job when you need explicit control over the "which copy to keep" metric.
- For older particle stacks, the v4.5 fix to 2D pixel-size handling avoids silent miscounts of duplicates; if duplicate counts look implausible, set the micrograph pixel size override and rerun.

### Plotting and ESS diagnostics
- v5.0 changed default plotting from size-sorted to similarity-sorted. Adjacent classes now look alike, which is better for spotting state differences and worse for at-a-glance "how clean is this" reads. Switch back to size-sorted via the plotting sort method if you prefer the old behavior.
- The class average tile shows particle count, FRC resolution per class, and median class ESS.
- High median ESS = classification stayed uncertain → too many overlapping classes or weak signal. Low ESS = particles confidently assigned.

## Class selection
Three jobs cover the curation surface, plus subset-by-statistic tooling.

**Select 2D Classes (interactive)** is the everyday tool. Inspect class images, sort by particle count / resolution / ESS, right-click to multi-select by threshold, and finalize. Outputs selected particles, excluded particles, and the matching template subsets. Resolution and particle-count thresholds enable automated selection inside Workflows but skip the interactive panel entirely — use only when the target dataset is already well characterized.

**Reference Based Auto Select 2D (BETA)** is for repeated workflows on the same or similar target. Provide a 3D reference; the job compares class averages to reference projections and selects automatically. The Sobel-score mode (v4.7+) is the default and most robust; cluster, threshold-only, top-N, and top-K modes remain available. Calibrate selection mode and thresholds on one well-curated dataset, then reuse the workflow on later collections.

**Class Probability Filter** is now a legacy job. Its functionality moved to **Subset Particles by Statistic** in v4.7+ under the `Class probability - 2D` or `Class probability - 3D` modes. Use Subset Particles by Statistic for any new class-probability, per-particle-scale, alignment-error, or defocus-based filtering.

**Reconstruct 2D Classes** is a useful sidecar after Select 2D: it regenerates class averages at a larger box size using existing alignments, without re-running classification. Useful for publication-quality images and for visualizing how curated classes evolve after upstream changes.

## Cleanup loops
A single 2D pass rarely catches everything. The standard cleanup loop:

1. Select coherent 2D classes; reject junk and ambiguous classes.
2. Generate templates from the kept classes (Create Templates) if you intend to re-pick.
3. Run Template Picker on the full micrograph set, then Inspect Picks, then Extract.
4. Run 2D again on the new picks; expect a cleaner separation of junk from signal.
5. Remove duplicates explicitly with Remove Duplicate Particles when combining picks from multiple pickers or after re-picking with overlapping coordinates. Use NCC, 2D alignment error, or 3D alignment error as the keep metric; random keep is also an option.
6. Optionally rebalance: **Rebalance 2D Classes** groups class averages into superclusters and can drop particles from over-represented views; **Rebalance Orientations** (after a first 3D refinement) directly rebalances on viewing-direction bins.

Two cautions on rebalancing:
- Rebalancing throws away particles. Use it when orientation bias is real and harmful (anisotropic map, severely uneven viewing-direction histogram), not as a default cleanup step.
- Rebalance Orientations needs 3D poses, so it lives after a first refinement, not in the 2D loop proper.

## Common failure patterns
- **All classes look like junk.** Almost always upstream: wrong particle diameter, biased templates, threshold too loose, or wrong pixel size at import. Recheck picking and metadata before tuning 2D parameters.
- **Blurry / streaky classes.** Lower the maximum resolution cap (e.g., 8 Å → 12 Å), increase class count modestly, and inspect for residual junk in the largest classes. Also check gain/motion correction.
- **One view dominates the class plot.** Expected for genuinely preferred-orientation samples. Confirm with Orientation Diagnostics later; do not try to fix it with 2D rebalancing alone.
- **Centering walks off.** Recentering is following a strong off-target feature. Turn off recentering during extraction, or refine the box and re-extract; in 2D, set a minimum alignment resolution to suppress low-frequency background.
- **Duplicate particles inflate "good" class counts.** Usually from multiple pickers feeding the same downstream job (auto-merge by UID does not deduplicate near-coincident picks). Run Remove Duplicate Particles with a sensible minimum separation distance before serious 2D/3D.
- **CUDA out of memory / cuFFT errors during extraction or 2D.** Box × batch × #GPUs exceeds VRAM. Drop GPUs first, then batch size, then crop. v4.1 reduced extraction GPU memory and v4.2 fixed some multi-GPU 2D blank-class issues; older instances should update before chasing parameter changes.
- **SSD cache hangs or "cache waiting for requested files to become unlocked".** Another job holds the lock. Let it finish; do not kill it. If clearly stale, delete the lock and re-queue. The v4.4+/v4.5+ cache rewrite handles this much better than older versions.
- **`AssertionError: particles.blob ... not connected` when launching 2D.** Picks were connected but particles were never extracted. Run Extract from Micrographs first.

## Version-aware highlights
- **v4.0** added the CPU Extract second-output ("Particles small") at a smaller Fourier-crop box for fast early classification while preserving the full-size stack.
- **v4.1** reduced GPU memory pressure in Extract from Micrographs (GPU).
- **v4.2** fixed blank/faint 2D classes when using multiple GPUs and fixed several 3D Classification I/O edge cases that feed back into 2D-curated stacks.
- **v4.4** introduced a new 2D Classification implementation with reduced memory use, added 16-bit float output for particles/micrographs, and added Rebalance Orientations and Reconstruct 2D Classes.
- **v4.5** added Reference Based Auto Select 2D (BETA) and fixed a 2D pixel-size handling bug that affected duplicate removal on older stacks.
- **v4.6** improved CPU requests for multi-GPU 2D classification and added auto-clustering in Inspect Particle Picks (designed for denoised micrographs).
- **v4.7** moved Class Probability Filter functionality into Subset Particles by Statistic and added the Sobel-score selection mode for Reference Based Auto Select 2D.
- **v5.0** changed default 2D plot sorting to similarity, added a Do orientation alignment toggle for 2D-without-alignment cases, and added per-particle scale optimization by default in refinements (relevant when feeding 2D outputs into refinement). Blob Picker also gained stretch/squeeze elliptical modes; relevant when feeding 2D from a new picking pass.

## Advisor defaults
- First extract: pad box ~1.5–2× particle diameter, choose an FFT-friendly size, Fourier-crop to a working pixel size around 2–3 Å/pixel (1.5–2 Å/pixel for small particles). Enable 16-bit float output. Recentering on.
- First 2D: 100–200 classes, default uncertainty, default resolution caps, default batch size. Watch ESS and per-class resolution before changing anything.
- Selection: interactive Select 2D for the first dataset on a new target; Reference Based Auto Select 2D once a trustworthy 3D reference exists for reuse across datasets.
- Iterate twice (2D → Select → 2D → Select) before assuming the picker or templates need rebuilding.
- Re-extract full-size only when refinement is close to the Nyquist limit of the cropped stack, or when polishing/RBMC needs the highest-quality particles.
- Use Restack Particles after heavy curation, never before; it consolidates files and helps cache performance.

## Cross-links
- `03_preprocessing.md` — patch CTF feeds per-particle CTF at extraction; gain/exposure curation upstream determines extraction success.
- `04_picking.md` — picker choice, template generation, Inspect Picks, and re-pick loops.
- `06_abinitio.md` — what to do once a clean 2D-curated particle set exists.
- `07_refinement.md` — when to re-extract full-size before refinement; per-particle scale handling.
- `08_classification_3d.md` — when discrete 3D classification replaces further 2D loops.
- `20_masks.md` — mask discipline for downstream focused 2D/3D heterogeneity work.
- `17_error_lookup.md` — exact strings for extraction/2D/cache failures.
- `particle_set_operations.md` — intersect/union/dedup patterns for combining particle sets across pickers or branches.

## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

- `docs/per_page/processing-data__all-job-types-in-cryosparc__extraction.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__extraction__job-extract-from-micrographs.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__extraction__job-downsample-particles.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__extraction__job-restack-particles.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__particle-curation.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__particle-curation__job-2d-classification.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__particle-curation__interactive-job-select-2d-classes.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__particle-curation__job-reference-based-auto-select-2d-beta.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__particle-curation__job-class-probability-filter.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__particle-curation__job-rebalance-2d-classes-beta.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__particle-curation__job-rebalance-orientations.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__particle-curation__job-reconstruct-2d-classes.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__particle-curation__job-subset-particles-by-statistic.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__utilities__job-remove-duplicate-particles.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__utilities__job-particle-sets-tool.md`
- `docs/per_page/processing-data__get-started-with-cryosparc-introductory-tutorial.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__case-study-dktx-bound-trpv1-empiar-10059.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-common-cryosparc-plots.md`
- `docs/forum_threads/digests/forum_2d-classification.md`
- `docs/forum_threads/digests/forum_particle-curation.md`
- `docs/forum_threads/digests/forum_particle-picking.md`
- `videos/notes/02_trpv1_and_a_standard_workflow.notes.md`
- `reference/release_notes/markdown/v4.0.md`
- `reference/release_notes/markdown/v4.1.md`
- `reference/release_notes/markdown/v4.2.md`
- `reference/release_notes/markdown/v4.4.md`
- `reference/release_notes/markdown/v4.5.md`
- `reference/release_notes/markdown/v4.6.md`
- `reference/release_notes/markdown/v5.0.md`
- `17_error_lookup.md`