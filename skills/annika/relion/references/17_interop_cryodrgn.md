# 17 — RELION -> cryoDRGN

## Scope
How to hand a clean **consensus** RELION 3D refinement (particle stack + per-particle poses + CTF) to **cryoDRGN** for continuous-heterogeneity / latent-space analysis: downsample to a small box, convert poses and CTF to cryoDRGN `.pkl`, `train_vae`, and `analyze`. cryoDRGN is not a RELION program — it lives in a conda env on this server (`<CRYODRGN_ENV>`, currently cryoDRGN 3.4.2), **not on base PATH**. RELION's only jobs here are producing the consensus refinement and (optionally) re-extracting/downsampling the stack. For the *why/when* of continuous heterogeneity, latent-space interpretation, and overfitting checks, defer to the **cryo-flex-knowledge** skill; this file is the mechanical RELION->cryoDRGN bridge only.

---

## 0. The mental model: what cryoDRGN needs from RELION

cryoDRGN does **not** re-estimate poses or CTF by default. It trusts the consensus poses you give it and learns only the per-particle latent code `z`. So the entire success of a cryoDRGN run depends on giving it:

| cryoDRGN input | RELION source | cryoDRGN file (fixture name) |
|---|---|---|
| Particle image stack (single `.mrcs`/`.star`, ideally small box) | re-extracted/downsampled particles | `particles_110.mrcs` |
| Per-particle poses (Euler angles + origin offsets) | `_data.star` from Refine3D (`rlnAngleRot/Tilt/Psi`, `rlnOriginXAngst/YAngst`) | `pose.pkl` |
| Per-particle CTF | same `_data.star` optics + per-particle defocus | `ctf.pkl` |

The poses and CTF `.pkl` are derived from the **same** `_data.star`, and that STAR file must describe the **exact** stack you train on, in the **same row order**. Mismatch = silently wrong volumes, not an error.

Fixture used as the worked example (READ-ONLY, do not write into it):
`<RELION_PROJECT_FIXTURE>/cryodrgn/RL_rf075_box110/`
The folder name encodes provenance: **R**e**L**ion **r**e**f**ine **job075**, **box 110**. Its consensus source is `Refine3D/job075/run_data.star` (NeCen/PRC1 nucleosome, RELION 4.0-beta project). The sibling `RL_rf079_box110/` is the same idea from job079.

---

## 1. Start from a CLEAN consensus refinement

cryoDRGN models heterogeneity **on top of** fixed consensus poses; it cannot rescue a bad alignment. Inputs must be:

- A finished **Refine3D** (gold-standard auto-refine) `_data.star`, **not** a Class3D class or a half-cleaned Select set. The fixture consensus is `Refine3D/job075/run_data.star` (auto-refine, C1, `RELION_JOB_EXIT_SUCCESS`).
- Junk already removed (2D/3D class selection, no duplicate picks, no ice/edge particles). cryoDRGN will happily allocate latent dimensions to garbage.
- One optics group with sane CTF. The fixture's `data_optics`: `_rlnMicrographOriginalPixelSize 0.53` (super-res K3) -> `_rlnImagePixelSize 1.060000`, `_rlnVoltage 300`, `_rlnSphericalAberration 2.7`, `_rlnAmplitudeContrast 0.1`, `_rlnImageSize 220`. Particle count `307172`.

The executed consensus command (from `Refine3D/job075/note.txt`):
```
relion_refine_mpi --o Refine3D/job075/run --auto_refine --split_random_halves \
  --i CtfRefine/job074/particles_ctf_refine.star --ref Refine3D/job065/run_class001.mrc \
  --ini_high 20 --ctf --particle_diameter 180 --flatten_solvent --zero_mask \
  --healpix_order 2 --auto_local_healpix_order 4 --offset_range 5 --offset_step 2 --sym C1 ...
```
See `08_refine3d.md` for refine flags; the relevant outputs for cryoDRGN are `run_data.star`, `run_class001.mrc` (size reference), and the two `run_half?_class001_unfil.mrc`.

> Symmetry: if the consensus was refined with point-group symmetry (e.g. C2/D2), cryoDRGN sees only the asymmetric poses RELION wrote. Continuous-heterogeneity analysis of a symmetric assembly with symmetry-expansion is a known subtlety — defer to **cryo-flex-knowledge**. The fixture is `--sym C1`, so this does not apply here.

---

## 2. Step 1 — get a small box (downsample / re-extract), keeping order identical

cryoDRGN trains in real time on a GPU; box size dominates cost. The fixture trained at **box 110** (downsampled 2x from the consensus box 220). Two equivalent routes; **pick one and do not reorder particles afterward**.

### Route A (recommended here): `cryodrgn downsample`
Operates directly on the consensus stack/STAR and preserves row order by construction.
```bash
# grounded: cryodrgn downsample -h (cryoDRGN 3.4.2)
<CRYODRGN_BIN> downsample \
    Refine3D/job075/run_data.star \
    -D 110 -o particles_110.mrcs \
    --datadir <RELION_PROJECT_FIXTURE>
```
- `-D` is the **new box size in pixels and must be even** (110 is even). `-D` is the *box*, not a radius.
- `--datadir` is the path prefix used to resolve the relative `_rlnImageName` paths inside the STAR (needed when the STAR lives elsewhere than the particle `.mrcs`).
- For very large stacks, `--chunk N` writes `particles.110.0.mrcs, particles.110.1.mrcs, …` plus an indexing `.txt`; `-b` sets the read batch size. The fixture stack (`particles_110.mrcs`, 307172 images of 110x110) is a single file.

### Route B: RELION re-extraction at a smaller box
Use `relion_preprocess` with `--reextract_data_star` (re-extract from micrographs using the consensus `_data.star`) — this regenerates a smaller stack *and* writes a matching `_data.star` you then parse:
```bash
# grounded: relion_preprocess --help
relion_preprocess --extract \
    --reextract_data_star Refine3D/job075/run_data.star \
    --i CtfRefine/job074/micrographs_ctf.star \
    --part_dir Extract/job_rextr110/ \
    --part_star Extract/job_rextr110/particles_110.star \
    --extract_size 220 --scale 110 --norm --bg_radius -1
```
Here `--extract_size` is the extraction box at the **original** pixel size and `--scale` is the rescaled output box (220 -> 110 = 2x bin). `--reextract_data_star` is documented as "A _data.star file from a refinement to re-extract, e.g. with different binning or re-centered." This produces a fresh `_data.star` whose order matches the new stack. (Plain image-stack rescaling with `relion_image_handler --new_box 110 --rescale_angpix 2.12` also works but does **not** emit a usable per-particle STAR, so prefer `--reextract_data_star` or Route A.)

> **Pixel-size bookkeeping (critical).** Box 220 at 1.06 A binned 2x -> box 110 at **2.12 A/px** (`1.06 * 220 / 110 = 2.12`). That downsampled 2.12 A is the value cryoDRGN needs as `--Apix`, **not** the consensus 1.06 A and **not** the super-res 0.53 A. See `12_conventions_symmetry.md` for the full pixel-size / box / Nyquist accounting. The cryoDRGN-written `particles_110.mrcs` header reports `angpix = 1` (placeholder) — do **not** read the real pixel size from the `.mrcs` header; carry it from the RELION STAR.

---

## 3. Step 2 — convert poses and CTF to `.pkl`

Both come from the **same** `_data.star` and must declare the **downsampled** box `-D` and **downsampled** `--Apix`. Use `run_data.star` from the consensus (Route A) or the re-extracted `_data.star` (Route B).

### Poses
```bash
# grounded: cryodrgn parse_pose_star -h (3.4.2)
<CRYODRGN_BIN> parse_pose_star \
    Refine3D/job075/run_data.star \
    -D 110 --Apix 2.12 -o pose.pkl
```
- `-D` = box size (110), `--Apix` = downsampled pixel size (2.12). cryoDRGN needs `--Apix` because RELION 3.1+ writes origin offsets in **Angstroms** (`rlnOriginXAngst/YAngst`), and they must be converted back to pixels at the *new* box; `parse_pose_star`'s own help says `--Apix` "override if translations are specified in Angstroms." Wrong Apix -> shifted/blurred reconstructions.

### CTF
```bash
# grounded: cryodrgn parse_ctf_star -h (3.4.2)
<CRYODRGN_BIN> parse_ctf_star \
    Refine3D/job075/run_data.star \
    -D 110 --Apix 2.12 --kv 300 --cs 2.7 -w 0.1 -o ctf.pkl
```
- Values from `data_optics`: `--kv 300` (voltage), `--cs 2.7` (spherical aberration, mm), `-w 0.1` (amplitude contrast `_rlnAmplitudeContrast`). `--ps` is phase shift (deg) — omit if zero. `-o` is the output pkl.
- **Version flag drift (read carefully):** in **cryoDRGN 3.4.2** (the installed env) the voltage flag is **lowercase `--kv`**. Older cryoDRGN (1.x/2.x, the version the fixture was made with in 2022) used **`--kV`**. The fixture `run.log` was created by `<OLD_CRYODRGN_ENV>/bin/cryodrgn` (that env no longer resolves). If you copy an old command verbatim into the 3.4.2 binary, `--kV` will be rejected. Always confirm with `cryodrgn parse_ctf_star -h` in the env you are actually using.

Resulting fixture files sit next to the stack: `RL_rf075_box110/pose.pkl`, `RL_rf075_box110/ctf.pkl`, `RL_rf075_box110/particles_110.mrcs`.

---

## 4. Step 3 — `train_vae`

The fixture is `z10_n50` = zdim 10, 50 epochs. Exact command recorded in `RL_rf075_box110/z10_n50/run.log`:
```
cryodrgn train_vae particles_110.mrcs --ctf ctf.pkl --poses pose.pkl \
    --zdim 10 -n 50 -o z10_n50 --multigpu
```
Re-expressed for the installed 3.4.2 env:
```bash
<CRYODRGN_BIN> train_vae \
    particles_110.mrcs \
    --poses pose.pkl --ctf ctf.pkl \
    --zdim 10 -n 50 -o z10_n50 \
    --multigpu
```
- `--zdim 10` = latent dimensionality (10 is a standard exploratory choice; small zdim = smoother, more interpretable landscape, less risk of overfitting noise). `-n / --num-epochs` (default 20; fixture 50). `-o` = output dir. `--multigpu` parallelises across **all detected** GPUs.
- The fixture run loaded "307172 110x110 images" and finished 50 epochs in ~4 h on this box; per `run.log` it ran with `--multigpu` across the 2x RTX 2080 Ti. **GPU memory note:** these cards are 11 GB each — box 110 fits comfortably; a large box (e.g. 256+) or large `--enc-dim/--dec-dim` can OOM. Keep the box small; that is the whole point of step 1.
- Data sign: cryoDRGN 3.x inverts data by default (assumes white-on-black). The 3.4.2 flag to *disable* inversion is `--uninvert-data` (older versions exposed `--invert-data`; the fixture `run.log` shows `invert_data=True` was the default-on behaviour). If reconstructions come out inverted-contrast, this is the knob — but for a standard RELION stack the default is correct.
- Particle subsetting: filter with `--ind indices.pkl` (a pickle of integer row indices) rather than re-extracting; this keeps the stack/pose/ctf alignment intact.

Outputs in `z10_n50/`: `config.pkl`, per-epoch `weights.N.pkl` and `z.N.pkl` (N=0..49), `run.log`. Epoch numbering is **0-based** (`z.49.pkl` = the 50th/last epoch).

---

## 5. Step 4 — `analyze`

```bash
# grounded: cryodrgn analyze -h (3.4.2)
<CRYODRGN_BIN> analyze z10_n50 49
```
- Positional args are `workdir epoch`; `49` selects `z.49.pkl`/`weights.49.pkl` (the last epoch, 0-based). Output defaults to `z10_n50/analyze.49/`.
- `--Apix 2.12` writes the correct pixel size into the generated `.mrc` headers (default behaviour: infer from `ctf.pkl`, else 1). `--flip` flips handedness, `--invert` inverts volume contrast, `-d N` downsamples output volumes, `--pc` and `--ksample` set the number of PC traversals / k-means samples.

What the fixture's `analyze.49/` contains (real layout, confirmed):
- `umap.png`, `umap_hexbin.png`, `z_pca.png`, `z_pca_hexbin.png`, `umap.pkl` — latent embeddings/plots.
- `kmeans20/` — 20 representative volumes `vol_000.mrc … vol_019.mrc` plus `centers.txt` (the 20 cluster-center z vectors, each a 10-D row = zdim), `centers_ind.txt` (the particle row index nearest each center, e.g. `239260`), `z_values.txt` (20x10 z values), `labels.pkl`.
- `pc1/`, `pc2/` — volumes along principal-component traversals (`vol_000.mrc … vol_009.mrc`, `z_values.txt`).
- `cryoDRGN_viz.ipynb`, `cryoDRGN_filtering.ipynb` — Jupyter notebooks for interactive latent inspection and particle filtering.

For interactive particle selection from the latent space, cryoDRGN 3.x also provides the standalone `cryodrgn filter z10_n50 --epoch 49` command (writes `indices.pkl`), which you then feed back via `train_vae … --ind indices.pkl` or convert to a RELION subset. Interpreting the landscape, deciding zdim, and validating that motions are real (not overfit) belong to **cryo-flex-knowledge**.

---

## 6. Going back to RELION (round trip)

cryoDRGN volumes (`vol_*.mrc`) are at the **downsampled** box/Apix (here 110 / 2.12 A). To use a cryoDRGN-selected particle subset for a high-resolution RELION refinement:
1. Get the integer indices from cryoDRGN (`filter` -> `indices.pkl`, or the notebook).
2. Map those indices back to rows of the **original full-resolution** `_data.star` (order is preserved iff you never reordered — Route A/B both preserve it). cryoDRGN does not write a RELION STAR; you select rows yourself (e.g. with the **cryosparc** skill's STAR helpers or a small script; pyem `csparc2star.py` at `csparc2star.py` is for the cryoSPARC direction, see `16_interop_cryosparc.md`).
3. Re-refine the subset in RELION at full box. Continuous motion itself is **not** directly transferable into a single RELION map — RELION's native continuous/flexible answers are **multi-body** (`11_subtract_multibody.md`) and 5.0 **DynaMight** (`00_overview.md`, `20_troubleshooting.md`).

---

## 7. Common failures / red flags

| Symptom | Likely cause | Fix |
|---|---|---|
| Volumes blurred / off-center even at low res | wrong `--Apix` in `parse_pose_star` (offsets are in Angstroms; converted at wrong scale) | use the **downsampled** Apix (2.12 here), not 1.06 or 0.53 |
| Garbage / noise-dominated latent space | uncleaned or heterogeneous-by-composition input set | clean with 2D/3D Select first; cryoDRGN needs a consensus, not raw picks |
| `cryodrgn: error: unrecognized arguments: --kV` | copied an old (1.x) command into 3.4.2 | use lowercase `--kv`; always check `parse_ctf_star -h` in the active env |
| `train_vae` reconstructions inverted contrast | data-sign default mismatch | toggle `--uninvert-data` (3.x) |
| Wrong/duplicated particles in volumes | stack reordered between extraction and `.pkl` generation; pose/ctf no longer match the stack | regenerate `pose.pkl`/`ctf.pkl` from the **same** STAR that describes the **exact** stack; never sort/dedupe in between |
| `-D` rejected ("must be even") | odd downsample box | choose an even box (110 ok) |
| `cryodrgn: command not found` | env not on PATH | call the absolute binary `<CRYODRGN_BIN>` or `conda activate cryodrgn-3.3` |
| OOM during `train_vae` | box too large / nets too wide for 11 GB 2080 Ti | smaller `-D`, smaller `--enc-dim/--dec-dim`, drop `--multigpu` issues |
| Apix shown as `1` in the `.mrcs`/volume header | cryoDRGN placeholder, not an error | carry Apix from the RELION STAR; pass `--Apix` to `analyze` for correct `.mrc` headers |

> RELION-side failures that are unrelated but live in this fixture: `Polish/job040,041` (`relion_motion_refine_mpi`: "Parameter estimation is not supported in MPI mode"), `MultiBody/job087,089` (`relion_flex_analyse`: "A GPU-function failed to execute"). Neither touches the cryoDRGN path; see `21_error_lookup.md`.

---

## 8. Version notes (cryoDRGN side)

- The installed env reports **cryoDRGN 3.4.2** (`cryodrgn --version`); subcommands present include `downsample, parse_pose_star, parse_ctf_star, train_vae, analyze, filter, eval_vol, eval_images, backproject_voxel, graph_traversal, abinit_homo, abinit_het, view_config`.
- The **fixture** was produced in 2022 by an older cryoDRGN (env path `<OLD_CRYODRGN_ENV>/`, now removed). Flag spellings drifted between major versions (`--kV`->`--kv`, `--invert-data`->`--uninvert-data`). Treat the fixture `run.log` as the *intent*, and re-confirm flags against the binary you run.
- cryoDRGN 3.x added `abinit_het`/`abinit_homo` (ab-initio without consensus poses), tilt-series (`--ntilts`, `-d/--dose-per-tilt`, `-a/--angle-per-tilt`) for cryo-ET, and the non-interactive `filter`. The classic RELION->consensus->`train_vae` route documented here is unchanged in spirit.

---

## Cross-links

- `12_conventions_symmetry.md` — pixel size / box / Nyquist accounting (the 0.53 -> 1.06 -> 2.12 chain), Euler/offset conventions.
- `08_refine3d.md` — producing the consensus `run_data.star`.
- `04_preprocessing.md`, `05_picking_extraction.md` — `relion_preprocess` extraction/re-extraction details.
- `11_subtract_multibody.md` — RELION's native continuous/flexible answer (multi-body) for comparison.
- `16_interop_cryosparc.md` — the cryoSPARC<->RELION STAR bridge and `csparc2star.py` (pyem) for subset round-trips.
- `00_overview.md`, `20_troubleshooting.md` — RELION 5.0 DynaMight (RELION-native deep flexibility) and Blush.
- `21_error_lookup.md` — fixture failure strings.

Owning skills (defer execution / interpretation):
- **cryo-flex-knowledge** — continuous heterogeneity theory, cryoDRGN landscape interpretation, zdim choice, overfitting/flexibility validation. **Consult before claiming a motion is biologically real.**
- **cryosparc** — STAR/`.cs` conversion helpers for subset round-trips.
- **structural-strategy** — what-to-do-next decisions across tools.

---

## Sources

Read / executed for grounding (all absolute):
- Fixture tree: `<RELION_PROJECT_FIXTURE>/cryodrgn/` and `.../cryodrgn/RL_rf075_box110/` (`ctf.pkl`, `pose.pkl`, `particles_110.mrcs`, `z10_n50/`).
- `<RELION_PROJECT_FIXTURE>/cryodrgn/RL_rf075_box110/z10_n50/run.log` (executed `train_vae` command, 307172 images, box 110, `--multigpu`, namespace defaults).
- `<RELION_PROJECT_FIXTURE>/cryodrgn/RL_rf075_box110/z10_n50/analyze.49/` incl. `kmeans20/{centers.txt,centers_ind.txt,z_values.txt}`, `pc1/`, `pc2/`.
- `<RELION_PROJECT_FIXTURE>/Refine3D/job075/run_data.star` (`data_optics`: 0.53/1.06 A, 300 kV, Cs 2.7, Q0 0.1, ImageSize 220) and `note.txt` (consensus refine command); particle count 307172.
- `relion_image_handler --i particles_110.mrcs --stats` (box 110x110, header `angpix = 1`).
- Captured help: `<RELION_SKILL_BUILD_ROOT>/references/cli/relion5_cli_capture_20260604/help/relion_preprocess.txt`, `.../relion_image_handler.txt`.
- Live cryoDRGN 3.4.2 help (`<CRYODRGN_BIN>`): `--version`, `downsample -h`, `parse_pose_star -h`, `parse_ctf_star -h`, `train_vae -h`, `analyze -h`, `filter -h`, `view_config -h`.
- Arithmetic: `1.06 * 220 / 110 = 2.12` (verified).
