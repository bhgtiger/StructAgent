# 12 — Euler angles, shifts, symmetry, pixel size

## Scope
The RELION 5.0 geometric and metrological conventions that every interop file depends on: the ZYZ-intrinsic Euler angle definition (reference-into-observation, the #1 trap vs cryoSPARC/EMAN/Scipion), origin/shift signs and units (`rlnOriginXAngst` Å vs `rlnOriginX` px), the point-group symmetry families and the icosahedral I1/I2/I3/I4 setting trap, helical twist/rise as symmetry, symmetry expansion for focused/asymmetric work, and the pixel-size stack (`rlnMicrographOriginalPixelSize` / `rlnMicrographPixelSize` / `rlnImagePixelSize`, magnification anisotropy, handedness). Grounded in the fixture optics (super-res 0.53 -> 2x-binned 1.06 Å/px).

---

## 1. Euler angles — `rlnAngleRot`, `rlnAngleTilt`, `rlnAnglePsi`

**Definition (grounded: Conventions.rst:118-128).** RELION uses a right-handed coordinate system, right-handed rotations positive, ZYZ intrinsic Euler angles:

| Label | Axis | Order | metadata_label.h |
|---|---|---|---|
| `rlnAngleRot` (ϕ) | Z | 1st | `EMDL_ORIENT_ROT`, "First Euler angle (rot, in degrees)" (line 1207) |
| `rlnAngleTilt` (θ) | new Y | 2nd | `EMDL_ORIENT_TILT`, "Second Euler angle (tilt, in degrees)" (line 1210) |
| `rlnAnglePsi` (ψ) | new Z | 3rd | `EMDL_ORIENT_PSI`, "Third Euler, or in-plane angle (psi, in degrees)" (line 1212) |

Same convention as **XMIPP, SPIDER, FREALICN** (Conventions.rst:128). Priors exist as `rlnAngleRotPrior`/`rlnAngleTiltPrior`/`rlnAnglePsiPrior` (metadata_label.h:1208-1213); helical bimodal psi uses `rlnAnglePsiFlipRatio`/`rlnAnglePsiFlip` (lines 1214-1215).

### The #1 interop trap: direction of rotation
> "Orientations (`rlnAngleRot`, `rlnAngleTilt`, `rlnAnglePsi`) in a STAR file **rotate the reference into observations** (i.e. particle image), while translations (`rlnOriginXAngstrom` and `rlnOriginYAngstrom`) **shift observations into the reference projection**." — Conventions.rst:118-119

So the stored angles are the orientation that, applied to the **reference**, produces the **observed particle**. This is the *opposite sense* of conventions that store "pose that brings the particle into the reference frame." When you import poses from another package (cryoSPARC, EMAN2, Scipion/XMIPP-via-other-tools), you cannot assume the rotation direction, axis order, or handedness matches — a wrong-handed or inverted-direction import yields a mirror-image or garbage reconstruction even though every number looks plausible. Conversion is the job of the dedicated converter, not hand-editing (see Cross-links: 16_interop_cryosparc.md, 17_interop_cryodrgn.md). For the canonical code path, Conventions.rst:120 points developers at `ObservationModel::predictObservation()` in `src/jaz/obs_model.cpp`.

**Box centre / rotation centre (Conventions.rst:130-133).** For an image of `xdim x ydim`, the centre is `((int)xdim/2, (int)(ydim/2))` with the first pixel at `(0,0)` upper-left. For both `xdim=ydim=65` and `xdim=ydim=64` the centre is `(32,32)`. "Origin offsets reported for individual images translate the image to its center and are applied **BEFORE rotations**." (Conventions.rst:133).

To dump the literal label definitions live:
```bash
relion_refine --print_metadata_labels    # grounded: relion_refine --help, --print_metadata_labels (false)
```

---

## 2. Origins / shifts — `rlnOriginXAngst` vs `rlnOriginX`

| Label | Unit | Since | metadata_label.h |
|---|---|---|---|
| `rlnOriginXAngst` | Ångström | 3.1+ | `EMDL_ORIENT_ORIGIN_X_ANGSTROM` (line 1200) |
| `rlnOriginYAngst` | Ångström | 3.1+ | `EMDL_ORIENT_ORIGIN_Y_ANGSTROM` (line 1201) |
| `rlnOriginZAngst` | Ångström | 3.1+ (3D) | `EMDL_ORIENT_ORIGIN_Z_ANGSTROM` (line 1202) |
| `rlnOriginX` | **pixels** | pre-3.1 | `EMDL_ORIENT_ORIGIN_X`, "X-coordinate (in pixels) for the origin of rotation" (line 1193) |
| `rlnOriginY` | **pixels** | pre-3.1 | `EMDL_ORIENT_ORIGIN_Y` |

**Note the exact label spelling.** The metadata table label is `rlnOriginXAngst` (metadata_label.h:1200), but the prose in Conventions.rst writes it as `rlnOriginXAngstrom`. The label written into 3.1+ STAR files is **`rlnOriginXAngst`** — use that when grepping/parsing. (Discrepancy is purely documentation prose vs. the registered EMDL name.)

**Sign / direction.** Translations shift the *observation* into the *reference projection* (Conventions.rst:119), i.e. the stored origin is the offset that re-centres the particle onto the box centre; it is applied **before** the rotation (Conventions.rst:133). When you re-extract or re-centre particles, RELION folds the origin into the new coordinate and resets the origin — do not double-apply.

**Unit conversion (3.1+ Å <-> px).** `rlnOriginX[px] = rlnOriginXAngst / pixel_size`. The relevant pixel size is the **image pixel size of the optics group** (`rlnImagePixelSize`, §4), not the super-resolution pixel size. A pre-3.1 project read by 5.0 carries `rlnOriginX`/`rlnOriginY` in pixels; the fixture here is a 4.0-beta project so it is already in `*Angst` form. Old-style STAR files are auto-upgraded by 3.1+; `relion_convert_star` does it manually (Conventions.rst:110-111).

---

## 3. Symmetry — point groups and the icosahedral trap

### 3.1 Families and naming (grounded: symmetries.cpp `isSymmetryGroup`, lines 329-594)
Symmetry strings are parsed case-insensitively (`toupper`, line 351), max 4 chars (line 344). Recognised prefixes:

| Family | String form | symmetries.cpp |
|---|---|---|
| Cyclic | `C<n>` (1- or 2-digit n) | `pg_CN` (lines 361-374) |
| Cyclic w/ inversion / mirror | `CI`, `CS` | `pg_CI` (376-381), `pg_CS` (383-388) |
| Cyclic + horizontal/vertical mirror | `C<n>H`, `C<n>V` | `pg_CNH` (390-403), `pg_CNV` |
| Dihedral | `D<n>` | `pg_DN` (437-446) |
| Dihedral + mirror | `D<n>V`, `D<n>H` | `pg_DNV`, `pg_DNH` |
| Tetrahedral | `T`, `TD`, `TH` | `pg_T` (482), `pg_TD` (489), `pg_TH` (496) |
| Octahedral | `O`, `OH` | `pg_O` (503), `pg_OH` (510) |
| Icosahedral | `I`, `I1`–`I5`, `IH`, `I1H`–`I5H` | `pg_I`/`pg_I1`..`pg_I5` (517-552), `pg_IH`/`pg_I1H`.. (559-594) |

The common SPA cases are **C1, C2..Cn, D1..Dn, T, O, I** (with an explicit icosahedral setting). Print the actual operator matrices for any group:
```bash
relion_refine --sym D7 --print_symmetry_ops    # grounded: Conventions.rst:221-224 + relion_refine --help
```

**Origins/orientations of each group (grounded: Conventions.rst:174-205):** Cn axis on Z; Dn principal axis on Z with the 2-fold on X; **T 3-fold axis on Z (RELION deviates from Heymann et al.!)**; O 4-folds on X/Y/Z; I origin at the intersection of symmetry axes.

### 3.2 The icosahedral I1 vs I2 (vs I3/I4) trap
Multiple icosahedral *settings* exist and they are **not interchangeable** — the same particle reconstructed in I1 vs I2 differs by a rotation, so a reference/map built under one setting will not refine correctly under another. From Conventions.rst:207-219:

| Setting | Description (Conventions.rst) |
|---|---|
| **I1** | "No-crowther 222 setting (=standard in Heymann et al)": 2-folds on X,Y,Z; front-most 5-folds in **YZ** plane, 3-folds in **XZ**. |
| **I2** | "Crowther 222 setting": 2-folds on X,Y,Z; front-most 5-folds in **XZ** plane, 3-folds in **YZ**. (Note: in symmetries.cpp `pg_I` defaults to the **I2** operators — `pgGroup == pg_I \|\| pgGroup == pg_I2`, lines 692/849. So bare `I` == `I2`.) |
| **I3** | 52-setting (SPIDER-like): 5-fold on Z, 2-fold on Y. |
| **I4** | Alternative 52 setting: as I3 but the front-most 5-fold is in +XZ. |

Practical rules:
- **Bare `I` means I2** in RELION (the code aliases them). cryoSPARC / Chimera viruses are frequently in a *different* icosahedral convention — confirm the setting before importing a map or particles.
- To **convert a map between icosahedral conventions** (or to align an arbitrary map onto the symmetry axes before imposing symmetry), use `relion_align_symmetry`:
```bash
# Align a C1 map onto the target point-group axes, optionally symmetrising:
relion_align_symmetry --i Refine3D/job050/run_class001.mrc \
    --o ConventionConvert/job060_I2aligned.mrc \
    --sym I2 --angpix 1.06 --apply_sym
# grounded flags (relion_align_symmetry --help): --i --sym --o --angpix --apply_sym
#   also: --only_rot, --keep_centre, --nr_uniform (400), --box_size (64), --maxres
```
`--apply_sym` "Also apply the symmetry to the map"; `--only_rot` keeps TILT/PSI fixed and searches only ROT; `--keep_centre` skips re-centring. Default working `--box_size` is 64 ("Very small box ... such that Nyquist is around 20 A is usually sufficient", per help text).
- For a pure handedness/axis re-orientation of a 3D map, `relion_image_handler` can `--sym`, `--flipX/--flipZ`, `--invert_hand` (see §4.4).

### 3.3 Helical twist/rise as symmetry
For helices, the "symmetry" is the (twist, rise) pair, refined in `relion_refine` with `--helix`:
```
--helix                       Perform 3D classification or refinement for helices?
--helical_twist_initial (0.)  Helical twist (deg, positive = right-handed)
--helical_rise_initial (0.)   Helical rise (Angstroms)
--helical_twist_min/max, --helical_rise_min/max, --*_inistep
--helical_symmetry_search     Perform local refinement of helical symmetry?
--ignore_helical_symmetry     Ignore helical symmetry?
```
(all grounded: `relion_refine --help`.) Stored as `rlnHelicalTwist` ("rotation per subunit, degrees", metadata_label.h:1023) and `rlnHelicalRise` ("translation per subunit, Angstroms", line 1027), with `rlnHelicalTwistMin/Max` and `rlnHelicalRiseMin/Max` (1024-1029); `rlnHelicalTwistMin` is documented "+ for right-handedness" (line 1024). See 13_helical_amyloid.md for the full helical workflow.

### 3.4 Symmetry expansion — `relion_particle_symmetry_expand`
For focused/asymmetric work (focused 3D classification on one sub-unit, multibody, breaking symmetry): replicate each particle once per symmetry operator, writing all symmetry-equivalent orientations, so downstream alignment can localise to a single asymmetric unit.
```bash
relion_particle_symmetry_expand \
    --i Refine3D/job050/run_data.star \
    --o SymExpand/job061_expanded.star \
    --sym D7
# grounded (relion_particle_symmetry_expand --help): --i, --o (expanded.star), --sym (C1)
# Helical mode:
relion_particle_symmetry_expand --i run_data.star --o expanded.star \
    --helix --twist 1.2 --rise 4.75 --angpix 1.06 --asu 1 \
    --frac_sampling 1 --frac_range 0.5
# grounded helical flags: --helix --twist --rise --angpix --asu --frac_sampling --frac_range --ignore_optics
```
`--ignore_optics` is for "relion-3.0 functionality, without optics groups" (help text). The expanded STAR is then fed to focused Class3D/Refine3D or MultiBody. See 11_subtract_multibody.md.

### 3.5 "Build in C1 then impose" — practical strategy
For symmetric assemblies where the symmetry might be pseudo or partial, refine in **C1 first**, inspect, then align onto the symmetry axes with `relion_align_symmetry` (§3.2) and impose the point group in a subsequent Refine3D `--sym`. For partial symmetry relaxation during refinement, `relion_refine --relax_sym <group>` ("Symmetry to be relaxed", grounded: `relion_refine --help`). This avoids locking in a wrong axis assignment.

---

## 4. Pixel size — the metrology stack

### 4.1 The three pixel-size labels (grounded: metadata_label.h)
| Label | Meaning | Lives in | metadata_label.h |
|---|---|---|---|
| `rlnMicrographOriginalPixelSize` | "Pixel size of original movie **before binning** in Å/px" | `data_optics` | line 988 |
| `rlnMicrographPixelSize` | "Pixel size of (averaged) micrographs **after binning** in Å/px" | `data_optics` | line 989 |
| `rlnImagePixelSize` | "Pixel size (in Angstrom)" — the **particle/image** pixel size | `data_optics` | line 912 |
| `rlnTomoTiltSeriesPixelSize` | original tilt-series pixel size (tomo) | tomo optics/tilt-series | line 1382 |

**Where each lives.** All three SPA labels live in the `data_optics` block (one row per optics group). `rlnMicrographOriginalPixelSize` and `rlnMicrographPixelSize` describe the motion-corrected micrograph; `rlnImagePixelSize` is the pixel size of the *extracted particle images* (after any down-scaling at Extract). After binning at extraction, `rlnImagePixelSize` = `rlnMicrographPixelSize` × extraction-binning. PixelSizeIssues.rst:101-105 shows a shiny.star `data_optics` carrying `rlnImagePixelSize` + `rlnMicrographOriginalPixelSize` together.

### 4.2 The fixture: 0.53 -> 1.06 (real, READ-ONLY)
The validation fixture `<RELION_PROJECT_FIXTURE>` (`particles.star`, `data_optics`, opticsGroup1) literally contains:
```
_rlnMicrographOriginalPixelSize  0.530000     # super-resolution / original movie
_rlnMicrographPixelSize          1.060000     # 2x-binned aligned micrograph
_rlnVoltage                    300.000000
_rlnSphericalAberration          2.700000
_rlnAmplitudeContrast            0.100000
_rlnMtfFileName  ../../other/MTF/mtf_k3_standard_300kV_FL2.star
```
So **0.53 = super-res / original, 1.06 = binned image pixel size** (2x bin). This is a K3 detector; the MTF file is `mtf_k3_standard_300kV_FL2.star` (`rlnMtfFileName`, metadata_label.h:907). Note this 4.0-beta optics block omits an explicit `rlnImagePixelSize` row and stores the post-bin size as `rlnMicrographPixelSize` 1.06; a particle extracted without further binning therefore has effective image pixel size 1.06 Å/px.

### 4.3 Magnification anisotropy
Real-space anisotropic magnification "brings the reference into observations" (Conventions.rst:160). Stored as a 2×2 matrix. **On-disk label names (verified):** the registered anisotropic-magnification labels in `metadata_label.h` are `rlnMagMat00`, `rlnMagMat01`, `rlnMagMat10`, `rlnMagMat11` (lines 913-916, `EMDL_IMAGE_MAG_MATRIX_00/01/10/11`), and the real fixture `CtfRefine/job072/particles_ctf_refine.star` confirms `_rlnMagMat00`..`_rlnMagMat11` columns on disk. The docs' prose spellings (`rlnMagMatrix_00`, Conventions.rst:163; `rlnMatrix00`, PixelSizeIssues.rst:233) are **not** the real column names — grep the job output. (The generic `rlnMatrix_1_1`..`rlnMatrix_3_3` labels at metadata_label.h:963-971 are for arbitrary 3×3 matrices, unrelated to magnification.) The matrix is refined by CtfRefine "Estimate anisotropic magnification: Yes" and captures only the **relative** pixel-size/stretch difference between optics groups, not the absolute scale (PixelSizeIssues.rst:152-154, 231-239). Cs/4th-order aberration error is instead stored in `rlnEvenZernike` (metadata_label.h:911; PixelSizeIssues.rst:63).

### 4.4 image_handler — rescale, force-header, handedness (grounded: relion_image_handler.txt + live --help)
```
--rescale_angpix (-1.)      Scale input image(s) to this new pixel size (in A)         # actually resamples
--force_header_angpix (-1.) Change the pixel size in the header (in A). Without
                            --rescale_angpix, the image is NOT scaled.                 # header-only edit
--new_box (-1)              Resize the image(s) to this new box size (in pixel)
--angpix (-1)              Pixel size (in A) of the input
--sym ()                   Symmetrise 3D map with this point group (e.g. D6)
--flipX / --flipY / --flipZ  Flip (mirror) in that direction
--invert_hand (false)      "Invert hand by flipping X? Similar to flipX, but preserves
                            the symmetry origin. Edge pixels are wrapped around."
```
**The MRC-header pixel-size gotcha.** `--rescale_angpix` *resamples* the data; `--force_header_angpix` only **rewrites the header number without touching voxels**. They are not the same operation:
```bash
# Resample a 0.53 super-res map to 1.06 (changes data + header):
relion_image_handler --i map_superres.mrc --o ConventionConvert/job062_map_106.mrc \
    --angpix 0.53 --rescale_angpix 1.06
# Fix ONLY a wrong header value (no resampling):
relion_image_handler --i map_wrongheader.mrc --o ConventionConvert/job062_fixed.mrc \
    --force_header_angpix 1.06
```
RELION trusts the **STAR optics-group pixel size**, not the MRC header, for refinement; `relion_refine` stretches/crops particles to match the *reference header* pixel size and box (PixelSizeIssues.rst:199, 222-229). A mismatched header on a reference map silently rescales your particles — a classic "resolution is wrong / map is the wrong size" bug.

**Handedness.** `--invert_hand` (or `--flipX`/`--flipZ`) flips chirality. `--invert_hand` is preferred over a bare `--flipX` for maps because it "preserves the symmetry origin" (help text). If your map refines to the wrong hand (alpha-helices left-handed), invert the map (and re-refine if you need correct poses), do not edit angles.

### 4.5 Pixel-size correction policy (grounded: PixelSizeIssues.rst)
- **Small error (1-2%), modest resolution (~3 Å):** just enter the corrected pixel size in the **PostProcess** job — this rescales the FSC x-axis and the output-map header (PixelSizeIssues.rst:7, 66-67, 212-213).
- **You should NEVER edit the pixel size in the STAR / optics table.** Defocus, coordinates and trajectories are all fitted/consistent at the nominal pixel size; editing it breaks consistency and Bayesian Polishing (PixelSizeIssues.rst:12-16, 64, 210).
- **"Manually set pixel size" in Extraction was removed in 3.1** for the same reason (PixelSizeIssues.rst:14-16).
- **Large error / high resolution:** the Cs term no longer absorbs the error; run **CtfRefine twice** — first "Estimate 4th order aberrations" (refines apparent Cs into `rlnEvenZernike`), then defocus — keeping `rlnSphericalAberration` fixed (PixelSizeIssues.rst:54-66). The true pixel size = NominalPixelSize·(Cs_true/Cs_apparent)^(1/4) (line 193).
- **Do NOT feed a PostProcess-rescaled map back into Refine3D/Class3D/MultiBody** — it will be re-stretched and double-corrected (PixelSizeIssues.rst:215-217).
- **Merging datasets with different pixel sizes** is supported from 3.1: give them different `rlnOpticsGroupName`, JoinStar, refine against the first group's box/pixel size (or `--trust_ref_size`), then CtfRefine anisotropic-mag for the relative scale (PixelSizeIssues.rst:80-157).

---

## Common failures / red flags
- **Mirror-image / left-handed map after import** -> wrong Euler-angle handedness or icosahedral setting from the source package; fix with `relion_align_symmetry --sym I2` and/or `relion_image_handler --invert_hand`, not by hand-editing angles.
- **"My virus won't refine in I"** -> bare `I` is **I2** in RELION; your reference may be I1/I3/I4. Re-align with `relion_align_symmetry`.
- **Output map is subtly the wrong size / resolution off** -> reference MRC **header** pixel size ≠ optics-group pixel size; `relion_refine` resampled the particles. Check both; use `--force_header_angpix` to correct the header only.
- **Shifts double-applied / particles drift on re-extraction** -> remember origins are applied **before** rotations and are folded into new coordinates on re-extraction (Conventions.rst:133).
- **Edited the optics pixel size to "fix" resolution** -> breaks defocus/coordinate/Polish consistency; never do this. Correct it in PostProcess instead.
- **Tetrahedral mismatch with other software** -> RELION's **T** puts the 3-fold on Z, *deviating from Heymann et al.* (Conventions.rst:197). Expect a re-orientation vs other packages.
- **`rlnMagMatrix_*` not found by your parser** -> the real on-disk labels are `rlnMagMat00`..`rlnMagMat11` (metadata_label.h:913-916; confirmed in the fixture `CtfRefine/job072` output), **not** the docs' `rlnMagMatrix_*` prose spelling.

## Cross-links
- `01_star_and_metadata.md` — STAR/optics-group structure, label tables.
- `08_refine3d.md` — `--sym`, `--relax_sym`, reference box/pixel-size matching at refinement.
- `09_mask_postprocess_localres.md` — PostProcess pixel-size rescaling and FSC.
- `10_ctfrefine_polish.md` — CtfRefine 4th-order/anisotropic-mag, Polish pixel-size consistency.
- `11_subtract_multibody.md` — where symmetry expansion feeds focused/asymmetric work.
- `13_helical_amyloid.md` — helical twist/rise symmetry in full.
- `14_tomo_sta.md` — `rlnTomoTiltSeriesPixelSize` and STA conventions.
- `16_interop_cryosparc.md`, `17_interop_cryodrgn.md`, `18_interop_chimerax_coot_phenix.md`, `19_interop_coordinates.md` — all depend on the angle/shift/pixel conventions above.
- Installed skills: **chimerax** (map align/flip/symmetry-in-Chimera), **mask** (mask box/pixel matching), **cryosparc** (pose/handedness interop), **structural-strategy** (when to impose symmetry).

## Sources
- `source/Reference/Conventions.rst` (Orientations, Symmetry, icosahedral I1-I4 settings, T deviation) — read.
- `source/Reference/PixelSizeIssues.rst` (pixel-size correction policy, anisotropic mag, dataset merging) — read.
- `src/symmetries.cpp` `isSymmetryGroup` and operator dispatch (`pg_*`, I==I2 aliasing) lines 329-594, 692, 849 — read.
- `src/metadata_label.h` lines 904-1030, 1145-1215, 1382 (angle/origin/pixel-size/helical/matrix/MTF labels) — read.
- `relion_image_handler` captured help (`relion5_cli_capture_20260604/help/relion_image_handler.txt`) + live `relion_image_handler --help` — read/ran.
- Live `relion_align_symmetry --help`, `relion_particle_symmetry_expand --help`, `relion_refine --help` (--sym, --print_symmetry_ops, --print_metadata_labels, --relax_sym, helical flags) — ran.
- Fixture `<RELION_PROJECT_FIXTURE>/particles.star` `data_optics` (0.53 -> 1.06, opticsGroup1, mtf_k3_standard_300kV_FL2.star) — read (READ-ONLY).
