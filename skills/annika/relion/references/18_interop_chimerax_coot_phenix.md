# 18 — RELION maps -> ChimeraX / Coot / Phenix

## Scope
How to hand a finished RELION 5.0 reconstruction to a model-building / refinement / validation tool (ChimeraX, Coot, Phenix, REFMAC/Servalcat) without lying to the downstream program about what the data is: which of RELION's several maps to give it, how the MRC header (pixel size, origin, mode) travels with the file, the classic "downstream tool ignored the header pixel size" gotcha, and per-tool handoff recipes. Execution of each downstream tool is owned by its own skill (`chimerax`, `coot`, `phenix`, `mask`); this file is the RELION-side contract. Grounded in the live `relion_image_handler` / `relion_postprocess` help, the 5.0 SPA tutorial (`ModelBuilding.rst`, `Validation.rst`, `Mask.rst`), and the read-only fixture `<RELION_PROJECT_FIXTURE>/{phenix,ccp4}` (a real RELION 4.0-beta -> Phenix/CCP-EM handoff).

---

## 1. Which map to hand off — the single most important decision

RELION emits *several* maps from the same reconstruction. They are NOT interchangeable. Handing the wrong one to refinement is the most common interop error.

| RELION map (rootname) | What it is | Hand to | NEVER hand to |
|---|---|---|---|
| `PostProcess/jobNNN/postprocess.mrc` | Sharpened, FSC-weighted, lowpass-to-resolution, **unmasked** map | ChimeraX visual fit; ModelAngelo; Coot building; **DockInMap**; the "display map" for everything | — |
| `PostProcess/jobNNN/postprocess_masked.mrc` | Same but solvent-flattened by the FSC mask | ModelAngelo (tutorial uses this); quick visual | real-space refinement *as the data* (its solvent is zeroed and the mask edge is baked in) |
| `Refine3D/jobNNN/run_half1_class001_unfil.mrc` + `run_half2_class001_unfil.mrc` | The **two unfiltered half-maps** — the actual independent half-set data | Phenix `real_space_refine` (two-half-map mode), Servalcat/REFMAC half-map refinement, any FSC-honest / `model_vs_data` work | — |
| FSC / solvent mask `MaskCreate/jobNNN/mask.mrc` | The soft solvent mask used in post-processing | Phenix/Servalcat as the **mask** argument (not the data); resolution/FSC calculation | as a map to build into |
| `LocalRes/jobNNN/relion_locres.mrc` | Per-voxel local-resolution map (Å) | ChimeraX "color by volume data value" overlay on `postprocess.mrc` | refinement (it is a resolution field, not density) |
| `LocalRes/jobNNN/relion_locres_filtered.mrc` | Locally-filtered (+sharpened) map | Visual inspection of map-quality variation across the molecule | refinement *as the data* |

Source for the names: `relion_postprocess --help` (`--i run_half1_class001_unfil.mrc`, `--o (postprocess)`), `Mask.rst:64-101` (`Refine3D/job019/run_half1_class001_unfil.mrc`, `MaskCreate/job020/mask.mrc`, `PostProcess/job021/postprocess.mrc`), `Validation.rst:16,49,53` (`run_half1_class001_unfil.mrc`, `LocalRes/job031/relion_locres.mrc`, `relion_locres_filtered.mrc`), `ModelBuilding.rst:15,40,54` (`postprocess_masked.mrc`, `postprocess.mrc`).

### The golden rule
**Never hand a tight-masked sharpened map to refinement as if it were the data.** A sharpened map is a *processed* product: it has had a B-factor applied, FSC weighting applied, a lowpass applied, and (for `_masked`) the solvent set to zero with a soft edge. Real-space refinement against it will (a) over-fit to the sharpening artefacts, (b) report an inflated model-to-map CC, and (c) see a hard mask boundary as "signal". For honest refinement and for any FSC-based validation, give the program the **two unfiltered half-maps plus the FSC mask** and let *it* sharpen/weight internally. Use the sharpened map only for *visual* placement and for ML builders (ModelAngelo) that are trained to expect a sharpened input.

> Fixture caveat: the real PRC1/NeCen project (`<PROJECT_ROOT>/...`) actually refined against a *sharpened* map — `phenix/RealSpaceRefine_20/...real_space_refined_020.eff` has `real_map_files = ".../Autosharpen_2/sharpened_map.ccp4"` and `resolution = 2.9`. That is the common, pragmatic single-map workflow and it is fine for *building*. It is shown below as the real example, but note its `CC_mask` values (0.68 -> 0.75 in the log) are model-to-map CC against a *sharpened* map and should not be quoted as a resolution-honest validation number — for that, switch to half-maps (`map_model_cc` / `mtriage` with two halves).

---

## 2. MRC header conventions — what travels with the file

RELION writes the **pixel size into the MRC header** (cell dimensions / `MX,MY,MZ` so that `cella/MX = angpix`). Most downstream tools (ChimeraX, Phenix, Coot, Servalcat) read it from there. But the header can be wrong (a binned map written with the unbinned angpix, a rescaled box, a tool that imported a stack and lost it), and some tools silently trust a value *you* type over the header. Fixing the header is `relion_image_handler`'s job.

| Need | `relion_image_handler` flag | Effect | Source |
|---|---|---|---|
| Map is correct, header pixel size is wrong | `--force_header_angpix <A>` | Rewrites header pixel size, **does not rescale** voxels | help line 48/133 |
| Resample voxels to a new pixel size | `--rescale_angpix <A>` | Scales the image to that new pixel size (and updates header) | help line 47/132 |
| Resize box only | `--new_box <pix>` | Pad/crop box to new size (combine with rescale to match another box) | help line 49/134 |
| Tell IH the *current* pixel size of the input | `--angpix <A>` | Input pixel size (needed for resolution-aware ops like `--lowpass`) | help line 46/131 |
| Save half the disk (16-bit) | `--float16` | Writes **MRC mode 12** (half-precision float) instead of mode 0 (32-bit float) | help line 14/99 |
| Flip handedness | `--invert_hand` | Inverts hand (flips X but preserves symmetry origin; wraps edge pixels) | help line 54/139, `Validation.rst:63-68` |

Runnable examples (every `--o` is a NEW rootname; never overwrite the RELION output in place, and never write into the read-only fixture):

```bash
# Header says wrong pixel size but the map is geometrically correct: just fix the header.
relion_image_handler \
  --i  PostProcess/job039/postprocess.mrc \
  --o  handoff/postprocess_angpix_fixed.mrc \
  --force_header_angpix 1.06

# Actually resample a 1.06 A/pix map onto 1.10 A/pix (changes voxels AND header).
relion_image_handler \
  --i  PostProcess/job039/postprocess.mrc \
  --o  handoff/postprocess_1p10.mrc \
  --angpix 1.06 --rescale_angpix 1.10

# Flip handedness of a postprocessed map (from Validation.rst:63-68).
relion_image_handler \
  --i  PostProcess/job039/postprocess.mrc \
  --o  handoff/postprocess_invert.mrc \
  --invert_hand
```

### Origin
RELION reconstructions are centred on the box; RELION generally writes a **zero origin** in the header and expects the model to be placed in box (not microscope) coordinates. After REFMAC/Servalcat masked refinement the model can come back with a non-zero shift (the fixture has `ccp4/Refmac_Servalcat_2/shifts.json` and `shifted.pdb` / `shifted_refined.pdb` — Servalcat shifts the model into a cropped box and records the inverse shift to put it back). When a refined model "lands off the map" in ChimeraX, suspect an origin/shift mismatch, not a real fit failure — re-apply the recorded shift or open the matching `shifted*.mrc`/`.mtz`.

### The classic gotcha: a downstream tool ignores the header pixel size
Symptom: you open `postprocess.mrc` in ChimeraX or Phenix and the molecule is the wrong physical size, or `real_space_refine`/`mtriage` reports a nonsense resolution, or a fitted model is scaled. Causes and fixes:
- **The header angpix is actually wrong** (e.g. a super-res 0.53 Å/pix map mislabelled, or a 2× binned map still tagged 0.53). The PRC1 fixture is exactly this kind of pixel-size minefield: `rlnMicrographOriginalPixelSize 0.53` (super-res) -> `rlnMicrographPixelSize 1.06` (2× binned). The *map* angpix should be 1.06 for that project, not 0.53. Fix the file with `--force_header_angpix 1.06`.
- **The tool offers a "pixel size" / "voxel size" field and you typed one** — that override beats the header. Leave it blank (or type the header value) so the header is honoured.
- **Some converters drop the header** (e.g. when a map round-trips through a raw `.mrcs` stack). Re-stamp with `--force_header_angpix` before the handoff.
- A map renamed `.ccp4` vs `.mrc` is the *same* binary format (MRC2014); the extension does not change the header. CCP-EM/Phenix accept either. Phenix Autosharpen and ResolveCryoEM in the fixture write `.ccp4` (e.g. `Autosharpen_2/sharpened_map.ccp4`, `ResolveCryoEM_3/denmod_map.ccp4`); these open fine in RELION/ChimeraX as maps.

If you must confirm what the header *says* before shipping a map, `relion_image_handler --i map.mrc --stats` reports per-image statistics (help line 39/124); pixel size and box are also printed by most viewers on open. (For a dedicated header dump, ChimeraX `volume` / `mrcinfo` from the `chimerax` skill is more verbose than IH.)

---

## 3. Per-tool handoff

### 3.1 ChimeraX — open + rigid fit + local-res colouring
ChimeraX reads MRC/CCP4 pixel size and origin from the header, so a header-correct `postprocess.mrc` just opens at the right scale.

- **Visual placement / rigid-body fit**: open `postprocess.mrc` and your model, then `fitmap`/`fit in map`. RELION 5.0's ModelAngelo output (`ModelAngelo/jobNNN/jobNNN.cif`) is meant to be viewed against `postprocess.mrc` (`ModelBuilding.rst:40`).
- **Handedness check**: the only practical absolute-hand test is whether an atomic model fits; if α-helices coil the wrong way, flip the map with `--invert_hand` (§2) and re-fit (`Validation.rst:57-76`).
- **Colour by local resolution**: open `postprocess.mrc`, then colour its surface "by volume data value" browsing to `LocalRes/jobNNN/relion_locres.mrc` (`Validation.rst:49-53`; the tutorial wording is the old Chimera menu, the ChimeraX equivalent is `color sample` / Surface Color).
- Execution (scripted/headless `.cxc`, `fitmap`, `matchmaker`, measurements, ISOLDE flexible fitting): use the **chimerax** skill. To build a *model-based* mask for local refinement, use the **mask** skill (ChimeraX `molmap` -> binarize/dilate/soft-edge -> resample) — RELION's own `relion_mask_create` makes *density-threshold* masks; model-based mask creation is owned by the **mask** skill.

### 3.2 Coot — interactive/scripted local rebuild
Coot reads the MRC header for the map and opens the model in the same frame. In the fixture, Coot was driven against both the Phenix and the CCP-EM products:
- `phenix/0-coot-history.py`: `handle_read_draw_molecule_with_recentre(".../RealSpaceRefine_20/PCGF1_Merge_M1_real_space_refined_020.pdb", 1)`, then `set_contour_level_in_sigma(1.50)` and residue deletions — i.e. open the refined model, contour the map, and trim bad residues.
- `ccp4/0-coot-history.py`: opens `phenix/PCGF1_Merge_M1.pdb` and `ccp4/Refmac_Servalcat_2/refined.pdb`, and a **difference map** via `make_and_draw_map_with_reso_with_refmac_params(".../Refmac_Servalcat_2/diffmap.mtz", "DELFWT", "PHDELWT", ...)`. Note: Coot prefers an **MTZ with amplitudes+phases** for difference maps; CCP-EM's *MRCtoMTZ* task converted the sharpened `.ccp4` to `ccp4/MRCtoMTZ_1/starting_map.mtz` for exactly this reason (`args.json`: `input_map = ".../Autosharpen_2/sharpened_map.ccp4"`, `resolution: 2.9`). RELION does not write MTZ; that conversion is a CCP-EM / Phenix step, not a RELION one.
- Execution (`coot --no-graphics`, fit-protein, add-waters, auto-fit-rotamer, dictionaries, Refmac-from-Coot): use the **coot** skill.

### 3.3 Phenix — real-space refine / sharpen / dock / validate
Phenix reads the MRC/CCP4 header pixel size; you additionally pass the **resolution** (RELION's reported FSC=0.143 resolution from `postprocess.star` `_rlnFinalResolution`). The fixture shows the real Phenix surface:

| Fixture Phenix job | RELION input it consumed | Output | Maps to |
|---|---|---|---|
| `Autosharpen_1/2/21` | a RELION map -> sharpened | `sharpened_map.ccp4` (+ `_coeffs.mtz`; `_21` is `..._RL_refine_079.ccp4`) | `phenix.auto_sharpen` |
| `DockInMap_5,11,16,17,18` | sharpened map + search model | `placed_model.pdb` / `placed_model_modified.pdb` | `phenix.dock_in_map` |
| `RealSpaceRefine_14,19,20` | `Autosharpen_2/sharpened_map.ccp4` + model + `resolution=2.9` | `..._real_space_refined_020.{pdb,cif,log,eff,geo}` | `phenix.real_space_refine` |
| `ResolveCryoEM_3` | half-maps -> density modification | `denmod_map.ccp4`, `denmod_half_map_1/2.ccp4`, `initial_map.ccp4` | `phenix.resolve_cryo_em` |

- **`phenix.real_space_refine`**: give it the **sharpened map + resolution** for ordinary building (the fixture path), OR the **two half-maps** for an FSC-honest refinement+validation. Either way you also need the model. The fixture `.eff` records `real_map_files = ".../Autosharpen_2/sharpened_map.ccp4"`, `resolution = 2.9`, `nproc = 1`, `resolution_factor = 0.25` — these are the load-bearing inputs.
- **`phenix.auto_sharpen`** = the fixture **Autosharpen** job. It produces `sharpened_map.ccp4` (+ a coefficients MTZ). Use it when RELION's B-factor sharpening is not enough or you want Phenix-style local sharpening; otherwise RELION `postprocess.mrc` is already sharpened.
- **DockInMap** = `phenix.dock_in_map`: places a search model into the (sharpened) map -> `placed_model.pdb`. Good first step before `real_space_refine` when you only have a homolog/AlphaFold model (fixture `models/AF_PCGF1.pdb`, `1kx5.pdb`, `2ckl.pdb`, `5lbn.pdb`).
- **Validation**: `phenix.mtriage` (map/half-map FSC and resolution — feed the **two half-maps** + mask, NOT the sharpened map), `phenix.emringer` (model-vs-map side-chain validation against the sharpened map), `phenix.molprobity`/`map_model_cc` for geometry and CC. EMRinger and `map_model_cc` are happy with the sharpened map; FSC/resolution numbers must come from half-maps.
- Execution (`phenix.real_space_refine`, `phenix.auto_sharpen`, `phenix.dock_in_map`, `phenix.emringer`, `.eff`/`.params` files): use the **phenix** skill. For *strategy* (what to run, in what order, when stuck) consult the **structural-strategy** skill; for primary-source method questions, **cryo-em-knowledge**.

### 3.4 REFMAC / Servalcat (CCP-EM) — the other refinement path
The fixture's `ccp4/Refmac_Servalcat_2` shows the CCP-EM masked-refinement route: `args.json` consumed `input_map = ".../Autosharpen_2/sharpened_map.ccp4"`, `start_pdb = ".../PCGF1_Merge_M1.pdb"`, `resolution = 2.9`, with `masked_refinement_on: true`, `jelly_body: true`, `ncycle: 20`. It writes `refined.pdb`, a `diffmap.mtz` (used for the Coot difference map above), `refined_fsc.json/.log`, and `shifted*` files (the box-shift bookkeeping noted in §2). Servalcat can also take the **two half-maps** directly (`half_map_1`/`half_map_2` in `args.json`, here `null` because this run used the single sharpened map) for FSC-weighted refinement — the half-map path is the honest one, same principle as Phenix. RELION is the upstream map source either way; CCP-EM owns the refinement. (No dedicated CCP-EM skill is installed; drive REFMAC-from-Coot via the **coot** skill, or run `servalcat`/`refmacat` directly.)

---

## 4. Common failures / red flags

- **"Refined model has impossibly good CC / overfits"** — you refined against a `_masked` or sharpened map and treated its CC as a quality metric. Re-validate with `phenix.mtriage` / `map_model_cc` against the **two half-maps**, not the sharpened map.
- **Model lands off the density / wrong physical size in ChimeraX/Phenix** — header pixel size is wrong, or a per-tool "voxel size" override was typed. Re-stamp with `relion_image_handler --force_header_angpix <A>` (use the project's *binned* angpix, e.g. 1.06 for the PRC1 fixture, NOT the super-res 0.53). Or, post-refinement, an unapplied Servalcat box shift (`shifts.json` / `shifted*.pdb`).
- **Difference map won't load in Coot** — Coot wants an MTZ with `DELFWT/PHDELWT` (or `FWT/PHWT`); RELION writes no MTZ. Convert via CCP-EM *MRCtoMTZ* (fixture `MRCtoMTZ_1/starting_map.mtz`) or let Servalcat/REFMAC emit `diffmap.mtz`.
- **Phenix/ChimeraX reports a resolution that disagrees with RELION** — they may be computing unmasked or half-map FSC over a different mask. RELION's number is the masked FSC=0.143 in `postprocess.star`. Mismatch is expected; do not "fix" RELION's processing to match a downstream unmasked number.
- **Wrong hand** — α-helices coil the wrong way and *no* sensible model fits. Flip the map with `--invert_hand` and re-dock; SGD initial models have a 50% chance of the mirror hand (`Validation.rst:57-76`).
- **`.ccp4` vs `.mrc` confusion** — they are the same MRC2014 container; extension is cosmetic. Do not "convert" between them, just open.

---

## 5. Version notes (5.0-accurate, version-aware)
- **5.0** ships **ModelAngelo** (`ModelAngelo building` job) which consumes a *sharpened* map (`postprocess_masked.mrc` in the tutorial) and a FASTA, emitting a `.cif` to refine/inspect (`ModelBuilding.rst:13-41`). This is the recommended automated-build entry to the ChimeraX/Coot/Phenix loop. **Blush** (regularised refinement) and **DynaMight** (flexibility) also originate in 5.0 but change the *map*, not the handoff format.
- **4.0** introduced the class-ranker and the tomo rewrite; the **PRC1 fixture is a 4.0-beta project** read by this 5.0 install — older `Refine3D`/`MaskCreate`/`PostProcess` node names are unchanged and the half-map/postprocess filenames above still apply.
- **3.1** added optics groups; pixel size lives per-optics-group in the STAR and is stamped into map headers from there. A pre-3.1 map may carry only a header angpix.
- The handoff *files* (MRC half-maps, sharpened MRC, solvent mask) are format-stable across 3.1/4.0/5.0; only the GUI job names and a few node labels move.

---

## Cross-links
- `09_mask_postprocess_localres.md` — produces `postprocess.mrc`, `postprocess_masked.mrc`, `postprocess.star` (with `_rlnFinalResolution`), the FSC mask, and `relion_locres*.mrc`; the upstream of everything here.
- `08_refine3d.md` — produces the `run_half1/2_class001_unfil.mrc` half-maps you hand to Phenix/Servalcat.
- `11_subtract_multibody.md` — focused/subtracted maps that also get handed off.
- `12_conventions_symmetry.md` — box origin, handedness, symmetry-axis conventions that matter when a model "lands off the map".
- `19_interop_coordinates.md` — model/coordinate round-trips (PDB/CIF, shifts) complementary to map handoff.
- `16_interop_cryosparc.md`, `17_interop_cryodrgn.md` — sibling interop chapters (map/particle exchange).
- `20_troubleshooting.md`, `21_error_lookup.md` — generic failure triage.

### Sibling skills that own execution
- **chimerax** — `fitmap`/`matchmaker`/measurements/ISOLDE, scripted `.cxc`, local-res colouring.
- **coot** — `coot --no-graphics` rebuild, ligand/water fitting, difference maps, Refmac-from-Coot.
- **phenix** — `real_space_refine`, `auto_sharpen`, `dock_in_map`, `emringer`, `mtriage`, `.eff`/`.params`.
- **mask** — model-based mask creation (ChimeraX `molmap`); RELION makes density-threshold masks only.
- **structural-strategy** — what to run, in what order, when stuck (read-only decision guide).
- **cryo-em-knowledge** / **cryo-flex-knowledge** — primary-source method/validation questions.

---

## Sources
- Live binary help (read from capture, identical to running `relion_image_handler --help` / `relion_postprocess --help` on the 5.0.0-commit-3d6c20 install): `<RELION_SKILL_BUILD_ROOT>/references/cli/relion5_cli_capture_20260604/help/relion_image_handler.txt`, `.../relion_postprocess.txt`.
- `<RELION_SKILL_BUILD_ROOT>/references/source/relion-documents_release-5.0/source/SPA_tutorial/ModelBuilding.rst` (ModelAngelo; `postprocess.mrc` / `postprocess_masked.mrc` -> ChimeraX/Coot).
- `.../SPA_tutorial/Validation.rst` (local-resolution `relion_locres.mrc` / `relion_locres_filtered.mrc`; `--invert_hand`; ChimeraX colour-by-local-res).
- `.../SPA_tutorial/Mask.rst` (postprocess inputs: `run_half1_class001_unfil.mrc`, `MaskCreate/job020/mask.mrc`, `PostProcess/job021/postprocess.mrc`).
- Read-only fixture `<RELION_PROJECT_FIXTURE>/phenix/` (`Autosharpen_1/2/21`, `DockInMap_5/18`, `RealSpaceRefine_20/...real_space_refined_020.{eff,log}`, `ResolveCryoEM_3`, `0-coot-history.py`, `models/`) and `.../ccp4/` (`MRCtoMTZ_1/args.json`+`starting_map.mtz`, `Refmac_Servalcat_2/args.json`+`diffmap.mtz`+`shifts.json`+`shifted*.pdb`, `0-coot-history.py`).
- Sibling reference cross-checked for naming consistency: `09_mask_postprocess_localres.md`.
