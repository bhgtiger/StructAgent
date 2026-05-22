# Topic 12 — Tomography / cryo-ET Boundaries

## Scope
This is an **advisor boundary page**, not a tomo pipeline. The bundled cryoSPARC documentation corpus is overwhelmingly single-particle analysis (SPA) focused and does **not** contain a dedicated cryoSPARC tomography job family (no tilt-series alignment, no tomogram reconstruction, no subtomogram averaging, no template matching in tomograms, no per-tilt CTF, no fiducial tracking jobs are attested in the local docs). When a user asks for "tomo help in cryoSPARC," the agent's first job is to figure out what they actually have, what they actually want, and which work — if any — belongs inside cryoSPARC versus outside it.

What lives elsewhere — do not duplicate:
- Overall job-catalog routing and the in-scope / out-of-scope table — `00_overview.md`.
- Helical (filaments in SPA frames, not tomograms) — `11_helical.md`.
- Native import mechanics for movies / micrographs / particles / volumes — `02_import.md`.
- SPA preprocessing (Patch Motion / Patch CTF / curation / denoiser / junk detector) — `03_preprocessing.md`.
- Topaz wrapper mechanics (Topaz publishes both cryoEM **and** cryoET models; cryoSPARC's wrapper is SPA-oriented) — `04_picking.md`, `23_external_jobs.md`.
- Particle extraction, box, Fourier crop — `05_extraction_2d.md`.
- Refinement branches once you have a particle stack — `07_refinement.md`, `09_local_refinement.md`.
- Postprocessing, including preferred-orientation diagnostics and conical FSC — `10_postprocessing.md`.
- External Jobs and wrapper boundaries — `23_external_jobs.md`.
- RELION interop bridge (RELION has native tomo support; cryoSPARC does not) — `27_relion_interop.md`.
- `cryosparc-tools` automation contract — `13_cryosparc_tools_api.md`.
- Decision-tree routing — `18_decision_trees.md`. Error-string lookup — `17_error_lookup.md`.

**Standing version disclaimer.** "cryoSPARC has no tomography support" is the state of the **bundled v4.0–v5.0 docs in this skill** (`docs/per_page/processing-data__all-job-types-in-cryosparc.md`, `docs/per_page/_manifest.md`, `reference/release_notes/markdown/v4.0.md`…`v5.0.md`). If Structura ships tomography jobs after the bundle cutoff, this page will be stale. Always confirm against the user's installed version and live job catalog before stating what is or is not available.

---

## 1. Bottom line for the agent

| Question | Honest answer from this bundle |
|---|---|
| Does cryoSPARC have a tilt-series alignment job? | Not attested. |
| Does cryoSPARC have a tomogram reconstruction job? | Not attested. |
| Does cryoSPARC have a subtomogram averaging job? | Not attested. |
| Does cryoSPARC have a per-tilt CTF / CTF-per-image-in-tilt-series job? | Not attested. |
| Does cryoSPARC have a fiducial detection / patch tracking job? | Not attested. |
| Does cryoSPARC have a tomogram template-matching job? | Not attested. |
| Can cryoSPARC import a tomogram volume? | Only as a generic **3D volume** (MRC); it will be treated as a map/reference, not as a tomogram with tilt metadata. See `02_import.md`. |
| Can cryoSPARC import "subtomogram" particles? | Only as **particles** — i.e. 2D-projection-flavored boxes with a `.cs`/STAR file. The "missing wedge" property is not represented in cryoSPARC's particle model in the bundled docs. |
| Is Topaz **cryoET** available through the cryoSPARC Topaz wrapper? | Not attested. The wrapper docs (`docs/per_page/processing-data__all-job-types-in-cryosparc__deep-picking__topaz*.md`) describe SPA picking and SPA denoising on micrographs; the Topaz authors cite cryoEM **and** cryoET capability for their tool (`docs/per_page/processing-data__all-job-types-in-cryosparc__exposure-curation__job-micrograph-denoiser-beta.md` references *Topaz-Denoise: general deep denoising models for cryoEM and cryoET*), but that does not mean the cryoSPARC wrapper exposes the cryoET pathway. Verify in the user's instance. |
| Does cryoSPARC Live ingest tilt-series? | Not attested; Live is designed for SPA-style streaming preprocessing (`25_cryosparc_live.md`). |
| Does "tomographic projection" wording in cryoSPARC mean tomo support? | **No.** "Tomographic projection" appears in `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-common-cryosparc-plots.md` and `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-ewald-sphere-correction.md` as the *projection model* used in SPA reconstruction (Radon-style integration along the beam axis through a single particle). It is not a reference to cryo-ET. |

If the user expected a cryoSPARC tomo pipeline, **say so plainly** and route them — do not fabricate a workflow out of SPA jobs.

---

## 2. Triage — what does the user actually have?

Before recommending anything, get four pieces of information. Do not skip these even if the user seems impatient; almost every wrong recommendation in this area comes from misreading the inputs.

1. **Data type on disk.** Movies (per-frame, per-position)? Aligned micrographs? Tilt-series (a stack of images at known tilt angles per position)? Reconstructed tomograms (3D MRC volumes)? Particles extracted from tomograms? A STAR file from RELION/Warp/AreTomo/IMOD?
2. **Intent.** Build tomograms? Detect particles in tomograms? Average subtomograms? Refine an existing reference against extracted particles? Just visualize a tomogram? Compare to a published SPA structure?
3. **Existing pipeline.** What produced the current files — Warp, RELION 4/5 tomo, IMOD, AreTomo, EMAN2 e2spt, M, Dynamo, custom? Are the upstream tools available on the same hardware?
4. **cryoSPARC instance state.** Master/worker version (`cryosparcm status`; see `14_cli_admin.md`). Live job catalog (cards view in the Job Builder, or `docs/per_page/processing-data__all-job-types-in-cryosparc.md` in this bundle). Newer cryoSPARC releases may add jobs the bundle does not know about (`reference/release_notes/markdown/v5.0.md`).

Only with all four does the routing matrix below have a defensible answer.

---

## 3. Decision matrix — does cryoSPARC belong in this workflow?

| User inputs | User goal | Does cryoSPARC help? | Route |
|---|---|---|---|
| Tilt-series only, no tomograms | Reconstruct tomograms | **No** in this bundle. | External: IMOD / AreTomo / Warp / RELION tomo. See §6. |
| Tilt-series only | Per-tilt CTF, fiducial alignment | **No** in this bundle. | External. |
| Reconstructed tomograms | Pick / template-match particles in tomograms | **No** in this bundle. | External: RELION 4/5 tomo template matching, Warp/M, EMAN2, pyTOM. |
| Reconstructed tomograms | Subtomogram averaging | **No** in this bundle. | External (RELION tomo, M, Dynamo, EMAN2 e2spt). |
| Extracted "particles" already projected to 2D (e.g., pseudo-SPA particles from Warp/M sub-projection or from tilt-series-aware extraction in RELION) | SPA-style 2D / ab initio / refinement | **Possibly yes**, with caveats. The particles must reach cryoSPARC as a normal particle stack (MRC stacks + `.cs`/STAR). Missing-wedge effects are not modeled. | §5.2 runbook, then `05_extraction_2d.md`, `06_abinitio.md`, `07_refinement.md`. |
| 3D map / EMDB volume from a tomo paper | Use as a reference / template / initial volume in SPA refinement | **Yes**, as a generic Import 3D Volume → Create Templates / Refinement reference. cryoSPARC has no awareness that the source pipeline was tomo. | `02_import.md`, `07_refinement.md`. |
| Tilted SPA grids (e.g., 30° / 40° stage tilt during *single-particle* collection, for preferred orientation rescue) | Standard SPA on a tilted dataset | **Yes** — this is SPA, not cryo-ET. Tilt is a stage angle during SPA collection, not a tilt-series. | `03_preprocessing.md`, `10_postprocessing.md`. Preferred-orientation tooling: Orientation Diagnostics (`10_postprocessing.md`), Rebalance Orientations (v4.5+, `reference/release_notes/markdown/v4.5.md`). |
| Helical filaments in 2D micrographs | Helical reconstruction | **Yes (BETA).** This is *not* tomography. | `11_helical.md`. |
| User wants to "connect tomo tools to cryoSPARC" | Run a wrapper or external pipeline | **Conditionally.** External Jobs via `cryosparc-tools` can shuttle particle datasets between cryoSPARC and arbitrary code, but cryoSPARC has no native concept of tilt-series, tomograms, or missing wedge. | `23_external_jobs.md`, `13_cryosparc_tools_api.md`. |
| User asks "does cryoSPARC support tomography?" | Yes/no answer | **In this bundle, no.** Defer to the user's installed version's job catalog and release notes before promising the opposite. | §1 table, then `00_overview.md`. |

---

## 4. SPA concepts that may still be relevant to tomo-adjacent work

When a user lands in cryoSPARC with tomo-derived data, these SPA surfaces are the only ones that legitimately apply:

| Surface | What carries over from SPA | What does **not** carry over |
|---|---|---|
| Import 3D Volume (MRC, `02_import.md`) | A tomogram or subtomogram average can be imported as a map for use as a reference or visualization target. Pixel size, box cubicity, and contrast convention must be honest. | Tilt-series metadata; per-tilt dose; missing-wedge geometry; CTF-per-tilt; original coordinates inside the parent tomogram. |
| Import Particle Stack (`02_import.md`, `27_relion_interop.md`) | Particles produced by a tomo pipeline that have already been reduced to 2D-projection-flavored boxes (with `_rlnImageName`, optics group, CTF parameters) can be imported via the RELION STAR bridge. | Subtomogram-as-3D-volume semantics; missing-wedge weighting; per-tilt CTF; per-particle 3D rotational priors derived from tilt geometry. |
| Exposure / CTF metadata (`03_preprocessing.md`) | Accelerating voltage, Cs, amplitude contrast, pixel size, and dose are still required and must be set honestly even for tomo-derived particle stacks. | A single defocus per particle from a tomo pipeline is an approximation; cryoSPARC will treat it as truth. |
| GPU / SSD cache / lane (`21_gpu_lane_queue.md`) | All standard SPA hardware planning still applies: box size vs VRAM, SSD cache, lane routing. Box sizes that came from tomo extraction can be **large**; verify against the VRAM/box-size table in `21_gpu_lane_queue.md`. | None — this layer is workflow-agnostic. |
| Storage and project layout (`24_disk_and_storage.md`) | Symlinks to externally produced MRC stacks must remain valid on the worker. Tomograms exported from cryoSPARC are still just MRC volumes. | None workflow-specific. |
| External Jobs (`23_external_jobs.md`) | The only attested integration surface for shuttling data between cryoSPARC and an outside tomo tool. Provenance is preserved per-result-group. | Native handling of tilt-series; native handling of missing wedge. |
| RELION interop (`27_relion_interop.md`) | `csparc2star.py` / pyem-style bridges round-trip SPA particle metadata. RELION's tomo STAR shapes (tilt series, tomograms) are not the same dialect as the SPA particle STAR. | Direct round-trip of tomo-specific STAR shapes. Treat as one-way SPA-particle bridge unless the user's pyem/csparc2star version explicitly documents the tomo schema. |
| Topaz wrapper (`04_picking.md`, `23_external_jobs.md`) | Topaz model paths and the deactivate-conda / activate-topaz `topaz.sh` pattern are SPA picking/denoising. The wrapper is SPA-shaped (micrographs in, picks out). | Topaz's `cryoET` model family. The bundled wrapper docs describe SPA picking/denoising on 2D micrographs; do not promise cryoET picking through the wrapper without verifying live. |
| Preferred-orientation diagnostics (`10_postprocessing.md`) | Orientation Diagnostics (v4.4+) and conical/3DFSC concepts are useful any time data has anisotropic angular coverage, including data extracted from tomograms. | A "preferred orientation" diagnosis on tomo-derived particles is *not* a missing-wedge correction — see §5. |

---

## 5. Common confusion points

### 5.1 Tilt-series vs tilted SPA
A **tilt-series** is one stack of images of the **same field of view** at known stage tilts (typically −60° to +60°), used to reconstruct a 3D tomogram. **Tilted SPA** is single-particle data where the stage is tilted (often 30°–40°) to add views and break preferred orientation — every image is still an independent SPA exposure of a different field. cryoSPARC handles tilted SPA natively; it does **not** treat tilt-series as a first-class object. When a user says "tilted data," ask which they mean before answering.

### 5.2 Tomogram vs micrograph
A **tomogram** is a 3D MRC volume; a **micrograph** is a 2D MRC image. cryoSPARC's exposure-curation, picking, and extraction jobs operate on 2D micrographs. Loading a tomogram into the Micrograph Denoiser, Micrograph Junk Detector, or any 2D picker is a category mistake. If a user has tomograms and asks for "denoising in cryoSPARC," route them to a tomo tool (Topaz cryoET, IsoNet, cryoCARE) outside cryoSPARC; the cryoSPARC Micrograph Denoiser is a 2D job (`docs/per_page/processing-data__all-job-types-in-cryosparc__exposure-curation__job-micrograph-denoiser-beta.md`).

### 5.3 Particle box vs subtomogram
A cryoSPARC **particle** is a 2D image (a box cropped from a micrograph) plus pose and CTF metadata. A **subtomogram** is a 3D sub-volume cropped from a tomogram, plus per-tilt CTF and missing-wedge information. cryoSPARC's data model in the bundled docs treats particles as 2D throughout: the volume model is the *output* of refinement, not the *input* per-particle. If the user has true 3D subtomograms, those cannot be ingested as cryoSPARC particles without first being reprojected back to 2D images (RELION's "tomo" pipeline and Warp/M produce such 2D-flavored particle stacks for handoff to SPA tools).

### 5.4 Missing wedge vs preferred orientation
Both produce **anisotropic resolution**. They are not the same problem.
- **Missing wedge** is geometric: tilt-series data does not cover all angles, so the 3D Fourier transform is empty in a wedge-shaped region.
- **Preferred orientation** is statistical: particles sit on the grid in non-uniform poses, so some Fourier directions are under-sampled.

cryoSPARC's Orientation Diagnostics and 3DFSC/cFSC concepts (`10_postprocessing.md`) measure the *symptom* (anisotropic FSC), not the *cause*. On tomo-derived particles they will report anisotropy even when the geometry is "correct" given the missing wedge — do not use them to claim cryoSPARC has fixed a missing-wedge problem. Forum context for conical FSC and tomogram anisotropy: `docs/forum_threads/digests/forum_particle-curation.md`.

### 5.5 Topaz "cryoEM and cryoET" wording
The Topaz-Denoise paper (Bepler et al., 2020) is cited in the cryoSPARC denoiser docs (`docs/per_page/processing-data__all-job-types-in-cryosparc__exposure-curation__job-micrograph-denoiser-beta.md`) and is titled *"…general deep denoising models for cryoEM and cryoET."* This citation establishes that Topaz the upstream tool has cryoET models — it does **not** establish that the cryoSPARC wrapper exposes them. The wrapper docs (`docs/per_page/processing-data__all-job-types-in-cryosparc__deep-picking__topaz*.md`) describe SPA picking/denoising on 2D micrographs. If a user wants Topaz-cryoET, verify wrapper coverage in their installed cryoSPARC version, and otherwise run Topaz directly outside cryoSPARC.

### 5.6 Importing MRC volumes ≠ importing a full tomo workflow
Import 3D Volume happily ingests an MRC file regardless of whether it came from a SPA reconstruction or a tomogram (`02_import.md`). After import, cryoSPARC will treat it as a reference map (for Create Templates, refinement initialization, visualization). There is no metadata in the import that records "this is a tomogram, with these tilt parameters." Treat such imports as opaque maps. Forum context: `docs/forum_threads/digests/forum_particle-picking.md` notes Topaz internally treats MRC micrograph/tomogram arrays interchangeably as numpy arrays — that is a Topaz internal detail, not cryoSPARC tomo support.

---

## 6. External handoff pattern

When the work has to leave cryoSPARC for a tomo step and come back, the only attested mechanism in this bundle is:

1. **Get the foreign tool installed and validated outside cryoSPARC.** Do not try to install RELION 4/5 tomo, Warp/M, AreTomo, IMOD, or Dynamo *into* the cryoSPARC conda env. See `23_external_jobs.md` for the wrapper-script pattern (deactivate cryoSPARC env, activate tool env, exec tool).
2. **Keep tilt-series and tomograms outside the cryoSPARC project tree** unless you specifically want them to count against project storage. Symlinks into the project from a stable external raw-data path are the standard pattern (`24_disk_and_storage.md`).
3. **Round-trip only what cryoSPARC understands.** Most pragmatic handoff:
   - The foreign tool reduces subtomograms to 2D-projection-flavored particles with a RELION-style STAR file (`_rlnImageName`, optics group, CTF, optionally tilt-aware pose priors).
   - Import via the RELION bridge (`27_relion_interop.md`).
   - Run SPA-style refinement / classification / heterogeneity in cryoSPARC.
   - Export via `csparc2star.py` (pyem) for return to the tomo tool, **only** if the foreign tool can consume an SPA-particle STAR (RELION 5 can; older pipelines vary).
4. **Use External Jobs (`23_external_jobs.md`) when the bridge is scripted.** Schema in / schema out is explicit; provenance is preserved as a first-class result group. Anything wedge-aware lives in the external script, not in cryoSPARC's data model.
5. **Do not edit MongoDB to fake tomo metadata.** This is called out as a hard rule across the skill (`14_cli_admin.md`, `00_overview.md`); it applies double here.

Caveat: pyem/csparc2star's tomo-STAR support has changed across releases, and the bundled forum digests document churn even on the SPA side of the bridge (`docs/forum_threads/digests/forum_import.md`). Verify the user's pyem version against their RELION tomo schema before promising a clean round-trip.

---

## 7. Runbooks for the four scenarios

### Runbook A — User has tilt-series and/or tomograms only
**Likely ask:** "How do I process this in cryoSPARC?"

1. State the boundary up front: cryoSPARC in this bundle does not align tilt-series, reconstruct tomograms, or do subtomogram averaging.
2. Verify against their installed version (`cryosparcm status`, live job catalog) before being absolute — Structura may add jobs after this bundle's cutoff. See `reference/release_notes/markdown/v5.0.md`.
3. Triage their goal:
   - Want a tomogram → IMOD / AreTomo / Warp / RELION tomo.
   - Want particles from tomograms → RELION 4/5 tomo, Warp/M, EMAN2 e2spt, pyTOM, Dynamo.
   - Want subtomogram averaging → same as above plus M, EMAN2 e2spt.
4. If they later want SPA-style refinement on 2D-projection particles produced by a tomo pipeline, that is Runbook B.
5. **Red flag:** they have tilt-series and assume Import Movies or Import Micrographs will "just work." Stop them before they create a polluted project. Tilt-series imported as movies will reconstruct *each tilt as a separate micrograph* — that is not what they want, and downstream defocus / CTF / pose metadata will be wrong.

### Runbook B — User has 2D-projection particles extracted from tomograms and wants SPA-like refinement
**Likely ask:** "I have a particles.star from RELION tomo / Warp / M; can I refine in cryoSPARC?"

1. Confirm the particle stack is genuinely **2D** (each row is a 2D image, with an `_rlnImageName` pointer to an MRC stack). If rows point to 3D subtomograms, this runbook does not apply — return them to Runbook A.
2. Use the RELION import bridge per `27_relion_interop.md`. Optics groups, pixel size, voltage, Cs, amplitude contrast, defocus must all be in the STAR file or supplied at import. Apply the standard SPA preflight from `02_import.md` (path resolves on worker; CTF values plausible; no Y-flip surprises).
3. Treat the result as a normal SPA particle set:
   - 2D Classification for diagnostics; do not be surprised if classes look anisotropic — that is missing wedge, not a cryoSPARC bug. See §5.4 and `05_extraction_2d.md`.
   - Ab initio reconstructions may seed weird poses because the input particles already have strong angular priors from the tomo geometry; if you have a known reference, prefer Homogeneous / Non-Uniform Refinement seeded with that reference (`07_refinement.md`).
   - Heterogeneity workflows (`08_classification_3d.md`, `26_continuous_heterogeneity.md`) apply, but caveat their interpretation: continuous heterogeneity from 3DVA / 3DFlex on missing-wedge data can confound conformational and orientation modes.
4. Postprocessing: read FSC and Orientation Diagnostics with the missing-wedge caveat in mind (§5.4, `10_postprocessing.md`). Do not advertise "isotropic resolution" after refinement of tomo-derived particles without independent evidence.
5. Round-trip back to the tomo tool, if needed, via `csparc2star.py` / pyem (`27_relion_interop.md`).
6. **Red flag:** user expects cryoSPARC to "correct the missing wedge." It cannot, in this bundle. Say so.

### Runbook C — User wants to connect an external tomo tool to cryoSPARC
**Likely ask:** "Can I wrap AreTomo / Warp / RELION tomo as a cryoSPARC job?"

1. Send them to `23_external_jobs.md` and `13_cryosparc_tools_api.md`. External Jobs via `cryosparc-tools` are the *only* attested wrapper surface for non-bundled tools.
2. Set expectations:
   - cryoSPARC will not understand tilt-series, tilt angles, per-tilt CTF, or missing wedge as first-class objects.
   - The External Job's job is to take SPA-shaped cryoSPARC inputs (movies, micrographs, particles, volumes), run the external tool **outside** the cryoSPARC env, and return SPA-shaped outputs.
   - Anything tomo-specific (tilt-series stack, tilt metadata, tomogram volume) must be parked in the external tool's filesystem and not pretended into cryoSPARC's data model.
3. Wrapper-script pattern is the same as DeepEMhancer / CTFFIND4 / MotionCor2 (`23_external_jobs.md`): deactivate cryoSPARC env, activate tool env, exec tool. Script path must be reachable identically on master and worker.
4. Match `cryosparc-tools` minor version to master minor version (`13_cryosparc_tools_api.md`).
5. Preserve provenance: every result group should carry explicit inputs/outputs schema; downstream cryoSPARC jobs should be able to introspect what the External Job consumed and produced.
6. **Red flag:** user wants to install RELION tomo / Warp / IMOD inside the cryoSPARC conda env. Stop them — the bundled forum threads document broken Topaz installs from exactly this pattern (`docs/forum_threads/digests/forum_particle-picking.md`).

### Runbook D — User asks "does cryoSPARC support tomography?"
1. **Answer honestly:** in the bundled v4.0–v5.0 documentation this skill ships, no. There are no tilt-series, tomogram, subtomogram, per-tilt CTF, fiducial, or template-matching jobs in the catalog (`docs/per_page/processing-data__all-job-types-in-cryosparc.md`, `docs/per_page/_manifest.md`).
2. **Qualify the answer with version-awareness:** Structura ships new jobs; the bundle has a cutoff. The user should check their installed instance's job catalog and the official release notes. Local release-notes snapshot lives at `reference/release_notes/markdown/v4.0.md`…`v5.0.md`.
3. **Do not invent a workflow.** Do not assemble Import 3D Volume + Local Refinement + Orientation Diagnostics into a "tomo pipeline" and present it as one. It is not one.
4. Offer the two legitimate paths: external tomo tools (Runbook A) or SPA-style refinement of already-2D-reduced particles (Runbook B).

---

## 8. Advisor defaults and first questions to ask a tomography user

Default stance: **do not invent a cryoSPARC tomography pipeline**. Verify the installed version and job catalog first, then either route to SPA-adjacent cryoSPARC jobs or hand off to external tomo software with provenance preserved.

Ask before recommending anything:

1. **What is the unit on disk?** Movie frames, aligned micrographs, tilt-series, tomograms, subtomograms, or 2D-projection particles?
2. **Which tool produced the current data?** Warp, RELION tomo, AreTomo, IMOD, Dynamo, EMAN2 e2spt, M, custom?
3. **What is the cryoSPARC version?** Run `cryosparcm status` and check the live job catalog (cards view in Job Builder, or `docs/per_page/processing-data__all-job-types-in-cryosparc.md` for the bundle's snapshot).
4. **Is there a reference / EMDB volume?** If yes, that is enough to start refinement of 2D-reduced particles in cryoSPARC; if no, the user needs an ab initio in cryoSPARC or an external reference.
5. **What is the goal?** Final map for publication, conformational study, screening, comparison to a SPA reference, or just visualization?
6. **What hardware is available?** Subtomogram boxes can be large; check against the VRAM / box-size table in `21_gpu_lane_queue.md`.
7. **Do they expect missing-wedge correction inside cryoSPARC?** If yes, set expectations (§5.4).

---

## 9. Red flags that should short-circuit normal routing

- "Let me Import Movies my tilt-series." → Stop. Tilt-series ≠ movies. Runbook A.
- "The cryoSPARC Topaz job will pick particles in my tomograms." → Stop. The bundled Topaz wrapper is SPA-shaped (`04_picking.md`). Use Topaz cryoET directly outside cryoSPARC, or use a tomo-native picker.
- "I'll import my tomogram as a particle." → Stop. A tomogram is a 3D MRC; cryoSPARC particles are 2D boxes. §5.3.
- "I'll fix the missing wedge with Non-Uniform Refinement." → Stop. NU does not model missing-wedge geometry. §5.4.
- "I'll just edit the `.cs` file to mark these as subtomograms." → Stop. The cryoSPARC data model has no first-class subtomogram type in this bundle; pretending one exists corrupts downstream metadata. Use External Jobs explicitly (`23_external_jobs.md`).
- "I'll install RELION tomo / Warp inside the cryoSPARC conda env so the wrappers see it." → Stop. Forum-documented failure mode for adjacent tools (`docs/forum_threads/digests/forum_particle-picking.md`); admin-side rule against pip-installing into the cryoSPARC env (`17_error_lookup.md`).

---

## 10. Version-awareness

Tomography support is the single most likely area for this bundle to go stale:

- This skill was authored against bundled v4.0–v5.0 docs. Cutoff is roughly 2026-05-05 per `reference/release_notes/markdown/v5.0.md`. After that date, the *only* trustworthy source for "does cryoSPARC support tomography now?" is the user's installed instance and the live release notes.
- The bundled release notes for v4.0…v5.0 (`reference/release_notes/markdown/v4.0.md`…`v5.0.md`) contain no entries for tilt-series, tomogram reconstruction, subtomogram averaging, per-tilt CTF, fiducial tracking, or 3D template matching. New job types in v4.0–v5.0 are SPA / Live / heterogeneity / orientation / postprocessing-flavored.
- Forum threads pre-dating a hypothetical future tomo release will look authoritative but be wrong. When recalling a forum claim about tomo, sanity-check against the user's installed version.
- The reference-paper inventory explicitly notes "**No tomo-specific cryoSPARC paper (if one exists)**" (`reference/papers/maria_inventory.md`) and flags "Tomo paper if separate" as an unresolved paper-discovery item (`reference/papers/README.md`). Treat that absence as informative.

When in doubt, the agent should *state the bundle's date and ask the user to confirm against the installed instance* before committing to "cryoSPARC has no tomography."

---

## 11. Cross-links

| If the user… | Go to |
|---|---|
| Asks anything tomo-shaped | This page first, then Runbooks A–D. |
| Has 2D-projection particles to refine | `02_import.md`, `27_relion_interop.md`, `05_extraction_2d.md`, `07_refinement.md` |
| Asks about Topaz cryoET | `04_picking.md`, `23_external_jobs.md` |
| Asks about importing an EMDB / tomo-derived volume | `02_import.md` |
| Reports anisotropic FSC after refinement of tomo-derived particles | `10_postprocessing.md`, `20_masks.md` |
| Wants to wrap an external tomo tool | `23_external_jobs.md`, `13_cryosparc_tools_api.md` |
| Confuses tilted SPA with tilt-series | This page §5.1, then `03_preprocessing.md` |
| Confuses helical reconstruction with tomography | `11_helical.md` |
| Asks for cryoSPARC's overall scope | `00_overview.md` |
| Hits an obscure tomo-flavored error string | `17_error_lookup.md`, `15_troubleshooting.md` |
| Needs to route generically | `18_decision_trees.md` |
| Needs hardware planning for large boxes | `21_gpu_lane_queue.md`, `24_disk_and_storage.md` |
| Needs to check `cryosparcm` version / job catalog | `14_cli_admin.md` |

---

## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

- `docs/per_page/_manifest.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__exposure-curation__job-micrograph-denoiser-beta.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-ewald-sphere-correction.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-common-cryosparc-plots.md`
- `docs/raw/llms-full.txt`
- `docs/forum_threads/digests/forum_particle-picking.md`
- `docs/forum_threads/digests/forum_particle-curation.md`
- `docs/forum_threads/digests/forum_import.md`
- `docs/forum_threads/digests/forum_troubleshooting.md`
- `docs/forum_threads/digests/forum_scripting.md`
- `reference/papers/README.md`
- `reference/papers/maria_inventory.md`
- `17_error_lookup.md`
- `reference/release_notes/markdown/v4.0.md`
- `reference/release_notes/markdown/v4.1.md`
- `reference/release_notes/markdown/v4.2.md`
- `reference/release_notes/markdown/v4.3.md`
- `reference/release_notes/markdown/v4.4.md`
- `reference/release_notes/markdown/v4.5.md`
- `reference/release_notes/markdown/v4.6.md`
- `reference/release_notes/markdown/v5.0.md`
- `00_overview.md`
- `02_import.md`
- `03_preprocessing.md`
- `04_picking.md`
- `05_extraction_2d.md`
- `07_refinement.md`
- `10_postprocessing.md`
- `11_helical.md`
- `13_cryosparc_tools_api.md`
- `14_cli_admin.md`
- `15_troubleshooting.md`
- `18_decision_trees.md`
- `20_masks.md`
- `21_gpu_lane_queue.md`
- `23_external_jobs.md`
- `24_disk_and_storage.md`
- `25_cryosparc_live.md`
- `27_relion_interop.md`
- `topic_plan.md`
- `plan.md`
