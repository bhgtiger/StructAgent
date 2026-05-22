# Topic 14 — CLI / Admin Operations (`cryosparcm`, `cryosparcw`)

## Scope
How to operate a cryoSPARC instance from the command line as an admin or admin-assistant: the `cryosparcm` (master) and `cryosparcw` (worker) mental model, the safe command families and what they own, where logs and config live conceptually, the runbooks that cover the most common operational events (restart / update / worker offline / DB-or-storage growth / migration / recovery), and the safety boundaries that distinguish "do this now" from "capture diagnostics first."

This page deliberately avoids fabricating CLI syntax. The exact flag names, sub-commands, and arguments differ between the **v5.0+** and **≤v4.7** documentation pages (CryoSPARC explicitly notes that `cryosparcm cli` arguments may change between versions — `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0__cryosparcm-cli-reference-v5.0.md`). When a recipe requires precise syntax, the agent should:

1. Identify the master and worker versions first (`cryosparcm status`, `cryosparcw version`).
2. Run `cryosparcm COMMAND --help` (or `cryosparcw COMMAND --help`) on the target host.
3. Cross-check against the version-matched reference page in `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0/…` or `…__management-and-monitoring-4.7/…`.

What belongs elsewhere: Python automation patterns and the `cryosparc-tools` library are in `13_cryosparc_tools_api.md`; GUI surface (admin panel, instance manage dialog, message of the day) is in `docs/per_page/application-guide__instance-management.md` and `docs/per_page/application-guide__admin-panel.md`; error-string lookup is in `17_error_lookup.md`; troubleshooting mental model is in `15_troubleshooting.md`; lane/queue/GPU mechanics live in `21_gpu_lane_queue.md`; install/connect-worker mechanics live in `01_installation_admin.md`; disk/storage growth lifecycle in `24_disk_and_storage.md`.

---

## 1. CLI vs GUI vs `cryosparc-tools` — what the admin page owns

| Surface | Owns | Use when | Source |
|---|---|---|---|
| **`cryosparcm` (master)** | Start/stop/restart, supervisor and database lifecycle, logs, user/license/admin tasks, worker/lane/cluster scheduler management, instance-wide config and env, update/patch, backup/restore/recover, instance error reports, maintenance mode, `cryosparcm cli "api…"` for programmatic master API | Anything affecting the master instance, lanes, the database, or system state shared across users | `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0__cryosparcm-reference-v5.0.md` |
| **`cryosparcw` (worker)** | Worker-side version, deps install, patch install, env export, GPU detection, connecting a worker to a master | Anything that has to run on the worker host (GPU listing, applying a patch the master already downloaded, registering the worker) | `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0__cryosparcw-reference-v5.0.md` |
| **GUI admin / instance tab** | View/edit users, manage tokens, view lanes/targets read-only, backups history, notifications, set message-of-the-day | Day-to-day user admin and read-only inspection of lanes/targets | `docs/per_page/application-guide__instance-management.md`, `docs/per_page/application-guide__admin-panel.md` |
| **`cryosparc-tools` (Python)** | Programmatic job orchestration, dataset I/O, scripted parameter sweeps | Automation of *job-level* work, not instance admin | `13_cryosparc_tools_api.md` |

Rule of thumb for the advisor: **admin work that mutates instance state → `cryosparcm` on the master**; **work that mutates worker registration / worker software → `cryosparcw` on the worker**; **GUI for day-to-day user creation and read-only inspection**; **`cryosparc-tools` for orchestrating jobs, not for restarting the instance**.

Important access constraints from the official docs:

- `cryosparcm` instance management commands "must be run from the UNIX user account that owns the CryoSPARC installation, and always on the same machine on the network that `cryosparc_master` was installed on." Otherwise the command can return `UnauthorizedException` (`…cryosparcm-reference-v5.0.md`).
- `cryosparcw` commands must be run **on the worker** node, from the worker installation directory (or with the worker `bin/` on `PATH`) (`…cryosparcw-reference-v5.0.md`, `…cryosparcw-4.7.md`).
- These constraints can be relaxed via `CRYOSPARC_FORCE_HOSTNAME` and `CRYOSPARC_FORCE_USER` in `cryosparc_master/config.sh`, but the defaults exist for a reason and should not be flipped without a written change record (`…environment-variables-v5.0.md`).

---

## 2. Master/worker mental model

```
┌────────────────────────────────────────────────────────────┐
│  Master node  (cryosparc_master, runs cryosparcm)          │
│  ─ Web app / API service                                   │
│  ─ command_core   (job scheduler / state machine)          │
│  ─ command_vis    (UI/viz + cryosparc-tools handler)       │
│  ─ command_rtp    (Live real-time processor)               │
│  ─ database       (MongoDB; the source of truth)           │
│  ─ supervisord    (process supervisor for the above)       │
│  ─ run/           (auto-exported instance config)          │
└────────────────────────────────────────────────────────────┘
              │  HTTP API + SSH to launch jobs
              ▼
┌────────────────────────────────────────────────────────────┐
│  Worker node(s)  (cryosparc_worker, runs cryosparcw)       │
│  ─ Compute programs and libraries used by jobs             │
│  ─ Optional local SSD scratch path                         │
│  ─ Registered to one or more master scheduler lanes        │
└────────────────────────────────────────────────────────────┘
```

Process-list shape from `cryosparcm status` (v4.3.1 example output is in `…cryosparcm-4.7.md`; v5.0 names are similar but include `app_api` processes whose process count is governed by `CRYOSPARC_API_PROCS`, default `3`, `…environment-variables-v5.0.md`):

- `app`, `app_api` (and `app_api_dev`, `app_legacy`, `app_legacy_dev`)
- `command_core`
- `command_vis`
- `command_rtp`
- `database`

A healthy instance has every non-`_dev` / non-`_legacy` process in `RUNNING` state, and the status output ends with "License is valid" (`docs/per_page/setup-configuration-and-management__troubleshooting.md`).

Practical implications:

- **The database is the source of truth.** Job/project/user state lives in MongoDB; file system paths and project directories carry the data those records point at. If the DB is intact but the master process is dead, the data is fine; if the DB files are corrupt, project directories alone are not enough — a recent instance config export (`cryosparc_master/run/cryosparc_instance_config_*.tar`) is the bridge back (`…guide-instance-recovery-v5.0.md`).
- **The master sends commands to workers over SSH.** Many "worker offline" or "FAILED TO LAUNCH" symptoms are SSH/shell-banner problems, not cryo-EM problems (`17_error_lookup.md`, `15_troubleshooting.md`).
- **A worker host without `cryosparc_worker` installed cannot be added.** The master can patch or connect workers it has on file, but the worker package must already exist on the target machine (`…cryosparcm-reference-v5.0.md` → `cryosparcm worker connect`, `…cryosparcw-reference-v5.0.md` → `cryosparcw connect`).

---

## 3. Safe command families (`cryosparcm`)

The tables below group sourced command families. Exact flags are referenced to their source page; the agent should always confirm against `cryosparcm COMMAND --help` on the target instance before running anything destructive.

### 3.1 Instance status & lifecycle

| Family | What it does | Source |
|---|---|---|
| `cryosparcm status` | Print master install path, version, per-process status, license validity, exported global config vars | `…cryosparcm-reference-v5.0.md`, `…cryosparcm-4.7.md` |
| `cryosparcm start` / `stop` / `restart` | Bring the supervisor + all services up, down, or down-then-up; can target a single sub-service (e.g. `cryosparcm start database`) | `…cryosparcm-reference-v5.0.md`, `…guide-reduce-database-size-v4.3.md` |
| `cryosparcm env` | Print the env vars CryoSPARC sets; intended for `eval $(cryosparcm env)` to load the same env in a subshell | `…cryosparcm-reference-v5.0.md` |
| `cryosparcm call <cmd>` / `cryosparcm python` / `cryosparcm ipython` / `cryosparcm icli` | Run a command, Python, IPython, or the interactive CryoSPARC shell with the master env loaded | `…cryosparcm-reference-v5.0.md`, `…cli-4.7.md` |
| `cryosparcm test install` / `cryosparcm test workers` | Verify install (license, services, GPU worker present) and per-worker LAUNCH / SSD / GPU health; optional `--test-tensorflow` / `--test-pytorch` | `…guide-installation-testing-with-cryosparcm-test.md` |
| `cryosparcm maintenancemode on|off|status` | Pause / resume the queue so running jobs finish but no new jobs launch; **does not pause Live sessions** automatically | `…guide-maintenance-mode-and-configurable-user-facing-messages.md` |

### 3.2 Logs

| Family | What it does | Source |
|---|---|---|
| `cryosparcm log <service>` | Stream a master service log; `q` to quit. Common services: `command_core`, `command_vis`, `command_rtp`, `database`, `webapp`, `supervisord` | `15_troubleshooting.md`, `17_error_lookup.md`, `docs/per_page/setup-configuration-and-management__troubleshooting.md` |
| `cryosparcm joblog Px Jx` | Tail the **stdout log** of a specific job (master-side capture) | `15_troubleshooting.md`, `…guide-installation-testing-with-cryosparcm-test.md` |
| Event log + job error report (GUI) | Per-job event log lives in the GUI's Event Log tab; a full job error report (event log + job log + browser + system logs from the last week) is downloadable from the Event Log tab | `…guide-download-error-reports.md` |
| Instance Logs tab → system error report | Admin panel exports an instance-wide diagnostic bundle (instance info, browser, last week of system logs) | `…guide-download-error-reports.md` |

Which log to open first (canonical first-pass triage from `17_error_lookup.md`):

| Symptom | First log |
|---|---|
| Job runtime error or traceback | GUI Event Log → then `job.log` in the job directory → then `cryosparcm joblog Px Jx` |
| Worker launch / "FAILED TO LAUNCH" / SSH banner / `non-zero exit status 255` | `cryosparcm log command_core` |
| DB / supervisor / socket | `cryosparcm status`, `cryosparcm log database`, `cryosparcm log supervisord` |
| cryosparc-tools or scripting silently misbehaving | `cryosparcm log command_vis` + the Python traceback |
| Live UI / RTP / streamlog | `cryosparcm log command_vis`, streamlog tab, browser console |

If the job is on a cluster and looks stuck without a traceback, **check the SLURM/PBS log for OOM-kill before anything else** — the master often only sees a heartbeat loss (`17_error_lookup.md`, `15_troubleshooting.md`).

### 3.3 Users, license, admin

| Family | What it does | Source |
|---|---|---|
| Admin Panel (GUI) | Create users, manage roles, view reset tokens, view instance logs | `docs/per_page/application-guide__admin-panel.md`, `…tutorial-user-management.md` (legacy ≤v3.3 CLI surface; v4.0+ uses the Admin Panel) |
| `cryosparcm cli "api.…"` | Programmatic master API: query/edit users, projects, jobs, lanes; e.g. `set_instance_banner(...)` for message-of-the-day | `…cryosparcm-cli-reference-v5.0.md`, `…guide-maintenance-mode-and-configurable-user-facing-messages.md` |
| `CRYOSPARC_LICENSE_ID` env var | License identity for the instance; `cryosparcm test install` validates against the license server `https://get.cryosparc.com` | `…guide-installation-testing-with-cryosparcm-test.md`, `…environment-variables-v5.0.md`, `docs/per_page/setup-configuration-and-management__troubleshooting.md` |

Caveat: the legacy `tutorial-user-management.md` page documents a CLI-based user-management flow for ≤v3.3 only — for v4.0+, the **Admin Panel** is the supported surface (`…tutorial-user-management.md`, `docs/per_page/application-guide__admin-panel.md`).

### 3.4 Workers, lanes, scheduler

| Family | What it does | Source |
|---|---|---|
| `cryosparcm worker connect …` (v5.0+) | Register or update a worker from the master side; sets `--lane`, `--cpus`, `--rams`, `--gpus`/`--no-gpu`, `--ssdpath`, `--ssdquota`, `--ssdreserve` | `…cryosparcm-reference-v5.0.md` |
| `cryosparcm worker disconnect --worker <name>` (v5.0+) | Remove a worker from the scheduler | `…cryosparcm-reference-v5.0.md` |
| `cryosparcm worker update` / `worker patch` (v5.0+) | Push updates / patches to all workers or a given worker | `…cryosparcm-reference-v5.0.md` |
| `cryosparcw connect …` (v5.0+ and ≤v4.7) | Same effect, run **on the worker**; required env vars `CRYOSPARC_LICENSE_ID`, `CRYOSPARC_MASTER_HOSTNAME`, `CRYOSPARC_BASE_PORT` | `…cryosparcw-reference-v5.0.md`, `…cryosparcw-4.7.md` |
| `cryosparcw gpulist` (≤v4.7) / `cryosparcw info --gpu` (v5.0+) | List GPUs visible to the worker; the canonical "is the GPU detected" check | `…cryosparcw-4.7.md`, `…cryosparcw-reference-v5.0.md` |
| `cryosparcm cluster example|dump|connect|remove` | Manage cluster (SLURM/PBS) lane definitions via `cluster_info.json` + `cluster_script.sh` | `…cryosparcm-4.7.md`, `…cryosparcm-reference-v5.0.md` |
| `cryosparcm cli "add_scheduler_lane(…)"` / `add_scheduler_target_cluster(…)` (≤v4.7 API) | Programmatic lane creation; v5.0+ exposes the equivalent under `api.…` | `…cli-4.7.md`, `…cryosparcm-cli-reference-v5.0.md` |

Worker registration is the moment when SSH connectivity, paths, and GPU/SSD config get persisted into the master DB. **Re-run `cryosparcw connect` (or `cryosparcm worker connect`) any time hostname, SSH path, SSD path, GPU set, or lane membership changes** — this is what regenerates the entry the scheduler uses (`15_troubleshooting.md`, `…cryosparcw-reference-v5.0.md`).

### 3.5 Config and environment

| Family | What it does | Source |
|---|---|---|
| `cryosparc_master/config.sh` | Master-side env vars: `CRYOSPARC_LICENSE_ID`, `CRYOSPARC_MASTER_HOSTNAME`, `CRYOSPARC_DB_PATH`, `CRYOSPARC_BASE_PORT`, `CRYOSPARC_DB_ENABLE_AUTH`, `CRYOSPARC_DB_MIN_SPACE_GB`, `CRYOSPARC_API_PROCS`, `CRYOSPARC_HEARTBEAT_SECONDS`, `CRYOSPARC_AUTO_EXPORT_INSTANCE_CONFIG_*`, `CRYOSPARC_CLI_SKIP_ACCESS_CHECK`, `CRYOSPARC_FORCE_HOSTNAME`, `CRYOSPARC_FORCE_USER`, `CRYOSPARC_DISABLE_EXTERNAL_REQUESTS`, scheduler timeouts, etc. **Restart with `cryosparcm restart` after changes.** | `…environment-variables-v5.0.md`, `…cryosparcm-reference-v5.0.md` |
| `cryosparc_worker/config.sh` | Worker-side env vars (mirrors a subset of the master vars) | `…environment-variables-v5.0.md` |
| `cryosparcm env` / `cryosparcw env` | Print the env CryoSPARC would set; `eval $(cryosparcm env)` loads it into a debugging shell | `…cryosparcm-reference-v5.0.md`, `…cryosparcw-reference-v5.0.md` |
| `cryosparc_master/run/cryosparc_instance_config_*.tar` | Auto-exported instance config snapshot (lanes, targets, users, project attachments); default cadence is hourly (`CRYOSPARC_AUTO_EXPORT_INSTANCE_CONFIG_INTERVAL_HOURS = 1`). This file is the input to `cryosparcm recover`. **Back this up to off-master storage.** | `…environment-variables-v5.0.md`, `…guide-instance-recovery-v5.0.md` |

Notable defaults worth knowing without inventing new ones:

- `CRYOSPARC_HEARTBEAT_SECONDS = 180`. If a job stops reporting for longer than this (e.g. slow network, busy worker, silent error), the master marks the job failed. Increase only for known-busy or slow-link environments (`…environment-variables-v5.0.md`).
- `CRYOSPARC_DB_MIN_SPACE_GB = 5`. The master refuses to start the database below this free-space threshold; address as a storage problem, not by lowering the floor (`…environment-variables-v5.0.md`).
- `CRYOSPARC_DB_ENABLE_AUTH = true`. Leave it on unless instructed otherwise (`…environment-variables-v5.0.md`).
- v5.0 added `CRYOSPARC_CLI_SKIP_ACCESS_CHECK = true` as an *escape hatch* for NFS / Lustre filesystems whose listed UNIX permissions misreport effective access. It disables filesystem permission checks for `cryosparcm` and `cryosparcw` command-line arguments. **Do not set it casually**; it is for known-broken permission reporting only (`reference/release_notes/markdown/v5.0.md`, `…environment-variables-v5.0.md`).
- v4.0+ added `--offline` and `--skip_workers` flags for `cryosparcm errorreport` (skip DB stats / skip worker info), useful when the instance is partly down (`reference/release_notes/markdown/v4.0.md`).

### 3.6 Update / patch / test

| Family | What it does | Source |
|---|---|---|
| `cryosparcm update` (optionally `--version=vX.Y.Z`) | Master update; on workstations also updates connected workers. **Make a DB backup first.** | `…guide-updating-to-cryosparc-v4.md`, `…guide-updating-to-cryosparc-v5.md`, `…cryosparcm-4.7.md` |
| `cryosparcm patch [--check|--download|--install|--force]` | Apply or stage patches on master + workers; clusters should `--download` then `--install`, not auto-patch | `…cryosparcm-4.7.md` |
| `cryosparcw patch [-f <file>] [--force]` | Apply a previously-downloaded patch on a single worker | `…cryosparcw-reference-v5.0.md`, `…cryosparcw-4.7.md` |
| `cryosparcw update` / `cryosparcw deps` | Manual worker update from `cryosparc_worker/cryosparc_worker.tar.gz`; `deps` (re)installs Python + external deps | `…cryosparcw-reference-v5.0.md` |
| `cryosparcm test install` / `cryosparcm test workers <project_uid> [--test all|gpu|launch|ssd] [--test-tensorflow] [--test-pytorch] [--target <hostname>]` | Verify install / per-worker LAUNCH / SSD / GPU; **requires a project to run inside** | `…guide-installation-testing-with-cryosparcm-test.md` |

v4 → v5 update has special considerations (`…guide-updating-to-cryosparc-v5.md`):

- Backwards-compatible down to v4.4 only; if you need to downgrade further, downgrade to v4 first, then to your target.
- The v5 update performs a **database upgrade** with a dry-run validation phase that may take up to ~1 hour for large instances; the UI is unavailable during this step.
- If validation finds invalid project content, the agent is offered the chance to detach those projects (data on disk is not deleted; detached projects can be reattached to another v4 instance).

### 3.7 Backup, recovery, migration

| Family | What it does | Source |
|---|---|---|
| `cryosparcm backup` | Dump the MongoDB contents to a single backup file (path can be redirected to other storage if the DB volume is tight). Recommended **before every update or maintenance**. | `…cryosparcm-4.7.md`, `…guide-reduce-database-size-v4.3.md`, `…guide-updating-to-cryosparc-v4.md` |
| `cryosparcm restore` | Restore from a `cryosparcm backup` file; also one of the routes to reduce database size when `compact` is insufficient | `…guide-reduce-database-size-v4.3.md` |
| `cryosparcm compact` (v4.3+) | Run MongoDB's `compact` on collections; **may or may not shrink files**. Verify by comparing post-compact DB size to a fresh `cryosparcm backup` size. | `…guide-reduce-database-size-v4.3.md`, `reference/release_notes/markdown/v4.3.md` |
| `cryosparcm recover -f <instance_config.tar>` (v5.0+) | Rebuild an instance from the auto-exported config snapshot in `cryosparc_master/run/`; reattaches projects, skips deleted ones, restores detached ones to the DB. **Requires a fresh empty DB.** | `…guide-instance-recovery-v5.0.md`, `reference/release_notes/markdown/v5.0.md` |
| `cryosparcm icli` → `api.jobs.get_symlinks`, `api.jobs.update_directory_symlinks(...)` (v5.0+) / `cli.get_project_symlinks`, `cli.get_job_symlinks` (v4.0–v4.7.1) | Repair import-job symlinks when raw movie/micrograph/particle data has moved on disk | `…tutorial-migrating-your-cryosparc-instance.md` |
| Detach / attach project, archive / unarchive | Per-project lifecycle moves; documented in data management guides; UI-driven in v4.0+ | `…guide-data-management-in-cryosparc-v4.0.md` (referenced from `…guide-data-cleanup-v4.3.md` and `…tutorial-migrating-your-cryosparc-instance.md`) |

### 3.8 Database / storage cleanup

| Family | What it does | Source |
|---|---|---|
| Data Cleanup tool (GUI, v4.3+) | Project- or workspace-scoped: clear non-final jobs, clear preprocessing jobs, delete certain statuses; respects "mark as final" / "ancestor of final" protection | `…guide-data-cleanup-v4.3.md` |
| Mark Job as Final | Protects a job and its ancestors from clear/delete; **always set finals before bulk cleanup**; v5.0+ adds an "Include final ancestor jobs" toggle for preprocessing cleanup | `…guide-data-cleanup-v4.3.md` |
| `cryosparcm cli "clear_intermediate_results(project_uid, …)"` / `cleanup_data(…)` / `cleanup_jobs(…)` / `clear_job(…)` (≤v4.7 API; equivalent under `api.…` in v5.0+) | Programmatic versions of the above for scripted cleanup | `…cli-4.7.md`, `…cryosparcm-cli-reference-v5.0.md` |
| `cryosparcm compact` → optional `cryosparcm backup` → `cryosparcm restore` | Two-stage DB-size reduction recipe documented in `…guide-reduce-database-size-v4.3.md` |
| Detach project | Reduces DB load by removing the project's metadata from the running instance while the on-disk directory stays intact | `…tutorial-migrating-your-cryosparc-instance.md`, `…guide-data-management-in-cryosparc-v4.0.md` |

Storage growth is best addressed *before* it forces the DB minimum-free-space check to fire. See `24_disk_and_storage.md` for the lifecycle view.

### 3.9 Error reports

| Family | What it does | Source |
|---|---|---|
| `cryosparcm errorreport [--offline] [--skip_workers]` | Build an instance-level error report; flags added in v4.0 to support reporting from a partly-down instance | `reference/release_notes/markdown/v4.0.md` |
| GUI → Event Log tab → "Download job error report" | Per-job report: event log + job log + browser diagnostics + last week of system logs; option to include/exclude event-log images | `…guide-download-error-reports.md` |
| GUI → Admin → Instance Logs → "Download system error report" | Per-instance: instance info + browser diagnostics + last week of system logs | `…guide-download-error-reports.md` |

**Pull a report before reproducing the failure** when the failure is intermittent — running the job again can rotate the relevant log lines out of the captured window.

---

## 4. `cryosparcw` — worker-side surface

`cryosparcw` is the worker analogue of `cryosparcm`, scoped to one worker's installation and its registration with the master.

| Command | What it does | Source |
|---|---|---|
| `cryosparcw version` | Show worker version; used to check master/worker version match | `…cryosparcw-reference-v5.0.md` |
| `cryosparcw env` | Print env CryoSPARC sets; `eval $(cryosparcw env)` loads it into a debugging shell | `…cryosparcw-reference-v5.0.md` |
| `cryosparcw call <cmd>` | Run a command inside a transient worker shell environment (e.g. `cryosparcw call which python`) | `…cryosparcw-4.7.md` |
| `cryosparcw connect [--license …] [--master …] [--port …] [--worker …] [--lane …] [--cpus …] [--rams …] [--gpus … | --no-gpu] [--ssdpath …] [--ssdquota …] [--ssdreserve …] [--sshstr …]` | Register or update this worker in the master scheduler (v5.0+ syntax; ≤v4.7 uses `--update`, `--nogpu`, `--nossd`, `--newlane`) | `…cryosparcw-reference-v5.0.md`, `…cryosparcw-4.7.md` |
| `cryosparcw gpulist` (≤v4.7) / `cryosparcw info --gpu` (v5.0+) | List GPUs visible to the worker process — the canonical CUDA-visibility check | `…cryosparcw-4.7.md`, `…cryosparcw-reference-v5.0.md` |
| `cryosparcw update` / `cryosparcw deps` / `cryosparcw patch` | Manual worker update, dep install, patch install | `…cryosparcw-reference-v5.0.md` |
| `cryosparcw ipython` | Worker env IPython shell | `…cryosparcw-4.7.md` |
| `cryosparcw newcuda <path>` (CryoSPARC ≤v4.3 only) | Point the worker at a different CUDA toolkit; **v4.4+ bundles its own CUDA** and removed this command | `…cryosparcw-4.7.md` |

Practical rules:

- **Worker version must match master.** A mismatch produces "Version mismatch! Worker and master versions are not the same. Please update." (`docs/per_page/setup-configuration-and-management__troubleshooting.md`).
- `cryosparcw connect` is the primary tool for re-registering after worker-side changes (SSD path, GPU list, new lane). The full options list in the docs takes precedence over any memorized syntax.
- For network-filesystem environments where reported UNIX permissions misrepresent actual access, set `CRYOSPARC_CLI_SKIP_ACCESS_CHECK=true` in **both** master and worker `config.sh` and restart (`reference/release_notes/markdown/v5.0.md`).

---

## 5. Where logs and config live (conceptually)

Avoid memorizing absolute paths beyond what the docs attest; layout varies by install.

| Thing | Where (conceptually) | How to find it |
|---|---|---|
| Master install | The path printed at the top of `cryosparcm status` (e.g. `/home/<user>/cryosparc_master`) | `cryosparcm status` |
| Master config | `cryosparc_master/config.sh` (loaded by every `cryosparcm` invocation) | `…environment-variables-v5.0.md` |
| Master env (live) | `cryosparcm env` | `…cryosparcm-reference-v5.0.md` |
| Database files | The directory pointed at by `CRYOSPARC_DB_PATH` | `cryosparcm status` exports `CRYOSPARC_DB_PATH` |
| Instance-config exports | `cryosparc_master/run/cryosparc_instance_config_*.tar` | `…guide-instance-recovery-v5.0.md` |
| Per-service logs | Streamed by `cryosparcm log <service>` | `15_troubleshooting.md` |
| Per-job logs | GUI Event Log + `cryosparcm joblog Px Jx` + the job directory's `job.log` | `17_error_lookup.md` |
| Worker install | The directory you `cd` into to run `bin/cryosparcw` | `…cryosparcw-reference-v5.0.md` |
| Worker config | `cryosparc_worker/config.sh` | `…environment-variables-v5.0.md` |
| Cluster lane scripts | The `cluster_info.json` + `cluster_script.sh` in the directory used at `cryosparcm cluster connect` time | `…cryosparcm-4.7.md` |
| Project on disk | Project's own directory; each job is a sub-directory inside it; `imported/` contains symlinks back to raw movie/particle paths | `…tutorial-migrating-your-cryosparc-instance.md` |

When in doubt: `cryosparcm status` prints the install path + exported env vars + per-service state in one place — start there.

---

## 6. Operational runbooks

Each runbook is "ordered checklist + escape hatch." None of these are syntax-precise; the agent should always pair each step with the matching `--help` and the version-specific reference page before executing.

### 6.1 Before a restart or update

1. **Notify users.** Set the Message of the Day via `cryosparcm cli "set_instance_banner(True, '<title>', '<body>')"` (`…guide-maintenance-mode-and-configurable-user-facing-messages.md`).
2. **Maintenance mode on**: `cryosparcm maintenancemode on`. Confirm with `cryosparcm maintenancemode status`. Remember it does **not** auto-pause Live sessions — pause those by hand in the GUI.
3. **Drain the queue.** Allow already-running jobs to finish. Confirm idle state.
4. **Pause Live sessions** explicitly in the GUI (the maintenance-mode guide flags this in a hint box).
5. **`cryosparcm backup` the database.** Redirect output to off-master storage if the DB volume is tight. Required by the v4 update guide and good practice everywhere.
6. **Confirm `cryosparc_master/run/cryosparc_instance_config_*.tar` is current.** Copy the latest one off-master too — this is what `cryosparcm recover` needs if the DB is later lost.
7. **Run the action** (`cryosparcm restart`, `cryosparcm update`, `cryosparcm patch`, `cryosparcm worker update`, `cryosparcm worker patch`, etc.).
8. **Verify**: `cryosparcm status` (all non-`_dev`/non-`_legacy` services `RUNNING`, license valid), `cryosparcm test install`, `cryosparcm test workers <project_uid> --test all` if any worker config or driver was touched.
9. **Maintenance mode off**: `cryosparcm maintenancemode off`. Clear the banner if appropriate.

For a v4 → v5 update specifically, also re-read `…guide-updating-to-cryosparc-v5.md` because of the database upgrade dry-run / detach-invalid-projects step and the OS / NVIDIA driver compatibility requirements (CryoSPARC v5 uses CUDA 12.8 and drops Kepler / compute capability ≤3.5 GPUs).

### 6.2 After a failed job

1. **Capture diagnostics first, then act.** Download the **Job Error Report** from the Event Log tab (`…guide-download-error-reports.md`); also save the exact error text as text, not a screenshot (`15_troubleshooting.md`).
2. Classify the failure bucket per `15_troubleshooting.md` (version-fixed bug / worker-shell-SSH / filesystem-path-permission / GPU-CPU-RAM-scheduling / workflow-misuse).
3. Open the log indicated by the bucket (`17_error_lookup.md` first-pass triage — see §3.2 above).
4. If error matches a known fix-in-version, check the `reference/release_notes/markdown/*.md` and consider updating first (e.g. v4.5.3+240807 fixed RBMC re-centering, v4.6.2 hardened SSD cache on cluster FS, v5.0.5 fixed local refinement plotting under intermediate-iteration plots).
5. Try the smallest safe corrective action — restart the job, or clear and rerun, before changing parameters or rebuilding the pipeline.

Anti-pattern: rewriting refinement parameters to "work around" what is really a launch / path / permission / version failure (`18_decision_trees.md` Tree 11).

### 6.3 Web app down / instance not starting

1. `cryosparcm status` — does it return at all? Are all non-`_dev`/non-`_legacy` services `RUNNING`? Is the license valid? (`docs/per_page/setup-configuration-and-management__troubleshooting.md`).
2. If any service is `STOPPED` / `EXITED`: `cryosparcm log <service>` to read the error.
3. If `cryosparcm restart` does not bring it back: confirm `CRYOSPARC_DB_PATH` has at least `CRYOSPARC_DB_MIN_SPACE_GB` (default 5 GB) free; confirm the DB directory is intact; check `cryosparcm log database`, `cryosparcm log supervisord`.
4. Confirm the master process is fully stopped before retrying — the troubleshooting guide explicitly references "Incomplete CryoSPARC shutdown" as a recurring class of bug; use the OS process tools to verify there is no orphaned `supervisord` / `mongod` (`docs/per_page/setup-configuration-and-management__troubleshooting.md`, `…guide-instance-recovery-v5.0.md`).
5. Check firewall + base port reachability if the web UI is the only thing inaccessible.
6. If the DB itself is suspect → §6.6 (recovery).

### 6.4 Worker offline / GPU not visible / launch failure

1. **Read the exact error.** `non-zero exit status 255` → SSH problem (auth, host key, banner noise from `.bashrc`/`.profile`); `FAILED TO LAUNCH ON WORKER NODE` / `failed to connect link` → env / ports / hostname; `Job must be queued on the master node` → interactive job on a non-master lane (`17_error_lookup.md`, `18_decision_trees.md`).
2. From the master, run a non-interactive SSH probe (`ssh worker "true"`) and confirm it returns silently. Banner output from `.bashrc` / `.profile` is a common silent killer.
3. On the worker: `cryosparcw info --gpu` (v5.0+) or `cryosparcw gpulist` (≤v4.7). `nvidia-smi` for driver / GPU state.
4. Confirm worker `cryosparc_worker` version matches master (`cryosparcw version` vs `cryosparcm status`).
5. Re-run `cryosparcw connect` (or `cryosparcm worker connect`) with the current `--sshstr`, `--lane`, `--ssdpath`, `--gpus`. This regenerates the scheduler entry.
6. `cryosparcm test workers <project_uid> --test all --target <hostname>` to validate LAUNCH / SSD / GPU end-to-end. Add `--test-tensorflow` / `--test-pytorch` only when the failing job uses TF (Topaz/DeepEMhancer) or PyTorch (3D Flex) — and only after `cryosparcw install-3dflex` for the PyTorch test (`…guide-installation-testing-with-cryosparcm-test.md`).
7. If `nvidia-smi` shows the right GPUs but jobs still don't see them and the host has multiple GPUs / multiple concurrent jobs, recall the v4.6.2 transparent-hugepages note and the v4.4.1+240110 RBMC `EXCLUSIVE_PROCESS` fix — version sanity check (`reference/release_notes/markdown/v4.6.md`, `reference/release_notes/markdown/v4.4.md`).

### 6.5 Database / storage growth

1. **Confirm there is a problem.** Look at the size of the directory at `CRYOSPARC_DB_PATH` and compare with the size of a fresh `cryosparcm backup` (`…guide-reduce-database-size-v4.3.md`).
2. **In the GUI**, mark important jobs as **Final** so cleanup tools cannot destroy them or their ancestors (`…guide-data-cleanup-v4.3.md`).
3. Run **Data Cleanup** at project or workspace scope: start with "clear non-final jobs"; add "clear preprocessing jobs" only after verifying the v5.0+ "Include final ancestor jobs" toggle is set the way you want (`…guide-data-cleanup-v4.3.md`).
4. **DB-side cleanup pass:**
   - Maintenance mode on, drain queue, `cryosparcm stop`.
   - `cryosparcm start database` (DB only).
   - `cryosparcm backup`.
   - `cryosparcm compact`. **Not guaranteed** to shrink the files.
   - Verify by comparing the post-compact DB size to a freshly-taken backup size.
   - If compact didn't help, the backup-restore path is the more aggressive option (`…guide-reduce-database-size-v4.3.md`).
   - `cryosparcm restart`, maintenance mode off.
5. **For storage growth (not DB growth)**, see `24_disk_and_storage.md`; broadly: clear intermediate results (v4.2.1 project-level option), restack particles to drop rejected ones, detach finished projects whose directories you want off the active instance.

### 6.6 Migration / recovery

**Migration (instance moved, paths moved, host changed)** — `…tutorial-migrating-your-cryosparc-instance.md`:

1. Database backup before anything.
2. **Raw data paths moved**: from `cryosparcm icli`, walk all jobs in the affected project(s) with `api.jobs.get_symlinks(...)` (v5.0+) / `cli.get_project_symlinks(...)` / `cli.get_job_symlinks(...)` (v4.0–v4.7.1), confirm what is broken, then `api.jobs.update_directory_symlinks(project_uid, job_uid, prefix_cut, prefix_new)` to retarget them.
3. **Project directories moved**: detach in the old location, attach in the new location.
4. **DB / master moved**: copy the database directory and the `cryosparc_master/run/*.tar` exports; reinstall master at the new host with the same version; restart and validate.
5. **Worker hosts changed**: re-run `cryosparcw connect` from each new worker.

**Recovery from DB loss / corruption** — `…guide-instance-recovery-v5.0.md`:

1. Stop CryoSPARC; verify *fully* stopped at the OS level.
2. Locate the latest `cryosparc_master/run/cryosparc_instance_config_*.tar` and **copy it outside the install directory** so it survives whatever you do next.
3. `mkdir` a fresh, empty database directory.
4. Edit `cryosparc_master/config.sh` so `CRYOSPARC_DB_PATH` points at the new empty directory.
5. `cryosparcm start`. The instance comes up empty — that is expected.
6. `cryosparcm recover -f <path-to-instance-config.tar>`. This restores the config and reattaches projects; skips deleted projects; reattaches detached projects' records so they are visible again; skips any project that fails to attach (which can be reattached manually afterwards).
7. After recovery, audit: do the user list, lanes, attached projects match what you remember? Run `cryosparcm test install` and a per-worker `cryosparcm test workers <project_uid> --test all`.

If a recent instance-config export is **not** available, recovery is materially harder — the recovery guide says you must contact CryoSPARC support. The defense is regular off-master backups of `cryosparc_master/run/cryosparc_instance_config_*.tar` (`…guide-instance-recovery-v5.0.md`).

### 6.7 Multi-user permissions

`…unix-permissions-and-data-access-control.md`:

- CryoSPARC must be installed under its own UNIX account; that account is the one all jobs run as on the master side.
- A common pattern is to create a `cryosparc` group, put project directories under that group, and use `chmod g+ws` so files created inside inherit the group (the `setgid` bit also propagates to subdirectories). This lets analysts read each other's outputs without being able to clobber them.
- The guide explicitly notes that **even with per-lab UNIX groups, the `cryosparc` user can still see all data**, because that is required for CryoSPARC to function. Lab-level isolation at the file-system level is *not* a substitute for in-app project permissions.
- Permissions changes here are sensitive; defer to the local sysadmin and the official guide, do not improvise.

---

## 7. Safety boundaries

| Don't | Why | Source |
|---|---|---|
| Delete files in a project directory by hand to free space | Breaks the DB ↔ disk consistency CryoSPARC depends on; use Data Cleanup or job clear/delete from the UI / API | `…guide-data-cleanup-v4.3.md`, `…guide-data-management-in-cryosparc-v4.0.md` |
| Update without `cryosparcm backup` first | v4 → v5 changes MongoDB schema; downgrade past v4.4 is blocked; a bad upgrade with no backup is unrecoverable | `…guide-updating-to-cryosparc-v5.md`, `…guide-updating-to-cryosparc-v4.md` |
| Skip Maintenance Mode for a "quick" restart | Running jobs are killed; users see failures with no warning; banner + maintenance mode give them notice and let in-flight work finish | `…guide-maintenance-mode-and-configurable-user-facing-messages.md` |
| Forget to pause Live sessions explicitly | Maintenance mode does not auto-pause Live; jobs spawned inside Live keep launching until paused | `…guide-maintenance-mode-and-configurable-user-facing-messages.md` |
| Set `CRYOSPARC_CLI_SKIP_ACCESS_CHECK=true` as a "fix" for any permission error | It is for **known-broken** UNIX-permission reporting on specific NFS / Lustre setups. Setting it elsewhere hides real permission bugs. | `reference/release_notes/markdown/v5.0.md`, `…environment-variables-v5.0.md` |
| Set `CRYOSPARC_FORCE_HOSTNAME` / `CRYOSPARC_FORCE_USER` casually | They exist to allow running `cryosparcm` from another host/user; the default safety check prevents two admins from racing the master from different shells | `…environment-variables-v5.0.md` |
| Reproduce the failing job before downloading the error report | The job error report includes the last week of system logs; rerunning may rotate the relevant lines out | `…guide-download-error-reports.md` |
| Delete the `cryosparc_master/run/cryosparc_instance_config_*.tar` files | They are the only thing that makes `cryosparcm recover` possible without contacting support | `…guide-instance-recovery-v5.0.md` |
| Manually edit MongoDB documents | v5 added strong validation; manual edits in v4 are a documented cause of v5 upgrade aborts | `…guide-updating-to-cryosparc-v5.md` |
| Run `cryosparcm` as root, or from a different UNIX user, or from a host other than where the master was installed | Produces `UnauthorizedException`; the defaults are there to prevent state corruption across users | `…cryosparcm-reference-v5.0.md` |
| Skip the v4 → v5 dry-run validation phase | The phase identifies invalid documents *before* committing the upgrade; skipping it is what the guide tells you not to do — re-downgrade and fix instead | `…guide-updating-to-cryosparc-v5.md` |

General rule: **capture diagnostics → notify users → quiesce the instance → take the action → verify → re-open**. Skip any one of those and you trade short-term speed for long-term debugging cost.

---

## 8. Failure modes table (admin-side)

| Symptom | First CLI/admin checks | Escalation / source |
|---|---|---|
| `cryosparcm status` returns `UnauthorizedException` | Confirm you are the install-owner UNIX user and on the master host | `…cryosparcm-reference-v5.0.md` |
| Some services `STOPPED`/`EXITED` in `cryosparcm status` | `cryosparcm log <service>` (especially `database`, `supervisord`); `cryosparcm restart` | `docs/per_page/setup-configuration-and-management__troubleshooting.md` |
| Web UI unreachable but status looks healthy | Firewall / base-port reachability; reverse proxy if used; check `app` and `app_api` are running | `…troubleshooting.md`, `…environment-variables-v5.0.md` |
| Worker jobs fail instantly with `non-zero exit status 255` | SSH banner / `.bashrc` noise; non-interactive `ssh worker "true"`; re-run `cryosparcw connect` | `17_error_lookup.md`, `15_troubleshooting.md` |
| `FAILED TO LAUNCH ON WORKER NODE` / `failed to connect link` | `cryosparcm log command_core`; confirm worker version matches master; check ports/hostname; `cryosparcm test workers ... --target` | `17_error_lookup.md`, `…guide-installation-testing-with-cryosparcm-test.md` |
| GPU missing on worker | `cryosparcw info --gpu` (v5.0+) / `cryosparcw gpulist` (≤v4.7); `nvidia-smi`; driver / CUDA compat (v5 → CUDA 12.8 → compute capability 5.0–12.0) | `…cryosparcw-reference-v5.0.md`, `…guide-updating-to-cryosparc-v5.md` |
| `Version mismatch! Worker and master versions are not the same` | `cryosparcw version` vs `cryosparcm status`; apply matching patch/update; `cryosparcw connect` after update | `…troubleshooting.md`, `…cryosparcm-4.7.md` |
| Cluster job "stuck" with no traceback | SLURM/PBS scheduler log for OOM-kill *first*; `cryosparcm joblog`; then in-app event log | `17_error_lookup.md` |
| Live session stopped finding new exposures | Compare instance version to known fixes (v4.2.1+230403); restart session; check path/wildcard/recursion/timestamps | `reference/release_notes/markdown/v4.2.md`, `18_decision_trees.md` (Tree 11) |
| `pymongo … ServerSelectionTimeoutError` / `database: ERROR (spawn error)` | `cryosparcm log database`, `cryosparcm log supervisord`; confirm `CRYOSPARC_DB_PATH` has ≥ `CRYOSPARC_DB_MIN_SPACE_GB` free; confirm no orphan `mongod` from incomplete shutdown | `17_error_lookup.md`, `…environment-variables-v5.0.md`, `…troubleshooting.md` |
| DB directory has grown huge | `cryosparcm backup` → compare backup size vs DB size → `cryosparcm compact` → re-verify; if compact didn't help, backup-restore path | `…guide-reduce-database-size-v4.3.md` |
| "file not found" / "invalid path" after a move | `cryosparcm icli` → `api.jobs.get_symlinks(...)` / `update_directory_symlinks(...)` (v5.0+) or `cli.get_project_symlinks` / `get_job_symlinks` (v4.0–v4.7.1); confirm worker shell sees the path as the master user | `…tutorial-migrating-your-cryosparc-instance.md`, `17_error_lookup.md` |
| Job tagged failed seconds after launch on a busy cluster, no traceback | Heartbeat loss: check `CRYOSPARC_HEARTBEAT_SECONDS` (default 180); raise only if the link is genuinely slow/busy | `…environment-variables-v5.0.md` |
| Update aborted in dry-run validation phase (v4 → v5) | Read the `cryosparc_master/run/validation_results_*.json`; choose to detach the flagged invalid projects or downgrade to v4 and fix | `…guide-updating-to-cryosparc-v5.md` |
| Cannot download / install / update CryoSPARC | `echo $CRYOSPARC_LICENSE_ID`; `curl https://get.cryosparc.com/checklicenseexists/$LICENSE_ID` should return `{"success": true}`; deactivate any active Conda envs | `…troubleshooting.md` |
| Web UI looks ok but message-of-the-day shows wrong content | `cryosparcm cli "get_instance_banner()"` then `set_instance_banner(...)` to correct | `…guide-maintenance-mode-and-configurable-user-facing-messages.md` |

---

## 9. Advisor defaults

Defaults the future agent should follow when it has the choice:

1. **Identify versions first.** `cryosparcm status` + `cryosparcw version` before any non-trivial admin action.
2. **`--help` is canonical.** When syntax matters, run `cryosparcm COMMAND --help` (or `cryosparcw COMMAND --help`) on the target host and trust that over any cached memory.
3. **Capture diagnostics before acting** — error report, exact error text, version, job type, recent changes.
4. **Maintenance mode + DB backup + instance-config copy** is the standard prelude to any restart-class or update-class action.
5. **Mark Final before any cleanup** — both the GUI Data Cleanup tool and scripted `cleanup_*` API calls respect Final / Ancestor-of-Final flags.
6. **One change at a time.** Restart → re-test → next change. This is the same principle that runs through `15_troubleshooting.md` and `16_tuning_recipes.md`.
7. **Trust the version-matched reference page over the forum.** Many forum threads predate fixes in v4.2.1, v4.3, v4.4.1+240110, v4.5.3, v4.6.2, v5.0; check `reference/release_notes/markdown/` before chasing a forum recipe.
8. **For `cryosparcm cli "api.…"`, look up the exact function** at `https://tools.cryosparc.com/api/cryosparc.api.html` (the v5.0+ CLI is a thin wrapper over this API surface) before assembling a call.
9. **Prefer the GUI for user CRUD** in v4.0+ — `…tutorial-user-management.md` is documented as ≤v3.3 only.
10. **Leave `CRYOSPARC_DB_ENABLE_AUTH=true`, `CRYOSPARC_FORCE_HOSTNAME=false`, `CRYOSPARC_FORCE_USER=false` at defaults** unless there is a written reason to change them.

---

## 10. Red flags

If any of these are true, **stop and escalate** rather than firing the next command:

- Anyone says "I'll just delete a few files in the project directory to free space." — let Data Cleanup or `cleanup_*` do it; the DB will get out of sync otherwise.
- A planned `cryosparcm update` without a fresh `cryosparcm backup` and a copy of `cryosparc_master/run/cryosparc_instance_config_*.tar` off-master.
- A planned v4 → v5 update on an instance that is more than two versions behind without a v4.4+ stopover first.
- A failing-job triage where nobody captured the **exact error string** before re-running the job.
- A "restart cryoSPARC" plan that doesn't include Maintenance Mode + pausing Live.
- `cryosparcm` invoked as root or as a non-owner UNIX user, "just this once."
- Setting `CRYOSPARC_CLI_SKIP_ACCESS_CHECK=true` to bypass a "permission denied" error without first confirming the file system is the known-broken kind (NFS / Lustre with misreported UNIX perms).
- Recovering a corrupted DB without a recent `cryosparc_master/run/*.tar` — there is no good recovery path here; pause and contact CryoSPARC support.
- Reinstalling or restoring without first verifying *no* `supervisord` / `mongod` process is still running ("incomplete shutdown" is a recurring class of bug in the troubleshooting guide).
- A worker that "should have all GPUs" but `cryosparcw info --gpu` / `cryosparcw gpulist` shows fewer — do not raise the worker's `--gpus` arg manually; fix the underlying driver / CUDA / hugepage issue first.

---

## 11. Cross-links

- Python / scripted job orchestration: `13_cryosparc_tools_api.md`
- Troubleshooting mental model and failure-bucket triage: `15_troubleshooting.md`
- Decision trees (including Tree 11 — troubleshooting escalation): `18_decision_trees.md`
- Error-string lookup: `17_error_lookup.md`
- Tuning recipes (when the right answer is "update, don't tune"): `16_tuning_recipes.md`
- Installation and worker-connect lifecycle: `01_installation_admin.md`
- Lane / GPU / queue mechanics: `21_gpu_lane_queue.md`
- Disk and storage growth lifecycle: `24_disk_and_storage.md`
- GUI admin surface: `docs/per_page/application-guide__instance-management.md`, `docs/per_page/application-guide__admin-panel.md`
- Version-by-version behavior changes referenced above: `reference/release_notes/markdown/v4.0.md`, `…v4.1.md`, `…v4.2.md`, `…v4.3.md`, `…v4.4.md`, `…v4.5.md`, `…v4.6.md`, `…v5.0.md`

---

## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

- `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0.md`
- `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0__cryosparcm-reference-v5.0.md`
- `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0__cryosparcm-cli-reference-v5.0.md`
- `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0__cryosparcw-reference-v5.0.md`
- `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0__environment-variables-v5.0.md`
- `docs/per_page/setup-configuration-and-management__management-and-monitoring-4.7__cli-4.7.md`
- `docs/per_page/setup-configuration-and-management__management-and-monitoring-4.7__cryosparcm-4.7.md`
- `docs/per_page/setup-configuration-and-management__management-and-monitoring-4.7__cryosparcw-4.7.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__guide-installation-testing-with-cryosparcm-test.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__guide-download-error-reports.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__guide-instance-recovery-v5.0.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__guide-maintenance-mode-and-configurable-user-facing-messages.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__guide-reduce-database-size-v4.3.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__guide-data-cleanup-v4.3.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__guide-updating-to-cryosparc-v5.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__guide-updating-to-cryosparc-v4.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__tutorial-migrating-your-cryosparc-instance.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__tutorial-user-management.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__unix-permissions-and-data-access-control.md`
- `docs/per_page/setup-configuration-and-management__troubleshooting.md`
- `docs/per_page/application-guide__instance-management.md`
- `docs/per_page/application-guide__admin-panel.md`
- `docs/forum_threads/digests/forum_troubleshooting.md`
- `docs/forum_threads/digests/forum_installation.md`
- `17_error_lookup.md`
- `reference/release_notes/markdown/v4.0.md`
- `reference/release_notes/markdown/v4.1.md`
- `reference/release_notes/markdown/v4.2.md`
- `reference/release_notes/markdown/v4.3.md`
- `reference/release_notes/markdown/v4.4.md`
- `reference/release_notes/markdown/v4.5.md`
- `reference/release_notes/markdown/v4.6.md`
- `reference/release_notes/markdown/v5.0.md`
- `13_cryosparc_tools_api.md`
- `15_troubleshooting.md`
- `16_tuning_recipes.md`
- `18_decision_trees.md`
- `topic_plan.md`
- `plan.md`
