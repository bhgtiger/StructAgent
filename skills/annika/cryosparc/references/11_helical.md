# Topic 11 — Helical Reconstruction (BETA)

## Scope
Advisor-mode page for cryoSPARC's helical reconstruction surface: how processing of filaments differs from standard single-particle analysis (SPA), how to route a project through the BETA helical jobs (Filament Tracer, Average Power Spectra, Symmetry Search Utility, Helical Refinement), how `cryoSPARC` parameterizes helical symmetry, and which failure modes are specific to helical assemblies. The page treats helical as a **specialized branch off the SPA workflow**, not as a separate pipeline — most upstream and downstream jobs (import, motion, CTF, 2D classification, postprocessing, RBMC, RELION interop) are the same, with documented exceptions.

What lives elsewhere — do not duplicate:
- Preprocessing mechanics (Patch Motion / Patch CTF / curation) — `03_preprocessing.md`.
- General picker strategy and Topaz / blob / template / deep picker mechanics — `04_picking.md`.
- Extraction box / Fourier crop / 2D parameters not specific to filaments — `05_extraction_2d.md`.
- Non-helical ab initio and refinement branch logic — `06_abinitio.md`, `07_refinement.md`.
- Mask design and validation — `20_masks.md`.
- FSC reading, sharpening, anisotropy reading — `10_postprocessing.md`.
- Point-group symmetry strategy, symmetry expansion, hand flipping — `19_symmetry.md`.
- Parameter cookbook by stage — `16_tuning_recipes.md`.
- Decision-tree routing — `18_decision_trees.md`.
- GPU / lane / VRAM box-size tradeoffs — `21_gpu_lane_queue.md`.
- RELION star-file round-tripping for filament metadata — `27_relion_interop.md`.
- Tomography — `12_tomography.md` (helical reconstruction is for filaments in single-particle frames, not for tomograms).

Version disclaimer: helical jobs are labeled **BETA** in the documentation as of the bundled v5.0 docs. Behavior, defaults, and even parameter names can change between releases. Verify against the local instance's job parameter list before scripting.

---

## 1. How helical workflows differ from SPA

Helical assemblies are continuous (or pseudo-continuous) polymers built from a repeating asymmetric unit related by a **rotation + translation** ("twist + rise") along a single axis. The downstream consequences for cryoSPARC processing:

| Aspect | SPA | Helical |
|---|---|---|
| Particle definition | One isolated molecule per pick | A **segment** of the filament — overlapping segments along the helical axis are normal and desirable |
| Symmetry parameterization | Point group (Cn / Dn / T / O / I) | Helical twist Δφ (°) + rise Δz (Å), optionally **stacked** on a point group (Cn or Dn) |
| Symmetry knownness | Usually known a priori or from biology | Often unknown — must be searched, sometimes ambiguous |
| Picking | Blob / template / Topaz on individual particles | **Filament Tracer** (or filament-aware use of other pickers) to walk the filament axis |
| In-plane alignment in 2D | Free | "Align filament classes vertically" used by default to expose tilt and segment polarity |
| Initial model | Random / SGD ab initio works in most cases | Ab initio frequently produces preferred-orientation traps; **asymmetric helical refinement** with scrambled azimuth is a common alternative |
| Risk of symmetry imposition | Wrong Cn produces obvious artifacts | Wrong twist/rise can refine to a *plausible-looking but wrong* high-resolution map; symmetry-validation discipline is mandatory |
| Hand ambiguity | Z-flip + Volume Tools / Reconstruction Only | Hand sign sits inside Δφ; the same map can be consistent with both hands until external evidence breaks the tie |
| Box / segment overlap | Avoid duplicate picks of the same particle | Adjacent segments are expected to share substantial particle content; **Number of times to apply helical symmetry** ties this to Δz |
| Register / seam ambiguity | Usually irrelevant | Seam-like register ambiguity and polarity/hand ambiguity can survive apparently good FSC; resolve with independent biology/model evidence, not FSC alone |

**Beta caveat.** Filament Tracer, Helical Refinement, and Symmetry Search Utility all carry the BETA label in the bundled docs. Average Power Spectra was added in v4.0 and is not labeled BETA, but its `.mrc`/`.cs` outputs are *not* registered as cryoSPARC outputs and only appear in the job directory. Plan exports accordingly.

---

## 2. Workflow map

A defensible default flow for a helical project, with the source-attested branch points:

```
Import Movies
   ↓
Patch Motion Correction (multi)
   ↓
Patch CTF Estimation (multi)
   ↓
Manually Curate Exposures             ← cut on CTF fit, motion, ice (see topics/03)
   ↓
─────────────── PICKING BRANCH ───────────────
   ┌── Manual Picker (small subset, ~150–200 picks across ≥10 micrographs, varied defocus)
   │        ↓
   │   2D Classification (few classes, e.g. 5; Force Max over poses/shifts ON; Align filament classes vertically ON by default)
   │        ↓
   │   Select 2D (clean filament views as templates)
   │        ↓
   │   Filament Tracer (template-based) — recommended for cylindrical filaments
   │
   ├── Filament Tracer (template-free) — set Min / Max filament diameter (Å)
   │
   ├── Template Picker — works on filaments but lacks filament-aware skeletonization/pruning
   │
   └── Topaz / Deep Picker — for non-cylindrical (e.g. amyloid) or low-contrast filaments
─────────────────────────────────────────────
   ↓
Inspect Particle Picks
   ↓
Extract from Micrographs                ← box ≥ ~1.5–2× longest dimension; FFT-friendly size
   ↓
2D Classification (full)
   ↓
Select 2D / Reference-Based Auto Select 2D
   ↓
─────────── INITIAL MODEL BRANCH ──────────────
   ┌── Ab-Initio Reconstruction
   │     - Cylindrical Window (v5.0+): "Volume window mode" → cylindrical mask
   │     - C1 unless biology supports more
   │     - High preferred-orientation risk
   │
   └── Asymmetric Helical Refinement
         (Helical Refinement with twist/rise left empty)
         - Initial density from tilt + scrambled azimuth
         - Tune Initial lowpass resolution, Number of images for initial density generation,
           GSFSC Split Resolution (12–15 Å for small filaments)
─────────────────────────────────────────────
   ↓
Average Power Spectra (optional) → external Fourier–Bessel tools (HELIXPLORER / PyHI / HI3D)
   ↓
Symmetry Search Utility (BETA)         ← on the asymmetric or low-symmetry volume
   ↓
Helical Refinement (BETA) with twist + rise enforced
   - Optional NU regularization (v4.4+: ~2× faster)
   - Optional local symmetry search
   - Optional point-group symmetry on top of helical
   - Optional "Limit shifts along the helical axis" (required for downstream Symmetry Expansion)
   ↓
Validation: GSFSC, Orientation Diagnostics, local resolution, asymmetric vs symmetric comparison
   ↓
(Optional) Symmetry Expansion → Local Refinement / 3D Classification (no global refinement after expansion)
   ↓
Postprocessing / Sharpen / DeepEMhancer / Export
```

The EMPIAR-10031 (MAVS) case study follows this flow with manual pick → 2D → templates → template-based Filament Tracer → 2D cleanup → ab initio / asymmetric refinement → symmetry search → symmetric Helical Refinement, and is the worked example to recommend when a user has not done helical before.

---

## 3. Helical symmetry in cryoSPARC: parameterization and conventions

cryoSPARC accepts two equivalent global parameter sets:

- **Rise / twist:** helical rise Δz (Å, strictly positive) and helical twist Δφ (°, sign carries handedness).
- **Pitch / subunits / hand:** helical pitch p (Å, positive), number-of-subunits-per-full-turn n (positive), and hand h ∈ {+1, −1} with h=+1 right-handed, h=−1 left-handed.

Conversion: Δφ = 360°·h / n, Δz = p / n. The Symmetry Search Utility can search in either "pitch mode" (over (n, p) with a chosen hand) or "rise mode" (over (Δφ, Δz)); the docs recommend pitch mode by default because it searches both hands, with the exception of helices whose asymmetric units are so large they do not really form a helical lattice — there pitch becomes uninterpretable and rise mode is preferred.

A helical assembly can additionally have a **point-group symmetry stacked on top** of helical symmetry. Helical Refinement supports cyclic (Cn) and dihedral (Dn) point groups; cyclic axes are assumed aligned with the helical axis (Z), and the Dn dyad is perpendicular. Other point groups (T, O, I) are not supported on top of helical.

**Known vs unknown symmetry branch logic:**

| State of knowledge | Recommended path |
|---|---|
| Twist + rise known from prior work / biology | Go straight to Helical Refinement with twist/rise filled in. Confirm by inspecting orientation distribution, GSFSC, and asymmetric-vs-symmetric comparison |
| Twist + rise unknown but reconstruction expected to be tractable | (a) Ab-initio or asymmetric Helical Refinement to get a starting volume; (b) Symmetry Search Utility on that volume; (c) take top candidates into a series of symmetric Helical Refinements; (d) accept the parameters that yield the most consistent FSC + Coulomb-density features |
| Twist + rise unknown and ab initio fails | Average Power Spectra → external Fourier–Bessel tool (HELIXPLORER / PyHI / HI3D) → candidate twist/rise → Helical Refinement |
| Hand ambiguity remains | Disambiguate with external evidence: model fit, tilt-pair validation, prior literature. Do not pick the hand based on FSC alone |

**Important practical convention:** Δz is always positive; Δφ carries the sign for hand. The Symmetry Search Utility's "rise mode" expects rise ranges as positive `x,y` pairs and twist ranges with sign preserved (e.g. `-30, -20` for left-handed); the lower endpoint must come first.

---

## 4. Filament Tracer (BETA): picking filaments

Filament Tracer is the cryoSPARC-native picker built for filaments. It runs a template- or blob-style cross-correlation, then post-processes via image skeletonization to **join picks into continuous contours**, prune bent filaments, and enforce a constant spacing of segments along each filament — conceptually similar to SPRING's helix tracing.

**Inputs:**
- Aligned, CTF-estimated micrographs.
- Optional templates. Results improve substantially with **multiple templates spanning diverse views along the helical axis**.
- If no templates: set **Minimum filament diameter (Å)** and **Maximum filament diameter (Å)** to enable template-free tracing.

**Key parameters (length units scale with filament diameter so defaults port across datasets):**

| Parameter | What it controls | Practical guidance |
|---|---|---|
| `Filament diameter (Å)` | Estimated filament diameter | Round to the nearest 5–10 Å if uncertain; tightness matters less than the separation distance |
| `Separation distance between segments (diameters)` | Spacing of picks along the filament, in diameters | Choose so the absolute distance is close to a **small integer multiple of the helical rise Δz**. For MAVS at 90 Å diameter, 0.25 was used (≈22.5 Å spacing) |
| `Minimum filament length to consider (diameters)` | Reject filaments shorter than this | Increase if many short false positives leak through |
| `Lowpass filter to apply (Å)` | Pre-filter the micrographs for tracing | Adjust if the default fails on small or large filaments |
| `Hysteresis thresholds` (low / high percentile, default 93 / 98) | Threshold the ridge-enhanced cross-correlation map | Lower both → more picks (more false positives). Raise both → fewer, more conservative picks. The default is the right starting point |
| `Radius around crossings to ignore (diameters)` | Exclude picks near filament crossings | Increase from 1 if many overlap artifacts survive |
| `Distance to trim from end points (diameters)` | Trim ends of contours | 0–2 diameters. Larger trims also reduce spurious crossings |
| `Standard deviation of gaussian blur (diameters)` | Blur prior to ridge detection | Lower than the default of 0.1 may help on very small filaments (e.g. < 100 Å diameter) per the docs |
| `Produce diagnostic plots` | Save per-stage CC-FOM plots and skeleton plots | **Leave on for any new dataset.** These are the primary tool for diagnosing picker failures |

**Filament Tracer assumes:**
- Roughly cylindrical cross-section.
- Approximately constant contrast along the helical axis.

**When Filament Tracer is *not* the right call:**
- **Amyloid fibrils** and other filaments with oblong cross-sections — assumption of cylindrical shape breaks. The Template Picker or a Deep Picking method is preferable.
- Tightly clumped or interwoven filaments where crossings overwhelm the skeletonization.
- Filaments with internal "twist-induced" intensity modulations strong enough to fool the constant-contrast prior.

**Diagnostic plots — what to look for:**
- Ridge-enhanced cross-correlation map: real filaments should appear as continuous bright ridges. If the map looks like a noisy speckle field, the lowpass filter or templates are wrong.
- Skeletonized contours: should overlay along the centerlines of visible filaments. Many short fragments or sharp branches → thresholds too low, blur too low, or filament diameter wrong.
- Final picks: should be evenly spaced along the axis at the configured separation. Clusters at ends or near crossings indicate trimming/crossing radius needs to go up.

**Picking through other pickers.** Helical refinement accepts particles from **any** cryoSPARC picker, as well as imported particles. The one extra obligation when picks come from Topaz, Deep Picker, manual picks, or an imported source is that the "Number of times to apply helical symmetry" parameter of Helical Refinement **must be set manually** (see §8).

---

## 5. 2D classification on filament segments

Use 2D Classification with the same general logic as SPA, but two settings change for filaments (per the 2D Classification docs):

- **`Align filament classes vertically`** — on by default for helical targets, off by default for non-helical. Aligning classes vertically gives an in-plane rotation estimate per filament segment (it does *not* resolve polarity).
- Manual picks for template generation can be **overlapping along the filament**; the absolute spacing does not matter at the manual-picking stage because Filament Tracer enforces the spacing later.

**Forum-attested helical-2D pitfalls:**
- Sigma annealing default can over-aggregate weak, true classes into the same bin as strong classes. For helical assemblies, running a second 2D pass with sigma annealing off (and re-centering off) has been used on the forum to expose junk previously hidden inside a "good" class.
- Many real filament 2D classes look very similar — do not raise the number of classes to compensate for noise; raise it only if you suspect distinct conformational populations.
- For template-generation 2D, the EMPIAR-10031 study used **5 classes** with `Force Max over poses/shifts = on`. Few classes is intentional because all filament views are similar and templates only need to be cleaner than the picks.

**Triage rule:** keep classes that show a clear bright filament against a dark background, with as little surrounding noise as possible. Three to a handful of good templates is enough — diversity of *views along the axis* matters more than count.

---

## 6. Initial volume strategies

Two source-attested options for producing the first 3D map of a filament:

### 6.1 Ab-Initio Reconstruction

Works when the dataset has enough view diversity (segments imaged at varied tilts relative to the helical axis). In v5.0+, set:
- `Volume window mode` → **cylindrical mask** (designed for helical targets).
- Inner/outer window diameters bracket the filament's transverse extent with a soft transition.
- Symmetry C1 by default; do not impose helical symmetry inside ab initio.

Failure mode: very straight, view-uniform filaments collapse to a strong **preferred-orientation** mode in which all segments are assigned similar poses, and the volume becomes a featureless rod. When this happens, abandon ab initio and use asymmetric Helical Refinement.

### 6.2 Asymmetric Helical Refinement

Run a Helical Refinement (BETA) job with **twist and rise left empty**. The job will:
- Generate an initial density using the in-plane (tilt) rotation estimates of the filament picks combined with **scrambled azimuth angles**, and
- Iterate refinement with no helical symmetry imposed.

This is often more robust than ab initio for filaments because it uses the existing pick geometry. Key parameters to budget:

| Parameter | Effect | Default and direction to deviate |
|---|---|---|
| `Initial lowpass resolution (Å)` | Resolution of the first iteration | Higher (coarser) → more bias from the initial random density; lower (finer) → may not align particles |
| `Number of images for initial density generation` | How many particles go into the random init | More images → more bias risk; fewer → less detail in init |
| `GSFSC Split Resolution (Å)` | Resolution beyond which half-maps are treated as independent | Default 20 Å. For **smaller filaments**, try 12–15 Å. If FSC oscillates strongly at low resolution, lower this value |

Per the docs: symmetric refinements are largely insensitive to these parameters (correct symmetry overcomes the initial-density risk); asymmetric refinements may require experimentation.

### 6.3 When to prefer which

| Symptom | Branch |
|---|---|
| Highly variable filament curvature, mix of segment views in 2D | Ab initio with cylindrical window |
| Mostly straight filaments, 2D classes nearly identical | Asymmetric Helical Refinement |
| Ab initio returns a featureless rod | Switch to asymmetric Helical Refinement |
| Asymmetric refinement converges to a noise map | Drop GSFSC split resolution, increase init images, or reduce initial lowpass — but do not chase this for long; consider whether picking is bad |

---

## 7. Average Power Spectra

Average Power Spectra is the bridge to **external Fourier–Bessel symmetry analysis** when in-cryoSPARC symmetry search is not enough.

**What it does (and does not).** It takes the output of `Select 2D Classes` and, for each selected class, computes the power spectrum of *each particle* belonging to that class, then **averages those spectra**. This is *not* the same as computing the power spectrum of the 2D class average — the order matters: power-then-average preserves layer-line content that class-averaging would smear.

**Inputs:**
- Selected 2D classes (and their particles).
- Pass only the classes you want spectra for; computing all classes is wasteful.

**Parameters:**
- `Particle computational batch size` — lower if memory errors hit; result is unchanged.
- `Interpolation order` — cubic by default; rarely tuned.

**Outputs (job directory only):**
- `JX_power_spectra.mrc` — the spectra themselves.
- `JX_power_spectra.cs` — metadata: class UID, sampling in Å⁻¹, paths, indices.

These are **not registered as cryoSPARC outputs** and do not appear in the UI's output graph. They live in the job directory and must be exported manually. Most external indexers expect `.jpg` / `.png`, so a conversion step is needed before use.

**Downstream tools that consume these spectra:**

| Tool | What it does | Source |
|---|---|---|
| HELIXPLORER | Grid-search symmetry parameters by comparing observed and theoretical power spectra | `http://rico.ibs.fr/helixplorer/` |
| PyHI | Python helical indexer (Bai Lab, UT Southwestern) | GitHub `xuewuzhang-UTSW/PyHI` |
| HI3D | Helical indexing (Jiang lab, Purdue) | `https://jiang.bio.purdue.edu/hi3d/` |

**When to use it:**
- Symmetry is unknown and Symmetry Search Utility (which works on a 3D volume) does not have a usable starting volume yet.
- You want a sanity check on candidate twist/rise from Symmetry Search Utility against a Fourier–Bessel inspection of layer lines.

**Limitations:**
- Output is in the job directory only — easy to lose track of when the job is cleared / project archived.
- Power spectra of low-SNR classes are noisy; pick the cleanest classes first.

---

## 8. Symmetry Search Utility (BETA)

A volume-based optimizer that grid-searches helical symmetry parameters by minimizing the mean-squared error between symmetry-related positions in a candidate volume. Use it **after** producing a starting volume (ab initio or asymmetric Helical Refinement) and **before** running symmetric Helical Refinement.

**Inputs:**
- A Volume (the asymmetric or low-symmetry reconstruction).
- An optional Mask. If omitted, the job synthesizes one from the volume; passing a clean mask narrows the search.

**Outputs:**
- 2D and 1D plots of the MSE surface across the search grid.
- Tables of candidate symmetry pairs (the local minima of MSE), ranked by MSE. The global optimum is the first table entry.
- A `.cs` file of symmetry candidates.

**Hands and modes:**

| Mode | Search grid | Hand handling |
|---|---|---|
| Pitch mode | 2D grid over (n, p) | Either right, left, or **both** hands. Default is recommended (both) |
| Rise mode | 2D grid over (Δφ, Δz) | Hand is implicit in the sign of Δφ |

If both hands are searched in pitch mode, the **first checkpoint** in the streamlog shows the right-handed table/plots, the **second checkpoint** the left-handed.

**Key parameters:**

| Parameter | Notes |
|---|---|
| `Search over pitch/number of subunits, or rise/twist?` | Pitch is the default recommendation; rise is preferred when asymmetric unit is so large it does not form a true helical lattice |
| Search grid sizes | Defaults are usually fine. Up to 512 grid points for very large ranges. Larger grids cost more time |
| `Override the number of asymmetric units to search` | If None, calculated automatically as in Helical Refinement |
| `Override outer/inner filament diameter for search (Å)` | If None, derived from the mask |
| Lowpass resolution / filter type | Optionally lowpass the volume before search; choose butterworth or boxcar |
| Which map to search | `map` (raw) or `map_sharp` |
| `Maximum number of candidates to output` | Increase to see more local minima |

**Reading the outputs.** A clean run shows a single deep, smooth MSE basin. Several near-equal candidates means the volume itself does not strongly determine the symmetry — improve the starting volume (better picks / cleaner 2D / asymmetric refinement with different init parameters) before trusting any single candidate.

**Limitations (called out in the docs):**
- The maximum helical rise the search can resolve is tied to the box size; large rises require larger boxes.
- The job is a search, not a validator — confirming the chosen candidate still requires a symmetric Helical Refinement and inspection of the final map.

---

## 9. Helical Refinement (BETA)

The core refinement job for filaments. Conceptually similar to Egelman's IHRSR but built into cryoSPARC's maximum-likelihood + branch-and-bound alignment + optional Non-Uniform regularization stack. v4.4+ delivers ~2× wall-clock speedup for Non-Uniform refinement and for Helical / Local refinements when NU regularization is on.

### 9.1 Inputs / outputs

| Inputs | Outputs |
|---|---|
| Particles (with CTF) | Refined 3D map, symmetrized + sharpened maps |
| Optional Initial model | Half-maps, FSC mask, FSC curve |
| Optional Mask | Mask used in refinement, plots, orientation distribution |
| | Estimated helical twist and rise after refinement |

### 9.2 Helical symmetry parameters

| Parameter | What it does | Notes |
|---|---|---|
| `Helical twist estimate` (°) | Initial Δφ | Sign carries hand. Leave empty for asymmetric refinement |
| `Helical rise estimate` (Å) | Initial Δz | Strictly positive |
| `Number of times to apply helical symmetry` | Controls how many neighbor asymmetric units along the axis are imposed during alignment / backprojection | **Auto-calculated** for Filament Tracer / Template Picker pickers (job prints "Refining with helical symmetrization degree of x enforced"). **Must be set manually** for Topaz / Deep Picker / imported particles, as `⌊d / Δz⌋` where d is inter-box distance |
| `Limit shifts along the helical axis` | Restrict shift search to the central asymmetric unit in the last few iterations | Generally improves resolution slightly; **must be on** if particles will later be used for Symmetry Expansion |
| `Resolution to begin real-space symmetrization` (Å) | When GSFSC reaches this, the alignment volumes have helical symmetry enforced in real space | Default 8 Å. Once real-space symmetrization starts, it tends to **lock the symmetry in** and further parameter search has little effect. If twist/rise are not trusted yet, drop to 4–5 Å to give the search more room |
| `Point group symmetry` | Stack a Cn or Dn point group on top of helical | Cn axis assumed aligned with helical (Z); Dn dyad assumed perpendicular. T/O/I not supported |

### 9.3 Helical Symmetry Search (BETA) parameters

A separate set of parameters governs local optimization of (Δφ, Δz) during refinement:

- `Resolution to begin local searches of helical symmetry` — once GSFSC crosses this, local searches around the current (Δφ, Δz) replace fixed-symmetry application.
- Search ranges and step sizes around the current estimate.
- If twist/rise are already trusted, the default works. If not, **start symmetry search earlier** (coarser resolution) so the parameters can move more before real-space symmetrization locks them in.

The combination "low Number of times to apply helical symmetry (e.g. 2–3) + earlier symmetry search + delayed real-space symmetrization" is the documented escape hatch when initial twist/rise estimates are weak.

### 9.4 Non-Uniform regularization

Optional, off by default for older versions. Recommended for any filament where local resolution varies along the axis or where the asymmetric unit has flexible regions. v4.4 made this ~2× faster than v4.3; there is no longer a strong cost-based reason to leave it off when the refinement is otherwise reasonable.

### 9.5 Initial density and small-filament considerations

Re-uses the same `Initial lowpass resolution`, `Number of images for initial density generation`, and `GSFSC Split Resolution` parameters as asymmetric refinement (§6.2). Symmetric refinements with correct twist/rise are largely insensitive to these; asymmetric refinements may need tuning, especially `GSFSC Split Resolution` at 12–15 Å for small filaments.

### 9.6 Amyloid and other challenging cases

The bundle does not provide an amyloid-specific case study, but the source-attested issues form a checklist:
- **Picking:** Filament Tracer's cylindrical / constant-contrast assumption is a poor fit for oblong amyloid cross-sections — switch to Template Picker or Deep Picking.
- **Symmetry:** amyloid twists are often small and rises near 4.7–4.8 Å; Symmetry Search Utility's grid step and range must accommodate this. Verify rise is well-separated from sampling artifacts before trusting it.
- **Polarity / pseudo-2_1 screw axis** is a recurring trap (often called the "C2 vs pseudo-2_1" ambiguity in the literature). cryoSPARC's helical jobs do not auto-resolve polarity — verify with external tools / model fits.
- **Mask:** start with a generous soft cylindrical mask (see `20_masks.md`); a tight mask inflates GSFSC and hides resolution anisotropy along the axis.

---

## 10. Validation and postprocessing for helical maps

| Diagnostic | What to read it for | Notes |
|---|---|---|
| GSFSC curve | Final resolution + oscillations | **Persistent strong oscillations into final iterations** are a primary signal of wrong symmetry being imposed |
| Asymmetric vs symmetric comparison | Sanity check | Re-run as asymmetric and verify the symmetric map's features are *consistent* with the asymmetric volume (no symmetry-induced artifacts), not just sharper |
| Orientation distribution | Preferred orientation | Filaments are intrinsically biased; combine with Orientation Diagnostics for cFSC / sphericity if available |
| Real-space asymmetric-unit overlay | Check that adjacent asymmetric units along the axis truly look the same after symmetrization | If they differ, the imposed (Δφ, Δz) is wrong or the box is too small to capture enough neighbors |
| Symmetry-search MSE basin | Depth and uniqueness of the chosen candidate | Several near-equal candidates = symmetry ambiguous; treat with suspicion |
| Local resolution along the axis | Tapering at filament ends is expected, but flat low-res zones in the middle suggest box too small or symmetrization wrong | |
| FSC mask sanity | Inflated GSFSC from too-tight mask | Mask logic: `20_masks.md` |

**Postprocessing path:** otherwise standard (`10_postprocessing.md`). For filaments, a soft, generous cylindrical mask is normal; an atomic-model-derived mask (via ChimeraX `molmap`) on the asymmetric unit then expanded along the axis works well once a model is available.

**Symmetry Expansion as a *follow-up* step.** Helical refinement's particle output can be passed to Symmetry Expansion (helical mode) to duplicate poses around the helical symmetry, then into Local Refinement / 3D Classification / 3DVA to look at symmetry-breaking features. Do **not** run a global refinement (Ab-Initio, Homogeneous, Heterogeneous, Non-Uniform, Helical) on symmetry-expanded particles — this duplicates particles in the FSC calculation. The `Limit shifts along the helical axis` option must have been on in the upstream Helical Refinement for this to work cleanly.

**Half-set integrity.** Repeated refinement after re-extraction, RBMC, or particle re-bucketing can re-mix half-sets and inflate FSC. From v4.5.3 onward, refinement jobs (including Helical Refinement) default to using the input particles' existing `alignments3D/split` field, which is the right default for filament pipelines. v4.2 added `Force re-do FSC split` in 3D Classification specifically to allow *preserving* the splits from previous helical refinements, symmetry expansions, or local refinements. If you import filament particles or route them through external tools, audit whether the split survived.

---

## 11. Advisor decision tables

### 11.1 First questions when a user says "I'm doing a helical project"

| Question | Why it matters |
|---|---|
| Is the twist + rise known from prior structures, biology, or literature? | If yes → straight to symmetric Helical Refinement. If no → branch through Symmetry Search Utility / Average Power Spectra |
| Is the filament approximately cylindrical with roughly constant axial contrast? | If no (e.g. amyloid) → do not use Filament Tracer; use Template Picker or Deep Picking |
| Roughly how big is the asymmetric unit? | Very small ASUs are highly sensitive to wrong symmetry; small filaments may need `GSFSC Split Resolution` 12–15 Å |
| Are the picks coming from Filament Tracer / Template Picker, or from Topaz / Deep Picker / imported? | Determines whether `Number of times to apply helical symmetry` auto-fills or must be set manually |
| What hand is biologically expected? | Hand is encoded in Δφ sign; the search will return both unless restricted |
| Is the goal a high-resolution symmetric map, or symmetry-breaking features in subregions? | The second case requires Symmetry Expansion after refinement and a Local Refinement strategy |

### 11.2 Picker decision

| Filament type | Picker | Notes |
|---|---|---|
| Cylindrical filament with reasonable contrast, 2D templates available | Filament Tracer (template-based) | Use 3+ diverse templates |
| Cylindrical filament, no templates yet | Filament Tracer (template-free) with Min/Max diameter | Run on a small subset first |
| Amyloid / oblong cross-section | Template Picker or Deep Picker | Filament Tracer's cylindrical assumption fails |
| Tightly clumped / many crossings | Manual subset → templates → Template Picker | Filament Tracer's crossing pruning can be aggressive |
| Low contrast / small filament | Topaz on a clean seed | Plan to set `Number of times to apply helical symmetry` manually in Helical Refinement |

### 11.3 Symmetry-handling branch

| State | Path |
|---|---|
| Twist + rise known and trusted | Helical Refinement with values filled, defaults for symmetrization onset, NU regularization on |
| Twist + rise plausible but not validated | Helical Refinement with values filled + earlier symmetry search start (lower-res threshold) + lower `Resolution to begin real-space symmetrization` |
| Twist + rise unknown, volume available | Symmetry Search Utility → top candidates → series of symmetric Helical Refinements |
| Twist + rise unknown, no usable volume | Asymmetric Helical Refinement → Symmetry Search Utility |
| Volume search ambiguous | Average Power Spectra → external Fourier–Bessel indexer (HELIXPLORER / PyHI / HI3D) |
| Hand ambiguous | Symmetry Search Utility with both hands → external validation (model fit, tilt-pair) |

### 11.4 Red flags (short-circuit normal routing)

| Red flag | Implication |
|---|---|
| Filament Tracer diagnostic plots not produced (turned off) on a new dataset | Cannot debug picking failure without them — turn back on and re-run |
| GSFSC has strong oscillations into the final iterations of a symmetric refinement | Wrong (Δφ, Δz) imposed — re-validate symmetry before trusting resolution |
| Symmetric map looks dramatically sharper than asymmetric map with same particles | Imposed symmetry may be inventing structure; cross-check with an asymmetric reference run |
| `Number of times to apply helical symmetry` set to its UI default after Topaz / Deep Picker / imported picks | Likely wrong — recompute as `⌊d / Δz⌋` |
| Symmetry Search Utility returns several near-equal candidates | Symmetry is not determined by the current volume — improve picks / 2D / initial density first |
| Power Spectra outputs missing in the UI graph | Expected — they are in the job directory only |
| Helical refinement run on symmetry-expanded particles | Wrong — only Local Refinement / 3D Classification / Variability after symmetry expansion |

### 11.5 Advisor defaults / safe defaults

| Stage | Default that is usually right |
|---|---|
| Preprocessing | Same as SPA (`03_preprocessing.md`) |
| Picking | Filament Tracer (template-based) with 3+ diverse templates, default hysteresis thresholds (93 / 98), diagnostic plots ON |
| Extraction | FFT-friendly box ≥ ~1.5–2× longest segment dimension; tighter only if VRAM-limited |
| 2D | Defaults, `Align filament classes vertically` ON, modest class count |
| Initial volume | Cylindrical-window ab initio (v5.0+); fall back to asymmetric Helical Refinement if ab initio collapses |
| Helical Refinement | NU regularization ON, `Resolution to begin real-space symmetrization` at default 8 Å, `Limit shifts along the helical axis` ON if expansion is planned |
| Postprocessing | Soft cylindrical mask, generous; auto-tight masks risk inflating GSFSC |
| Export | Half-maps + mask for downstream RELION / ChimeraX (see `27_relion_interop.md`) |

---

## 12. Failure modes

Source-attested or source-implied failures, with the upstream lever that fixes them. Most "ugly helical map" complaints reduce to one of these.

### 12.1 Picking failures

| Symptom | Likely cause | Fix |
|---|---|---|
| Filament Tracer picks cluster at filament ends, not centers | Trim distance too low, or hysteresis thresholds too low | Raise `Distance to trim from end points` to 1–2 diameters; raise thresholds slightly |
| Many false picks across crossings | Crossings not being removed | Raise `Radius around crossings to ignore` from 1 |
| Few picks on visible filaments | Thresholds too high, or wrong filament diameter | Lower hysteresis thresholds in small steps; re-check filament diameter on the micrograph |
| Picker performance fine on cylindrical filaments, bad on amyloid | Cylindrical / constant-contrast assumption violated | Switch to Template Picker or Deep Picking |
| Diagnostic plots show speckle, not ridges | Lowpass filter wrong, templates wrong, or contamination dominates | Re-tune lowpass; use fewer, cleaner templates |
| Topaz / imported picks → Helical Refinement runs but features look smeared along axis | `Number of times to apply helical symmetry` left at UI default | Recompute manually as `⌊d / Δz⌋` |

### 12.2 2D failures

| Symptom | Cause | Fix |
|---|---|---|
| All 2D classes look identical, no view diversity | Filament too straight, all segments imaged near 90° to beam | Live with it; rely on asymmetric Helical Refinement for initial model |
| Junk persists inside "good" classes after Select 2D | Sigma annealing default oversmooths | Re-run 2D with sigma annealing and re-centering off; cross-check selections (forum-attested for helical) |
| Templates from 2D have ghost particles in the background | Manual picks too dense or near edges | Re-do manual picking with more variety in defocus and fewer crowded fields |

### 12.3 Initial-model failures

| Symptom | Cause | Fix |
|---|---|---|
| Ab initio collapses to a featureless rod | Preferred orientation from view-uniform filaments | Switch to asymmetric Helical Refinement |
| Asymmetric refinement converges to noise | Initial lowpass too low, or too few init images, on a small filament | Lower `GSFSC Split Resolution` (12–15 Å); raise initial lowpass cautiously; raise init image count |
| Asymmetric refinement converges to a clearly wrong shape | Picking is bad, not initialization | Go back to Filament Tracer and re-tune; do not chase symmetric refinement parameters |

### 12.4 Symmetry failures

| Symptom | Cause | Fix |
|---|---|---|
| Symmetric refinement looks sharper than truth supports | Wrong (Δφ, Δz) imposed | Re-validate with Symmetry Search Utility on the asymmetric map; compare asymmetric vs symmetric maps side-by-side |
| GSFSC oscillates strongly into final iterations | Wrong symmetry locked in early | Lower `Resolution to begin real-space symmetrization` to 4–5 Å; restart symmetry search at coarser resolution |
| Symmetry Search Utility returns multiple equally good candidates | Volume does not determine symmetry | Improve volume first (better picks, more particles, asymmetric refinement with better init); only then re-run search |
| Hand is wrong | Δφ sign | Use Volume Tools to flip volume; **`Homogeneous Reconstruction Only` with `Flip handedness`** also updates particle poses, which is what Helical Refinement actually needs (note: v4.1 fixed a related bug for helical sym + custom box size) |
| Helical + point group imposed but volume looks distorted | Point-group axis convention violated | Cn must be along Z; Dn dyad must be perpendicular to the helical axis. Re-align volume first |

### 12.5 Box / VRAM failures

| Symptom | Cause | Fix |
|---|---|---|
| `cufftAllocFailed` / `pycuda._driver.MemoryError` on Helical Refinement | Box × batch × #GPU > VRAM | Reduce box (re-extract with Fourier crop), drop batch / #GPU, move to higher-VRAM card. v4.1 reduced extraction GPU memory; see `21_gpu_lane_queue.md` |
| Box too small to contain enough neighbors for symmetrization | Real-space symmetrization on a tight box leaves edge artifacts | Re-extract at a larger box; raise `Resolution to begin real-space symmetrization` so it kicks in later |
| Box too large, refinement painfully slow | FFT non-friendly size or excessive padding | Use the FFT-friendly box list from Extract from Micrographs (e.g. 384, 400) |

### 12.6 Half-set / postprocessing failures

| Symptom | Cause | Fix |
|---|---|---|
| GSFSC suspiciously high after RBMC + re-refinement on helical particles | Half-set split lost in re-extraction | Audit `alignments3D/split` propagation; v4.5.3+ refinements default to preserving the input split |
| Strong FSC dip at low resolution on a tight mask | Mask too tight | Loosen mask (see `20_masks.md`); use mask resolution ≈ 1 Å fallback for a no-mask sanity check |
| 3D Classification on helical-refinement output fails / inflates FSC | Forgot to reuse splits | v4.2+: enable `Force re-do FSC split` only if you actually want to reset the split; off preserves upstream helical splits |

### 12.7 Beta / version failures

| Symptom | Version note | Source |
|---|---|---|
| Homogeneous Reconstruction Only fails on helical symmetry + custom box | Fixed in v4.1 | `reference/release_notes/markdown/v4.1.md` |
| Homogeneous Ab-Initio Refinement `KeyError` on helical data | Fixed in v5.0 | `reference/release_notes/markdown/v5.0.md` |
| Helical Refinement quick actions / info tags missing in UI | Added in v4.5; older versions show fewer tags but refinement still works | `reference/release_notes/markdown/v4.5.md` |
| Non-Uniform-regularized helical refinement very slow | v4.4 made NU ~2× faster | `reference/release_notes/markdown/v4.4.md` |
| `Force re-do FSC split` missing in 3D Classification | Added in v4.2 specifically to preserve helical refinement / symmetry-expansion splits | `reference/release_notes/markdown/v4.2.md` |
| Forum thread recommends a parameter or workflow from before v4.0 | Predates Average Power Spectra; cross-check against current job pages | `version_caveats.md` (see also `17_error_lookup.md`) |

When in doubt about a behavior described on the forum, verify against the local instance's job page and the bundled per-page docs; helical jobs are BETA and the parameter UI has shifted across minor releases.

---

## 13. Cross-references to other topics

| Need | Topic |
|---|---|
| Movie import / metadata / pixel size confirmation | `02_import.md` |
| Patch motion + CTF + curation defaults | `03_preprocessing.md` |
| Picker decision tree, Topaz mechanics, Inspect Picks | `04_picking.md` |
| Extraction box / FFT-friendly sizes / Fourier crop | `05_extraction_2d.md` |
| Ab-initio cylindrical window mode (v5.0+) | `06_abinitio.md` |
| Refinement branch logic for non-helical or post-helical local refinement | `07_refinement.md`, `09_local_refinement.md` |
| 3D Classification on filament particles | `08_classification_3d.md` |
| FSC reading, sharpening, anisotropy | `10_postprocessing.md` |
| Mask construction (cylindrical, model-derived, soft) | `20_masks.md` |
| Point-group / hand strategy, symmetry expansion | `19_symmetry.md` |
| Tuning recipes by stage | `16_tuning_recipes.md` |
| Decision-tree routing across the pipeline | `18_decision_trees.md` |
| Troubleshooting mental model | `15_troubleshooting.md` |
| Error string lookup | `17_error_lookup.md` |
| Lanes / GPU / VRAM and box trade-offs | `21_gpu_lane_queue.md` |
| Disk lifecycle, project archival, where job-directory-only Power Spectra files live | `24_disk_and_storage.md` |
| RELION star-file round-trips with helical/optics metadata | `27_relion_interop.md` |
| External postprocessing (DeepEMhancer / ModelAngelo) | `23_external_jobs.md` |

---

## 14. Version notes and beta caveats

- Helical jobs are **BETA** in the bundled v5.0 documentation. Treat parameter names, defaults, and UI labels as version-dependent; verify against the local instance.
- **v4.0** added the Average Power Spectra job and shipped the helical reconstruction branch as part of the main job catalog.
- **v4.1** fixed a bug in Homogeneous Reconstruction Only with helical symmetry + custom box size, and reduced extraction GPU memory.
- **v4.2** added 3D Classification's `Force re-do FSC split` parameter, which interoperates with helical refinement / symmetry expansion splits.
- **v4.4** delivered ~2× speedups on Non-Uniform refinement and on Helical / Local refinements with NU regularization enabled.
- **v4.5** added UI quick actions and info tags for Helical Refinement; **v4.5.3** consolidated `alignments3D/split` reuse across re-extraction / RBMC.
- **v5.0** added cylindrical Volume window mode in Ab-Initio Reconstruction, and fixed a `KeyError` in Homogeneous Ab-Initio Refinement when running on helical data.
- If a user is more than two minor versions behind and reports a helical-job bug, update before deep debugging — many helical bugs have specific version-fixed entries.

If a specific helical parameter or behavior is not in this page and not in the bundled per-page docs, verify locally rather than invent: run the job with defaults on a small subset, inspect the streamlog for the relevant parameter line, or query the per-page docs via the GET-with-`ask` mechanism documented on each cryoSPARC docs page.

---

## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

Documentation pages (cryoSPARC guide, bundled per-page docs):

- `docs/per_page/processing-data__all-job-types-in-cryosparc__helical-reconstruction-beta.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__helical-reconstruction-beta__helical-symmetry-in-cryosparc.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__helical-reconstruction-beta__job-average-power-spectra.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__helical-reconstruction-beta__job-helical-refinement-beta.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__helical-reconstruction-beta__job-symmetry-search-utility-beta.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__particle-picking__job-filament-tracer-beta.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__particle-picking.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__particle-curation__job-2d-classification.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-reconstruction__job-ab-initio-reconstruction.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__3d-refinement__job-homogeneous-refinement.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__utilities__job-symmetry-expansion.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__case-study-empiar-10031-mavs.md`

Local topic and reference files:

- `topic_plan.md`
- `plan.md`
- `00_overview.md`
- `03_preprocessing.md`
- `04_picking.md`
- `05_extraction_2d.md`
- `06_abinitio.md`
- `07_refinement.md`
- `10_postprocessing.md`
- `16_tuning_recipes.md`
- `18_decision_trees.md`
- `19_symmetry.md`
- `20_masks.md`
- `21_gpu_lane_queue.md`
- `24_disk_and_storage.md`
- `27_relion_interop.md`
- `17_error_lookup.md`

Release notes:

- `reference/release_notes/markdown/v4.0.md`
- `reference/release_notes/markdown/v4.1.md`
- `reference/release_notes/markdown/v4.2.md`
- `reference/release_notes/markdown/v4.4.md`
- `reference/release_notes/markdown/v4.5.md`
- `reference/release_notes/markdown/v5.0.md`

Video notes:

- `videos/notes/01_introduction_and_cryoem_fundamentals.notes.md`
- `videos/notes/02_trpv1_and_a_standard_workflow.notes.md`
- `videos/notes/04_encapsulated_ferritin_and_non_point_group_symmetry.notes.md`
- `videos/notes/08_reference_based_motion_correction.notes.md`

Forum digests:

- `docs/forum_threads/digests/forum_particle-picking.md`
- `docs/forum_threads/digests/forum_2d-classification.md`
- `docs/forum_threads/digests/forum_3d-reconstruction.md`
- `docs/forum_threads/digests/forum_troubleshooting.md`
- `docs/forum_threads/digests/forum_cryo-em-data-processing.md`
