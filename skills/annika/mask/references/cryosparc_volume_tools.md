# CryoSPARC Handoff — Import & Volume Tools

Checked 2026-09-07 against [Volume Tools](https://guide.cryosparc.com/processing-data/all-job-types-in-cryosparc/utilities/job-volume-tools) and the [Mask Creation tutorial](https://guide.cryosparc.com/processing-data/tutorials-and-case-studies/mask-selection-and-generation-in-ucsf-chimera). Documentation verification does not establish the installed CryoSPARC version or run schema.

## Import and finalization

Create an unsoftened base explicitly with `--binarize --dilation 0 --soft 0`; omitting `--soft` does not disable Gaussian smoothing. Import that MRC with Import 3D Volumes as a map, then connect it to Volume Tools. A fully finished mask may be imported as a mask. Preserve the target map’s box, voxel size, and coordinate frame.

| Current Volume Tools parameter | Starting choice | Validation |
|---|---|---|
| Type of input volume | `volume` for the connected base | Only the selected input slot is processed |
| Type of output volume | `mask` | Check the output type before downstream connection |
| Threshold | `0.5` for a binary base | For nonbinary molmap output, inspect contour/topology; no universal threshold |
| Dilation radius (pix) | A few pixels; historical trials used 3–6 | Spherical dilation radius in final output pixels |
| Soft padding width (pix) | At least `ceil(5 × GSFSC_resolution / final_apix)` as the Guide starting recommendation | Cosine-edge width; compare wider settings if FSC/coverage requires it |
| Output box / sampling | Preserve target grid | Check output dimensions, origin, and voxel size |

The previous `Type of operation = threshold` and long dilation/padding labels are historical wording; consult the installed job schema before API automation. Operation order is **resample/filter/crop → threshold/dilate/pad → invert**. Inversion occurs last since v4.4. Starting in **v5**, lowpass filtering defaults to **Butterworth, order 8** (previously rectangular; order default 10). Make filter choice explicit when reproducing an older mask. To choose a contour after lowpass filtering, run a first filter-only Volume Tools job, inspect its output, then threshold in a second job.

## Where the mask plugs in

| Job | Mask role |
|---|---|
| Local Refinement | Region to retain and refine |
| Particle Subtraction | Region to subtract, normally the particle outside the local region |
| 3D Variability Analysis | Region included in variability analysis |
| 3D Classification | Optional solvent mask |
| Homogeneous / Non-uniform Refinement | Optional static mask; compare against the current dynamic-mask route |

A box-wide `1 - region` mask also includes solvent; use a particle-bounded complement when following the tutorial’s subtraction workflow. Finish each base with suitable padding, inspect the pair, and do not assume independently softened masks remain an exact algebraic complement.

## Checks before downstream work

Inspect mask and map together at mask contour 0.5. Confirm coverage, dimensions, voxel size/origin, and finite values within [0,1]. Downstream masks need soft edges; a hard base is only an intermediate. The tutorial notes an exception for **3D Flex Mesh generation**, which does not require a soft mask. Where the job reports both Tight and Corrected FSC, a large separation suggests masking artifacts: revisit dilation and padding. A similar pair of curves is useful evidence, not proof that the model or alignment is correct.
