# Reference — cryoSPARC Particle Set Operations

## Scope / how to use

Retrieval-first reference for manipulating particle stacks/particle metadata in cryoSPARC without losing track of identity, image data, poses, CTF, class assignments, and downstream validity.

Use this when the question is:
- “How do I combine/intersect/subtract two particle sets?”
- “Which output should I use after classification/selection?”
- “How do I remove duplicates after multiple pickers or symmetry expansion?”
- “How do I split particles by score/class probability/3DVA coordinate/orientation?”
- “When should I downsample, restack, re-extract, or low-level swap `blob`?”

Core rule: **particle-set operations usually preserve metadata from a specific input. Know which input donates `blob`, `ctf`, `location`, `alignments2D`, `alignments3D`, class probabilities, and passthroughs before using the output.**

Source note: original synthesis from public cryoSPARC guide/release notes/forum/tutorial materials and public `cryosparc-tools` documentation/API material; consult upstream documentation for authoritative details.

---

## Fast decision table

| Goal | Prefer | Why | Main caveat |
|---|---|---|---|
| Random/equal-size split of one stack | **Particle Sets Tool** `split` | Creates multiple particle batches plus optional remainder. | Does not curate; just partitions. |
| A ∩ B / A-B / B-A | **Particle Sets Tool** `intersect` | Computes intersection and set differences by `uid` or `path`. | `intersect` output metadata comes from A; `intersect_B` from B. |
| Combine picks from multiple pickers | Connect/merge then **Remove Duplicate Particles** | Removes near-coincident particle coordinates before 2D/3D. | Choose shift key/score field deliberately. |
| Filter by score, scale, defocus, class probability, ESS, 3DVA coordinate | **Subset Particles by Statistic** | Uses thresholds or GMM; exposes many particle metadata fields. | Difference modes inherit metadata from **Final Particles**. |
| Reduce severe preferred orientation | **Rebalance Orientations** after 3D poses | Directly rebalances viewing-direction bins. | Throws away particles; can degrade map if overused. |
| Diagnose/balance 2D view classes | **Rebalance 2D Classes** | Groups class averages into superclusters. | Mostly diagnostic; 3D orientation tools are better once poses exist. |
| Consolidate a heavily curated stack | **Restack Particles** | Writes fewer/larger particle files; improves cache/storage behavior. | Does not change results; run after curation, not before. |
| Make smaller images for fast classification | **Downsample Particles** or extraction Fourier crop | Changes `blob`/box/pixel size for speed. | Preserve full-size path for final refinement via re-extract or low-level `blob` swap. |
| Resolve symmetry-breaking local features | **Symmetry Expansion** → Local Refinement / 3DVA / 3D Classification | Duplicates poses by symmetry operator. | Do not run global refinements on expanded particles. |
| Use full-size images with downsampled poses | Low-level result swap of `blob` | Keeps poses/CTF/class metadata while changing particle image data. | Requires exact slot-level connection; verify box/pixel consistency. |

---

## Particle identity and metadata model

Particle stacks are not only image files. A useful particle set is a table of linked slots/results:

| Slot/result | Meaning | Typical source |
|---|---|---|
| `uid` | Internal particle identity used for joining/deduplication. | Generated/propagated by cryoSPARC. |
| `blob` | Actual particle image path/index, box size, pixel size. | Extract/Downsample/Restack/Import. |
| `location` | Particle center on source micrograph. | Picker / Inspect Picks / Import. |
| `pick_stats` | Picker scores such as NCC/power. | Blob/template/Topaz/filament picking. |
| `ctf` | Per-particle CTF metadata. | Patch CTF + extraction / CTF refinement. |
| `alignments2D` | 2D pose/class metadata. | 2D Classification / Select 2D / Reconstruct 2D. |
| `alignments3D` | 3D pose, shift, scale, half-set info. | Homogeneous/NU/Heterogeneous/Local refinement. |
| `alignments3D_multi` | Multi-class probabilities/ESS. | 3D Classification / Heterogeneous-style classification outputs. |
| `components_mode_x` | 3DVA component coordinate. | 3D Variability Analysis. |

`job.load_output('particles')` in cryosparc-tools combines created and passthrough metadata; direct `.cs` readers may miss passthroughs unless exported. Dataset fields use `<slot>/<field>` names, e.g. `blob/path`, `ctf/df1_A`, `alignments3D/error` (source: `ui_to_api_crosswalk.md`).

---

## Particle Sets Tool

### Split mode

Use when one input stack A should be divided into batches.

Inputs:
- `particles_A` only.

Parameters:
- `Action = split`.
- `Split num. batches`: number of split outputs.
- `Split batch size`: number of particles per batch; if unset, batches are equal-sized.
- `Split randomize`: randomize assignment to batches.

Outputs:
- `split_X`: one output per batch.
- `remainder`: particles left out when batch size/number do not consume all particles.

Use cases:
- pilot refinements on equal-size subsets;
- reproducibility tests across random batches;
- speed-limited parameter sweeps.

Guardrail: split mode does not improve particle quality; it just partitions A.

### Intersect mode

Use when comparing two particle stacks A and B.

Inputs:
- `particles_A` and `particles_B`.

Parameters:
- `Action = intersect`.
- `Field to Intersect`:
  - `uid`: match by cryoSPARC particle identity.
  - `path`: match by `blob/path` + `blob/idx` token; useful when UIDs diverged but image path/index still encode identity.

Outputs:
- `intersect`: A ∩ B, with common result groups/passthroughs copied from **A**.
- `intersect_B`: A ∩ B, with result groups/passthroughs copied from **B**.
- `A_minus_B`: particles in A but not B.
- `B_minus_A`: particles in B but not A.

Advisor rule: when the same physical particles exist in both sets but one set has the metadata you want, pick the intersection output whose donor set owns that metadata.

Examples:
- You want particles common to two 3D-classification replicates but want poses from replicate B → use `intersect_B`.
- You want particles in a consensus refinement minus all particles assigned to a ligand-bound class → A = consensus, B = ligand class, use `A_minus_B`.
- You want particles shared by four replicate loose-state classifications → iteratively intersect pairwise; document which replicate donates final metadata.

---

## Remove Duplicate Particles

Use when multiple rows likely refer to the same physical particle coordinate.

Inputs:
- `Particles` with `location` required.
- Optional `Micrographs` with `micrograph_blob` for plotting/coordinate context.
- Optional particle slots: `blob`, `pick_stats`, `alignments2D`, `alignments3D`.

Parameters:
- `Minimum separation distance (A)`: default 20 Å; larger for large particles or duplicate-prone multi-picker merges.
- `Micrograph pixel size (A)`: required if micrographs are not connected.
- `Shift key`:
  - `none`: use `location` only.
  - `alignments2D` / `alignments3D`: apply alignment shifts before deciding centers.
- `Score field`: decides which duplicate to keep; options include picker `ncc_score`, reference agreement `error`, scaled agreement `error_min`, or `none` for random.
- `Remove duplicates entirely`: reject all members of duplicate clusters rather than keeping one.

Common uses:
1. **Combine pickers** — template + blob/Topaz picks often overlap; deduplicate before 2D/3D to avoid inflated counts and overfitting.
2. **After 2D/3D alignment shifts** — use `Shift key` when alignment shifted centers significantly.
3. **Undo symmetry expansion** — set minimum separation `0`, shift key `none`, and optionally score field to select one copy per expanded coordinate.

Guardrails:
- If the stack already has 3D poses, using `alignments3D` shifts changes what “duplicate coordinate” means. Good for recentered refined particles; bad if you only want original picker coordinates.
- Random keep is acceptable only when duplicate members are equivalent for the downstream question.
- Removing duplicates entirely is conservative but can throw away rare true close particles in crowded fields.

---

## Subset Particles by Statistic

Use when particle quality/state is encoded in a numeric metadata field.

### Modes

| Mode | Inputs | Metadata donor | Use |
|---|---|---|---|
| Single statistic | `Particles` | same input | Split by one field such as scale, error, defocus, pick score, class probability, 3DVA component. |
| Difference statistic | `Initial Particles` + `Final Particles` | **Final Particles** | Split by absolute change in pose/shift/defocus between two stacks. |

Difference-mode rule: put the particle stack whose metadata you want downstream into **Final Particles**.

### Curation methods

| Method | Best for | Output behavior |
|---|---|---|
| Gaussian mixture model (GMM) | multimodal distributions such as per-particle scale | outputs component groups; optional minimum probability drops uncertain assignments. |
| Manual thresholds | known cutoffs, class probabilities, ESS, defocus, coordinate windows | outputs threshold-separated groups ordered low→high. |

### High-value statistics

| Statistic | Dataset field(s) / meaning | Use |
|---|---|---|
| Per-particle scale optimal | `alignments3D/alpha_min` | GMM split to separate possible junk/thick-ice populations; v5 distinguishes optimal vs used. |
| Per-particle scale used | `alignments3D/alpha` | threshold-style filtering after refinement. |
| Picking NCC | `pick_stats/ncc_score` | remove weak template/blob matches. |
| Picking power | `pick_stats/power` | remove low/high contrast outliers. |
| Average defocus | average `ctf/df1_A`, `ctf/df2_A` | split by defocus range or local CTF behavior. |
| 2D/3D alignment error | `alignments2D/error`, `alignments3D/error` | remove poor image-reference matches; prefer 3D error when available. |
| 2D/3D shift | vector length × pixel size | detect particles that moved too far during alignment. |
| Class probability 2D/3D | `alignments2D/class_posterior`, selected `alignments3D_multi/class_posterior` | keep confident class members; v4.7+ replacement for Class Probability Filter. |
| Class ESS 2D/3D | `alignments2D/class_ess`, `alignments3D_multi/class_ess` | remove uncertain class assignments; lower ESS = more confident. |
| Total motion | path from `motion/path` | remove high-motion particles. |
| X/Y location fraction | `location/center_x_frac`, `location/center_y_frac` | spatial windowing or edge-effect tests. |
| 3DVA component X | `components_mode_x/value` | split continuous-heterogeneity coordinates. |
| Particle half-set split | `alignments3D/split` | v5: split particles by half-set, usually threshold at 0.5. |
| Absolute pose/shift/defocus difference | computed between initial/final stacks | detect unstable poses or changes after refinement/CTF refinement. |

### Class probability rules

For `Class probability - 3D`:
- `Class indices` are zero-based.
- `sum` mode is for multiple good classes representing the same target/state family; particles split between those classes can still be good.
- `max` mode is for multiple good classes representing distinct targets/states; a particle split across them is ambiguous.

Do not confuse class probability filtering with selecting a class output. Class outputs already assign particles to classes; probability filtering asks how confident those assignments are.

---

## Rebalance operations

### Rebalance 2D Classes

Use after 2D Classification to group class averages into superclusters and optionally balance particle counts among those superclusters.

Inputs:
- Particles and 2D class averages from the same 2D Classification job.

Parameters:
- `Rebalance factor`: 0 means no discard; 1 makes superclasses equal-sized; high values discard many particles.
- `Number of superclasses/templates`: should approximate unique views; inspect affinity matrix.
- `Override maximum superclass size`: explicit cap alternative to rebalance factor.

Best use:
- diagnosing view distribution after 2D;
- rare severe orientation-bias mitigation before ab initio.

Caution: once 3D poses exist, Orientation Diagnostics/Rebalance Orientations are more direct.

### Rebalance Orientations

Use after a 3D refinement when particles have 3D poses and viewing-direction bias is harming reconstruction.

Inputs:
- Particles with 3D pose estimates from Homogeneous/NU/etc.

Parameters:
- `Number of orientation bins`: more bins can target narrow over-represented views.
- `Rebalance percentile`: bins above percentile are reduced to the percentile bin count.
- `Intra-bin exclusion criterion`: random, `pick_stats/ncc_score`, `alignments3D/error`, `alignments3D/alpha`, `alignments2D/error`.

Outputs:
- `rebalanced particles`.
- `excluded particles`.
- before/after viewing-direction plots.

Cautions:
- It is idempotent with same parameters; a second identical run should do nothing.
- Particle loss may degrade overall map quality even if anisotropy improves.
- If underrepresented views are absent from micrographs, rebalancing cannot create them; use it as a diagnostic or to create better templates for re-picking.

---

## Downsample, restack, re-extract, low-level blob swap

| Operation | Changes image data? | Changes metadata? | Use when |
|---|---:|---:|---|
| Downsample Particles | yes, new `blob` at smaller/cropped/padded box | mostly preserves poses/CTF; optional recentering uses shifts | Need smaller/faster stack after extraction. |
| Restack Particles | yes, rewrites files/consolidates `blob` paths | should not change results | Heavy curation left many unused particles in source `.mrc` files. |
| Re-extract from Micrographs | yes, new `blob`, refreshed location/CTF context | can update centers/CTF from upstream | Need full-size/high-quality final stack or changed pick locations. |
| Low-level `blob` swap | changes only selected slot connection | preserves other chosen slots from another branch | Need full-size images with downsampled/refined poses. |

### Downsample Particles

Key parameters:
- `Crop / pad to box size (pix)`: real-space crop/pad before downsampling.
- `Desired approx. pixel size (A)` **or** `Fourier crop to box size (pix)`: choose one, not both.
- `Lowpass resolution (A)`.
- `Recenter using aligned shifts`: uses `alignments3D` if present, otherwise `alignments2D`.
- `Save results in 16-bit floating point` (v4.4+).

Use for fast 2D/3D classification, 3DVA, or heterogeneity exploration. For final high-resolution refinement, return to full-size images by re-extracting or low-level swapping the `blob` slot.

### Restack Particles

Restack consolidates particles into fewer/larger files and removes unused particle images from the new stack. It can improve caching/file-system behavior and save space after curation. It should not change downstream results.

Use after:
- 2D selection;
- 3D class cleanup;
- subset-by-statistic filtering;
- duplicate removal;
- before long repeated 3DVA/refinement runs on a stable curated set.

Do not restack too early if you may discard most particles later.

### Low-level `blob` swap

Classic pattern:
1. Extract two outputs: full-size `Particles` and small Fourier-cropped `Particles small`.
2. Run fast 2D/ab initio/refinement on small particles.
3. Build final refinement/local refinement using poses/CTF/class metadata from the small/refined branch.
4. Replace only the `blob` result with the full-size stack via low-level result connection.

Guardrails:
- Ensure the particles correspond one-to-one; `uid`/path/index consistency matters.
- Keep pixel/box/origin consistency explicit.
- Do not swap unrelated `ctf`, `location`, or `alignments3D` slots accidentally.

---

## Symmetry Expansion

Use to duplicate particle poses by point-group or helical symmetry so symmetry-related subunits can be treated as independent observations.

Inputs:
- Particles with `alignments3D` from a prior global refinement.
- Volume/particles should be aligned to conventional symmetry axes; enforce symmetry upstream or use Volume Alignment Tools.

Parameters:
- `Symmetry group`: e.g. `C4`, `D7`, `T`, `O`, `I`.
- Helical twist/rise/order for helical expansion; source particles should come from helical refinement.
- `Split output by symmetry operator`: outputs one stack per operator.

Outputs:
- Expanded particle stack size = input count × symmetry order.

Allowed next steps:
- Local Refinement with C1/asymmetric ROI mask.
- 3D Variability Analysis.
- 3D Classification / Flexible Refinement when the question is symmetry-breaking heterogeneity.
- Homogeneous Reconstruction Only with C1 as a sanity check that expansion succeeded.

Forbidden/unsafe next steps:
- Do **not** run Ab Initio, Homogeneous, Heterogeneous, Non-Uniform, or Helical refinements with global pose searches on expanded particles; duplication mis-estimates FSC/statistics.
- Generally do not enforce symmetry again downstream; the stack is already expanded.

Undo pattern:
- Run Remove Duplicate Particles on expanded/subselected stack with minimum separation `0`, shift key `none`, and appropriate score field/random keep to select one copy per original coordinate.

---

## Common recipes

### A. Two pickers → one clean stack

1. Run both pickers on same micrographs.
2. Inspect/threshold each picker output.
3. Extract or combine particle picks as appropriate.
4. Run Remove Duplicate Particles.
   - Minimum separation ≈ particle diameter fraction appropriate for target.
   - Score field = picker score or random if equivalent.
5. Extract/2D classify deduplicated set.

Why: duplicate near-coincident picks inflate class counts and can bias FSC/overfitting.

### B. Keep only particles reproducible across replicate classifications

1. Run replicate 3D Classification / heterogeneous branches.
2. Select good class particles from each replicate.
3. Use Particle Sets Tool `intersect` pairwise.
4. Choose `intersect` vs `intersect_B` based on which branch's poses/metadata you want.
5. Refine the consensus intersection and compare against union/less strict sets.

Tradeoff: intersection is cleaner but smaller; union is larger but may mix states.

### C. Remove one known state from a consensus stack

1. A = full/refined particle stack.
2. B = selected state/class to remove.
3. Particle Sets Tool `intersect`, field `uid` when possible.
4. Use `A_minus_B` for follow-up classification/refinement.

Use when a strong class masks weaker states in the remaining population.

### D. Filter uncertain class assignments

1. After 2D/3D classification, use Subset Particles by Statistic.
2. `Subset by = Class probability - 2D` or `Class probability - 3D`.
3. Use manual thresholds; set class indices for 3D.
4. Use `sum` for related good classes; `max` for distinct classes.
5. Refine kept and rejected outputs separately as a sanity check.

### E. Split continuous heterogeneity coordinate

1. Run 3DVA.
2. Use Subset Particles by Statistic on `3DVA component X`, or use 3DVA Display intermediates if evenly-spaced coordinate bins are enough.
3. Refine/reconstruct bins only if particle counts remain sufficient.

### F. ROI/local-refinement stack from symmetry-expanded particles

1. Refine globally with correct symmetry and aligned axes.
2. Symmetry Expansion.
3. Focused C1 Local Refinement or 3DVA/3D Classification on expanded particles.
4. If returning to symmetry-enforced refinement after selecting a subset, undo expansion with Remove Duplicate Particles.

### G. Curate then restack for long runs

1. 2D/3D select, duplicate-remove, subset-by-statistic.
2. Restack final curated particles with float16 if appropriate.
3. Clear old intermediate particle-heavy jobs only after verifying downstream output and project backup policy.

---

## Automation notes

With cryosparc-tools:
- Discover job type keys and parameter names from the live job spec (`print_job_types`, `print_param_spec`, `full_spec.params`), not display labels.
- Use `load_output('particles')` to inspect slots/fields before deciding on `uid` vs `path` matching.
- Check available output group names (`print_output_spec`) before connecting `split_X`, `A_minus_B`, etc.
- For low-level swaps, use result-level connection methods (`connect_result`) only after confirming source and destination slot names.
- For custom external metadata operations, prefer External Jobs / Import Result Group over editing `.cs` files in place.

Minimal safety assertions before queueing an automated particle operation:

```text
assert input particle count > 0
assert required slots present: location/blob/ctf/alignments2D/alignments3D as needed
assert chosen set-operation field exists (`uid` or `blob/path` + `blob/idx`)
assert output donor metadata matches downstream goal
assert particle count after operation is plausible
assert final status == completed
```

---

## Common failure patterns

| Symptom | Likely cause | Fix |
|---|---|---|
| Intersection unexpectedly empty | A and B have diverged UIDs or image paths; wrong field to intersect. | Try `path` if `uid` mismatch is expected; verify `blob/path` + `blob/idx`. |
| Intersection has right particles but wrong poses | Used `intersect` when desired metadata was in B, or vice versa. | Use `intersect_B` or swap input order. |
| 2D/3D counts look inflated | Duplicate picks from multiple pickers or symmetry expansion treated as independent. | Remove Duplicate Particles before downstream classification/refinement. |
| Duplicate removal discards good neighboring particles | Minimum separation too large, or shift key moved centers. | Lower separation; use `Shift key = none` if original coordinates matter. |
| Subset-by-statistic removes all good particles | Statistic direction misread; threshold/GMM component chosen backward. | Inspect histogram; refine each output group as validation. |
| Per-particle scale filtering tracks view direction | Anisotropic map makes scale unreliable. | Check viewing-direction plots; avoid scale-only cleanup. |
| 3DVA component split uses old component values | Components are updated, not removed; later 3DVA with fewer components leaves older higher-index values. | Confirm component number source before splitting. |
| Local refinement on expanded particles overclaims resolution | Expanded copies treated as independent / wrong downstream job. | Use C1 local/focused jobs only; validate with independent subsets. |
| Restack output differs scientifically | Should not happen; likely wrong input or downstream compared against different metadata. | Compare slots/counts before/after; restack only stable curated set. |
| Low-level `blob` swap breaks refinement | Mismatched box/pixel/origin or wrong slot swapped. | Recheck `blob`, `ctf`, `alignments3D`, `location` slots and output versions. |

---

## Sources consulted

This reference is original synthesized workflow guidance prepared from public cryoSPARC guide pages, public release notes, public forum reports, public tutorials/webinars, relevant papers, and public `cryosparc-tools` documentation/API material. Raw upstream documents, transcripts, forum posts, screenshots, and datasets are not bundled here. For authoritative and current details, consult the official cryoSPARC documentation, release notes, discussion forum, and upstream project documentation.
