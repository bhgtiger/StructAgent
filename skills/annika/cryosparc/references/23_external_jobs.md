# Topic 23 — External Jobs and Wrapper / Integration Boundaries

## Scope
How CryoSPARC integrates with software that is not part of its native job set: built-in **wrapper jobs** (DeepEMhancer, CTFFIND4, MotionCor2, Gctf, ThreeDFSC) that shell out to a separately-installed third-party binary, and **External Jobs** created via `cryosparc-tools` that let arbitrary Python code (or a third-party command-line tool such as crYOLO) read CryoSPARC inputs, do work outside CryoSPARC, and write results back into the project as first-class result groups. The page focuses on the *boundary* — what crosses it, what does not, what provenance survives the round-trip, and which failure modes are unique to this layer.

What lives elsewhere — do not duplicate:

- Python automation patterns, connection mechanics, workflow templating internals, output-group concepts — `13_cryosparc_tools_api.md`. This page references the External Job API surface by purpose, not by exact signature.
- `cryosparcm` / `cryosparcw` admin surface, log layout, restart and recovery, version disclaimer for exact CLI syntax — `14_cli_admin.md`.
- Storage planning, project directory tree, archive/compact/restore, raw-data symlink lifetime — `24_disk_and_storage.md`. Wrapper / external outputs live in the project tree like any other job; this page only notes where outputs land and how to keep them recoverable.
- Postprocessing interpretation (FSC honesty, sharpening cautions, when *not* to use DeepEMhancer as a scientific map) — `10_postprocessing.md`. This page covers the wrapper *operationally*, not the science.
- Scheduler/lane assignment and SSD-cache behavior visible to wrappers and external jobs — `21_gpu_lane_queue.md`.
- RELION import/export round-trips — `27_relion_interop.md`.
- Exact error strings — `17_error_lookup.md`.

The exact `cryosparc-tools` method names referenced below (`create_external_job`, `connect`, `add_input`, `add_output`, `start`, `stop`, `clear`, `alloc_output`, `save_output`, `load_input`, `load_output`, `subprocess`, etc.) are attested in the local source bundle (`reference/cryosparc-tools/…`). Their signatures evolve across minor releases (v4.x → v5.0 was a breaking change — see `reference/cryosparc-tools/CHANGELOG.md`). **Before scripting against them, confirm the signature against the installed package or `https://tools.cryosparc.com/`.**

---

## 1. Mental model — three flavors of "external"

Most integration questions route faster after naming which of these three is in play.

| Flavor | What it is | Owns the data path | Provenance in CryoSPARC | Examples (source-attested) |
|---|---|---|---|---|
| **Native job** | Built into CryoSPARC; Structura-developed code that runs inside the worker | CryoSPARC reads the project filesystem and writes outputs into `project_dir/Jx/` with full dataset/result-group metadata | Complete — parameters, inputs, outputs, logs, plots all in the job record | Patch Motion, Patch CTF, Ab-Initio, NU Refinement, 3D Classification, Local Refinement, Sharpening Tools |
| **Wrapper job** | A CryoSPARC job whose run-step shells out to a separately-installed third-party binary that the user must license and install | CryoSPARC stages inputs to the wrapped tool, runs it as a subprocess, reads its outputs back, and records them as a normal CryoSPARC output group | Mostly complete — CryoSPARC owns inputs/outputs and the parameter record, but the *binary's* version, weights, and any wrapper shell script are external state that CryoSPARC does **not** capture | DeepEMhancer (post-sharpening), CTFFIND4 (CTF), MotionCor2 (motion, BETA), Gctf (CTF, Legacy), ThreeDFSC (directional FSC, Legacy) |
| **External Job via cryosparc-tools** | A `snowflake`-type job created from Python; user-defined input slots are connected to other jobs, the user runs arbitrary code (often calling a third-party tool), then writes results back into user-defined output result groups | The script owns the bridge between CryoSPARC and the third-party tool; CryoSPARC sees only what the script chooses to materialize | Partial — connection lineage and output result groups are first-class; the *code* that produced them is not stored in the job unless the user logs it as an asset or links a repo | crYOLO via the `cryosparc-tools` example; "Import Image Sets" external job example; any custom picker / classifier / QC bridge |

Where data leaves and returns:

- **Native:** data never leaves the project directory tree the worker can see.
- **Wrapper:** data stays on the worker filesystem; the wrapped binary reads and writes the same paths CryoSPARC reads. Nothing crosses a network boundary unless the wrapped binary itself does it.
- **External Job:** data path is whatever the script chooses. The common safe pattern is "read paths from CryoSPARC, write into `job.dir`, register the new files back as outputs." Anything outside the project tree (a `/tmp` scratch, a cluster scratch path, a remote server) becomes invisible to CryoSPARC archive/compact/restore.

### A note on ModelAngelo (and similar "external integrations seen in the wild")

ModelAngelo is **not** documented as a built-in CryoSPARC wrapper job in the source bundle used to build this skill. If a user describes a "ModelAngelo job in CryoSPARC", it is almost certainly an external integration written against `cryosparc-tools` (read a refined map / mask / particle stack from CryoSPARC, run ModelAngelo locally, register the model file as a job asset), *not* a guaranteed first-party job. The advisor default is to:

1. Validate against the installed CryoSPARC instance's Job Builder list (or `CryoSPARC.print_job_types` / `cs.job_register`) before recommending it as native.
2. Treat it as the External-Job pattern described in §4 if no built-in exists.
3. Never represent ModelAngelo (or any similar map-to-model tool) output as *validated by CryoSPARC* — CryoSPARC has no opinion on its correctness; the user owns map-to-model evaluation.

The same caution applies to any "I saw a CryoSPARC + X integration somewhere" claim: confirm presence, version, and stability tag before treating it as a supported branch.

---

## 2. Wrapper jobs (the source-attested set)

All wrappers share the same install-and-license shape: the third-party tool is installed and licensed **by the user**, outside the CryoSPARC conda environment, and the wrapper job is told the absolute path to the executable (or a wrapper shell script that activates the right environment first).

### 2.1 DeepEMhancer (Postprocessing)

Source: `docs/per_page/processing-data__all-job-types-in-cryosparc__post-processing__job-deepemhancer-wrapper.md`.

| Aspect | Detail |
|---|---|
| Purpose | Deep-learning post-sharpening / masking of a map, primarily for **visualization**. |
| Licensing | CryoSPARC does **not** distribute DeepEMhancer; user must install under DeepEMhancer's Apache 2.0 terms with their own model weights. |
| Install constraint | Must use a **separate** conda environment from the one CryoSPARC bundles — CryoSPARC's bundled conda is destroyed and recreated on update, so anything installed into it can be wiped or break other jobs. |
| Path constraint (master/worker or cluster) | The path to the conda installation must be **identical** on the master and every worker that runs the job. The common solution is a shared filesystem mounted at the same mount point everywhere. |
| Common parameters | `Path to deepEMhancer executable`, `Path to deepEMhancer models`, `Use half maps`, `Normalization mode`. |
| Project-level default | From v4.1+, the executable path can be set as a project-level parameter so new DeepEMhancer jobs autofill it (`reference/release_notes/markdown/v4.1.md`). |
| Inputs | Volume (half maps or full map), optional mask. |
| Outputs | `map_sharp` — a single sharpened volume. |
| Scientific caveat | "Treating a more-sharpened version as evidence of more signal" is the canonical misuse — see `10_postprocessing.md`. The map is for figures, not for FSC claims. |
| Optional wrapper script | A `deepemhancer.sh` that deactivates the CryoSPARC conda env and activates the DeepEMhancer one before `exec deepemhancer "$@"` is the documented workaround when env conflicts surface. The script path must be reachable at the same path from master and worker. |

### 2.2 CTFFIND4 (CTF Estimation)

Source: `docs/per_page/processing-data__all-job-types-in-cryosparc__ctf-estimation__job-ctffind4-wrapper.md`.

- Wraps CTFFIND4 (Rohou & Grigorieff 2015). Janelia license terms reproduced in the doc; user must read and accept.
- Accepts either movies or micrographs (unlike CryoSPARC's native Patch CTF, which is micrograph-only after motion correction).
- **Trap:** when feeding movies, the movies must have been **gain-corrected before import**. CryoSPARC does *not* bake gain correction into movies during import, so movies imported with a separate gain reference will fail in CTFFIND4 — the wrapper does not see the gain ref. Patch CTF avoids this; CTFFIND4 does not.
- Outputs: exposures with CTF estimates, same type (movies or micrographs) as input.
- Next step from movies output: Patch Motion Correction.

### 2.3 MotionCor2 (Motion Correction, BETA)

Source: `docs/per_page/processing-data__all-job-types-in-cryosparc__motion-correction__job-motioncor2-wrapper-beta.md`.

- Wraps MotionCor2 (Zheng 2017). CryoSPARC does not distribute binaries; user must accept the MotionCor2 Non-Commercial Software License Agreement (for-profit users contact David Agard separately).
- BETA-tagged. Treat its outputs as experimental and validate against Patch Motion on a pilot before committing a full dataset.
- Patch X / patch Y is the main user-visible parameter and is **distinct from** Patch Motion Correction's `knots` setting — they are different parameterizations of different algorithms. Do not mechanically translate one to the other.
- Output: motion-corrected micrographs; typically followed by Patch CTF.

### 2.4 Gctf (CTF Estimation, Legacy)

Source: `docs/per_page/processing-data__all-job-types-in-cryosparc__ctf-estimation__job-gctf-wrapper-legacy.md`.

- Legacy. Hidden from the default Job Builder; enable "Show legacy jobs" to find it (`docs/per_page/application-guide__creating-and-running-jobs.md`).
- Wraps Gctf (Zhang 2016). Binaries must be installed at `deps/external/gctf-1.06/bin/` inside the `cryosparc_worker` directory — note the **non-portable** install location that survives only as long as the worker install survives.
- Requires a **CUDA 8** toolkit because public Gctf binaries only support CUDA ≤ 8. The user maintains a separate CUDA 8 toolkit (no root needed, runfile install) and points the wrapper at its `lib64`. v4.5 also fixed a bug where the wrapper failed if `LD_LIBRARY_PATH` was unset (`reference/release_notes/markdown/v4.5.md`).
- Local-refinement of CTF parameters is only worth using when the consensus map is already ≤ ~4 Å.
- Default to native Patch CTF over Gctf for any new project unless there is a specific reason. Reasons to keep Gctf around are basically reproducing a published Gctf-based result.

### 2.5 ThreeDFSC (Postprocessing, Legacy)

Source: `docs/per_page/processing-data__all-job-types-in-cryosparc__post-processing__job-threedfsc-wrapper-legacy.md`.

- Legacy NYSBC/Salk tool for visualizing directional FSCs. MIT license.
- Output is mostly streamlog-based: a histogram of FSCs in the streamlog, and instructions for opening the full ThreeDFSC outputs in Chimera.
- The doc explicitly says full functionality is "not currently implemented in this wrapper".
- For new work, prefer native **Orientation Diagnostics** (cFAR / tFAR / SCF\* / Relative Signal) for anisotropy diagnostics (`10_postprocessing.md`), and only fall back to ThreeDFSC when reproducing prior 3DFSC plots specifically.

### 2.6 Quick wrapper-vs-native heuristics

| Need | Native default | Wrapper exists when… |
|---|---|---|
| Motion correction | Patch Motion Correction | MotionCor2 (BETA) — only if comparing to existing MotionCor2 pipeline or matching a published recipe |
| CTF estimation | Patch CTF | CTFFIND4 — gain-corrected inputs only; Gctf (Legacy) — for matching old recipes |
| Post-sharpening for figures | Sharpening Tools (B-factor) | DeepEMhancer — visualization only, not for resolution claims |
| Directional FSC | Orientation Diagnostics (cFAR / tFAR / SCF\* / Relative Signal) | ThreeDFSC (Legacy) — only when reproducing a 3DFSC plot |
| Picking with a tool not in CryoSPARC | Topaz (native, deep-picking) / Blob / Template / Filament Tracer | crYOLO via External Job; any other picker via the same External-Job bridge |
| Map-to-model | (none native) | ModelAngelo / Phenix / Coot via External Job pattern — validate per-instance |

---

## 3. The External-Job bridge via `cryosparc-tools`

Source: `docs/per_page/processing-data__cryosparc-tools.md`, `reference/cryosparc-tools/docs/guides/jobs.ipynb`, `reference/cryosparc-tools/docs/examples/cryolo.ipynb`, `reference/cryosparc-tools/cryosparc/controllers/job.py`, `reference/cryosparc-tools/cryosparc/tools.py`, `reference/cryosparc-tools/cryosparc/models/external.py`.

### 3.1 What an External Job is

An External Job is a special CryoSPARC job of type `snowflake` whose **inputs and outputs are defined by the user at build time**, not predetermined by a job code path. The script:

1. Connects existing outputs from other jobs as input slots (`particles`, `micrographs`, `volumes`, etc.).
2. Calls into third-party code (often via `job.subprocess(...)` so the tool's stdout/stderr is forwarded into the CryoSPARC event log).
3. Registers new files / datasets back into the CryoSPARC project as named output result groups.
4. Marks the job complete so its outputs are connectable just like any other job's.

This is the bridge that makes "do something outside CryoSPARC and have its results behave like a CryoSPARC job" possible.

### 3.2 The four-step shape

These method names are attested in the source bundle but their signatures move across minor versions. **Confirm against the installed package before scripting.**

| Step | What happens | Source attestation |
|---|---|---|
| **Create** | `project.create_external_job(workspace_uid, title=…)` (or via `workspace.create_external_job`) returns an `ExternalJobController`. | `tools.py`, `controllers/job.py` `ExternalJobController` |
| **Wire inputs / declare outputs** | `job.connect(target_input, source_job_uid, source_output, slots=[…])` connects upstream output groups as named input slots. `job.add_input(type, name, min, max, slots, title, desc)` declares input shapes when you want them empty-then-filled. `job.add_output(type, name, slots)` declares the output result groups the job will produce. | `controllers/job.py` |
| **Start, fill, save, stop** | `job.start()` marks the job running. The script either fills allocated datasets in place (`job.alloc_output(name, alloc=N)` returns a Dataset that the script writes to) or builds a Dataset externally and `job.save_output(name, dset)`. Files written into `job.dir` are visible from the GUI. `job.stop()` marks the job complete. | `controllers/job.py`, `examples/cryolo.ipynb`, `examples/custom-workflow.ipynb` |
| **Inspect from CryoSPARC** | Once `stop()` returns, the External Job behaves like a native job in the GUI: outputs appear in the Outputs tab, connect to downstream jobs, show up in Workflows, get cleared/compacted by data-cleanup, get exported by `cryosparcm` data-management commands. | `application-guide__inspecting-job-data.md`, `24_disk_and_storage.md` |

Note the **v5.0 lifecycle hardening** (`reference/cryosparc-tools/CHANGELOG.md`):

- Inputs and outputs can no longer be added to an external job that is already completed — must call `job.clear()` first to return it to `building`.
- Outputs can no longer be saved to a `building` *or* `completed` job — only between `start()` and `stop()`. Re-running means clear → start → save → stop.
- `CryoSPARC.get_job_specs()` was removed; `CryoSPARC.job_register` replaces it.
- Several model attributes moved from dict-style to dot-style access (`asset['filename']` → `asset.filename`, `lane['name']` → `lane.name`, etc.).
- `slots=[{"prefix": …}]` is deprecated in favor of `slots=[{"name": …}]`.

### 3.3 Dataset / result-group provenance — what survives the round-trip

| Item | Survives | Notes |
|---|---|---|
| Connection lineage (which upstream output flowed into which input) | **Yes** | Visible in Related Jobs and in `job.doc.spec.inputs`. |
| Output result groups (type, slot list, dataset columns) | **Yes** | Defined by `add_output` and the dataset the script writes. Slot definitions must be valid CryoSPARC slot specs (`location`, `pick_stats`, `ctf`, `blob`, etc. — see `controllers/job.py`). |
| Passthrough fields from inputs | **Yes (if declared)** | The script must explicitly route passthrough slots; otherwise downstream jobs may complain about missing fields. |
| The **script** that produced the outputs | **No, unless you save it as an asset** | `job.log(text)`, `job.upload_asset(...)` (where supported) and writing the script into `job.dir` are how you make the *code* part of provenance. Treat this as a discipline, not a guarantee. |
| The **environment** of the external tool (binary version, model weights, conda env, GPU driver) | **No** | This is the largest provenance hole at this boundary — see §5. |
| Image / plot assets attached to the job | **Yes** | Lives in MongoDB GridFS (`job.list_assets()`, `job.download_asset(asset_id, target)`), so they survive backup/restore but not the same as a file on disk; they are *not* in `job.dir`. |

### 3.4 Queueing, lanes, and logs

- An External Job runs **where the Python script runs**, not on a CryoSPARC worker. `cs = CryoSPARC(...)` opens an HTTP session to the master; `job.subprocess(...)` runs locally to the script. This is the opposite of native and wrapper jobs, which dispatch to a worker via SSH or a cluster submission template.
- Therefore: lane / SSD-cache / GPU accounting from `21_gpu_lane_queue.md` does **not** apply by default. The driver host is responsible for its own GPU isolation, scratch, and CPU budget. If you want External-Job work to honor CryoSPARC lanes, you have two patterns: (a) run the driver script *on* a worker host that has the right environment, or (b) submit the driver itself to the cluster as a non-CryoSPARC job that happens to call `cryosparc-tools`.
- Logs: `job.subprocess(...)` forwards stdout/stderr into the CryoSPARC event log, so the runtime trail is in the job's Event Log tab. The Python traceback for any tools error appears in `cryosparcm log command_vis` (`17_error_lookup.md`).
- Heartbeat: External Jobs do *not* report through the same worker heartbeat as native jobs. A driver that crashes in the middle of an External Job leaves the job in a half-completed state until `job.clear()` is called.

### 3.5 Workflow templating with External Jobs

Workflows (`docs/per_page/application-guide__workflows.md`, `13_cryosparc_tools_api.md`) can contain External Jobs as part of a saved pipeline. The pattern is:

- Build the pipeline in the GUI with the External Job as a node (its inputs already wired to upstream outputs in the workspace).
- Save the workflow JSON.
- The "Queue on Apply" toggle queues the deterministic native jobs; the External Job still requires the driver script to attach and run when the workflow lands in a new workspace. This is the half of the workflow that is **not** click-to-apply, and it must be documented in the workflow's description.

The GPCR automation workflow (`docs/per_page/processing-data__automated-workflows.md`) is the source-attested example of an end-to-end workflow that mixes locked parameters, flagged dataset-specific knobs (extraction box size, blob diameter, exposure-group regex, reference paths), and a tools-side driver. Use it as the canonical reference when planning a multi-dataset external workflow.

### 3.6 Re-import / export — when External-Job outputs need to leave and come back

Three common patterns:

| Pattern | When | How |
|---|---|---|
| **External → CryoSPARC** | A non-CryoSPARC tool produced particles, picks, or volumes that should appear as a CryoSPARC result group. | External Job in which `job.add_output` declares the shape and the script writes the dataset and any `*.mrc` files into `job.dir`. |
| **CryoSPARC → External → CryoSPARC** | A CryoSPARC dataset needs to be modified outside (e.g., custom QC, custom classifier) and reinserted. | External Job that `connect`s the upstream output, loads the dataset (`job.load_input`), mutates the metadata in Python or via a third-party tool, then `add_output`s a modified dataset that downstream jobs consume. |
| **CryoSPARC → other package** | Output is needed in a different ecosystem (RELION, ChimeraX, Phenix). | This is a *download/export*, not an External Job; see `24_disk_and_storage.md` for export commands and `27_relion_interop.md` for RELION round-trips. Do not wrap a download-only operation in an External Job. |

The crYOLO example in `reference/cryosparc-tools/docs/examples/cryolo.ipynb` is the canonical CryoSPARC → External → CryoSPARC walkthrough.

---

## 4. Integration boundaries — what makes this layer fragile

This is the layer where most "it worked yesterday" problems live. Treat every item below as a state that lives **outside CryoSPARC's database** and therefore is your responsibility to track.

### 4.1 Environment and software dependencies

- **Never install third-party tools into CryoSPARC's bundled conda env.** That env is destroyed and recreated on `cryosparcm update`, and packages added to it can break other jobs (the DeepEMhancer install instructions call this out explicitly). For wrappers: separate conda env, point the wrapper at its absolute executable path. For External Jobs: the driver runs *outside* CryoSPARC entirely.
- **Conda path identity across master and workers** is a hard requirement for wrapper jobs in distributed setups: the master and every worker that may run the wrapped tool must see the same absolute path to the conda env and the executable. The common solution is a shared filesystem mounted at the same mount point on all nodes.
- **Container or system library mismatch** is a frequent External-Job failure mode. `LD_LIBRARY_PATH`, `PYTHONPATH`, and stray `numpy`/`PYTHONPATH` overrides have all been observed (`17_error_lookup.md` §4) to break either the wrapper subprocess or the CryoSPARC worker that called it. The DeepEMhancer wrapper-shell-script idiom (unset conda + path vars, source the right env, exec the tool) is the canonical fix.
- **GPU driver / CUDA version** is a per-tool concern. Gctf needs CUDA 8 specifically; modern wrappers and `cryosparc-tools` drivers should match the CryoSPARC-supported CUDA range. v4.4 fixed cases where reference-based motion correction failed when GPUs were in `EXCLUSIVE_PROCESS` mode — wrappers do not get a similar built-in fix, so the user must verify mode compatibility for each tool.

### 4.2 GPU / CPU / storage implications

| Concern | Wrapper jobs | External Jobs |
|---|---|---|
| GPU allocation | Done by the CryoSPARC scheduler (`num_gpu` request → cluster GRES / direct device assignment). | Done by the **driver host**, not CryoSPARC. The driver script is responsible for setting `CUDA_VISIBLE_DEVICES` or coordinating with the cluster's GPU isolation. |
| CPU budget | Wrapper requests CPUs per its own spec; the scheduler enforces. | Whatever the driver host has. Long-running External Jobs on a master node can starve the master. |
| RAM budget | Same as native — slot-counted (8GiB slots) on workers. | Driver host's responsibility. |
| Disk path | All artifacts live under the project tree, like any job's `Jx/` directory. | Driver-defined. Writing into `job.dir` is the safe default and is what archive/compact/restore expect. Writing into a non-project scratch path is **invisible** to all CryoSPARC data-management commands. |
| SSD cache | Wrappers participate normally if they take particle/exposure inputs. | External Jobs do not consume the SSD cache the way native jobs do — they read whatever paths the driver opens. Cache thrash is not a typical External-Job symptom. |

### 4.3 Version / schema drift

The schema for inputs/outputs (slot names, dataset column conventions, group types) evolves across CryoSPARC versions. The `cryosparc-tools` library tracks the CryoSPARC minor version closely — `reference/cryosparc-tools/CHANGELOG.md` documents that mismatches produce a warning at connection time and may produce hard errors at call time. Practical rules:

- Pin the `cryosparc-tools` version to the connected CryoSPARC minor version (`pip install --force cryosparc-tools~=<X.Y>.0`).
- After a CryoSPARC update, regenerate any wrapper-shell-script absolute paths; CryoSPARC's bundled conda was rebuilt and `LD_LIBRARY_PATH` may have moved.
- After a CryoSPARC update, re-test every External-Job driver before treating it as production again. v5.0 specifically broke several `cryosparc-tools` patterns (`add_output` slots, asset access, lane / target dict access).
- Workflow JSON exported from version A may not re-import cleanly into version B if it touches External Jobs whose driver has not been re-tested.

### 4.4 Reproducibility

The most important thing to internalize at this boundary: **CryoSPARC's database does not store the external tool's version, model weights, or code.** A wrapper job record will tell you you ran DeepEMhancer with given parameters and inputs; it will not tell you which DeepEMhancer commit / which weight file. For an External Job, CryoSPARC will tell you the inputs and outputs; it will not tell you which crYOLO version / which config / which trained model produced the picks.

To close the gap, write — by hand, as part of the External Job or as an asset attached to a wrapper job's `Jx/` directory:

- Tool name, version (commit hash or release tag).
- Model / weight identity (file path, checksum, or version label).
- Driver script (for External Jobs) or wrapper shell script (for wrappers).
- The conda env spec (e.g., `conda env export > env.yaml` saved as an asset).

A separate "do not trust without local validation" reflex applies to the **output**: e.g., a DeepEMhancer-sharpened map is for visualization, not for FSC claims (`10_postprocessing.md`); a ModelAngelo model is a draft, not a validated structure; a crYOLO pick set should still be sanity-checked with cryoSPARC 2D classification.

### 4.5 Not treating external output as automatically validated

CryoSPARC's QC machinery (FSC, local resolution, orientation diagnostics, particle scale) is calibrated for native pipeline outputs and inputs whose schema matches. External outputs that *look* like native outputs (particles, exposures, volumes) pass through CryoSPARC's QC plumbing, but that does not mean CryoSPARC validated the external tool's correctness. Two specific failure shapes are worth naming:

- A picker (external or wrapped) producing picks at the wrong scale / coordinate convention: extraction proceeds, 2D classification runs, but the 2D averages look subtly wrong (off-center, smeared) — and only this kind of close look catches it.
- An external "map improvement" tool producing a volume that fits into Refinement as a reference and silently biases alignments. This is one of the canonical reasons DeepEMhancer output is specifically marked as visualization-only.

The advisor default is: validate every external output with at least one downstream native sanity job (2D for picks, FSC + Orientation Diagnostics for volumes, Inspect Picks for picker outputs) before trusting it.

---

## 5. Runbooks

### 5.1 Deciding native vs wrapper vs external

```
1. Is there a native CryoSPARC job that does this?
   - YES → use native unless there is a specific scientific reason not to.
   - NO  → continue.
2. Is there a built-in CryoSPARC wrapper for the tool I need?
   - YES → use the wrapper. Confirm: licensing, install location, master/worker
           path identity, executable path parameter, whether a wrapper shell
           script is needed to deactivate CryoSPARC's conda env.
   - NO  → continue.
3. Does the tool have a Python or CLI interface I can call?
   - YES → External Job via cryosparc-tools. Plan provenance up front:
           which inputs to connect, which outputs to write back, where the
           driver script lives, how the tool version is recorded.
   - NO  → not a CryoSPARC integration question — export / import outside
           CryoSPARC and treat the result as imported data.
```

Red flags that should short-circuit this tree into "stop and validate":

- The user describes a "CryoSPARC + X" integration that is not in the local Job Builder. Confirm presence and stability tag before recommending.
- The user wants to use a Legacy wrapper (Gctf, ThreeDFSC) for a new project rather than to reproduce a specific old result. Default to the native equivalent (Patch CTF, Orientation Diagnostics).
- The user wants to install the third-party tool *inside* CryoSPARC's conda env. Hard stop — refer to §4.1.

### 5.2 Setting up a wrapper job safely

Checklist (DeepEMhancer is the canonical example; the same shape applies to CTFFIND4 / MotionCor2 / Gctf when the third-party tool is licensable and installable):

- [ ] User has accepted the third-party tool's license.
- [ ] Tool is installed in a conda env **separate** from CryoSPARC's bundled env.
- [ ] Conda installation path is **identical** on master and every worker (shared filesystem or matching local installs).
- [ ] `which <tool>` from the active env returns an absolute path that is also valid on every worker as the CryoSPARC user.
- [ ] If conda env activation conflicts with CryoSPARC's env, a wrapper shell script (see DeepEMhancer's `deepemhancer.sh` template) is in place and `chmod +x`'d, also reachable at the same path from master and worker.
- [ ] Path is entered into the wrapper job's `Path to <tool> executable` parameter, or set as a **project-level default** (v4.1+ for DeepEMhancer, v4.0+ for Topaz) so newly built jobs of that type autofill it.
- [ ] A *pilot run* on a small input has been done and inspected before scaling to the full dataset.
- [ ] Tool version (release tag or commit) and any model/weight file path are recorded somewhere durable — ideally as a text asset attached to the project or workspace description.

### 5.3 Setting up an External Job safely

Checklist:

- [ ] Driver script lives in source control (or at least in a known path on the driver host) — *not* only in a notebook cell history.
- [ ] Driver uses `python -m cryosparc.tools login` (v5.0+) rather than putting password / license in the script, *or* uses environment variables (`CRYOSPARC_BASE_URL`, `CRYOSPARC_EMAIL`, `CRYOSPARC_PASSWORD`, `CRYOSPARC_LICENSE_ID`) read at startup.
- [ ] `cs.test_connection()` is the first thing the script does.
- [ ] Input slot list (`connect(..., slots=[...])`) names the **exact** slots the tool needs (e.g., `micrograph_blob`, `location`, `ctf`, `blob`). Avoid relying on default-all-slots — schema drift can change what "default" includes.
- [ ] Output `add_output(...)` slot list matches the **downstream job's expected schema** for that data type (location + pick_stats for picks, etc.). If you do not know, look at the slot list a native equivalent job produces (`Job.print_output_spec`).
- [ ] Tool subprocesses are called via `job.subprocess(...)` so their stdout/stderr is captured in the job log.
- [ ] Tool version / model identity is written into the job's event log via `job.log(...)` at the start of the run.
- [ ] The script exits via `job.stop()`. If it raises, it should call `job.clear()` (or be designed so the user does) before retrying.
- [ ] A *small-pilot* downstream sanity job (2D for picks, FSC for volumes) is queued automatically or by the user before any production use.

### 5.4 Troubleshooting missing outputs or logs (External Job)

| Symptom | First checks |
|---|---|
| External Job stuck in `running` after script exited | Driver crashed without calling `job.stop()`. `job.clear()` from a fresh `cryosparc-tools` session, then re-run the script. |
| `add_input` / `add_output` raises `cannot add … to completed job` | v5.0+ enforces lifecycle: clear → start → save → stop. Call `job.clear()` first. |
| Output dataset appears in the GUI but downstream job complains "missing slot X" | The output's slot list does not match the downstream job's expectation. Print the native equivalent's output spec, fix `add_output(..., slots=[...])`. |
| Image / plot from the external tool not visible in the GUI | It is either in `job.dir` (visible via the file browser) or needs to be uploaded as an asset (`job.upload_asset` / matplotlib figure handed to a log call). Files written outside `job.dir` are not visible. |
| External Job event log empty | Tool was not run through `job.subprocess(...)` (stdout was lost), or the script wrote to its own log file in a non-project path. Re-route through `job.subprocess` so output is forwarded. |
| `cryosparc-tools` raises connection or schema errors after a CryoSPARC update | `cryosparc-tools` minor version no longer matches CryoSPARC minor version (warning at connect time). Update with `pip install --force cryosparc-tools~=<X.Y>.0`. |
| Python traceback at the master | Look at `cryosparcm log command_vis` (`17_error_lookup.md` §6). |

### 5.5 Troubleshooting missing outputs (wrapper job)

| Symptom | First checks |
|---|---|
| Wrapper job fails at launch with "executable not found" or non-zero exit before any tool output | Executable path is wrong, or path resolves on master but not on the worker. Confirm `ls -l` from the worker shell as the CryoSPARC user. |
| Tool runs, produces files in its own working dir, but the job has no outputs | The wrapper's expected output filenames did not match the tool's actual output (often a tool-version mismatch). Check the job's stdout/stderr in the event log against the tool's documented output paths for the installed version. |
| DeepEMhancer-style env conflict ("module X not found", numpy version errors) | The wrapper inherited CryoSPARC's env vars. Install the wrapper shell script that explicitly deactivates CryoSPARC's conda env and re-activates the tool's. |
| CTFFIND4 fails on every movie | Movies were imported with a separate gain reference — gain correction is not baked into the import for the wrapper to see. Use Patch CTF, or motion-correct first and feed micrographs. |
| Gctf wrapper fails with `LD_LIBRARY_PATH` error | Update to v4.5+ which patched this (`reference/release_notes/markdown/v4.5.md`), or `export LD_LIBRARY_PATH=` to a non-empty no-op value in the worker env. |
| ThreeDFSC wrapper streamlog blank | Functionality is partial by design (`docs/per_page/.../job-threedfsc-wrapper-legacy.md`); use native Orientation Diagnostics for new work. |
| Assertion error "No output result named `micrographs_fail.ctf`" after CTFFIND4 failures | All CTFFIND runs failed, so the failed-output result was never created (`17_error_lookup.md`). Check why the runs failed — usually gain-correction or path issues. |

### 5.6 Archiving provenance

Treat the project tree as the primary record; treat MongoDB GridFS assets and the database as a *secondary* record that survives `cryosparcm backup` / `restore` but not a hand-rolled `cp` of the project dir.

- Save the driver script for every External Job into the project dir (`Jx/driver.py` or as an uploaded asset) **before** the job is treated as final.
- Save a `tool_env.yaml` (`conda env export` of the tool's env) into the project at first use; re-save when the env changes.
- Save the tool's version output (`<tool> --version`) into the job event log via `job.log(...)`.
- For wrappers, record the wrapper shell script path and contents in the workspace's description or as an asset.
- Use `cryosparcm backup` to capture the MongoDB record alongside the project directory tree (`14_cli_admin.md`, `24_disk_and_storage.md`).

### 5.7 Recovering after an external tool failure

```
1. Read the actual error.
   - Wrapper: Event Log tab → job.log in Jx/ → cryosparcm joblog Px Jx.
   - External Job: Event Log tab → cryosparcm log command_vis on the master
                   → traceback in the driver host's terminal.
2. Classify the failure (see §5.4 / §5.5 tables).
3. If the tool produced partial output:
   - Wrapper: clear the job, fix the underlying cause, re-run. Do not
     try to import the partial output via a separate External Job — the
     output schema may be incomplete.
   - External Job: call job.clear(), re-fill, re-stop. Or, if the
     external tool's partial output is genuinely usable, write a *new*
     External Job that wraps the partial files explicitly, with the tool
     version and "this is partial" noted in job.log.
4. If the wrapper job repeatedly fails the same way on a particular
   subset of inputs:
   - Try the native equivalent on the same subset to confirm the inputs
     themselves are sane. This isolates whether the failure is data or
     tool. (Same rule as RELION interop — see 27_relion_interop.md.)
5. Escalate to update / env rebuild only after the above narrows the
   bucket to an env / version problem.
```

---

## 6. Failure modes table — external job and wrapper layer

| Symptom | Likely layer | First checks | Escalation / source |
|---|---|---|---|
| `executable not found` at wrapper launch | Wrapper install / path | `ls -l <path>` as CryoSPARC user on both master and worker; confirm conda env active in the wrapper shell script | `15_troubleshooting.md` §2; DeepEMhancer install instructions |
| Wrapper job starts then fails inside the tool with "module / numpy / version" error | Env contamination from CryoSPARC's bundled conda | Wrap tool in a `*.sh` script that `unset`s `PYTHONPATH`, `LD_LIBRARY_PATH`, `CONDA_*` and re-sources the tool's env | DeepEMhancer doc; `17_error_lookup.md` §4 (`numpy.float64` index error pattern) |
| `LD_LIBRARY_PATH` empty → Gctf fails | Wrapper edge case | Update to v4.5+ (the env-var fix) or set a non-empty no-op value | `reference/release_notes/markdown/v4.5.md` |
| CTFFIND4 wrapper fails on all movies | Wrapper input schema | Movies imported with separate gain ref — wrapper does not see gain. Use Patch CTF or motion-correct first | CTFFIND4 wrapper doc (gain-correction warning) |
| `AssertionError: No output result named micrographs_fail.ctf` | Wrapper output-handling bug after all-fail input | All CTFFIND runs failed — fix the underlying input/path problem, not the assertion | `17_error_lookup.md` §4 |
| External Job stuck `running` after script exits | External-Job lifecycle | Driver crashed without `job.stop()` — call `job.clear()` and re-run | `cryosparc-tools` `controllers/job.py` |
| `cannot add input / output to completed external job` | External-Job lifecycle (v5.0+) | Lifecycle now enforces clear → start → save → stop | `reference/cryosparc-tools/CHANGELOG.md` v5.0.0 |
| External Job outputs OK but downstream job fails "missing slot X" | External-Job output schema | `add_output(..., slots=[...])` did not include the slot the downstream expects | `controllers/job.py`; native equivalent's `Job.print_output_spec` |
| `cryosparc-tools` produces schema / type errors after CryoSPARC update | Version drift | `pip install --force cryosparc-tools~=<CryoSPARC X.Y>.0`; retest External-Job drivers | `reference/cryosparc-tools/CHANGELOG.md` |
| Tool subprocess output missing from event log | External-Job logging | Tool was called via raw `subprocess.run` instead of `job.subprocess(...)` | `examples/cryolo.ipynb` |
| Wrapper job runs on master but fails on worker | Master/worker path divergence | Conda install path differs between master and worker; or shell init prints text that breaks SSH launch | `15_troubleshooting.md` §2; `17_error_lookup.md` (worker-launch entries) |
| External Job outputs missing after `cryosparcm compact` | Outputs were written outside `job.dir` (or were intermediate) | Compaction only knows about files in `Jx/` it can prove are intermediate. Files outside the project tree are invisible to it. Re-run with outputs written into `job.dir`. | `24_disk_and_storage.md` |
| DeepEMhancer / wrapper map shows extra detail that disappears with parameter changes | Tool-output interpretation | DeepEMhancer is visualization-only; do not back FSC / resolution claims with it | `10_postprocessing.md` |
| crYOLO External Job "Inspect Picks" shows no power histogram or particle overlays | External-Job output schema or path | Particle locations not registered in the slot the GUI expects (`location` slot in `pick` group); or the micrograph paths used at pick time differ from the paths CryoSPARC sees now | Forum thread *crYOLO particle picking problem* (`docs/forum_threads/digests/forum_scripting.md` #1) |
| Job ran outside CryoSPARC, no External Job exists, results need to live in CryoSPARC | Wrong tool for the job | Create an External Job *post hoc* that connects upstream inputs, declares outputs, writes the files into `job.dir`, and records the tool version in `job.log` | `controllers/job.py` `ExternalJobController` |

---

## 7. Advisor defaults and red flags

### Defaults

- **Prefer native over wrapper** when a native equivalent exists (Patch CTF over CTFFIND4, Patch Motion over MotionCor2, native Orientation Diagnostics over ThreeDFSC). Wrappers earn their place when the user needs a specific tool for licensing, comparison, or replication reasons.
- **Prefer wrapper over External Job** when CryoSPARC ships a wrapper. The wrapper records parameters and outputs in the job database; the External Job leaves more of the provenance on the user.
- **Pilot every wrapper / External Job** on a small input before committing the full dataset.
- **Pin `cryosparc-tools` to the CryoSPARC minor version**, and re-pin after every CryoSPARC update.
- **Write provenance you would want in 12 months**: tool version, weights identity, driver script, env spec, attached as assets or in `job.dir`. CryoSPARC's database does not track these.
- **Treat external output as draft until validated downstream**: 2D for picks, FSC + Orientation Diagnostics for volumes, Inspect Picks before extraction.

### Red flags

- A claim that a tool ("ModelAngelo", "X-Picker", "DeepFooBar") is "a CryoSPARC job" — confirm against the local Job Builder before treating as native.
- Installation of a third-party Python package into CryoSPARC's bundled conda env. Hard stop.
- Wrapper path that resolves on the master but not on the worker as the CryoSPARC user. Hard stop until corrected.
- An External-Job driver with credentials inline in the script. Move them to a login session or env vars.
- Using a Legacy wrapper (Gctf, ThreeDFSC) for a brand-new project rather than reproducing a known recipe.
- Treating a DeepEMhancer-sharpened map as evidence of more signal (it is post-hoc visualization, not a resolution claim).
- Trusting external picks without a 2D classification gate.
- An External Job whose outputs were written to a scratch path outside `job.dir`. Move them in or wrap a new External Job that points at them in-tree.
- Workflow JSON that bundles an External Job without explicit driver instructions in the workflow description.
- A wrapper or External Job that has been "working fine" across several CryoSPARC updates without re-pinning `cryosparc-tools` or re-testing the wrapper shell script.

---

## 8. Cross-links

- `13_cryosparc_tools_api.md` — connection mechanics, dataset I/O, Workflow templating, the `cryosparc-tools` boundary with the GUI and CLI.
- `14_cli_admin.md` — `cryosparcm` / `cryosparcw` syntax disclaimer, log layout (`command_core`, `command_vis`), restart and update mechanics.
- `21_gpu_lane_queue.md` — scheduler / lane behavior. Wrappers participate; External-Job drivers do not unless the driver itself is submitted as a non-CryoSPARC job.
- `24_disk_and_storage.md` — where wrapper and External-Job outputs land in the project tree; archive / compact / restore guarantees and what falls outside them.
- `10_postprocessing.md` — interpretation of DeepEMhancer, FSC, Orientation Diagnostics. The wrapper's *operational* shape lives here; its *scientific* shape lives there.
- `27_relion_interop.md` — round-trips with RELION; not an External Job in the cryosparc-tools sense, but the same provenance discipline applies.
- `15_troubleshooting.md` — five-bucket triage; external/wrapper failures usually live in buckets 2 (env / SSH / shell) and 5 (workflow misuse / mismatched inputs).
- `18_decision_trees.md` — branching rules for "do not chase parameters when the failure is at the install / env / wrapper layer."
- `17_error_lookup.md` — exact-string lookup, including CTFFIND4 failed-output assertion, numpy index errors, worker-launch SSH issues.

---

## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

- `topic_plan.md`
- `plan.md`
- `10_postprocessing.md`
- `13_cryosparc_tools_api.md`
- `14_cli_admin.md`
- `15_troubleshooting.md`
- `18_decision_trees.md`
- `21_gpu_lane_queue.md`
- `24_disk_and_storage.md`
- `17_error_lookup.md`
- `reference/cryosparc-tools/CHANGELOG.md`
- `reference/cryosparc-tools/cryosparc/tools.py`
- `reference/cryosparc-tools/cryosparc/controllers/job.py`
- `reference/cryosparc-tools/cryosparc/models/external.py`
- `reference/cryosparc-tools/cryosparc/api.pyi`
- `reference/cryosparc-tools/docs/guides/jobs.ipynb`
- `reference/cryosparc-tools/docs/examples/custom-workflow.ipynb`
- `reference/cryosparc-tools/docs/examples/cryolo.ipynb`
- `reference/release_notes/markdown/v4.0.md`
- `reference/release_notes/markdown/v4.1.md`
- `reference/release_notes/markdown/v4.2.md`
- `reference/release_notes/markdown/v4.3.md`
- `reference/release_notes/markdown/v4.4.md`
- `reference/release_notes/markdown/v4.5.md`
- `reference/release_notes/markdown/v4.6.md`
- `reference/release_notes/markdown/v5.0.md`
- `docs/per_page/processing-data__cryosparc-tools.md`
- `docs/per_page/processing-data__automated-workflows.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__post-processing.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__post-processing__job-deepemhancer-wrapper.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__post-processing__job-threedfsc-wrapper-legacy.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__ctf-estimation__job-ctffind4-wrapper.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__ctf-estimation__job-gctf-wrapper-legacy.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__motion-correction__job-motioncor2-wrapper-beta.md`
- `docs/per_page/application-guide__creating-and-running-jobs.md`
- `docs/per_page/application-guide__workflows.md`
- `docs/per_page/application-guide__inspecting-job-data.md`
- `docs/forum_threads/digests/forum_scripting.md`
- `docs/forum_threads/digests/forum_troubleshooting.md`
- `docs/forum_threads/digests/forum_motion-correction.md`
