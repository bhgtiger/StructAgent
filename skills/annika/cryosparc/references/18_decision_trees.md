# Topic 18 — Decision Trees

## Scope
Advisor-side routing trees for the most common "what next?" questions in cryoSPARC. Each tree is a compressed index across the per-stage topics: the goal is to pick the right branch fast, not to re-teach the parameter logic. Mechanics live in the per-stage topics (`02_import.md` … `26_continuous_heterogeneity.md`); error strings live in `17_error_lookup.md`; debugging mental model lives in `15_troubleshooting.md`; parameter recipes live in `16_tuning_recipes.md`.

## How to use these trees
- Read top-to-bottom; the first matching row wins.
- "Red flags" are conditions that should *short-circuit* normal routing and force triage instead.
- "Advisor default" is the safe move if no red flag fires and the user has not given a strong reason to deviate.
- Cross-links point at the topic that owns the actual mechanics.

---

## Tree 1 — Import / Preprocessing

**Question:** what to ingest, in what order, and when to stop and fix metadata.

**Red flags (fix before anything else):**
- Pixel size, voltage, Cs, or dose not confirmed against collection sheet.
- Path resolves on master but not from the worker shell as the cryoSPARC owner.
- Patch CTF defocus map looks plausibly wrong but no one re-checked import values.
- Gain reference not supplied for non-gain-corrected movies (or orientation untested).
- TIFF picks from RELION/MotionCor2/Warp re-aligned in cryoSPARC without Y-flip check.

**Branch rules:**

| Inputs available | Branch | Why |
|---|---|---|
| Raw movies (EER/TIFF/MRC) | Import Movies → Patch Motion → Patch CTF → curate | Enables RBMC and per-frame jobs later |
| Aligned micrographs only | Import Micrographs → Patch CTF → curate | RBMC unavailable; accept it |
| External particle coords (RELION etc.) | Import Movies + redo motion/CTF, then Import Particle Stack with cryoSPARC mics as Source Micrographs | Keeps per-particle CTF / exposure groups / RBMC consistent |
| Imported volumes / result groups | Import 3D Volumes / Import Result Group | Not an image-import path |
| Live session already preprocessed | Export accepted exposures/particles to main project, re-verify gain/CTF/threshold provenance | Production branch must be self-consistent |

**Advisor defaults:**
- Always pilot Patch Motion + Patch CTF with `Only process this many movies` before committing the full set.
- Set exposure groups (AFIS / Import Beam Shift) at import if CTF refinement or beam-tilt correction is planned later.
- Curate exposures on motion, CTF fit, ice/junk thumbnails, early particle counts — in that order.
- Defer Global/Local CTF refinement and RBMC until a decent 3D refinement exists.

**Cross-links:** `02_import.md`, `03_preprocessing.md`, `17_error_lookup.md` (launch / path / metadata strings).

---

## Tree 2 — Picking / 2D

**Question:** which picker to use, and when 2D is telling you to go back to picking.

**Red flags:**
- Templates generated from a single view (template bias incoming).
- Deep Picker workflow on v5.0+ (deprecated and removed — do not plan around it).
- Picks come from a non-cryoSPARC source but no Extract from Micrographs job between import and 2D.
- "Bad" 2D classes still show particle-like averages — those are not necessarily junk.
- Box size below ~1.5–2× longest particle dimension, or not on an FFT-friendly value.

**Branch rules:**

| State | Branch | Notes |
|---|---|---|
| No reference, no templates | Blob Picker → Extract → 2D | Treat first picks as disposable |
| Blob picks look wrong with defaults | Blob Picker Tuner with 15–40 manual seeds | Cannot beat Blob Picker in principle, only tune it |
| Have clean 2D / known map | Template Picker from selected classes (or projected reference) | Use diverse views; turn on denoised input if denoiser model exists |
| Small / heterogeneous / low-contrast particle | Topaz Train on clean subset (~hundreds–thousands), then Topaz Extract | Re-extract after re-pick |
| Filaments / amyloid / helical | Filament Tracer | Not vanilla template picking |
| Calibration / ground truth only | Manual Picker on small subset | Feeds tuner / Topaz / template gen |
| 2D shows preferred orientation | Stay in picking + curation; do not move to 3D | See Tree 5 |

**Advisor defaults:**
- Power slider is the most useful blob-stage filter; NCC matters more for template picks.
- Be stricter when selecting 2D classes to make templates than when selecting particles for downstream 3D.
- Crop more aggressively at extraction for early speed; re-extract full-size before resolution approaches cropped Nyquist.
- Use Restack Particles after heavy curation; reclaim disk and speed up caching.

**Cross-links:** `04_picking.md`, `05_extraction_2d.md`, `videos/notes/02_trpv1_and_a_standard_workflow.notes.md`.

---

## Tree 3 — Ab Initio / Refinement

**Question:** how to go from a curated stack to a stable consensus map.

**Red flags:**
- "Just rerun NU" when no Heterogeneous Refinement cleanup pass has been done.
- Local refinement attempted before the consensus refinement converges cleanly.
- Symmetry imposed at ab initio with no external evidence.
- 2D looked excellent but Homogeneous/NU underperform — *do not* tune parameters first.
- Reconstructions claimed at cropped-stack Nyquist (corrected FSC near Nyquist) without re-extraction.

**Branch rules:**

| Situation | Branch | Why |
|---|---|---|
| Curated stack, no 3D reference yet | Multi-class Ab-Initio (3–6 classes), then Heterogeneous Refinement to re-decide classes | Ab-initio class assignments are drafts |
| Trusted scale-correct map already exists | Skip ab initio; go straight to Homogeneous or NU Refinement | Use low-passed EMDB volume as starting reference for well-characterized targets |
| Particles already have valid `alignments3D`, only need fresh box/sym/mask | Homogeneous Reconstruction Only | No realignment cost |
| Want safe first global refinement | Homogeneous Refinement first, then NU on the same particles + Homogeneous output | Compare on corrected FSC + visible features, not unmasked number |
| Membrane protein / micelle / small disordered target | Non-Uniform Refinement | Adaptive regularization helps |
| 2D looks excellent, Homogeneous/NU underperform | Homogeneous Ab-Initio Refinement (BETA, v5.0+) as a rescue | Slower; single output |
| Junk vs signal mixed in consensus | Heterogeneous Refinement with one good + 1–2 junk volumes, often `force hard classification` | Cleanup branch |

**Advisor defaults:**
- Default class count for ab initio: 2–4 (one good + 1–2 junk slots). >8 classes is rarely productive.
- Leave particle count blank for single-class; use all particles when downstream depends on multi-class assignment.
- Re-extract at full pixel size before corrected FSC approaches cropped Nyquist; then refine again.
- Do not chase resolution with parameter knobs when symmetry is enforced and consensus is solid.

**Cross-links:** `06_abinitio.md`, `07_refinement.md`, `16_tuning_recipes.md`.

---

## Tree 4 — Resolution stalls

**Question:** refinement converged but the corrected FSC is short of expectations, or it plateaus.

**Red flags:**
- Sharpening B-factor being increased to "fix" missing detail.
- Recomputing FSC against an aggressive custom mask and quoting that as the resolution.
- Reading the locally-filtered map as the primary scientific map.
- Resolution number rising while map features visibly degrade.

**Branch rules:**

| Symptom on diagnostics | Branch | Why |
|---|---|---|
| Corrected FSC ≈ Nyquist | Re-extract at full pixel size; refine again | Information cap, not refinement cap |
| Corrected FSC dips / oscillates with imposed symmetry | Re-refine in C1 to test (`19_symmetry.md`) | Most direct symmetry-breaking test |
| Big delta between Tight and Loose FSC | Mask is too tight; recompute with Loose / regenerate mask | See `20_masks.md` |
| cFSC strongly anisotropic; viewing-direction plot peaked | See Tree 5 | Preferred orientation regime |
| ROI blurred relative to rest of map | Local Refinement on that ROI (`09_local_refinement.md`) | Only after consensus is good |
| Map shows blurred ligand/domain | Stop polishing; go to classification (`08_classification_3d.md`) or continuous heterogeneity (`26_continuous_heterogeneity.md`) | Heterogeneity, not B-factor |
| Per-particle scale histogram has empty / inverted tails | Subset Particles by Statistic; rebuild stack | Cleanup branch |
| No clear diagnostic improvement | Try Global/Local CTF refinement + RBMC (only after solid consensus) | Late-stage corrections only |

**Advisor defaults:**
- Validate with the diagnostic for the question: corrected FSC + unsharpened map + viewing-direction + cFSC (v4.5+).
- Do not interpret the locally-filtered map as the FSC-truthful map.
- Don't tune past the data's information content; v5.0+ warns explicitly at Nyquist.

**Cross-links:** `07_refinement.md`, `10_postprocessing.md`, `16_tuning_recipes.md`.

---

## Tree 5 — Preferred orientation / anisotropy

**Question:** the map is directionally weak, ringing, or has a streaky 2D.

**Red flags:**
- Reading angular plots as a particle-count histogram (they are not).
- Forcing more classes in ab initio to "spread" orientations.
- Picking only frontal views during template generation.

**Branch rules:**

| State | Branch | Why |
|---|---|---|
| 2D shows few dominant views | Go back to picking with diverse templates; consider Topaz on a clean seed | Picking-stage problem |
| Anisotropic cFSC at consensus | Inspect viewing-direction plot + cFAR/tFAR/SCF* / Relative Signal in Orientation Diagnostics | Confirm anisotropy is real, not just mask |
| Real anisotropy, confirmed | Mitigate at sample/grid level (tilt collection, surfactant, grid) | cryoSPARC cannot synthesize missing views |
| Recurring NU instability with anisotropy + small target | Try Homogeneous Refinement as the consensus instead | NU regularization can latch onto sparse views |
| Symmetric target, ab initio returns flat "disc" | Increase minibatch (~1000), push max-res finer, rebalance views *before* imposing symmetry | Disc is often a pose-collapse artifact, not a symmetry signal |

**Advisor defaults:**
- Treat orientation diagnostics as *cautions*, not scores.
- A pretty map from a few views is still a few-view map; do not paper over with sharpening.

**Cross-links:** `10_postprocessing.md`, `19_symmetry.md`, `07_refinement.md`.

---

## Tree 6 — Heterogeneity routing

**Question:** the map is blurred *somewhere specific*, or you suspect multiple states.

**Red flags:**
- Forcing discreteness on motion that visibly varies smoothly.
- Running 3D Classification when consensus poses are not yet trustworthy.
- 3D Classification with a tight focus mask on a region that moves with a coupled larger domain.
- Continuous methods (3DVA / 3DFlex) on uncleaned stacks — 3DFlex especially.

**Branch rules:**

| Question | Branch | Notes |
|---|---|---|
| Sample-identity heterogeneity (different particles entirely) | Heterogeneous Refinement with junk + signal volumes, often `force hard classification` | Cleanup branch |
| Compositional (present vs absent ligand/subunit) | 3D Classification first if poses are good; else Heterogeneous Refinement with two identical starting volumes | Heterogeneous Refinement does small pose updates per class |
| Conformational, discrete states | 3D Classification with focus mask only if motion is truly local; else solvent mask only | See `08_classification_3d.md` |
| Conformational, continuous, small-scale | 3D Variability Analysis (3DVA), 2–3 dimensions, mask covering the moving region | Cheaper, interpretable axes |
| Conformational, continuous, large/nonlinear, want motion-corrected map | 3D Flexible Refinement (3DFlex) | Far more sensitive to mesh / rigidity / cleanliness |
| 3DVA scatter shows clear bimodality | Switch to 3DVA cluster mode or 3D Classification on the same particles | Discreteness is recoverable from continuous analysis |
| Apo class still has residual ligand-like density after 3D Classification | Suspect pose bias from consensus; rerun via Heterogeneous Refinement with two identical volumes | Consensus poses can pin apo to ligand-bound reference |

**Advisor defaults:**
- Bulk consensus must be trusted before any heterogeneity job; junk in → junk classes out.
- Preserve `alignments3D/split` through Refinement → RBMC → Refinement → Classification loops.
- Per-class FSC and class-specific reconstructed volumes (not weighted blends) are the right diagnostics.

**Cross-links:** `08_classification_3d.md`, `26_continuous_heterogeneity.md`, `07_refinement.md`, `videos/notes/05_fanac1_and_discrete_heterogeneity.notes.md`, `videos/notes/06_fanac1_and_continuous_heterogeneity.notes.md`.

---

## Tree 7 — Local / focused regions

**Question:** one part of an otherwise good map needs sharpness or independent alignment.

**Red flags:**
- Local Refinement attempted on raw ab-initio poses (no gold-standard split, unstable).
- Local Refinement on a consensus volume when the question is class-specific.
- Local Refinement on a region that is moving continuously (hinge, breathing) — produces sharper-looking but biologically misleading maps.
- Iterating subtraction + local refinement to "rescue" a region that is actually compositionally absent in many particles.

**Branch rules:**

| Situation | Branch | Why |
|---|---|---|
| Bulk consensus solid, ROI rigidly offset, want sharper map | Local Refinement with static soft mask around ROI | Standard branch |
| ROI is compositionally heterogeneous (present vs absent) | 3D Classification with focus mask *first* | Identity before pose |
| ROI is continuously flexible | 3DVA cluster mode or 3DFlex first | Then optionally local refine the canonical state |
| ROI is too small to align alone | Symmetry expand + masked classification before forcing local refinement | More effective particles per ASU |
| Per-class question (apo vs liganded local view) | Local Refinement against the *class-specific* volume, not consensus | Avoid dragging minority-state poses |
| Want particle subtraction | Pair static soft mask over region to *subtract* with complementary kept-region mask; same box/pixel/origin | See `20_masks.md` |

**Advisor defaults:**
- Initial low-pass below ROI resolution, not at consensus global resolution.
- Search range deliberately small; Gaussian prior over pose/shift useful for small flexible ROIs.
- Do Global/Local CTF refinement and RBMC *upstream* of local refinement, so local sees corrected metadata.

**Cross-links:** `09_local_refinement.md`, `20_masks.md`, `08_classification_3d.md`.

---

## Tree 8 — Symmetry

**Question:** impose, stay C1, expand, or relax.

**Red flags:**
- Imposing icosahedral / octahedral / tetrahedral symmetry without external structural evidence.
- Imposing `Cn` and missing pseudosymmetry (one site differs; symmetry averages it away).
- Symmetry-expanded particles fed into a refinement that resplits half-sets silently.
- Wrong-`n` mistakes (C3 on C4, D2 on C2) presenting as ringing FSC or weak satellite densities.

**Branch rules:**

| Situation | Branch | Why |
|---|---|---|
| Known point group, consensus matches | Impose from ab initio through refinement | SNR per ASU rises ~`N` |
| High-symmetry target, ab initio returns flat disc in C1 | Raise minibatch, push max-res finer, rebalance views; impose only if disc persists with external evidence | Disc is usually pose-collapse, not symmetry signal |
| Suspected pseudosymmetry (symmetric shell + asymmetric cargo/ligand) | Stay C1 through consensus; address downstream with Hetero / classification / relaxation | Imposing symmetry early erases the biology |
| Symmetric consensus solid, want ASU detail | Symmetry expand → C1 Local Refine on ASU | More effective particles per ASU |
| Particles trapped in symmetry-related local minima | Symmetry relaxation + extra final passes | Forces evaluation of all symmetry-related poses |
| Continuous variation within symmetric assembly | Symmetry expand → 3DVA / 3DFlex on expanded stack | More signal per ASU |
| Helical assembly | Helical refinement / symmetry search; not point-group habits | Twist/rise parameter space |
| Different features support different symmetries | Make separate maps/refinements per symmetry regime | Do not force one symmetry everywhere |

**Advisor defaults:**
- Default to C1 at ab initio unless you have external evidence.
- Treat any imposed symmetry as a hypothesis to revisit at refinement.
- Use `Force re-do FSC split` only when symmetry-expanded stacks demand re-derivation.

**Cross-links:** `19_symmetry.md`, `08_classification_3d.md`, `07_refinement.md`.

---

## Tree 9 — Masks

**Question:** which mask, how soft, generated how.

**Red flags:**
- Hard-edged mask used in any refinement / FSC / classification / local refinement job (only 3DFlex mesh prep tolerates this).
- Final mask built directly from raw high-frequency map noise (no lowpass/blur first).
- Floating dust / islands remaining after dilation + soft padding.
- Mask, particles, half-maps not on the same box / pixel size / origin.
- Tight mask producing better FSC numbers while the map visibly degrades.

**Branch rules:**

| Goal | Mask type | Construction |
|---|---|---|
| Standard Homogeneous / NU refinement | Dynamic refinement + resolution masks (v5.0+) | Inspect both; default usually fine |
| Local refinement of subregion | Static soft generous mask around ROI | ChimeraX segmentation / volume eraser / `molmap` → Volume Tools |
| Particle subtraction | Static soft mask over region to *subtract* + complementary kept-region mask | Same session in ChimeraX |
| FSC / postprocess resolution | Generous, repeatable soft mask | Too tight inflates GSFSC |
| Classification focus / 3DVA / 3D Classification | Soft mask around varying region only | Too tight forces noise classes |
| 3DFlex mesh generation | Mask without soft edge OK | Do not generalize |
| Atomic model exists | Prefer `molmap` + `onGrid` mask base at ~12–20 Å (16 Å default) | Reproducible, scriptable |

**Advisor defaults:**
- Soft cosine edge minimum: `5 × resolution(Å) / apix(Å)` voxels.
- Dilation + soft padding are empirical; try a few; inspect in viewer.
- Always pass `onGrid` to ChimeraX `molmap` / `volume resample`.
- Inspect both refinement and resolution masks; high-frequency phase-randomization in the FSC plot is a tell for too-tight masks.

**Cross-links:** `20_masks.md`, `09_local_refinement.md`, `10_postprocessing.md`.

---

## Tree 10 — cryoSPARC Live

**Question:** Live session is misbehaving or a decision must be made during collection.

**Red flags:**
- Live "doesn't see exposures" — almost always file-discovery, not cryo-EM.
- Tight thresholds set early (NCC / power / edge distance) bias the session silently.
- Templates activated before verifying they represent multiple views.
- Treating Live's streaming refinement as a final result.

**Branch rules:**

| Symptom | Branch | Why |
|---|---|---|
| New exposures not detected | Check wildcard, recursion, file type (movie vs corrected), timestamps, symlinks, multi-session contention | File-discovery problem |
| Blob picks look noisy | Verify diameter range, contamination level; do not jump to templates yet | Picker calibration before triage |
| 2D classes good enough for templates | Generate templates from selected 2D, verify multiple views, then activate template picker | Template bias mitigation |
| Thresholds need tightening | Adjust NCC / power / edge distance; rely on selective reprocessing rather than restarting session | Live's strength is targeted re-runs |
| Throughput lagging | Increase preprocessing workers; rebalance GPU allocation | Lane/worker bottleneck |
| Ready for production | Export accepted exposures/particles → main project for NU / local / heterogeneity | Live is screening, not production |

**Advisor defaults:**
- Run motion + CTF in Live even if Live particle outputs will be discarded.
- Use denoised micrographs for picking only; extract from original micrographs.
- Keep one Live session per clean project (export/share/handoff is project-scoped).

**Cross-links:** `25_cryosparc_live.md`, `04_picking.md`, `03_preprocessing.md`.

---

## Tree 11 — Troubleshooting escalation

**Question:** something failed. What is the shortest useful path to the next action?

**Red flags before debugging the cryo-EM:**
- Job text contains `non-zero exit status 255` → SSH / shell / banner output → launch problem, not cryo-EM problem.
- `FAILED TO LAUNCH ON WORKER NODE` / `failed to connect link` → worker env / ports / hostname.
- `Job must be queued on the master node` → interactive job on wrong lane (Select 2D, Curate Exposures, interactive Volume Tools).
- `pymongo … ServerSelectionTimeoutError` / `database: ERROR (spawn error)` → Mongo / supervisor, not job-level.
- Cluster job "stuck" with no traceback → check SLURM/PBS OOM-kill before anything else.
- Master and worker see different paths under the same string → namespace/permission, not "file not found".

**Branch rules:**

| Bucket | First check | Then |
|---|---|---|
| Version-fixed bug (UI brittleness, plotting failures, older Live discovery bugs, v5.0 shell/launch fixes) | Compare instance version to known-fixed releases | Update before deep manual debugging |
| Worker / shell / SSH | `cryosparcm log command_core`; non-interactive `ssh worker "true"`; silence `.bashrc`/`.profile` | Re-run `cryosparcw connect`, re-run worker test |
| Filesystem / path / permission | Resolve the path from worker shell as the cryoSPARC owner; check symlinks and mount; check path-suffix-cut for Import Particle Stack | Fix mount/symlink/path before tuning parameters |
| GPU / CPU / RAM / scheduling | `nvidia-smi`, driver / CUDA compat, scheduler log for OOM | Reduce resource demand or fix env |
| Workflow misuse / mismatched inputs | Confirm input slots (volume vs map vs mask), pixel size / box / origin, exposure groups, alignments3D presence | Re-wire inputs; do not rerun unchanged |

**Shortest useful loop:**
1. Read the exact error / traceback (text, not screenshot).
2. Classify the failure bucket.
3. Check whether the version may already have fixed it.
4. Smallest safe corrective action (restart job → clear and rerun → restart cryoSPARC → reduce resources).
5. Escalate to environment / data-path debugging only if (4) fails.

**Advisor defaults:**
- Get exact error string + version + job type + non-default parameters before any deep suggestion.
- A pasted traceback beats a screenshot of red text.
- Do not rewrite refinement parameters to "work around" a launch / path / version failure.

**Cross-links:** `15_troubleshooting.md`, `17_error_lookup.md`, `16_tuning_recipes.md`.

---

## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

- `topic_plan.md`
- `17_error_lookup.md`
- `02_import.md`
- `03_preprocessing.md`
- `04_picking.md`
- `05_extraction_2d.md`
- `06_abinitio.md`
- `07_refinement.md`
- `08_classification_3d.md`
- `09_local_refinement.md`
- `10_postprocessing.md`
- `15_troubleshooting.md`
- `16_tuning_recipes.md`
- `19_symmetry.md`
- `20_masks.md`
- `25_cryosparc_live.md`
- `26_continuous_heterogeneity.md`
- `videos/notes/02_trpv1_and_a_standard_workflow.notes.md`
- `videos/notes/05_fanac1_and_discrete_heterogeneity.notes.md`
- `videos/notes/06_fanac1_and_continuous_heterogeneity.notes.md`
