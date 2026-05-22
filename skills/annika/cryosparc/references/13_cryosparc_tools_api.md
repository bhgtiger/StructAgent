# Topic 13 — cryosparc-tools API & Automation Patterns

## Scope
How to use `cryosparc-tools` to automate cryoSPARC: what the library is for vs the GUI and `cryosparcm` CLI, how to connect safely, how to orchestrate jobs (create / configure / connect / queue / wait / check / download / export), how to reuse GUI-built workflows, how to read job state and outputs, where the boundary with `cryosparcm` and external tooling lives, and what the common failure modes look like.

Mechanics that belong in adjacent pages are linked, not duplicated: GUI behavior in `docs/per_page/application-guide__creating-and-running-jobs.md`, workflow templating in `docs/per_page/application-guide__workflows.md`, output-group internals in `docs/per_page/application-guide__low-level-results-interface.md`, project/workspace shape in `docs/per_page/application-guide__projects-workspaces-and-live-sessions.md`, troubleshooting in `15_troubleshooting.md`, error strings in `17_error_lookup.md`.

This page deliberately avoids hard-coding exact Python method names beyond what the local source bundle attests. The authoritative API surface lives at `https://tools.cryosparc.com/` and in the public repository `https://github.com/cryoem-uoft/cryosparc-tools`. Before calling anything, the agent should confirm method/attribute names against the live docs or the installed package — both because the API evolves and because cryosparc-tools' minor version is expected to track the connected CryoSPARC minor version (see Version Compatibility below).

## 1. What cryosparc-tools is for vs GUI vs `cryosparcm` CLI

| Surface | Owns | Use when |
|---|---|---|
| **GUI (web app)** | Interactive job building, inspection, comparison, workflow templating, Live sessions | Manual processing, decision-making, picker thresholding, 2D selection, anything needing visual feedback |
| **`cryosparc-tools` (Python)** | Programmatic access to projects/workspaces/jobs, dataset I/O, custom workflows, third-party integration | Scripted pipelines, batch parameter sweeps, reading particle/exposure/volume metadata, external-job round-trips, scripted post-processing or QC |
| **`cryosparcm` CLI (master)** | Instance admin — start/stop, logs, supervisor/database, configure DB, recover, error reports, user management, project delete/attach/detach | Restarts, log reading, database/supervisor issues, lane management, instance recovery |

Key sourced facts:

- cryosparc-tools is an open-source Python library for **CryoSPARC v4.1+**, released first as Beta in v4.1, with use cases that explicitly include "Programmatically read and write exposure, particle and volume data", "Access project, workspace and job data", "Build and run jobs to orchestrate custom cryo-EM workflows" and "Extend CryoSPARC functionality with third-party software packages" (`docs/per_page/processing-data__cryosparc-tools.md`, `reference/release_notes/markdown/v4.1.md`).
- Parameter code names that drive scripted parameter setting can be **copied from the GUI's 'Inputs and Parameters' tab** when previewing a job — that is the canonical way to discover the exact `name` to use in a tools script (`reference/release_notes/markdown/v4.4.md`).
- cryosparc-tools / scripting failures show up in `cryosparcm log command_vis` together with the Python traceback. That log path is the first place to look when a tools script silently misbehaves (`17_error_lookup.md`).
- The full reference documentation for the library is hosted at `https://tools.cryosparc.com/` and source at `https://github.com/cryoem-uoft/cryosparc-tools` — both linked from the official guide (`docs/per_page/processing-data__cryosparc-tools.md`).

Advisor rule: if the task requires manual inspection (picker thresholding, 2D class selection, viewing volumes) keep it in the GUI; if it requires admin (restart, log capture, delete project) use `cryosparcm` (see `14_cli_admin.md`); only use cryosparc-tools when the value is *programmatic repetition, dataset manipulation, or orchestration*.

## 2. Connection, authentication, and safety

The library talks to a running CryoSPARC master over its HTTP API. The agent must not assume anything about credentials, ports, or schema; everything below is the safe pattern.

### Connection inputs

| Input | Notes |
|---|---|
| Base URL / host + base port | The same URL used to reach CryoSPARC from a browser. Tools versions ≥ v5 require only the base port forwarded; older tools required `BASE_PORT + 2`, `+3`, `+5` (`docs/per_page/processing-data__cryosparc-tools.md` and tools release context) |
| Email + password (recommended) | Standard interactive auth, normally obtained via the `python -m cryosparc.tools login` flow that mints a session token cached locally — confirm exact command name against live tools docs |
| License-key auth | Legacy / superadmin path; treat as deprecated and prefer email+password tokens |

Safe handling:

- **Never hard-code credentials in scripts.** Pull them from environment variables or a secrets store; the library is built to read standard `CRYOSPARC_*` env vars (verify exact names against live tools docs before relying on them).
- **Use one CryoSPARC user account per automation context** and respect the GUI permissions model — projects are shared explicitly, so a tools session can only see what its user can see (`docs/per_page/application-guide__projects-workspaces-and-live-sessions.md`).
- **Test the connection first.** Tools exposes a connectivity check that confirms the master is reachable and the token is valid. Run it once at the top of every script — a failed connection error gives a clearer signal than a downstream "object not found" error.

### Version compatibility

| Rule | Why it matters |
|---|---|
| Match the cryosparc-tools **minor** version to the CryoSPARC minor version (e.g. CryoSPARC v4.6.x → cryosparc-tools `~=4.6.0`) | Tools and master evolve in lockstep; a mismatched minor version commonly produces brittle errors, especially around workspace/session loading |
| Update tools immediately after a CryoSPARC update | v4.6 explicitly fixed cases where cryosparc-tools produced errors loading workspace/session objects (`reference/release_notes/markdown/v4.6.md`); v5.0 changed the public API so that internal `CryoSPARC.cli`, `CryoSPARC.rtp`, `CryoSPARC.vis` attributes were retired in favor of a unified API surface (consult the tools changelog at `https://tools.cryosparc.com/`) |
| Don't run an automation against an instance two or more minor versions behind without checking the changelog | The bundle calls this out for general troubleshooting and it applies equally to scripted workflows (`17_error_lookup.md`) |

### Permissions and filesystem visibility

- Tools that read raw files (movies, particles, micrographs) only see what the **user the master runs as** can see. A surprising fraction of "file not found" reports are namespace/permission mismatches, not bugs (`17_error_lookup.md`).
- For network filesystems where listed UNIX permissions are misleading, v5.0 introduced `CRYOSPARC_CLI_SKIP_ACCESS_CHECK=true` to disable filesystem permission checks for `cryosparcm` and `cryosparcw` command-line arguments (`reference/release_notes/markdown/v5.0.md`). Do not set this casually — it is an instance-level switch for known-broken NFS permission reporting.
- Never assume the project directory is locally mounted on the host running the script. If the agent is not co-located with the master, use the download/upload-by-path pattern rather than direct filesystem reads (see Data Access below).

### Live-schema caution

Both inputs/outputs and parameter names are job-type-dependent and version-dependent. Before scripting against a job type:

1. Open one example of that job type in the GUI.
2. Use the **'Inputs and Parameters' tab** in the job preview to copy the parameter code name (v4.4+).
3. Use the **Outputs tab / output-group sidebar** to identify the exact output group names and result names you'll need to connect or load (`docs/per_page/application-guide__inspecting-job-data.md`, `docs/per_page/application-guide__low-level-results-interface.md`).
4. Only then write the tools script. The agent should *not* invent parameter names from memory.

## 3. Concepts and IDs

cryosparc-tools mirrors the GUI model directly:

| Concept | UID format | Holds | Source |
|---|---|---|---|
| **Project** | `P<N>` (e.g. `P3`) | A project directory on disk; all jobs and intermediate/output data live inside it; strict isolation between projects | `docs/per_page/application-guide__projects-workspaces-and-live-sessions.md` |
| **Workspace** | `W<N>` (e.g. `W1`) | A logical grouping inside a project; no on-disk directory; a job can live in multiple workspaces | same |
| **Live Session** | Distinct session ID | A Live workspace plus streaming preprocessing/picking/2D/3D state, project-scoped | same; `25_cryosparc_live.md` |
| **Job** | `J<N>` (e.g. `J42`) | One processing unit with inputs, parameters, outputs, logs, on-disk directory | `docs/per_page/application-guide__creating-and-running-jobs.md` |
| **Output group** | Named (e.g. `particles`, `volume`, `exposures`) | Bundle of related output results | `docs/per_page/application-guide__low-level-results-interface.md` |
| **Output result** | Named within a group (e.g. `blob`, `ctf`, `location`, `alignments3D`, `mscope_params`) | One typed slice of metadata; can be referenced by `J<N>.<group>.<result>.<version>` (final iteration is `F`) | same |

Reading job state from cryosparc-tools maps to the same surface the GUI exposes (`docs/per_page/application-guide__inspecting-job-data.md`):

- Title, type, status, parameters, inputs, outputs, on-disk directory.
- A status string drawn from the standard set (building / queued / launched / started / running / waiting / completed / killed / failed).
- The event log (text + figure stream) and the text job log (the same log shown under the GUI's Metadata → Log tab).
- Per-output-group results, queryable per output result and per iteration.

When the agent needs a value from a job, prefer reading via the tools API over scraping the GUI or parsing files; the tools API already understands passthroughs (CryoSPARC and cryosparc-tools both auto-fetch passthrough information, so passthrough results behave like normal outputs in scripts) (`docs/per_page/application-guide__low-level-results-interface.md`).

## 4. Job orchestration pattern

Every cryosparc-tools workflow follows the same lifecycle as the GUI's Builder (`docs/per_page/application-guide__creating-and-running-jobs.md`):

```
create → set params → connect inputs → (optionally) connect specific result slots → queue → wait → check → load / download / export
```

The recipe and the per-step verification below stay stable across versions; only the exact method names should be confirmed against `https://tools.cryosparc.com/`.

### Step-by-step pattern

| Step | What you're doing | What to verify before moving on |
|---|---|---|
| 1. Resolve / open instance | Connect with credentials, run a health/test-connection probe | Connectivity success message; user identity matches the account expected to own outputs |
| 2. Find or create project + workspace | Look up by UID (`P3`, `W1`) or create a new workspace inside an existing project | Project is accessible to the script's user; you are writing into the intended workspace |
| 3. Create the job | Specify job type by its code name (e.g. `import_movies`, `homo_abinit`, `homo_reconstruct`, `class_2D`, `homo_refine` — confirm names against `cs.job_register` / live docs); supply optional initial input connections and parameter dict at creation | Job comes back in `building` status |
| 4. Set parameters | Set parameters individually using the **exact parameter code name copied from the GUI's Inputs and Parameters tab** (v4.4+, `reference/release_notes/markdown/v4.4.md`) | Parameter set returns success; job is still `building` and has no build error |
| 5. Connect inputs | Wire output groups from parent jobs into the new job's input groups; for surgical replacement at the result level, use a low-level result connection that mirrors the GUI's Low Level Results Interface (`docs/per_page/application-guide__low-level-results-interface.md`) | Each required input slot is populated; no red error markers; passthrough resolution looks sane |
| 6. Queue | Queue to a specific lane (or leave unspecified for master/local), optionally pin to a hostname and/or specific GPU indexes, optionally pass cluster variables | Status transitions to `queued` then `launched` / `started` |
| 7. Wait | Block until status reaches a terminal state (`completed`, `killed`, `failed`) with an explicit timeout and explicit error-on-incomplete flag | Final status is `completed`; if not, capture last events and `cryosparcm joblog` output before retrying anything |
| 8. Check | Read job status, errors/warnings, event log, and key outputs | Errors/warnings panel is empty; expected output groups are present and non-empty |
| 9. Load / download / export | Read output datasets (e.g. micrographs, particles), download specific files from the job directory, download CS/MRC files, or trigger a job export | Datasets have expected slot columns; downloaded files non-zero size; for export, downstream consumer can parse |

### Tools-specific verification rules

- **Verify status, not absence of exceptions.** A job can fail without raising in the script — always inspect the final `status`. Tools provides explicit "wait until status in {completed, killed, failed}" semantics with an optional "error on incomplete" flag; use it instead of polling by hand.
- **Re-fetch the job object after structural changes.** After connect / set-param / queue, the cached job model is stale; tools exposes a refresh call for exactly this. Don't make decisions off a stale `status`.
- **Read the dashboard's Errors and Warnings.** The v5.0 dashboard surfaces these prominently (`docs/per_page/application-guide__inspecting-job-data.md`); scripted runs should fetch and assert on the same data, not just the binary completed/failed split.
- **For interactive job types (Select 2D Classes, Curate Exposures, Manual Picker, Volume Tools)**, the queue→wait pattern doesn't fit: these jobs require a human or a scripted "interactive action" call. Decision Tree 11 in `18_decision_trees.md` explicitly flags `Job must be queued on the master node` as a symptom of running an interactive job on the wrong lane.

### Minimal recipe template (illustrative — confirm exact names against `https://tools.cryosparc.com/`)

```text
# Pseudocode — verify exact method/attribute names before running
cs = CryoSPARC(<url>, <email>, <password>)
assert cs.test_connection()

project   = cs.find_project("P3")
workspace = project.find_workspace("W1")

job = project.create_job(
    workspace_uid="W1",
    type="<job_type_code_name>",
    connections={"<input_group>": ("<parent_uid>", "<parent_output_group>")},
    params={"<param_code_name>": <value>, ...},
    title="<descriptive title>",
)

job.queue(lane="<lane_name>")     # confirm queue method signature in live docs
status = job.wait_for_done(error_on_incomplete=True, timeout=<seconds>)
# Inspect outputs only after status == "completed"
dataset = job.load_output("<output_group>")
```

The above is a **pattern**, not a verified API call. Before pasting into a production script, the agent should: (a) confirm exact attribute and method names from the live docs at `https://tools.cryosparc.com/`; (b) confirm the job type's code name from `cs.job_register` or the GUI builder; (c) confirm parameter and input/output names from the GUI's Inputs/Outputs tabs as described in §2.

## 5. Workflow templating (clone & reuse GUI-built workflows)

CryoSPARC ships a first-class **Workflows** feature (`docs/per_page/application-guide__workflows.md`, `docs/per_page/processing-data__automated-workflows.md`). For repeatable end-to-end pipelines this is almost always a better choice than building the job graph from scratch in cryosparc-tools.

Key sourced properties:

- Workflows are *templates* of pre-connected, pre-parameterized job graphs that can be applied into any workspace. They support both top-to-bottom pipelines and partial branches dependent on existing jobs.
- Workflows are portable: exported as a `.json` file containing **no instance-specific identifiers or job UIDs**, so they move cleanly between instances and between users.
- When applying a template, a "Queue on Apply" toggle queues every job in the workflow to a chosen lane atomically.
- Some parameters are surfaced as "flagged" knobs during apply (e.g. for GPCR automation: extraction box size, blob diameter and separation, F-crop factor, exposure-group regex, reference paths), and others can be locked so users cannot override them at apply time.
- The published GPCR automation Workflow is a worked example of an end-to-end repeat-target pipeline (`docs/per_page/processing-data__automated-workflows.md`).

### When to use workflows vs raw tools scripting

| Situation | Pick |
|---|---|
| Reusable, named pipeline you want collaborators to apply by clicking | **Workflow** (built in the GUI, exported as JSON, re-imported elsewhere) |
| You need to thread custom Python logic between jobs (e.g. external picker, custom QC, conditional branch) | **cryosparc-tools** (or workflows that contain External Jobs, see §7) |
| You want one-click batch over many datasets with the same recipe | **Workflow + small tools driver** that imports the workflow, sets the dataset-specific knobs, and applies it |
| You want bare scripted job orchestration with no GUI artifact | **cryosparc-tools** end-to-end |

### Safe parameterization rules for workflow templates

- **Don't tune more than one thing per branch.** This is the general tuning rule in `16_tuning_recipes.md` and it applies equally to workflow templates: keep most knobs at sane defaults, expose only the dataset-specific ones (per the GPCR template, that's typically box size, blob diameter, exposure-group regex, reference volumes/masks).
- **Lock parameters that should never drift.** Locked parameters are read-only at apply time and signal intent.
- **Pilot first.** Even when applying a trusted workflow, the import + Patch Motion + Patch CTF triage rule from `02_import.md` / `03_preprocessing.md` still applies — pilot on a small subset before committing the full dataset.
- **Keep provenance.** Workflows preserve the parent/child connections that the GUI uses for the related-jobs sidebar and the comparison view (`docs/per_page/application-guide__inspecting-job-data.md`). Don't reach around the workflow to mutate connections after apply — re-clone if a recipe needs to change.
- **Be aware of cross-version edges.** v5.0 fixed an issue where connections between Workflow jobs would fail in some cases due to a connection edge case (`reference/release_notes/markdown/v5.0.md`); if a workflow apply behaves oddly across versions, check the changelog before debugging.

## 6. Data access patterns

cryosparc-tools is the right surface for moving structured cryo-EM metadata between cryoSPARC and external code. The mental model is the same as the GUI's Low Level Results Interface: jobs produce output **groups** containing typed output **results**.

### Reading

| Goal | Path |
|---|---|
| Read a job's particle / exposure / volume metadata as a dataset | Load the relevant output group from the job (e.g. `particles`, `exposures`, `micrographs`); the returned dataset includes slot columns like `blob`, `ctf`, `location`, `alignments3D` etc. (`docs/per_page/application-guide__low-level-results-interface.md`) |
| Read a specific output result only | Request only the slots you need; for an alignment2D shift you only need the `alignments2D` slot, not the whole group |
| Read at a specific iteration | Specify the output version; final iteration is `F`. The GUI's Outputs tab also lets you download specific iterations of low-level results (e.g. `alignments3D` at iteration 2) (`docs/per_page/application-guide__downloading-and-exporting-data.md`) |
| Read raw files (CS, MRC) when project directory is mounted | Open the file directly with the dataset / MRC loaders from the same project directory the master sees |
| Read raw files (CS, MRC) when project directory is **not** mounted | Use the project- or job-scoped download helpers to pull files from the master to the script host |
| Read event log / job log | Tools mirrors the GUI's Event Log + Log tabs; for archival, the GUI's "Download Job Event Log" produces a PDF (job-log-PDF generation is a v4.0+ feature) (`docs/per_page/application-guide__downloading-and-exporting-data.md`) |
| Read a job report (event log + system logs) for debugging | GUI feature, see `docs/per_page/application-guide__downloading-and-exporting-data.md`; same artifact can be downloaded over the network |

### Writing (back into cryoSPARC)

| Goal | Path |
|---|---|
| Write modified metadata back into the project as a new result | Create an **External Job** in the workspace and save the new dataset as its output; this is the supported way to round-trip metadata so downstream jobs can connect to it cleanly |
| Inherit unchanged slots from a parent | Use passthrough so the External Job only owns the slots it actually modifies, and downstream jobs still see the parent's `ctf`, `location`, etc. (`docs/per_page/application-guide__low-level-results-interface.md`) |
| Replace exactly one slot of a downstream job's input | Use the Low Level Results Interface pattern — drag-equivalent at the API level — to swap a specific result (e.g. replace `blob` from a downsampled refinement with `blob` from the full-size Extract from Micrographs job) without touching the other slots (`docs/per_page/application-guide__low-level-results-interface.md`) |

### Exporting

| Goal | Path |
|---|---|
| Share a single job's results with another user / instance | Export the job (GUI action; the exported `.cs` file *contains* passthrough metadata that an external program reading `.cs` directly otherwise would not have) (`docs/per_page/application-guide__low-level-results-interface.md`, `docs/per_page/application-guide__downloading-and-exporting-data.md`) |
| Move a whole project | Export the project — see the data-management guide referenced by `docs/per_page/application-guide__downloading-and-exporting-data.md` and `14_cli_admin.md` |
| Bulk-download a list of jobs / projects / workspaces / sessions as CSV | GUI CSV download; respects filters and sort (`docs/per_page/application-guide__downloading-and-exporting-data.md`) |

### Destructive-change avoidance

- **Treat existing jobs and their files as read-only by default.** A tools script should produce *new* External Job outputs rather than overwriting files inside an existing job's directory; the GUI's data-cleanup tools and `delete_project` are the supported destruction paths (`docs/per_page/application-guide__projects-workspaces-and-live-sessions.md`).
- **Never remove a project directory from the filesystem by hand.** Project directories managed by attached CryoSPARC projects must be removed via the *Delete Project* GUI action or the `delete_project()` CLI method (`docs/per_page/application-guide__projects-workspaces-and-live-sessions.md`).
- **Don't write into another job's directory.** Write outputs into a new External Job's directory (or upload-by-path within its directory). This keeps provenance intact and avoids corrupting passthroughs.
- **Re-extract instead of editing pixel-size or box size in place.** This is a general cryoSPARC discipline (`16_tuning_recipes.md`) but it bites scripted users the hardest because it is so easy to mutate columns in a dataset.

## 7. External jobs and automation boundaries

External Jobs are the supported extension point: a "job" inside a CryoSPARC workspace that is driven by Python code outside the master. Use them for:

- Plugging in a third-party tool (custom picker, custom denoiser, custom classifier, model-building helper) and emitting its results as a normal output group that downstream cryoSPARC jobs can consume.
- Surgical metadata edits (re-centered particles, filtered exposures) that should appear in the project history as a discrete job, not as a hidden in-place mutation.
- Custom QC: scripted checks (e.g. for corrupt micrographs) that produce a new output set the next job can connect to.

External Jobs respect the same input/output-group model as built-in jobs — they declare inputs, optionally declare expected output slots, and finalize when their script signals completion (`docs/per_page/application-guide__low-level-results-interface.md`, `docs/per_page/processing-data__cryosparc-tools.md`).

### When *not* to use cryosparc-tools

| Need | Use instead |
|---|---|
| Restart the instance, read supervisor or database logs, recover state | `cryosparcm` CLI — see `14_cli_admin.md` |
| Configure lanes, workers, GPUs | `cryosparcw connect`, `cryosparcm` admin commands |
| Submit to / inspect SLURM/PBS scheduler | The cluster's own tooling; cryoSPARC only sees the heartbeat, and an "OOM-kill" appears in the cluster log first (`17_error_lookup.md`) |
| Pure file conversion that doesn't need round-trip into cryoSPARC | Standalone scripts on `.cs` / `.mrc` / `.star` files — the cryosparc-tools dataset format documentation describes the file format if you must read it directly (linked from the official guide for v4.0-and-older projects) |
| Interactive thresholding or 2D class selection | GUI; or a Workflow with the interactive job stage explicitly carved out |
| Live preprocessing / picking / streaming refinement | Live UI (`25_cryosparc_live.md`); export to a main project before scripting against the data |

Advisor rule: cryosparc-tools is for **orchestration and data movement**; `cryosparcm` is for **administration**; the GUI is for **judgment**.

## 8. Failure modes and troubleshooting

The full debug mental model lives in `15_troubleshooting.md`; the full error-string index lives in `17_error_lookup.md`. The table below distills the failure modes that specifically bite cryosparc-tools users.

| Symptom | Likely cause | First check | Fix |
|---|---|---|---|
| `Could not connect to CryoSPARC at ...` / health check fails | Master not running, wrong URL/port, token expired, port not forwarded | `cryosparcm status`, browser-based GUI access to the same URL, valid login session | Bring the master up; re-run the login flow; for SSH tunnels, ensure correct port (v5+ only needs base port; older tools need `+2`, `+3`, `+5`) |
| Connect succeeds but downstream calls fail with version/incompatibility errors | cryosparc-tools minor version drifted from CryoSPARC minor version | `cs_version` from the API vs installed tools version | `pip install --force cryosparc-tools~=<master_minor>.0`; if running a pre-release master, install tools from the matching git branch |
| `Project P# not found` / `Workspace W# not found` / `Job J# not found` | Project/workspace/job UID wrong, or the script's user does not have access | List the user's projects via tools; verify GUI access for the same user account | Use the correct UID; share the project with the automation user via the GUI's *Share With Users* (`docs/per_page/application-guide__projects-workspaces-and-live-sessions.md`) |
| Loading workspace or session object errors out on older instances | Pre-v4.6 bug in tools loading workspace/session objects | Master/tools version | Update master to v4.6+ (`reference/release_notes/markdown/v4.6.md`) |
| Job stuck in `queued` indefinitely | Lane has no capacity; or cluster scheduler is holding it; or no GPU/CPU resources match request | `cryosparcm log command_core`; for cluster lanes the scheduler log | Free resources, fix lane config, requeue with corrected `gpus` / `lane` parameters |
| Job marked failed immediately on launch (`non-zero exit status 255`, `FAILED TO LAUNCH ON WORKER NODE`) | SSH / shell / banner / env on the worker, **not** the cryo-EM | `cryosparcm log command_core`, then non-interactive `ssh worker "true"` | Silence `.bashrc`/`.profile`, re-run `cryosparcw connect`, re-run worker tests (`17_error_lookup.md`) |
| Cluster job "stuck" with no traceback | Scheduler OOM-killed the worker; master only sees a heartbeat loss | SLURM/PBS log for OOM-kill | Reduce memory demand / box size / GPU count; do **not** rewrite cryosparc-tools script first (`17_error_lookup.md`) |
| `set_param` / `connect` returns "build error" or silently no-ops | Wrong parameter / input / output name, or job no longer in `building` status | Print `job.params` / `job.inputs` / `job.outputs` after refresh; copy parameter code names from the GUI's Inputs and Parameters tab | Use the GUI-sourced code name; or rebuild the job from scratch (`reference/release_notes/markdown/v4.4.md`) |
| Output looks present but `load_output` returns empty / wrong shape | Wrong iteration version (asked for an iteration that wasn't produced); wrong slot list; passthrough mismatch | Inspect the job's outputs panel in the GUI; check the related-jobs view for what was actually produced | Request `version="F"` for the final iteration; request `slots="all"` to include passthroughs |
| `alignments3D_multi` missing or mismatched class count in downstream job | v5.0 fix changed semantics: when multiple particle set inputs are connected, `alignments3D_multi` is **removed** rather than passed through, to avoid class-count mismatch failures (`reference/release_notes/markdown/v5.0.md`) | Master version | Update to v5.0+; restructure the input wiring so each connected set has a coherent class count |
| File path resolves on the script host but not from the worker (`file not found`, `invalid path` during caching) | Master and worker see different namespaces; symlink only resolves on one side | Resolve the path from the worker shell as the cryoSPARC owner (`17_error_lookup.md`) | Fix mount/symlink so master and worker agree on the path |
| Unexpected `Permission denied` on NFS / Lustre even though the file is accessible | Listed UNIX permissions don't match the true permissions on the network filesystem | Try the path manually as the cryoSPARC owner | v5.0+ supports `CRYOSPARC_CLI_SKIP_ACCESS_CHECK=true` to disable that check at the instance level — set with care (`reference/release_notes/markdown/v5.0.md`) |
| `Job must be queued on the master node` | Trying to script an interactive job (Select 2D Classes, Curate Exposures, Manual Picker, Volume Tools) onto a worker lane | Job type | Queue interactive jobs on the master lane and complete them either manually in the GUI or via the interactive-action API (`18_decision_trees.md`, Tree 11) |
| Workflow apply succeeds in GUI but fails when driven by script | Workflow-connection edge case (fixed in v5.0) or stale workflow JSON | Master version; workflow JSON checksum | Update master; re-export and re-import the workflow (`reference/release_notes/markdown/v5.0.md`) |
| Script silently misbehaves with no Python traceback | The exception was raised inside the master command_vis service | `cryosparcm log command_vis` plus the Python traceback (`17_error_lookup.md`) | Read the master log, then fix script — do not retry blindly |

### Triage rule for scripted runs

The general troubleshooting rule from `15_troubleshooting.md` and Decision Tree 11 in `18_decision_trees.md` applies:

1. Read the exact error / traceback as text — pasted, not screenshotted.
2. Classify the failure bucket: version, worker/shell/SSH, filesystem/permission, GPU/CPU/RAM/scheduling, workflow misuse/mismatched inputs.
3. Check whether a known fix in the changelog already exists.
4. Apply the smallest safe corrective action (restart job → clear and rerun → restart cryoSPARC → reduce resources).
5. Escalate to environment / data-path debugging only after the small fix fails.

Crucially: **do not rewrite cryosparc-tools logic to work around a launch/path/version failure.** Fix the environment first.

## 9. Advisor defaults

Crisp rules for any future assistant driving cryosparc-tools:

1. **Confirm the API before calling it.** Look up exact method/attribute names at `https://tools.cryosparc.com/` (or the installed package), not from memory. Parameter and output names come from the GUI's Inputs and Parameters / Outputs tabs.
2. **Match tools minor version to CryoSPARC minor version.** Re-check after every CryoSPARC update.
3. **Authenticate via login token, not embedded credentials.** Test connection at the top of every script.
4. **Read GUI-sourced code names for parameters and inputs/outputs.** Never invent them.
5. **Use the standard lifecycle.** create → set params → connect → queue → wait_for_done → check status + warnings → load/download. Refresh the job object after each structural change.
6. **Always check final status and the Errors and Warnings panel,** not just "did the call return".
7. **Prefer External Jobs to in-place mutation.** Round-trip new data through a real workspace job so passthroughs and provenance stay intact.
8. **Prefer Workflows for repeatable pipelines** and a tools driver for cross-pipeline glue. Don't reimplement the GUI workflow apply path in raw tools code unless there's a real reason.
9. **Pilot before committing.** Patch Motion + Patch CTF + a small box-size pilot for new datasets, even when applying a trusted workflow.
10. **Stay in the right surface.** GUI for judgment, `cryosparcm` for admin, cryosparc-tools for orchestration and dataset I/O. Don't admin from tools, don't judge in tools.
11. **Don't shell into project directories to "fix" files.** Use Delete Project / detach via the GUI or `cryosparcm`; use External Jobs for new outputs.
12. **When uncertain about a parameter, output, or method, inspect live.** Print the job spec, list outputs, copy code names from the GUI — this is faster and safer than guessing.
13. **For scripting failures, look in `cryosparcm log command_vis` first**, then the Python traceback, then job-level logs.
14. **Don't tune cryosparc-tools code to mask a cryo-EM problem.** A blurred ligand, a streaky 2D class, a featureless refinement — these belong in `04_picking.md`, `05_extraction_2d.md`, `07_refinement.md`, etc., not in `params={...}` adjustments in a tools script.

## 10. Cross-links

- GUI job building and lifecycle: `docs/per_page/application-guide__creating-and-running-jobs.md`
- Inspecting jobs (dashboard, charts, related jobs, comparisons): `docs/per_page/application-guide__inspecting-job-data.md`
- Output groups and the Low Level Results Interface (passthroughs, slot swapping): `docs/per_page/application-guide__low-level-results-interface.md`
- Projects, workspaces, Live sessions, sharing, deletion: `docs/per_page/application-guide__projects-workspaces-and-live-sessions.md`
- Downloading and exporting (jobs, projects, CSVs, event logs, job reports): `docs/per_page/application-guide__downloading-and-exporting-data.md`
- Workflow templates: `docs/per_page/application-guide__workflows.md`
- End-to-end automation (GPCR repeat-target template): `docs/per_page/processing-data__automated-workflows.md`
- Library overview and links: `docs/per_page/processing-data__cryosparc-tools.md`
- Troubleshooting mindset and triage: `15_troubleshooting.md`
- Error-string lookup, version-fixed bugs: `17_error_lookup.md`
- Tuning recipes and per-stage knobs (do **not** mutate via tools without reading): `16_tuning_recipes.md`
- Decision trees, including the failure-bucket router: `18_decision_trees.md`
- Live session handoff to production projects: `25_cryosparc_live.md`
- Import / preprocessing prerequisites for any scripted pipeline: `02_import.md`, `03_preprocessing.md`

## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

- `docs/per_page/processing-data__cryosparc-tools.md`
- `docs/per_page/application-guide__creating-and-running-jobs.md`
- `docs/per_page/application-guide__inspecting-job-data.md`
- `docs/per_page/application-guide__low-level-results-interface.md`
- `docs/per_page/application-guide__projects-workspaces-and-live-sessions.md`
- `docs/per_page/application-guide__downloading-and-exporting-data.md`
- `docs/per_page/application-guide__workflows.md`
- `docs/per_page/processing-data__automated-workflows.md`
- `reference/release_notes/markdown/v4.0.md`
- `reference/release_notes/markdown/v4.1.md`
- `reference/release_notes/markdown/v4.2.md`
- `reference/release_notes/markdown/v4.3.md`
- `reference/release_notes/markdown/v4.4.md`
- `reference/release_notes/markdown/v4.5.md`
- `reference/release_notes/markdown/v4.6.md`
- `reference/release_notes/markdown/v5.0.md`
- `17_error_lookup.md`
- `15_troubleshooting.md`
- `16_tuning_recipes.md`
- `18_decision_trees.md`
- `topic_plan.md`
- `plan.md`
