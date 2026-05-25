# Topic 28 — SPA Playbook / Phenotype Router

## Scope and guardrails

This file is a **planning router and per-job checklist**, not an executor. It is the entry point for **broad** SPA workflow requests ("run cryoSPARC", "process this dataset", "what workflow/protocol should I use", "match my dataset to a case study"). It does **not** replace the per-stage references, the decision trees in `18_decision_trees.md`, or the scenario cards in `case_studies_and_tutorials.md` — it points at them.

- Do not run, queue, start, restart, or delete cryoSPARC jobs based on anything in this file. Job execution must follow the safety rules in `SKILL.md` (confirm `project_uid`, `workspace_uid`, lane, dry-run vs queue).
- Case studies are **curated successes on well-behaved datasets**; do not force-fit a messy dataset into the closest playbook. If no phenotype clearly matches, use the escape hatch at the bottom of this file.
- For exact parameter values, defer to the relevant per-stage reference. Parameter defaults drift across CryoSPARC versions (v4.0–v5.0 corpus window); see `version_caveats.md`.
- For specific phrases that already have dedicated routing in `SKILL.md` (preferred orientation, masks, local refinement, continuous heterogeneity / 3DVA / 3DFlex, exact error strings, `cryosparc-tools` / `cryosparcm` automation, RELION interop, particle set operations, helical, Live), route directly to that file. This playbook is for the general "I have a dataset, what do I do" case.

## §1 Trigger map

| User phrase pattern | Load order |
|---|---|
| "run cryoSPARC", "process this dataset", "what's the workflow", "from scratch", "end-to-end" | this file → `00_overview.md` → §2 stage spine refs as needed |
| "what protocol/pipeline should I use for X" with no concrete error/phenotype yet | this file (§5 playbooks) → `case_studies_and_tutorials.md` → loaded playbook's listed refs |
| "my data looks like / I have a [GPCR / TRPV1 / nucleosome / ferritin / HA trimer / tri-snRNP / FaNaC1 / membrane protein / negative stain / phase plate / EER / EPU AFIS]" | `case_studies_and_tutorials.md` (jump straight to that card) → its listed refs |
| "what next?" stage-specific, no case-study phenotype | `18_decision_trees.md` → relevant stage ref |
| "preferred orientation", "anisotropic map", "missing views" | `orientation_and_preferred_views.md` + `04_picking.md` (specific routing — bypass this file) |
| "mask", "molmap", "particle subtraction mask", "ChimeraX mask" | `20_masks.md` + `20a_mask_generation_chimerax.md` (specific routing — bypass this file) |
| "local refinement", "focused refinement" | `09_local_refinement.md` + `20_masks.md` (specific routing — bypass this file) |
| "3DVA", "3DFlex", "continuous heterogeneity" | `26_continuous_heterogeneity.md` (specific routing — bypass this file) |
| Exact error text / traceback | `17_error_lookup.md` + `15_troubleshooting.md` (specific routing — bypass this file) |
| `cryosparc-tools` / `cryosparcm` / API / scripting | `13_cryosparc_tools_api.md` + `ui_to_api_crosswalk.md` (specific routing — bypass this file) |
| "during collection" / Live session question | `25_cryosparc_live.md` (specific routing — bypass this file) |
| Helical / filament / amyloid | `11_helical.md` (specific routing — bypass this file) |

## §2 Stage spine

One-line flow. Every stage links to the reference that owns its mechanics.

Import (`02_import.md`) → Patch Motion + Patch CTF + curation (`03_preprocessing.md`) → Picking (`04_picking.md`) → Extraction + 2D classification (`05_extraction_2d.md`) → Ab initio (`06_abinitio.md`) → Heterogeneous / Homogeneous / NU refinement (`07_refinement.md`) → Optional: discrete heterogeneity (`08_classification_3d.md`), continuous heterogeneity (`26_continuous_heterogeneity.md`), CTF refinement / RBMC (`ctf_refinement_and_rbmc.md`), local refinement (`09_local_refinement.md`) → Postprocess / FSC / sharpening / local resolution (`10_postprocessing.md`) → Export / handoff (`24_disk_and_storage.md`, `27_relion_interop.md`).

Cross-cutting: symmetry choices (`19_symmetry.md`), masks (`20_masks.md`, `20a_mask_generation_chimerax.md`), preferred orientation (`orientation_and_preferred_views.md`), particle-set bookkeeping (`particle_set_operations.md`), tuning ranges (`16_tuning_recipes.md`), version-gated behavior (`version_caveats.md`).

## §3 Decision gates

Each gate: signal that fires the gate / branch to take / reference that owns the mechanics. Defer ordering and parameter ranges to the referenced files; this is a router, not a recipe.

**Gate A — Import / metadata trust**
- Signal: pixel size, voltage, Cs, dose, gain orientation, or beam-shift groups not confirmed; worker cannot see the path that master sees.
- Branch: stop, fix metadata or mount, re-run Patch CTF on a small subset before committing.
- Ref: `02_import.md`, `03_preprocessing.md`, Tree 1 in `18_decision_trees.md`.

**Gate B — Picking quality**
- Signal: 2D shows few dominant views, picks look biased, low-contrast / small / heterogeneous particle, or no usable reference yet.
- Branch: choose Blob → Blob Tuner → Template (from diverse 2D) → Topaz progression; consider Filament Tracer for filaments; route preferred-orientation cases out to `orientation_and_preferred_views.md`.
- Ref: `04_picking.md`, Tree 2 in `18_decision_trees.md`.

**Gate C — 2D vs back-to-picking**
- Signal: 2D classes look particle-like but biased, box size below ~1.5–2× particle, classes split by view rather than identity.
- Branch: re-pick with diverse templates / Topaz before moving to 3D; re-extract at a larger or non-cropped box if approaching Nyquist later.
- Ref: `05_extraction_2d.md`, Tree 2 in `18_decision_trees.md`.

**Gate D — Ab initio strategy**
- Signal: no trusted reference vs trusted reference; symmetry suspected vs unknown; expected junk fraction.
- Branch: multi-class ab initio (one good + 1–2 junk) → Heterogeneous Refinement cleanup; or Homogeneous Reconstruction Only when `alignments3D` already valid.
- Ref: `06_abinitio.md`, `19_symmetry.md`, Tree 3 in `18_decision_trees.md`.

**Gate E — Refinement choice**
- Signal: membrane protein / micelle / small disordered target vs rigid soluble complex; consensus stable vs not.
- Branch: Homogeneous → NU comparison (corrected FSC + features, not unmasked number); rescue via Homogeneous Ab-Initio Refinement when 2D is good but Homogeneous/NU underperform.
- Ref: `07_refinement.md`, Tree 3 / Tree 4 in `18_decision_trees.md`.

**Gate F — Resolution stall**
- Signal: corrected FSC near cropped Nyquist; tight/loose FSC delta large; cFSC anisotropic; ROI blurred; per-particle scale histogram tails empty.
- Branch: re-extract full-size, regenerate looser mask, test C1 if symmetry imposed, classify or local-refine the ROI, subset by statistic, or run CTF refinement + RBMC after consensus is solid.
- Ref: `07_refinement.md`, `10_postprocessing.md`, `20_masks.md`, `ctf_refinement_and_rbmc.md`, Tree 4 in `18_decision_trees.md`.

**Gate G — Heterogeneity type**
- Signal: blurred region (where), compositional vs conformational, discrete vs continuous, sample-identity vs intra-particle.
- Branch: Heterogeneous Refinement for sample-identity / junk cleanup; 3D Classification for discrete compositional/conformational; 3DVA for small continuous motion; 3DFlex for large continuous motion (only on a clean stack).
- Ref: `08_classification_3d.md`, `26_continuous_heterogeneity.md`, Tree 6 in `18_decision_trees.md`.

**Gate H — Local vs global**
- Signal: bulk consensus solid but one ROI under-resolved; ROI rigid vs flexible vs compositional.
- Branch: Local Refinement with static soft mask once consensus is good; classify / 3DVA first if ROI varies in identity or moves continuously; symmetry-expand if ROI is too small to align alone.
- Ref: `09_local_refinement.md`, `20_masks.md`, Tree 7 in `18_decision_trees.md`.

**Gate I — Symmetry call**
- Signal: known point group with external evidence vs suspected pseudosymmetry vs ab initio "disc" in C1 vs symmetric shell with asymmetric cargo.
- Branch: impose only with external evidence; otherwise C1 through consensus, then symmetry-expand or relax downstream.
- Ref: `19_symmetry.md`, Tree 8 in `18_decision_trees.md`.

**Gate J — Failure escalation**
- Signal: launch / worker / path / Mongo / scheduler error, or job stuck with no traceback.
- Branch: classify by error bucket, check whether the version already fixed it, then take the smallest corrective action.
- Ref: `15_troubleshooting.md`, `17_error_lookup.md`, `version_caveats.md`, Tree 11 in `18_decision_trees.md`.

## §4 Phenotype playbooks

Each row is a pointer into `case_studies_and_tutorials.md`. Use the dataset signature to disambiguate; if signature is fuzzy, fall back to §3 + `18_decision_trees.md`. Do not restate the case-study card here.

| Case-study card | Dataset signature (sharpen the match) | Dominant branch | Card lives in |
|---|---|---|---|
| Motor-bound nucleosome part 1 / 2 | Pseudosymmetric assembly + low-population conformational state; classes vanish in broad classification | Global → exploratory 3DVA/classification → targeted class separation → local refine | `case_studies_and_tutorials.md` |
| Ligand-bound GPCR | Good global map, weak ligand / pocket / loop / transducer density; membrane protein with local signal loss | Curation → NU baseline → focused mask → local refine + focused classification | `case_studies_and_tutorials.md` |
| DkTx-bound TRPV1 | One peripheral domain/ligand region blurred while core refines well | Curate → baseline → inspect local blur → local refine → classify if multistate | `case_studies_and_tutorials.md` |
| TRPV5/calmodulin | Pseudo-related subunits/domains; symmetry plausible but biologically wrong | Asymmetric baseline → pseudosymmetry-aware classification → refine selected states | `case_studies_and_tutorials.md` |
| Inactive GPCR | Membrane protein with continuous conformational motion after reasonable global/local refinement | Global/local baseline → 3DVA → interpret motion → 3DFlex or focused classification | `case_studies_and_tutorials.md` |
| Encapsulated ferritin | High-symmetry particle with local symmetry / non-point-group relationships | Symmetry-aware ab initio → local symmetry analysis → symmetry expansion → local refine | `case_studies_and_tutorials.md` |
| FaNaC1 | Mixed dataset with both compositional/discrete states **and** continuous motion | Curation/merge checks → 3D classification → state-specific refinement → 3DVA/3DFlex on selected states | `case_studies_and_tutorials.md` |
| HA trimer | Streaky/anisotropic map, missing views, picking suspected of orientation bias | Orientation plots → compare pickers → rebalance/subset → refine and validate | `case_studies_and_tutorials.md` |
| Yeast U4/U6.U5 tri-snRNP | Large assembly, one region locally resolvable but diluted by global flexibility | Global baseline → focused mask → local refinement → validate FSC / local resolution | `case_studies_and_tutorials.md` |
| Oliver Clarke exploratory | Novice / exploratory route, no fixed protocol | Import/QC → picking trials → 2D → ab initio → refinement, iterate from observed failure modes | `case_studies_and_tutorials.md` |
| Membrane protein tips | Low contrast, micelle/nanodisc issues, weak peripheral density, hard picking | Preprocess/curation → picker/curation refinement → global baseline → local refine if needed | `case_studies_and_tutorials.md` |
| Common CryoSPARC Plots | "What does this plot mean?" / "this looks bad" | Identify job + plot → diagnose → route to stage ref | `case_studies_and_tutorials.md` |

Tutorial pointers (negative stain, phase plate, EER, EPU AFIS, Patch Motion/CTF, Float16, picking calibration, Blob Tuner, helical MAVS, max box, CTF Refinement, Ewald, symmetry relaxation, orientation diagnostics, BILD, mask creation, 3D Classification, 3DVA parts 1/2, 3DFlex, 3DFlex mesh) live in the same file under "Data-processing tutorial pointers".

## §5 Per-job checklist

Inspect → continue if → branch if. Job-type-keyed; one block per job type. Mechanics live in the referenced stage file.

**Patch Motion + Patch CTF (pilot)**
- Inspect: motion traces, defocus map, ice/contamination thumbnails, CTF fit resolution, gain orientation.
- Continue if: motion plausible, CTF fit resolution consistent across subset, defocus map looks sane, no obvious gain artifact.
- Branch if: weird defocus map → re-check pixel size / voltage / Cs / dose (`02_import.md`); Y-flip suspected on TIFF imports from external packages (`02_import.md`); see Tree 1 in `18_decision_trees.md`.

**Exposure curation**
- Inspect: motion, CTF fit, ice / junk thumbnails, early particle counts (in that order).
- Continue if: distributions clean, no single failure mode dominating.
- Branch if: large fraction at the tail → tighten thresholds; persistent stragglers → fix upstream (gain, mount, beam-shift groups) before tightening further (`03_preprocessing.md`).

**Blob / Template / Topaz picking**
- Inspect: pick overlay on raw + denoised micrographs, picks-per-micrograph histogram, NCC / power distributions.
- Continue if: picks track real particles, distribution unimodal-ish, no obvious carbon / ice / aggregate bias.
- Branch if: under-picked low-contrast → Topaz on a clean seed; over-picked junk → tighten Blob Tuner; biased by template → regenerate templates from diverse 2D (`04_picking.md`, `orientation_and_preferred_views.md` if anisotropy suspected).

**Extract + 2D classification**
- Inspect: 2D classes (view diversity, junk vs signal), class occupancy, box vs particle dimensions.
- Continue if: multiple distinguishable views, classes coherent at expected resolution.
- Branch if: only side / only top views → back to picking + curation, not to 3D; sub-Nyquist box → re-extract larger or uncropped (`05_extraction_2d.md`, Tree 2 in `18_decision_trees.md`).

**Ab initio (multi-class)**
- Inspect: per-class volumes (one good + 1–2 junk slots), class occupancy, residual junk in "good" class.
- Continue if: at least one class shows recognizable particle features, junk pulled into separate classes.
- Branch if: all classes are junk-mixed → revisit picking / 2D; symmetric target returns flat "disc" → raise minibatch / push max-res / rebalance views before imposing symmetry (`06_abinitio.md`, Tree 3 / Tree 8 in `18_decision_trees.md`).

**Heterogeneous Refinement (cleanup or compositional)**
- Inspect: per-class volumes, occupancy, whether minority classes look biological or noise.
- Continue if: cleanup separated junk; compositional split shows the expected presence/absence.
- Branch if: apo class still has residual ligand-like density → suspect consensus pose bias, rerun with two identical starting volumes (`08_classification_3d.md`, Tree 6 in `18_decision_trees.md`).

**Homogeneous / NU Refinement (consensus)**
- Inspect: corrected FSC, unsharpened map, viewing-direction plot, cFSC (v4.5+), per-particle scale histogram.
- Continue if: corrected FSC ahead of cropped Nyquist, cFSC roughly isotropic, features improving with resolution number.
- Branch if: corrected FSC ≈ Nyquist → re-extract full-size; cFSC anisotropic → orientation diagnostics (`orientation_and_preferred_views.md`); ROI blurred → local refine; symmetry suspected → C1 test refine (`07_refinement.md`, Tree 4 in `18_decision_trees.md`).

**3D Classification (discrete heterogeneity)**
- Inspect: per-class volumes (not weighted blends), per-class FSC, occupancy, focus-mask placement.
- Continue if: classes split by identity / state, not by pose or noise.
- Branch if: tight focus mask on a region coupled to a larger moving domain → loosen / solvent-only mask; consensus poses untrustworthy → fix consensus first (`08_classification_3d.md`, Tree 6 in `18_decision_trees.md`).

**Local Refinement**
- Inspect: ROI mask placement / soft edge, ROI FSC, ROI local resolution, alignment stability.
- Continue if: ROI density sharpens without bulk-map dragging, consensus was already solid.
- Branch if: ROI is compositionally heterogeneous → 3D Classification with focus mask first; ROI moves continuously → 3DVA / 3DFlex first; ROI too small to align → symmetry-expand + masked classification before forcing local refine (`09_local_refinement.md`, Tree 7 in `18_decision_trees.md`).

**3DVA / 3DFlex**
- Inspect: per-component frames, scatter plots / clusters, mask coverage, mesh / rigidity (3DFlex), input stack cleanliness.
- Continue if: motion is interpretable and confined to the masked region; for 3DFlex, mesh is stable and stack is clean.
- Branch if: 3DVA scatter is bimodal → cluster mode or 3D Classification on the same particles; 3DFlex on an uncleaned stack → stop, clean first (`26_continuous_heterogeneity.md`, Tree 6 in `18_decision_trees.md`).

**CTF Refinement / RBMC**
- Inspect: per-particle defocus / tilt / trefoil distributions, FSC delta vs prior refinement, exposure group setup.
- Continue if: FSC improves after refinement, residuals tighten, exposure groups consistent with collection metadata.
- Branch if: no improvement or FSC degrades → revert and revisit upstream (consensus stability, exposure groups, mask) (`ctf_refinement_and_rbmc.md`).

**Postprocess / sharpening / local resolution / orientation diagnostics**
- Inspect: corrected FSC vs tight/loose FSC, sharpened map features, local resolution map, viewing-direction + cFAR/tFAR/SCF* / Relative Signal.
- Continue if: features improve at higher cutoff; locally-filtered map for visualization only.
- Branch if: tight-mask FSC bump with visible map degradation → loosen mask; anisotropic cFSC → orientation pathway (`10_postprocessing.md`, `20_masks.md`, `orientation_and_preferred_views.md`).

## §6 Escape hatch

If no phenotype in §4 fits the dataset, or the dataset is messier than any curated case study:

- For a stage-specific "what next?", go to `18_decision_trees.md` (Trees 1–11) and pick the matching tree.
- For an exact error string or traceback, go to `17_error_lookup.md` + `15_troubleshooting.md`.
- For version-gated behavior (a feature behaves unexpectedly across v4.0–v5.0), check `version_caveats.md`.
- For parameter tuning ranges, see `16_tuning_recipes.md`.
- For overview / project / interface terminology, see `00_overview.md`.

Do not invent a new playbook. If the agent still cannot route after the escape hatch, stop and ask the user for one extra signal (job type, plot screenshot description, exact symptom, or symmetry assumption).
