# Reference — cryoSPARC CTF Refinement and RBMC

## Scope / how to use

Retrieval-first reference for late-stage CTF/motion polishing in cryoSPARC:
- **Local CTF Refinement** — per-particle defocus refinement.
- **Global CTF Refinement** — per-exposure-group higher-order aberration and anisotropic magnification refinement.
- **Reference Based Motion Correction (RBMC)** — per-particle movie-frame trajectories and empirical dose weights.

Use this after the project already has a stable consensus refinement. These jobs do not rescue a bad particle stack, bad poses, mixed states, wrong metadata, or a poor reference. They are last-mile corrections that must be validated by matched before/after reconstruction or refinement.

Source note: original synthesis from public cryoSPARC guide/release notes/forum/tutorial materials and public `cryosparc-tools` documentation/API material; consult upstream documentation for authoritative details.

---

## Fast decision table

| Question | Use | Prerequisites | Main diagnostic | Stop if |
|---|---|---|---|---|
| Are per-particle defocus values limiting resolution? | Local CTF Refinement | particles with `ctf`, `blob`, `alignments3D`; reference half-maps; mask | defocus-error landscapes with single deep minima near 0; before/after reconstruction improves | shallow/multiple minima, heavy tails, or reconstruction worsens |
| Are microscope higher-order aberrations or anisotropic magnification limiting high-res signal? | Global CTF Refinement | particles with `ctf`, `blob`, `alignments3D`; reference map; exposure groups | phase-error data → fit → residual; red/blue pattern captured and residual reduced | data pattern weak/incoherent or residual not improved |
| Is residual per-particle motion / dose weighting limiting final map? | RBMC | raw movies/exposures from Patch Motion, particles trace back to movies, good reference volume/half-maps/mask, stable poses | empirical dose weights plausible; trajectories smooth; matched refinement improves | only aligned micrographs exist, reference/poses poor, dose weights look overfit, no matched gain |
| Need a quick test of whether CTF refinement helped? | Homogeneous Reconstruction Only before/after | same mask and same input poses | GSFSC/map features at matched settings | comparison uses different masks/poses/refinement settings |
| Multiple collection sessions / AFIS / beam-shift groups? | Exposure Group Utilities before Global CTF/RBMC | honest group IDs by microscope condition | per-group plots sensible | groups mix incompatible optics/CTF values |

---

## Placement in the workflow

Default late-stage order:

1. Import movies correctly with exposure groups when possible.
2. Patch Motion → Patch CTF → exposure curation → picking/extraction → 2D/3D cleanup.
3. Homogeneous/NU consensus refinement; verify clean map/FSC and stable poses.
4. Test **Local CTF** and/or **Global CTF**; validate by matched Homogeneous Reconstruction Only or same-refinement rerun.
5. If raw movies exist and consensus is solid, test **RBMC**; validate by same downstream refinement/local refinement settings.
6. Continue with final NU/local refinement/classification only after confirming the correction helped.

Do not run CTF refinement or RBMC as an early cleanup branch. If the consensus is blurry because states are mixed, particles are junky, box/pixel size is wrong, or the map is near Nyquist, fix those first.

---

## Prerequisite checklist

### Common prerequisites for CTF refinement

- Particles have required slots:
  - `ctf`
  - `blob`
  - `alignments3D`
- Reference volume comes from the **same refinement branch** as the particles.
- Local CTF has `map_half_A` and `map_half_B`; global CTF needs the map and can use `mask_refine` or supplied mask.
- Mask covers the signal used for fitting without excessive solvent/noise.
- Current map has enough medium/high-resolution signal for the intended fit.
- Exposure groups are meaningful if doing Global CTF.

### Common prerequisites for RBMC

- Raw movies/exposures were imported into cryoSPARC. Aligned micrographs alone are not enough.
- Exposures came through Patch Motion Correction so they have rigid motion and background estimates.
- Particles trace back to those movies/exposures.
- Reference volume has half-maps and mask.
- Particles and reference are from the same refinement, ideally with `minimize over per-particle scale` enabled upstream.
- For heterogeneous datasets, provide multiple particle/volume/mask sets by increasing `Number of reference volumes`.
- Hardware can sustain the job: GPU(s), CPU feeding, RAM cache, and disk I/O.

---

## Local CTF Refinement

### What it does

Local CTF Refinement estimates an optimal **per-particle defocus** against a 3D reference. Conceptually, it searches defocus values around the current particle CTF and asks which value best explains the particle image from its known pose/reference.

Best suited for:
- larger, rigid, high-quality particles;
- maps already reaching reasonably high resolution, often better than ~4 Å;
- samples with non-flat ice where particle height differs within micrographs;
- cases where Patch CTF is good but per-particle height still matters.

Less reliable for:
- small/flexible/low-SNR particles;
- membrane proteins dominated by micelle/disorder;
- mixed-state stacks;
- early refinements with unstable poses.

### Inputs and outputs

Inputs:
- Particles: `ctf`, `alignments3D`, `blob` required.
- Volume: `map_half_A`, `map_half_B` required; `map` optional; `mask_refine` optional.
- Mask: optional.

Output:
- Particle set with updated CTF parameters.

### Key parameters

| Parameter | Practical guidance |
|---|---|
| `Minimum fit res (A)` | Use medium/high-resolution signal only. For smaller particles, make this a higher-resolution cutoff so low-resolution signal does not dominate the fit. |
| `Maximum fit res (A)` | Leave blank for FSC-based auto choice unless you have reason to cap noisy high-resolution signal. |
| `Defocus search range` | If Patch CTF was used, keep relatively small — roughly expected ice thickness / plausible particle height range. Large search ranges encourage edge hits and false minima. |
| `Optimize defocus over per-particle scale` | v5 default. Jointly optimizes scale and defocus and can improve the defocus error landscape. |
| Ewald settings | Use only if prior Ewald-sphere reconstructions showed measurable benefit and curvature sign is known. |

### Diagnostics to trust

| Plot/signal | Good | Bad |
|---|---|---|
| Per-particle defocus error landscape | single clear minimum, often near 0 change; deep well | shallow well, multiple similar minima, minimum at edge of search range |
| Defocus-change histogram | peaked near 0, no heavy tails | broad/heavy tails, many particles at search bounds |
| Matched reconstruction FSC | same mask/settings improves or map detail improves | worsens or only unmasked FSC improves |

Interpretation: broad or multi-well landscapes mean the data do not strongly support a unique per-particle defocus. Do not force Local CTF into final particles just because the job completed.

---

## Global CTF Refinement

### What it does

Global CTF Refinement fits **per-exposure-group** high-order CTF parameters against a reference:
- beam tilt;
- trefoil;
- spherical aberration;
- tetrafoil;
- anisotropic magnification.

It uses aggregate signal from all particles in an exposure group, so it can work better than Local CTF for some smaller/flexible particles, but it still needs a good reference and sufficient high-resolution signal.

### Inputs and outputs

Inputs:
- Particles: `ctf`, `alignments3D`, `blob` required.
- Volume: `map` required; `mask_refine` optional.
- Mask: optional.

Output:
- Particle set with updated CTF parameters.

### Parameter strategy

| Parameter | Practical guidance |
|---|---|
| `Number of iterations` | 1 is usually enough for aberrations only; use at least 2 when fitting anisotropic magnification together with aberrations. |
| `Minimum fit res (A)` | Avoid low-resolution signal; smaller particles need stricter/high-resolution fitting. |
| `Maximum fit res (A)` | Auto via half-map FSC is usually safest. |
| Fit Tilt / Trefoil | Third-order terms; default on from v4.0; lower signal requirement than fourth-order terms. |
| Fit Spherical Aberration / Tetrafoil | Fourth-order terms; default off from v4.0; can be detrimental if earlier terms/per-particle defocus are wrong or high-res signal is weak. |
| Fit Anisotropic Magnification | Usually rare; default off; turn on deliberately and use ≥2 iterations. |

### Plot interpretation

For each aberration order, inspect three plot types:
1. **Measured phase error data** — look for coherent red/blue patterns.
2. **Fit prediction** — should resemble the coherent part of the measured pattern.
3. **Residual** — should be weaker/noise-like after fitting.

Rules:
- Odd terms are optimized from zero each run, so measured-data plots can still show aberration patterns on repeated runs.
- Even terms and anisotropic magnification start from current values; repeated runs may show near-zero measured even terms if already corrected.
- Beam tilt is internally parameterized in Å; log may also report mrad when spherical aberration is non-zero.
- For anisotropic magnification, an unconstrained displacement plot should show a linear trend; residual should lose that trend after fitting. No trend = little anisotropy; nonlinear trend = severe anisotropy or other systematic effects.

### Exposure-group hygiene

Global CTF is only as good as exposure grouping.

Use exposure groups for:
- separate collection days/sessions;
- AFIS/image-shift groups;
- different grids/microscope states;
- distinct optics conditions.

Tools:
- set groups at Import with `Override Exposure Group ID` when known;
- use Exposure Group Utilities to `split`, `combine&set`, `cluster&split`, or inspect groups;
- split by path token for EPU/SerialEM-style file names;
- use beam-shift clustering when valid metadata exists.

Danger: combining incompatible groups dilutes or corrupts per-group fits. Splitting groups too finely can leave insufficient signal per group.

---

## CTF refinement ordering patterns

### Pattern A — simple test branch

1. Take best Homogeneous/NU particles + volume.
2. Run Local CTF Refinement.
3. Run Homogeneous Reconstruction Only using the Local CTF particles, same mask.
4. Run Global CTF Refinement from the original or Local CTF particles.
5. Run Homogeneous Reconstruction Only using Global CTF particles, same mask.
6. Compare against original reconstruction.

Use this when exploring whether CTF refinement helps at all without committing to a long re-refinement chain.

### Pattern B — global then local

Use when Global CTF gives clear fit/residual improvement and Local CTF landscapes look plausible:

```text
consensus particles → Global CTF → Local CTF → final refinement
```

Reasoning: per-group aberration/magnification correction can improve the baseline CTF before per-particle defocus refinement.

### Pattern C — local then global

Use when per-particle height/defocus seems obviously limiting and global plots are ambiguous:

```text
consensus particles → Local CTF → Global CTF → final refinement
```

Always validate both orders if the decision matters; fit quality can depend on each other.

### Pattern D — on-the-fly refinement

Homogeneous Refinement can run local/global CTF refinement on-the-fly after initial convergence. Non-Uniform Refinement supports higher-order CTF correction, but standalone Local/Global CTF before NU is often clearer for testing and diagnostics. Legacy refinements do not support high-order CTF aberration/anisotropic magnification correction.

---

## Reference Based Motion Correction (RBMC)

### What it does

RBMC uses particle poses, pick locations, raw movie frames, and a high-quality 3D reference to estimate:
- per-particle motion trajectories across movie frames;
- empirical dose weights via Fourier Cylinder Correlation (FCC);
- motion-corrected particle images for final refinements.

It is inspired by RELION Bayesian Polishing but implemented natively in cryoSPARC, with multi-GPU support, hyperparameter search, multiple reference volumes, and reusable hyperparameters/dose weights.

### Inputs

| Input | Requirement |
|---|---|
| Exposures / Movies | Must have Patch Motion rigid motion and background estimates. In v4.4 this input was called Movies; Exposures is equivalent. |
| Particles | Same refinement branch as reference; poses and pick locations must be valid. Upstream `minimize over per-particle scale` is recommended. |
| Volumes | Reference volume with half-maps and mask. |
| Masks | Optional static masks per reference; otherwise use connected volume mask. |
| Hyperparameters | Optional prior motion hyperparameters and/or dose weights from previous RBMC. |

For heterogeneous datasets, increase `Number of reference volumes` and connect matched particles/volumes/masks for each state/species.

### Key parameters and hardware

| Parameter | Practical guidance |
|---|---|
| `Final processing stage` | Stop early to compute only hyperparameters or dose weights for diagnostic/reuse. |
| `Save results in 16-bit floating point` | Usually encouraged; halves output particle disk use without known quality loss in most cases. |
| `Override: EER number of fractions` | Only if no frames were discarded in Patch Motion. |
| `Recenter particles` | Recenter pick locations based on upstream optimized shifts; useful when poses/shifts are reliable. |
| `Skip movies with wrong frame count` | Use when a minority of movies differ in frame count; discards non-modal frame-count movies. |
| `Hyperparameter search thoroughness` | Fast usually sufficient; Balanced/Extensive cost more. |
| `Maximum total prior strength` | Increase if trajectory activity does not approach zero at last search iteration. |
| `Target number of particles` | Only a subset is needed for hyperparameter estimation. |
| Override prior parameters | Supply all three overrides or none. Use when auto-search produced known bad weights/trajectories. |
| `Use all Fourier components` | Usually leave on for final iteration. |
| Fourier-crop output box | Use to reduce output particle resolution/size; be explicit about final refinement needs. |
| Number of GPUs | More helps only if CPU/RAM/I/O can feed them; scaling beyond ~3–4 GPUs can be CPU-limited. |
| GPU oversubscription threshold | Oversubscribe high-VRAM GPUs only if CPU can keep up. |
| In-memory cache size | Use ~60–80% RAM, lower unless machine has >256 GB RAM. |
| Slicing GPU also computes trajectories | Turn off to reduce VRAM pressure on slicing GPU; requires at least two GPUs. |

### Hyperparameter logic

RBMC regularizes trajectories with:
- **spatial prior** — nearby particles should move similarly;
- **acceleration/temporal prior** — motion should be smooth over frames.

If priors are too weak, trajectories follow noise. If too strong, motion collapses toward zero. Auto-search tries many total-prior/balance/correlation-distance rays and scores them by cross-validation against the opposite half-map; lower/more negative cross-validation is better.

### Dose-weight diagnostics

Good empirical dose weights usually show high-frequency information strongest in early frames, sometimes with frame 2/3 better than frame 1 if initial motion damages frame 1.

Red flags:
- high-frequency signal apparently reappears in very late frames;
- dose weights look noisy/striped without physical interpretation;
- trajectories are jagged or too large;
- final refinements worsen despite nominal RBMC completion.

For tricky small/noisy datasets, case studies suggest manually strengthening the spatial prior just for dose-weight estimation can improve empirical dose weights. Treat this as an expert branch: clone RBMC, override priors, and compare matched downstream refinements.

### Reuse of dose weights / hyperparameters

Reuse is reasonable when:
- same or closely related dataset;
- same microscope/camera/dose/fractionation/collection conditions;
- same sample type and similar motion behavior;
- rerunning after a parameter-only change.

Patch Motion v4.4+ can accept RBMC empirical dose weights as an optional input, allowing reuse of dose weights at lower cost for related datasets.

---

## Validation patterns

### Matched reconstruction check

For CTF refinement:
1. Original particles → Homogeneous Reconstruction Only with mask M.
2. CTF-refined particles → Homogeneous Reconstruction Only with same volume/poses/mask M.
3. Compare FSC and visible map features.

This isolates CTF metadata effects from pose re-optimization.

### Matched refinement check

For RBMC:
1. Original particles → same final refinement settings.
2. RBMC particles → same final refinement settings.
3. Compare corrected FSC, local features, map interpretability, and half-set behavior.

Do not compare an RBMC branch that also changed mask, box, symmetry, particle count, or cleanup state unless the experiment is explicitly multi-factor.

### What counts as improvement

Trust:
- consistent improvement in corrected FSC and visible features;
- better density in known high-resolution regions;
- cleaner CTF/RBMC diagnostic residuals;
- no new artifacts or half-set split issues.

Do not trust:
- unmasked FSC only;
- tiny nominal resolution gain with worse map features;
- overfit-looking late-frame dose weights;
- improvement after many unconstrained re-refinement loops without split audit.

---

## Common failure patterns

| Symptom | Likely cause | Fix |
|---|---|---|
| Local CTF minima shallow/multiple | particle too small/flexible/noisy; reference/poses weak | skip Local CTF or tighten fit-res range; improve consensus first |
| Many Local CTF particles hit search bounds | search range too small/large or input defocus wrong | inspect Patch CTF/import metadata; adjust search range only after metadata check |
| Global CTF residual still shows same red/blue pattern | fit not capturing real aberration or wrong group/mask | try fewer terms; fix exposure groups; check reference/mask |
| Fourth-order terms worsen map | insufficient high-res signal or lower-order/per-particle terms not stable | fit tilt/trefoil first; leave spherical/tetrafoil off |
| Anisotropic mag fit unstable | no linear displacement trend, too few particles, iterative instability | fit only in standalone Global CTF; avoid repeated on-the-fly aniso mag |
| CTF-refined branch cannot merge with another branch | CTF values inconsistent after separate refinement | choose a common pre-classification CTF donor or low-level swap CTF values carefully |
| RBMC cannot run | only aligned micrographs or imported particles exist | recover/import raw movies; otherwise RBMC unavailable |
| RBMC worse/no gain | poor reference/poses, overfit dose weights, insufficient residual motion, wrong priors | validate diagnostics; rerun with adjusted priors or skip RBMC |
| RBMC GPU scaling poor | CPU/RAM/I/O bottleneck | fewer GPUs, avoid oversubscription, increase RAM cache appropriately |
| Wrong-frame-count failure | mixed frame-count movies | enable skip wrong frame count or split datasets |
| Half-set contamination suspicion | repeated RBMC/refinement/re-extraction lost `alignments3D/split` | audit split preservation; v4.5+ defaults help, older branches need care |

---

## Version-aware notes

- **v4.0:** Global CTF defaults changed: third-order Tilt/Trefoil fit by default; fourth-order Spherical Aberration/Tetrafoil not fit by default.
- **v4.4:** RBMC introduced; Patch Motion can accept empirical dose weights from RBMC; float16 output added for motion/extraction contexts.
- **v4.5:** RBMC stability improved; refinements preserve input half-set split by default, reducing RBMC→refinement contamination risk; cFSC summary plots emitted every refinement iteration.
- **v5.0:** Local CTF Refinement adds/defaults joint defocus + per-particle-scale optimization; Patch Motion/RBMC gain hot-pixel threshold; RBMC exposure count display fixed; new CLI/version behavior affects automation.

See `version_caveats.md` for broader upgrade/compatibility issues.

---

## Advisor defaults

If asked “Should I run CTF refinement / RBMC?”:

1. Check whether the consensus map is already good. If not, fix cleanup/refinement first.
2. Check whether raw movies exist and are linked. If not, RBMC is unavailable.
3. Run Global/Local CTF as **test branches**, not irreversible replacements.
4. Inspect fit diagnostics before trusting outputs.
5. Validate with matched reconstruction/refinement.
6. For RBMC, let auto hyperparameter search run first; only override priors after inspecting bad dose weights/trajectories.
7. Preserve half-set splits through all late-stage loops.
8. If no matched improvement, skip the correction and keep the simpler branch.

---

## Sources consulted

This reference is original synthesized workflow guidance prepared from public cryoSPARC guide pages, public release notes, public forum reports, public tutorials/webinars, relevant papers, and public `cryosparc-tools` documentation/API material. Raw upstream documents, transcripts, forum posts, screenshots, and datasets are not bundled here. For authoritative and current details, consult the official cryoSPARC documentation, release notes, discussion forum, and upstream project documentation.
