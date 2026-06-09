# Topic 29 — External-tool bridge format (crYOLO / cryoDRGN / RELION pattern)

## Scope
A lightweight contract for making cryoSPARC orchestrate external programs while keeping those
programs usable as independent skills. Use this when the user wants a future integration such as
"run crYOLO from cryoSPARC", "send a cryoSPARC particle set through cryoDRGN and bring classes
back", or "standardize an adapter between cryoSPARC and another cryo-EM CLI".

This page does **not** replace the tool-specific skills. Exact crYOLO commands and output formats
belong to `cryolo-skill`; exact cryoDRGN commands belong to `cryodrgn-skill`; RELION STAR semantics
belong to `relion`. The cryoSPARC skill owns only the wrapper shape: how inputs leave cryoSPARC,
how provenance is recorded, and how validated outputs become cryoSPARC result groups again.

For already-implemented RELION focused Class3D round-trips, use `28_relion_class3d_roundtrip.md`.
For the underlying External Job mechanics, use `23_external_jobs.md`.

---

## 1. Design rule — hub + independent spokes

Use a **hub-and-spoke** layout:

- **cryoSPARC hub skill**: owns `cryosparc-tools` connection, External Job lifecycle, queue
  confirmation, cryoSPARC result-group schemas, and re-entry validation.
- **external tool skill**: owns install/config, native CLI flags, native formats, independent
  workflows, and tool-specific validation.
- **adapter page/script**: only the glue. It should cite the external tool skill for native details
  rather than copying them.

This prevents a monolithic "cryoSPARC + every tool" skill while still letting cryoSPARC drive a
complete workflow when the user's starting and ending point is a cryoSPARC project.

Recommended future layout inside the cryoSPARC skill:

```text
references/29_external_tool_bridge_format.md       # this contract
scripts/external_tools/<tool>/README.md            # adapter-specific runbook
scripts/external_tools/<tool>/<tool>_bridge.py     # optional driver, dry-run first
scripts/external_tools/<tool>/<tool>.example.json  # config template, no secrets
```

Keep `scripts/external_tools/<tool>/` small and deterministic. If the adapter grows into a full
standalone workflow, create/update the independent `<tool>` skill and leave only a cross-link here.

---

## 2. Bridge manifest v1

Every adapter should write a small JSON manifest into the External Job directory (or the chosen
round-trip working directory for non-External-Job bridges). Name it `bridge_manifest.json`.
It is the durable audit record that cryoSPARC itself does not store.

```json
{
  "schema": "structagent.cryosparc_external_bridge.v1",
  "tool": "cryolo|cryodrgn|relion|other",
  "tool_skill": "cryolo-skill|cryodrgn-skill|relion",
  "mode": "external_job|export_only|import_only|roundtrip",
  "cryosparc": {
    "project_uid": "Pxx",
    "workspace_uid": "Wxx",
    "source_jobs": ["Jxx"],
    "tools_version": "5.0.x",
    "master_version": "5.0.x"
  },
  "inputs": [
    {
      "name": "micrographs|particles|volume|mask",
      "source_job": "Jxx",
      "result_group": "...",
      "slots": ["location", "micrograph_blob", "ctf", "blob"]
    }
  ],
  "external": {
    "command": ["tool", "arg1", "arg2"],
    "working_dir": "relative/or/project/path",
    "env_name": "conda/container/module label",
    "version": "tool --version output",
    "model_or_weights": "path/checksum/label if applicable"
  },
  "identity_keys": {
    "particles": "cryosparc uid; fallback image stack stem + 1-based index",
    "micrographs": "exposure uid; fallback normalized path suffix + shape"
  },
  "outputs": [
    {
      "name": "picks|particles|volumes|classes|indices",
      "foreign_paths": ["relative/file.star"],
      "cryosparc_result_group": "... or null",
      "validation": "pending|passed|failed"
    }
  ],
  "safety": {
    "credentials_inline": false,
    "queued_compute": false,
    "user_confirmed_queue": false
  }
}
```

Rules:
- No passwords, API keys, license tokens, private hostnames, or absolute personal paths.
- Store the actual command argv. If a wrapper shell script activates an environment, store the
  wrapper path and the resolved `tool --version` too.
- Store model/weights identity for ML tools (crYOLO config/model, cryoDRGN weights, etc.). Prefer
  checksum when a file path alone is not durable.
- Record the identity key used to map results back. For particles, prefer cryoSPARC `uid`; when a
  foreign tool only knows stacks, use `(stack stem, 1-based index)` and abort on unmatched rows.

---

## 3. Adapter shapes

### 3.1 External picker: crYOLO → cryoSPARC picks

When the user starts in cryoSPARC and wants crYOLO picks returned as cryoSPARC-native picks:

1. cryoSPARC External Job connects upstream micrographs/exposures.
2. Adapter stages micrograph paths (or a manifest of paths) into `job.dir`.
3. Adapter invokes crYOLO through the independent crYOLO environment.
4. Adapter writes crYOLO native outputs unchanged under `job.dir/cryolo_raw/`.
5. Adapter converts/registers picks into a cryoSPARC output result group with the downstream
   extraction-compatible slots (`location` + pick statistics, plus passthrough linkage as needed).
6. Validate with Inspect Picks on a one-micrograph pilot, then 2D classification on a small subset.

Do not duplicate crYOLO CLI flag details here; load `cryolo-skill/references/06_interoperability.md`
and the crYOLO CLI reference when building the actual command. crYOLO remains independently usable
via its own STAR / CRYOSPARC / EMAN / CBOX outputs.

### 3.2 Heterogeneity analysis: cryoSPARC → cryoDRGN → selections/maps → cryoSPARC

When the user starts from cryoSPARC particles and wants cryoDRGN latent analysis or class selections:

1. Export/locate the cryoSPARC particle `.cs` and stacks needed by cryoDRGN.
2. Adapter invokes cryoDRGN parse/train/analyze commands in the independent cryoDRGN environment.
3. Store latent coordinates, indices, volumes, and plots under `job.dir/cryodrgn_raw/`.
4. For selections, map cryoDRGN indices back to existing cryoSPARC particle `uid`s and create a
   filtered External subset / passthrough-preserving result group.
5. For volumes, import/register maps as assets or volume outputs, then run native cryoSPARC
   refinement/validation as appropriate.

Important constraint from the cryoDRGN skill: `cryodrgn_utils write_cs` / `filter_cs` filters an
**existing** `.cs`; it does not create a brand-new cryoSPARC `.cs` from arbitrary stacks. Therefore
CryoSPARC re-entry should preserve and filter the original cryoSPARC particle set whenever possible.

### 3.3 RELION round-trip

Use `28_relion_class3d_roundtrip.md` and `scripts/roundtrip/` for the implemented focused Class3D
case. It is the concrete example of this contract: a RELION-native step stays RELION-owned, while
cryoSPARC owns uid mapping, External subsets, Local Refinement, and optional NU Refinement re-entry.

---

## 4. Validation gates before trusting returned outputs

Minimum gates by output type:

| Returned output | First validation inside cryoSPARC |
|---|---|
| Picks / coordinates | Inspect Picks on representative micrographs; confirm no scale/y-flip/origin error. Then a small Extract + 2D Classification pilot. |
| Particle subset / classes | Count check, uid-match check with 0 unmatched rows, class-size sanity, then a short local/homogeneous refinement. |
| Volume / map | Header pixel size/box/handedness check, visual overlay with source map, then FSC/orientation diagnostics after a native refinement if the map affects alignment. |
| Metadata-only QC | Confirm row counts and key columns; attach plots/assets to the External Job; do not treat plots as particle provenance. |

Abort rather than guess if:
- identity keys do not match 1:1;
- pixel size or box size is missing/contradictory;
- a downstream native job complains about missing slots;
- a tool output lives outside `job.dir` and cannot be archived with the project.

---

## 5. Safety defaults

- Credentials come from `cryosparc-tools` login state or `CRYOSPARC_*` environment variables only.
- Dry-run/build before queueing. Any compute-heavy native cryoSPARC job still requires explicit
  user confirmation of project, workspace, lane, and queue vs dry run.
- External tool compute is not automatically governed by cryoSPARC lanes. If the adapter consumes
  GPU time, either run the driver on a controlled worker/GPU host or submit it through the site
  scheduler and record that in the manifest.
- Preserve raw external outputs unchanged under `job.dir/<tool>_raw/` before conversion. This makes
  later debugging possible and keeps the external tool independently auditable.
- Pilot first: one micrograph for pickers, a small particle subset for cryoDRGN/RELION, one map for
  volume postprocessing.

---

## Cross-links

- `23_external_jobs.md` — External Job mechanics, provenance gaps, lifecycle, and wrapper-vs-external decision tree.
- `13_cryosparc_tools_api.md` — connection and dataset I/O details; confirm exact API signatures against the installed cryoSPARC-tools version.
- `27_relion_interop.md` and `28_relion_class3d_roundtrip.md` — RELION metadata bridge and implemented focused Class3D round-trip.
- `particle_set_operations.md` — combining/diffing/filtering particle sets once external classes or indices return.
- `cryolo-skill/references/06_interoperability.md` — crYOLO-native coordinate outputs and downstream import cautions.
- `cryodrgn-skill/references/06_interoperability.md` — cryoDRGN parse/filter/write-back constraints.
