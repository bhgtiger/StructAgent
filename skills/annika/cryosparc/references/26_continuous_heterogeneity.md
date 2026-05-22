# Topic 26 — Continuous Heterogeneity

## Scope
Continuous heterogeneity in cryoSPARC: when 3D Variability Analysis (3DVA) or 3D Flexible Refinement (3DFlex) is the right branch, what each method needs from upstream, how to read intermediate displays without overclaiming motion, and how to escalate or fall back when the assumption of continuity breaks. Discrete heterogeneity lives in `08_classification_3d.md`. Consensus refinement choices that feed both methods live in `07_refinement.md`. Local refinement of selected states lives in `09_local_refinement.md`. Symmetry strategy (expansion, relaxation, handedness) lives in `19_symmetry.md`. Mask construction discipline lives in `20_masks.md`. FSC reading and sharpening live in `10_postprocessing.md`. Branch-agnostic debugging mental model lives in `15_troubleshooting.md`.


## Decision surface — which continuous-heterogeneity job to use

| Job | Primary question | When it is the right call |
|---|---|---|
| **3D Variability Analysis (3DVA)** | What are the principal modes of the 3D covariance given fixed consensus poses? | Continuous motion is plausible; want interpretable axes plus optional cluster separation; also exposes discretizable heterogeneity through clear bimodal coordinates. |
| **3D Variability Display — simple** | What does each mode look like as a linear combination of consensus + scaled component? | Quick interpretation of one mode's geometry. Not particle-backed; samples coordinate axes directly even where particles are sparse. |
| **3D Variability Display — intermediates** | What do particle-backed reconstructions look like at sampled bins along one coordinate? | Want real reconstructions slice-by-slice along a coordinate; subsets can be exported for downstream refinement. |
| **3D Variability Display — cluster** | What discrete groupings exist in 3DVA latent space? | Two or more clusters visible in the coordinate scatter; want per-cluster particle subsets and reconstructions. |
| **3D Flexible Refinement (3DFlex)** | What is a nonlinear deformation model plus latent coordinate per particle, and a motion-corrected canonical map? | Continuous motion exceeds the linear regime; want sharper flexible regions; the motion model itself is biologically interesting. |
| **3D Classification** | What discrete states exist given fixed consensus poses? | Differences are present/absent or compositional (`08_classification_3d.md`). |
| **Heterogeneous Refinement** | Which of N initial volumes best matches each particle, with per-class pose updates? | Cleanup or state separation needing pose updates; pseudosymmetry rescue (`07_refinement.md`). |
| **Local Refinement** | Can one region be aligned independently for sharpness? | Identity is settled; the question is local pose refinement, not motion modeling (`09_local_refinement.md`). |

Practical rule: if **the motion is continuous and small-scale relative to the object**, 3DVA is usually enough and far cheaper. If **the motion is large, nonlinear, or you want a motion-corrected map**, 3DFlex is the right tool. If the question is "is this region present" or "which discrete state is this?", neither is the right branch.


## Prerequisites
Both 3DVA and 3DFlex amplify whatever is upstream; neither rescues an unstable consensus.

- **Clean particle stack.** Run 2D classification and at least one cleanup branch (Heterogeneous Refinement with junk volumes; Subset Particles by Statistic on per-particle scale) before either method. 3DFlex is especially intolerant of compositional contamination because it cannot create or delete density — it can only deform.
- **Trusted consensus poses.** 3DVA assumes alignments are fixed and "good enough that refinement against a consensus structure would not yield grossly incorrect alignments". 3DFlex requires consensus poses on the *same* particles used in Flex Data Prep. Use Align 3D Maps to bring multiple class refinements into a common frame before downstream continuous analysis.
- **Mask covering the full region expected to move.** For 3DVA, "if the mask doesn't cover regions in which the protein may actually move through, the 3D variability won't be able to detect flexibility in that area". For 3DFlex, the solvent mask defines the boundary of the tetrahedral mesh.
- **Preserved half-set splits.** 3D Flex Reconstruction depends on independent half-sets between training Nyquist and reconstruction Nyquist; from v4.5 refinements default to preserving the input split, which keeps RBMC → refinement → Flex loops honest.
- **Enough particles and SNR.** Higher latent-space dimensions and finer meshes both increase capacity; both increase overfitting risk if the dataset is too small or too noisy.
- **Symmetry decided.** 3DVA and 3DFlex should generally operate on symmetry-expanded particles when the motion of interest sits inside one asymmetric unit of a symmetric assembly; otherwise use C1 unless symmetry is biologically established (`19_symmetry.md`).


## 3DVA — practical workflow
3DVA solves K orthogonal principal modes (eigenvectors of the 3D covariance) on aligned particles, plus a per-particle "reaction coordinate" along each mode. Poses are not updated. The output linearizes motion as `V0 + Σ_i (z_i × V_i)`.

**Number of modes.** Default is 3. The algorithm orders modes by importance, so asking for more modes does not degrade the leading ones. Start at 2–3 to expose the dominant motion; increase to 4–6 only if unrelated motions are being forced into one mode.

**Filter resolution as motion-scale knob.** The filter resolution controls both noise suppression and the scale of motion the linear model can approximate. Heuristic from the tutorial and the FaNaC1 case study:

- Set filter resolution **lower than** the consensus global resolution (e.g., 5–6 Å for a 3 Å consensus).
- Match the filter resolution to the **size scale of the expected motion**: a single difference component can model motion of order ~1/filter-resolution. A 6 Å filter is appropriate when the moving region shifts ~5–7 Å; a 12 Å filter is appropriate for whole-domain swings.
- Try a few values (e.g., 4 / 8 / 12 Å) — 3DVA is sensitive enough that 0.5 Å changes can move features in and out of the model.

**High-pass resolution.** Membrane proteins and small particles often have low-frequency "structured noise" (pancaked particles, empty micelles) that dominates components. Setting a high-pass resolution (~20 Å typical) suppresses variability larger than that scale and forces 3DVA to focus on the molecule.

**Mask design.** Cover the full extent of expected motion, with a soft edge. For membrane proteins exclude the micelle unless modeling micelle dynamics is the goal — otherwise all modes report micelle motion. Mask construction defaults and pitfalls live in `20_masks.md`.

**When 3DVA reveals discretizable heterogeneity.** A bimodal coordinate scatter is a signal: the "continuous" basis vector has separated two discrete states. The dataset is then a candidate for cluster-mode reconstruction (below) followed by per-class refinement, or for Heterogeneous Refinement with identical starting volumes (`07_refinement.md`).


## 3D Variability Display — modes and hazards
3DVA Display consumes the 3DVA particles + volumes and produces interpretable outputs.

**Simple mode.** Linear "movie" of `consensus + z × V_i` at evenly-spaced positions along each component. Fast, no reconstruction. **Hazards**: appearing/disappearing density and exaggerated motion at the ends of the range are artifacts of the linear model — the coordinate may sample regions with very few particles. Use simple mode to *interpret* a component; do not build models against simple-mode frames without an independent reconstruction.

**Intermediates mode.** Sorts particles along one coordinate and reconstructs weighted subsets. Window > 0 = triangular weighting (overlapping bins); window = 0 = tophat (strict bins); window = -1 = equal-particle-count bins (variable bin widths). Particle subsets per intermediate frame can be exported (parameter `Intermediates: output particle subsets` plus a chosen component, available in v3.3+). **Hazard**: a particle's value on coordinate 1 says nothing about its value on coordinate 0; intermediates along a single coordinate can blur together particles that differ strongly along orthogonal modes.

**Cluster mode.** Fits a Gaussian Mixture Model in the full latent space and reconstructs each cluster. Outputs per-cluster particle subsets and volumes ready for downstream refinement. **Hazards**: clustering is unstable for genuinely continuous distributions (clusters may not be reproducible across runs); particle counts per cluster can be small enough that per-cluster reconstructions are noisier than the consensus.

For all modes, refine selected cluster/intermediate particle subsets against their *own* reconstructed volume (not the mixed consensus) before drawing conclusions — re-aligning a per-state subset to a consensus reference can pull it back toward the average and dilute the separation.


## 3DFlex — workflow
3DFlex models flexibility as deformations of a single canonical 3D density `V` driven by a latent coordinate `z` per particle; a flow generator network `f_θ(z) → u` outputs the flow field that deforms `V` into the convected map `W`. Five jobs:

1. **3D Flex Data Prep.** Crops and downsamples particles and the consensus; associates the prepared images with their full-resolution counterparts for later reconstruction. Box size for training must be ≤ 440 pixels. From v4.4, full-resolution CTF values (including higher-order aberrations) are computed on the fly downstream, not pre-stored.
2. **3D Flex Mesh Prep.** Generates the tetrahedral mesh from the consensus map plus a solvent mask. Either an automatic regular mesh (`Base num. tetra cells`, max 40 in current builds) or a custom segmented mesh.
3. **3D Flex Training.** Trains the flow generator and assigns each particle a latent coordinate. Key knobs: number of latent dims, hidden units, rigidity (lambda), noise-injection stdev, latent centering strength.
4. **3D Flex Generator.** Renders volume series from a trained model along chosen latent directions. Can apply the learned deformation to a higher-resolution map than was used in training. Useful for inspecting motion mid-training.
5. **3D Flex Reconstruction.** Half-set-aware reconstruction at full resolution using the trained deformation model. Outputs two half-maps for FSC validation and downstream sharpening. From v4.4 supports particle-on-SSD-cache and CTF aberrations; CPU RAM requirements at training time still scale with dataset size.

**Strengths.** Models nonlinear motion the 3DVA linear basis cannot represent; can sharpen flexible regions by combining signal across conformations; produces an interpretable canonical map plus a continuous latent landscape.

**GPU / RAM / runtime cautions.** GPU memory at reconstruction time must fit at least 2× a full-resolution volume; training time scales approximately linearly with both the number of latent dimensions and the number of voxels inside the solvent mask. Performance is more strongly GPU-bound than other cryoSPARC jobs.

**v4.1–v4.3 dependency note.** 3DFlex jobs in CryoSPARC v4.1–v4.3 require an extra `cryosparcw install-3dflex` step on each worker; dependencies are bundled automatically from v4.4 onward.


## Mesh design
The mesh is the regularizer: it forces deformations to be smooth on the scale of one tetrahedral cell, which is what prevents the flow generator from overfitting to image noise.

**Automatic vs custom.** The default mesh is a regular tetrahedral tiling. Tutorial recommendation: choose `Base num. tetra cells` so a tetra spans roughly one to two alpha helices. Defaults are sufficient for most single-body targets.

**Custom mesh.** Required when domains slip past each other or separate across a solvent gap — a single mesh penalizes that motion unrealistically. Custom meshes accept either a Segger `.seg` export or an `.mrc` segment-ID volume (one integer per voxel, `-1` for solvent). Segment fusions are encoded in the `Segment connections` parameter using `X>Y` (`X` is the root segment, `Y` is fused to it). Custom mesh authoring is its own deep skill — run 3DVA first to see what motions are actually present before designing topology.

**Density and rigidity weights.** 3D Flex Mesh Prep auto-generates per-cell rigidity weights from the density inside each cell so that empty space between subunits costs less to deform than core density. Rigidity weights can also be supplied via cryosparc-tools when needed. The training-time `Rigidity (lambda)` parameter scales the prior globally.

**Micelle / nanodisc caveats.** No universally best treatment. Options observed across tutorials and the case study:
- Fuse the micelle to the transmembrane domain and mark it rigid — risk: rigid vertices propagate through fused boundaries, freezing the transmembrane domain.
- Do not mark the micelle rigid — risk: latent capacity is spent modeling biologically uninteresting micelle motion.
- Mask the micelle out entirely — risk: real-space reconstruction artifacts where the mask cuts through density.
- Fuse the rigid micelle to a non-essential body (e.g., a Fab) — sometimes preserves channel motion better. Test multiple strategies.

**Always run 3DVA first when possible.** Mesh design is informed by knowing which motions exist; treating mesh prep as guesswork is one of the most common reasons 3DFlex underperforms.


## 3DFlex limitations
- **Compositional heterogeneity.** 3DFlex moves density; it cannot create or delete it. Partially occupied domains may be modeled by deformations that *expand* density over a wider region, lowering apparent occupancy — wasting capacity on a problem 3D Classification or Heterogeneous Refinement should handle upstream.
- **Intricate sidechain / loop motion.** Mesh granularity bounds the scale of resolvable motion; sidechain rearrangements are typically below that floor and below the per-particle signal level anyway.
- **Discrete states with no intermediate data.** If the data are bimodal, 3DFlex will still learn a deformation connecting the endpoints, but the intermediate states have no data evidence — the rigidity prior alone controls them, and they should not be interpreted as physically observed conformations.
- **Latent-space interpretation.** The latent space is nonlinear; relative distances and volumes carry no Boltzmann-like meaning, so particle density in latent space is not a free-energy surface. Do not over-interpret latent-coordinate histograms.


## Mask and symmetry interactions
- **Mask too tight** in 3DVA: components dominated by mask-edge ringing; motion you wanted to see lies just outside the mask. Mitigations in `20_masks.md` (dilate, soft-pad, blur the base before thresholding).
- **Mask too loose** in 3DVA: components dominated by micelle / glycan / background motion. Tighten or apply a high-pass resolution (~20 Å).
- **Symmetry.** Symmetry-expand before 3DVA / 3DFlex when the motion of interest is per-asymmetric-unit and the consensus was refined under symmetry. Do not run global refinements on expanded stacks before continuous analysis (`19_symmetry.md`).
- **Mask consistency.** Particles, consensus volume, and any mask must agree on box, pixel size, and origin. Mismatches are a silent failure mode for both 3DVA and 3DFlex.


## Validation and readout
- For 3DVA simple mode, confirm the interpretation against intermediate or cluster reconstructions before claiming the motion is real.
- For cluster outputs, refine each cluster against its own volume; report corrected FSC under a soft mask per `10_postprocessing.md`. Do not quote 3DVA Display's display-time resolution as the resolution of a state.
- For 3DFlex, the FSC of the two Reconstruction half-maps is the validation surface; pre/post sharpening comparisons against the consensus are how to claim a real local-resolution gain in flexible regions.
- Inspect the latent-space distribution: it should fill roughly ±1.5 in each dimension; particles pinned near 0 mean centering is too strong, particles piled at the edges mean centering is too weak.
- Inspect the Training / Validation loss curves: a gap between the "rigid" and "full" validation curves indicates the model is using flexibility productively; the curves on top of each other mean rigidity is too high.


## Common failure patterns
- **3DVA components show only structured noise.** Filter resolution too sharp, mask too loose, or particles too few. Lower filter resolution; tighten / re-center mask; high-pass at ~20 Å.
- **All clusters look identical.** Bimodality not real; or filter resolution too coarse to resolve the motion. Try a finer filter or revisit upstream cleanup.
- **`numpy.linalg.LinAlgError: Array must not contain infs or NaNs` in 3DVA.** Per-particle scale anomalies on input particles. Switching the per-particle scale source from `Input` to default `Optimal` resolves a known class of cases; alternatively try a different GPU (some reports trace to GPU-specific numerics). See `17_error_lookup.md`.
- **3DFlex latent space collapses to a point.** Centering strength too high — reduce until coordinates span ±1.5.
- **3DFlex latent space pegs at ±1.5.** Centering strength too low — particles clipping at the boundary; raise centering.
- **3DFlex Generator shows "jelly" motion of secondary structure.** Rigidity too low — secondary structure should not stretch. Raise `Rigidity (lambda)`.
- **3DFlex Generator shows essentially rigid motion despite multiple latent dimensions.** Rigidity too high, or the training mask is too tight to allow flexing. Lower rigidity; verify mask coverage.
- **Reconstruction FSC does not drop to zero at high resolution / shows artifacts.** Increase `Max BFGS iterations` (default 20 → 40); BFGS optimization had not converged.
- **OOM in 3D Flex Reconstruction at large box.** Turn off `Load all particles in RAM` (v4.4+) and let the job stream from SSD cache; reduce CPU RAM footprint substantially.


## Version-aware notes
- **v2.9 → v2.12**: 3DVA introduced; high-pass resolution parameter added; multi-component numerical instability ("streaking") improved; up to 12+ modes feasible.
- **v3.3**: 3D Variability Display intermediates mode gains particle-subset output via `Intermediates: output particle subsets` + chosen component.
- **v4.1**: 3DFlex (BETA) introduced; requires `cryosparcw install-3dflex` on each worker through v4.3.
- **v4.2**: fixed `numpy.linalg.LinAlgError` failure pattern in 3DVA at iteration 6 of 20 (a separate failure class; see also the per-particle-scale workaround above).
- **v4.4**: 3DFlex dependencies bundled; 3D Flex Reconstruction supports particles on SSD cache and CTF aberrations; CPU RAM requirements reduced substantially.
- **v4.5**: 3D Flex Generator latent-space plot colors by deformation magnitude; `Freeze latents during training` parameter for preserving 3DVA-style motions when seeding Flex from 3DVA latents.
- **v5.0**: dynamic refinement masking redesign affects mask discipline for upstream consensus; per-particle scale optimization on by default in refinements (useful upstream of 3DVA / 3DFlex).


## Advisor defaults
1. Confirm consensus poses are good and the question is "what is the motion?" — not "what discrete state is this?" (route to Topic 08) and not "is this region present?" (route to Topic 08 with a focus mask).
2. Run 3DVA first with 2–3 modes at a filter resolution matched to the expected motion scale; inspect simple-mode movies and coordinate scatters before reaching for 3DFlex.
3. Add a high-pass (~20 Å) when low-frequency structured noise (micelle, blob particles) dominates components.
4. Use 3D Variability Display cluster mode when scatter shows obvious clusters; intermediates mode when motion is genuinely continuous and you want particle-backed maps along one axis.
5. Refine cluster / intermediate subsets against their *own* reconstructed volume before drawing conclusions; do not re-align to the mixed consensus.
6. Reach for 3DFlex when motion is large or nonlinear, when you want a motion-corrected canonical map, or when 3DVA reveals motion that the linear model is clearly struggling with.
7. Clean compositional heterogeneity (3D Classification / Heterogeneous Refinement) *before* 3DFlex; 3DFlex cannot fix presence/absence.
8. Build the 3DFlex mesh from 3DVA-informed motion expectations; use the default regular mesh when possible, custom mesh only when domains slip past or separate from each other.
9. Treat micelle / nanodisc handling as a tuning surface: test rigid-fused, non-rigid, masked-out, and non-essential-fusion variants before settling on a final mesh.
10. Validate 3DFlex via half-map FSC from 3D Flex Reconstruction; treat latent-space density as exploratory, not thermodynamic.


## Cross-links
- `07_refinement.md` — consensus refinement that feeds both 3DVA and 3DFlex; Heterogeneous Refinement as the discrete-state alternative when pose updates per class are essential.
- `08_classification_3d.md` — discrete heterogeneity branch; what to use when the question is compositional rather than continuous.
- `09_local_refinement.md` — local refinement of selected continuous-heterogeneity subsets; refine cluster outputs here, not against the mixed consensus.
- `19_symmetry.md` — symmetry expansion before per-ASU continuous analysis; handedness flipping.
- `20_masks.md` — mask construction discipline (soft edge, threshold, dilation, noise-island prevention) for both 3DVA masks and 3DFlex solvent / segmentation masks.
- `10_postprocessing.md` — FSC reading, sharpening, and local resolution for per-state refinements and 3D Flex Reconstruction outputs.
- `15_troubleshooting.md` — branch-agnostic debugging mental model.


## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

- `docs/per_page/processing-data__all-job-types-in-cryosparc__variability.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__variability__job-3d-variability.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__variability__job-3d-variability-display.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__variability__job-3d-flexible-refinement-3dflex-beta.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-3d-variability-analysis-part-one.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-3d-variability-analysis-part-two.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-3d-flexible-refinement.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-3d-flexible-refinement__installing-3dflex-dependencies.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-3d-flex-mesh-preparation.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__case-study-discrete-and-continuous-heterogeneity-in-fanac1-empiar-11631-and-11632.md`
- `videos/notes/06_fanac1_and_continuous_heterogeneity.notes.md`
- `videos/notes/11_3dflex_custom_mesh_generation.notes.md`
- `docs/forum_threads/digests/forum_3d-var.md`
- `docs/forum_threads/digests/forum_3d-classification.md`
- `docs/forum_threads/digests/forum_3d-reconstruction.md`
- `docs/forum_threads/digests/forum_troubleshooting.md`
- `17_error_lookup.md`
- `07_refinement.md`
- `08_classification_3d.md`
- `09_local_refinement.md`
- `10_postprocessing.md`
- `15_troubleshooting.md`
- `19_symmetry.md`
- `20_masks.md`
- `reference/release_notes/markdown/v4.1.md`
- `reference/release_notes/markdown/v4.2.md`
- `reference/release_notes/markdown/v4.4.md`
- `reference/release_notes/markdown/v4.5.md`
- `reference/release_notes/markdown/v5.0.md`
