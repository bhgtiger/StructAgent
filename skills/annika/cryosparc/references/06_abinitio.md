# Topic 06 — Ab-Initio Reconstruction

## Scope
Producing the first 3D models from a 2D-curated particle stack: when to run Ab-Initio Reconstruction, how to set it up, how to interpret the resulting volumes, and which downstream branch to pick. Picking and 2D cleanup live in `04_picking.md` and `05_extraction_2d.md`. Homogeneous / NU / local refinement details belong in `07_refinement.md`. Discrete 3D Classification on a fixed consensus belongs in `08_classification_3d.md`. Continuous heterogeneity (3DVA / 3DFlex) is in `26_continuous_heterogeneity.md`.

## Decision surface — when to run Ab-Initio Reconstruction
Run Ab-Initio Reconstruction when:
- 2D cleanup looks coherent but you have no 3D reference, or
- the available reference is the wrong target, wrong scale, wrong hand, or so low-resolution that template-based refinement will mis-fit, or
- you want a reproducible junk-vs-signal sort in 3D before committing to a refinement branch.

Skip ab initio when:
- a trusted, scale-correct map of the same target already exists — go straight to Homogeneous or Non-Uniform Refinement.
- the target is large, well-characterized, and the deposited EMDB map is reliable (ribosome, viral capsid, apoferritin); a quick low-pass of the EMDB volume is often a better starting reference than a noisy fresh ab initio.
- the particles already have valid `alignments3D` and you only need a fresh reconstruction at a different box size, symmetry, or mask — use Homogeneous Reconstruction Only.

Prefer Heterogeneous Refinement (started from two or more existing volumes) over a fresh ab initio when:
- particles already cluster around one or more plausible 3D references and the question is class identity, not topology discovery.
- one ab initio class looks right but is still contaminated by junk that 2D could not catch.

Practical rule from the official workflow: a multi-class ab initio is most often used to generate 3D references, not to make final class assignments. Treat ab initio class membership as a draft; re-decide it with Heterogeneous Refinement.

## Standard post-2D workflow
A robust default after a clean Select 2D step:

1. Multi-class Ab-Initio Reconstruction (typically 3–6 classes) on the curated particle stack to expose junk and rough states.
2. Inspect the volume set: identify one or more credible volumes plus dedicated "junk" classes.
3. Use the credible volumes as inputs to Heterogeneous Refinement on the broader particle set (often including particles previously held back), with `force hard classification` when class collapse is likely.
4. Select the best class; route it to Homogeneous Refinement or Non-Uniform Refinement for the consensus map.
5. Re-extract particles at full pixel size (no Fourier crop) before the resolution starts to approach the cropped Nyquist; for typical projects this happens shortly after the first NU refinement.
6. Use Select Volume to automate "best volume out of several" choices in repeatable workflows.

When the consensus map looks plausible but you suspect a subtle global mis-alignment (small target, low SNR, recurring NU instability), Homogeneous Ab-Initio Refinement (BETA, v5.0+) is a fallback worth trying before deeper troubleshooting.

## Ab-Initio Reconstruction setup
The defaults are usable; the parameters below are the ones worth thinking about before queueing.

### Number of classes
- **One class:** quick way to make a single starting reference for downstream refinement. Ab-initio does not need every particle for a one-class reference; the job will subsample. Leave the particle count blank.
- **Two to four classes:** typical first multi-class run for junk-vs-signal sorting. Reserve one slot per expected state and one or two extra slots for junk.
- **Five to eight classes:** use when 2D shows clear multiple states or when junk fraction is high enough that you want more dedicated junk classes.
- **More than eight:** rarely productive in ab initio. If you need fine-grained class discovery, switch to Heterogeneous Refinement or 3D Classification.

### Number of particles
- Leave blank for the standard cases. The job auto-selects a subset for single-class runs and uses all particles for multi-class runs.
- Only set this when running multi-class ab initio on a very large stack purely to seed downstream Heterogeneous Refinement and you want a faster, cheaper job. If the classification itself will be used downstream, all particles are required.

### Maximum resolution / initial resolution
- Default resolution range is suitable for typical particles. Push the maximum resolution higher (lower numerical Å) for small membrane proteins and highly symmetric targets that look uninformative at very low resolution — see the disc-like-volume failure mode below.
- Pushing maximum resolution too high overfits because ab initio does not use half-sets.

### Initial / final minibatch size
- Larger minibatch sizes stabilize alignment for hard cases (small particles, low SNR, high symmetry); they cost GPU memory and time. Increasing both to roughly 1000 is a known recovery move for apoferritin-style C1 and icosahedral particles that otherwise produce squashed maps.
- Reduce only when you must fit a job onto a small GPU.

### Symmetry
- Default and almost always correct: **C1**.
- Impose a higher point group only when ab initio reproducibly returns flattened disc-like volumes and external information (XRD, prior EM, biochemistry) supports the symmetry.
- Symmetry imposed at ab initio is fast but inflexible; for pseudosymmetric targets (apparent C4 / D2 / icosahedral shell with a single internal ligand), keep C1 here and address symmetry later in refinement / 3D classification with symmetry relaxation.

### Class similarity
- Raising class similarity forces particles to populate multiple classes early. Useful when two states look very alike and the algorithm otherwise collapses them into a single class.
- The two `Class similarity anneal` controls govern when the algorithm releases this constraint.

### Volume window mode (v5.0+)
- Default spherical mask is correct for most globular targets.
- Cylindrical windowing helps helical targets.
- Disabling the volume window is occasionally appropriate when low-density symmetry-breaking features (e.g., a small ligand or floppy domain) would otherwise be discarded; see the encapsulated-ferritin case for a worked example.

### Multiple seeds
- Ab-initio uses stochastic gradient descent; reruns with different random seeds can converge to different volumes, especially for difficult particles.
- Run two or three independent ab initio jobs when:
  - the first map is borderline interpretable,
  - the dataset is small or noisy,
  - results are unusually sensitive to minibatch size or resolution.
- Compare the maps; if they are consistent at low resolution but differ in detail, feed all of them into Heterogeneous Refinement for a multi-reference cleanup.

## Class-count heuristics
- **One good + one or more junk:** the most common useful outcome for a real dataset. Forward the good class to refinement; route junk classes to the rejected bin.
- **All classes plausible but similar:** the dataset is mostly clean; convert the volumes into Heterogeneous Refinement seeds to get cleaner class assignments rather than trusting ab initio's posteriors.
- **All classes "good" but tiny:** class capacity is starving the alignment. Reduce class count and rerun.
- **Highly skewed occupancy with one dominant class:** sometimes correct (one real state + scatter into junk), sometimes a sign of orientation bias collapsing every particle into a single view. Inspect 2D / orientation diagnostics before trusting it.
- **More than half "junk-like":** picking or 2D cleanup are not yet good enough; do not push these volumes downstream.

Occupancy numbers from ab initio are not authoritative class fractions; treat them as a rough sort. The dependable occupancy comes from Heterogeneous Refinement or 3D Classification once particle assignments have been re-decided.

## Interpreting ab initio outputs
Good signs:
- visible secondary structure consistent with the particle size; helices/sheets emerging in at least one class.
- reasonable orientation distribution; no single view dominating.
- 2D reprojections (visualised via downstream refinement starts) match the curated 2D classes.

Suspicious signs:
- **Disc / "cake" / squashed shapes** — typical for highly symmetric particles or small membrane proteins when the algorithm cannot align them. Try larger minibatch, higher max-resolution, and (only with external support) imposed symmetry; if disc persists, revisit picking and 2D cleanup before forcing symmetry.
- **Streaky high-resolution detail** — overfitting; ab initio has no half-sets to regularize, so noise can be amplified. Lower the maximum resolution.
- **Strong preferred-view artifacts** (smearing along Z, elongated maps) — orientation bias from picking or 2D; reconstruct will not fix it. Rebalance 2D classes and reconsider picker choice.
- **Mirror or wrong-hand maps** — common for ab initio from 2D alone; project images do not pin down 3D chirality. Hand is decidable from atomic models or a reference; use Homogeneous Reconstruction Only with hand flipping (which also updates particle poses) instead of Volume Tools (which flips the volume only).
- **Pseudosymmetric blur** — symmetric-looking density with a weak, repeated bump at symmetry-related positions is a classic warning that the true biological state breaks the apparent symmetry. Do not lock symmetry in based on the ab initio map; address it later via C1 refinement or symmetry relaxation (see `19_symmetry.md`).

## Cleanup and rescue loops
- **Single good class:** forward the volume and its particles to Homogeneous or Non-Uniform Refinement. If the class is small but clean, consider routing the full curated particle set through Heterogeneous Refinement with the ab initio volume + one or more junk volumes to recover good particles ab initio sent to junk.
- **Two or three plausible volumes:** wire them all as initial models into Heterogeneous Refinement (`force hard classification` when collapse is likely). Use C1 unless symmetry is well-established.
- **All maps look like junk:** ab initio is not the right tool to fix this. Return to 2D classification, picking, or even denoiser / junk-detection steps. Iterating ab initio harder rarely rescues a bad input.
- **Reference exists from a related dataset:** use that volume as the input to Heterogeneous Refinement (mixed with one or two ab initio volumes) rather than re-running ab initio from scratch.
- **Cropped-stack ab initio worked, but resolution is plateauing near the cropped Nyquist:** re-extract particles at full size (or use the two-output extraction's full-size stack) before the next refinement.
- **Hand wrong:** flip via Homogeneous Reconstruction Only with `Flip handedness` so the particles' alignments are updated alongside the volume.

## Homogeneous Ab-Initio Refinement (BETA)
New in cryoSPARC v5.0. Uses the ab-initio SGD algorithm but splits particles into two independent half-sets, refines half-maps from scratch, and keeps them aligned during the run. Distinct from both standard Ab-Initio Reconstruction (no half-sets, multiple classes) and standard refinement (EM, requires a starting volume).

When to consider it:
- 2D classes look high-quality and clearly contain real signal, AND
- Homogeneous / Non-Uniform Refinement of the same particles still produces a map noticeably worse than the 2D classes suggest is possible.

When not to use it:
- as a default replacement for the normal refinement pipeline — it is much slower per iteration and produces a single homogeneous output, not classes.
- for routine cleanup or junk-vs-signal sorting — that is what regular Ab-Initio Reconstruction plus Heterogeneous Refinement are for.

Outputs are half-maps plus the corresponding particle set; downstream, use Local Refinement with "initialize from input half-maps" turned on, or Homogeneous Reconstruction Only to produce an averaged map.

## Failure patterns
- **All classes are junk-looking:** the input stack is not yet clean enough; do another 2D pass, revisit picker thresholds, or denoise before re-running ab initio.
- **One dominant class with anatomically wrong topology:** typical for highly symmetric particles in C1 with default minibatch. Increase minibatch (e.g., 1000 initial/final), keep C1, and only impose symmetry once a sphere-like map appears. For icosahedral / octahedral capsids, imposed symmetry is sometimes necessary to escape the squashed-disc attractor.
- **Multiple classes nearly identical:** ab initio cannot find heterogeneity; the discrimination is either continuous (move to 3DVA / 3DFlex) or sub-particle (use focus masks in 3D Classification or Local Refinement).
- **No high-resolution features anywhere:** check pixel size, box size, and whether 2D classes themselves showed secondary structure. Ab initio cannot conjure detail that 2D never showed.
- **OOM / GPU memory errors:** reduce minibatch, reduce class count, drop GPU count, or move to a higher-VRAM card. v4.1 reduced extraction GPU memory pressure; cuFFT-related OOM in newer versions almost always means batch size × box size is exceeding VRAM.
- **Wrong hand / pseudosymmetry / forced-symmetry artifacts:** ab initio cannot disambiguate hand on its own, and symmetry imposed too early bakes pseudosymmetric ambiguity into the reference. Default to C1 here; resolve symmetry questions in refinement / 3D classification.

## Version-aware highlights
- **v4.4**: Heterogeneous Reconstruction Only added (clean way to re-reconstruct per-class volumes from ab initio / heterogeneous outputs at a new box size or with a new mask).
- **v4.5**: Ab-Initio Reconstruction no longer fails when upstream particles already carry `alignments3D` and a number-of-particles cap is set; multi-volume outputs are now exposed as a "volumes group" output that can drive single-input downstream jobs (useful when feeding all ab initio volumes into Heterogeneous Refinement).
- **v5.0**: Homogeneous Ab-Initio Refinement (BETA) added; Ab-Initio Reconstruction adds spherical / none / cylindrical `Volume window mode` plus configurable inner/outer window diameters, and a new `Minimum alignment resolution` high-pass; NaN failures with near-empty class volumes fixed; Select Volume utility makes "pick the best ab initio map" automatable in workflow templates.

## Advisor defaults
When a user asks "what should I do for the first 3D model?":
1. Confirm the 2D classes show secondary structure and reasonable view coverage; if not, fix 2D before continuing.
2. Run an Ab-Initio Reconstruction with 3–4 classes, C1, defaults otherwise, on the curated particle stack.
3. Identify good vs junk classes by eye; do not trust class fractions yet.
4. Feed the good volume(s) plus one junk volume into Heterogeneous Refinement on a broader particle set with `force hard classification`.
5. Forward the surviving class into Non-Uniform Refinement for a consensus map.
6. Re-extract full-size before the FSC nears the cropped Nyquist.
7. Only impose symmetry once the C1 map clearly justifies it.

When a user asks "the ab initio map looks squashed":
- Check picking and 2D first; rerun ab initio with larger initial/final minibatch and higher maximum resolution; consider symmetry only after that.

When a user asks "should I use Homogeneous Ab-Initio Refinement?":
- Only after Homogeneous / NU Refinement underperforms 2D-implied quality on a stack with strong 2D classes.

## Cross-links
- `05_extraction_2d.md` — when to re-extract before the cropped Nyquist becomes limiting.
- `07_refinement.md` — Homogeneous / Non-Uniform / Local Refinement after ab initio.
- `08_classification_3d.md` — discrete heterogeneity from a fixed consensus.
- `19_symmetry.md` — when symmetry helps, when it harms, symmetry relaxation, hand flipping.
- `20_masks.md` — solvent vs focus masks; dynamic masking risks in refinement after ab initio.
- `15_troubleshooting.md` — recurring ab-initio failure strings and version-fixed bugs.
- `16_tuning_recipes.md` — parameter cookbooks for small / symmetric / membrane targets.
- `26_continuous_heterogeneity.md` — when continuous motion is the right interpretation rather than discrete classes.

## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-reconstruction__job-ab-initio-reconstruction.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-reconstruction__job-homogeneous-ab-initio-refinement-beta.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-refinement__job-heterogeneous-refinement.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-refinement__job-heterogeneous-reconstruction-only.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-refinement__job-homogeneous-refinement.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-refinement__job-homogeneous-reconstruction-only.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__utilities__job-select-volume.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__utilities__job-volume-alignment-tools.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__case-study-dktx-bound-trpv1-empiar-10059.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__case-study-pseudosymmetry-in-trpv5-and-calmodulin-empiar-10256.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__case-study-end-to-end-processing-of-encapsulated-ferritin-empiar-10716.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__case-study-discrete-and-continuous-heterogeneity-in-fanac1-empiar-11631-and-11632.md`
- `videos/notes/02_trpv1_and_a_standard_workflow.notes.md`
- `videos/notes/03_trpv5_and_symmetry_breaking.notes.md`
- `videos/notes/04_encapsulated_ferritin_and_non_point_group_symmetry.notes.md`
- `videos/notes/05_fanac1_and_discrete_heterogeneity.notes.md`
- `docs/forum_threads/digests/forum_3d-reconstruction.md`
- `docs/forum_threads/digests/forum_3d-classification.md`
- `reference/release_notes/markdown/v4.4.md`
- `reference/release_notes/markdown/v4.5.md`
- `reference/release_notes/markdown/v5.0.md`