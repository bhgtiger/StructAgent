# 01 — STAR format, rln* labels, data_optics

## Scope
How RELION 5.0 stores all metadata: the STAR text format it reads/writes, the atomic write-by-rename that protects half-written files, the `rln*` label vocabulary (grouped with real types from the installed build), the `data_optics` + `data_particles` two-block layout introduced in 3.1, how `--print_metadata_labels` is the authoritative label list for *your* binary, and the `relion_star_handler` / `relion_convert_star` tools for combining, splitting, selecting, operating on, and histogramming STAR files. Grounded against the installed `5.0.0-commit-3d6c20` binary, the pinned source, and the read-only 4.0-beta fixture.

---

## 1. STAR syntax as RELION uses it

RELION uses the **STAR** (Self-defining Text Archiving and Retrieval) format for *all* input/output metadata (`Conventions.rst` lines 64-89). Rules RELION enforces:

| Element | Syntax | Notes |
|---|---|---|
| Extension | `.star` | File name must end in `.star` (`Conventions.rst:73`). |
| Data block | `data_<name>` | One or more per file; `<name>` is optional (e.g. `data_optics`, `data_particles`, `data_images`). |
| Table | `loop_` then `_label #N` header lines, then whitespace-delimited value rows | A loop **must be followed by an empty line** to mark its end (`Conventions.rst:78`). |
| List (key→value) | `_label  value` pairs, one per line, **no** `loop_` | Used for single-record blocks (e.g. `data_general`, `data_job`). `readStarList` in `metadata_table.h:294`. |
| Label | starts with `_`, used once per block | e.g. `_rlnVoltage`. |
| Quoting | double-quote `"` for strings with spaces; `""` = empty string | `Conventions.rst:87-88`. |
| Comments | `#` (or leading `;`) on its own line; `#` after a value; all text before first `data_` | three comment positions (`Conventions.rst:83-86`). |
| Values | numeric or whitespace-free strings | space-containing strings must be quoted. |

A block can hold **both** a list and a loop; `MetaDataTable::readStar` returns 2 then 1 in that case (`metadata_table.h:296-307`).

**Atomic write-by-rename (no partial reads).** `MetaDataTable::write(fn_out)` writes to `fn_out + ".tmp"`, closes it, then `std::rename(fn_tmp, fn_out)` (`metadata_table.cpp:1521-1533`). The in-source comment is explicit: *"Rename to prevent errors with programs in pipeliner reading in incomplete STAR files."* Practical consequence: a `*.star` that exists is complete; if you ever see a `*.star.tmp` lingering, a writer crashed mid-write. Never assume a partially-written `.star`.

**Unknown-label tolerance.** RELION does not choke on labels it does not recognise. Unknown columns are stored under a single internal `EMDL_UNKNOWN_LABEL` and round-tripped via `unknownLabelNames` (`metadata_table.h:89-98, 120-121`). So a STAR file carrying foreign columns (e.g. from cryoSPARC-derived conversions, or a newer RELION) is read, preserved on write, and ignored by programs that do not need it — but two files with the *same* unknown labels in *different order* are still comparable (`metadata_table.h:92-93`).

---

## 2. The `data_optics` + `data_particles` two-block layout (3.1+)

RELION **3.1** introduced optics groups (`Conventions.rst:100-112`). Since then a particle/micrograph STAR file is **two blocks**: a `data_optics` table whose rows describe optical properties per group, and a `data_<movies|micrographs|particles>` table whose rows reference an optics group via the integer `rlnOpticsGroup` column (`Conventions.rst:106`). `rlnOpticsGroupName` (string) is what is matched when merging two files; differently-named groups are kept distinct and `rlnOpticsGroup` IDs get re-numbered (`Conventions.rst:107-108`).

**Real fixture `data_optics` block** (`<RELION_PROJECT_FIXTURE>/particles.star`, READ-ONLY, written by RELION 4.0-beta):

```
# version 30001

data_optics

loop_
_rlnOpticsGroupName #1
_rlnOpticsGroup #2
_rlnMtfFileName #3
_rlnMicrographOriginalPixelSize #4
_rlnVoltage #5
_rlnSphericalAberration #6
_rlnAmplitudeContrast #7
_rlnMicrographPixelSize #8
opticsGroup1            1 ../../other/MTF/mtf_k3_standard_300kV_FL2.star  0.530000  300.000000  2.700000  0.100000  1.060000
```

Read it as: one optics group, K3 super-resolution physical pixel `rlnMicrographOriginalPixelSize 0.53` Å binned 2× to `rlnMicrographPixelSize 1.06` Å, 300 kV, Cs 2.7 mm, amplitude contrast 0.1, detector MTF `mtf_k3_standard_300kV_FL2.star`.

Notes on this specific fixture file:
- The `# version 30001` tag in the header is *not* the RELION release; it is the STAR-format version (`5.0001`-style integer; version tags were introduced at 31000, `metadata_table.cpp:1213`). A 4.0-beta project read by a 5.0 install is normal — older projects upgrade transparently (`Conventions.rst:110-111`).
- Here the second block is `data_particles` but holds only `_rlnMicrographName / _rlnCoordinateX / _rlnCoordinateY` — i.e. it is a **coordinate / extract-input** list, not aligned particles. A post-Refine3D `run_data.star` would additionally carry `rlnImageName`, the CTF columns, and the orientation columns (section 3).

**Pixel-size split (3.1+ gotcha):** with optics groups, the pixel size lives in `data_optics` (`rlnImagePixelSize` for particles, `rlnMicrographPixelSize` for micrographs), **not** per-row. Older 3.0 files had no optics block and you must pass `--angpix`. See `--ignore_optics` below.

---

## 3. The `rln*` label vocabulary (grouped, with installed types)

Types below are exactly as `relion_refine --print_metadata_labels` prints them on this build (the parenthesised type is authoritative for whether a column is `int`/`double`/`string`/`bool`/`vector<double>`). The enum backing these labels is `EMDLabel` in `metadata_label.h`.

### Optics (`data_optics` columns)
| Label | Type | Meaning |
|---|---|---|
| `rlnOpticsGroup` | int | Integer group id referenced from the particle table |
| `rlnOpticsGroupName` | string | Group name; used when merging files |
| `rlnVoltage` | double | Microscope voltage (kV) |
| `rlnSphericalAberration` | double | Cs (mm) |
| `rlnAmplitudeContrast` | double | Q0, as a fraction (10% = 0.1) |
| `rlnMicrographOriginalPixelSize` | double | Pixel size of original movie *before* binning (Å/pix) |
| `rlnMicrographPixelSize` | double | Pixel size of averaged micrograph *after* binning (Å/pix) |
| `rlnImagePixelSize` | double | Pixel size of extracted particle images (Å) |
| `rlnImageSize` | int | Box size of an image (pixels) |
| `rlnMtfFileName` | string | STAR file with the detector MTF for this group |
| `rlnBeamTiltX` / `rlnBeamTiltY` | double | Beam tilt (mrad) |
| `rlnOddZernike` | vector<double> | Antisymmetric Zernike coeffs (beam tilt / odd aberrations) |
| `rlnEvenZernike` | vector<double> | Symmetric Zernike coeffs (Cs-like / even aberrations) |
| `rlnMagMatrix_00`..`rlnMagMatrix_11` | double | Anisotropic-magnification 2×2 matrix |

Zernike ordering is fixed and unnormalised: `rlnOddZernike` = Z₁⁻¹, Z₁¹, Z₃⁻³, Z₃⁻¹, Z₃¹, Z₃³…; `rlnEvenZernike` = Z₀⁰, Z₂⁻², Z₂⁰, Z₂², Z₄⁻⁴… and the 7th even term relates to a Cs error (`Conventions.rst:148-156`).

### Micrograph / movie
| Label | Type | Meaning |
|---|---|---|
| `rlnMicrographName` | string | Aligned, summed micrograph |
| `rlnMicrographMovieName` | string | Movie stack (pre-motioncorr) |
| `rlnMicrographGainName` | string | Gain reference |
| `rlnMicrographNameNoDW` | string | Micrograph without dose-weighting |
| `rlnMicrographNameEven` / `rlnMicrographNameOdd` | string | Even/odd frame sums (for denoising / FSC) |
| `rlnAccumMotionTotal/Early/Late` | double | Global motion (Å) from MotionCorr |

### Coordinate
| Label | Type | Meaning |
|---|---|---|
| `rlnCoordinateX` / `rlnCoordinateY` | double | Pick position in the micrograph, **pixels** in the aligned/summed (possibly binned) micrograph; origin = first array element = upper-left (`Conventions.rst:137-139`) |
| `rlnCoordinateZ` | double | Z position in a 3D tomogram (pixels) |
| `rlnCenteredCoordinateXAngst` / `…YAngst` / `…ZAngst` | double | Centre-origin coords in Å (5.0 tomo convention; center is 0,0) |

### CTF
| Label | Type | Meaning |
|---|---|---|
| `rlnDefocusU` / `rlnDefocusV` | double | Defocus (Å, positive = underfocus) |
| `rlnDefocusAngle` | double | Astigmatism angle between X and U (degrees) |
| `rlnCtfFigureOfMerit` | double | CTF-fit FOM (CC); *not* used inside `relion_refine` |
| `rlnCtfMaxResolution` | double | Max resolution of significant Thon rings (Å) — your per-micrograph quality knob |
| `rlnPhaseShift` | double | Phase-plate phase shift (degrees) |
| `rlnCtfAstigmatism` | double | |DefocusU − DefocusV| (Å) |
| `rlnCtfImage` | string | Name of CTF model image |

CTF parameters follow the CTFFIND4.1 definition (`Conventions.rst:145`).

### Image
| Label | Type | Meaning |
|---|---|---|
| `rlnImageName` | string | Particle image as `index@stack`, e.g. `000042@Extract/job010/.../parts.mrcs` (`Conventions.rst:22-29`) |
| `rlnImageOriginalName` | string | Original name before re-extraction |

MRC convention: 3D maps `.mrc`, 2D stacks `.mrcs`; image *n* in a stack is `n@file.mrcs`, 1-indexed (`Conventions.rst:20-29`).

### Orientation (alignment output)
| Label | Type | Meaning |
|---|---|---|
| `rlnAngleRot` | double | First Euler (rot), around Z (degrees) |
| `rlnAngleTilt` | double | Second Euler (tilt), around new Y |
| `rlnAnglePsi` | double | Third Euler (psi), around new Z; in-plane for 2D |
| `rlnOriginXAngst` / `rlnOriginYAngst` | double | Origin-of-rotation offset (Å), 3.1+ unit |
| `rlnOriginX` / `rlnOriginY` | double | Same offset in **pixels** — the pre-3.1 form (`Conventions.rst:135`) |
| `rlnAngleRotPrior` / `rlnAngleTiltPrior` / `rlnAnglePsiPrior` | double | Prior centres (helical / constrained search) |

Convention (`Conventions.rst:115-135`): the three Euler angles **rotate the reference into the observation**; the `rlnOrigin*Angst` translations **shift the observation into the reference projection** and are applied *before* rotation. RELION's Euler convention matches XMIPP/SPIDER/FREALIGN. See `12_conventions_symmetry.md`.

### Class / model / per-particle stats
| Label | Type | Meaning |
|---|---|---|
| `rlnClassNumber` | int | Class with the particle's highest probability |
| `rlnGroupName` | string | Image group (intensity-scale / noise group, e.g. per-micrograph) |
| `rlnGroupNumber` | int | Numeric group id |
| `rlnNrOfSignificantSamples` | int | Number of orientation/class assignments with significant probability (1st adaptive-oversampling pass) — a per-particle "how peaked is the alignment" diagnostic |
| `rlnClassDistribution` | double | PDF (fraction of images) per class — `*_model.star` |
| `rlnEstimatedResolution` | double | Per-class/ref resolution (Å) — `*_model.star` |
| `rlnClassScore` / `rlnClassPredictedScore` | double | Class-ranker (4.0+) scores |
| `rlnMaxValueProbDistribution` *(via optimiser)* / `rlnLogLikeliContribution` | — | per-particle likelihood diagnostics (confirm exact spelling via `--print_metadata_labels` if used) |

The full enum is far larger (~320 labels: BODY_*, MLMODEL_*, OPTIMISER_*, SAMPLING_*, JOB*, PIPELINE*, TOMO*, CLASS_FEAT_* class-ranker features, etc., `metadata_label.h`). For `job.star`, `default_pipeline.star`, and the `_rlnJob*` / `_rlnPipeLine*` labels see `02_project_job_tree.md`.

---

## 4. `--print_metadata_labels` is the source of truth for the build

The label list is compiled into the binary. The canonical way to ask *your* installed RELION what labels exist and what type each is:

```
relion_refine --print_metadata_labels
```

This is what `Conventions.rst:90-98` points users to. The underlying source is the `EMDLabel` enum + `StaticInitialization` in `src/metadata_label.h`. **Always trust the live `--print_metadata_labels` output over any table, including this one** — a different commit can add labels (e.g. 5.0 added Blush `rlnDoBlush`, tomo `rlnCenteredCoordinate*Angst`, AreTomo2 scores; 5.1 adds amyloid-related labels). On this build it printed under the banner `+++ RELION MetaDataLabel (EMDL) definitions: +++`.

---

## 5. `relion_star_handler` — combine / split / select / compare / operate / hist / dedupe

All flags below are from the installed `5.0.0-commit-3d6c20` help (captured `relion_star_handler.txt`; verifiable live with `relion_star_handler --help`). General: `--i` input STAR file(s), `--o` output (default `out.star`).

| Operation | Flags | Notes |
|---|---|---|
| Combine | `--combine` with multiple filenames inside double-quotes after `--i`; `--combine_picks` for manual/autopick coord files; `--check_duplicates rlnImageName` | string label only for the dup check |
| Split | `--split` + `--nr_split N` and/or `--size_split M`; `--random_order` (+`--random_seed`) | equal-sized and/or fixed-size chunks |
| Select (numeric) | `--select rlnCtfMaxResolution --minval … --maxval …` | inclusive bounds |
| Select (string) | `--select_by_str rlnMicrographName --select_include STR` / `--select_exclude STR` | substring match |
| Discard on image stats | `--discard_on_stats --discard_label rlnImageName --discard_sigma 4` | drop outlier images |
| Compare | `--compare other.star --label1 … [--label2 --label3] --max_dist D` | 2D/3D distance compare across files |
| Operate | `--operate LABEL [--operate2 --operate3]` + one of `--set_to` / `--multiply_by` / `--add_to` | bulk column edit |
| Centering | `--center --center_X/_Y/_Z` | shift particles to a reference position (pix) |
| Column edit | `--remove_column LABEL`; `--add_column LABEL` + `--add_column_value V` or `--copy_column_from LABEL` | |
| Histogram | `--hist_column LABEL [--hist_bins N --hist_min --hist_max] [--in_percent] [--show_cumulative]` | default bins by Freedman–Diaconis |
| Remove duplicates | `--remove_duplicates D` (distance in **Å**); `--image_angpix A` for down-sampled particles | negative disables |
| 3.0 compat | `--ignore_optics` + `--angpix A` + `--i_tablename NAME` | read an old single-block (no `data_optics`) file as RELION-3.0 |

**Runnable examples** (outputs point at NEW rootnames; never write into the fixture):

```bash
# Histogram of CTF max-resolution to see micrograph quality spread
relion_star_handler --i CtfFind/job003/micrographs_ctf.star \
  --hist_column rlnCtfMaxResolution --o /tmp/ctfres_hist.star

# Keep only particles whose CTF fit resolves better than 5 A
relion_star_handler --i Refine3D/job050/run_data.star \
  --select rlnCtfMaxResolution --minval 0 --maxval 5 \
  --o Select/myselect/particles.star

# Combine several coordinate files into one
relion_star_handler --combine --i "j1/parts.star j2/parts.star" \
  --check_duplicates rlnImageName --o /tmp/combined.star

# Remove duplicate picks within 100 A
relion_star_handler --i particles.star --remove_duplicates 100 \
  --image_angpix 1.06 --o /tmp/dedup.star
```

`removeDuplicatedParticles()` (`metadata_table.h:389-391`) groups by micrograph and a distance threshold in px, scaling Origin by `origin_scale` to compensate for down-sampling — which is why `--image_angpix` matters for binned particles.

---

## 6. `relion_convert_star` — upgrade old STAR / fix optics

Installed help (`relion_convert_star --help`):

| Flag | Meaning |
|---|---|
| `--i` | Input STAR to convert |
| `--o` | Output STAR |
| `--Cs` | Spherical aberration (mm) to inject |
| `--Q0` | Amplitude contrast to inject |
| `--box_size` | Image box size when the image stack is missing (assumes a 2D stack) |

Use this to manually convert a pre-3.1 (3.0, no `data_optics`) file into the modern two-block layout — RELION 3.1+ also does this automatically on read (`Conventions.rst:110-111`). Downgrading 3.1→3.0 is not officially supported (`Conventions.rst:112`).

---

## Common failures / red flags

- **`File ...run_data.star does not exist`** — a downstream program got a path to a STAR that was never produced (e.g. an upstream job failed before writing). Seen in the fixture MultiBody/job087,089 chain after `relion_flex_analyse` hit "A GPU-function failed to execute". The missing-file error is a *symptom*; find the first failure. See `21_error_lookup.md`.
- **Pixel size "wrong" after import** — with optics groups the pixel size is in `data_optics` (`rlnMicrographPixelSize` / `rlnImagePixelSize`), not per row. If a tool reports angpix=1.0, you likely fed a 3.0-style file and need `--angpix` / `--ignore_optics`, or the `data_optics` block is missing.
- **`--combine` reads only the first file** — the multiple filenames must be inside **one** pair of double-quotes after `--i` (help line for `--combine`).
- **`rlnOriginX` vs `rlnOriginXAngst` mismatch** — pixels (pre-3.1) vs Å (3.1+). Mixing them silently mis-shifts particles. Confirm units with `--print_metadata_labels`.
- **Stray `*.star.tmp`** — a writer crashed mid-write (the atomic rename never completed). The real `.star` may be stale; re-run the producing job.
- **Foreign columns survive but are ignored** — unknown labels round-trip (section 1); do not assume RELION "used" a column just because it is still present.

## Cross-links

- `00_overview.md` — skill map and what each reference covers.
- `02_project_job_tree.md` — `job.star`, `note.txt`, `default_pipeline.star`, exit sentinels, `_rlnJob*` / `_rlnPipeLine*` labels.
- `03_cli_inventory.md` — full `relion_*` binary list and where each help lives.
- `12_conventions_symmetry.md` — Euler-angle / origin / symmetry conventions in depth.
- `16_interop_cryosparc.md` — `csparc2star.py` (pyem) producing RELION STAR; unknown-label tolerance on import.
- `19_interop_coordinates.md` — coordinate STAR / pick-file formats and `--combine_picks`.
- `20_troubleshooting.md`, `21_error_lookup.md` — missing-file and write-race diagnosis.

## Sources

- `relion_refine --print_metadata_labels` — live, installed `5.0.0-commit-3d6c20` (label names + types).
- `relion_star_handler --help` — live; matches captured `references/cli/relion5_cli_capture_20260604/help/relion_star_handler.txt`.
- `relion_convert_star --help` — live, installed.
- `src/metadata_label.h` (pinned 5.0 source) — `EMDLabel` enum, label grouping.
- `src/metadata_table.h` (pinned) — STAR read/write API, list-vs-loop, unknown-label handling, `removeDuplicatedParticles`, `compareLabels`.
- `src/metadata_table.cpp:1213, 1521-1533` (pinned) — atomic write-by-rename (`fn_out.tmp` → `std::rename`), STAR version-tag note.
- `source/Reference/Conventions.rst` (pinned docs) — STAR rules, optics groups, orientations, image/MRC conventions, Zernike ordering, CTF.
- `<RELION_PROJECT_FIXTURE>/particles.star` (READ-ONLY fixture) — real `data_optics` block.
