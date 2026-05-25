# Topic 03 — Preprocessing

## Scope
Early cryoSPARC preprocessing after import and before serious particle picking/extraction: Patch Motion Correction, Patch CTF Estimation, exposure curation, denoising/junk annotation, and when to defer advanced motion/CTF refinement. Import-specific metadata belongs in `02_import.md`; picking strategy belongs in `04_picking.md`; later CTF/RBMC refinement belongs partly here and partly in the future `ctf_refinement_and_rbmc.md`.

## Decision surface — what preprocessing path should I use?
Default SPA path when raw movies are available:

1. Import Movies with correct pixel size, dose, voltage, Cs, gain reference, and exposure groups.
2. Patch Motion Correction.
3. Patch CTF Estimation.
4. Curate exposures using motion, CTF fit, ice/junk/thumbnails, and early particle counts.
5. Optionally run Micrograph Denoiser / Micrograph Junk Detector for picking and cleanup.
6. Pick/extract particles, then do early 2D/3D cleanup.
7. Only after a decent 3D refinement exists: consider Global/Local CTF Refinement and Reference Based Motion Correction (RBMC).

Prefer a different path when:
- **Only aligned micrographs exist:** start at Import Micrographs → Patch CTF → picking/extraction; RBMC and per-frame correction are unavailable unless raw movies are recovered.
- **External motion correction was already done but raw movies still exist:** usually reprocess raw movies in cryoSPARC anyway, so Patch Motion, Patch CTF, RBMC, exposure groups, and downstream metadata stay self-consistent.
- **A live screening session already did preprocessing:** export the accepted exposures/particles and verify gain, CTF, and threshold provenance before treating them like a normal project branch.
- **You only need a fast pilot:** run Patch Motion on a subset using `Only process this many movies`, Patch CTF the subset, and inspect diagnostics before committing the whole dataset.

## Patch Motion Correction — default first job
Patch Motion Correction is the modern default for movie alignment. It estimates rigid and anisotropic motion without particle locations, applies dose weighting, and outputs motion-corrected micrographs plus metadata needed by later jobs.

### What to inspect
- Rigid and patch motion trajectories in the streamlog.
- Number of incomplete micrographs and their first error in the Event Log.
- Whether early/late frames look bad enough to justify `Start frame` / `End frame` trimming.
- Whether gain correction artifacts remain visible after motion correction.

### Parameters that matter in practice
- **Only process this many movies** — use for a pilot subset; set the random seed if you want repeatable subset tests.
- **Low-memory mode** — use on low-VRAM GPUs or when patch motion fails while preloading the next movie; it slows the job but reduces memory pressure.
- **Save results in 16-bit floating point** — usually safe and saves large amounts of disk.
- **Output denoiser training data** — enable if you plan to use Micrograph Denoiser; ~100 training micrographs are often sufficient, but the default may produce more to survive later curation.
- **Output F-crop factor** — for ordinary non-super-resolution data, default 1.0 is safest; do early downsampling at extraction instead. For 2× super-resolution movies, 0.5 usually brings the output to physical detector pixel size.
- **Start/End frame** — trim known bad frames, especially blank or artifact frames at the beginning/end of movies.
- **Override knots X/Y/time** — rarely first-line. These change spline smoothness, not patch size. Use only when diagnostics show the automatic motion model is under/over-fitting.

### What Patch Motion is not
- It is not a final per-particle polishing step. RBMC is the late-stage per-particle motion correction once a good reference volume and poses exist.
- It does not require particle locations; do not wait for picking before running it.
- It does not remove the need for CTF estimation.

## Patch CTF Estimation — default CTF job
Patch CTF estimates a spatially varying defocus landscape from motion-corrected micrographs. It does not need particle locations. During extraction, cryoSPARC uses the patch model to assign local CTF values at particle positions.

### What to inspect
- **1D search plot:** ideally a single sharp defocus peak.
- **2D/3D defocus landscape:** should be plausible for tilted/bent ice; large variations are not automatically wrong.
- **CTF fit plot:** check Thon rings, fitted red curve, correlation curve, and reported fit resolution.
- **Ice thickness plot:** useful for curation, but not a direct resolution promise.

### Common CTF triage
If Patch CTF looks wrong:
1. Re-check import values first: pixel size, accelerating voltage, spherical aberration, phase plate flag, negative stain flag.
2. Inspect the raw micrograph/power spectrum. Sometimes the CTF envelope is simply poor even if particles are visible.
3. Compare with CTFFIND4 on a few bad micrographs if the patch fit is suspicious.
4. For a diagnostic subset, try flat-sample behavior by setting `Override knots X/Y = 1`; this tests whether the variable defocus landscape is hurting rather than helping.
5. If low-resolution signal dominates the fit but high-resolution rings look real, test a higher minimum fit resolution on a small subset; do not bake this into the full workflow until the subset clearly improves.

Treat the CTF fit resolution as an estimate of expected micrograph quality, not a hard reconstruction limit.

## Exposure curation
Curate after Patch Motion + Patch CTF and before large picking/extraction runs. The point is to remove exposures that will dominate downstream cleanup with obviously bad signal.

Use multiple signals together:
- Motion trajectories / total motion.
- CTF fit resolution, astigmatism, defocus outliers, and failed CTF estimates.
- Ice thickness and visible crystalline ice / carbon / contamination.
- Particle counts after a pilot picker, if available.
- Manual thumbnail review for edge cases.

Advisor rule: be strict about clearly broken exposures, but do not over-curate borderline exposures before seeing particle-level behavior. A micrograph with mediocre CTF can still contribute useful low-resolution particles for early cleanup; a micrograph full of contaminant or crystalline ice usually hurts immediately.

## Denoiser and junk annotation
These are helper surfaces for picking/curation, not a substitute for physical signal.

### Micrograph Denoiser
Use Micrograph Denoiser when visual inspection or particle picking is difficult due to low contrast.

Key rules:
- Denoised micrographs help picking and inspection; extraction/reconstruction still uses the original raw micrographs automatically.
- Inputs need Patch Motion background-subtracted micrographs and CTF estimates.
- Training a dataset-specific model is usually preferred; ~100 training micrographs are often enough.
- If denoised outputs are flat/blown out/blotchy, adjust greyscale normalization or train longer.
- For older workflows without denoiser training data, rerun Patch Motion on a small subset with denoiser training output, train a model, then apply it to the full older set.
- Historical caution: older docs warned that Topaz did not perform well on Micrograph Denoiser outputs; v5.0 notes add Topaz v0.3.0 compatibility. Be version-aware.

### Micrograph Junk Detector
Use after picking and before extraction, or during exposure curation, when contamination/ice defects/carbon edges are causing bad picks.

Key rules:
- It annotates good ice, carbon/gold support, intrinsic ice defects, and extrinsic junk.
- With particles connected, it rejects picks too close to labeled junk.
- In v5.0+, `Min label area for particle rejection` helps avoid rejecting real high-contrast particles when tiny labels are false positives.
- Always inspect the first annotated examples; a detector mask that is slightly offset or overly aggressive will silently bias particle selection.

## Where RBMC fits
Reference Based Motion Correction is a late preprocessing/refinement upgrade, not an initial preprocessing replacement.

Use RBMC when:
- raw movies were imported and Patch Motion was run;
- particles trace back to those movies;
- a good 3D refinement exists, preferably with `minimize over per-particle scale` enabled;
- the reference volume has half maps and a mask;
- motion blur or dose-weighting behavior still seems to limit final resolution.

Do not use RBMC when:
- only aligned micrographs are available;
- consensus refinement is still poor or particle poses are unstable;
- the dataset is still full of junk/states that should be separated first;
- hardware cannot support the CPU/RAM/GPU load.

RBMC can recompute empirical dose weights and particle trajectories. Reuse hyperparameters/dose weights only for closely related datasets or reruns where collection conditions are similar. More GPUs help only when CPU and RAM can feed them; oversubscription on a CPU-limited system can slow the job.

## Common failure patterns

### Patch Motion or Patch CTF stops with `exit code -9`
Likely host RAM or scheduler OOM, not a cryo-EM parameter problem. Check scheduler stdout/stderr, cgroup OOM messages, and requested memory before changing motion/CTF settings.

### GPU memory errors during motion/preprocessing
Use Low-memory mode, reduce concurrent jobs, verify no other process holds VRAM, and avoid unnecessary GPU oversubscription. If the failure is in extraction or later classification, solve it in that job rather than blaming Patch Motion.

### Patch CTF fit suddenly disagrees with Live or another run
First check metadata: pixel size, Cs decimal point, voltage, phase plate/negative stain flags, and whether the compared run used the same micrographs. A wrong Cs or pixel size can look like a mysterious algorithmic failure.

### Denoiser output looks great but 2D/3D does not improve
Expected if the denoiser only improved visual contrast/picking. It does not add reconstruction signal. Validate by picking quality and downstream class averages, not by the denoised thumbnail alone.

### Junk detector rejects plausible particles
Inspect annotation overlays. Increase the minimum label area (v5.0+) or reduce rejection distances if small false-positive labels are eating real particles.

### RBMC makes results worse or no better
Check whether the input poses/reference were strong enough, whether half-sets stayed consistent, whether priors were over/under-regularized, whether frame counts differ across movies, and whether the dataset actually has motion left to correct. Compare before/after refinements at matched settings.

## Version-aware highlights
- **v4.0:** Curate Exposures threshold/output consistency improved; Patch Motion/Patch CTF corrupt-exposure handling improved.
- **v4.1:** Patch CTF ice-thickness NaN bug fixed; motion/extraction event logs count from one rather than zero.
- **v4.2:** Quick action added to run CTF estimation from Patch Motion; Live exposure-discovery issues improved.
- **v4.3:** Interactive exposure curation gained improved grid/preview tools and threshold-start options.
- **v4.4:** RBMC introduced; Patch Motion can accept empirical dose weights; AFIS beam-shift import and exposure group clustering improved; float16 output added for motion/extraction; several RBMC/Patch CTF edge cases fixed.
- **v4.5:** Micrograph Denoiser introduced; RBMC stability improved; Patch Motion frame-count metadata fixed; motion/CTF freeze after abnormal child process termination fixed.
- **v4.6:** Inspect Picks auto-clustering supports denoised-micrograph workflows; EER/Live pixel-size display and denoised-micrograph scaling fixes.
- **v5.0:** Patch Motion/Live worker faster on low-magnification movies; hot-pixel threshold added to Patch Motion/RBMC; Micrograph Junk Detector gets minimum label area; Topaz v0.3.0 compatibility with Micrograph Denoiser outputs noted; RBMC exposure count display fixed.

## Advisor defaults
If a user asks “how should I preprocess this dataset?”:

1. Ask whether raw movies exist. If yes, default to Import Movies → Patch Motion → Patch CTF.
2. Run a small pilot subset when data quality or parameters are uncertain.
3. Inspect motion and CTF diagnostics before picking.
4. Curate obvious bad exposures, but avoid over-curating borderline data before particle-level evidence exists.
5. Use denoiser/junk detector as picking/curation aids, not as proof of improved reconstruction signal.
6. Keep raw movies connected if RBMC, Local Motion, or late-stage CTF/motion refinement might matter.
7. Defer RBMC until after a good refinement; validate before/after rather than assuming it helps.
8. For tracebacks or launch/OOM errors, consult `17_error_lookup.md` before tuning scientific parameters.

## Cross-links
- `02_import.md` — import path, gain, exposure groups, raw movies vs micrographs.
- `04_picking.md` — blob/template/Topaz/deep picking and pick inspection.
- `05_extraction_2d.md` — extraction, Fourier crop at particle level, 2D cleanup.
- `07_refinement.md` — consensus and NU refinement before late-stage corrections.
- `15_troubleshooting.md` — general triage model.
- `25_cryosparc_live.md` — real-time preprocessing and export/handoff.
- `17_error_lookup.md` — traceback/error string lookup.
- `ctf_refinement_and_rbmc.md` — future targeted CTF/RBMC branch guide.

## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

- `docs/per_page/processing-data__all-job-types-in-cryosparc__motion-correction__job-patch-motion-correction.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__motion-correction__job-reference-based-motion-correction-beta.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__ctf-estimation__job-patch-ctf-estimation.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__exposure-curation__interactive-job-manually-curate-exposures.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__exposure-curation__job-micrograph-denoiser-beta.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__exposure-curation__job-micrograph-junk-detector-beta.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-patch-motion-and-patch-ctf.md`
- `videos/notes/02_trpv1_and_a_standard_workflow.notes.md`
- `videos/notes/08_reference_based_motion_correction.notes.md`
- `docs/forum_threads/digests/forum_motion-correction.md`
- `docs/forum_threads/digests/forum_ctf-estimation.md`
- `17_error_lookup.md`
- `reference/release_notes/markdown/v4.0.md`
- `reference/release_notes/markdown/v4.1.md`
- `reference/release_notes/markdown/v4.2.md`
- `reference/release_notes/markdown/v4.3.md`
- `reference/release_notes/markdown/v4.4.md`
- `reference/release_notes/markdown/v4.5.md`
- `reference/release_notes/markdown/v4.6.md`
- `reference/release_notes/markdown/v5.0.md`
