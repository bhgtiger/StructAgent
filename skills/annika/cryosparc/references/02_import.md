# Topic 02 — Import

## Scope
How to bring data into cryoSPARC cleanly: deciding what to import, getting metadata right, using gain references and exposure groups correctly, and avoiding the classic import/linking mistakes that quietly break downstream work. Error-string lookup belongs in `17_error_lookup.md`; broader debugging logic belongs in `15_troubleshooting.md`.

## Fast preflight before debugging an import
Do this before changing parameters, especially when the symptom is a traceback or a launch failure rather than obviously wrong coordinates:

1. **Check the first failing log.** For import job runtime errors, start with the Event Log and `job.log`; for worker launch/path failures, check `cryosparcm log command_core`; for cryosparc-tools imports, also check `cryosparcm log command_vis`.
2. **Confirm the exact cryoSPARC version.** Import behavior is version-shaped: EER, TIFF, symlink/project-path handling, exposure groups, and some Import 3D Volume edge cases have all changed across v4.x–v5.x.
3. **Test the path from the worker shell as the cryoSPARC owner.** A path that exists on the master but not the worker is the most common real cause behind `invalid path`, `file not found`, failed symlinks, and missing imported files.
4. **Separate filesystem errors from metadata errors.** If the file cannot be opened, fix mount/permission/symlink first. If the file imports but particles land wrong or reconstructions fail, debug pixel size, coordinate scaling, Y-flip, CTF, and path-suffix trimming.

## Decision surface — what am I importing?
Before opening an import job, answer one question: **what are my inputs, and what is the earliest downstream job I want to reach?** Pick the import type from that, not from what is already on disk.

Four practical cases:
1. **Raw movies** (EER / TIFF / MRC stacks).
   - Use Import Movies.
   - Required for any motion-correction workflow inside cryoSPARC, and for any job that needs per-frame information later (e.g. Reference Based Motion Correction).
2. **Pre-aligned micrographs** (already motion-corrected outside cryoSPARC).
   - Use Import Micrographs.
   - Fine for picking, extraction, 2D/3D, and refinement, but RBMC and any per-frame job will not be available.
3. **Particle coordinates / particle stacks from another package** (most often RELION).
   - Use Import Particle Stack.
   - The linkage between particles and their source micrographs is the part most often misconfigured.
4. **Imported results from another cryoSPARC instance / job** (volumes, masks, full result groups).
   - Use Import 3D Volumes, Import Result Group, etc.
   - These are not movie/micrograph imports and have their own narrower failure modes (e.g. missing volume slots).

If multiple paths look workable, prefer the one that re-runs preprocessing inside cryoSPARC, because the downstream tooling (Patch CTF, RBMC, exposure-group utilities, denoiser) is consistent that way.

## Canonical RELION -> cryoSPARC recipe
This is the local corpus's most consistent recommendation. Use it when starting from a RELION project but wanting cryoSPARC's downstream:

1. **Import the raw movies into cryoSPARC** (not the RELION-aligned micrographs).
2. **Run Patch Motion Correction and Patch CTF Estimation in cryoSPARC.**
3. **Import the RELION particle positions** (`particles.star`) using Import Particle Stack, with the cryoSPARC-aligned micrographs connected as Source Micrographs.
   - Set `Length of Mic. path suffix to cut` and `Length of Part. path suffix to cut` so the trailing path pieces match exactly. Expect to iterate.
   - Watch for the **TIFF Y-flip caveat** below if positions came from RELION/MotionCor2/Warp alignment and you re-aligned in cryoSPARC.
4. **Extract particles in cryoSPARC** from the now-linked positions.
5. **Run a single Homogeneous Refinement against the RELION map** to bring the particles into a self-consistent cryoSPARC pose space.
6. **Run Reference Based Motion Correction (RBMC)** — only if the raw movies were imported in step 1.

Two things this recipe is not:
- It is not a full RELION/cryoSPARC interop guide; see the future `27_relion_interop.md` for export and round-tripping details.
- It is not the only valid path: if you genuinely cannot import movies (e.g. only motion-corrected micrographs remain), skip steps 1–2 and accept that RBMC is unavailable.

## Metadata essentials
Most "silent" import failures are metadata problems. Get these right before debugging anything else.

### Pixel size
- The pixel size in the import job must match the pixel size of the data on disk, including any super-resolution / binning state.
- If coordinates were picked on **binned** images but the cryoSPARC-aligned micrographs are at **unbinned super-resolution**, X/Y coordinates need to be scaled (e.g. 2x) before linking, and origin/shift columns scale the same way. Doing only the coordinates and missing the origins produces particles whose centers look almost right but are off by a few pixels.
- Mismatches typically present as "particles are roughly in the right places but the reconstruction is garbage."

### Coordinate scaling: binned vs super-res
- Decide once whether your downstream pipeline runs on super-res or binned data, then keep coordinates in that frame consistently.
- If imported coordinates were generated against one frame and the source micrographs in cryoSPARC are in another, particle alignment will be visually plausible but quantitatively wrong.

### Origin / coordinate conventions
- Coordinates and origins (`rlnCoordinateX/Y`, `rlnOriginX/Y`) live in micrograph-pixel space; particle box origins from cryoSPARC refinement are in refinement-box space, not particle-box space. When round-tripping out, this is what the `--boxsize` argument in `csparc2star.py` exists to correct. Inside cryoSPARC, the same idea applies: be deliberate about which box and pixel size each coordinate set lives in.

### Defocus / CTF preservation
- Imported particle metadata can carry per-particle defocus/CTF, but **only fields that are actually present in the input** survive. Selection jobs and some intermediate steps in either package can drop micrograph names or CTF fields, which is why bare `imported_particles.cs -> .star` round-trips sometimes lose `rlnMicrographName`, defocus, etc.
- Practical rule: if you intend to use cryoSPARC's CTF downstream, **re-run Patch CTF in cryoSPARC** after import rather than relying on inherited CTF from another package.

### Path suffix trimming
- The Import Particle Stack job matches particles to source micrographs by the *remaining* path string after a configurable number of trailing characters is cut from each side.
- This is the single most common source of "imported particles do not align with source micrographs."
- Practical recipe:
  - Open the particle file, look at the example micrograph name (e.g. `…micrograph01_A.mrc`).
  - Look at the cryoSPARC-aligned micrograph name (e.g. `…micrograph01_rigid_aligned.mrc`).
  - Set particle suffix cut to the length of `_A.mrc` (6) and micrograph suffix cut to the length of `_rigid_aligned.mrc` (18) — so what remains on each side is identical.
  - Expect the first run to fail; tweak and re-run.

### TIFF Y-flip caveat
- cryoSPARC reads TIFF images with positive-y as the slow axis; RELION (and several other packages) read y in the opposite order. Consequence: if you re-align TIFF/EER movies inside cryoSPARC and then import particle coordinates that were picked against RELION/MotionCor2/Warp-aligned versions of the same movies, particles end up flipped vertically in the cryoSPARC frame.
- Mitigations:
  - If you can avoid re-aligning movies inside cryoSPARC (i.e. import the already-motion-corrected MRC micrographs from RELION), the flip does not occur.
  - If you must re-align in cryoSPARC, enable `flip micrograph in Y` in the Extract Particles job when extracting against imported coordinates.
- MRC micrograph imports do not have this issue; the flip is specifically tied to how the TIFF byte order is interpreted.

### Header check / corrupt files
- Import Movies / Import Micrographs have a `Skip header check` parameter (enabled by default from v4.2 onward) that bypasses a validation pass on the file headers. Leave it on for normal imports; if you suspect corruption, use the Check for Corrupt Micrographs / Check for Corrupt Particles jobs rather than fighting the header check.

## File-type basics
### MRC
- The straightforward case. Either single micrographs or `.mrcs` stacks.
- No Y-axis convention surprise relative to RELION.
- Particle stacks imported into cryoSPARC are symlinked into the import job's `imported/` directory; the symlink target must resolve from the worker, not only the master.

### TIFF
- Common for movie data.
- Y-axis byte-order convention differs from several other packages — see the Y-flip caveat above.
- TIFF gain references are supported (the import job tooltip was corrected to reflect this in v5.0).

### EER
- Native support, including Falcon 4 and (since v4.5) Falcon C `.eer` movies.
- EER imports have had specific bug history: Falcon C EER files were fixed to no longer fail on import in v4.6.2.
- Upsampling and fractionation choices are made in the motion-correction stage, not in the import itself; RBMC also exposes an EER upsampling override.

## Gain references
- Use a gain reference whenever the imported movies are not already gain-corrected. The movie metadata's `is_gain_corrected` flag is what cryoSPARC checks; if that is set incorrectly the rest of the pipeline silently degrades.
- The gain reference goes through standard `flip_x` / `flip_y` / `rotate` controls. If the gain orientation is wrong, motion-corrected micrographs typically look obviously striped or patterned — fix at import, not later.
- Live-specific note: older versions could fail to export accepted exposures from a Live session if no gain reference was specified; this was tightened in v5.0.x. If you do not have a gain reference, ensure that is intentional.

## Exposure groups
- Exposure groups are the right unit for per-group CTF refinement, beam-tilt correction, and AFIS-style optics-grouped processing.
- Two sources for grouping at import time:
  - **EPU AFIS beam shift** values, which Import Movies / Import Micrographs can read directly (since v4.4). Existing datasets can be patched with Import Beam Shift.
  - **Regex-based grouping** on filename, handled in Exposure Group Utilities (unmatched items collapse into a single residual group from v4.0.2 onward).
- From v5.0, exposure-group IDs increment from a project-level counter, so newly created groups will not silently collide with older ones.
- Practical default: if there is any chance you will run global or local CTF refinement with optics groups, set up exposure groups at import or immediately after. Retrofitting them later is more work than doing it once.

## What must be connected for each downstream goal
A compact table — use it when planning the import:

| Downstream job / goal | Minimum object that must be imported/connected |
|---|---|
| Patch Motion + Patch CTF | Raw movies (Import Movies). |
| Picking on existing micrographs | Imported or motion-corrected micrographs. |
| Extraction from imported coordinates | Imported particle metadata + source micrographs, correctly linked by path-suffix trimming. |
| Local Motion Correction | Particles linked to imported movies/micrographs (the linkage is what enables local motion). |
| Reference Based Motion Correction (RBMC) | Raw movies imported into cryoSPARC + particles that trace back to those movies + a refinement to provide the reference. RBMC will not work from imported micrographs alone. |
| Global / Local CTF Refinement with optics groups | Exposure groups configured (AFIS beam shift or regex), so per-group parameters can be fit. |
| Refinement starting from external particles only | Import Particle Stack with `Ignore raw data` enabled; downstream jobs that need movies/micrographs will still need a separate import. |
| Round-trip back to RELION later | Either Patch CTF in cryoSPARC and use cryoSPARC's CTF, or carry the original CTF through and accept its limits; do not assume a half-finished CTF chain will round-trip cleanly. |

## Common import / linking failure shapes
Keep this section short on purpose — for specific error strings, use `17_error_lookup.md`.

- **"Imported particles do not align with source micrographs."** Almost always wrong path-suffix trimming between particle metadata and source micrographs, or a binning/super-res mismatch in coordinates.
- **"Import worked, but the downstream movie-dependent job (e.g. RBMC, Local Motion) fails."** Movies were never imported; only micrographs are connected. Re-import the raw movies and re-link.
- **"Reconstruction from imported particles is garbage even though picks look fine."** Likely Y-flip (TIFF re-aligned in cryoSPARC vs RELION-aligned coords), wrong pixel size, or wrong CTF assumption. Check those three before anything else.
- **"Cannot find match for FoilHole_…."** Path-suffix join is producing a name that does not exist on the micrograph side. Inspect what string actually remains after the cut on each side; the goal is exact equality.
- **"Gain reference orientation wrong."** Motion-corrected micrographs show stripes or grid patterns. Adjust gain `flip_x`/`flip_y`/`rotate` at import.
- **"Live session can't export without a gain reference"** (older versions). Update or supply a gain reference.

For any of these that present as a Python traceback rather than a visible behavioral wrongness, treat the symptom as version-shaped first and consult `17_error_lookup.md` and `15_troubleshooting.md`.

## Sanity checks immediately after import
Do not wait until refinement to discover a bad import. Before branching into expensive jobs:

- Open a few imported movies/micrographs and confirm orientation, dimensions, pixel size, and obvious gain-correction behavior.
- For imported coordinates, inspect overlays on source micrographs. Check both a center exposure and an edge-case exposure; a Y-flip or suffix-trim mismatch can look plausible on one image and fail globally.
- Compare particle count, exposure count, and rejected/missing file counts against the source manifest or STAR file.
- If importing particles from another package, run a small extraction / 2D classification smoke test before large 3D jobs. Gross coordinate, pixel-size, or CTF mistakes usually show up immediately.
- If the next planned job is RBMC, Local Motion, or Local/Global CTF refinement, verify that movies, source micrographs, CTF metadata, and exposure groups are connected before queueing.

## Filesystem and linking sanity
Imports are unusually sensitive to filesystem behavior because they create the symlinks that the rest of the pipeline depends on:

- Master and worker must resolve the same literal path; symlinks must resolve from the worker shell, not just the master.
- On distributed filesystems, listed UNIX permissions may not match real permissions. `CRYOSPARC_CLI_SKIP_ACCESS_CHECK=true` (v5.0+) can be set when this is the cause.
- Be careful when moving or detaching projects after import — the symlinks inside `imported/` will not follow.

## Version-aware highlights for import
- **v4.0:** Exposure Group Utilities regex grouping collapses unmatched items into one residual group; reduces silent loss when patterns are imperfect.
- **v4.1.2:** Errors reading TIFFs during Import Movies no longer cause abnormal termination.
- **v4.2:** `Skip header check` parameter enabled by default on Import Movies / Import Micrographs; `.mrc.bz2` gain references read correctly in Live.
- **v4.4:** AFIS beam-shift import; Import Particles supports build-time output validation (needed for Workflows); 3D Classification stops producing extraneous fields that broke older `csparc2star.py` runs.
- **v4.5:** Falcon C `.eer` (2k×2k) support added; Import Result Group robustness improved.
- **v4.6.2:** Falcon C EER files no longer fail to import.
- **v5.0:** Import Particle Stack handling of helical `filament_uid` corrected; Import 3D Volumes works for EMDB IDs starting with zero, and (in v5.0.5) no longer fails on integer-type MRC volumes; Import Movies tooltip clarifies TIFF gain support; project-wide exposure-group counter prevents ID collisions.

## Advisor defaults
If a user asks "I have data from package X — how do I get it into cryoSPARC?":
1. Establish the four-case decision: movies, micrographs, particles, or results.
2. Default to importing **raw movies** when they exist, even if alignment was already done elsewhere — it preserves RBMC and Local Motion as options.
3. For RELION particle imports, walk the canonical 6-step recipe above.
4. Force explicit checks on pixel size, coordinate scaling, path-suffix trimming, and (for TIFF) Y-axis convention before debugging anything downstream.
5. Re-run Patch CTF in cryoSPARC if you intend to use cryoSPARC CTF features later; do not rely on inherited CTF metadata.
6. If a downstream symptom is a traceback, send the user to `17_error_lookup.md`; if it is a behavioral wrongness, look first at the metadata essentials above.

## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

- `docs/forum_threads/digests/forum_import.md`
- `15_troubleshooting.md`
- `17_error_lookup.md`
- `reference/release_notes/markdown/v4.0.md`
- `reference/release_notes/markdown/v4.1.md`
- `reference/release_notes/markdown/v4.2.md`
- `reference/release_notes/markdown/v4.4.md`
- `reference/release_notes/markdown/v4.5.md`
- `reference/release_notes/markdown/v4.6.md`
- `reference/release_notes/markdown/v5.0.md`
