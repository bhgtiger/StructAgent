# Topic 04 — Particle Picking

## Scope
Strategies and job-level guidance for particle picking in cryoSPARC: choosing among blob picker, template picker, manual picker, Topaz, Deep Picker (legacy), and filament tracer, plus how to threshold and curate picks before extraction. Preprocessing context (motion/CTF/denoiser/junk detector) lives in `03_preprocessing.md`; extraction and 2D classification handoff lives in `05_extraction_2d.md`; Live-specific picking transitions are summarized here and detailed in `25_cryosparc_live.md`.

## Decision surface — picker choice
Pick the picker by what you already have, not by the picker's headline accuracy.

- **No reference, no templates, never seen the sample:** start with Blob Picker. Use it to get something into 2D classification; treat early picks as disposable.
- **Blob picking but defaults look wrong:** use Blob Picker Tuner with 15–40 manual picks on the best micrographs to grid-search size/shape/threshold.
- **Have a few good 2D classes or a known map:** move to Template Picker. Generate templates from a small Select-2D-then-Create-Templates loop, or from a projected reference volume.
- **Small / heterogeneous / low-contrast particle:** train Topaz on a clean subset (hundreds to low thousands of particles); often outperforms blob/template once a clean seed exists.
- **Filaments, amyloid, helical assemblies:** use Filament Tracer rather than vanilla template picking; switch to Topaz/Template Picker if filaments are not roughly cylindrical.
- **Manual curation only (calibration, ground-truth set, hard cases):** use Manual Picker on a small subset and feed it into 2D, Blob Picker Tuner, or Topaz Train.

In modern installs (v5.0+), Deep Picker Train and Deep Picker Inference are deprecated and removed; do not plan new workflows around them.

## Standard picking workflow
A robust default for typical SPA after motion/CTF and exposure curation:

1. Blob Picker on a representative subset, with deliberate diameter padding.
2. Extract with a small Fourier crop for speed; 2D classify; Select 2D for templates.
3. Create Templates from selected 2D classes (and/or from a low-res reference projection).
4. Template Picker on the full dataset using diverse views; turn on denoised input if a denoiser model exists.
5. Inspect Particle Picks: adjust NCC, power, low-pass filter, and edge thresholds; rely on defocus-calibrated scores.
6. Extract for production. Run 2D classification or heterogeneous refinement to clean.
7. Optional: train Topaz on the cleaned set to recover difficult or low-contrast particles, then re-extract.

This is the TRPV1-style default discussed in the official walkthrough; it generalizes well as long as the templates are not all the same view.

## Blob Picker and Blob Picker Tuner
Blob Picker compares micrographs against Gaussian-like circular, elliptical, or ring templates.

- Set a **minimum and maximum particle diameter** that brackets the real particle generously. In v5.0+, the number of blobs across that range is controlled by a new `Blob size spacing (A)` parameter; elliptical generation gained "stretch" (rod-like) and "squeeze" (disk-like) modes.
- Use a single blob shape per job (circular vs elliptical vs ring). Different modes are normalized differently; mixing them within one job confuses thresholding. Combine across jobs downstream instead.
- If a Micrograph Denoiser model exists, pick on denoised micrographs. Extraction still uses raw micrographs regardless of this setting.

**Blob Picker Tuner** turns the parameter sweep into a comparison against a small ground-truth set:

- Provide 15–40 manual picks on a handful of the cleanest micrographs, including neighbouring particles so the tuner can learn spacing.
- Set the agreement-distance parameter to roughly the protein size.
- The tuner does a grid search of size/shape/threshold and reports the best parameter set; connect outputs to Inspect Picks to verify.
- Limitation: the tuner cannot pick better than Blob Picker in principle, only with better-tuned parameters.

## Manual Picker and Inspect Particle Picks
Manual Picker is for small subsets, not full datasets. Typical uses:
- Seed picks for Blob Picker Tuner, Topaz Train, or template generation.
- Hand-pick a few hundred high-quality particles to generate first templates.
- Calibrate diameter and box size before committing to an auto-picker.
- Pick across several micrographs that span the defocus range so resulting templates are not biased to one focus regime.

Inspect Particle Picks is the interactive curation layer for any auto-picker:
- Sliders for NCC, power, low-pass filter, and edge distance.
- Pick-score calibration against defocus (v2.13+) is on by default; thresholds set on one defocus regime now generalize across the dataset. Look for tight clustering in the NCC × power plot after calibration.
- v4.6 added an auto-clustering option, designed for use with denoised micrographs; useful for non-interactive workflows or workflow templates.

## Create Templates + Template Picker
Templates are projections of an input volume on an SK97 angular grid.

- Number of templates: enough to cover the views you actually see in 2D (typically ~20+ for asymmetric particles).
- The volume need not be high-resolution; ~20 Å is enough to drive template picking. Even a rough ab initio map works.
- Output size and zero-padding factor control the box size of generated templates; bigger pads improve interpolation at higher memory cost.

Template Picker takes one or more templates plus aligned/CTF-corrected micrographs. Practical knobs:
- The particle-diameter parameter must match the real particle, not the box.
- Minimum separation distance is expressed in units of diameters; 0.5 lets centres be one diameter apart. Increase for filaments-on-membrane or dense backgrounds.
- "Pick on denoised micrographs" automatically turns off CTF-based template filtering, because denoising suppresses CTF effects in the image.

Watch for template bias: if all templates show the same view, picks are biased toward that orientation and downstream 3D may misrepresent the structure.

## Topaz: Train, Extract, Denoise
Topaz is a separately licensed external tool wrapped by cryoSPARC. Install it in its own conda environment and point cryoSPARC at the executable (or a wrapper shell script that activates the right env first). v5.0 supports Topaz v0.3.0; older versions are pinned to Topaz 0.2.5.

**Topaz Train / Cross Validation**
- Inputs: a clean particle set (often from blob → 2D → Select 2D) plus the micrographs they came from.
- Set the expected-particles-per-micrograph reasonably; if it falls below the actual labeled density, the loss reverts to the inferior PN function instead of GE-binomial.
- Downsampling factor ~8–16 is normal for training; this is for training only and does not change extraction box size.
- Keep the train-test split > 0 so cross-validation metrics mean something.
- Topaz training is sensitive to seed-set quality. Garbage in → biased model.

**Topaz Extract**
- Tune the particle-score threshold to balance recall vs purity; iterate by passing extracted picks through Inspect Particle Picks, where Topaz scores show up in the power-score axis.
- After Topaz Extract, particles still need an Extract from Micrographs job to refresh per-particle CTF and metadata before any 2D/3D job uses them.

**Topaz Denoise**
- Three modes: pretrained model, train a new model from raw movies, or apply a previously trained user model. The combination of denoise-model and training-micrograph inputs selects the mode.
- Denoised micrographs are for picking and inspection only; reconstruction still uses raw micrographs.
- Older notes warned Topaz performed badly on cryoSPARC's Micrograph Denoiser output; v5.0 adds explicit compatibility with Topaz 0.3.0.

## Deep Picker Train / Extract
Deep Picker Train / Deep Picker Inference were cryoSPARC's in-house deep picker through v4.7. They are deprecated and removed in v5.0+.

For v4.x users still running Deep Picker:
- Same general training discipline as Topaz: clean labeled seed, validation split, watch loss/accuracy plots per epoch.
- The job saves the best-validation-loss model even on failure; you can resume from it.
- Workflows that span major versions should migrate to Topaz or Template Picker; do not introduce new Deep Picker dependencies.

## Filament Tracer (specialized branch)
Filament Tracer handles helical / fibrillar samples where picks need to be laid out along the helical axis.

- Works with or without templates. Without templates, set minimum and maximum filament diameters and expect lower hysteresis defaults.
- Assumes roughly cylindrical filaments with constant axial contrast. For oblong amyloid cross-sections, prefer Template Picker or Topaz.
- Key knobs: segment separation distance (set close to a multiple of the helical rise), minimum filament length, hysteresis thresholds (default 93/98; 90/95 for template-free), and crossing radius.
- Produces filament identifiers so downstream helical refinement and 2D classification can stay filament-aware.

## Thresholding, overpicking, underpicking, duplicates, edges and junk

**Thresholding**
- NCC, power, and edge-distance are the standard knobs. Power is most useful for blob picking; NCC is more diagnostic for template/Topaz picking.
- Defocus calibration lets one threshold generalize across the dataset.
- Don't over-tighten thresholds early — borderline particles that look like junk in raw micrographs sometimes survive 2D cleanup and contribute signal.

**Overpicking**
- Predictable for Blob Picker on samples with strong Gaussian contaminants (gold edges, ice contamination, micelles). Fix downstream with 2D classification + Select 2D rather than aggressive picking thresholds.
- Template Picker can overpick on carbon edges and grid bars; combine with the Micrograph Junk Detector or edge-distance thresholds.

**Underpicking**
- Usually a denoiser problem (raw micrographs too noisy), a particle-diameter mis-set, or a too-tight threshold.
- For small particles, switch to Topaz with a curated seed, or rebuild templates from a higher-quality 2D class set.

**Duplicate picks**
- Auto-merging by UID happens whenever multiple particle inputs are connected to the same downstream slot; this is set-union, not duplicate removal.
- For near-duplicates with slightly different centres (typical of Topaz on dense fields), use the Remove Duplicate Particles utility — it supports NCC, 2D alignment error, and 3D alignment error as the "which to keep" metric.
- 2D classification has a built-in duplicate-removal step using minimum separation distance; turn it off and use a standalone Remove Duplicates job when you want explicit control over the keep/reject metric.

**Edge and junk issues**
- The edge-distance threshold in Inspect Picks removes border picks where the box would clip the micrograph.
- Use the Micrograph Junk Detector (after picking, before extraction) to reject picks near labeled junk/carbon/ice defects. In v5.0+, the minimum-label-area parameter prevents tiny false-positive labels from killing real particles.
- If extraction surfaces many border failures, increase edge distance rather than re-running the picker.

## cryoSPARC Live picking transitions and handoff
Live is the screening surface; production picking still flows back into the main project.

- Start with Blob Picker in Live to verify diameter, contamination level, and base contrast.
- Once 2D classes from blob picks are usable, generate templates and switch to Template Picker. Set the particle diameter before activating; use test-on-one-exposure before activating for all.
- Live's selective reprocessing lets you retune thresholds or regenerate templates without restarting the session; only affected stages rerun.
- Pick statistics in Live (NCC, power, edge distance) drive on-the-fly curation and are sticky across the session.
- Common Live picking failures: zero-pick thresholds breaking downstream array shapes (older versions), NaN-driven ice-thickness or slider crashes, and template-source loading bugs. Most are version-fixed; check `25_cryosparc_live.md` and `17_error_lookup.md` before tuning parameters.
- Handoff: export accepted exposures/particles into the main project, then re-pick or re-extract in the main interface for the production branch.

## Handoff to extraction and 2D classification
After picks pass Inspect Picks (or auto-cluster in v4.6+):
- Extract from Micrographs is mandatory for Topaz and other external picks before any 2D/3D job uses them; it refreshes per-particle CTF and metadata.
- Use Fourier crop in extraction to speed early 2D/3D (see `05_extraction_2d.md` for Nyquist and box-size implications). Don't crop so aggressively that small/junk discrimination becomes impossible.
- For the first 2D classification, expect strong junk classes; that is how downstream cleanup is supposed to work. If everything looks like junk, the problem is upstream (diameter, templates, threshold) — not 2D.
- After 2D selection, regenerate templates if you intend to re-pick the full dataset, then iterate once more if 2D still shows missing views.

## Common failure patterns
- **Blob Picker returns mostly contamination / gold / ice.** Tighten power threshold in Inspect Picks; clean in 2D rather than over-restricting at the picker stage.
- **Template Picker shows one orientation dominating 3D.** Templates were view-biased; rebuild from a more diverse 2D selection or from a projected ab initio volume.
- **Topaz Train converges but Extract returns very few particles.** Threshold too high in Extract — drop it and triage in Inspect Picks. Also check the expected-particles-per-micrograph value used during training.
- **Topaz fails with "Cannot determine topaz version" / wrong conda env.** Use a `topaz.sh` wrapper that deactivates cryoSPARC's conda before activating the Topaz env; set this as the Topaz executable path.
- **`ValueError: could not broadcast input array from shape ...` in Create Templates.** Input volume is non-cubic or has a box shape that violates job assumptions; rebuild the volume at the expected pixel size and box.
- **Remove Duplicates "keeps the wrong particle".** It picks by the metric you select (NCC, 2D/3D alignment error); pre-validate the metric on a test subset before running on production sets.
- **Live picking sees zero picks and downstream jobs break.** Older versions had `IndexError` failures on zero-pick thresholds; loosen the threshold or update to a fixed Live build.
- **Picks fall outside vesicles / membrane dominates 2D centring.** Turn off recentring in 2D, or set the recentring threshold and binary mode so membrane density is weighted less; then run Remove Duplicates after a first 2D pass.

## Version-aware highlights
- **v4.0:** Inspect Picks rejects outliers by absolute power-score value (matching v3.3) rather than percentile. Interactive jobs redesigned for large datasets. Project-level default for Topaz executable path.
- **v4.1:** NCC slider zero-pick failure in Live fixed. Failed-exposure double-counting fixed. NaN ice-thickness bug fixed.
- **v4.2:** "Live stops finding new exposures" fixed. Manual Picker no longer requires CTF input.
- **v4.3:** Inspect Particle Picks tolerates datasets without pick statistics. Manual Picker writes locations to disk every 10 s. Live auto-pauses cleanly on instance restart.
- **v4.4:** Reconstruct 2D Classes job. Live-session picking jobs no longer fail for sessions created pre-v4.4. Template Picker gained an option to disable automatic template re-centring.
- **v4.5:** Micrograph Denoiser GA. Denoised micrographs flow into blob/template picking. Removed unused "Recenter templates" parameter from Blob Picker. Topaz Extract accepts particle-diameter units for region radius.
- **v4.6:** Inspect Particle Picks auto-clustering for non-interactive workflows. Quick action to build Blob Picker Tuner from Inspect Picks.
- **v5.0:** Deep Picker Train/Inference removed. Blob Picker generates multiple blobs across the diameter range (controlled by blob-size-spacing); elliptical stretch vs squeeze modes added. Topaz v0.3.0 support plus compatibility with Micrograph Denoiser output. Micrograph Junk Detector: minimum-area parameter and mask-offset fix. Inspect Picks now skips empty CTF bins instead of failing.

## Advisor defaults
If a user asks "how should I pick particles?":
1. Start with Blob Picker on a representative subset; pad the diameter range.
2. 2D classify, Select 2D, build first templates from diverse views.
3. Template Picker on the full dataset (denoised input if available).
4. Inspect Particle Picks with calibrated thresholds; do not over-tighten.
5. Extract, 2D-clean, then optionally train Topaz on the clean set for hard subsets.
6. Use Filament Tracer only for helical/fibrillar samples; do not retrofit it onto globular workflows.
7. Always verify version-specific bug fixes for Live picking and Topaz before trusting older forum advice.

## Cross-links
- `03_preprocessing.md` — motion/CTF/denoiser/junk detector that feeds picking inputs.
- `05_extraction_2d.md` — extraction box size, Fourier crop, first 2D classification.
- `06_abinitio.md` — generating reference volumes for Create Templates.
- `16_tuning_recipes.md` — picker parameter starting points by particle type.
- `25_cryosparc_live.md` — Live picking transitions, reprocessing, and export.
- `17_error_lookup.md` — picker- and Live-specific error strings.
- `particle_set_operations.md` — union/dedup semantics for picks across jobs.
- `version_caveats.md` — version-fixed picking bugs.

## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

- `docs/per_page/processing-data__all-job-types-in-cryosparc__particle-picking.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__particle-picking__job-blob-picker.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__particle-picking__job-blob-picker-tuner.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__particle-picking__interactive-job-manual-picker.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__particle-picking__interactive-job-inspect-particle-picks.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__particle-picking__job-create-templates.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__particle-picking__job-template-picker.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__particle-picking__job-filament-tracer-beta.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__deep-picking__topaz.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__deep-picking__topaz__job-topaz-train-beta.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__deep-picking__topaz__job-topaz-extract-beta.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__deep-picking__topaz__job-topaz-denoise-beta.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__deep-picking__deep-network-particle-picker__job-deep-picker-train-beta-and-deep-picker-extract-beta.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__deep-picking__guideline-for-supervised-particle-picking-using-deep-learning-models.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-blob-picker-tuner.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-particle-picking-calibration.md`
- `docs/forum_threads/digests/forum_particle-picking.md`
- `docs/forum_threads/digests/forum_particle-curation.md`
- `docs/forum_threads/digests/forum_2d-classification.md`
- `docs/forum_threads/digests/forum_cryosparc-live.md`
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
- `videos/notes/02_trpv1_and_a_standard_workflow.notes.md`
- `videos/notes/07_cryosparc_live_walkthrough.notes.md`