# Official automated-workflow examples

Verified against the linked official pages on **2026-09-07**. Read the relevant card; open the full guide for exact setup details. Workflow **v1/v2** are template revisions, separate from CryoSPARC software versions. The supplied materials support **CryoSPARC v4.7.1+**.

## Choose an example

| Situation | Starting example | Supporting reference |
|---|---|---|
| Repeated GPCR structures with an appropriate known reference | GPCR Workflow v1 | `09_local_refinement.md` |
| Small target, repeated datasets, substantial preferred orientation | CAK Workflow v2 | `orientation_and_preferred_views.md` |
| Import/apply a workflow or adapt it to a new target | Practical setup | `13_cryosparc_tools_api.md` |
| Unknown composition or unexpected species | Complex I card in `case_studies_and_tutorials.md` | `06_abinitio.md`, `08_classification_3d.md` |

## CAK: Workflow v2 and preferred orientation

The [CAK case study](https://guide.cryosparc.com/processing-data/automated-workflows/advanced-automated-data-processing-a-case-study-using-cak) develops its workflow using apo-CAK, EMPIAR-11800, then applies it across nine datasets. Use its strategy when a small target has a usable reference but pronounced angular bias.

Its sequence is preprocessing/denoising/junk detection → reference-derived template picking → automated pick curation → extraction → decoy heterogeneous refinement → NU refinement → orientation rebalancing → multiclass ab initio/heterogeneous refinement → automatic class selection → rebalancing and scale-based selection → NU/RBMC/final refinement. References and particle dimensions must be adapted to the target.

The study suggests raising the rebalance percentile to **80–90** when orientation bias is weak, retaining more particles. Treat this as a candidate setting; evaluate directional FSC, map features, and retained particle count. Preserve an unrebalanced comparison. Workflow v2 cannot supply missing experimental views.

For a new target, inspect picking, automated thresholding, rebalancing, and final extraction/Nyquist in small job groups. Save the successful graph as a reusable workflow after reviewing its results. These settings do not establish a universal optimum.

## GPCR: Workflow v1 for repeat targets

The [GPCR automation case study](https://guide.cryosparc.com/processing-data/automated-workflows/full-automated-data-processing-a-case-study-using-gpcrs) provides a known-reference route for active/inactive GPCR datasets. It reports matching or improving published resolution and map quality in **17 of 21** datasets; that is a benchmark outcome, not a guarantee for a new sample.

Adapt reference/junk volumes, the receptor mask, import metadata, beam-image-shift grouping, and both extraction jobs. Check the receptor and ligand region as well as global resolution. Use exploratory classification if additional species or states are the scientific question.

For its supplied reference, the guide's extraction example is **310.6 Å divided by the motion-corrected pixel size**, rounded to an even pixel count. That physical extent belongs to this example and should not be copied to unrelated targets.

## Practical setup and downloads

The [download page](https://guide.cryosparc.com/processing-data/automated-workflows/downloads-workflow-jsons-sample-volumes-and-masks) supplies:

- [Workflow v1 materials](https://structura-assets.s3.us-east-1.amazonaws.com/automated-workflows/Automated_workflow_materials_v1.zip): JSONs plus volumes/masks; separate entry points for raw movies and Live-preprocessed micrographs.
- [Workflow v2 materials](https://structura-assets.s3.us-east-1.amazonaws.com/automated-workflows/Automated_workflow_materials_v2.zip): JSON, CAK reference, and junk volumes.
- A separate download of resulting CAK maps/models for comparison.

Keep large assets outside the skill. When asked to use an example, retrieve the selected material, record its source/checksum, and inspect the JSON before applying it.

Follow the [practical workflow guide](https://guide.cryosparc.com/processing-data/automated-workflows/practical-tips-using-workflows-to-process-your-own-data):

1. Place volumes/masks on worker-visible storage. Browser uploads land in the selected project's `uploads` directory; shared references may live elsewhere.
2. Import the JSON through the Workflows sidebar. For `agpcr_workflow_live_exposures.json`, select the Live Exposure Export parent job before opening the workflow.
3. Review movie/gain paths, pixel size, voltage, Cs, dose, gain transforms, grouping, F-crop, reference paths, and extraction boxes. **Flagged parameters are reminders, not enforced requirements**; an unchanged flag can still be applied.
4. For initial inspection, leave **Queue on Apply** off. Applying still creates connected jobs. Queueing requires the project/workspace/lane and execution authorization specified in `../SKILL.md`; reuse authorization already provided.

## Runtime expectations

Use the [processing-times tables](https://guide.cryosparc.com/processing-data/automated-workflows/processing-times-from-automated-workflow-examples) with their hardware/software context. GPCR timings use v4.7 and a two-RTX-4090 workstation, with selected eight-GPU comparisons. CAK timings use v5.0 and an eight-A100 server; the reported average is approximately 21 hours. Dataset sizes, I/O, caching, and stage parallelism differ. Estimate on the user's setup before promising a completion time.
