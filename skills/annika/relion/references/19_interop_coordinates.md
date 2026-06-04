# 19 — Picker / coordinate format interop

## Scope
How particle coordinates move into and out of RELION 5.0: the native RELION coordinate STAR format (`_autopick.star` / manual-pick STARs, `coords_suffix*.star`), the foreign formats RELION's `Import` job and `relion_preprocess --extract` can read directly (EMAN `.box`, ximdisp, xmipp, External-job picker STARs), the Topaz wrapper baked into `relion_autopick`, and how crYOLO / cryoSPARC picks are bridged across. The recurring theme is the **coordinate-origin convention** (top-left, pixel units in the aligned/summed micrograph frame) and the **Y-flip trap** when picks cross between RELION, MotionCor2 and cryoSPARC. Execution of the foreign pickers themselves is owned by sibling skills (crYOLO, cryoSPARC); this file owns the RELION-side format/convention details and the one hard rule: **after importing foreign picks you must re-extract in RELION**.

---

## 1. Native RELION coordinate STAR

A RELION coordinate file is a per-micrograph STAR table. RELION never stores all coordinates in one giant file; it stores one coordinate STAR **per micrograph** plus a small "suffix" pointer file at the job level.

### 1.1 Per-micrograph coordinate STAR

Minimal columns (from the real fixture `Import/job015/Micrographs/*_fractions.star`):

```
data_

loop_
_rlnMicrographName #1
_rlnCoordinateX #2
_rlnCoordinateY #3
FoilHole_300206_..._fractions.mrc 3196 3924
FoilHole_300206_..._fractions.mrc 4024 1644
...
```

| Label | Meaning | Notes |
|---|---|---|
| `rlnCoordinateX`, `rlnCoordinateY` | particle centre, **pixels, in the micrograph frame** | unit is pixel in the aligned & summed micrograph (possibly binned from super-res movies) — Conventions.rst:137 |
| `rlnMicrographName` | which micrograph the row belongs to | links the pick to a micrograph; often present even in per-mic files |
| `rlnAutopickFigureOfMerit` | picker score / FOM | written by template-matching, LoG and Topaz autopick; thresholded later at extraction (Autopicking.rst:453) |
| `rlnClassNumber` | template class that fired | written by reference-based (template) autopick |
| `rlnAnglePsi` | in-plane angle | written for **helical** picks (in-plane psi estimated for helical references), see 13_helical_amyloid.md |

The fixture file above is a foreign (cryoSPARC-derived) import, so it carries only the three mandatory columns. A native `relion_autopick` Topaz/LoG/template run additionally writes `rlnAutopickFigureOfMerit` (and `rlnClassNumber` for template matching).

### 1.2 The `coords_suffix` pointer file

`relion_autopick` writes coordinate files under `--odir` with rootname `--pickname` (default `autopick`). The job-level pointer is a small text/STAR file whose single content line is the input micrographs STAR. Real fixture (`Import/job015/coords_suffix.star`):

```
Micrographs/*.mrc
```

- `relion_autopick` default `--pickname autopick` → per-mic files `<mic>_autopick.star` and a job-level `autopick.star` you feed to extraction (Autopicking.rst:101, 487).
- Manual picking writes the analogous `<mic>_manualpick.star` and a `manualpick.star` pointer (the GUI `relion_manualpick` binary is FLTK-only and cannot be run headless on this install — see Red flags).
- External-job pickers (Topaz wrapper-as-External, crYOLO-as-External) write `coords_suffix_PICKNAME.star`, where `PICKNAME` is a free string such as `topaz` or `cryolo` (Using-RELION.rst:276-281). Its one line is the input micrographs STAR (e.g. `CtfFind/job005/micrographs_ctf.star`), and the node must be registered in `RELION_OUTPUT_NODES.star` with node type `2`.

### 1.3 Combining / handling coordinate STARs

`relion_star_handler` operates on coordinate STARs (verified flags, relion_star_handler.txt):

```bash
# Merge several manual/autopick coordinate STARs into one (e.g. two pickers on the same mics)
relion_star_handler --combine_picks \
  --i "AutoPick/job010/autopick.star ManualPick/job012/manualpick.star" \
  --o Combine/job013/combined_picks.star
```

- `--combine_picks` is the picks-specific combine (distinct from generic `--combine`); both take **multiple filenames inside one double-quoted `--i`**.
- De-duplicate overlapping picks (e.g. two pickers firing on the same particle) at **extraction** time with `relion_preprocess` (see §6), or post-extraction with `relion_star_handler --remove_duplicates <dist_A> --image_angpix <orig_A>` (relion_star_handler.txt:68-69).
- `relion_star_handler --operate rlnCoordinateX --add_to <px>` (and `--operate2 rlnCoordinateY`) can shift a whole column by a constant — useful for box-corner→centre fixes, but **prefer** the extraction-time `--extract_bias_x/--extract_bias_y` (§6) so the source picks stay untouched.

---

## 2. Coordinate ORIGIN conventions (the part everyone gets wrong)

Grounded in Conventions.rst:137-139:

- **Units:** `rlnCoordinateX/Y` are **pixels in the aligned, summed micrograph** — i.e. if movies were super-res 0.53 Å/pix and binned 2× to 1.06 Å/pix micrographs (as in the fixture optics), the coordinates are in the **1.06 Å/pix** frame, not the super-res frame. Foreign picks made at a different binning must be **scaled** before they line up (§3, §4).
- **Origin:** "the first element in the 2D array of an MRC file." In RELION this origin is **displayed at the upper-left corner** (other programs may display differently).
- **Centre convention:** `rlnCoordinateX/Y` is the **particle centre**, not a box corner.

### 2.1 The Y-flip trap

The danger is not the X axis — it is the Y direction and whether a foreign program measures Y from the **top** or the **bottom** of the image.

- RELION measures from the **top-left** (Y increases downward), consistent with "first element of the MRC 2D array displayed upper-left."
- Some pipelines/tools measure Y from the **bottom-left** (image/Cartesian convention). If you import such coordinates verbatim, **every particle ends up mirrored about the horizontal mid-line**: `Y_relion = (micrograph_height_px − 1) − Y_foreign`.
- Note that TIFF readers (UCSF MotionCor2, IMOD) flip TIFF images along the slow axis on read/write (relion_import.txt:17 / Conventions.rst:17). So a coordinate produced against a TIFF-derived micrograph in one program may already be flipped relative to another program's view of "the same" micrograph. Confirm with one micrograph before trusting a batch.

**How to diagnose:** import a handful of foreign picks, extract, and look at the extracted particles or overlay picks in the GUI. If particles are systematically off-centre in a way that mirrors top↔bottom (good picks become half-on/half-off the particle, and the pattern flips across the image), you have a Y-flip. Fix it before re-extracting the whole set, e.g.:

```bash
# Flip Y for a micrograph of height H (px): Y_new = (H-1) - Y_old, done as multiply by -1 then add (H-1)
relion_star_handler --i picks_in.star --o picks_yflip.star \
  --operate rlnCoordinateY --multiply_by -1 --add_to <H_minus_1>
```

(unverified: the exact off-by-one — `H` vs `H-1` — depends on the foreign program's pixel-centre convention; verify against one micrograph rather than assuming.)

See **12_conventions_symmetry.md** (handedness / axis conventions) and **16_interop_cryosparc.md** (cryoSPARC↔RELION coordinate transfer) for the cross-package details.

---

## 3. crYOLO (.cbox / .star) → RELION

crYOLO writes two relevant outputs:

- **`.star`** files (one per micrograph) under `STAR/` — already in RELION-style `_rlnCoordinateX`/`_rlnCoordinateY` columns; these import directly.
- **`.cbox`** files under `CBOX/` — crYOLO's own boxed format that additionally carries box **width/height**, a **confidence** score, and (for filaments) extra geometry. `.cbox` is richer but is **not** a RELION coordinate STAR; map it to RELION coords by taking the box **centre** and the confidence as a FOM.

Practical bridging:

- crYOLO `.star` outputs: point a RELION `Import` job (Node type `2D/3D particle coordinates`) at `<crYOLO_out>/STAR/*.star`, or just feed `--coord_dir`/`--coord_suffix .star` to extraction.
- crYOLO `.cbox`: convert centre + confidence to a RELION coordinate STAR (`rlnCoordinateX/Y` = box centre, `rlnAutopickFigureOfMerit` = confidence) before import. crYOLO ships helpers for this; the **crYOLO skill** owns running crYOLO and the conversion, and also owns the **cryoSPARC external-picker** path (crYOLO-in-cryoSPARC via cryosparc-tools).
- **Box size / centering:** crYOLO box size is a picking-display parameter; in RELION the box you extract with is set independently by `--extract_size` (§6). What must match is the **centre convention** — crYOLO centres are box centres, which is exactly what RELION wants, so no corner correction is needed (unlike EMAN `.box`, §5).

Cross-link the **cryolo** skill for crYOLO execution, `.cbox` conversion, SLURM/high-throughput picking, and the cryoSPARC external-picker integration. This file only covers the RELION-side format expectations.

---

## 4. Topaz → RELION

Two distinct routes:

### 4.1 Built-in Topaz wrapper inside `relion_autopick` (recommended)

`relion_autopick` has native Topaz wrapper options (verified, relion_autopick.txt:46-60). It calls the Topaz executable `--fn_topaz_exe` (default `relion_python_topaz`, the conda-installed wrapper) and writes **RELION coordinate STARs directly**, so there is **no coordinate-scaling or origin conversion to do** — the wrapper handles it.

Key flags (all verified in relion_autopick.txt):

| Flag | Purpose |
|---|---|
| `--topaz_train` | wrap `topaz train` (run **single-MPI** — training is not parallelised; Autopicking.rst:450) |
| `--topaz_extract` | wrap `topaz extract` (predict positions; this **can** use multiple MPI ranks) |
| `--topaz_nr_particles (200)` | expected particles per micrograph |
| `--topaz_threshold (-6)` | minimum FOM threshold for picking |
| `--topaz_train_picks` / `--topaz_train_parts` | train on a coordinate STAR *or* on a particle STAR |
| `--topaz_downscale (-1)` | downscale factor for Topaz |
| `--topaz_model` | saved model from a prior train for extract (empty = Topaz's default general model) |
| `--topaz_radius (-1)` | particle radius in **pix** for extract (default derived from `--particle_diameter`) |
| `--fn_topaz_exe (relion_python_topaz)` | Topaz executable |

Trained model lands as e.g. `AutoPick/jobNNN/model_epoch10.sav`; picks land as `autopick.star` + per-mic `<mic>_autopick.star` with `rlnAutopickFigureOfMerit` (Autopicking.rst:433, 453). Topaz default picking gives many low-FOM picks; a minimum FOM of ~ −3 is "probably reasonable" and is applied **at extraction** (Autopicking.rst:454, 495), not in the pick file.

Example (new output rootnames; GPU IDs are illustrative — this box has 2× RTX 2080 Ti):

```bash
# Train on selected particles, single MPI rank, one GPU
relion_autopick --i Select/job005/micrographs_split1.star --angpix 1.06 \
  --topaz_train --topaz_train_parts Select/job009/particles.star \
  --particle_diameter 180 --topaz_nr_particles 300 \
  --gpu --odir AutoPick/job_topaz_train/ --pickname autopick

# Pick the full set with the trained model (extract can be multi-MPI)
relion_autopick --i CtfFind/job003/micrographs_ctf.star --angpix 1.06 \
  --topaz_extract --topaz_model AutoPick/job_topaz_train/model_epoch10.sav \
  --particle_diameter 180 --topaz_nr_particles 300 \
  --gpu --odir AutoPick/job_topaz_pick/ --pickname autopick
```

(`--angpix` shown explicitly; in the GUI/pipeline it is normally read from the input STAR via "Pixel size in micrographs = -1", Autopicking.rst:40.)

### 4.2 Standalone Topaz (outside RELION)

If you run upstream `topaz` directly (its own `topaz extract` → `.txt`/coordinate table), the output is **not** in RELION's pixel frame unless you ran Topaz on full-scale micrographs. Topaz commonly works on **downsampled** images, so the coordinates come back in the downsampled frame and must be **scaled by the downscale factor** to land in the RELION micrograph frame before import. The built-in wrapper (§4.1) avoids this entirely. If you must import standalone Topaz picks, convert to a per-mic RELION coordinate STAR, multiply `rlnCoordinateX/Y` by the downscale factor (`relion_star_handler --operate rlnCoordinateX --multiply_by <f>` + `--operate2 rlnCoordinateY`), then import and **re-extract**.

The **cryo-flex-knowledge** / general processing skills do not own Topaz; the RELION wrapper is owned here, standalone Topaz is upstream Topaz's own docs.

---

## 5. EMAN `.box` → RELION

RELION reads Steven Ludtke's `e2boxer.py` `.box` files **with a `.box` extension** (Preprocessing.rst:289). This is also visible in the extractor: `relion_preprocess --coord_suffix` help literally gives `".box"` as an example suffix (relion_preprocess.txt).

**The corner-vs-centre trap.** The classic EMAN1/`e2boxer` `.box` format is 4 columns:

```
x_lower_left   y_lower_left   box_width   box_height
```

i.e. the first two numbers are the **lower-left corner** of the box, not the particle centre. RELION wants the **centre**. RELION's `.box` reader applies the standard `centre = corner + box/2` conversion, so a well-formed 4-column `.box` imports correctly. But be careful when:

- the `.box` was written with a **different box size** than you intend to extract with — the `box_width/box_height` in the file define where the centre is; if those are wrong, centres are wrong;
- the file is a **2-column** variant (already centre, no width/height) — then no `+box/2` should be applied, and a reader expecting 4 columns will mis-handle it;
- the producing program used a **bottom-left Y origin** — same Y-flip trap as §2.1.

**Import path** (Preprocessing.rst:290-292): save the `.box` files in the micrograph directory with the **same rootname** as the micrograph (`Movies/006.box` for `Movies/006.mrc`), then run `Import` → Node type `2D/3D particle coordinates`, giving an input wildcard ending in the suffix, e.g. `Movies/*.box`. Then **re-extract** (§6).

Other supported foreign formats (Preprocessing.rst:289): ximdisp (any extension) and xmipp-2.4 (any extension). For those, the suffix can be anything; for `.box` it must be `.box`.

---

## 6. Re-extraction is mandatory after importing foreign picks

Importing coordinates only registers positions; it does **not** create particle images. You must run a RELION **Particle extraction** job (`relion_preprocess` / `relion_preprocess_mpi`) against the **RELION-side** CTF'd micrographs to cut, normalise, invert and (optionally) rescale particles, so downstream optics, CTF and pixel-size metadata are consistent with the rest of the project.

Real fixture extraction command (Extract/job016/note.txt) — a genuine "foreign picks → RELION extract" case (coordinates imported in `Import/job015`, then extracted):

```bash
`which relion_preprocess_mpi` --i CtfFind/job003/micrographs_ctf.star \
  --coord_dir Import/job015/ --coord_suffix .star \
  --part_star Extract/job016/particles.star --part_dir Extract/job016/ \
  --extract --extract_size 220 --float16 --scale 60 \
  --norm --bg_radius 22 --white_dust -1 --black_dust -1 --invert_contrast \
  --pipeline_control Extract/job016/
```

Extraction flags that matter for interop (verified, relion_preprocess.txt):

| Flag | Use |
|---|---|
| `--coord_dir` / `--coord_suffix` | where the per-mic coordinate files are and their suffix (`.star`, `.box`, …) |
| `--coord_list` | alternative: a 2-column STAR of micrograph→coordinate-file (instead of dir+suffix) |
| `--extract_size` | box size in **pixels** (in the micrograph frame); always even |
| `--scale` | rescale extracted particles (downscale for speed; re-extract at full scale later) |
| `--extract_bias_x` / `--extract_bias_y` | add a constant pixel shift to all coords — the clean way to correct a constant centre offset from a foreign picker (do **not** edit the source picks) |
| `--minimum_pick_fom` | extract only picks with `rlnAutopickFigureOfMerit` ≥ this (e.g. −3 for Topaz; Autopicking.rst:495) |
| `--invert_contrast`, `--norm`, `--bg_radius` | standard contrast/normalisation, independent of picker origin |
| `--reextract_data_star` + `--recenter` / `--recenter_x/y/z` | re-extract from a refinement `_data.star` (re-bin or re-centre on a 3D reference position) — not foreign-pick import, but the other major re-extraction route |

**Key interop point:** `--extract_size` and `--scale` are set **in the RELION extract job**, independent of whatever box size the foreign picker displayed. The only thing that must be correct in the imported picks is the **centre position in the RELION micrograph pixel frame** (right binning, right origin, no Y-flip). Everything else (box, normalisation, contrast) is re-derived here.

After extraction, the resulting `particles.star` carries RELION optics (`data_optics` with `rlnMicrographPixelSize` etc.) and is a normal RELION particle set; the foreign coordinate metadata (crYOLO confidence, Topaz FOM) survives only as `rlnAutopickFigureOfMerit` if it was mapped in.

---

## Common failures / red flags

- **Particles mirrored top↔bottom after import** → Y-flip (§2.1). Diagnose on one micrograph; fix with `relion_star_handler --operate rlnCoordinateY --multiply_by -1 --add_to <H-1>` before re-extracting the batch.
- **All particles uniformly off-centre / picks tiny or huge** → coordinate pixel frame mismatch. Foreign picks made at super-res or at a Topaz downscale must be **scaled** to the RELION micrograph frame (×0.5 super-res→2×-binned; ×downscale for standalone Topaz). The fixture frame is 0.53→1.06 Å/pix.
- **EMAN `.box` picks shifted by half a box** → corner-vs-centre: the file is corners but was read/written as centres (or vice-versa). Confirm 4-column corner+width format (§5).
- **`Import` shows red "coordinates files are missing"** → the input wildcard suffix doesn't match the actual files, or the micrograph rootname in the coordinate file's `rlnMicrographName` doesn't match the project's micrograph names. The wildcard **must** end in the coordinate suffix, e.g. `Movies/*.box` (Preprocessing.rst:292).
- **Forgot to re-extract** → you imported coordinates but have no particle images; downstream 2D/3D jobs have nothing to read. Importing picks is never enough (§6).
- **`relion_manualpick --help` errors with `libfltk.so.1.3: cannot open shared object file`** (manualpick.txt:5-11). The manual-picker is a GUI/FLTK binary and is not runnable headless on this install; do manual picking interactively or import foreign coordinates instead. This is expected, not a broken install.
- **Topaz training launched with multiple MPI ranks** → Topaz **training is not parallelised** and must be single-MPI (Autopicking.rst:450); only `--topaz_extract` picking parallelises. (Compare the analogous fixture trap in Polish/job040,041 where `relion_motion_refine_mpi` rejects parameter estimation in MPI mode — training/estimation steps want a single rank.)
- **Modest GPU memory:** Topaz train/extract need a GPU; on the 11 GB RTX 2080 Ti cards here, large boxes / many particles per micrograph can OOM — reduce `--topaz_nr_particles` or downscale.

---

## Cross-links

- **05_picking_extraction.md** — native RELION LoG/template/Topaz picking and extraction in depth (this file is the *interop* slice).
- **12_conventions_symmetry.md** — axis/handedness conventions, origin definitions.
- **16_interop_cryosparc.md** — cryoSPARC ↔ RELION coordinate/particle transfer, `csparc2star.py` (pyem), Y-flip across packages.
- **13_helical_amyloid.md** — helical picks (`rlnAnglePsi`, tube coordinates, amyloid).
- **01_star_and_metadata.md** — STAR table/label mechanics; **03_cli_inventory.md** — `relion_star_handler` / `relion_preprocess` flag reference.
- **20_troubleshooting.md**, **21_error_lookup.md** — broader failure triage.
- Sibling **skills**: **cryolo** (crYOLO execution, `.cbox` conversion, cryoSPARC external-picker), **cryosparc** (cryoSPARC SPA + its RELION interop boundary).

---

## Sources

- `relion_autopick --help` captured: `<RELION_SKILL_BUILD_ROOT>/references/cli/relion5_cli_capture_20260604/help/relion_autopick.txt` (Topaz wrapper flags, FOM map options).
- `relion_star_handler --help` captured: `.../help/relion_star_handler.txt` (`--combine_picks`, `--operate`/`--multiply_by`/`--add_to`, `--remove_duplicates`).
- `relion_preprocess --help` (live, `<RELION_BIN>/relion_preprocess`) + captured `.../help/relion_preprocess_mpi.txt` (`--coord_dir`, `--coord_suffix ".box"`, `--extract_size`, `--scale`, `--extract_bias_x/y`, `--minimum_pick_fom`, `--reextract_data_star`, `--recenter*`).
- `relion_import --help` (live + captured `.../help/relion_import.txt`): `--do_coordinates`, `--ofile`, `--odir`.
- `relion_manualpick --help` captured (`.../help/relion_manualpick.txt`): FLTK library failure (GUI-only).
- Docs: `.../source/relion-documents_release-5.0/source/SPA_tutorial/Autopicking.rst` (LoG/Topaz picking, `autopick.star`, `rlnAutopickFigureOfMerit`, FOM threshold at extraction, model_epoch10.sav, single-MPI training).
- Docs: `.../SPA_tutorial/Preprocessing.rst` (manual picking; supported foreign formats: ximdisp / xmipp-2.4 / EMAN `.box`; import wildcard+suffix rule).
- Docs: `.../Reference/Using-RELION.rst` (External-job picker contract: `coords_suffix_PICKNAME.star`, per-mic `<mic>_PICKNAME.star`, `RELION_OUTPUT_NODES.star` node type 2).
- Docs: `.../Reference/Conventions.rst:135-139,17` (rlnCoordinateX/Y units = micrograph pixels; origin = first element of MRC 2D array, displayed upper-left; TIFF slow-axis flip in MotionCor2/IMOD; right-handed system).
- Real fixture (READ-ONLY) `<RELION_PROJECT_FIXTURE>`: `Import/job015/coords_suffix.star` (`Micrographs/*.mrc`), `Import/job015/Micrographs/*_fractions.star` (3-column coord STAR), `Import/job015/note.txt` (`relion_import --do_coordinates`), `Extract/job016/note.txt` (`relion_preprocess_mpi … --coord_dir Import/job015/ --coord_suffix .star … --extract_size 220 --scale 60`).
