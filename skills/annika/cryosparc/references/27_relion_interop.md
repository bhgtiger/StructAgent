# Topic 27 — RELION Interoperability

## Scope
What CryoSPARC and RELION actually exchange when you move a project between them, where the metadata bridge silently degrades, and how to decide when round-tripping is worth the bookkeeping. The page covers RELION → CryoSPARC import boundaries, CryoSPARC → RELION export via bridge scripts (`csparc2star.py` / pyem-style), round-trip validation, and the recurring path/optics/coordinate mistakes that cost users days. Native import mechanics (the recipe, gain refs, exposure groups) belong in `02_import.md`; extraction needs after foreign picks land in CryoSPARC live in `05_extraction_2d.md`; programmatic STAR I/O via `cryosparc.star` belongs in `13_cryosparc_tools_api.md`; arbitrary code bridges (External Jobs) are owned by `23_external_jobs.md`; on-disk lifetime of imported/symlinked data is owned by `24_disk_and_storage.md`. Error-string lookup is in `17_error_lookup.md`.

The page deliberately avoids hardcoding exact pyem/csparc2star command syntax beyond what the local corpus attests. `csparc2star.py` has changed several times across pyem releases (forum threads document `--passthrough` being removed, the `--copy-micrograph-coordinates` flag, the `--boxsize` flag for box-size injection, Bayesian-polishing support, micrograph-coordinate merge keys breaking and being fixed). Treat any specific flag below as a *bridge pattern*: confirm against the installed pyem version and the current `csparc2star.py --help` on the system before scripting it.

---

## 1. Mental model — what crosses the boundary

CryoSPARC and RELION model "a particle dataset" very differently, and most interop pain is one of those models silently losing fidelity when expressed as the other.

| Concept | CryoSPARC | RELION |
|---|---|---|
| Particle metadata container | `.cs` dataset (numpy structured array) inside an output result group, with `passthrough` slots carrying upstream lineage | One or more `.star` files, with `data_optics` (3.1+) and `data_particles` blocks |
| Particle image storage | `.mrc` particle stacks emitted by Extract / Restack; data sign convention is dark-on-light by default | `.mrcs` particle stacks; RELION's Extraction flips particles to light-on-dark by default (`Data Sign = -1` interpretation in CryoSPARC import) |
| Pixel size / box size | Stored on the particle blob and refreshed by Extract; refinement carries its own working pixel size | Stored in `data_optics` per optics group as `rlnImagePixelSize` and `rlnImageSize` (3.1+); particle image size has to be present or RELION refuses to load |
| CTF | Per-particle defocus + a CTF model; higher-order aberrations (beam-tilt, trefoil, tetrafoil, spherical-aberration, anisotropic magnification per v3.3+) stored in CryoSPARC's own slots | Per-particle CTF + higher-order terms recorded in `data_optics` (beam-tilt, anisotropic mag matrix, odd/even Zernikes) |
| Pose | `alignments3D` (`shift`, `pose`/`rotation`, `psize_A`, `error`, per-particle scale) | `rlnAngleRot/Tilt/Psi`, `rlnOriginX/YAngst` (3.1+) or `rlnOriginX/Y` (3.0 and earlier) |
| Linkage to source mic / movie | Result-group connection, plus `mscope_params` and the import job's symlinks | `rlnMicrographName` path string, with optional `rlnMicrographMovieName` for movies and `rlnMicrographGainName` for the gain ref |
| Optics groups / exposure groups | CryoSPARC "exposure groups" (AFIS / beam-shift / regex-built); refinement uses these for per-group beam-tilt | RELION "optics groups" — must be present in `data_optics` for any 3.1+ workflow |
| Postprocessed map | A sharpened `.mrc` with separately stored half-maps and FSC mask; `map_sharp` is a single output of Sharpening Tools or refinement | A B-factor-sharpened `.mrc` from RELION PostProcess; the underlying half-maps and FSC mask are managed by RELION's job tree |

What survives a round-trip well:
- Per-particle defocus and the bulk CTF (voltage, Cs, amplitude contrast, pixel size).
- Particle pose (`alignments3D` ⇄ `rln*` angles + origins), if the box size is consistent and the bridge converts origins correctly.
- Micrograph name as a path string (with the right prefix/suffix trimming).

What survives a round-trip poorly or not at all:
- **Higher-order CTF aberrations.** Per the Import Particle Stack docs: "RELION and CryoSPARC record higher-order CTF parameters in mutually incompatible formats. Performing higher-order refinements in global CTF in one processing software will require re-fitting CTF in the other." Re-refine global CTF on the receiving side; do not trust transported higher-order terms.
- **Optics-group ↔ exposure-group mapping.** Coarse correspondence works (one optics group per exposure group). Fine details (beam-tilt values, anisotropic-magnification matrix, per-group Zernikes) do not transfer cleanly and should be re-fit.
- **Sharpening / postprocessing decisions.** CryoSPARC's automatic refinement-time sharpening and RELION's PostProcess apply different masks, FSC corrections, and B-factor choices; "the postprocessed map" is not a portable artifact. Move half-maps and a mask if you want the receiving side to do its own postprocessing.
- **Per-particle scale, rejected-particle subset, and per-particle alignments diagnostics** — these are CryoSPARC concepts and have no native RELION equivalent.
- **Provenance/lineage.** The receiving side sees a stack of particles and a STAR file. It does not see which 2D selection, which junk-class cut, which mask, or which symmetry choice produced them.

---

## 2. Where this page sits vs adjacent topics

| If the question is… | Go here instead |
|---|---|
| "How do I configure Import Particle Stack / Import Movies / Import Micrographs?" | `02_import.md` (canonical RELION → CryoSPARC recipe, gain refs, exposure groups) |
| "I have foreign picks — do I need to extract before 2D?" | `05_extraction_2d.md` (external picks always need Extract from Micrographs before 2D/3D) |
| "How do I read or write `.cs` / `.star` programmatically?" | `13_cryosparc_tools_api.md` (note: `cryosparc-tools` ships a `cryosparc.star` helper) |
| "I want to call pyem / a RELION binary as part of a custom workflow." | `23_external_jobs.md` (External Job is the bridge; this page focuses on the metadata semantics) |
| "Where do imported particle stacks and symlinked movies live? Can I delete them?" | `24_disk_and_storage.md` (Import jobs symlink raw data; CryoSPARC never deletes raw data) |
| "I see error string X." | `17_error_lookup.md` |
| "Which import branch should I take given my inputs?" | `18_decision_trees.md`, Tree 1 |

This page is the place to think about **what the bridge does and does not preserve**, and what to validate on the other side.

---

## 3. RELION → CryoSPARC

### 3.1 What you can import, and what each path costs

Three practical scenarios, in increasing fidelity:

| Starting point in RELION | CryoSPARC import path | What you keep | What you give up |
|---|---|---|---|
| Raw movies on disk (still have them) | Import Movies → Patch Motion → Patch CTF; then Import Particle Stack pointed at RELION's particle STAR with the cryoSPARC-aligned micrographs as Source Micrographs | Full CryoSPARC preprocessing (Patch CTF, exposure groups, RBMC eligibility, per-particle CTF refresh on Extract) | Some bookkeeping: path-suffix trimming, possible TIFF Y-flip caveat, re-extraction |
| Aligned micrographs only | Import Micrographs → Patch CTF; then Import Particle Stack with these as Source Micrographs | Patch CTF redone consistently inside CryoSPARC; per-particle CTF on re-extract | RBMC and any per-frame job — they require raw movies |
| Particle STAR + particle `.mrcs` only, no movies/mics | Import Particle Stack (no Source Exposures); set Pixel size / Voltage / Cs / Total dose if not in the STAR | Pose, defocus, ability to refine and classify | RBMC, Local Motion, Remove Duplicate Particles by movie position, anything that needs the micrograph image |

`02_import.md` is the owner of the step-by-step canonical RELION → CryoSPARC recipe; this page focuses on the *metadata caveats* you must check at each step.

### 3.2 Metadata caveats to confirm on entry

Run through these every time, in order. Most of the long forum threads about "particles do not align" or "Inspect Picks shows blanks" trace back to one of them.

- **Pixel size on the import job vs in the STAR vs on disk.** Import Particle Stack will read pixel size, voltage, Cs, and dose from the STAR if you do not override them. Confirm the values once against the collection sheet. If coordinates were picked on binned images in RELION but you re-aligned micrographs at unbinned super-res in CryoSPARC, X/Y coordinates need to be scaled (e.g. 2x) — see `02_import.md` for the linkage details.
- **Box size at re-extraction.** RELION's extraction box and CryoSPARC's choice can differ. The conservative default is to re-extract inside CryoSPARC after the import; that refreshes per-particle CTF and the particle blob at a known box and pixel size. (`05_extraction_2d.md` covers when re-extraction is mandatory; external picks always qualify.)
- **`rlnMicrographName` path suffix.** Import Particle Stack matches imported particles to Source Micrographs via the `rlnMicrographName` field. CryoSPARC's micrograph paths almost never match RELION's character-for-character; you tune `Length of Mic. path suffix to cut` and `Length of Part. path suffix to cut` until the trailing pieces line up. Expect to iterate; an off-by-one cut is the most common cause of "no matched micrographs" symptoms.
- **Y-flip caveat for TIFF-derived picks.** Picks that came from RELION / MotionCor2 / Warp alignments, when re-aligned in CryoSPARC, can be Y-flipped relative to the new micrographs. `18_decision_trees.md` flags this as a red-flag preflight item. Spot-check a handful of micrographs in Inspect Picks after the first Extract; if the picks are visibly mirrored vertically, fix the convention before continuing.
- **Data sign.** CryoSPARC's Import Particle Stack notes that "RELION flips particles to be light on dark by default during extraction." Set `Data Sign = -1` (or rely on autodetection) when bringing in already-extracted RELION stacks so that CryoSPARC displays them dark-on-light consistently. Stacks displaying as "inverted" in 2D thumbnails are almost always a Data Sign mismatch, not a real contrast problem.
- **Gain reference.** Import Movies expects a gain reference for non-gain-corrected movies; orientation (flip / rotation) is not always inferable. If the gain ref was estimated post hoc with `relion_estimate_gain`, confirm it on a small Patch Motion batch before committing.
- **CTF — higher-order terms.** Per the Import Particle Stack doc: incoming RELION higher-order terms (beam-tilt, anisotropic mag, Zernikes) do not transfer faithfully. Plan to re-fit Global CTF in CryoSPARC if higher-order correction matters to your final resolution.
- **Optics group → exposure group.** If your RELION project had multiple optics groups (multi-grid, multi-session, AFIS), set exposure groups on the CryoSPARC side at import or via Exposure Group Utilities. Future Global / Local CTF refinement and Reference Based Motion Correction depend on this.

### 3.3 When to re-extract on the CryoSPARC side

Always, except in two narrow cases:
1. You only need to do a quick visualization-only pass (looking at 2D classes once, throwing the project away).
2. You explicitly want to use RELION's stacks as-is because you do not have access to the source movies/micrographs.

Reasons to re-extract whenever feasible (consistent with `05_extraction_2d.md`):
- Per-particle CTF is refreshed from CryoSPARC's Patch CTF (the only way refinement gets full fidelity from the per-particle CTF model).
- Exposure-group / micrograph linkage becomes a first-class CryoSPARC relation, not a path-string match.
- Box / pixel size are guaranteed self-consistent across downstream jobs.
- 16-bit float storage (v4.4+) becomes available, materially reducing disk usage on large stacks.

### 3.4 Runbook — RELION particles into CryoSPARC

Preflight:
- [ ] You have the source movies (best) or aligned micrographs (acceptable) or just the particle stacks (limited).
- [ ] Pixel size, voltage, Cs, total dose confirmed against collection sheet, not just the STAR header.
- [ ] Gain reference available; orientation known or testable.
- [ ] Sample STAR opened in a text editor — confirm `rlnMicrographName`, `rlnCoordinateX/Y`, `rlnDefocusU/V`, `rlnAnglePsi`, and (3.1+) `data_optics` block presence; note `rlnImageSize` / `rlnImagePixelSize`.
- [ ] If your STAR is RELION 3.1+ (has `data_optics`), confirm your CryoSPARC version is recent enough to handle it; very old CryoSPARC builds predate optics-table aware import.

Import:
1. If raw movies exist: Import Movies → Patch Motion Correction → Patch CTF Estimation. Always pilot Patch Motion + Patch CTF with `Only process this many movies` first.
2. If only aligned micrographs exist: Import Micrographs → Patch CTF Estimation. Accept that RBMC will not be available.
3. Import Particle Stack:
   - Particle meta path: the RELION particles STAR.
   - Particle data path: the directory holding the `.mrcs` files.
   - Source Exposures: the cryoSPARC-aligned micrographs (mandatory if you want micrograph linkage).
   - Microscope parameter overrides: only set if the STAR is missing them or you know the STAR is wrong.
   - Data Sign: set to match RELION's convention (typically `-1` if RELION did the extraction).
   - Tune `Length of Mic. path suffix to cut` and `Length of Part. path suffix to cut` until matched-micrograph count in the event log equals the expected particle count.
4. (Recommended) Extract from Micrographs inside CryoSPARC at the chosen working box / pixel size.
5. Single Homogeneous Refinement against the RELION map to bring particles into a self-consistent CryoSPARC pose space.
6. Optionally: Reference Based Motion Correction — only if the raw movies were imported in step 1.

Validation:
- [ ] Inspect Picks on a few representative micrographs — particles overlap real density and are not Y-flipped.
- [ ] 2D Classification yields class averages with the expected views; junk vs signal looks normal.
- [ ] Initial Homogeneous Refinement converges to a resolution consistent with (or better than) the RELION refinement that produced these particles.
- [ ] FSC, mask plot, and viewing-direction plot in the refinement look honest (see `10_postprocessing.md` for what "honest" means here).

---

## 4. CryoSPARC → RELION

### 4.1 The bridge pattern

CryoSPARC does not natively write a RELION STAR file for general use. The community-standard bridge for >5 years has been **Daniel Asarnow's `pyem` package**, specifically `csparc2star.py` (forum: "csparc2star.py" thread series, including the "final update" thread). Forum guidance for "How do I move a refinement to RELION 3.1?" "How do I do Bayesian Polishing on cryoSPARC particles?" "How do I export to RELION post-process?" all route to the same script.

Operationally, the bridge does:
- Read one or more `.cs` files (a base particle file plus passthrough/aux `.cs` files from upstream jobs as needed).
- Map CryoSPARC fields to `rln*` fields; emit `data_optics` + `data_particles` for RELION 3.1+ (or `data_` for RELION 3.0 with a flag).
- Optionally merge fields from an input particles STAR (e.g. `--copy-micrograph-coordinates`), which is the historic fix for missing `rlnMicrographName` after certain CryoSPARC jobs.
- Optionally inject a box size (`--boxsize`), which is required because some CryoSPARC outputs do not store the original RELION extraction box; without it, RELION may refuse to load (`ObservationModel::getBoxSize: box sizes not available`).
- Optionally export coordinates / trajectories suitable for RELION's Bayesian Polishing — explicitly experimental at the time of the linked forum thread, requires a separate wiki recipe, not extensively tested.

**Treat all of the above as a pattern.** Specific flag names have churned: `--passthrough` was removed; multi-file syntax was added; the merge-key behavior for `--copy-micrograph-coordinates` has broken and been fixed across pyem versions; `rlnMicrographGainName` errors appeared on movies-without-gain inputs and required pyem updates. Always:
- Confirm `csparc2star.py --help` on the installed pyem version before scripting it.
- Pin the pyem version in any pipeline you depend on; do not silently upgrade.
- Run on a small dataset first and validate (Section 4.4) before running on the production set.

CryoSPARC also exposes a programmatic `cryosparc.star` helper in `cryosparc-tools` (see `reference/cryosparc-tools/cryosparc/star.py`) that knows the RELION dtype table and can read/write STAR files. It is not a finished `cs → star` converter on its own — it is the low-level I/O layer — but it is the right building block for in-house bridges and for External Jobs that need to emit STAR files.

### 4.2 What to actually export

The receiving RELION step decides the export shape:

| RELION-side goal | Minimum CryoSPARC outputs to export | Bridge notes |
|---|---|---|
| RELION PostProcess | Refinement's `map_half_A` + `map_half_B` + an FSC mask | Maps go to disk via the GUI download (`Outputs` panel of the job dialog) or `cryosparc-tools` `download` helpers. STAR not needed. Half-maps must be in the same box/pixel size as RELION expects. |
| RELION Refine3D / further classification | Particles `.cs` (with `alignments3D`) → STAR + the corresponding particle stack `.mrcs` files | The bridge has to emit RELION-style image names (`<index>@<path>`). `--boxsize` typically required to populate `rlnImageSize`. |
| RELION CtfRefine / beam-tilt / aberrations | Same as Refine3D, with the understanding that higher-order CTF will be re-fit in RELION | Per Import-Particle-Stack docs, this is the *correct* step in the round-trip — do not try to carry CryoSPARC's higher-order terms over. |
| RELION Bayesian Polishing | Particles STAR with movie linkage + per-particle trajectories + a PostProcess STAR + motion-corrected micrograph STAR | Forum thread documents the pyem wiki recipe ("Using cryoSPARC output for Bayesian Polishing"); marked experimental. Requires raw movies to have been imported in CryoSPARC; particles must carry trajectory metadata. Validate end-to-end before relying on it. |

### 4.3 Common bridge-time mistakes

These come straight out of the forum corpus and the troubleshooting topic:

- **Missing `rlnMicrographName`.** Some CryoSPARC jobs (notably certain pre-extraction or selection paths) emit `.cs` files without a usable micrograph-name column. csparc2star.py then fails with `KeyError: 'rlnMicrographName'`. Workaround in the forum thread: pass the original imported particles STAR via `--copy-micrograph-coordinates`, or feed the appropriate passthrough `.cs` so the merge brings the field across.
- **Missing `rlnImageSize`.** RELION 3.1+ refuses to load particles without `_rlnImageSize` in `data_optics`. Use the bridge's `--boxsize` flag (matching the actual particle box) to inject it.
- **`.mrc` vs `.mrcs` extension.** CryoSPARC writes particle stacks as `.mrc`. RELION expects multi-particle stacks as `.mrcs`. Some forum recipes rename / symlink the files; some bridge versions handle the rename. Validate that the path RELION resolves actually exists and opens.
- **Wrong box / unmatched downsampled particles.** If you exported downsampled particles but want to keep the original-box angles, you have to merge the angles `.cs` against the downsampled `.cs` and inject the correct `--boxsize` (forum: csparc2star.py multi-input usage example).
- **Optics-table parameters lost.** If you converted with a pyem version that did not yet handle optics fully, the resulting STAR may have an empty/partial `data_optics`. Symptom: RELION reports `data_micrographs` with no particle data, or refuses to load. Fix: update pyem or post-process the STAR to add the optics table.
- **Stale forum advice.** Posts from 2018–2020 about CryoSPARC v0/v1/v2 export are *not safe* references for current versions; `.cs` format and CryoSPARC's higher-order CTF model both changed materially in v3.x and again across v4.x → v5.0. Treat any forum recipe as a starting point, not an executable script.
- **Bayesian-polishing experimental support.** Per the linked forum announcement: "I believe it is working, but it has not been tested extensively." Validate on a small subset, against a known good RELION-only polishing baseline, before betting a paper on it.

### 4.4 Validation after CryoSPARC → RELION

- [ ] Particle count in the STAR matches the count in CryoSPARC (or matches your stated subset).
- [ ] `data_optics` has `rlnImageSize`, `rlnImagePixelSize`, `rlnImageDimensionality = 2`, `rlnVoltage`, `rlnSphericalAberration`, `rlnAmplitudeContrast`. Missing any of these is an immediate red flag.
- [ ] `rlnImageName` paths resolve from RELION's project root (check a few with a file existence test). The `.mrcs` extension matches the actual files.
- [ ] One particle picked at random — open in 2D viewer, confirm it looks like a particle and is in the orientation you expect.
- [ ] A short Refine3D with local searches converges to the same approximate resolution as the CryoSPARC refinement you started from. A large drop (e.g. 5 Å → 17 Å) means the bridge lost information — common cause is wrong box / wrong pixel size, see the "Exporting Map and Particle File to RELION 3.0" forum thread where this exact symptom was traced to `--boxsize`.

---

## 5. Round-trip decisions — when to bother

### 5.1 Worth round-tripping

- **RELION Bayesian Polishing on a CryoSPARC-aligned particle set.** This is the most-cited reason to round-trip. Bridge support exists but is experimental; raw movies must be imported in CryoSPARC up front.
- **A specific RELION classification or refinement mode that CryoSPARC does not offer**, when you also want the speed of CryoSPARC's earlier stages.
- **Side-by-side method comparison for a paper.** Reproduce the result in both packages from the same particles to demonstrate robustness.
- **Compatibility with collaborators or downstream tools that consume RELION outputs.** This is a workflow decision, not a scientific one — accept the bookkeeping.

### 5.2 Not worth round-tripping

- **"Polishing for polishing's sake"** when CryoSPARC's RBMC is available and the raw movies are still on disk. RBMC is the native equivalent; running it inside CryoSPARC avoids every bridge failure mode.
- **A sharpening or visualization tweak.** The right scope here is CryoSPARC's Sharpening Tools, DeepEMhancer wrapper (see `23_external_jobs.md` and `10_postprocessing.md`), or external visualization software. Round-tripping just to use RELION PostProcess for the cosmetic step has a low signal-to-noise ratio.
- **A re-refinement to "see if it changes."** It will, slightly, in either direction. That is not a scientific result.
- **Carrying higher-order CTF aberrations between packages.** The official guidance is that they do not transfer; the correct response is to re-fit on the receiving side, not to round-trip through both.
- **Bug-hunting an upstream CryoSPARC problem.** Round-tripping rarely diagnoses the original issue and adds new failure modes. Use `15_troubleshooting.md` and `17_error_lookup.md` first.

### 5.3 Validation checks after each direction

After **RELION → CryoSPARC** (in addition to the import runbook checks above):
- [ ] Inspect Picks shows particles on density, not on background or off the field of view.
- [ ] Patch CTF defocus distribution matches RELION's defocus range to within reasonable scatter.
- [ ] A short Homogeneous Refinement against the RELION map gives a resolution and FSC shape consistent with the RELION refinement.
- [ ] Viewing-direction plot does not show a sudden new preferred orientation — that is a coordinate-convention or pose-conversion smell.

After **CryoSPARC → RELION** (in addition to the bridge validation checks above):
- [ ] RELION Refine3D with local searches from the imported angles converges quickly. Slow convergence to a worse map = wrong origin convention or wrong pixel size.
- [ ] PostProcess resolution from CryoSPARC half-maps is close to CryoSPARC's reported resolution (small differences from mask/B-factor choice are expected; large differences signal a problem).
- [ ] Higher-order CTF, if you ran CtfRefine, materially improves resolution after a second Refine3D — confirms the re-fit was needed and worked.

---

## 6. Failure modes table

| Symptom | Likely metadata/path layer | First checks | Escalation / source |
|---|---|---|---|
| `KeyError: 'rlnMicrographName'` from csparc2star.py | Bridge: input `.cs` lacks micrograph-name column (some pre-extraction or selection jobs) | Pass the original imported particles STAR via the bridge's coordinate-merge flag; or include the appropriate passthrough `.cs` | Forum: "csparc2star.py rlnMicrographName error" thread |
| `KeyError: 'rlnMicrographGainName'` from csparc2star.py movie/polishing path | Bridge: movies were imported without a gain reference (e.g. already-corrected Falcon data) | Provide a dummy/estimated gain reference, or upgrade pyem to a version that tolerates absent gain | Forum: "Experimental support for RELION Bayesian polishing in csparc2star.py" thread |
| `ObservationModel::getBoxSize: box sizes not available` in RELION 3.1 | Bridge: STAR has no `_rlnImageSize` in `data_optics` | Re-run the bridge with the correct `--boxsize`; if multi-particle-size, run per-subset and merge | Forum: "How to import cryoSPARC particle coordinates in RELION 3.1" thread |
| `Cannot read file >J10/extract/…mrcs It does not exist` in RELION | Path: file extension is `.mrc` on disk, STAR says `.mrcs` (or symlinks are not where RELION expects) | Confirm what RELION resolves the path to; symlink/copy `.mrc` → `.mrcs`; rerun the bridge with the matching extension | Forum: "csparc2star output relion compatibility" thread |
| RELION refinement on bridged particles converges to much worse resolution than CryoSPARC | Bridge or units: wrong box, wrong pixel size, or origin convention not converted | Try `--boxsize` matching the actual particle box; verify pixel size in `data_optics`; verify a single particle pose visually | Forum: "Exporting map and particle file to RELION 3.0" thread (symptom resolved by box-size correction) |
| Imported RELION particles "do not align" in CryoSPARC | Linkage or units: wrong `rlnMicrographName` suffix, wrong pixel scaling, Y-flip | Re-tune `Length of Mic. path suffix to cut` and `Length of Part. path suffix to cut`; check coordinate scaling; spot-check Inspect Picks | `02_import.md`, `15_troubleshooting.md` |
| Inspect Picks shows blank thumbnails after import of RELION coords | Picks: TIFF Y-flip after CryoSPARC re-alignment; or wrong source micrographs connected | Compare a RELION-side micrograph with the cryoSPARC-aligned one; if Y-flipped, fix coordinate convention before extraction | `18_decision_trees.md` (Tree 1 red flags), forum: import digest |
| Imported particles match micrographs but defocus distribution looks bizarre | CTF: import inherited an old/incompatible higher-order CTF, or pixel size mismatch | Re-run Patch CTF in CryoSPARC against your cryoSPARC-aligned micrographs; use those CTFs, not the imported ones | Import Particle Stack docs (higher-order CTF caveat) |
| Bridge ran fine but RELION 3D Classification gives a single occupancy class | Per v4.2 fix: 3D Classification in earlier CryoSPARC builds emitted extraneous `alignments3D` that confused csparc2star.py's class assignment | Update CryoSPARC to v4.2+ before exporting; re-run the bridge | `reference/release_notes/markdown/v4.2.md` |
| `csparc2star.py` traceback referencing `set_index(key)` / `None of [None] are in the columns` | Bridge: merge key not present in the secondary file (often `--copy-micrograph-coordinates` against a STAR that does not have the right column) | Drop the merge flag and re-run plain; if you need micrograph coords, pass the correct passthrough `.cs` instead of (or in addition to) the STAR | Forum: "converting to star file" thread |
| RELION PostProcess result is dramatically different from CryoSPARC's automatic sharpened map | Postprocessing semantics: different masks, different B-factor choice, different FSC correction | Re-make a tight mask in RELION matching CryoSPARC's; quote the corrected FSC, not the tight; expect small differences | `10_postprocessing.md` |

When a row above does not match: capture the exact error text + the pyem version + the CryoSPARC version + the upstream job type + a one-line description of the bridge invocation. That is the minimum the troubleshooting topic (`15_troubleshooting.md`) needs to make further progress.

---

## 7. Common mistakes (long-form)

- **Treating old forum advice as current.** The most cited interop forum threads span 2018–2024 and predate multiple breaking changes in both pyem (`--passthrough` removed, multi-file syntax added, optics-table emission added) and CryoSPARC (v3.1's optics-aware STAR import, v3.3's anisotropic-magnification support in Global CTF Refinement, v4.x changes to `.cs` schema, v4.2 fixes to `alignments3D` in 3D Classification). Quote forum advice as a starting point only; check the current `csparc2star.py --help` and the relevant `reference/release_notes/markdown/v*.md`.
- **Mismatched pixel/box silently kills resolution.** Bridges happily emit a STAR with wrong (or absent) pixel size and box size; RELION will load it (sometimes) and refine to noise. Always validate `data_optics` and a quick local-search Refine3D before scaling up.
- **Missing the source movies/micrographs.** If you do not import movies on the CryoSPARC side, RBMC is unavailable and Bayesian Polishing on the RELION side becomes much harder. If raw movies still exist on the original storage, link them in before importing particles, even if you "just want to look at it."
- **Broken paths after a project move.** Both Import Movies and Import Particle Stack symlink rather than copy. Moving the raw data or the project breaks the link silently. See `24_disk_and_storage.md` for the storage-side rules; the symptom on this page is "particles import but Patch Motion / Extract fails to open files."
- **Wrong coordinate / origin / angle convention.** RELION 3.1+ uses `rlnOriginXAngst` (Å), older RELION uses `rlnOriginX` (pixels). Some bridge versions assumed pixels; check that the `data_optics` block contains the angstrom-convention origin fields if you target RELION 3.1+. Visualizing a single particle and confirming the pose in both packages is the cheapest sanity check.
- **Optics-table mismatch.** Importing a RELION 3.1+ STAR with one optics group into a CryoSPARC project where exposure groups were set differently (e.g. by AFIS regex) leads to mis-assigned beam-tilt downstream. Set CryoSPARC exposure groups deliberately at import; do not assume the import "did the right thing" from the optics table.
- **Treating map postprocessing as equivalent.** CryoSPARC's automatic sharpening and RELION's PostProcess differ in mask construction, FSC correction (cryoSPARC's noise-substitution corrected FSC vs RELION's), and B-factor choice. A "better-looking" map on the other side is not evidence of more signal; the corrected FSC is. See `10_postprocessing.md` for what to quote and what to ignore.
- **Skipping re-extraction.** External (RELION) picks always require Extract from Micrographs inside CryoSPARC before any 2D/3D job (`05_extraction_2d.md`). Skipping this leaves per-particle CTF unset and exposure-group linkage broken.

---

## 8. Runbooks / checklists

### 8.1 Import RELION particles into CryoSPARC
See Section 3.4 above for the full version. Compressed checklist:
- [ ] Raw movies imported (if available) → Patch Motion → Patch CTF.
- [ ] STAR pixel size, voltage, Cs, dose confirmed.
- [ ] Import Particle Stack with cryoSPARC-aligned mics as Source Micrographs; path suffixes tuned; Data Sign set per RELION convention.
- [ ] Extract from Micrographs inside CryoSPARC.
- [ ] Homogeneous Refinement against the RELION map as a consistency check.
- [ ] (Optional) Reference Based Motion Correction.

### 8.2 Export CryoSPARC particles + map to RELION
- [ ] Decide which RELION step you are feeding (PostProcess, Refine3D, CtfRefine, Polishing); that decides the export shape.
- [ ] Confirm pyem / csparc2star.py is installed and pinned; run `csparc2star.py --help`.
- [ ] Locate the right `.cs` files: the final refinement's particles `.cs` (with `alignments3D`) plus any passthrough you need for `rlnMicrographName`.
- [ ] Run the bridge with `--boxsize` matching the actual particle box; emit RELION 3.1+ format unless you have a specific reason to target 3.0.
- [ ] (If needed) Use `--copy-micrograph-coordinates` against the original imported particles STAR to repopulate missing fields.
- [ ] Confirm the resulting STAR has a populated `data_optics` block and `data_particles` block.
- [ ] Place particle stacks (`.mrcs`) where the STAR's `rlnImageName` paths resolve from RELION's project root.
- [ ] Sanity-check by visualizing one particle + running a short local-search Refine3D.

### 8.3 Compare refinements between CryoSPARC and RELION
- [ ] Same particles, same box, same pixel size, same mask convention.
- [ ] Use CryoSPARC's corrected FSC (not the tight-masked curve) as the CryoSPARC-side resolution claim.
- [ ] Use RELION's PostProcess corrected FSC as the RELION-side claim.
- [ ] Generate matching masks on both sides if possible; the tight-mask FSC otherwise differs for reasons unrelated to the refinement.
- [ ] Treat a < ~0.2 Å difference as noise; treat a multi-Å gap as a real difference worth investigating (likely mask, alignment, or convergence).
- [ ] See `10_postprocessing.md` for the "five FSC curves" framing and what constitutes honest reading.

### 8.4 Recover from STAR / path errors
- [ ] Reproduce the bridge invocation with `--loglevel debug` (or the equivalent verbose flag for the installed pyem version).
- [ ] Capture the full traceback. Many failures point at a single missing column (`rlnMicrographName`, `rlnMicrographGainName`) — fix that column's source, not the bridge.
- [ ] If the receiving RELION job complains about file paths: print one `rlnImageName` from the STAR, manually check whether RELION can open it from its project root.
- [ ] If RELION 3.1+ complains about box size or optics: open the STAR in a text editor, confirm the `data_optics` block has `_rlnImageSize`, `_rlnImagePixelSize`, `_rlnImageDimensionality`.
- [ ] If symlinks are involved: verify the resolved physical paths exist and are readable from the worker shell as the relevant user (consistent with the general filesystem-vs-metadata triage rule in `02_import.md` and `15_troubleshooting.md`).
- [ ] If everything else looks right and refinement still degrades, the cause is almost always wrong box, wrong pixel size, or wrong origin units. Re-run the bridge with explicit values.

---

## 9. Advisor defaults and red flags

### Defaults

- **Prefer the cryoSPARC-native path** when both sides are options. RELION → CryoSPARC import + CryoSPARC RBMC + CryoSPARC Global CTF Refinement is more reliable than a round-trip through RELION Polishing in the median case.
- **Always re-extract** after importing RELION coords, unless you have a specific reason not to.
- **Always re-fit Global CTF** on the receiving side of any round-trip if higher-order aberrations matter.
- **Always pin the pyem version** and the CryoSPARC version when documenting a bridge workflow; record both in lab notebooks or scripts.
- **Always validate on a small subset** before running a bridge or a re-extraction at full scale.
- **Always quote the corrected FSC**, in both CryoSPARC and RELION, when comparing refinements.

### Red flags (stop and triage)

- A bridge succeeds silently but RELION refinement resolution drops by >2 Å on the same particles.
- Inspect Picks shows blanks or Y-flipped picks after a RELION→cryoSPARC import.
- `data_optics` in the bridged STAR is empty, partial, or has obviously wrong `rlnImageSize` / `rlnImagePixelSize`.
- A forum recipe being copy-pasted from 2019–2020 without checking against current pyem / current CryoSPARC.
- A "higher-order CTF transfer" claim — the official guidance is that it cannot be done; re-fit instead.
- Anyone "just re-running" with `csparc2star.py` after a CryoSPARC update without re-testing the pipeline.
- Bayesian Polishing being treated as a standard workflow rather than experimental.

---

## 10. Cross-links

- Canonical import recipe, gain refs, exposure groups, path-suffix mechanics: `02_import.md`
- External picks need Extract from Micrographs before 2D/3D: `05_extraction_2d.md`
- FSC honesty, sharpening differences vs RELION PostProcess, mask cautions: `10_postprocessing.md`
- Programmatic STAR I/O via `cryosparc.star`, External Job orchestration for custom bridges: `13_cryosparc_tools_api.md`
- Wrapper jobs (DeepEMhancer etc.) and External Jobs as the right place to wrap a RELION binary: `23_external_jobs.md`
- Symlinks, project moves, raw-data lifetime: `24_disk_and_storage.md`
- Troubleshooting mental model: `15_troubleshooting.md`
- Decision tree for "which import branch?" with the RELION red flags: `18_decision_trees.md`
- Error-string lookup: `17_error_lookup.md`

---

## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

- `topic_plan.md`
- `plan.md`
- `02_import.md`
- `05_extraction_2d.md`
- `10_postprocessing.md`
- `13_cryosparc_tools_api.md`
- `15_troubleshooting.md`
- `18_decision_trees.md`
- `23_external_jobs.md`
- `24_disk_and_storage.md`
- `17_error_lookup.md`
- `reference/cryosparc-tools/cryosparc/star.py`
- `reference/cryosparc-tools/CHANGELOG.md`
- `reference/cryosparc-tools/docs/guides/jobs.ipynb`
- `reference/release_notes/markdown/v4.0.md`
- `reference/release_notes/markdown/v4.1.md`
- `reference/release_notes/markdown/v4.2.md`
- `reference/release_notes/markdown/v4.3.md`
- `reference/release_notes/markdown/v4.4.md`
- `reference/release_notes/markdown/v4.5.md`
- `reference/release_notes/markdown/v4.6.md`
- `reference/release_notes/markdown/v5.0.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__import__job-import-particle-stack.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__import__job-import-movies.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__import__job-import-micrographs.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__utilities__job-particle-sets-tool.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__utilities__job-exposure-sets-tool.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__post-processing__job-sharpening-tools.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-ctf-refinement.md`
- `docs/per_page/application-guide__downloading-and-exporting-data.md`
- `docs/per_page/application-guide__inspecting-job-data.md`
- `docs/forum_threads/digests/forum_import.md`
- `docs/forum_threads/digests/forum_scripting.md`
- `docs/forum_threads/digests/forum_cryo-em-data-processing.md`
- `docs/forum_threads/digests/forum_troubleshooting.md`
- `docs/forum_threads/raw/import/01_2687_how-to-import-particles-from-relion.json`
- `docs/forum_threads/raw/import/02_3073_csparc2star-py-final-update.json`
- `docs/forum_threads/raw/import/03_2026_export-data-to-relion-in-v2.json`
- `docs/forum_threads/raw/import/04_2928_exporting-map-and-particle-file-to-relion-3-0.json`
- `docs/forum_threads/raw/import/05_9848_experimental-support-for-relions-bayesian-polishing-in-csparc2star-py.json`
- `docs/forum_threads/raw/import/06_5528_how-to-import-cryosparc-particle-coordinates-in-relion-3-1.json`
- `docs/forum_threads/raw/import/07_4978_csparc2star-output-relion-compatibility.json`
- `docs/forum_threads/raw/import/09_7273_converting-to-star-file.json`
- `docs/forum_threads/raw/import/10_3750_csparc2star-py-rlnmicrographname-error.json`
- `docs/forum_threads/raw/3d-reconstruction/09_4224_how-to-go-from-cryosparc-refinement-to-relion-post-processing.json`
- `docs/forum_threads/raw/cryo-em-data-processing/03_3241_bayesian-polishing-of-cryosparc-processed-particles.json`
