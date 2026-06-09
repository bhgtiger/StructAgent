# 16 — RELION <-> cryoSPARC interop

## Scope
The RELION-side view of the RELION<->cryoSPARC bridge: what metadata crosses, what degrades, and the exact mechanics on the RELION end of each direction. RELION->cryoSPARC means exporting particles (STAR + `.mrcs`) or a map (half-maps + mask) into cryoSPARC's *Import Particle Stack* / *Import 3D Volumes*; cryoSPARC->RELION means converting `.cs` (+ passthrough) to a RELION `data_optics`+`data_particles` STAR with `csparc2star.py` (pyem). The cryoSPARC-side detail (the Import recipe, exposure groups, path-suffix tuning, the forum corpus, RBMC) is owned by the **cryosparc** skill's `27_relion_interop.md` — cross-linked, not duplicated here. Convention traps (Euler direction, shift sign, pixel vs box) live in `12_conventions_symmetry.md`.

---

## 1. What crosses the bridge (RELION-side view)

cryoSPARC stores a particle dataset as a `.cs` numpy structured array (plus `passthrough_*.cs` carrying upstream lineage) and writes particle images as `.mrc` stacks. RELION stores the same dataset as STAR files with a `data_optics` block (3.1+) and a `data_particles` block, and writes stacks as `.mrcs`. Most interop pain is one model silently losing fidelity when re-expressed as the other.

| Concept | cryoSPARC | RELION |
|---|---|---|
| Particle metadata | `.cs` (+ `passthrough_*.cs`) | STAR: `data_optics` + `data_particles` |
| Image stack | `.mrc` (one stack per batch) | `.mrcs`, addressed as `index@stack.mrcs` (`Conventions.rst:22-29`) |
| Pose | `alignments3D` (`pose`, `shift`, `psize_A`) | `rlnAngleRot/Tilt/Psi`, `rlnOriginXAngstrom/YAngstrom` (3.1+) (`Conventions.rst:118-119,135`) |
| Pixel/box | on the blob; refreshed on Extract | `rlnImagePixelSize` + `rlnImageSize` in `data_optics` |
| CTF (bulk) | per-particle defocus + CTF model | `rlnDefocusU/V/Angle`, optics-group voltage/Cs/Q0 |
| CTF (higher-order) | cryoSPARC's own beam-tilt/aniso-mag slots | `rlnOddZernike`/`rlnEvenZernike`/`rlnMagMatrix_*` in `data_optics` (`Conventions.rst:148-165`) |
| Mic linkage | result-group connection + symlinks | `rlnMicrographName` path string |
| Optics/exposure groups | exposure groups (AFIS/regex) | optics groups via `rlnOpticsGroup`/`rlnOpticsGroupName` (`Conventions.rst:103-108`) |
| Sharpened map | refinement/Sharpening-Tools `.mrc` | `relion_postprocess` output `.mrc` + separate half-maps + FSC mask |

**Survives a round-trip well:** per-particle defocus, bulk CTF (voltage, Cs, amplitude contrast, pixel size), particle pose (if box/pixel are consistent and origins are converted correctly), micrograph name as a path string (with the right suffix trimming).

**Degrades or does not transfer:**
- **Higher-order CTF aberrations.** cryoSPARC and RELION record beam-tilt / anisotropic-magnification / Zernikes in mutually incompatible formats. After any round-trip you must **re-fit higher-order CTF on the receiving side** (RELION: a fresh CtfRefine job — see `10_ctfrefine_polish.md`). Do not trust transported higher-order terms.
- **Optics-group <-> exposure-group mapping.** Coarse 1:1 correspondence works; per-group beam-tilt values, the anisotropic-mag matrix, and per-group Zernikes do not transfer cleanly. Re-fit.
- **Sharpening / postprocessing.** Different masks, FSC corrections, and B-factor choices. "The postprocessed map" is not a portable artifact — move half-maps + mask and let the receiver redo PostProcess.
- **Per-particle scale, rejected subsets, provenance/lineage** — cryoSPARC concepts with no native RELION equivalent. The receiver sees only a stack + a STAR.

---

## 2. RELION -> cryoSPARC

The cryosparc skill (`27_relion_interop.md`, `02_import.md`) owns the Import-job mechanics. The RELION-side facts you must get right before export:

### 2.1 Two export shapes
- **Particles** for cryoSPARC refinement/classification: the particle STAR (`run_data.star` from Refine3D/Class3D, or the `particles.star` from Extract/Select) + the `.mrcs` stacks it points at. cryoSPARC reads these via **Import Particle Stack** (particle-meta path = the STAR, particle-data path = the `.mrcs` directory; optionally connect cryoSPARC-aligned micrographs as Source).
- **A map** for cryoSPARC validation/local-refine: the two unfiltered half-maps + an FSC mask, imported via cryoSPARC **Import 3D Volumes**. The canonical RELION half-map names are `run_half1_class001_unfil.mrc` / `run_half2_class001_unfil.mrc` (the `--i` example in `relion_postprocess --help`).

### 2.2 Data sign — RELION extraction is light-on-dark
RELION's Extract job inverts contrast by default: `relion_preprocess --invert_contrast` ("Invert the contrast in the input images", `relion_preprocess --help`). So extracted RELION particles are **light protein on dark background**. cryoSPARC's Import Particle Stack exposes a **Data Sign** parameter; set it so cryoSPARC treats already-extracted RELION stacks consistently (cryoSPARC's own doc: "RELION flips particles to be light on dark by default during extraction"). A stack that displays as "inverted" in cryoSPARC 2D thumbnails is almost always a Data Sign mismatch, not a real contrast problem.

### 2.3 Optics group -> exposure group
A RELION optics group (`rlnOpticsGroup` / `rlnOpticsGroupName`, `Conventions.rst:103-108`) maps to a cryoSPARC exposure group. If the RELION project had multiple optics groups (multi-grid / multi-session / AFIS), set exposure groups deliberately on the cryoSPARC side at import or via cryoSPARC's Exposure Group Utilities — downstream Global/Local CTF refinement and RBMC depend on it. STAR files merge by `rlnOpticsGroupName`; groups with different names are renumbered (`Conventions.rst:107-108`).

### 2.4 Path-suffix matching
Import Particle Stack links particles to Source Micrographs by trailing path match on `rlnMicrographName`. cryoSPARC's micrograph paths rarely match RELION's character-for-character; you tune cryoSPARC's "Length of Mic. path suffix to cut" / "Length of Part. path suffix to cut" until the matched count equals the particle count. An off-by-one cut is the most common "no matched micrographs" cause. This is a cryoSPARC-side dial — see `27_relion_interop.md`.

### 2.5 Coordinate scaling
If picks were made on binned images in RELION but micrographs were re-aligned at unbinned super-res in cryoSPARC (the fixture is super-res 0.53 A/pix -> 2x-binned 1.06 A/pix), `rlnCoordinateX/Y` must be scaled (e.g. 2x). Coordinates are in pixels of the aligned/summed (possibly binned) micrograph (`Conventions.rst:137-139`).

---

## 3. cryoSPARC -> RELION (csparc2star.py)

The community bridge is **Daniel Asarnow's pyem `csparc2star.py`**. cryoSPARC does not natively emit a general-purpose RELION STAR. Installed here at `csparc2star.py`.

### 3.1 Flags confirmed live (`csparc2star.py --help`, 2026-06-04)
```
csparc2star.py [-h] [--movies] [--boxsize BOXSIZE] [--class CLS]
               [--minphic MINPHIC] [--stack-path STACK_PATH]
               [--micrograph-path MICROGRAPH_PATH]
               [--copy-micrograph-coordinates COPY_MICROGRAPH_COORDINATES]
               [--swapxy] [--noswapxy] [--invertx] [--inverty]
               [--flipy] [--flipy-pose] [--flipy-ctf] [--cached]
               [--transform TRANSFORM] [--relion2]
               [--strip-uid [STRIP_UID]] [--10k] [--loglevel LOGLEVEL]
               [input ...] output
```

| Flag | What it does (verbatim from `--help`) | RELION-side why |
|---|---|---|
| `[input ...] output` | "Cryosparc metadata .csv (v0.6.5) or .cs (v2+) files" -> "Output .star file" | Pass the particles `.cs` **plus** the `passthrough_*.cs` so columns like the micrograph name merge across. |
| `--boxsize BOXSIZE` | "Cryosparc refinement box size (if different from particles)" | Populates `rlnImageSize` in `data_optics`. **Required when the `.cs` lacks the box**, else RELION aborts: `ObservationModel::getBoxSize: box sizes not available`. |
| `--copy-micrograph-coordinates SRC` | "Source for micrograph paths and particle coordinates (file or quoted glob)" | The fix for a missing `rlnMicrographName` (some pre-extraction/selection `.cs` lack it). Point at the original imported particles STAR (or glob of micrograph STARs). |
| `--class CLS` / `--minphic` | keep a class / min posterior prob for class assignment | Export a single 3D-class subset. |
| `--stack-path` / `--micrograph-path` | replacement stack / micrograph path | Fix paths when stacks moved relative to the project. |
| `--swapxy`/`--noswapxy`/`--invertx`/`--inverty`/`--flipy`/`--flipy-pose`/`--flipy-ctf` | coordinate/pose/defocus-angle handedness fixes | Use only to correct a verified flip; see `12_conventions_symmetry.md` before flipping anything. |
| `--relion2`,`-r2` | "Relion 2 compatible outputs" | **Omit** for RELION 3.1/4.0/5.0 — you want the `data_optics`+`data_particles` two-block format, not the single flat `data_` table. |
| `--strip-uid [N]` | strip leading cryoSPARC UIDs from filenames | cryoSPARC prefixes filenames with long UID digits; strip them so paths resolve. |
| `--movies` | "Write per-movie star files" | Toward Bayesian Polishing (experimental). |
| `--10k`, `--loglevel`/`-l` | first 10k particles for testing; log level | Run `--10k` first to validate the bridge cheaply. |

There is **no `--passthrough` flag** in this build — passthrough `.cs` files are given as additional positional `input` arguments. (Older pyem had `--passthrough`; it was removed. Do not script it.)

### 3.2 Core pattern (real, runnable — edit paths/box)
```bash
# Convert a cryoSPARC refinement's particles + passthrough to a RELION 3.1+ STAR.
# Run from the cryoSPARC project root so relative .mrc paths resolve.
csparc2star.py --10k \                         # validate on 10k first; drop for the full run
  J164/J164_particles.cs \                      # particles (.cs with alignments3D)
  J164/J164_passthrough_particles.cs \          # passthrough carries rlnMicrographName etc.
  --boxsize 256 \                               # match the ACTUAL particle box -> rlnImageSize
  particles_from_cryosparc.star                 # NEW output rootname
```
Then, if `rlnMicrographName` is still missing (selection/pre-extract `.cs`):
```bash
csparc2star.py J164/J164_particles.cs --boxsize 256 \
  --copy-micrograph-coordinates "Import/job001/micrographs.star" \
  particles_from_cryosparc.star
```

### 3.3 `.mrc` vs `.mrcs`
cryoSPARC writes particle stacks as `.mrc` (e.g. `J164_particles_fullres_batch_00000.mrc` in the fixture). RELION expects multi-particle stacks to carry the `.mrcs` extension (`Conventions.rst:20-21`: 3D maps use `.mrc`, stacks use `.mrcs`). The bridge writes `index@path` image names; confirm the path RELION resolves actually exists and opens. If RELION reports a stack "does not exist," symlink/rename `.mrc` -> `.mrcs` (or fix the names the bridge emitted).

### 3.4 Origin units: Angstrom vs pixel
RELION 3.1+ stores translations in Angstroms (`rlnOriginXAngstrom`/`rlnOriginYAngstrom`); RELION 3.0 and earlier used pixels (`rlnOriginX`/`rlnOriginY`) (`Conventions.rst:135`). The bridge must emit the Angstrom-convention origins for a 3.1+/4.0/5.0 target. A pose that imports but refines to noise is the classic units bug — validate a single particle (Section 4).

### 3.5 Higher-order CTF must be re-fit in RELION
Higher-order terms (`rlnOddZernike`/`rlnEvenZernike`/`rlnMagMatrix_*`, `Conventions.rst:148-165`) do **not** survive the bridge. After import, run a fresh **CtfRefine** (beam-tilt / trefoil / aniso-mag / 4th-order) in RELION 5.0 if higher-order correction matters — see `10_ctfrefine_polish.md`. Do not attempt to carry cryoSPARC's terms over.

---

## 4. Convention traps and validation

The convention traps live in `12_conventions_symmetry.md`. The three that bite the bridge, grounded in `Conventions.rst`:
- **Euler direction:** angles rotate the **reference into the observation**; translations shift the **observation into the reference** (`Conventions.rst:118-119`). A mirrored/transposed pose -> wrong-handed map.
- **Shift sign / order:** origin offsets are applied **BEFORE** rotations, and recenter the image (`Conventions.rst:133`). Origin in Angstrom for 3.1+ (`Conventions.rst:135`).
- **Pixel vs box:** coordinates are micrograph pixels (`Conventions.rst:137-139`); box size lives only in `data_optics` (`rlnImageSize`) and must be injected via `--boxsize` when absent.

**Validation after cryoSPARC -> RELION (do all four):**
1. **Count** — particles in the STAR == count in cryoSPARC (or your stated subset).
2. **`data_optics` complete** — has `rlnImageSize`, `rlnImagePixelSize`, `rlnVoltage`, `rlnSphericalAberration`, `rlnAmplitudeContrast`. Missing any is an immediate red flag (`relion_refine --print_metadata_labels` lists all labels, `Conventions.rst:97`).
3. **One-particle pose** — open one particle in the 2D viewer; confirm it looks like a particle in the orientation you expect.
4. **Short local-search Refine3D** — `relion_refine` with `--auto_local_healpix_order` engaging local searches and small `--sigma_ang` (all from `relion_refine --help`) should converge quickly to a resolution near cryoSPARC's. A large drop (e.g. 5 A -> 17 A) means lost information — almost always wrong box, wrong pixel size, or wrong origin units.

Example local-search Refine3D sanity check (real flags; `--o` is a NEW rootname):
```bash
relion_refine --i particles_from_cryosparc.star --ref cryosparc_map.mrc \
  --o Refine3D/job_csparc_check/run \
  --ini_high 8 --healpix_order 3 --auto_local_healpix_order 3 --sigma_ang 2 \
  --particle_diameter 200 --ctf --flatten_solvent --zero_mask --pad 2 \
  --firstiter_cc --gpu --j 8
```

---

## 5. The fixture P140 — a real round-trip

`<RELION_PROJECT_FIXTURE>/cryosparc/P140` (READ-ONLY) is a real cryoSPARC project that round-tripped with this RELION project (NeCen/PRC1 nucleosome). Concrete evidence:
- `P140/exports/jobs/` holds `P140_J31_import_particles`, `P140_J8_patch_ctf_estimation_multi`, and `P140_J10_extract_micrographs_multi` — i.e. RELION-side particles/micrographs were **imported into cryoSPARC** (the RELION->cryoSPARC direction).
- `P140/imports/` symlinks a Topaz-train export from another cryoSPARC project (`P39_J559_topaz_train`) — cryoSPARC imports symlink rather than copy (`27_relion_interop.md`, cryosparc `24_disk_and_storage.md`).
- Refinement jobs (e.g. `P140/J164`) write `J164_particles.cs` + `.csg` + `J164_map.mrc` and `J164_particles_fullres_batch_*.mrc` stacks — exactly the `.cs`/`.mrc` inputs `csparc2star.py` consumes to go **back to RELION**, and the `.mrc` (not `.mrcs`) extension that triggers Section 3.3.
- `P140/exports/jobs/.../P140_J10_micrographs/J1/imported/*.tiff` are the original movies (`*_fractions.tiff`) — TIFF, so the slow-axis flip note (`Conventions.rst:16-18`) applies if picks ever cross between RELION/MotionCor2 and cryoSPARC alignments.

The parent RELION project is RELION 4.0-beta data read by this 5.0 install; older optics-group STARs are auto-upgraded (`Conventions.rst:110-111`). Real optics: `opticsGroup1`, `rlnMicrographOriginalPixelSize 0.53` -> `rlnMicrographPixelSize 1.06`, 300 kV, Cs 2.7, Q0 0.1.

---

## Common failures / red flags

| Symptom | Layer | First check | Grounding |
|---|---|---|---|
| `ObservationModel::getBoxSize: box sizes not available` | bridge: no `rlnImageSize` in `data_optics` | re-run with `--boxsize` == actual box | `csparc2star.py --help` (`--boxsize`); cryosparc `27_relion_interop.md` |
| `KeyError: 'rlnMicrographName'` from the bridge | `.cs` lacks mic-name column (pre-extract/selection) | add `--copy-micrograph-coordinates` or feed the passthrough `.cs` | `csparc2star.py --help`; cryosparc `27_relion_interop.md` |
| RELION says a stack "does not exist" | `.mrc` on disk, STAR says `.mrcs` (or moved) | symlink/rename `.mrc`->`.mrcs`; check resolved path | `Conventions.rst:20-21` |
| Imports but Refine3D goes to noise / much worse res | wrong box, pixel size, or origin **units** | verify `data_optics` pixel size + box; visualize one pose; check Angstrom origins | `Conventions.rst:133-135` |
| cryoSPARC 2D thumbnails look "inverted" after import | Data Sign mismatch (RELION is light-on-dark) | set cryoSPARC Data Sign for already-extracted RELION stacks | `relion_preprocess --help` (`--invert_contrast`) |
| Higher-order CTF "doesn't help" after round-trip | aberrations never transferred | run a fresh RELION CtfRefine; don't trust carried terms | `Conventions.rst:148-165`; `10_ctfrefine_polish.md` |
| `data_optics` empty/partial after conversion | converted with `--relion2` or an optics-unaware path | re-run without `-r2`; targets 3.1+ two-block STAR | `csparc2star.py --help` (`--relion2`) |
| Mirrored/wrong-handed reconstruction | coordinate/pose flip across packages | use `--flipy`/`--invertx`/etc only after confirming; read conventions first | `csparc2star.py --help`; `12_conventions_symmetry.md` |

Do **not** treat 2018-2020 forum recipes as current — `.cs` schema and cryoSPARC's higher-order CTF model changed across v3.x/v4.x/v5.0, and pyem flags (`--passthrough` removal, multi-file positional inputs) changed too. Always confirm against the live `csparc2star.py --help` and the cryosparc skill.

---

## Cross-links

- `12_conventions_symmetry.md` — Euler direction, shift sign/order, pixel-vs-box, symmetry conventions (the authoritative trap list).
- `10_ctfrefine_polish.md` — re-fitting higher-order CTF (beam-tilt/aniso-mag/Zernikes) and Bayesian Polishing on the RELION side.
- `09_mask_postprocess_localres.md` — making the FSC mask + running PostProcess on imported cryoSPARC half-maps.
- `08_refine3d.md` — the local-search Refine3D used as the round-trip sanity check.
- `05_picking_extraction.md` — Extract / `relion_preprocess` `--invert_contrast`, box/scale choices.
- `01_star_and_metadata.md` — STAR `data_optics`/`data_particles` structure and label semantics.
- `17_interop_cryodrgn.md`, `18_interop_chimerax_coot_phenix.md`, `19_interop_coordinates.md` — sibling interop pages.
- **Full round-trip workflow** "focused RELION 3D classification of a cryoSPARC local-refine region → split by class → re-refine each class back in cryoSPARC (native poses/CTF preserved)" is owned by the **cryosparc** skill: `28_relion_class3d_roundtrip.md` + the config-driven `scripts/roundtrip/` bundle. This page (RELION-side binaries: csparc2star, `relion_image_handler` downsample, `relion_mask_create` soften, `relion_refine --skip_align` focused Class3D) supplies the RELION legs that workflow drives.
- `21_error_lookup.md` — error-string lookup (`ObservationModel::getBoxSize`, missing-stack, KeyError).
- Sibling skills that own execution: **cryosparc** (the cryoSPARC-side Import recipe, exposure groups, path-suffix tuning, RBMC, forum corpus — `27_relion_interop.md`); **cryolo** (picking), **mask** / **chimerax** (mask generation), **phenix** / **coot** / **chimerax** (downstream model building).

---

## Sources
- Live: `csparc2star.py --help` (`csparc2star.py`, run 2026-06-04).
- Live: `relion_preprocess --help`, `relion_refine --help`, `relion_postprocess --help` (RELION 5.0.0-commit-3d6c20, `<RELION_BIN>`).
- `<RELION_SKILL_BUILD_ROOT>/references/source/relion-documents_release-5.0/source/Reference/Conventions.rst`
- Sibling mirror: `<HOME>/.claude/skills/cryosparc/references/27_relion_interop.md`
- Fixture (READ-ONLY): `<RELION_PROJECT_FIXTURE>/cryosparc/P140` (exports/jobs, imports, J164).
