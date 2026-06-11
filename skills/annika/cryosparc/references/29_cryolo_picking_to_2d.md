# Topic 29 — crYOLO general-model picking → cryoSPARC extract / 2D

## Scope

A **workflow** (not just a format bridge): pick particles with **SPHIRE-crYOLO's
general model** on motion-corrected, CTF-estimated micrographs that already live in a
cryoSPARC project, inject the picks back into cryoSPARC through a **cryosparc-tools
External Job**, run **Extract from Micrographs** and **2D Classification**, and
**optimize the 2D** when classes are weak — all without ever leaving cryoSPARC's
metadata model (native micrograph↔particle linkage, per-particle CTF from the patch CTF
model). The defining trick: crYOLO runs entirely *outside* cryoSPARC and its picks land
as fractional centres carried by the External Job's `location/*` slots, so no particle
stack is re-imported and downstream extraction refreshes CTF natively.

This page owns the *end-to-end recipe, the parameter rationale (box sizing, threshold,
2D optimization), the External-Job injection contract, the localization-verification
logic, and the decision of when crYOLO general-model picking beats Blob / Template /
Topaz.* It builds on:
- `04_picking.md` — picker choice (Blob / Template / Topaz / Filament / Manual) and the standard picking workflow this slots into.
- `05_extraction_2d.md` — Extract box size, Fourier crop / Nyquist, and the first-2D knobs reused here.
- `13_cryosparc_tools_api.md` — connection mechanics, the create→connect→queue→wait lifecycle, output-group / slot I/O.
- `23_external_jobs.md` — the External-Job bridge: `create_external_job`, `add_input`/`add_output`, `alloc_output`/`save_output`, provenance, the crYOLO example, and the validation-before-trust discipline.
- crYOLO skill — the crYOLO-side binaries and formats, by leg: `11_cryosparc_picking_workflow.md` (filter-matched general models, box sizing, CBOX re-threshold, config generation, and the pointer back to this bundle), `03_cli_reference.md` (`cryolo_gui.py config`, `cryolo_predict.py`), `04_data_model_and_formats.md` (CBOX/STAR/EMAN layout), `05_core_workflows.md` (general-model prediction), `06_interoperability.md` (what crYOLO emits for cryoSPARC/RELION + the y-flip caution).

**Executable companion:** `scripts/cryolo_pick/` (config-driven, portable). See its
`README.md`. This page is the brain; that bundle is the hands. Everything below was
**executed and verified live** on cryoSPARC v5.0.4 / cryosparc-tools 5.0.3 and
crYOLO 1.9.9.

---

## 1. When to do this (and when not to)

### Use crYOLO general-model picking when [verified decision surface, from `04_picking.md`]
- You have **no 2D templates yet** and have **never seen the sample**, but the particle
  is reasonably well-defined — crYOLO's pre-trained general model is a strong
  **template-free, training-free** alternative to Blob Picker.
- The field is **heterogeneous / low-contrast** where Blob Picker over-picks Gaussian
  contaminants (gold, ice, micelles); the general model is often cleaner with no tuning.
- You want a picker that runs in **seconds on a GPU** and feeds straight into a native
  cryoSPARC extract → 2D cleanup loop.

### Prefer a different picker when [verified, cross-ref `04_picking.md`]
| Situation | Go to |
|---|---|
| Never seen the sample, just want *something* into 2D fast, fully inside cryoSPARC | **Blob Picker** (+ Blob Picker Tuner) → `04_picking.md` |
| You already have **good 2D classes** or a known map | **Template Picker** (Create Templates from Select-2D) → `04_picking.md` |
| You already have a **clean labeled seed** of hundreds–thousands of particles | **Topaz Train/Extract** (often beats blob/template once seeded) → `04_picking.md` |
| Filaments / amyloid / helical assemblies | **Filament Tracer** → `04_picking.md` |
| Calibration / ground-truth / hard cases only | **Manual Picker** → `04_picking.md` |

crYOLO's general model is the **template-free entry point** that doesn't degenerate on
contaminant-rich fields the way Blob Picker can, and needs no clean seed the way Topaz
does. Once it has produced a clean 2D selection, the normal `04_picking.md` cleanup loop
applies: generate templates from the kept classes and switch to Template Picker, or train
Topaz on the cleaned set. crYOLO is the first leg, not the whole pipeline.

A licensing note that shapes the workflow: crYOLO and its general-model weights are
**user-supplied** — never download model weights as part of this skill (licensing).
The `.h5` general model is an input, like a reference volume.

---

## 2. The pipeline

```
cryoSPARC exposures  (motion-corrected + CTF-estimated: Patch Motion → Patch CTF,
   │                  optionally Curate Exposures / an exposure_sets split)
   │  load_output(<exposures group>, slots=[micrograph_blob, ctf, mscope_params])
   │  symlink chosen .mrc into one input dir            (crYOLO -i takes a folder)
   ▼
crYOLO config  (cryolo_gui.py config out.json BOX --filter LOWPASS --low_pass_cutoff 0.1)
   │  cryolo_predict.py -c cfg -w MODEL.h5 -i mics/ -o out/ -g 0 -t 0.3 --otf
   ▼
out/CBOX/*.cbox  (ALL detections + confidence — the re-thresholdable master)
   │  re-threshold CBOX at target confidence  →  particle centres (corner + box/2)
   │  fractional coords: center_x_frac = cx/NX, center_y_frac = cy/NY
   ▼
cryosparc-tools External Job  (create_external_job → add_input exposure → connect →
   │                            add_output particle [NO passthrough] → alloc → save)
   ▼
J_picks.picked_particles  (location/* slots; micrograph↔particle link via micrograph_uid)
   │  extract_micrographs_multi  (box_size_pix, bin_size_pix, output_f16)
   ▼
J_extract.particles  (per-particle CTF refreshed natively from the patch CTF model)
   │  VERIFY localization (Y-flip check: average blob, not std ratio) — gate
   ▼
class_2D_new  (class2D_K; optimize with window_outer_A + min_res_align if classes weak)
   ▼
2D class averages  →  Select 2D  →  normal 04_picking.md cleanup loop
```

Each leg's *why* [all legs verified live]:

| Leg | Why it's done this way |
|---|---|
| load exposures + symlink mics | crYOLO reads the dose-weighted motion-corrected `.mrc`; `-i` takes a folder, so symlink the chosen mics into one dir. Pull `micrograph_blob/path`, `/shape` (`[NY,NX]`), `/psize_A`, and `mscope_params/exp_group_id` off the exposures group. **[verified]** |
| config box = particle / pixel | box (px) ≈ particle **longest dimension / pixel_size**; it lands in `model.anchors=[box,box]`. **[verified: ~110 Å / 0.656 Å·px⁻¹ ≈ 168 px]** |
| `--filter LOWPASS` + matched model | the 2020 PhosaurusNet general models are **filter-specific**: `LOWPASS_gmodel_*` ↔ `--filter LOWPASS`; `JANNI_gmodel_*` ↔ `--filter JANNI` (+ JANNI denoise model). **Match model to filter** or picking degrades. **[verified]** |
| predict `-t 0.3 --otf` | CBOX holds **every** detection with confidence, so a low predict threshold is fine — you re-threshold from CBOX later with no GPU re-run. `--otf` is silently ignored under `--filter NONE`. **[verified]** |
| re-threshold CBOX (no GPU re-run) | filtering CBOX at a new confidence is **mathematically identical** to re-running `cryolo_predict -t`; use it to hit a target particles/image cheaply. **[verified]** |
| External Job inject **without passthrough** | a `particle` output **cannot** passthrough an `exposure` input — cryoSPARC raises APIError 422 (see §4). The micrograph↔particle link rides on `location/micrograph_uid` instead. **[verified bug + fix]** |
| `extract_micrographs_multi` | refreshes **per-particle CTF** from the patch CTF model and writes the actual stack; mandatory for any non-cryoSPARC pick source (`05_extraction_2d.md`). **[verified]** |
| Y-flip verify gate | external picks are the classic place a coordinate-origin / y-flip mistake hides; the **average blob** catches it before you waste a full 2D run (§6). **[verified]** |
| 2D optimize (mask + high-pass) | a small/low-contrast particle with a background ring needs a tighter circular mask + alignment high-pass so ice/background doesn't drive alignment (§7). **[verified to help]** |

---

## 3. crYOLO-side parameters and the threshold→particles-per-image trick

The crYOLO commands themselves live in the crYOLO skill (`11_cryosparc_picking_workflow.md`,
`03_cli_reference.md`); this section states only the parameter *rationale* that the
cryoSPARC side depends on.

**Box size for the config.** The trailing positional of `cryolo_gui.py config` is the box
size in pixels, which crYOLO writes to `model.anchors=[box,box]`. Set it to the particle's
**longest dimension divided by the micrograph pixel size**. The config command verified this
session: `cryolo_gui.py config <out.json> <BOX> --filter LOWPASS --low_pass_cutoff 0.1`
(PhosaurusNet, input_size 1024, norm STANDARD, max_box_per_image 700). **[verified, crYOLO
1.9.9]** This crYOLO box drives *detection only* — it is **not** the cryoSPARC extraction
box (see §5; they are sized for different purposes).

**CBOX vs STAR.** A single prediction writes both `STAR/*.star` (thresholded particle
**centres**, `_rlnCoordinateX/Y`) and `CBOX/*.cbox` (**ALL** detections, including
below-threshold, with confidence + estimated size). **Inject from CBOX, not STAR**, because
CBOX is the re-thresholdable master. **[verified]**

**CBOX geometry.** `.cbox` v1.0 columns are `CoordinateX CoordinateY CoordinateZ Width
Height Depth EstWidth EstHeight Confidence NumBoxes Angle`. `CoordinateX/Y` is the box
**lower-left corner**; `Width=Height=box`. So the **particle centre = corner + box/2**.
Confidence is column 9 (0-indexed 8). **[verified: corner 3471.9 + 84 = 3555.9 = the STAR
centre.]** The injector reads columns 0,1 (corner), 3,4 (w,h), 8 (conf) and emits
`cx = x + w/2`, `cy = y + h/2`.

**The re-threshold trick (threshold → particles-per-image).** Because CBOX carries every
detection with its confidence, **filtering CBOX at a new confidence is mathematically
identical to re-running `cryolo_predict -t` at that threshold** — no GPU re-run needed.
Use it to dial in a target particles-per-image: pick a low predict threshold once, then
sweep the confidence cutoff on CBOX until the per-image median matches what you expect.
Verified per-image medians on this dataset: **thr 0.30 → 9/img (18,020 total); 0.20 →
19/img (34,464); 0.18 → 22/img (39,417)**. **[verified]** Tune one knob — the confidence
cutoff — and read the particle count back, exactly the "one thing per branch" discipline.

**Fractional coords for cryoSPARC.** `center_x_frac = cx / NX`, `center_y_frac = cy / NY`,
where `NX = micrograph_blob/shape[1]`, `NY = micrograph_blob/shape[0]` (shape is `[NY,NX]`).
**[verified]**

---

## 4. Injecting picks → cryoSPARC External Job (the verified contract)

`cryosparc-tools` v5 External Job, driven by one JSON config. The verified shape
[every line executed live]:

```python
job = project.create_external_job(workspace, title="crYOLO picks ...")
job.add_input("exposure", name="input_micrographs", min=1,
              slots=["micrograph_blob", "ctf", "mscope_params"])
job.connect("input_micrographs", SOURCE_JOB, SOURCE_OUTPUT)
job.add_output("particle", name="picked_particles", slots=["location"])   # NO passthrough
out = job.alloc_output("picked_particles", N)
out['location/micrograph_uid']   = u8    # = exposure uid for each pick
out['location/exp_group_id']     = u4
out['location/micrograph_path']  = object  # the micrograph_blob/path string
out['location/micrograph_shape'] = u4 [NY, NX]
out['location/center_x_frac']    = f4
out['location/center_y_frac']    = f4
with job.run():
    job.save_output("picked_particles", out)
```

### The verified passthrough-422 bug + fix [VERIFIED]

Adding the particle output with `passthrough="input_micrographs"` **fails**. cryoSPARC
returns:

> **APIError 422 "Invalid External Job Spec … specified passthrough input
> input_micrographs does not match output type particle"**

A `particle` output **cannot** passthrough an `exposure` input — the passthrough mechanism
requires the input and output to be the same data type. **The fix is to omit passthrough
entirely.** The micrograph↔particle linkage is carried by `location/micrograph_uid`
(= the exposure `uid` for each pick), and **Extract from Micrographs pulls the
per-particle CTF from the `micrographs` input it is independently connected to** — so no
CTF passthrough is needed at the pick stage. This is the single most important contract on
this page: **inject `location/*` only, no passthrough.** (General External-Job mechanics
and the v5.0 lifecycle hardening — clear → start → save → stop, `slots=[{"name":…}]` —
are in `23_external_jobs.md`; the passthrough-422 specifics are unique to this
exposure-in / particle-out shape.)

### Slot details [verified]
- `add_input("exposure", …, slots=["micrograph_blob","ctf","mscope_params"])` — the
  `ctf` slot is connected so a downstream extract can resolve CTF through the
  *micrographs* input; the **particle** output only declares `location`.
- `out['location/micrograph_path']` is the `object`-dtype `micrograph_blob/path`
  (relative to the project dir); `out['location/micrograph_shape']` is `[NY,NX]` as `u4`.
- Match each pick row's `micrograph_uid`/`exp_group_id`/`shape`/`path` to the exposure it
  came from (keyed on micrograph basename minus `.mrc` ↔ CBOX file stem in the injector).

---

## 5. Box sizing — crYOLO box vs cryoSPARC extract box (two different boxes)

These are **distinct** and sized for **different jobs** — do not reuse one for the other.

| Box | Set where | Rule | Verified value this session |
|---|---|---|---|
| **crYOLO detection box** | `cryolo_gui.py config … <BOX>` → `model.anchors` | ≈ particle **longest dim / pixel_size** (tight on the particle, for detection) | ~110 Å / 0.656 Å·px⁻¹ ≈ **168 px** |
| **cryoSPARC extract box** | `box_size_pix` on `extract_micrographs_multi` | ≈ **1.5–2× particle longest dim**, padded to capture delocalized CTF, **FFT-friendly** size (`05_extraction_2d.md`) | **320 px** (≈ 210 Å) |
| **cryoSPARC Fourier-crop box** | `bin_size_pix` (Fourier crop output box) | crop to a working pixel size; **1.5–2 Å/px for small/low-contrast** particles so junk stays discriminable (`05_extraction_2d.md`) | **128 px** → 1.64 Å/px |

The extract step (verified shape) [every param name verified against the live job]:

```python
ex = project.create_job(workspace, "extract_micrographs_multi",
       connections={"micrographs": (SOURCE_JOB, SOURCE_OUTPUT),
                    "particles":   (PICKS_JOB, "picked_particles")})
ex.set_param("box_size_pix", BOX_EXTRACT)   # ~1.5–2× particle longest dim, FFT-friendly
ex.set_param("bin_size_pix", BOX_CROP)      # Fourier-crop output box → working px size
ex.set_param("output_f16", True)            # 16-bit float (v4.4+), safe, halves disk
ex.queue(lane=LANE)
```

**Verified param names** (`extract_micrographs_multi`): `box_size_pix`, `bin_size_pix`,
`output_f16`, `do_recenter` (default `False`), `recenter_using_shifts`, `recenter_key`,
`scale_const_override`. **Recentering is correctly OFF for external picks** — there are no
prior 2D/3D shifts to recenter against, and leaving it on would let a strong off-target
feature walk the box off the particle (`05_extraction_2d.md`). **[verified]**

**Edge-clipping is silent.** Particles whose box would clip the micrograph border are
dropped during extraction without error; the job log reports the count. **[verified:
18,020 picks → 17,630 extracted.]** A large drop means the box is too big for the field of
view or the picker put too many particles near the border (`05_extraction_2d.md`).

Job-type names [verified]: Extract GPU = `extract_micrographs_multi`; Extract CPU =
`extract_micrographs_cpu_parallel`. Extract inputs are `micrographs` and `particles`.

---

## 6. Verifying localization — the Y-flip check (mandatory gate before 2D)

External picks are the classic place a coordinate-origin / y-flip mistake hides
(`06_interoperability.md` flags this as a verify-on-import caution). **Run this gate
before trusting the batch into a full 2D run.**

Sample ~100 extracted particles (`load_output("particles")`; read `blob/path` + `blob/idx`
with `cryosparc.mrc.read`), compute the per-pixel **average** and **std** across the stack.

- **The AVERAGE is the reliable test. [verified]** Correctly-centred particles produce a
  faint **centred blob** of coherent density in the average; a Y-flipped extraction puts
  every box on mirrored background, so the average is **flat** (no centred blob). This
  session showed a centred blob → no flip, and the real 2D classes later confirmed it.
- **The centre/edge std ratio is a WEAK discriminator. [verified caveat]** For small,
  low-contrast particles it can read ≈ 1.0 **even when localization is correct** (this
  session: **0.997 ≈ 1.0** despite correct centring). **Do not rely on the std ratio
  alone** — trust the average blob and the 2D class averages. Quote both numbers when
  reporting: a flat average *and* ratio ≈ 1.0 together suggest a flip; a centred-blob
  average with ratio ≈ 1.0 is fine.
- **If flipped:** set `center_y_frac = 1 - cy/NY` in the injector, re-inject, re-extract,
  re-verify. **[verified fix path]**

**Rendering note.** Matplotlib is **not** in the cryosparc-tools env but **is** in the
crYOLO conda env (3.4.3). Two-step pattern [verified]: the cryosparc-tools script dumps the
sampled `average`/`std` arrays to `.npy`; a montage script run **in the crYOLO env** renders
the PNG. (`scripts/cryolo_pick/make_montage.py` is that crYOLO-env renderer.)

---

## 7. 2D classification and the small/low-contrast optimization

The 2D job (verified shape) [param names verified against the live job]:

```python
cl = project.create_job(workspace, "class_2D_new",
       connections={"particles": (EXTRACT_JOB, "particles")})
cl.set_param("class2D_K", 50)
cl.queue(lane=LANE)
```

**Verified 2D param names** (`class_2D_new`): `class2D_K`, `class2D_max_res`,
`class2D_max_res_align`, `class2D_min_res_align`, `class2D_window`,
`class2D_window_outer_A`, `class2D_window_inner_A`, `class2D_recenter`,
`class2D_sigma_init_factor`, `class2D_remove_duplicate_particles`, `class2D_min_dist_A`,
`class2D_force_max`. **[verified]** Job-type: `class_2D_new` (current), `class_2D`
(legacy); input group is `particles`.

### The optimization (verified to help) [VERIFIED]

For a **small / low-contrast particle with a prominent background ring**, two knobs — both
targeting background — form a coherent pair:

1. **Tighter circular mask:** `class2D_window_outer_A ≈ particle_longest + ~30 Å`
   (this session **150 Å**). Removes the background ring from the masked region so it
   can't dominate the class average.
2. **Alignment high-pass:** `class2D_min_res_align ≈ 40–60 Å` (this session **50 Å**).
   Stops large low-frequency background (ice halos, neighbouring particles) from driving
   alignment — the same `40–60 Å` high-pass `05_extraction_2d.md` recommends for
   background-dominated alignment.

**Verified effect:** classes reaching < 14 Å went from **17/50 → 25/50**, and the
background ring was removed. **[verified]** These two are a deliberate pair (both attack
background); change knobs deliberately and one concept at a time — do not also bump
`class2D_K`, resolution caps, and uncertainty in the same run, or you cannot attribute the
improvement.

### Inspecting results [verified]
- `class_averages` output carries `blob/res_A` per class (per-class est. resolution).
- Per-class particle counts = `np.bincount(particles['alignments2D/class'])`.
- Then hand off to **Select 2D Classes** and the normal `04_picking.md` / `05_extraction_2d.md`
  cleanup loop (build templates → Template Picker, or seed Topaz).

### The job.json status-lag gotcha [VERIFIED]
The on-disk `job.json` `status` field **lags actual completion by a few seconds.** A single
`job.json` read can say "running" when the job has finished. **Trust the job log
("main process now complete") or the events stream, not one `job.json` read** — this is the
same "verify status, not absence of exceptions; refresh the job object after structural
changes" rule from `13_cryosparc_tools_api.md` §4, specialized to the on-disk file.

---

## 8. Runbook / checklist

Drives the `scripts/cryolo_pick/cryolo_pick.py` bundle (subcommands
`inspect|config|predict|threshold|inject|extract|verify|class2d|dumpclasses`). One JSON config supplies every
site/dataset value; credentials come from `CRYOSPARC_EMAIL`/`CRYOSPARC_PASSWORD` in the
environment only; real GPU jobs are gated behind `--confirm` **and** a lane.

Prepare (no compute):
- [ ] `inspect` — connect read-only; print the source exposures group, `micrograph_blob`
      `shape`/`psize_A`, and pick counts. Confirm the source is **motion-corrected + CTF-estimated**.
- [ ] `config` — write the crYOLO config with `BOX ≈ particle_longest / pixel_size`,
      `--filter LOWPASS`; confirm the supplied `.h5` **matches the filter** (LOWPASS model ↔ LOWPASS filter).
- [ ] `predict` — run `cryolo_predict.py` in the crYOLO conda env on a GPU, low `-t` (e.g. 0.3), `--otf`.
      Confirm `out/CBOX/` populated.

Inject + extract (compute gated):
- [ ] `inject` — re-threshold CBOX to the target particles/image; build the External Job
      with `add_output("particle", slots=["location"])` and **NO passthrough**;
      `save_output`. Confirm matched-vs-missing CBOX count is sane.
- [ ] `extract --confirm --lane <lane>` — `extract_micrographs_multi`, `box_size_pix` (FFT-friendly,
      ~1.5–2× particle), `bin_size_pix` (working px), `output_f16`, recenter OFF. Note the
      edge-clip drop count from the job log.

Verify + classify (gate, then compute):
- [ ] `verify` — sample ~100 particles; dump `.npy`; render the average via the crYOLO-env
      montage. **Average must show a centred blob.** Treat the std ratio as a weak signal only.
      If flat/flipped → set `center_y_frac = 1 - cy/NY`, re-inject, re-extract, re-verify.
- [ ] `class2d --confirm --lane <lane>` — `class_2D_new`, `class2D_K` ~50. If classes are weak on
      a small/low-contrast particle, add `class2D_window_outer_A` and `class2D_min_res_align`
      (the §7 pair) — and nothing else in the same run.
- [ ] Read `class_averages.blob/res_A` and `np.bincount(alignments2D/class)`; **trust the job
      log / events, not a single `job.json` status read** (§7 gotcha). Then Select 2D and iterate.

Each subcommand is run individually in the order above; the GPU steps still require
`--confirm` + a lane. Dry-run / build-only by default.

---

## 9. Failure modes

| Symptom | Layer | First check / fix |
|---|---|---|
| `APIError 422 … passthrough input input_micrographs does not match output type particle` | External-Job inject | You set `passthrough=` on the particle output. **Omit passthrough**; carry the link via `location/micrograph_uid` (§4). **[verified]** |
| Picks land but 2D averages are flat / off-centre, std ratio ≈ 1.0 | localization (y-flip) | Render the **average** (the std ratio is unreliable for small particles, §6). If flat/mirrored → `center_y_frac = 1 - cy/NY`, re-inject, re-extract. |
| Far fewer extracted than injected | extract edge-clip | Box too large for the field of view, or too many picks near the border — extraction drops edge-clipped particles **silently** (`05_extraction_2d.md`). Reduce `box_size_pix` or tighten picks. |
| Way too many / too few picks per image | crYOLO threshold | Re-threshold **from CBOX** (no GPU re-run) to the target particles/image (§3). Don't re-run `cryolo_predict`. |
| Picking quality poor despite a sane box | crYOLO model/filter mismatch | LOWPASS model must run with `--filter LOWPASS`, JANNI model with `--filter JANNI` (+ denoise model). Match model to filter (`11_cryosparc_picking_workflow.md`). |
| `--otf` had no effect | crYOLO filter | `--otf` is silently ignored under `--filter NONE`; use it with `--filter LOWPASS`/`JANNI` (§2). |
| 2D classes dominated by a background ring; few high-res classes | 2D background | Apply the §7 pair: `class2D_window_outer_A` tight + `class2D_min_res_align` 40–60 Å. Change only these two. |
| Extract `AssertionError: particles.blob … not connected` when launching 2D | wiring | Particles were connected but never extracted; run `extract_micrographs_multi` first (`05_extraction_2d.md`). |
| `set_param` no-ops / "build error" | tools / param name | Confirm the exact param code name from the GUI Inputs tab; job must still be `building` (`13_cryosparc_tools_api.md`). |
| Job looks "running" after it finished | status lag | `job.json` `status` lags a few seconds; trust the job log / events stream (§7). |
| External Job stuck `running` after the script exits | External-Job lifecycle | Driver crashed before `save`/finalize; `job.clear()` then re-run (`23_external_jobs.md`). |
| `cryosparc-tools` schema/type errors after a cryoSPARC update | version drift | Pin tools to the cryoSPARC minor version; re-test the driver (`13_cryosparc_tools_api.md`, `23_external_jobs.md`). |
| Matplotlib import fails in the inject/verify script | env | Matplotlib is **not** in the cryosparc-tools env; render the montage in the crYOLO conda env from the dumped `.npy` (§6). |

---

## 10. Worked example (fixture) [generic values only — no secrets/IDs]

A NeCEN-style dataset in a cryoSPARC project (v5.0.4), source = an `exposure_sets`
**`split_0` of 500 micrographs** (motion-corrected + CTF-estimated). Particle ~**110 Å**
at **0.656 Å/px** → crYOLO box **168 px**; config `--filter LOWPASS --low_pass_cutoff 0.1`
with the user-supplied `LOWPASS_gmodel_*.h5`. GPU prediction (RTX-class GPU) was **~67 s
for 500 mics**. Re-thresholding CBOX: thr 0.30 → 9/img (**18,020** picks); 0.20 → 19/img;
0.18 → 22/img. Injected from CBOX (centre = corner + box/2) into an External Job with
`location/*` slots and **no passthrough** (the 422 fix). Extract `box_size_pix=320`
(≈ 210 Å) → `bin_size_pix=128` (1.64 Å/px), `output_f16`, recenter OFF → **17,630**
extracted (390 edge-clipped, dropped silently). Y-flip check: centred **average blob** →
no flip (std ratio 0.997, ignored as weak). 2D `class_2D_new`, `class2D_K=50`. Optimization
for the small low-contrast particle: `class2D_window_outer_A=150`,
`class2D_min_res_align=50` → classes < 14 Å went **17/50 → 25/50** and the background ring
was removed. The original (hard-coded) session scripts are the un-generalized form of the
`scripts/cryolo_pick/` bundle; this page is their generalized brain.

---

## 11. Cross-links

cryoSPARC skill:
- `04_picking.md` — picker decision surface (Blob/Template/Topaz/Filament/Manual) and the standard picking + cleanup loop crYOLO feeds into.
- `05_extraction_2d.md` — Extract box size, Fourier crop / Nyquist, recentering, and first-2D knobs (`min_res_align` high-pass, mask) reused in §5/§7.
- `13_cryosparc_tools_api.md` — connection, the create→connect→queue→wait lifecycle, output-group / slot I/O, "verify status not exceptions", refresh-after-structural-change.
- `23_external_jobs.md` — the External-Job bridge: `create_external_job`/`add_input`/`add_output`/`alloc_output`/`save_output`, v5.0 lifecycle (clear→start→save→stop), provenance, the canonical crYOLO example, validate-before-trust.
- `21_gpu_lane_queue.md` — lanes/queue for the `--confirm` extract / 2D steps.

crYOLO skill:
- `11_cryosparc_picking_workflow.md` — **the crYOLO-side companion** to this page: filter-matched general models, box sizing, CBOX re-threshold, config generation, and the pointer back to this bundle.
- `03_cli_reference.md` — `cryolo_gui.py config`, `cryolo_predict.py` flags.
- `04_data_model_and_formats.md` — CBOX / STAR / EMAN column layout.
- `05_core_workflows.md` — general-model prediction workflow.
- `06_interoperability.md` — what crYOLO writes for cryoSPARC/RELION + the y-flip verify-on-import caution.

Executable companion:
- `scripts/cryolo_pick/README.md` — the config-driven CLI (`inspect|config|predict|threshold|inject|extract|verify|class2d|dumpclasses`) that drives this workflow.

---

## Sources

- Live workflow executed and verified 2026-06-10 against cryoSPARC v5.0.4 / cryosparc-tools 5.0.3 and crYOLO 1.9.9 (the project's `FACTS.md` single-source-of-truth).
- Original (hard-coded) session scripts, generalized into `scripts/cryolo_pick/`: `build_picks.py` (External-Job inject + CBOX re-threshold + 422 fix), `extract.py` (`extract_micrographs_multi` params), `class_2d.py` (`class_2D_new` params + optimization knobs), `verify_extract.py` (average/std Y-flip check), plus the crYOLO config/predict and montage helpers.
- Verified formats: `.cbox` v1.0 column layout (corner + box/2 = centre), exposures `micrograph_blob/{path,shape,psize_A}` + `mscope_params/exp_group_id`, External-Job `location/*` slots, extract edge-clip drop count, 2D `class_averages.blob/res_A`.
- This skill: `04_picking.md`, `05_extraction_2d.md`, `13_cryosparc_tools_api.md`, `23_external_jobs.md`.
- crYOLO skill: `11_cryosparc_picking_workflow.md`, `03_cli_reference.md`, `04_data_model_and_formats.md`, `05_core_workflows.md`, `06_interoperability.md`.
