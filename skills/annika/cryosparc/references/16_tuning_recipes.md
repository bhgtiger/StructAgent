# Topic 16 — Tuning Recipes (Parameter Cookbook by Stage)

## Scope
A workflow-stage cookbook for tuning cryoSPARC: where the safe defaults sit, which knobs are worth touching first, which are last resorts, and which "don't tune that — fix something upstream" cases hide behind a parameter problem. The page is intentionally recipe-shaped: short blocks per stage, each with a safe starting point, the knobs to inspect, escalation moves when defaults don't suffice, and the diagnostic to use to confirm a change is real. Mode- and branch-level decisions live in the per-stage topics already linked — see `02_import.md`, `03_preprocessing.md`, `04_picking.md`, `05_extraction_2d.md`, `06_abinitio.md`, `07_refinement.md`, `08_classification_3d.md`, `09_local_refinement.md`, `10_postprocessing.md`, `15_troubleshooting.md`, `19_symmetry.md`, `20_masks.md`, `25_cryosparc_live.md`, and `26_continuous_heterogeneity.md`.

## Tuning principles (read first)

A few rules survive across stages:

1. **Defaults first, then one change at a time.** cryoSPARC defaults are tuned for "typical" SPA and are usually right. Resist tuning more than one parameter per branch.
2. **Branch, don't overwrite.** Clone the job and change one thing; keep raw inputs unmolested so branches can be compared.
3. **Validate with the right diagnostic for the question, not headline resolution.**
   - 2D / picker quality → class averages + per-class FRC + ESS
   - Global refinement → corrected FSC, the *unsharpened* map, viewing-direction distribution, cFSC summary (v4.5+)
   - Heterogeneity → class flow, occupancy histograms, ESS, per-class reconstructed volumes (not weighted blends)
   - Postprocessing → unsharpened and sharpened maps *together*, local resolution, mask sanity
4. **Don't tune past the data's information content.** Corrected FSC at Nyquist means re-extract, not more sharpening; v5.0+ raises an explicit warning.
5. **Don't tune away upstream errors.** A blurred ligand is a classification problem, not a B-factor; a streaky 2D class is usually a picking, curation, or metadata problem; a featureless high-resolution refinement is rarely a refinement-parameter problem.
6. **Be version-aware.** Several "tuning answers" are really "update to the release that fixed this". The per-stage topics and `15_troubleshooting.md` carry the version table.

## Stage 1 — Import

Default starting point: **Import Movies** whenever raw movies exist; **Import Micrographs** only if raw movies are unavailable; **Import Particle Stack** only for cross-package linkage. Full decision surface in `02_import.md`.

Knobs worth thinking about deliberately:

| Knob | Default behavior | When to change |
|---|---|---|
| Pixel size / voltage / Cs / dose | User-supplied | Mandatory; wrong values silently degrade everything downstream |
| Gain reference | Optional | Always supply for non-gain-corrected movies; `flip_x` / `flip_y` / `rotate` set here, not later |
| EER upsampling factor | Default 2 (super-res-equivalent) | Reduce when downstream pipeline runs at physical pixel size |
| Skip header check | On by default v4.2+ | Leave on for normal imports; use Check for Corrupt Micrographs/Particles jobs when corruption is suspected |
| Exposure groups (AFIS / Import Beam Shift) | Off unless metadata present | Set once if CTF refinement / beam-tilt correction is planned |

Don't tune pixel size to make the resolution number look better — fix the collection metadata.

Inspection checks before queueing more:
- Resolved file paths from the worker shell (not just master)
- A small Patch Motion + Patch CTF pilot with `Only process this many movies` before committing the dataset

## Stage 2 — Preprocessing

### Patch Motion Correction

Defaults are correct for the large majority of datasets. Full background in `03_preprocessing.md` and the Patch Motion / Patch CTF tutorial.

| Knob | Safe default | When to change |
|---|---|---|
| Only process this many movies | All | Pilot subset; set random seed for repeatable subsets |
| Low-memory mode | Off | On for <16 GB VRAM or if patch motion fails while preloading the next movie |
| Save in 16-bit float | On recommended | Off only if downstream demands float32 |
| Output denoiser training data | Off | On if you plan to train Micrograph Denoiser; ~100 mics is usually enough after curation (default count higher to survive curation) |
| Output F-crop factor | 1.0 (no super-res), 0.5 (2× super-res → physical) | Prefer downsampling at extraction unless storage is the constraint |
| Start / End frame | All frames | Trim only known-bad frames |
| Override knots X / Y / time | Auto | Last resort; only touch if streamlog diagnostics show clear under/over-fitting |

Don't tune knots first when motion plots look noisy — re-run with defaults, look for incomplete micrographs in the Event Log, and check gain orientation in the corrected micrographs before changing the motion model.

### Patch CTF Estimation

Defaults are almost always sufficient. Inspect, don't tune:
- **1D search plot:** single sharp defocus peak
- **CTF fit plot:** Thon rings, fitted red curve, correlation curve, reported fit resolution
- **2D defocus landscape:** plausible for tilted/bent ice
- **Ice thickness plot:** for curation, not a resolution promise

If Patch CTF looks wrong, re-check the imports (pixel size, voltage, Cs, amplitude contrast, dose) before tuning estimation parameters.

### Curate vs re-run

- Curate Exposures on motion, CTF fit, ice/junk thumbnails, and early particle counts before serious picking.
- Re-run motion / CTF only if the input metadata was wrong or a known version-fixed bug applies; otherwise curate.
- Micrograph Denoiser: use denoised micrographs for *picking only*; extract from raw.

## Stage 3 — Particle Picking

Picker choice is the first knob, not a parameter. Decision tree (`04_picking.md`):

| You have | Picker | First-pass knobs |
|---|---|---|
| Nothing — no template, no reference | Blob Picker | Min/Max particle diameter (Å) padded generously, single blob shape per job |
| Blob picks but slider thresholds look guessy | Blob Picker Tuner | 15–40 manual picks spanning the defocus range; agreement-distance ≈ protein size |
| Good 2D classes or a known map | Template Picker | `Particle diameter in Angstrom`, `Min. separation dist (diameters)` default 0.5 = touching but not overlapping, `Pick on denoised micrographs` if denoiser model exists |
| Small / heterogeneous / low contrast particle | Topaz (after clean seed) | Hundreds to low-thousands of seed particles |
| Filaments / amyloid | Filament Tracer | Helical-specific guidance |

Practical recipes:
- **Diameter range:** pad generously on both sides. Blob Picker is forgiving on size but unforgiving on truncated ranges.
- **Single blob shape per job (v5.0+):** circular vs elliptical vs ring are normalized differently — mixing them within one job confuses thresholding. Combine across jobs downstream instead. `Blob size spacing (A)` controls number of blobs across the range.
- **Power vs NCC at curation:** at blob stage, *power* is the more useful slider for catching contamination; NCC is more meaningful with template picking, where the reference resembles the particle. Defocus-calibrated pick scores (v2.13+) mean a threshold on one defocus regime usually carries across the dataset.
- **Template diversity:** generate templates from a Select-2D set covering multiple views, not all the same view, otherwise template bias is baked in. ~20 Å templates are sufficient for picking.
- **Denoised input:** when on, Template Picker auto-disables `Use CTFs to filter the templates`.

Don't over-tune thresholds early. Aggressive thresholding (zero picks per micrograph) has historically broken downstream behavior in Live; the better path is to let picking succeed and clean in 2D / heterogeneous refinement.

## Stage 4 — Extraction and First 2D Classification

### Extract from Micrographs

| Knob | Default | Recipe |
|---|---|---|
| Extraction box | Particle-dependent | Use an FFT-efficient box from the published list (32, 36, 40, 48, 64, 100, 128, 192, 256, 320, 384, 512, …) generously larger than the particle to capture CTF-delocalized signal |
| Fourier-crop to box size | Off | Crop aggressively (e.g. 128–256) for an early screening branch; re-extract at full size before resolution approaches the cropped Nyquist |
| Second (small) F-crop box (CPU extraction, v4.0+) | Off | Output a second, smaller-box particle set for fast early 2D/3D while preserving the full-size stack |
| Recenter using aligned shifts | On | Off if recentering is following an off-target feature |
| 16-bit float (v4.4+) | On | On unless an external dependency requires float32 |

Don't double-extract. If you use Local Motion Correction (legacy), it does its own extraction.

### First 2D Classification

| Knob | Default | Recipe |
|---|---|---|
| Number of 2D Classes | 50 typical | 50–200 for hundreds-of-thousands particles; fewer when expected views are few, more when junk fraction is high |
| Maximum resolution (Å) | ~6 Å | Lower the resolution cap (numerically higher Å, e.g. 12 Å) when classes look spiky/overfit; raising it rarely helps 2D and risks overfit |
| Maximum alignment res (Å) | Same as max res | Use a coarser alignment res when neighbours / micelle drag alignment, then average at the finer res |
| Minimum alignment res (Å) | Off | 40–60 Å when neighbours / micelle / contamination drag alignment |
| Plotting sort method (v5.0+) | Similarity | Switch to size-sorted for "how clean is this" reads; keep similarity for state-spotting |

Iteration / batch heuristics: defaults are good for the typical case. v4.4 rewrote 2D with reduced memory and added 16-bit float output for particles/micrographs; v4.6 improved CPU requests for multi-GPU 2D. If you hit `cufftAllocFailed` or blank classes on multi-GPU, drop GPUs / batch / crop before tuning class count.

Cleanup loop recipe:
1. 2D
2. Select 2D
3. Optional second 2D on the kept particles
4. Optional: regenerate templates → Template Picker → re-Extract → re-2D
5. Remove Duplicate Particles (NCC / 2D-error / 3D-error key) when combining pickers
6. Rebalance only when orientation bias is real and harmful — Rebalance 2D Classes for class-level, Rebalance Orientations after a first 3D refinement for view-level

Don't tune away "all classes look like junk." That is almost always a picking / metadata / pixel-size problem; debug upstream.

## Stage 5 — Ab Initio and Heterogeneous Refinement

### Ab-Initio Reconstruction

Defaults are usable. Knobs worth deliberate thought (`06_abinitio.md`):

| Knob | Default | Recipe |
|---|---|---|
| Number of classes | 1 for a single reference | 3–6 for first multi-class junk-vs-signal sort; reserve ≥1 slot for junk; >8 rarely productive — escalate to Heterogeneous Refinement / 3D Classification |
| Number of particles to use | Blank | Set only if you must speed a multi-class job whose classification will *not* be used downstream; single-class jobs auto-subsample |
| Maximum resolution | Default range | Push finer for small membrane proteins / high-symmetry particles producing flat "disc" volumes |
| Initial / final minibatch size | Default | Increase to ~1000 for apoferritin-like C1 / icosahedral pose-collapse cases |
| Symmetry | C1 | Stay C1; only impose at ab initio when "disc" persists and external evidence supports it |
| Volume window mode (v5.0+) | Spherical | Cylindrical for helical; none for testing whether windowing is biasing alignment |

Don't push maximum resolution to "get more detail" — ab initio uses no half-sets and overfits.

### Heterogeneous Refinement

Treat as cleanup and state separation, not final polish (`07_refinement.md`):

- **Identical starting volumes** is a deliberate strategy for state separation when small per-class pose updates matter (FaNaC1-style apo/holo separation; pseudosymmetry rescue).
- **`Force hard classification`** = on when classes drift toward equal occupancy or ESS stays high.
- Initial models must be on the right grey scale; ab-initio outputs satisfy this, imported EMDB maps may not.
- v4.5 added a spherical-mask input (inner/outer diameter); useful when neighbouring density leaks into the box.

Don't expect Heterogeneous Refinement to produce a final consensus map — that's Homogeneous / NU.

## Stage 6 — Global Refinement (Homogeneous / NU / Local)

### Homogeneous Refinement — the safer first branch

Default starting point after cleanup. Inspect, don't pre-tune.

| Knob | Default | Recipe |
|---|---|---|
| Symmetry | C1 | Impose only when point group is well established and the consensus map matches |
| Window inner / outer radius | Tuned for typical centred particles | Tighten only in crowded grids; verify particles are well-centred first (windowing is applied before centring) |
| Initial lowpass resolution | Coarse | Keep coarse for ab-initio / hetero outputs; finer only for trusted high-res references |
| Mask | Dynamic | Provide a static soft mask if dynamic masking fails or to focus on a stable region |
| Per-particle scale (v5.0+ default on for Homo/NU/Helical) | On | Leave on; zero/negative-scale particles go to Rejected Particles for inspection |

### Non-Uniform Refinement

Reach for NU when the target is a membrane protein with micelle/nanodisc, small with flexible loops, or when Homogeneous shows surface noise. NU regularization is fully GPU-accelerated and constrained by `3 × box³ × 4 bytes` GPU RAM (a 12 GB GPU handles ~1024³). v4.4 made regularization 7–10× faster; if VRAM is tight at large boxes (box ≳ 600 on 11 GB, ≳ 700 on 16 GB, ≳ 882 on 32 GB), enable `Low-memory mode` to revert to the pre-v4.4 path.

NU-specific cautions:
- **NU can be worse than Homogeneous** on small/unusual targets. v5.0 added a switch to disable the dynamic refinement mask in NU.
- **`Adaptive Marginalization`** on by default; helps small/noisy particles.
- **Per-particle scale** on by default v5.0+.

Don't tune by pulling the dynamic-mask threshold tight to make Tight FSC look higher. If Corrected FSC drops while Tight rises, the mask is doing the work, not the signal. Relax the threshold (as low as ~0.05 in extreme cases) or supply a softer static mask.

### Per-particle defocus / global CTF refinement / RBMC ordering

Do CTF refinement / RBMC **after** the consensus is solid. For RBMC, turn on `minimize over per-particle scale` upstream, then let the auto hyperparameter search choose spatial, acceleration, and temporal priors. Reuse priors and dose weights across related datasets. Diminishing returns past ~3–4 GPUs if CPU is slow.

### Local Refinement and Particle Subtraction

Only run when global consensus is already solid and one region is blurred because it moves rigidly with respect to the consensus alignment frame (`09_local_refinement.md`).

| Knob | Recipe |
|---|---|
| Starting poses | From a converged Homogeneous / NU / prior local refinement — never raw ab initio |
| Starting volume | The volume the poses were aligned to; prefer a class-specific volume when the question is class-specific |
| Initial low-pass / alignment resolution | Just below the resolution of the region of interest, not at the global consensus value |
| Mask | Static, soft-edged, generous; built from a blurred map base; no detached islands; dilate ~5–10 voxels then soft-pad ~20 voxels as a starting heuristic |
| `Local shift search extent` / `Local rotation search extent` | Deliberately small; pair with Gaussian priors on shifts/rotations for small ROIs |
| Fulcrum | Centroid of the mask is a common stable choice (Chimera `measure center`) |
| Particle subtraction mask | Covers the region to **subtract**, not the region to keep; partition cleanly against the local-refinement mask |

Overfitting cautions:
- Tight focus masks + low SNR amplify overfitting risk; use the smallest justifiable mask, the smallest search range, and Gaussian priors.
- Subtraction quality is bounded by the quality of the volume being subtracted; locally refine the to-be-subtracted region first when it materially helps.
- Match Particle Subtraction's windowing/scaling to the input refinement, not job defaults.

## Stage 7 — Discrete and Continuous Heterogeneity

### 3D Classification (discrete, fixed poses)

Discrete states given trusted poses (`08_classification_3d.md`):

| Knob | Default | Recipe |
|---|---|---|
| Number of classes | 3–6 for first pass | Larger counts (10–50+) become cheap (no alignment); ≥100 for large-scale sorting, then Regroup 3D Classes |
| `Filter resolution` (v4.5+) | Must be set explicitly | 3–6 Å for small ligand presence/absence, 6–10 Å for inter-domain conformational change, >10 Å for present/absent domain |
| `Force hard classification` | Off | On when ESS stays high, classes look similar, or weighted back-projection is averaging classes together |
| `Use latent mixing coefficients` (v5.0) | Off | On when classes drift toward uniform occupancy |
| PCA initialization | Off | On to expose subtle differences; ~3–5 reconstructions per output class is a working rule |
| Solvent / focus mask | Solvent auto-generated v5.0+ | Focus mask only when motion is geographically localized; too-tight focus masks collapse coupled motion |

Don't ask 3D Classification to settle identity when poses are bad. Fix the consensus first.

### Heterogeneous Refinement (when small pose updates matter)

Use it instead of 3D Classification when residual blur suggests pose bias inherited from a mixed consensus. The FaNaC1 apo/holo example: fixed-pose 3D Classification left a fake ligand bump in the apo class; identical-volume heterogeneous refinement with C3 separated cleanly.

### 3D Variability Analysis

Continuous motion under fixed poses (`26_continuous_heterogeneity.md`):

| Knob | Default | Recipe |
|---|---|---|
| Number of modes | 3 | 2–3 to expose dominant motion; 4–6 only if unrelated motions are being forced into one mode |
| Filter resolution | Must be set | Below consensus global resolution, matched to expected motion scale (e.g. 6 Å for ~5–7 Å shifts; 12 Å for whole-domain swings); 0.5 Å changes can move features in/out of the model |
| High-pass resolution | Off | ~20 Å for membrane proteins to suppress micelle / structured-noise variability |
| Mask | Cover full extent of motion, soft-edged; exclude micelle/nanodisc unless modelling it intentionally |

3DVA Display modes:
- **Simple:** linear movie; ignores particles; do not build models against simple-mode frames.
- **Intermediates:** particle-backed slices along one coordinate; `window > 0` = triangular weighting, `0` = tophat, `-1` = equal-particle bins.
- **Cluster:** Gaussian-mixture in latent space; unstable for genuinely continuous distributions. Refine cluster subsets against their **own** reconstructed volume, not the mixed consensus.

### 3D Flex

Continuous nonlinear motion with mesh prior; far more sensitive than 3DVA. Run 3DVA first to know what motions are present before designing a mesh. Tune rigidity (lambda) empirically, latent-centring so coordinates land within ±~1.5, mesh granularity ≈ "one tetra per ~1–2 alpha helices" as a working rule. Don't use 3D Flex for compositional separation — it deforms density, it cannot create or delete it.

## Stage 8 — Postprocessing

Postprocessing interprets; it does not rescue (`10_postprocessing.md`).

### Sharpening Tools

| Knob | Default | Recipe |
|---|---|---|
| B-factor to apply | Auto / Guinier (v4.4+) | Start with the auto-estimated B; use manual when auto over-sharpens; compare maps across the dataset on a single B for like-for-like reading |
| Which FSC to filter by (v5.0+) | full | half = refinement-style filter; none = Butterworth lowpass for like-for-like comparison across maps |
| Lowpass filter order + corner resolution | Used only with `none` | Set corner to a common value when comparing several maps |
| Mask | Auto-tightened FSC mask from input volume group (v5.0+) | Provide a manual softer mask if dynamic masking is artificially tight; v5.0+ allows running without a mask |

Don't sharpen *until* features appear. Side-chain density that only exists at large negative B-factor and disappears in the unsharpened map is almost certainly hallucinated.

### Local Resolution Estimation

- Uses half-maps (Homo / Hetero / NU refinement output).
- `Annealing Factor = 0` for local; `1` yields the global resolution.
- View in Chimera with `Surface Color` driven by `map_locres`.
- v4.6.2 fixed a Z-flip in the volume-viewer colormap; if a pre-v4.6.2 plot looks flipped, update before drawing conclusions.

### Validation (FSC)

Use to re-FSC with a custom mask, to test mask auto-tightening, or to export EMDB-compatible `.txt` / `.xml` curves. From v5.0 FSC plots are standardized in colour, indicate the mask used and whether phase randomization was applied, and Validation (FSC) no longer fails on CPU-only workers.

### Don't trust cosmetically better maps

- Tight FSC rising while Corrected FSC drops = mask doing the work.
- Corrected FSC at Nyquist = re-extract at smaller pixel size (v5.0+ raises an explicit warning).
- An apparent resolution jump after several re-refinements → suspect half-set contamination, especially after RBMC → refinement loops. v4.5.3 fixed this by defaulting refinements to use the input split; Particle Sets Tool can balance unequal splits.
- Featureless map with high reported resolution → alignment failure, model bias, or wrong handedness; do not postprocess further. Flip handedness via Homogeneous Reconstruction Only (updates particle poses), not just Volume Tools (volume-only flip).

## Stage 9 — Performance and Resource Tuning

The cheapest performance fixes touch box, crop, and cache. See `03_preprocessing.md`, `05_extraction_2d.md`, and `15_troubleshooting.md`.

| Symptom / goal | First knob |
|---|---|
| OOM at large box | Reduce GPUs first, then batch size, then Fourier crop |
| `cufftAllocFailed` during extraction (older versions) | Update; v4.1 reduced extraction GPU memory pressure |
| Blank / faint 2D classes on multi-GPU (older) | Update; v4.2 fixed this; v4.6 improved CPU requests for multi-GPU 2D |
| NU OOM at large box | Enable `Low-memory mode` (reverts to pre-v4.4 path) |
| Slow extraction | Verify it is I/O-bound; CPU and GPU extraction run at similar wall-clock on typical hardware |
| SSD cache hangs / "waiting for unlocked files" | Let the holding job finish; only delete locks after confirming the holding process is gone. v4.4 / v4.5 / v4.6 rewrote the cache layer — update before deep cache debugging |
| GPUs idle but queue is long | CPU starvation per GPU; cryoSPARC needs enough CPU per GPU to feed work |
| Transparent hugepages hurting performance | v4.6.2 changed worker processes to request not-always-THP; OS warnings are surfaced in the job log |

Cluster / lane tuning is out of scope at parameter level — see the planned `21_gpu_lane_queue.md`. The high-level rule: don't tune algorithm parameters to compensate for a scheduling problem.

## Failure-pattern mini table — symptom → first knobs → escalation

| Symptom | First knobs to inspect | Escalate to |
|---|---|---|
| All 2D classes look like junk | Picker thresholds, particle diameter, import pixel size, gain orientation | Re-pick after fixing upstream; do not tune 2D class count first |
| 2D classes streaky / overfit | Lower max resolution (e.g. 8 → 12 Å), raise class count modestly, set min alignment res 40–60 Å | Check motion/gain artefacts in micrographs |
| Centering walks off during 2D | Turn off recentering during extraction; minimum alignment resolution to suppress background | Refine box and re-extract |
| Ab initio returns flat "disc" volumes | Raise minibatch (~1000), push max resolution finer | Impose symmetry only if disc persists with external evidence |
| Hetero Refine classes collapse to identical | `Force hard classification` on | Try identical starting volumes (state separation); revisit class count |
| NU FSC: Tight high, Corrected drops | Relax dynamic-mask threshold; supply softer static mask | Inspect `mask_refine` / `mask_fsc`; try disabling NU dynamic mask (v5.0+) |
| 3D Classification: classes look identical, mean ESS high | `Force hard classification` on; lower `Filter resolution` to the scale of the expected difference | Heterogeneous Refinement with identical starting volumes |
| Local refinement: blips/shells at mask edge | Enlarge mask, add soft edge, smaller search range, Gaussian prior | Particle subtraction; re-extract centred on ROI |
| 3DVA: components dominated by ringing | Loosen mask, set high-pass (~20 Å for membrane proteins) | Reduce filter resolution to the expected motion scale |
| 3D Flex underperforms 3DVA | Mesh granularity, rigidity, micelle handling | Run 3DVA first to characterize motions; redesign mesh |
| Corrected FSC at Nyquist | None — don't sharpen / tighten | Re-extract at smaller pixel size and re-refine |
| Suspiciously good resolution after re-refinements | Check half-set independence | Particle Sets Tool to balance splits; Subset Particles by Statistic to re-split (v5.0+) |
| Featureless map with good number | None — postprocessing won't fix | Check handedness (Homogeneous Reconstruction Only flip); check consensus / symmetry assumptions |
| Nontrivial Rejected Particles (zero/neg scale) | Inspect rejected micrographs | Revisit import / preprocessing for contrast inversion, blanks, bad import |
| Job fails immediately on queue / launch | Worker/SSH/shell/launch, lane | `cryosparcm log command_core`; do not tune algorithm |
| Live stopped finding new exposures | Path/wildcard/recursion/timestamps, stale session state | Restart session; check version-specific Live fixes (v4.2/v4.3) |

## Advisor defaults — 13 rules the future agent should follow

1. **Defaults first.** Read the "Common Parameters" and "Recommended Alternatives" sections of the cryoSPARC job docs before touching expert knobs.
2. **Change one thing per branch.** Clone, compare, keep the better branch.
3. **Look at the unsharpened map alongside the FSC plot.** Pretty sharpened maps with no FSC support are warning signs.
4. **Match filter / classification resolution to the question's scale.** 3D Classification at 3–6 Å for ligand presence, 6–10 Å for inter-domain, >10 Å for domain present/absent; 3DVA filter set below consensus and matched to expected motion scale.
5. **Stay C1 at ab initio.** Impose symmetry only after a symmetry hypothesis is established and a C1 consensus is plausible.
6. **Use Heterogeneous Refinement, not 3D Classification, when small pose updates matter.** Pose bias inherited from a mixed consensus is invisible to fixed-pose classification.
7. **Use Local Refinement only after consensus identity is settled.** Never start from raw ab-initio poses; never on uncleaned junk.
8. **Build masks soft, generous, blurred-base, no islands.** A pretty boundary on the raw map is not the goal; a robust boundary on a blurred copy is.
9. **Re-extract before Nyquist saturation.** Re-extract at full pixel size before the corrected FSC approaches the cropped Nyquist; v5.0+ raises an explicit warning.
10. **Do CTF refinement / RBMC after the consensus is solid**, not before. Turn on per-particle scale upstream; let the RBMC auto-hyperparameter search do its job.
11. **Preserve half-set splits through RBMC → refinement loops.** v4.5.3+ defaults to using the input split; older instances can re-mix splits silently.
12. **Don't tune Nyquist-saturated maps or featureless high-resolution maps.** Go upstream: re-extract, fix handedness, fix consensus.
13. **Be version-aware.** A surprising fraction of "tuning" answers are actually "update": v4.1 (extraction GPU memory), v4.2 (multi-GPU 2D blanks, Live new-exposure discovery), v4.4 (NU regularization speed, 2D rewrite, Orientation Diagnostics, Heterogeneous Reconstruction Only), v4.5 (refinement split defaults, 3D Classification `Filter resolution` rename), v4.6 (multi-GPU 2D CPU requests, transparent hugepages, local-resolution Z-flip), v5.0 (Nyquist warning, FSC plot standardization, per-particle scale defaults, NU dynamic-mask switch, Homogeneous Ab-Initio Refinement BETA).

## Cross-links

- Import & metadata: `02_import.md`
- Preprocessing (Patch Motion / Patch CTF / curation / denoiser): `03_preprocessing.md`
- Picking: `04_picking.md`
- Extraction & 2D: `05_extraction_2d.md`
- Ab initio: `06_abinitio.md`
- Homogeneous / NU / Heterogeneous refinement: `07_refinement.md`
- 3D Classification (discrete): `08_classification_3d.md`
- Local Refinement & particle subtraction: `09_local_refinement.md`
- Postprocessing (sharpening / FSC / local resolution): `10_postprocessing.md`
- Troubleshooting: `15_troubleshooting.md`
- Symmetry: `19_symmetry.md`
- Masks: `20_masks.md`
- cryoSPARC Live: `25_cryosparc_live.md`
- Continuous heterogeneity (3DVA / 3DFlex): `26_continuous_heterogeneity.md`
- Error string lookup: `17_error_lookup.md`

## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

- 02_import.md
- 03_preprocessing.md
- 04_picking.md
- 05_extraction_2d.md
- 06_abinitio.md
- 07_refinement.md
- 08_classification_3d.md
- 09_local_refinement.md
- 10_postprocessing.md
- 15_troubleshooting.md
- 19_symmetry.md
- 20_masks.md
- 25_cryosparc_live.md
- 26_continuous_heterogeneity.md
- 17_error_lookup.md
- docs/per_page/processing-data__all-job-types-in-cryosparc__import.md
- docs/per_page/processing-data__all-job-types-in-cryosparc__import__job-import-movies.md
- docs/per_page/processing-data__all-job-types-in-cryosparc__motion-correction__job-patch-motion-correction.md
- docs/per_page/processing-data__all-job-types-in-cryosparc__ctf-estimation__job-patch-ctf-estimation.md
- docs/per_page/processing-data__all-job-types-in-cryosparc__particle-picking__job-blob-picker.md
- docs/per_page/processing-data__all-job-types-in-cryosparc__particle-picking__job-template-picker.md
- docs/per_page/processing-data__all-job-types-in-cryosparc__particle-curation__job-2d-classification.md
- docs/per_page/processing-data__all-job-types-in-cryosparc__extraction__job-extract-from-micrographs.md
- docs/per_page/processing-data__all-job-types-in-cryosparc__3d-reconstruction__job-ab-initio-reconstruction.md
- docs/per_page/processing-data__all-job-types-in-cryosparc__3d-refinement__job-heterogeneous-refinement.md
- docs/per_page/processing-data__all-job-types-in-cryosparc__3d-refinement__job-homogeneous-refinement.md
- docs/per_page/processing-data__all-job-types-in-cryosparc__3d-refinement__job-non-uniform-refinement-new.md
- docs/per_page/processing-data__all-job-types-in-cryosparc__variability__job-3d-classification-beta.md
- docs/per_page/processing-data__all-job-types-in-cryosparc__local-refinement__job-local-refinement-beta.md
- docs/per_page/processing-data__all-job-types-in-cryosparc__local-refinement__job-particle-subtraction-beta.md
- docs/per_page/processing-data__all-job-types-in-cryosparc__post-processing__job-sharpening-tools.md
- docs/per_page/processing-data__all-job-types-in-cryosparc__post-processing__job-local-resolution-estimation.md
- docs/per_page/processing-data__all-job-types-in-cryosparc__post-processing__job-validation-fsc.md
- docs/per_page/processing-data__all-job-types-in-cryosparc__variability__job-3d-variability.md
- docs/per_page/processing-data__all-job-types-in-cryosparc__variability__job-3d-variability-display.md
- docs/per_page/processing-data__tutorials-and-case-studies__tutorial-patch-motion-and-patch-ctf.md
- docs/per_page/processing-data__tutorials-and-case-studies__tutorial-ctf-refinement.md
- docs/per_page/processing-data__tutorials-and-case-studies__tutorial-orientation-diagnostics.md
- docs/per_page/processing-data__tutorials-and-case-studies__tutorial-3d-variability-analysis-part-one.md
- videos/notes/02_trpv1_and_a_standard_workflow.notes.md
- videos/notes/05_fanac1_and_discrete_heterogeneity.notes.md
- videos/notes/06_fanac1_and_continuous_heterogeneity.notes.md
- videos/notes/08_reference_based_motion_correction.notes.md
- reference/release_notes/markdown/v4.0.md
- reference/release_notes/markdown/v4.1.md
- reference/release_notes/markdown/v4.2.md
- reference/release_notes/markdown/v4.3.md
- reference/release_notes/markdown/v4.4.md
- reference/release_notes/markdown/v4.5.md
- reference/release_notes/markdown/v4.6.md
- reference/release_notes/markdown/v5.0.md
