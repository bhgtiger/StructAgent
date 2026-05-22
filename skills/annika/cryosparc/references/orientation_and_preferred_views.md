# Reference — Orientation Diagnostics and preferred views

## Purpose

Use this page when a cryoSPARC refinement looks globally acceptable but the map is directionally weak, streaky, locally uninterpretable, or dominated by one/few particle views. The goal is to separate four related but different questions:

1. **What views did the particles take?** Read the viewing-direction distribution.
2. **What Fourier directions were actually sampled?** Read posterior precision / Fourier sampling.
3. **Where does the reconstructed signal remain strong or weak?** Read cFSC, cFAR, tFAR, and relative signal.
4. **What should we do next?** Choose upstream mitigation: better picking, altered curation, rebalancing, tilted data, or sample-prep changes.

Preferred orientation is not a postprocessing defect. Sharpening, masking, and local filtering can make the artifact easier or harder to see, but they cannot create missing views.

## Quick diagnosis

| Symptom | Strongest interpretation | First response |
|---|---|---|
| One/few regions dominate the viewing-direction plot | Particle poses are unevenly distributed | Confirm with Orientation Diagnostics before acting; a histogram alone is not proof of harmful anisotropy |
| cFAR below ~0.5 | Directional signal is anisotropic | Inspect cFSC / relative-signal plots; route upstream rather than sharpening harder |
| SCF\* below ~0.81 | Alignment-implied Fourier sampling is uneven | Treat as likely preferred-orientation / coverage problem, especially if cFAR is also low |
| Low cFAR, high SCF\* | Signal anisotropy without obviously bad pose sampling | Suspect junk, contaminants, bad classes, local disorder, or alignment failure in particular views |
| High cFAR, low SCF\* | Sampling metric flags bias but signal looks less affected | Inconclusive; inspect maps, classes, particle quality, and tFAR/relative signal in v5+ |
| Strong global FSC but directional map streaking | Global FSC is hiding weak directions | Run Orientation Diagnostics from refined volume + particles + mask |
| Rebalance improves isotropy but worsens map detail | Rebalancing threw away useful particles | Use rebalanced map as an aid for re-picking / templates, not necessarily final reconstruction |

## What each plot or metric means

### Viewing-direction distribution

The viewing-direction distribution is a particle-count histogram over orientation space. It answers: **where did the aligned particles point?** Every particle contributes according to its estimated viewing direction, plotted on an azimuth/elevation parameterization of the unit sphere.

Do not overinterpret it. It does not directly say which Fourier directions are well sampled, nor does it measure directional FSC. It is most useful as an early warning that one view dominates, or that a class/refinement has collapsed into a narrow pose family.

### Posterior precision and Fourier sampling

Posterior precision and Fourier sampling are closer to the Fourier-slice geometry. A particle viewed along direction **v** contributes Fourier information in the plane orthogonal to **v**. Therefore, a dense region in the viewing-direction plot maps to sampling in an orthogonal set of Fourier directions, not the same apparent direction on the sphere.

This distinction is the common source of wrong advice: a weak conical-FSC direction does **not** automatically mean “collect more particles viewed from that exact direction.” Use the diagnostic plots together.

### cFSC and cFAR

Conical FSC evaluates FSC curves over many cone axes in Fourier space. CryoSPARC summarizes the variation using **cFAR**: the ratio between the weakest and strongest weighted area under conical FSC curves. Higher is better. The cryoSPARC Orientation Diagnostics page gives **cFAR < ~0.5** as a practical threshold indicating preferred orientation / anisotropy.

cFAR depends on both the particle alignments and the signal actually present in the particle images. That makes it often more diagnostically useful than a pose histogram alone: junk particles, bad classes, or view-dependent alignment failure can lower signal in some directions even when the nominal pose distribution is not obviously catastrophic.

### Relative signal and tFAR

From v4.5, Orientation Diagnostics reports **Relative Signal**, a viewing-direction-oriented measure derived from toroidal FSCs. Low relative-signal regions identify views whose absence or weakness is harming the map.

From v5.0, CryoSPARC also reports **tFAR**, a toroidal analog of cFAR. This matters for small membrane proteins and unimodal/bimodal viewing distributions where cFAR can look pathologically low even when the map remains usable. In v5+, read cFAR and tFAR together rather than treating cFAR as the only scalar verdict.

### SCF\*

**SCF\*** is the Sampling Compensation Factor. It describes geometric sampling implied by particle viewing directions and does **not** know whether a particle is true signal or junk. CryoSPARC gives **SCF\* < ~0.81** as a practical anisotropy threshold.

Use it as a sampling companion to cFAR:

| cFAR | SCF\* | Practical read |
|---|---|---|
| High | High | No strong orientation-bias signal |
| Low | Low | Preferred orientation and/or junk likely harm the reconstruction |
| Low | High | Signal-quality problem may dominate over geometry: junk, bad particles, flexible regions, or view-dependent alignment |
| High | Low | Sampling looks uneven but may not be limiting the current map; inspect tFAR/relative signal and map quality |

## Recommended workflow

### 1. Start from a real refinement, not raw particles

Run Orientation Diagnostics after a 3D refinement that has plausible poses: Homogeneous Refinement, Non-Uniform Refinement, local refinement where appropriate, or a comparable branch. If the upstream 3D alignment is wrong, the orientation diagnostics describe the wrong solution.

Inputs to prefer:

- refined volume / volume group from the refinement;
- particles with 3D poses if SCF\*, Fourier sampling, scale-factor, and per-particle plots are needed;
- the same symmetry as the upstream refinement;
- the same mask context used for FSC interpretation, unless deliberately testing a custom mask.

CryoSPARC notes that the cFSC plot produced during the final iteration of refinements uses the auto-tightened FSC mask. Orientation Diagnostics will automatically use that mask when connected from a refined volume group or via the “Build Orientation Diagnostics” quick action. A custom mask can change the results, so record it explicitly.

### 2. Read the scalar metrics first, then the plots

Use cFAR / tFAR / SCF\* as triage, not as the full interpretation. Then inspect:

- cFSC summary and all cFSC curves: how broad is the spread of directional FSCs?
- relative-signal map: where are weak views concentrated?
- viewing-direction distribution: are particles genuinely overrepresented in a narrow region?
- Fourier sampling / posterior precision: is Fourier coverage geometrically sparse?
- scale factor vs viewing direction, if generated: are certain views systematically lower quality?

### 3. Decide whether this is harmful

Not every uneven viewing-direction plot is an actionable problem. Treat it as harmful when one or more of these are true:

- directional FSC spread is large enough to affect model building;
- map has visible streaking, elongation, or direction-dependent blur;
- local resolution is systematically poor in features that require the missing views;
- global FSC is good but the map is hard to interpret in one direction;
- different classes or processing branches repeatedly lose the same structural direction.

If the map is interpretable and tFAR/relative-signal are acceptable, document the bias and avoid over-optimizing it.

## Mitigation branches

### A. Fix picking bias before extraction or 2D curation

Preferred orientation often starts before 3D refinement: the picker may preferentially find high-contrast views. In the HA case study, top views are obvious and score well, while side views are faint and score inconsistently. Strict NCC/power thresholds can therefore enrich the already-dominant view.

Practical responses:

- lower or widen pick thresholds when rare views are faint but plausible;
- use non-standard blob diameters or alternate templates to avoid encoding one view;
- build templates from diverse 2D classes or projected volumes, not from one dominant class;
- inspect micrographs manually for rare side/oblique views before declaring them absent;
- defer aggressive cleanup if it preferentially removes weak rare views.

### B. Adjust 2D classification strategy

2D classification can amplify preferred-view problems. If the dominant view occupies most classes, rare views may be forced into poor averages or discarded.

Practical responses:

- use a circular/soft mask on class averages when multiple dominant-view particles fit in one box;
- request enough classes that rare views have room to separate;
- do not select only the prettiest dominant-view classes if side/oblique classes are noisier but real;
- consider skipping or minimizing 2D classification when it repeatedly destroys rare views, as in the HA preferred-orientation workflow.

### C. Rebalance orientations after an initial 3D refinement

The **Rebalance Orientations** job removes particles from overrepresented viewing-direction bins and emits both rebalanced and excluded particle sets. It requires particles with 3D pose estimates from an upstream 3D refinement.

Key parameters:

- **Number of orientation bins** — default is usually sufficient; increase if the bias is narrow and localized.
- **Rebalance percentile** — bins above this percentile are trimmed down to the threshold bin population. This percentile is over bins, not particles; it does not mean “remove exactly 20% of particles.”
- **Intra-bin exclusion criterion** — random, picking NCC score, 3D alignment error, per-particle scale, or 2D alignment error. Quality-based criteria can help, but alignment-derived values may be unreliable if the anisotropic map itself is already poor.

Use the rebalanced output carefully. Removing overrepresented views can make a map more isotropic while reducing total signal. A useful pattern is:

1. run Rebalance Orientations;
2. refine the rebalanced particles;
3. use the more isotropic map to create better templates or guide repicking;
4. recover rare views from the original micrographs rather than treating the particle-thinned map as automatically final.

Rebalance Orientations is idempotent for the same parameters: running it twice in a row should not keep removing particles.

### D. Add tilted data or change data collection

If rare views are genuinely absent from the grid, software can only partially mitigate the problem. Tilted data changes the orientation distribution at collection time. The HA tutorial/case study uses tilted EMPIAR-10097 as the “good coverage” reference and untilted EMPIAR-10096 as the biased example.

Use this branch when:

- cFAR/SCF\*/relative-signal remain poor after careful picking and curation;
- rare views cannot be found visually in micrographs;
- rebalancing only throws away data without recovering interpretable directions;
- the final scientific question depends on density in the missing direction.

### E. Accept and report the limitation

If the sample has unavoidable preferred orientation and the map is still usable for the question at hand, do not hide the limitation. Report directional-resolution diagnostics, use conservative filtering, avoid overclaiming local features in weak directions, and keep model interpretation tied to local density quality rather than the best global FSC number.

## Version caveats

- **v4.4** introduced Orientation Diagnostics with cFAR and SCF\*, replacing the need to use the legacy 3DFSC wrapper as the main workflow.
- **v4.5** added Relative Signal and made refinement jobs emit cFSC summary plots at every iteration, so anisotropy can be monitored during refinement rather than only after the fact.
- **v5.0** added tFAR and all-toroidal-FSC plotting, plus raw cFSC curves written to `csfsc.csv` in the job directory. v5.0 also separates refinement/FSC masks more explicitly, which helps diagnose when anisotropy conclusions depend on mask choice.

## Agent checklist

When advising on preferred orientation:

1. Ask for or locate the Orientation Diagnostics job output if available.
2. Record CryoSPARC version, refinement type, symmetry, mask choice, and whether particles were connected.
3. Read cFAR, tFAR if available, SCF\*, and relative-signal plots together.
4. Compare against viewing-direction and posterior-precision/Fourier-sampling plots.
5. Check whether the suspected missing views were already filtered out during picking or 2D selection.
6. Prefer upstream mitigation over postprocessing: repick, diversify templates, alter 2D strategy, rebalance, collect tilt, or change sample prep.
7. Warn if the user is trying to fix anisotropy with sharpening, local filtering, or a tighter mask.

## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

- `docs/per_page/processing-data__all-job-types-in-cryosparc__utilities__job-orientation-diagnostics.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-orientation-diagnostics.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__case-study-picking-induced-orientation-bias-in-ha-trimer-empiar-10096-and-10097.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__particle-curation__job-rebalance-orientations.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__tutorial-common-cryosparc-plots.md`
- `04_picking.md`
- `05_extraction_2d.md`
- `07_refinement.md`
- `10_postprocessing.md`
- `version_caveats.md`
