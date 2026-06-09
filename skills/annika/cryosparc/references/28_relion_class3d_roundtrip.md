# Topic 28 — RELION focused 3D classification ⇄ cryoSPARC round-trip

## Scope

A **workflow** (not just a format bridge): take a cryoSPARC **local/focused refinement**
of a small region inside a large particle, run a **focused, no-align RELION 3D
classification** of that region to resolve discrete conformational states, then split
the particles by class and **re-refine each class back in cryoSPARC** — both a local
refinement of the region and (optionally) a whole-molecule Non-Uniform refinement.
The defining trick: class labels are mapped back onto the **original cryoSPARC
particles**, so native poses + CTF are preserved and no particle stack is re-imported.

This page owns the *end-to-end recipe, the parameter rationale, the validation logic,
and the decision of when this round-trip beats staying in one package.* It builds on:
- `27_relion_interop.md` — what metadata crosses the `.cs`⇄`.star` bridge and what degrades.
- `08_classification_3d.md` — cryoSPARC-native 3D classification (the alternative).
- `09_local_refinement.md` — local/focused refinement, masks, particle subtraction.
- relion skill — the RELION-side binaries, by leg: `16_interop_cryosparc.md` (csparc2star `.cs`→`.star` + the `.mrcs` requirement), `03_cli_inventory.md` (`relion_image_handler` downsample), `09_mask_postprocess_localres.md` (`relion_mask_create --width_soft_edge` mask soften), `07_initialmodel_class3d.md` (focused `relion_refine --K --skip_align --tau2_fudge` Class3D + reading class distribution).

**Executable companion:** `scripts/roundtrip/` (config-driven, portable). See its
`README.md`. This page is the brain; that bundle is the hands.

---

## 1. When to do this (and when not to)

### Use this round-trip when
- You have a **confident consensus/local refinement** in cryoSPARC and suspect a small
  region adopts **discrete conformational states** that the consensus averages over.
- You want RELION's **focused 3D classification with alignment held fixed**
  (`--skip_align`, reusing the cryoSPARC poses) — it isolates *occupancy/conformation*
  of the masked region without letting global alignment drift, and lets you push
  `--tau2_fudge` (T) hard to force genuine splits.
- You ultimately want the answer back **in cryoSPARC** (per-class local + NU refine,
  native poses/CTF, GUI lineage).

### Prefer a different path when
| Situation | Go to |
|---|---|
| Continuous motion, not discrete states | 3DVA / 3DFlex → `26_continuous_heterogeneity.md` |
| You're happy staying in cryoSPARC | cryoSPARC 3D Classification (no align) → `08_classification_3d.md` |
| The region is too small / low-contrast to classify at all | particle subtraction first → `09_local_refinement.md` |
| You just need a format conversion, not this workflow | `27_relion_interop.md` |

cryoSPARC's own 3D Classification (v4.4+) can also classify with alignments fixed; the
reason to leave for RELION here is operational preference for RELION's focused-class
behavior and the ability to crank T. If you don't have that preference, the native
route avoids every bridge failure mode in `27_relion_interop.md`.

---

## 2. The pipeline

```
cryoSPARC J_src  (Local Refinement: particles + volume + focus mask)
   │  csparc2star.py  J_src_particles.cs  J_src_passthrough_particles.cs  --boxsize BOX
   ▼
particles.star  (poses + CTF, .mrc stacks, paths relative to CS project root)
   │  relion_prep.py   (.mrcs symlink farm + absolute, location-independent rlnImageName)
   ▼
particles_abs.star
   │  relion_image_handler --new_box / --rescale_angpix   (optional downsample, speed)
   │  relion_mask_create --width_soft_edge 6              (re-soften the hard CS mask)
   ▼
focused RELION Class3D   (relion_refine --skip_align --solvent_mask ... --tau2_fudge T high)
   │  map_relion_classes.py   (rlnClassNumber  →  cryoSPARC uid, via stem+index key)
   ▼
class_assign_uid.npz   (uid, cls)
   │  cs_roundtrip.py  inspect → build → queue → nurefine   (cryosparc-tools)
   ▼
per-class External particle subsets  +  Local Refinement (region)  +  NU Refinement (whole molecule)
```

Each leg's *why*:

| Leg | Why it's done this way |
|---|---|
| `csparc2star --boxsize` | populate `rlnImageSize`; pass the passthrough `.cs` so `rlnMicrographName` etc. merge (`27_relion_interop.md` §3). |
| `.mrcs` farm + abs paths | RELION rejects `.mrc` for stacks; absolute paths make the RELION project relocatable. |
| downsample | the region is small; classify fast at a coarse box, then apply labels to **full-res** originals. |
| re-soften mask | cryoSPARC focus masks are hard 0/1; RELION focused classification needs a cosine edge or it biases. |
| `--skip_align` | reuse the trusted cryoSPARC poses; classify *conformation*, not alignment. |
| high `--tau2_fudge` | low T over-smooths and collapses to one class; high T forces the latent splits to express (see §3). |
| map labels to originals | preserves native poses/CTF and avoids re-importing stacks — the whole point. |

---

## 3. Classification parameters and the two failure modes that matter

Representative validated command (focused, no-align, reuse poses), run from the RELION
project root:

```bash
mpirun -n 3 relion_refine_mpi \
  --i particles_ds128.star --o Class3D_T20/run \
  --ref ref_128.mrc --ini_high 10 --firstiter_cc \
  --ctf --K 5 --tau2_fudge 20 --particle_diameter 250 \
  --skip_align --solvent_mask mask_128_soft.mrc --flatten_solvent --zero_mask \
  --iter 25 --sym C1 --pad 2 --norm --scale \
  --gpu 0 --j 6 --pool 30 --dont_combine_weights_via_disc
```

**Failure mode A — T too low → degenerate collapse.** At a modest classification T
(RELION's default is ≈2–4), a focused no-align run can collapse monotonically into a
single occupied class. In the reference example, **T=8 collapsed** to 0.3 / 98.4 / 0.2 / 1.0 %.
That is *over-smoothing*, not "the data is homogeneous." **Raise T** (the reference example
needed T=20) to force the latent states to separate. T is a means to express splits, not
a free knob — see B.

**Failure mode B — T too high → balanced-but-meaningless classes.** A high T can also
manufacture an even partition of *noise*. So a balanced split is **not** evidence by
itself. **Validate distinctness:** compute pairwise **in-mask map cross-correlation**
between class volumes. Real states are structurally distinct at comparable resolution;
if every pair has CC > ~0.97 the "split" is a noise partition. In the reference example the
kept classes had in-mask CC 0.79–0.92 (none > 0.97) at comparable est. resolution →
real 4-way split. Discard the tiny low-resolution junk class.

Other knobs: `--ini_high 10` (low-pass the reference; the region is small),
`--firstiter_cc` (CC for the first iteration), `--zero_mask`/`--flatten_solvent` with
the soft solvent mask, `--K` = a few more classes than you expect (lets junk separate).

---

## 4. Mapping classes back to cryoSPARC (the durable-uid join)

The class labels must land on the **original** cryoSPARC particles so poses + CTF stay
native. `map_relion_classes.py` joins the RELION `run_itNNN_data.star` back onto the
source job's particles on a key that survives conversion + downsample:

- **RELION side:** `rlnImageName = NNNNNN@/…/<stem>[_ds128].mrcs`. Index is **1-based**;
  `<stem>` is the basename minus the `.mrcs`/`.mrc` extension and the downsample suffix.
- **cryoSPARC side:** each particle has `blob/path` + `blob/idx` (**0-based**) + `uid`.
  Key = `(basename(blob/path) without ext, blob/idx + 1)`.

The join is **order-independent** and **aborts on any unmatched particle** — the
original round-trip required *0 unmatched*. (`--by order` is available only when the
RELION rows are a strict 1:1 order-preserving descendant of the source job.)

Result: `class_assign_uid.npz` with equal-length `uid` (uint64) and `cls` (int32).

---

## 5. Per-class re-refinement in cryoSPARC

`cs_roundtrip.py` (cryosparc-tools), driven by one JSON config:

| Step | What it does | Compute? |
|---|---|---|
| `inspect` | connect read-only; print source job spec; verify uid↔assignment overlap; per-class counts | none |
| `build` | for each kept class: `save_external_result` (particle subset, **passthrough** from the source job → poses/CTF preserved) + `create_job("new_local_refine")` connected to subset + source volume + source mask; params **cloned from the source job** | none (jobs left *building*) |
| `queue` | queue the built Local Refinements to a lane | yes — `--confirm` + lane required |
| `nurefine` | for each class build `nonuniform_refine_new` (whole molecule) against a consensus ref (e.g. the parent refinement) | queues only with `--confirm` + lane |

**Interpretation — pair the two refinements per class:**
- The **local refine** asks: does the *region* resolve better once conformations are
  separated? (it should, if the split is real).
- The **NU refine** asks: does the *whole molecule* adopt a distinct global state per
  region-conformation? If the whole-molecule maps are identical **outside** the region,
  the heterogeneity is local-only; if they diverge, the region-conformation is coupled
  to a global state.
- Large confident classes are your real conformations; small classes (tens of k) may be
  sub-states — judge by whether their refinements hold up, not by the classification %.

---

## 6. Runbook / checklist

Outbound (cryoSPARC → RELION):
- [ ] `csparc2star.py` with the passthrough `.cs` and `--boxsize` = actual box; confirm a populated `data_optics`.
- [ ] `relion_prep.py` → `.mrcs` farm; spot-check that one `rlnImageName` path resolves and opens.
- [ ] (optional) downsample; re-soften the focus mask; rescale the reference to the classification box.

Classify (RELION):
- [ ] focused `relion_refine --skip_align` reusing poses; start T modest, **raise it if it collapses**.
- [ ] at convergence, **validate distinctness** (in-mask pairwise CC < ~0.97 at comparable resolution); discard junk classes.

Map back + re-refine (cryoSPARC):
- [ ] `map_relion_classes.py` → npz; require **0 unmatched**.
- [ ] `cs_roundtrip.py inspect` → counts + 100% uid overlap.
- [ ] `build` (no compute) → review jobs in the GUI.
- [ ] `queue --confirm` (+ `nurefine --confirm`) to a confirmed lane.
- [ ] Compare each class's local-refine and NU-refine maps/FSCs; decide real states vs sub-states.

---

## 7. Failure modes

| Symptom | Layer | First check |
|---|---|---|
| RELION refuses to load: `ObservationModel::getBoxSize` | csparc2star: no box | re-run with `--boxsize` = actual box (`27_relion_interop.md`) |
| `Cannot read … .mrcs … does not exist` | `.mrc` on disk, STAR says `.mrcs` | run `relion_prep.py`; confirm the symlink target exists |
| Class3D collapses to one occupied class | T too low (over-smoothing) | raise `--tau2_fudge` (e.g. 4 → 20); keep `--skip_align` |
| Balanced classes but maps look identical | T forced a noise partition | in-mask pairwise CC; if all > ~0.97, not a real split |
| `map_relion_classes.py` reports unmatched > 0 | wrong `--strip-suffix`, or wrong `source_job` | match the downsample suffix; point at the job csparc2star converted from |
| `cs_roundtrip inspect` overlap < 100% | npz built against a different particle set | re-run the mapper on the correct source job |
| Built Local Refine errors on params | a cloned auto-set param isn't settable | drop it via `local_refine.params_override` (set to default) |
| All per-class NU maps identical outside the region | heterogeneity is local-only (not a bug) | this is a real result — report it as such |

---

## 8. Worked example

This workflow was generalized from a validated production round-trip (cryoSPARC v5.0.4,
RELION 5.0). Source: a Local Refinement of a ~84 Å focus region inside a 262 Å (400 px
@ 0.656 Å/px) particle, 258,326 particles. Focused RELION classification: at T=8 it
collapsed to one occupied class (0.3 / 98.4 / 0.2 / 1.0 %); at **T=20, K=5 it gave a
real 4-way split** (in-mask pairwise CC 0.79–0.92, none > 0.97, at comparable
resolution), with one tiny low-resolution junk class discarded. Class labels mapped back
to the original particles with **0 unmatched**; each kept class then got a per-class
External particle subset → Local Refinement (region) + whole-molecule NU Refinement
against the parent consensus map. The `scripts/roundtrip/` bundle is the generalized,
config-driven form of the scripts that ran that round-trip.

---

## 9. Cross-links

- `27_relion_interop.md` — `.cs`⇄`.star` metadata semantics, csparc2star flags, bridge failure modes.
- `08_classification_3d.md` — cryoSPARC-native 3D classification (the in-package alternative).
- `09_local_refinement.md` — local/focused refinement, focus masks, particle subtraction.
- `26_continuous_heterogeneity.md` — when the motion is continuous, not discrete.
- `13_cryosparc_tools_api.md` — `save_external_result`, `create_job`, `queue`, `load_output`.
- `23_external_jobs.md` — External Jobs as the bridge for externally-computed particle subsets.
- `21_gpu_lane_queue.md` — lanes/queue for the `--confirm` step.
- relion skill, by leg: `16_interop_cryosparc.md` (csparc2star + `.mrcs`), `03_cli_inventory.md` (downsample), `09_mask_postprocess_localres.md` (`relion_mask_create --width_soft_edge` mask soften), `07_initialmodel_class3d.md` (focused Class3D: `--K`/`--tau2_fudge`/`--skip_align`, run_it*_{class,data,model}.star). Use `08_refine3d.md` only for the per-class Refine3D sanity check, not the classification itself.
- `scripts/roundtrip/README.md` — the executable companion.

---

## Sources

- Generalized from a validated production round-trip (cryoSPARC v5.0.4 / RELION 5.0); join key and class distribution verified against the real `run_itNNN_data.star` (`rlnImageName`, `rlnClassNumber`), the csparc2star output STAR, the `.mrcs` symlink farm, and the resulting `uid`/`cls` assignment.
- cryoSPARC skill: `27_relion_interop.md` (bridge metadata semantics), `08_classification_3d.md`, `09_local_refinement.md`, `13_cryosparc_tools_api.md`.
- relion skill: `16_interop_cryosparc.md` (csparc2star), `03_cli_inventory.md`, `07_initialmodel_class3d.md`, `09_mask_postprocess_localres.md` (RELION 5.0 binaries).
