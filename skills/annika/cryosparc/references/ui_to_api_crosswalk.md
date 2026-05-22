# Reference — cryoSPARC UI ↔ API Crosswalk

## Scope / how to use

Retrieval-first map from common cryoSPARC GUI actions to the corresponding `cryosparc-tools` controller/API surfaces. Use this when converting a manual GUI workflow into automation or when debugging a script by comparing it to what the GUI shows.

This is **not** a complete API reference. The exact method signatures and parameter names are version-dependent. Before writing a runnable script, confirm against the installed `cryosparc-tools` docs/package and the target job's live spec.

Core rule: **the GUI is the safest source of job-specific names; the tools API is the safest way to automate once those names are known.**

Primary sources: `13_cryosparc_tools_api.md`, `docs/per_page/application-guide__creating-and-running-jobs.md`, `docs/per_page/application-guide__inspecting-job-data.md`, `docs/per_page/application-guide__low-level-results-interface.md`, `reference/cryosparc-tools/docs/guides/jobs.ipynb`, `reference/cryosparc-tools/cryosparc/api.pyi`, `reference/cryosparc-tools/cryosparc/models/job_spec.py`.

---

## Fast translation checklist

When converting GUI → API:

1. **Find exact job type key**
   - GUI: Job Builder job name, e.g. “Extract from Micrographs”.
   - API: machine-readable job type, discover with `CryoSPARC.print_job_types()` / job register / existing job `job.type`.
2. **Find exact parameter code names**
   - GUI: job dialog/sidebar **Inputs and Parameters** tab; copy parameter key/value text or inspect job metadata.
   - API: `job.print_param_spec()`, `job.full_spec.params`, `job.set_param(<param_name>, value)`.
3. **Find input group names**
   - GUI: Builder input boxes.
   - API: `job.print_input_spec()`, `job.inputs`, `job.connect(target_input=..., source_job_uid=..., source_output=...)`.
4. **Find output group names**
   - GUI: job card outputs view / Outputs tab / right sidebar output groups.
   - API: `parent_job.print_output_spec()`, `parent_job.outputs`, `job.load_output(<output_group>)`.
5. **Find low-level result slot names only when needed**
   - GUI: “Show slots” in Inputs and Parameters; expand Outputs tab groups; low-level result labels such as `blob`, `ctf`, `location`, `alignments3D`.
   - API/model: `Connection.results`, `InputResult`, `connect_result`, `disconnect_result`; dataset columns appear as `<slot>/<field>`.
6. **Queue and verify**
   - GUI: Queue slide-over → lane/target/GPU/resource choice.
   - API: `job.queue(lane=...)`, `job.wait_for_done(error_on_incomplete=True)`, then inspect status/errors/logs/outputs.

Never invent parameter names from the display label alone. Display labels are human-friendly; API keys are machine-readable and may differ.

---

## Concept crosswalk

| GUI concept | API / model concept | Notes | Source |
|---|---|---|---|
| Project card / project page | `ProjectController`, `ProjectsAPI`; UID `P<N>` | Project is the disk-backed container for jobs and data. | `13_cryosparc_tools_api.md`, `api.pyi` |
| Workspace inside a project | `WorkspaceController`, `WorkspacesAPI`; UID `W<N>` | Logical grouping; jobs may appear in workspaces. | same |
| Live Session | `SessionsAPI`, `Session`; session UID | Live has session-specific preprocessing/picking/2D/3D operations and config profiles. | `api.pyi`, `25_cryosparc_live.md` |
| Job card / job dialog | `JobController`, `JobsAPI`; UID `J<N>` | Job has `type`, `status`, `spec`, params, inputs, outputs, logs. | `models/job.py` |
| Job Builder display name | job `type` key | Use `print_job_types()` / `get_job_register()` / existing job `job.type`; do not infer blindly. | `jobs.ipynb`, `api.pyi` |
| Builder categories/tags | `Category`, `BuilderTag` | Categories include import, motion_correction, ctf_estimation, particle_picking, extraction, reconstruction, refinement, etc.; tags include interactive, gpuEnabled, multiGpu, utility, import, live, benchmark, wrapper. | `models/job_spec.py` |
| Input group box | `Input` / `Connection` | Group-level connection to a parent job output. | `models/job_spec.py` |
| Output group box | `OutputSpec` | Typed group such as `particle`, `exposure`, `volume`, `volume_multi`, `mask`. | `models/job_spec.py` |
| Low-level result slot | `InputResult`, `OutputSlot` | Slot names like `blob`, `ctf`, `location`, `alignments3D`; dataset columns use `<slot>/<field>`. | `low-level-results-interface.md`, `models/job_spec.py`, `jobs.ipynb` |
| Final output version `F` | `version='F'` in `InputResult` | Earlier iterations can be selected by numeric version. | `low-level-results-interface.md`, `models/job_spec.py` |
| Passthrough slot | `passthrough` / auto-fetched metadata | Tools auto-fetch passthrough metadata; direct `.cs` readers may not unless job/output is exported. | `low-level-results-interface.md` |
| Queue slide-over | `job.queue(...)` / `api.jobs.enqueue(...)` | Can specify lane; exact resource/target signatures are version-specific. | `jobs.ipynb`, `api.pyi` |
| Job status chip | `JobStatus` | `building`, `queued`, `launched`, `started`, `running`, `waiting`, `completed`, `killed`, `failed`. | `models/job.py` |
| Event Log tab | `job.get_event_logs()` / `api.jobs.get_event_logs()`; job assets | Use for text/image/checkpoint events. | `api.pyi`, `inspecting-job-data.md` |
| Metadata → Log tab | `job.get_log()` / `api.jobs.get_log()` / `get_log_path()` | Use for stdout/job log diagnostics. | `api.pyi`, `inspecting-job-data.md` |
| Download files/assets | `job.list_files()`, `download_file()`, `download_mrc()`, `list_assets()`, `download_asset()` | Files live in project/job directory; assets live in DB. | `jobs.ipynb` |
| GUI “Compare” differing parameters | Compare job params from `job.spec` / API | Good way to identify parameters worth scripting. | `inspecting-job-data.md` |
| Workflow template | `WorkflowsAPI`, `BlueprintsAPI`, `api.jobs.apply_blueprint`, `create_job_from_blueprint` | Prefer GUI workflows for reusable pipelines; use API to apply/parameterize. | `api.pyi`, `13_cryosparc_tools_api.md` |
| Admin Panel / instance banner | `ConfigAPI.set_instance_banner`, `set_login_message`, `UsersAPI`, `ResourcesAPI` | Admin/state mutation may also belong to `cryosparcm` rather than job automation. | `api.pyi`, `14_cli_admin.md` |

---

## GUI action → cryosparc-tools operation

| GUI action | API pattern | Verification |
|---|---|---|
| Open / connect to instance | `cs = CryoSPARC(<url>, ...)`; `cs.test_connection()` | Connection success; user identity/permissions correct. |
| Select project | `cs.find_project('P3')` or project lookup | Project UID/title matches intended project. |
| Select workspace | project workspace lookup / pass `workspace_uid` | Workspace UID/title matches intended workspace. |
| Browse jobs in a workspace/category | `project.find_jobs(workspace_uid='W40', category='motion_correction')` | Returned jobs have expected UID/type/status. |
| Create job from Builder | `project.create_job('W40', '<job_type>')` | New job is `building`; type matches desired job. |
| Load manually-created GUI job | `project.find_job('J1405')` | Inspect `job.uid`, `job.type`, `job.status`. |
| Show available parameters | `job.print_param_spec()` / `job.full_spec.params` | Machine-readable first column is the key to use. |
| Set a parameter | `job.set_param('<param_key>', value)` | Return success; re-fetch job/spec if needed. |
| Clear/reset parameter | `job.clear_param(...)` / `api.jobs.clear_param(...)` | Parameter back to default/cleared in GUI. |
| Show required inputs | `job.print_input_spec()` / `job.inputs` | Required groups and slots identified. |
| Show parent outputs | `parent_job.print_output_spec()` / `parent_job.outputs` | Output type/slots satisfy child input. |
| Drag output group into input group | `job.connect(target_input='...', source_job_uid='J...', source_output='...')` | Required input populated; no build errors. |
| Remove an input connection | `job.disconnect(...)` or `disconnect_all(...)` | Input group empty or updated. |
| Low-level slot replacement | `connect_result(...)` / result-level connection model | Only intended slot changes; other slots remain from original group. |
| Queue job | `job.queue(lane='...')` or `api.jobs.enqueue(...)` | Status transitions beyond `building`; lane/target correct. |
| Wait for completion | `job.wait_for_done(error_on_incomplete=True)` | Raises on killed/failed; final status `completed`. |
| Kill job | `job.kill()` / `api.jobs.kill(...)` | Status becomes `killed`; capture logs before retry. |
| Clear job back to building | `job.clear()` / `api.jobs.clear(...)` | Status `building`; outputs removed/invalidated. |
| Inspect event log | `api.jobs.get_event_logs(...)` / controller helpers | Capture errors/warnings and checkpoint/image/text events. |
| Inspect text log | `api.jobs.get_log(...)`, `get_log_path(...)` | Use for runtime traceback. |
| Load output dataset | `job.load_output('particles', slots=[...])` | Dataset includes created + passthrough metadata. |
| Download a file from job dir | `job.list_files()`, `job.download_file(...)` | Non-zero file; path belongs to expected job. |
| Download MRC | `job.download_mrc(...)` | Header/data shape plausible. |
| Download `.cs` dataset | `job.download_dataset(...)` | Columns use `<slot>/<field>` convention. |
| Export job / result group | `api.jobs.export_job(...)`, `export_output_results(...)` | Export directory created; downstream can parse `.cs/.csg`. |
| Import job / result group | `api.jobs.import_job(...)`, `import_result_group(...)` | Imported job/result appears in target workspace. |
| Set title/description/priority | `api.jobs.set_title`, `set_description`, `set_priority` | GUI card updates. |
| Star/tag job/project/workspace/session | `star_*`, `unstar_*`, `add_tag`, `remove_tag` APIs | GUI filters show new state. |

---

## Parameter-name crosswalk rules

### Where names come from

| GUI surface | API source | Use |
|---|---|---|
| Builder parameter label, e.g. “Extraction box size (pix)” | `job.print_param_spec()` key such as a machine-readable `*_pix` name | Set with `job.set_param(key, value)`. |
| Inputs and Parameters tab | shows configured inputs/parameters; v4.4+ can copy parameter code names / blueprint JSON | Canonical source for translating existing GUI jobs to scripts. |
| Comparison view parameter table | differing/custom/default parameter display | Identify which knobs changed between successful/failed jobs. |
| Blueprint JSON copied from GUI | blueprint parameter keys | Good bridge from GUI tuning to reusable automation. |
| `job.full_spec.params` | structured parameter spec | Use when writing a general translator. |

### Guardrails

- GUI labels can be renamed without changing code keys; code keys can be non-obvious. Always inspect spec.
- Advanced parameters may be hidden by default in the GUI; API can still set them, but the script should document why.
- Copy/paste parameters between jobs in v5 only applies shared parameters; scripts should similarly ignore non-existent keys rather than forcing them.
- For scripts that must support multiple cryoSPARC versions, branch on `ConfigAPI.get_version()` and re-read the job spec for that version.

---

## Input/output and low-level result crosswalk

### Group-level connection

GUI: drag a parent output group into a child input group.

API pattern:

```text
job.connect(
    target_input='<child_input_group>',
    source_job_uid='<parent_job_uid>',
    source_output='<parent_output_group>',
)
```

Examples of group types: `exposure`, `particle`, `template`, `volume`, `volume_multi`, `mask`, `ml_model`, `denoise_model`, `flex_mesh`, `flex_model`.

Verification:
- `target_input` exists in `job.print_input_spec()`.
- `source_output` exists in `parent_job.print_output_spec()`.
- Parent output type and required slots satisfy child input.

### Result-level connection

GUI: expand slots with “Show slots” or Outputs tab, then replace a single result such as `blob` while keeping `ctf` and `alignments3D` from another job.

API/model surface:
- `InputResult`: `name`, `dtype`, `job_uid`, `output`, `result`, `version`.
- `Connection.results`: list of slot-level result connections.
- API methods include `connect_result`, `disconnect_result`, `find_output_result`.

Canonical use case: use poses from a downsampled Homogeneous Refinement while replacing only the particle image `blob` slot with the full-size Extract from Micrographs `blob` slot. GUI display changes from something like `J688.particles.blob.F` to `J683.particles.blob.F`; API must make the same slot-level substitution.

### Dataset field names

`job.load_output('particles')` returns a dataset whose columns use:

```text
<slot>/<field>
```

Examples from sources:
- `ctf/amp_contrast`
- `blob/path`
- `location/...`
- `alignments2D/...`
- `alignments3D/...`

`uid` is special: CryoSPARC uses it to join/deduplicate metadata. Do not rewrite `uid` casually.

---

## Status, logs, and diagnostics crosswalk

| GUI symptom/surface | API/log surface | Action |
|---|---|---|
| Card stuck in `building` | `job.status`, build errors in `job.spec` | Check missing required params/inputs. |
| Queued but not launching | `job.status`, queue/lane info, `allocated_resources`, scheduler logs | Check lane target availability. |
| Running then failed | Event Log, text log, `api.jobs.get_log`, `cryosparcm joblog` | Capture first traceback and final status. |
| Dashboard errors/warnings | RunError / event logs / v5 dashboard data | Do not rely only on `completed`; warnings may matter. |
| Scripting failure | `cryosparcm log command_vis` + Python traceback | Especially for cryosparc-tools and API calls. |
| Worker launch failure | `cryosparcm log command_core` | Usually SSH/shell/env rather than job parameter. |
| DB/supervisor issue | `cryosparcm status`, `log database`, `log supervisord` | Admin lane; not cryosparc-tools job automation. |

Automation rule: `wait_for_done(error_on_incomplete=True)` is better than hand polling, but still inspect outputs/logs after completion.

---

## Live crosswalk

Live is not just a normal job graph. Use `SessionsAPI` / Live-specific helpers for session state and only use normal job APIs for exported/downstream jobs.

| GUI Live action | API surface | Notes |
|---|---|---|
| Create Live Session | `api.sessions.create(...)` / tools Live session helpers | Confirm version-specific signatures. |
| Start / pause session | `api.sessions.start`, `pause` | Pausing kills/marks active Live jobs complete per Live docs; understand side effects. |
| Configure compute resources | `update_compute_configuration`, `LiveComputeResources` | v5 has richer resource controls. |
| Update preprocessing / picking / 2D / ab-init / refine params | `update_session_params`, `update_phase2_*_params`, `Live*Params` models | These are Live params, not ordinary job params. |
| Exclude/reject exposures | `manual_reject_exposure`, `manual_unreject_exposure`, thresholds APIs | Maps to Live curation UI. |
| Update picking thresholds/templates | `update_picking_threshold_values`, `toggle_picking_template`, threshold selection APIs | Use after understanding the UI behavior. |
| Export particles/exposures | `create_and_enqueue_export_particles`, `create_and_enqueue_export_exposures` | Creates downstream export jobs. |
| Configuration profiles | `get/create/apply/update/delete_configuration_profile` | v5 profiles have compatibility caveats; see `version_caveats.md`. |
| Compact / restore session | `compact_session`, `restore_session` | Storage-management operation; verify before destructive cleanup. |

Guardrail: if the user is tuning Live visually during data collection, do not replace that with blind automation. Script only repeatable, version-checked operations.

---

## Admin / instance crosswalk

Some GUI/API surfaces are instance admin, not job automation. Prefer `cryosparcm` for service lifecycle and logs; use API for structured settings when appropriate.

| GUI/admin action | API / CLI surface | Preferred route |
|---|---|---|
| Show instance version | `api.config.get_version()` / `cryosparcm status` | Either; CLI gives process health too. |
| Set home-page banner | `api.config.set_instance_banner(...)` | API or `cryosparcm cli` with version-matched syntax. |
| Set login message | `api.config.set_login_message(...)` | API. |
| User management | `UsersAPI` / Admin Panel | GUI for routine; API for controlled bulk edits. |
| Lanes/workers/targets | `ResourcesAPI`, `cryosparcm worker ...`, `cryosparcw ...` | CLI for worker registration; API for inspection/structured edits. |
| File browser settings | `ConfigAPI` / `UsersAPI` file browser methods | API. |
| Restart/start/stop services | `cryosparcm restart/start/stop` | CLI only; not cryosparc-tools job API. |
| Logs | `cryosparcm log <service>`, `get_service_log` | CLI for live admin triage. |
| Backup/recover/update | `cryosparcm backup/recover/update/patch` | CLI/admin runbook. |

---

## Blueprint / Workflow crosswalk

| GUI feature | API surface | Use when |
|---|---|---|
| Copy parameters as blueprint JSON | `BlueprintsAPI`, job blueprint methods | Convert tuned GUI job parameters into shareable automation. |
| Create job from blueprint | `api.jobs.create_job_from_blueprint`, `apply_blueprint` | Recreate a configured job safely. |
| Workflows page | `WorkflowsAPI` | Reusable multi-job templates. |
| Apply workflow | `api.workflows.apply(...)` | One-click/batch pipeline application. |
| Set workflow job parameter | `api.workflows.set_job_param(...)` | Expose/override dataset-specific knobs. |

Use workflows when the human GUI recipe is the source of truth and the goal is repeatable processing. Use raw job orchestration when conditional Python logic is required.

---

## Destructive-action guardrails

- Do not delete/clear/kill/export/import projects or jobs just because the corresponding API exists.
- Treat `delete`, `delete_many`, `clear_many`, `delete_output_result_files`, `cleanup_data`, `archive`, `detach`, and `accept_failed_attach` as destructive/admin operations requiring explicit user intent and backups where relevant.
- Prefer creating a new External Job output over mutating existing output files or `.cs` metadata in place.
- Never manually edit another job's directory as a shortcut to make the GUI see new data.
- For project deletion/detach/attach, use official GUI/API/CLI paths only; never remove a project directory by shell without a project-state plan.

---

## Minimal GUI-to-script recipe

```text
# Pattern only; confirm exact method names/signatures against installed tools.
from cryosparc.tools import CryoSPARC

cs = CryoSPARC('<base-url>')
assert cs.test_connection()

project = cs.find_project('P3')
workspace_uid = 'W1'

# Discover from GUI/job register, not from display label alone.
job = project.create_job(workspace_uid, '<job_type_key>')

# Discover exact keys with job.print_param_spec() or copied GUI parameter JSON.
job.set_param('<param_key>', <value>)

# Discover input/output names with job.print_input_spec() and parent.print_output_spec().
job.connect(
    target_input='<child_input_group>',
    source_job_uid='<parent_job_uid>',
    source_output='<parent_output_group>',
)

# Queue and verify.
job.queue(lane='<lane_name>')
job.wait_for_done(error_on_incomplete=True)

# Load outputs after completion.
ds = job.load_output('<output_group>', slots=['<slot1>', '<slot2>'])
```

Checklist before running:
- Version checked (`api.config.get_version()` or `cryosparcm status`).
- `cryosparc-tools` version compatible with instance.
- Project/workspace/job UIDs verified.
- Job type key verified.
- Parameter keys verified from spec/GUI.
- Inputs/outputs/slots verified from spec/GUI.
- Lane/target resource choice verified.
- Timeout and failure handling defined.
- Logs/events captured on failure.

---

## Source inventory

- `13_cryosparc_tools_api.md` — automation mental model, lifecycle, safety rules.
- `14_cli_admin.md` — boundary between `cryosparcm` admin operations and job-level tools automation.
- `docs/per_page/application-guide__creating-and-running-jobs.md` — Builder, Job Cart, parameters, queue slide-over, chaining jobs.
- `docs/per_page/application-guide__inspecting-job-data.md` — Inputs/Parameters tab, Outputs tab, Metadata/Log, Comparison view.
- `docs/per_page/application-guide__low-level-results-interface.md` — output groups/results, slot replacement, passthroughs, result versions.
- `reference/cryosparc-tools/docs/guides/jobs.ipynb` — concrete tools examples: `create_job`, `set_param`, `connect`, `queue`, `wait_for_done`, `load_output`, downloads.
- `reference/cryosparc-tools/cryosparc/api.pyi` — API namespaces/method inventory.
- `reference/cryosparc-tools/cryosparc/models/job_spec.py` — job spec, input/output/result models, categories, builder tags.
- `reference/cryosparc-tools/cryosparc/models/job.py` — job model and status literals.
