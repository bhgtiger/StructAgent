# Topic 20 — Masks

## Scope

Choosing, generating, and validating 3D masks for cryoSPARC jobs: refinement FSC, local refinement, particle subtraction, classification focus, 3DVA, postprocessing. Covers mask base creation in ChimeraX (segmentation, volume eraser, molmap) and conversion to final masks via Volume Tools. Mask design is empirical — expect iteration.

## Decision surface — what kind of mask do I need?

| Goal | Mask type | Notes |
|---|---|---|
| Standard homogeneous/NU refinement | Dynamic refinement + resolution masks (v5.0+) | Inspect; default is usually fine. |
| Local refinement of a subregion | Static, soft, generous mask around ROI | Prefer static per docs; avoid overfitting risk of dynamic here. |
| Particle subtraction | Static soft mask over region to **subtract**, not to keep | Pair with complementary kept-region mask if doing local refine next. |
| FSC / postprocess resolution | Generous, repeatable soft mask | Too tight → inflated GSFSC. |
| Classification focus / 3DVA / 3D Classification | Soft mask around varying region | Too tight forces noise classes. |
| 3DFlex mesh generation | Mask without soft edge OK (per tutorial footnote) | Do not generalize to other jobs. |

If an atomic model exists → prefer model + `molmap` mask base. Else → segmentation in ChimeraX, or volume eraser for simple cases.

## Core rules that prevent bad masks

- Same **box size, pixel size, and origin** as the target map. Verify before use.
- Soft cosine edge is required for nearly all cryoSPARC jobs. Hard masks cause Fourier ringing and alignment bias.
- Minimum soft padding heuristic: `5 × resolution(Å) / apix(Å)` voxels. More may be needed.
- Never build a final mask directly from raw high-frequency map noise — blur/lowpass first (`volume gaussian #1 sDev 2` is a reasonable start).
- No floating dust/noise islands. After dilation + soft padding they become latch points for alignment.
- Dilation and soft padding values are empirical — try a few. Inspect the result in a viewer.

## Mask base vs final mask

- **Mask base**: region proposal from the user. May be hard-edged or non-binarized. Must already be on the correct grid/box of the target map.
- **Final mask**: binarized → dilated → soft-padded. This is what cryoSPARC jobs consume.

Pipeline: build mask base (ChimeraX) → save `.mrc` → **Import 3D Volumes** → **Volume Tools** → final mask attached to job.

## Static / manual vs dynamic / automatic

- **Dynamic masks (v5.0+)** in refinements are robust and resolution-scaled. Two masks under the hood: a refinement mask (threshold default = max × 0.2) and a resolution/FSC mask (threshold fixed at 0.5). Near multiplier 2.0, far multiplier 5.0, soft edge = resolution × (far − near). Wide when map is poor, tightens as GSFSC improves.
- **Static masks**: required for any ROI you need to commit to (local refinement, subtraction, focused classification). Use static when shape cannot be inferred from current map alone.
- Always **inspect** both refinement and resolution masks. High-resolution phase-randomization in the FSC plot is a tell for too-tight/hard masks.

## How to make a mask base in ChimeraX

Three workflows. There is **no undo** in segmentation or eraser flows — save intermediate states.

### Segmentation (Segger / watershed)
- Safest for complex map-derived shapes.
- **Hide** regions rather than deleting them during selection, so you can iterate.
- Segger MRC outputs are often cropped (e.g. 96×94×129 from a 380³ map). Resample onto the original grid:
  ```
  volume resample #4 onGrid #1
  ```
- Save the resampled `.mrc`. For particle subtraction, build the complementary mask base in the same session.

### Volume Eraser
- Fast for cutting away large simple regions.
- Tends to leave dust and awkward boundaries — clean up before exporting.
- Make a copy of the volume before erasing if a complementary mask is needed.

### Model-based `molmap` (preferred when an atomic model exists)
- Easiest, scriptable, reproducible.
- Example:
  ```
  molmap #2/U 16 onGrid #1
  ```
  where `#2/U` is the model selection (chain/domain/residue range), `16` is the simulated resolution in Å, `#1` is the target map.
- **Always pass `onGrid`** or the result silently lands on the wrong grid.
- Use a realistic resolution (~12–20 Å, 16 Å is a sensible default). Docs warn against finer than 12 Å for mask purposes; never use 1 Å.

After any of the above: save `.mrc`, then go to cryoSPARC.

## Converting mask base to final mask in Volume Tools

1. **Import 3D Volumes** to bring the mask base into the project. Import as `map` if Volume Tools still needs to threshold/dilate/pad it; import as `mask` only if it is already a final soft mask.
2. **Volume Tools** operation order:
   1. Resampling / lowpass / cropping
   2. Thresholding / dilation / soft padding
   3. Inversion (if needed)
3. Match the input slot to the data type — mask vs volume — operations apply only to the selected slot.
4. Key parameters:
   - `Threshold` — binarizes the input.
   - `Dilation radius (pix)` — in final resampled pixels; `0` skips.
   - `Soft padding width (pix)` — cosine-padded edge; `0` skips. **Do not leave at 0** for downstream mask jobs.
5. For lowpass→threshold workflow: one Volume Tools job to lowpass only, inspect threshold in ChimeraX/viewer, then a second Volume Tools job to threshold/dilate/pad at the chosen level.

## Masks for local refinement and particle subtraction

### Local refinement
- Cover ROI **plus comfortable margin**, soft-edged, same grid/box, no detached islands.
- Practical local default (heuristic, not universal): dilate ~5–10 voxels, soft pad ~20 voxels. Tune.
- Generous masks are more stable for small ROIs. Tighten only when adjacent density moves independently — and then pair with small search range + Gaussian prior on shifts/rotations.
- Too-small ROI mask → noise, ring/shell artifacts, blips at the mask edge. Enlarge and/or add Gaussian prior.

### Particle subtraction
- Mask covers the region to **subtract**, not the region to keep.
- Requires gold-standard half-sets on the particles and a volume with both half maps.
- Mask must be soft-edged. Subtraction quality is bounded by input volume quality — locally refining the subvolume first usually improves the subtraction.
- Match windowing/scaling parameters to the **input refinement**, not job defaults — common silent failure mode.
- Sanity check: Homogeneous Reconstruction Only on the subtracted particles, then Local Refinement.
- If using complementary masks (subtract one half, refine the other), they must partition the density cleanly — gaps/overlaps cause problems.

## Masks for FSC / postprocessing / classification / 3DVA / 3DFlex

- **FSC / postprocess**: generous, repeatable soft mask. Too-tight masks inflate reported resolution. Symptom: large discrepancy between Tight, Corrected, and Spherical/Loose curves, or a dip in the Corrected curve.
- **Classification focus / 3D Classification / 3DVA**: soft mask around the varying region. Too tight forces overclassification onto noise.
- **3DFlex mesh generation**: per the tutorial footnote, a soft mask is not required. Do not generalize this — every other job still wants soft edges.

## Diagnostics and failure patterns

| Symptom | Likely cause | Fix |
|---|---|---|
| Tight FSC not following Corrected FSC | Mask too tight / too high-res | Loosen; lowpass before threshold; larger dilation. |
| GSFSC suspiciously high vs map appearance | Shared signal leaking through tight mask | Re-do mask with more dilation + soft padding. |
| Phase-randomization spike at high res | Hard or too-tight FSC mask | Add soft edge; loosen threshold. |
| Blips/shells near mask edge in local refine | ROI mask too small or hard | Enlarge ROI; add soft edge; consider Gaussian prior. |
| Floating density islands in final mask | Threshold too low or no cleanup | Raise threshold; segment + delete dust before export. |
| Mask "looks right" but job rejects / aligns wrong | Wrong grid/origin (missing `onGrid`) | Re-run `molmap … onGrid #target` or `volume resample … onGrid #target`. |
| Overclassification on noisy region | Focus mask too tight | Loosen; verify ROI actually varies. |

## Automation hooks

**With atomic model (preferred):**
1. Pick model selection (chain / domain / residue range).
2. ChimeraX: `molmap <sel> 16 onGrid <target_map>` — adjust to 12–20 Å as needed.
3. Save resulting `.mrc`.
4. cryoSPARC: Import 3D Volumes → Volume Tools (threshold + dilate + soft pad).
5. Verify box/apix/origin match target map.

For the local automation helper, the model path looks like:

```bash
"$CHIMERAX" --nogui --exit --script scripts/make_mask_from_model.py -- \
  --model model.cif \
  --selection "/A:120-340" \
  --target-map refined_map.mrc \
  --resolution 16 \
  --out mask_base.mrc
```

Treat `mask_base.mrc` as the proposal, not the final cryoSPARC mask, unless dilation and soft edge were explicitly applied and inspected.

**Without atomic model:**
- ChimeraX segmentation or eraser — GUI-heavy, scripting is limited.
- A crude automated path: `volume gaussian #1 sDev 2` → threshold via Volume Tools. Flag this as low-confidence; recommend manual segmentation cleanup if mask shape matters.

**Always verify** before attaching a mask to a job: same box, same pixel size, same origin as the target volume.

## Version notes

- **v4.0** — Local Refinement and Particle Subtraction warn if binary masks are used; treat that warning as meaningful, not cosmetic.
- **v4.4** — Volume Tools can invert masks without thresholding; dilation/padding specified in **pixels**; default soft padding 12 px.
- **v4.5** — Volume Tools reports centre of mass when input volume is a mask.
- **v5.0** — Default lowpass filter changed to **Butterworth order 8** (was rectangular order 10); dynamic refinement masks made robust and resolution-scaled.

## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

- `docs/per_page/processing-data__tutorials-and-case-studies__mask-selection-and-generation-in-ucsf-chimera.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-dynamic-masking-in-refinements-v5.0.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__utilities__job-volume-tools.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__local-refinement__job-new-local-refinement-beta.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__local-refinement__job-particle-subtraction-beta.md`
- `videos/notes/10_mask_creation_in_chimerax.notes.md`
- `videos/10_mask_creation_in_chimerax.transcript.md`
- `09_local_refinement.md`
- `reference/release_notes/markdown/v4.0.md`
- `reference/release_notes/markdown/v4.4.md`
- `reference/release_notes/markdown/v4.5.md`
- `reference/release_notes/markdown/v5.0.md`
