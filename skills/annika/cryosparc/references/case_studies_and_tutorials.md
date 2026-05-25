# Official tutorials and case-study playbooks

Use this file when a user describes a dataset phenotype, symptom, official tutorial/case-study name, or EMPIAR example. This is a **scenario-to-strategy map**, not a reproduced walkthrough. Match the user problem to the closest pattern, then load only the detailed references listed in that card.

## How to use this file

- **Scenario map first:** use it when the user describes a dataset phenotype: pseudosymmetry, weak ligand density, flexible domain, low-population state, preferred orientation, membrane protein behavior, local refinement, or high/local symmetry.
- **Decision trees first:** use `18_decision_trees.md` when the user asks stage-specific “what next?” without a distinctive case-study phenotype.
- **Avoid overfitting:** cards transfer strategy; they are not exact EMPIAR recipes. Do not claim exact parameters unless they appear in the loaded detailed reference or current official guide.
- **Disambiguate:** if several cards match, choose the dominant phenotype first; mention complementary cards only when they change the next action.
- **Version-aware:** cards cover a corpus centered on cryoSPARC v4.0-v5.0. For version-gated features, check `version_caveats.md`.

## Scenario map

| User situation / phenotype | Primary case-study pattern | Complementary refs |
|---|---|---|
| Global pseudosymmetry or symmetry ambiguity | TRPV5/calmodulin; motor-bound nucleosome; encapsulated ferritin | `19_symmetry.md`, `08_classification_3d.md` |
| Low-population conformational state | motor-bound nucleosome; FaNaC1 | `08_classification_3d.md`, `26_continuous_heterogeneity.md` |
| Good global map but weak ligand/local pocket density | ligand-bound GPCR | `09_local_refinement.md`, `20_masks.md` |
| Flexible peripheral domain / blurred region | DkTx-bound TRPV1; inactive GPCR; motor-bound nucleosome | `09_local_refinement.md`, `26_continuous_heterogeneity.md` |
| Preferred orientation / anisotropic map | HA trimer orientation-bias case | `orientation_and_preferred_views.md` |
| Membrane protein cleanup and curation | membrane-protein tips; GPCR/TRPV examples | `16_tuning_recipes.md`, `ctf_refinement_and_rbmc.md` |
| Local/focused refinement question | tri-snRNP; TRPV1; GPCR; nucleosome | `09_local_refinement.md`, `20_masks.md` |
| High symmetry / local or non-point-group symmetry | encapsulated ferritin | `06_abinitio.md`, `19_symmetry.md` |
| Novice exploratory SPA workflow | Oliver Clarke exploratory processing | `00_overview.md`, `18_decision_trees.md` |
| Plot interpretation across jobs | Common CryoSPARC Plots | stage-specific refs; `orientation_and_preferred_views.md` |

## Case-study playbook cards

### Motor-bound nucleosome parts 1/2 — pseudosymmetry + low-population state separation
Official entries: **End-to-end processing of a motor-bound nucleosome part 1**; **Processing of a motor-bound nucleosome part 2**; EMPIAR-10739.
- **Trigger:** global pseudosymmetry, flexible region, minor conformational state, or classes that vanish in broad classification.
- **Strategy:** use exploratory 3DVA/classification to discover motions, then narrow classification/local refinement around the signal-bearing region.
- **First checks:** orientation distribution, class occupancy, whether masks isolate biology rather than noise, and whether alignment is dominated by pseudo-related features.
- **Sequence:** global baseline → 3DVA/exploratory classification → targeted class separation → focused/local refinement.
- **Avoid:** forcing a single global refinement to explain mixed states; over-trusting low-occupancy classes without reproducibility checks.
- **Load:** `26_continuous_heterogeneity.md`, `08_classification_3d.md`, `09_local_refinement.md`, `19_symmetry.md`.

### Ligand-bound GPCR — weak local ligand/pocket density
Official entry: **End-to-end processing of a ligand-bound GPCR**; EMPIAR-10853.
- **Trigger:** good global map but poor ligand, pocket, loop, or transducer density; membrane protein with local signal loss.
- **Strategy:** improve input curation, then use local/focused refinement and focused 3D classification around the ligand-bearing region.
- **First checks:** local mask coverage, orientation distribution, particle subset quality, local resolution, and whether sharpening/masking hides the ligand region.
- **Sequence:** preprocessing QC → particle curation/subset → global NU baseline → focused mask → local refinement/classification.
- **Version notes:** Micrograph Denoising, Micrograph Junk Detector, and subset-by-statistic behavior can be version dependent; check `version_caveats.md`.
- **Avoid:** treating weak ligand density as only a model-building problem or over-sharpening to “create” density.
- **Load:** `03_preprocessing.md`, `08_classification_3d.md`, `09_local_refinement.md`, `20_masks.md`.

### DkTx-bound TRPV1 — flexible/blurry domain diagnosis
Official entry: **DkTx-bound TRPV1**; EMPIAR-10059.
- **Trigger:** a domain or ligand-associated region is blurred while the core refines well.
- **Strategy:** separate particle-quality problems from real flexibility, then use focused/local refinement or classification to recover the moving region.
- **First checks:** 2D/3D particle quality, local resolution, mask boundary, class consistency, and whether the flexible domain contributes enough signal for alignment.
- **Sequence:** curate particles → global baseline → inspect local blur → focused/local refinement → classify if multiple states remain.
- **Avoid:** using an over-tight mask or expecting global alignment to resolve a mobile peripheral feature.
- **Load:** `05_extraction_2d.md`, `07_refinement.md`, `09_local_refinement.md`, `16_tuning_recipes.md`.

### TRPV5/calmodulin — pseudosymmetry and 3D Classification choices
Official entry: **Pseudosymmetry in TRPV5 and Calmodulin**; EMPIAR-10256.
- **Trigger:** pseudo-related subunits/domains confuse alignment or classification; symmetry appears plausible but biologically wrong.
- **Strategy:** lower symmetry assumptions, classify with masks that preserve the asymmetric signal, and validate whether classes reflect biology or alignment degeneracy.
- **First checks:** symmetry used in ab initio/refinement, asymmetric feature strength, class occupancy, and whether masks erase the symmetry-breaking element.
- **Sequence:** asymmetric/global baseline → pseudosymmetry-aware classification → inspect asymmetric density → refine selected states.
- **Avoid:** imposing point-group symmetry before proving the asymmetric feature is not biologically meaningful.
- **Load:** `19_symmetry.md`, `08_classification_3d.md`, `07_refinement.md`.

### Inactive GPCR — continuous heterogeneity and 3DFlex
Official entry: **End-to-end processing of an inactive GPCR**; EMPIAR-10668.
- **Trigger:** membrane protein with continuous conformational motion after reasonable global/local refinement.
- **Strategy:** use local refinement for stable regions, then 3DVA/3DFlex or classification to model continuous heterogeneity rather than forcing discrete classes.
- **First checks:** map quality after curation, whether motion is local vs global, particle count after filtering, and mask suitability for flexible regions.
- **Sequence:** global/local baseline → 3DVA → interpret motion → 3DFlex or focused classification/refinement.
- **Version notes:** 3DFlex availability/dependencies are version and install dependent; check `26_continuous_heterogeneity.md` and `version_caveats.md`.
- **Avoid:** interpreting every continuous motion as discrete states or running 3DFlex before the baseline refinement is stable.
- **Load:** `26_continuous_heterogeneity.md`, `09_local_refinement.md`, `08_classification_3d.md`.

### Encapsulated ferritin — high symmetry + local/non-point-group symmetry
Official entry: **End-to-end processing of encapsulated ferritin**; EMPIAR-10716.
- **Trigger:** high-symmetry particle with local symmetry, non-point-group relationships, or custom geometry operations.
- **Strategy:** build a robust high-symmetry global solution, then treat local symmetry/non-point-group components separately with symmetry expansion or geometry operations.
- **First checks:** whether imposed symmetry matches biology, whether local regions obey different symmetry, and whether masks isolate repeated local units.
- **Sequence:** symmetry-aware ab initio/global refinement → local symmetry analysis → symmetry expansion/custom operations → local refinement.
- **Avoid:** applying one global symmetry assumption to all components when local arrangements differ.
- **Load:** `06_abinitio.md`, `19_symmetry.md`, `09_local_refinement.md`.

### FaNaC1 — discrete + continuous heterogeneity in a mixed dataset
Official entry: **Discrete and Continuous Heterogeneity in FaNaC1**; EMPIAR-11631/11632.
- **Trigger:** combined/heterogeneous ion-channel dataset with both compositional/discrete states and continuous motion.
- **Strategy:** separate coarse discrete states first, then analyze residual continuous heterogeneity within cleaner subsets.
- **First checks:** dataset provenance, particle-set compatibility, class occupancy, whether heterogeneity is compositional vs conformational, and whether combining datasets introduces batch effects.
- **Sequence:** particle curation/merge checks → 3D classification → state-specific refinement → 3DVA/3DFlex on selected states.
- **Avoid:** running continuous-heterogeneity tools on a mixture dominated by discrete/compositional differences.
- **Load:** `08_classification_3d.md`, `26_continuous_heterogeneity.md`, `particle_set_operations.md`.

### HA trimer — picking-induced orientation bias
Official entry: **Picking-induced Orientation Bias in HA Trimer**; EMPIAR-10096/10097.
- **Trigger:** streaky/anisotropic map, missing views, strong side/top-view imbalance, or picking method suspected of orientation bias.
- **Strategy:** diagnose orientation distribution early, compare picking/curation routes, and rebalance or recollect rather than relying on sharpening.
- **First checks:** viewing-direction plots, 3DFSC/isotropy diagnostics, 2D class view distribution, and whether picking preferentially selects one orientation.
- **Sequence:** inspect orientation plots → compare picker/curation outputs → rebalance/subset if appropriate → refine and validate anisotropy.
- **Version notes:** Orientation Diagnostics and BILD visualization behavior can vary; check `orientation_and_preferred_views.md` and `version_caveats.md`.
- **Avoid:** mistaking anisotropic artifacts for real structural features.
- **Load:** `orientation_and_preferred_views.md`, `04_picking.md`, `05_extraction_2d.md`, `10_postprocessing.md`.

### Yeast U4/U6.U5 tri-snRNP — local refinement of a large flexible complex
Official entry: **Yeast U4/U6.U5 tri-snRNP**; EMPIAR-10073.
- **Trigger:** large assembly where a region is locally resolvable but diluted by global flexibility.
- **Strategy:** use focused masks/local refinement to improve a region after establishing a credible global alignment.
- **First checks:** mask placement/soft edge, particle count, local resolution, and whether the local region has enough signal for alignment.
- **Sequence:** global baseline → focused mask design → local refinement → validate FSC/local resolution and map interpretability.
- **Avoid:** refining a tiny/noisy mask without enough signal, or overinterpreting local FSC gains.
- **Load:** `09_local_refinement.md`, `20_masks.md`, `10_postprocessing.md`.

### Oliver Clarke exploratory processing — novice/try-it-and-see SPA workflow
Official entry: **Exploratory data processing by Oliver Clarke**.
- **Trigger:** user wants a practical beginner workflow or exploratory route rather than a heavily optimized protocol.
- **Strategy:** encourage small, interpretable branches; compare outputs; keep provenance; make decisions from plots/classes/maps rather than one “perfect” path.
- **First checks:** data import correctness, exposure QC, particle picking sanity, 2D class quality, and whether enough particles remain after curation.
- **Sequence:** import/QC → picking trials → extraction/2D → ab initio → refinement → iterate from observed failure modes.
- **Avoid:** premature fine-tuning before basic QC and 2D/ab initio sanity checks.
- **Load:** `00_overview.md`, `18_decision_trees.md`, then route by stage.

### Membrane protein structures — curation and local-signal pragmatics
Official entry: **Tips for Membrane Protein Structures**.
- **Trigger:** membrane protein with low contrast, micelle/nanodisc issues, weak peripheral density, or difficult particle picking/curation.
- **Strategy:** prioritize careful preprocessing/curation and local masks; use membrane-protein examples as heuristics, not universal settings.
- **First checks:** ice/motion/CTF quality, junk particles, micelle/nanodisc signal, orientation distribution, and local mask behavior.
- **Sequence:** exposure/particle QC → picker/curation refinement → global baseline → local/focused refinement if needed.
- **Avoid:** assuming all membrane-protein failures are heterogeneity; many are curation, contrast, or orientation problems.
- **Load:** `16_tuning_recipes.md`, `03_preprocessing.md`, `04_picking.md`, `20_masks.md`, `ctf_refinement_and_rbmc.md`.

### Common CryoSPARC Plots — diagnostic reference, not a workflow
Official entry: **Common CryoSPARC Plots**.
- **Trigger:** user asks what a plot means, or a job “looks bad” based on FSC, orientation, CTF, 2D, or refinement plots.
- **Strategy:** identify the job type and plot first; interpret the plot as a diagnostic, then route to the stage-specific reference.
- **First checks:** exact job type, plot name/screenshot, axes/units, warnings, and whether the plot reflects input quality, alignment, masking, or validation.
- **Avoid:** making workflow decisions from a single plot without checking upstream context.
- **Load:** stage-specific refs; commonly `03_preprocessing.md`, `05_extraction_2d.md`, `07_refinement.md`, `10_postprocessing.md`, `orientation_and_preferred_views.md`.

## Data-processing tutorial pointers

| Official tutorial | Use when | Load |
|---|---|---|
| Tutorial: Negative Stain Data | negative-stain import/preprocessing differs from standard cryo-EM SPA | `02_import.md`, `03_preprocessing.md` |
| Tutorial: Phase Plate Data | phase-plate data or CTF interpretation needs special care | `02_import.md`, `03_preprocessing.md`, `ctf_refinement_and_rbmc.md` |
| Tutorial: EER File Support | importing/processing EER movies | `02_import.md`, `03_preprocessing.md`, `version_caveats.md` |
| Tutorial: EPU AFIS Beam Shift Import | EPU AFIS / beam-shift metadata import | `02_import.md`, `ctf_refinement_and_rbmc.md`, `27_relion_interop.md` |
| Tutorial: Patch Motion and Patch CTF | basic motion/CTF preprocessing | `03_preprocessing.md`, `ctf_refinement_and_rbmc.md` |
| Tutorial: Float16 Support | Float16 storage/performance questions | `03_preprocessing.md`, `24_disk_and_storage.md`, `version_caveats.md` |
| Tutorial: Particle Picking Calibration | picking thresholds/calibration are the main issue | `04_picking.md`, `16_tuning_recipes.md` |
| Tutorial: Blob Picker Tuner | blob picking needs systematic tuning | `04_picking.md`, `16_tuning_recipes.md` |
| Tutorial: Helical Processing using EMPIAR-10031 (MAVS) | helical reconstruction/filament processing | `11_helical.md`, `19_symmetry.md` |
| Tutorial: Maximum Box Sizes for Refinement | box size, memory, speed, or refinement limits | `05_extraction_2d.md`, `07_refinement.md`, `21_gpu_lane_queue.md` |
| Tutorial: CTF Refinement | local/global CTF refinement strategy | `ctf_refinement_and_rbmc.md`, `07_refinement.md` |
| Tutorial: Ewald Sphere Correction | high-resolution Ewald correction question | `ctf_refinement_and_rbmc.md`, `07_refinement.md` |
| Tutorial: Symmetry Relaxation | relaxing or validating imposed symmetry | `19_symmetry.md`, `07_refinement.md` |
| Tutorial: Orientation Diagnostics | preferred-orientation diagnosis | `orientation_and_preferred_views.md`, `10_postprocessing.md` |
| Tutorial: BILD files | visualizing orientations/directions with BILD | `orientation_and_preferred_views.md`, `version_caveats.md` |
| Tutorial: Mask Creation | local/focused refinement masks, including ChimeraX mask generation | `20_masks.md`, `09_local_refinement.md` |
| Tutorial: 3D Classification | discrete heterogeneity/class separation | `08_classification_3d.md`, `16_tuning_recipes.md` |
| Tutorial: 3D Variability Analysis (Part One) | first-pass 3DVA / continuous motion discovery | `26_continuous_heterogeneity.md`, `08_classification_3d.md` |
| Tutorial: 3D Variability Analysis (Part Two) | follow-up 3DVA interpretation/use | `26_continuous_heterogeneity.md`, `08_classification_3d.md` |
| Tutorial: 3D Flexible Refinement | 3DFlex refinement setup/interpretation | `26_continuous_heterogeneity.md`, `09_local_refinement.md` |
| Tutorial: 3D Flex Mesh Preparation | custom mesh preparation for 3DFlex | `26_continuous_heterogeneity.md` |

## Worked routing examples

- **“My GPCR map is decent globally, but the ligand pocket is weak.”** → Start with **Ligand-bound GPCR**, then load `09_local_refinement.md` + `20_masks.md`; add `08_classification_3d.md` if focused classification is needed.
- **“The map is streaky and mostly side views after picking.”** → Start with **HA trimer orientation bias**, then load `orientation_and_preferred_views.md` + `04_picking.md`.
- **“My complex has pseudo-symmetry and classes look mixed.”** → Start with **TRPV5/calmodulin** or **motor-bound nucleosome** depending on whether the issue is symmetry breaking or low-population state separation; load `19_symmetry.md` + `08_classification_3d.md`.
- **“Large complex, one region improves with a focused mask.”** → Start with **tri-snRNP**; load `09_local_refinement.md` + `20_masks.md`.
