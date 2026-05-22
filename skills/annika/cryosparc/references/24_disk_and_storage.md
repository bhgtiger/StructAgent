# Topic 24 — Disk and Storage (Planning, Cleanup, Compaction, Export, Archival, Recovery)

## Scope
How CryoSPARC consumes and releases storage: the four storage layers (project directory tree, MongoDB metadata, SSD particle cache, raw-data symlinks), how each layer grows, what each cleanup operation actually removes (and what it does *not* touch), and the lifecycle runbooks the agent needs to safely move, archive, recover, and shrink an instance without losing data. The page is deliberately conservative about destructive commands — most of the durable risk in cryoSPARC operations is at this layer, and a single confident `rm` is the canonical way to destroy a multi-TB project.

What lives elsewhere — do not duplicate:

- Scheduler/lane/cache *behavior* visible to the queue (cache thrashing as a *scheduling* symptom, GPU/CPU/RAM provisioning, SSD path *as a worker attribute*) — `21_gpu_lane_queue.md`. This page owns SSD planning, lifetime, content, and physical sizing; the lane page owns when the scheduler waits on the cache.
- Exact `cryosparcm` / `cryosparcw` syntax, restart/maintenance-mode/backup/restore lifecycle, log layout, and version disclaimer — `14_cli_admin.md`. This page references commands by name and source; the admin page owns flags.
- Programmatic project/job orchestration, dataset I/O, downloading via API — `13_cryosparc_tools_api.md`.
- Install / connect-worker mechanics and worker prerequisites — `01_installation_admin.md`.
- Error-string lookup — `17_error_lookup.md`. Debugging mental model — `15_troubleshooting.md`. Decision-tree routing — `18_decision_trees.md`.
- Live preprocessing/extraction streaming and session UI — `25_cryosparc_live.md`. This page owns Live *data on disk* (compaction, raw vs micrographs vs particles vs metadata cells, archived/active state, restoration).

Version disclaimer: data-management GUI, cleanup-tool checkboxes, database utilities, and recovery utilities all evolved across v4.0 → v5.0. Where behavior differs the page calls out the version. When a precise command is needed the agent should always confirm against the version-matched reference (`docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0__cryosparcm-reference-v5.0.md`, or the `…__management-and-monitoring-4.7/…` equivalents) and `cryosparcm COMMAND --help` on the target instance, exactly as in `14_cli_admin.md`.

---

## 1. Mental model — four independent storage layers

CryoSPARC's storage footprint is the union of four layers that grow and shrink for different reasons. Routing a "running out of disk" question is mostly a matter of identifying which layer is full.

| Layer | What it holds | Lifecycle | Where it lives |
|---|---|---|---|
| **Raw / imported data** | Movies, micrographs, particle stacks, gain refs, templates, volumes brought in by Import jobs | **CryoSPARC never deletes or modifies it** (`…guide-data-cleanup-v4.3.md`: "CryoSPARC does not currently … attempt to manage *raw* data on your filesystems"). Reachable via symlinks in each Import job's `imported/` directory. | Wherever the user told the Import job to look. For Import Templates / Import Volumes the file is *copied* into the job directory instead of symlinked (`…tutorial-migrating-your-cryosparc-instance.md`). |
| **Project directory tree** (per project) | Project-scoped self-contained directory containing every job's directory, intermediate + output files, session directories for Live, `cs.lock`, `project.json` | Created by **Create / Attach**; updated by "continuous export" on every metadata or job state change; emptied selectively by *Clear* / cleanup tools; emptied entirely by **Delete Project**; left in place by **Detach** / **Archive**. | The path the user picked at project creation; named after the project title (v4.0+, prefix `CS-…`) rather than the numeric `PXX` UID (`…guide-data-management-in-cryosparc-v4.0.md`). |
| **MongoDB database** | Instance state: projects, workspaces, jobs (parameters, inputs, outputs, status, event log, image data), users, lanes, sessions, info-tag plots | Grows with every job action; shrinks via *Cleanup Data* (which clears job data on disk *and* in the DB), **Delete Project from Database** (v4.1.2+), and `cryosparcm compact` / backup-restore (`…guide-reduce-database-size-v4.3.md`). | Filesystem directory pointed at by `CRYOSPARC_DB_PATH`. The MongoDB layer is documented as "separate from project and job directories" (`…guide-data-cleanup-v4.3.md`). Master refuses to start the DB below `CRYOSPARC_DB_MIN_SPACE_GB` (default 5GB) (`14_cli_admin.md` → `…environment-variables-v5.0.md`). |
| **SSD particle cache** (per worker) | Particle stacks copied from project storage for fast random-access reads by classification/refinement/reconstruction jobs | **Managed transparently** by CryoSPARC: copied in on job start when `Cache particle images on SSD = on`, **automatically evicted to make room** (LRU under quota/reserve), purged for files unaccessed >30 days by default (v3.3+, `CRYOSPARC_SSD_CACHE_LIFETIME_DAYS`) (`…tutorial-ssd-particle-caching-in-cryosparc.md`). | The `ssd_path` configured per worker via `cryosparcw connect --ssdpath …` / `--ssdquota` / `--ssdreserve`. Nodes that only do motion/CTF/picking do not need an SSD. |

Two implications fall out of this model and are worth committing to memory:

1. **The database is the source of truth; the project directory is the durable copy.** Continuous export writes a self-contained, attachable copy of every project to disk on every relevant state change — so the project directory survives DB loss and can be re-attached to *any* compatible instance (`…guide-data-management-in-cryosparc-v4.0.md` §1, §"Rescuing a project from an inoperable instance"). The DB carries faster/richer state (live event log of running jobs, image data, info tags) that is regenerated or partially lost during recovery.
2. **The SSD cache is not durable storage.** It is a read-only mirror of particle files that already exist in the project directory. "It is safe to delete cache files any time (it's a read-only cache)" (`…tutorial-ssd-particle-caching-in-cryosparc.md` FAQ). A user who points their project directory *at* an SSD cache, or who treats the cache as their working set, will lose data when the cache evicts (or when another job uses the space).

---

## 2. What this page owns vs adjacent pages

| Question | Owned by |
|---|---|
| "How big should the SSD be? How do I size storage for N TB of movies?" | **this page** §3 |
| "What does *Clear job* vs *Delete job* vs *Detach project* actually remove?" | **this page** §4–§6 |
| "How do I archive a finished project / move a project to slow storage?" | **this page** §6–§7 |
| "DB or project directory full — what do I clean up first?" | **this page** §8 (disk-full runbook) |
| "Project directory is on a different host now — how do I update CryoSPARC?" | **this page** §7 (migration), with API mechanics in `14_cli_admin.md` §6.6 |
| "DB was wiped, can I save the data?" | **this page** §7 (recovery), via `cryosparcm recover` whose syntax lives in `14_cli_admin.md` |
| "SSD cache message X — what does it mean?" | **this page** §9 → `17_error_lookup.md` |
| "Why is my job *queued*?" / lane mechanics | `21_gpu_lane_queue.md` |
| "Restart / maintenance mode / `cryosparcm backup` syntax" | `14_cli_admin.md` |
| "Which job to use for X scientific question?" | per-stage topics |

Rule: **before recommending any destructive cleanup, identify which layer is full.** "We're out of disk" usually means *project tree* or *SSD*; "the database is huge" means *MongoDB*; "the master won't start" with `CRYOSPARC_DB_MIN_SPACE_GB` errors means *the DB volume* specifically, even if the project volume has terabytes free.

---

## 3. Storage planning

### 3.1 Raw movies / micrographs / particle stacks

CryoSPARC does not move or copy raw data into project directories; it symlinks. The agent should treat raw data as the user's responsibility, but should advise on placement:

- **Raw data should be on storage the worker can read fast and reliably** — local NFS / Lustre / direct-mount (`17_error_lookup.md`: `TIFFOpen ... Input/output error` failures are commonly sshfs / NFS stall problems on the Live worker, not a CryoSPARC bug).
- **Raw data should be on storage that can outlive the project directory** — archiving a project does not archive the raw movies (`…guide-data-management-in-cryosparc-v4.0.md` §7).
- **Import Templates / Import Volumes copy into the job directory; Import Movies / Micrographs / Particles symlink.** The agent should not advise on deletion of raw movies without also accounting for the symlink in any active Import job.

### 3.2 Project directory growth and particle stack sizing

Project directory size is dominated, in order, by:

1. **Particle stacks** from Extract / Restack / Live extraction (`…guide-data-cleanup-v4.3.md`).
2. **Motion-corrected micrographs** (Patch Motion) and dose-weighted variants.
3. **Job intermediates** (per-iteration volumes, classification states, 3DVA / 3DFlex intermediates).
4. **Output volumes, maps, and FSC artifacts**.
5. **Event log, plots, and metadata** (small individually; large in aggregate over thousands of jobs).

Per-particle-stack sizing rule of thumb (`…tutorial-ssd-particle-caching-in-cryosparc.md`):

```
dataset_size ≈ (4 * box² + nsymbt + header_length) * num_particles
```

Worked examples from the same doc:

| Box | Particles | Approx size |
|---|---|---|
| 256 | 1,000,000 | ≈ 263 GB |
| 432 | 2,000,000 | ≈ 1.5 TB |

That formula governs both the project-directory footprint of an extraction and the size needed in the SSD cache to host the stack — they are the same number.

### 3.3 SSD cache sizing

- The hardware guide recommends **≥ 2 TB SSD** as a default for current large datasets (`…tutorial-ssd-particle-caching-in-cryosparc.md` §Hardware).
- Quota + reserve let one machine share its SSD with other applications: `--ssdquota` caps CryoSPARC's footprint; `--ssdreserve` keeps a floor of free space (`…tutorial-ssd-particle-caching-in-cryosparc.md` §Advanced Parameters).
- Default cache lifetime is **30 days** (since v3.3); tune via `CRYOSPARC_SSD_CACHE_LIFETIME_DAYS` in `cryosparc_master/config.sh`. Shorter for short-cycle facilities; longer for long-running projects.
- Multi-threaded copy is on by default (v4.3.0+), 2 threads; tune via `CRYOSPARC_CACHE_NUM_THREADS` (set `=1` to disable multithreading).
- **The cache holds the *entire referenced stack*, not the subset you selected.** If 2D Selection picked 30% of a 1.5 TB stack, the cache will still request the full 1.5 TB unless you **Downsample Particles** or **Restack Particles** to materialize a subset (`…tutorial-ssd-particle-caching-in-cryosparc.md` §Consolidating a Particle Stack, `…guide-data-cleanup-v4.3.md` §Restack particles).
- Cluster filesystems: from v4.6.2 the cache system retries on transient failures and produces additional diagnostics; from v4.2.1+230427 it computes free space correctly to avoid the infinite-cache-hang regression (`reference/release_notes/markdown/v4.6.md`, `reference/release_notes/markdown/v4.2.md`).

### 3.4 Live session footprint

Live sessions carry their own per-session subdirectory inside the project directory, holding five distinguishable data categories that the data-management UI tracks separately (`…cryosparc-live-session-data-management-4.7.md`, `docs/per_page/application-guide__managing-data.md`):

- Raw imported data (symlinks — not deletable from CryoSPARC; "Available for all categories except for *raw data*")
- Motion-corrected micrographs
- Exposure thumbnails (cannot be downloaded/state-tagged via the CLI menu but can be deleted)
- Extracted particles
- Session metadata (DB-side)

Per-session sizes are **out of date by default** in the management table — refresh via the Actions column before reasoning about them (`docs/per_page/application-guide__managing-data.md`).

### 3.5 Database growth

The MongoDB database grows roughly with:

- Number of jobs (parameters, inputs/outputs metadata, event log per job).
- Image data the event log embeds (per-iteration plots, info-tag thumbnails).
- Live sessions, especially with full plotting enabled.
- Per-job intermediate-iteration output records.

Notable knobs that affect DB growth:

- v4.2.1 added a **project-level toggle** for whether jobs save intermediate results at all (default on; turning it off saves disk without needing post-hoc cleanup) (`reference/release_notes/markdown/v4.2.md`, `…guide-data-management-in-cryosparc-v4.0.md` §4).
- v4.3 default: automatic deletion of intermediate results is **enabled** for new jobs in all projects (`…guide-data-cleanup-v4.3.md`).
- v4.4.1 Live reduced per-micrograph DB plot footprint by ~10% (`reference/release_notes/markdown/v4.4.md`).
- v4.4.1 turned on **MongoDB journaling** by default — increases durability, slightly increases disk use.

### 3.6 Backups and exports

Two artifacts every running instance produces on its own, both of which the agent should treat as load-bearing backups:

| Artifact | Purpose | Cadence |
|---|---|---|
| `cryosparc_master/run/cryosparc_instance_config_*.tar` | Snapshot of lanes, targets, users, project attachments, sched config — required input to `cryosparcm recover` (v5.0+) | Hourly by default (`CRYOSPARC_AUTO_EXPORT_INSTANCE_CONFIG_INTERVAL_HOURS = 1`, `…environment-variables-v5.0.md`). v5.0.5 also packages Live session profiles in this snapshot (`reference/release_notes/markdown/v5.0.md`). |
| `cryosparcm backup` output | Full MongoDB dump for `cryosparcm restore` | On demand. Required before every update, `compact`, restore, or migration; explicitly recommended in `…guide-updating-to-cryosparc-v4.md`, `…guide-reduce-database-size-v4.3.md`, `…tutorial-migrating-your-cryosparc-instance.md`. |

Both must be **copied off the master host** for the disaster cases they exist for. A local-only backup against database corruption is the most common false-safety pattern.

---

## 4. Cleanup levels — what each one removes (and what it does not)

Cleanup in CryoSPARC is multi-layered and the layers are not interchangeable. Choosing the wrong layer wastes work or destroys data.

### 4.1 Quick reference table

| Action | What it removes | What it keeps | Source |
|---|---|---|---|
| **Clear Job** | All output data files for that job; status reset to **building** | Job metadata, inputs, parameters in DB; can be re-run later | `…guide-data-cleanup-v4.3.md` §Clearing vs. deleting |
| **Delete Job** | Job data + the job entry itself | Nothing — fully removed from DB | `…guide-data-cleanup-v4.3.md` |
| **Clear Intermediate Results** (per-job or project-wide) | Per-iteration outputs from iterative jobs (e.g. early-iteration volumes); v4.3+ enabled by default for new jobs | Final-iteration outputs; downstream jobs continue to work | `…guide-data-cleanup-v4.3.md` §Clear intermediate results, `…guide-data-management-in-cryosparc-v4.0.md` §4 |
| **Clear non-final jobs** (Cleanup Data tool) | Every job in scope not marked **final** and not an ancestor of a final job | Final jobs and their ancestors (with v5.0+ exception for the "Include final ancestor jobs" toggle) | `…guide-data-cleanup-v4.3.md` §Clear non-final results |
| **Clear pre-processing jobs** (Cleanup Data tool) | Deterministic preprocessing outputs (motion, CTF, extraction) that can be re-run; restack particles **not cleared** by default | DB metadata; downstream particles if you restacked them first | `…guide-data-cleanup-v4.3.md` §Clear preprocessing jobs |
| **Clear killed / failed jobs** | Partial outputs from non-completed runs | DB metadata; can be re-run | `…guide-data-cleanup-v4.3.md` |
| **Restack Particles** | Nothing on its own | *Adds* a new, dense particle stack containing only your kept subset, so subsequent Clear of upstream extraction is safe | `…guide-data-cleanup-v4.3.md` §Restack particles; v4.1.2 added the job (`reference/release_notes/markdown/v4.1.md`) |
| **Compact Live Session** (v4.3+) | Motion-corrected micrographs and extracted particles for the session | Saved particle locations and parameters needed to *restore* the session later | `…guide-data-cleanup-v4.3.md` §Compacting a Live session |
| **Restore Live Session** | Re-runs preprocessing/extraction to recreate compacted data | — | same |
| **SSD cache cleanup** (manual / automatic) | Cached copies of particle files on the worker SSD; safe to delete any time | The originals in the project directory (which are the source) | `…tutorial-ssd-particle-caching-in-cryosparc.md` FAQ |
| **Detach Project** | Removes lock file; project disappears from active UI lists | All project data on disk; can be attached anywhere | `…guide-data-management-in-cryosparc-v4.0.md` §Detach |
| **Archive Project** | Marks project read-only in the UI; nothing on disk | Lock file still in place; project visible but immutable | same §Archive |
| **Delete Project** (GUI) | **Erases the entire project directory from disk** *and* removes it from the DB | Nothing project-related | `docs/per_page/application-guide__managing-data.md` warning hint |
| **Delete Project from Database** (v4.1.2+, on already-detached projects) | DB-side records remaining after detach | Project directory on disk untouched | `reference/release_notes/markdown/v4.1.md`, `…guide-data-management-in-cryosparc-v4.0.md` §Detach |
| **`cryosparcm compact`** | Defragments MongoDB collection files | All data — but **not guaranteed to actually shrink files** | `…guide-reduce-database-size-v4.3.md` Option 1 |
| **`cryosparcm backup` → `cryosparcm restore`** to a fresh DB directory | Re-writes the DB from a dump; usually shrinks to the dump's size | All data | `…guide-reduce-database-size-v4.3.md` Option 2 |
| **`delete_output_result_files(...)`** (v5.0+ CLI) | One specific output-result group within a job (e.g. `micrographs_non_dw`) | Other outputs in the same job | `reference/release_notes/markdown/v5.0.md` |

### 4.2 "Final" marking is your safety net

The Cleanup Data tool only protects jobs that have been explicitly marked as **final** (and their ancestors). Forgetting to mark before bulk cleanup is the canonical destructive mistake (`…guide-data-cleanup-v4.3.md` §Clear non-final results: "It is best to mark important jobs as final before performing data cleanup actions"). Linked jobs across workspaces are particularly easy to lose — a job that is **also** in another workspace is still treated as part of the workspace you are cleaning, and will be cleared there (`…guide-data-cleanup-v4.3.md`).

In v5.0+ the **"Include final ancestor jobs"** toggle further controls whether preprocessing jobs that are ancestors of finals get cleared by preprocessing-clear actions — a knob that lets the agent reclaim significant additional space *only when* the raw data is still around to regenerate them (`…guide-data-cleanup-v4.3.md` §1, `reference/release_notes/markdown/v5.0.md`).

### 4.3 Determinism caveat — what you can safely Clear and re-run

CryoSPARC explicitly classifies preprocessing jobs (motion correction, CTF estimation, picking, extraction) as **near-deterministic for the same version**: re-running with identical parameters and inputs yields results differing only at noise-floor scale (`…guide-data-cleanup-v4.3.md` §Determinism in CryoSPARC). Downstream jobs (2D, ab-initio, refinement, 3DVA, etc.) are **not** deterministic — random seeds and iterative accumulation amplify floating-point differences. **Only clear-and-re-run preprocessing jobs casually; downstream jobs should be assumed irreproducible bit-for-bit.**

---

## 5. Cache behavior on disk

The cache is a separate layer with its own failure modes and its own safety rules.

- **Reuse across jobs within a project**: once a particle stack is cached on a given worker, subsequent jobs in the same project that need the same particles skip the copy (`…tutorial-ssd-particle-caching-in-cryosparc.md`). This is why the cache often grows in bursts and then idles.
- **LRU eviction under pressure**: if room is needed, the oldest entries are evicted — but only entries CryoSPARC owns. The message `cache does not have enough space for download... but there are no files that can be deleted` means another application is squatting on the SSD; the cache cannot evict files it does not own (`…tutorial-ssd-particle-caching-in-cryosparc.md` Troubleshooting).
- **File-locking under concurrent jobs**: `cache waiting for requested files to become unlocked` is a *normal* transient — one job is copying, another is waiting on the same files; the waiter unblocks when the first finishes (same source).
- **Cache files are addressed by path + size + modtime**, so pre-caching via symlinks works — the cache will skip the copy if a file already exists at the expected path (`…tutorial-ssd-particle-caching-in-cryosparc.md` FAQ).
- **Manual cache deletion is safe** at any time — cache files are read-only mirrors. But manual deletion is rarely the right answer; let LRU + lifetime handle it unless the SSD is shared with other workloads.
- v4.6.2 added robustness for cluster filesystems and improved diagnostics; `File not found` errors during caching on cluster FS should no longer occur (`reference/release_notes/markdown/v4.6.md`).
- **`Cache Particles on SSD` (Utility job)** is a stand-alone job that fronts the cache copy so the GPU isn't held by the next job during the copy (`docs/per_page/processing-data__all-job-types-in-cryosparc__utilities__job-cache-particles-on-ssd.md`). Useful when the user complains "my Refinement was on the GPU for an hour but didn't start" — the GPU was held during cache copy.

---

## 6. Project lifecycle — attach / detach / archive / unarchive / delete

This is the most reliably misunderstood surface in CryoSPARC operations. The actions are not synonyms.

| Action | Lock file (`cs.lock`) | Project visible in UI? | Project modifiable? | On-disk data | Use for |
|---|---|---|---|---|---|
| **Attach** | Created | Yes | Yes | Untouched | Bringing a project (back) into an instance |
| **Detach** | Removed | Yes, marked "Detached" (read-only stub) | No | Untouched | Moving a project to another instance |
| **Archive** | Kept | Yes, read-only | No | Untouched | Project staying on this instance but moving to slow storage |
| **Unarchive** | Kept | Yes | Yes | Must be back at the pointed-at path | After moving the directory back |
| **Delete Project** (GUI) | — | No | — | **Erased from disk** | Final removal — the GUI action **does** delete project data |
| **Delete Project from Database** (v4.1.2+) | Must already be detached | No (DB-side hidden) | — | Untouched | Cleanup of DB residue after a detach |

Rules that go with these actions (`…guide-data-management-in-cryosparc-v4.0.md`, `…application-guide__projects-workspaces-and-live-sessions.md`):

- **Never `rm -rf` a project directory that is attached.** Both `docs/per_page/application-guide__managing-data.md` and `…guide-data-management-in-cryosparc-v4.0.md` open with this warning. Always *Detach* or *Delete Project* first.
- **Never modify a project directory outside CryoSPARC** while archived. Unarchiving a modified directory leads to DB/disk inconsistency and "can lead to CryoSPARC malfunction and data loss" (`…guide-data-management-in-cryosparc-v4.0.md` §Archive).
- **A project can only be attached to one instance at a time.** The lock file enforces this. The recovery flow (§7.3) is the only sanctioned way to bypass it.
- **Use `tar -cv` (no `-h`)** when consolidating a project directory. `-h` dereferences symlinks and explodes the tar to include all raw movies plus duplicates of internal symlinks (`…guide-data-management-in-cryosparc-v4.0.md` §7).
- **Renaming a project directory** is a three-step archive → rename → unarchive (`…guide-data-management-in-cryosparc-v4.0.md` §Use Case: Renaming).
- **Moving a project directory** is archive → move → unarchive at the new path.
- **Transfer between instances** is detach → copy → attach.
- **Detached projects accumulate DB cruft**; v4.1.2+ added *Delete Project from Database* on already-detached projects to clean it up.

The v4.0 directory-naming change is worth flagging: project directories are named `CS-<title-slug>`, not `PXX`, and that name persists across instances even though the numeric UID changes. The `cryosparc_PXX_` prefix that older versions stamped on output files was also dropped from on-disk filenames; the browser adds it back on download for human disambiguation only (`…guide-data-management-in-cryosparc-v4.0.md`).

---

## 7. Export / download / migration / recovery

### 7.1 Export & download (single-job, single-output, single-project)

In current versions (`docs/per_page/application-guide__downloading-and-exporting-data.md`):

- **CSV of projects / workspaces / sessions / jobs**: footer button in browse views; respects filters; v5.0+ supports info-tag inclusion and selection-only.
- **Job outputs**: any output group or individual `.cs` / `.map` / volume can be downloaded from the Outputs tab, including per-iteration variants (`docs/per_page/application-guide__inspecting-job-data.md`).
- **Event log PDF / Job Error Report**: per-job, GUI-button. Job Error Report is the canonical "ship this for debugging" artifact — it bundles event log + job log + browser + last week of system logs (`docs/per_page/application-guide__downloading-and-exporting-data.md`, `14_cli_admin.md` §3.9).
- **Exporting individual jobs / output groups** for sharing or re-import: unchanged behavior since v2.11+ (`…guide-data-management-in-cryosparc-v4.0.md` §5–§6; legacy detail in `…guides-for-v3__tutorial-data-management-in-cryosparc.md`).
- **Exporting an entire project**: in v4.0+ this is the *detach + copy* flow above. Continuous export means the on-disk project directory is always a valid, self-contained, attachable copy.

### 7.2 Archive flow

Recommended sequence (`…guide-data-cleanup-v4.3.md` "Project is completed and will not be needed in the near future"; `…guide-data-management-in-cryosparc-v4.0.md`):

1. Mark every important job **final**; run Cleanup Data preview to see what would survive.
2. Restack particles you actually need (Section 4.1; release notes v4.1.2 introduced Restack Particles for this purpose) so the upstream extraction can be cleared without losing the particle set.
3. Run Cleanup Data with the cleanup-options the preview shows are safe; v5.0+ consider toggling "Include final ancestor jobs" if raw data is preserved separately.
4. Compact every completed Live session (v4.3+); save particle locations and parameters for restore later.
5. (Optional) Reduce intermediate output via per-project intermediate-results toggle (v4.2.1+).
6. *Archive Project* in the GUI — locks read-only, keeps `cs.lock`.
7. Move the project directory off-tier with `tar -cv` or `rsync --links` (no symlink dereferencing). **Move/archive raw data separately** — the project directory only contains symlinks to it.
8. Later: place the directory at a reachable path, *Unarchive Project* and supply the new path.

### 7.3 Migration

Migration is the union of one or more of (`…tutorial-migrating-your-cryosparc-instance.md`):

| What moved | What to do |
|---|---|
| **Raw data only** | Use `api.projects.get_symlinks` / `api.jobs.update_directory_symlinks(project, job, prefix_cut, prefix_new)` (v5.0+) or `cli.get_project_symlinks` / `cli.job_import_replace_symlinks` (v4.0–v4.7.1) to retarget Import jobs. Run via `cryosparcm icli`. |
| **Project directories** | Use the *Archive → move → Unarchive* flow (v4.0+). Legacy `update_project(...)` direct DB edits are only for ≤v3.3. |
| **Database (only)** | Shutdown → `rsync -r --links` the DB directory → update `CRYOSPARC_DB_PATH` in `cryosparc_master/config.sh` → start. **Do not modify project directories while the DB is in flight.** |
| **Master host** | Two paths: shared filesystem → just update `CRYOSPARC_MASTER_HOSTNAME` and start on the new host; non-shared → install fresh with the same `LICENSE_ID`, copy the DB directory over, update `CRYOSPARC_DB_PATH`, copy any custom env from old `config.sh`. **Project directories and raw data must mount at the same paths.** |
| **Worker host** | Re-run `cryosparcw connect` from the new worker; see `14_cli_admin.md` §6.4. |

All of these benefit from `cryosparcm backup` *before* anything else.

### 7.4 Recovery from a lost / corrupt database (v5.0+)

If the project directories are intact and a recent `cryosparc_master/run/cryosparc_instance_config_*.tar` is available, full recovery is one command (`…guide-instance-recovery-v5.0.md`):

1. `cryosparcm stop`; confirm no orphan `supervisord` / `mongod` (`docs/per_page/setup-configuration-and-management__troubleshooting.md` "Incomplete CryoSPARC shutdown").
2. **Copy the latest `cryosparc_instance_config_*.tar` to a path outside the master install** before doing anything else to that install.
3. Make a fresh empty directory for the new DB; update `CRYOSPARC_DB_PATH` in `cryosparc_master/config.sh`.
4. `cryosparcm start` (will come up empty).
5. `cryosparcm recover -f /path/to/copied_instance_config.tar`. Recovery imports config + users, then walks every project recorded in the snapshot and attempts to attach from its on-disk location. Projects marked `archived` come back as `detached` (unarchive metadata isn't reconstructable); projects marked `deleted` are skipped; failures are captured in a JSON report written to `cryosparc_master/run/recovery_results_*.json`.
6. After recovery, manually re-attach any project that did not restore automatically.

If no recent config export is available, the fallback (also documented in the same guide) is: install fresh, create users, **attach each project directory** by hand. You lose lane/target config and have to redefine it.

If the *project directories* are also lost, there is no recovery — that is the case the regular off-master backups of `cryosparcm backup` output exist for.

---

## 8. Risk points and red flags

Things to flag and stop on before any cleanup or migration.

| Red flag | Why it matters | First action |
|---|---|---|
| User says "I'll just `rm -rf` the project" | Attached projects must be deleted via *Delete Project* or detached first; raw symlinks may resolve to user files outside the project | Stop. Confirm attached/detached state and whether raw data lives inside or outside. Use *Delete Project* in GUI. |
| `cs.lock` present but project not visible in this instance | Project is attached to a *different* instance; multiple instances modifying the same dir corrupts metadata | Either re-attach in the original instance and detach properly, or follow the *rescue* flow (delete `cs.lock` only after confirming the other instance is dead) |
| Project directory modified outside CryoSPARC while archived/detached | Diverges from DB; on re-attach/unarchive, leads to malfunction and data loss | If still attached and unmodified — re-detach and re-attach. If modified — assess loss; consider attaching as a new project and rebuilding ancestry by hand |
| Raw data moved without repairing Import-job symlinks | All downstream jobs that depend on raw movies will fail on re-run | Use `api.jobs.update_directory_symlinks` (v5.0+) / `cli.job_import_replace_symlinks` (v4.0–v4.7.1) via `cryosparcm icli` |
| User about to clear non-final jobs in a workspace, important jobs not marked | Linked jobs across workspaces will be cleared too | Mark finals at the **project** level first, then preview Cleanup Data |
| Cache mistaken for durable storage (e.g. project dir on SSD path) | LRU eviction or another job can purge "their work" | Move project directory to durable storage; use SSD as cache only |
| Master refuses to start, `CRYOSPARC_DB_MIN_SPACE_GB` error | DB volume below floor (default 5 GB free) | Free space on the DB volume — do not just lower the floor (`14_cli_admin.md`) |
| Live session running while a project detach is attempted | v4.3.1 fixed *one* race; in general, detach should not happen while sessions run | Pause Live sessions, then detach |
| Multi-user instance with mixed ownership | Linux permissions can prevent users from reading each other's exports | See `…unix-permissions-and-data-access-control.md`; usually solved by a shared `cryosparc` Unix group, not by `chmod 777` |
| `rsync` or `tar` of a project directory with `-h` (deref symlinks) | Inflates the copy by ingesting raw movies + duplicating internal symlinks | Re-run without symlink dereference |
| Forum advice to delete files from a job directory directly | The continuous-export model assumes CryoSPARC owns the layout; manual deletion can produce attach failures later | Use the GUI cleanup / clear / delete actions |
| `cryosparcm compact` "didn't shrink" | The MongoDB `compact` is "not guaranteed to reduce" file size — fragmentation may already be minimal | Compare DB-on-disk size to a fresh `cryosparcm backup` — if they're already similar, no further reduction is available without backup-restore (`…guide-reduce-database-size-v4.3.md`) |

---

## 9. Runbooks

Each runbook is a stop-and-check checklist, not a syntax recipe. Pair each command with the version-matched reference and `--help`.

### 9.1 Disk full — emergency

Capture the symptom precisely before acting.

1. **Identify which volume is full** — DB volume vs project storage vs SSD vs raw. `df` on each. If multiple volumes share a filesystem, identify the largest contributor with directory-level sizing (the GUI's Project Data table also surfaces project sizes once refreshed).
2. **If the master is down because `CRYOSPARC_DB_MIN_SPACE_GB` tripped**: free space on the DB volume *first*. The master refuses to start otherwise (`14_cli_admin.md`).
3. **If projects are the cause**:
   - Refresh project sizes in the Project Data table (`docs/per_page/application-guide__managing-data.md`).
   - Mark finals across the project; preview Cleanup Data; clear intermediate results / non-final jobs at *workspace* scope to start.
   - If that is not enough, restack-and-clear: Restack Particles on the kept subset, then clear extraction.
   - If still not enough, compact all completed Live sessions.
   - As a last resort, archive a finished project and move its directory off-tier.
4. **If the SSD is the cause** (on a worker, not the master):
   - Confirm CryoSPARC owns the offending files: a non-CryoSPARC application can squat on the cache.
   - Confirm no jobs are running on that worker before clearing.
   - Manual deletion of cache files is safe (`…tutorial-ssd-particle-caching-in-cryosparc.md` FAQ); the cache will re-populate on demand. Prefer letting LRU + lifetime handle it.
5. **If the DB volume is the cause but the master is up**: see §9.4.
6. **If raw data is the cause** (rare in CryoSPARC's directories, common in the user's): raw data lives outside CryoSPARC; the agent advises but does not delete.

### 9.2 Before deleting any data — pre-flight checklist

Run this list every time, even for "obvious" deletions.

- [ ] Have we **identified** which storage layer the data is in (project tree / DB / SSD / raw)?
- [ ] Is the project **attached** to this instance? If not — do not act in this instance's GUI.
- [ ] Have important downstream jobs (the ones a paper depends on) been marked **final**?
- [ ] If a workspace cleanup: is every job we care about linked also into the workspace we're *not* cleaning, or marked final, so a linked-job clear can't take them out?
- [ ] Have we **previewed** the cleanup via Cleanup Data (or via the v5.0 dry-run output of `delete_output_result_files` / DB CLI calls)?
- [ ] Has the latest `cryosparcm backup` been taken and **copied off the master host**?
- [ ] Is the latest `cryosparc_master/run/cryosparc_instance_config_*.tar` copied off as well?
- [ ] Is the SSD cache that mirrors the data we're about to delete actually a cache, not someone's working set?
- [ ] If raw data is involved: do we have a separate inventory / backup, and are Import-job symlinks documented?

### 9.3 Archiving a project for long-term storage

1. Mark every important job **final** (project-wide, not workspace-wide).
2. Run Cleanup Data preview. Confirm the survivor set is what you expect.
3. Restack any particle subsets you want preserved, before clearing upstream extraction.
4. Run Cleanup Data with the chosen options (likely: clear preprocessing, clear non-final, optionally clear failed/killed; in v5.0+ optionally "Include final ancestor jobs").
5. Compact every completed Live session.
6. Take a `cryosparcm backup`; copy off-master.
7. *Archive Project* in the GUI.
8. `tar -cv` the project directory (no `-h`); copy to long-term storage.
9. Separately, archive/move the raw data referenced by Import jobs.
10. Optionally *Detach Project* afterward if you do not intend to unarchive on this instance.

### 9.4 Database is growing — pre-fail cleanup

1. Maintenance mode on (`14_cli_admin.md`); pause Live sessions explicitly.
2. Mark finals across active projects; run Cleanup Data on the largest first.
3. Delete killed/failed jobs older than relevance.
4. *Detach* projects no longer worked on; in v4.1.2+, *Delete Project from Database* on those detached projects to remove the DB residue.
5. Drain the queue, `cryosparcm stop`, `cryosparcm start database`, `cryosparcm backup`, `cryosparcm compact`. Compare DB-on-disk size to the backup size *afterward* — if they are similar, no further reduction is available.
6. If the gap is large, use the *backup-restore-to-fresh-DB-directory* path documented in `…guide-reduce-database-size-v4.3.md` Option 2 (worst-case requires 2× current DB free). Test by checking projects/jobs come back intact, then delete the old DB directory and the backup file.
7. Maintenance mode off.

### 9.5 Migrating an instance

See `14_cli_admin.md` §6.6 for the command surface. The *order* matters:

1. `cryosparcm backup` first.
2. Copy `cryosparc_master/run/cryosparc_instance_config_*.tar` off-master.
3. Maintenance mode on, drain queue, pause Live, `cryosparcm stop`.
4. Move raw data → repair Import symlinks via `api.jobs.update_directory_symlinks` / `cli.job_import_replace_symlinks` (`…tutorial-migrating-your-cryosparc-instance.md`).
5. Move project directories → archive/unarchive each one at the new path.
6. Move database → `rsync -r --links`, then update `CRYOSPARC_DB_PATH`.
7. New master host → install with the same `LICENSE_ID`; ensure project directories and raw data mount at the same paths.
8. New worker hosts → re-run `cryosparcw connect` from each.
9. Start, `cryosparcm status`, `cryosparcm test install`, `cryosparcm test workers --test all`.

### 9.6 Recovery from a lost or corrupt DB (v5.0+)

See §7.4. Key safety steps the agent must enforce:

- Copy `cryosparc_instance_config_*.tar` off the original install *before* touching anything else.
- Confirm CryoSPARC is fully stopped (no orphan `mongod` / `supervisord`) before pointing `CRYOSPARC_DB_PATH` elsewhere.
- Read the recovery report JSON — projects that did not attach (lock conflicts, missing `project.json`, archived-but-unrecoverable) need manual triage.

### 9.7 SSD cache troubleshooting

Three messages, three different actions (`…tutorial-ssd-particle-caching-in-cryosparc.md` Troubleshooting):

| Message | Meaning | First action |
|---|---|---|
| `cache waiting for requested files to become unlocked` | Another job is mid-copy of the same files | Wait; second job unblocks when first finishes copy. Normal. |
| `cache does not have enough space for download... but there are no files that can be deleted` | A non-CryoSPARC application is holding the SSD | Confirm with `du`/`ls` on `ssd_path`; have the user free the space or move CryoSPARC to a different SSD |
| `cache requires NNN MB more on the SSD for files to be downloaded` (sizes look too large for your selection) | Cache is requesting the entire upstream stack, not your selected subset | Consolidate the stack — Downsample Particles or Restack Particles |
| `File not found` during caching on cluster FS | Pre-v4.6.2 cache fragility on cluster FS | Update to v4.6.2+ (`reference/release_notes/markdown/v4.6.md`) |

If a worker shows persistent SSD problems, also confirm: `--ssdpath` points to a real local SSD; `--ssdquota` / `--ssdreserve` are sane; `nvidia-smi` and `df -h` agree on what storage is available; `CRYOSPARC_SSD_PATH` env var is set correctly if the dynamic-path mechanism is in use.

---

## 10. Failure modes — symptom → layer → first checks

| Symptom | Likely layer | First checks | Escalation / source |
|---|---|---|---|
| Master refuses to start, "DB free space" error | DB volume | `df` the volume holding `CRYOSPARC_DB_PATH`; default floor is `CRYOSPARC_DB_MIN_SPACE_GB = 5` | `14_cli_admin.md`; `…environment-variables-v5.0.md` |
| Master starts but UI is slow / DB-on-disk huge | DB | Compare DB dir size to a fresh `cryosparcm backup` size | `…guide-reduce-database-size-v4.3.md` |
| Project disk usage growing without obvious cause | Project tree (intermediates) | Project-level *Generate Intermediate Results* toggle; per-job intermediate clearing; v4.3+ default is on for new jobs | `…guide-data-management-in-cryosparc-v4.0.md` §4, `reference/release_notes/markdown/v4.2.md` |
| Job fails with "file not found" on rerun after a move | Raw data symlinks | `ls -l` the job's `imported/`; broken symlinks are visible immediately | `…tutorial-migrating-your-cryosparc-instance.md` §A |
| Job sits in queue with "SSD cache: waiting for unlocked" | Cache (cooperating with scheduler) | Normal — wait. Confirm another job on same worker is copying same particles | `…tutorial-ssd-particle-caching-in-cryosparc.md` |
| Cache request sizes much larger than dataset size | Cache (still seeing whole upstream stack) | Confirm with the Inspect Picks / Select 2D filter step; consolidate via Downsample / Restack | same |
| Cache cannot evict, "no files can be deleted" | Cache (foreign occupancy) | Non-CryoSPARC files on the SSD path | same |
| Project shows "Detached" unexpectedly | Lifecycle | Confirm whether someone detached on purpose; do not delete data | `…guide-data-management-in-cryosparc-v4.0.md` §Detach |
| Cannot attach a project — "already locked to another instance" | Lifecycle | Another instance still owns the `cs.lock`; either detach there, or run the *rescue from inoperable instance* flow | `…guide-data-management-in-cryosparc-v4.0.md`; recovery output in `…guide-instance-recovery-v5.0.md` |
| `cryosparcm recover` skipped projects with "Could not access project document" | Recovery — project directory missing or has no `project.json` | Verify the project directory is mounted at the original path before re-running | `…guide-instance-recovery-v5.0.md` |
| `cryosparcm recover` saved an archived project as "detached" | Recovery — expected behavior in v5.0+ | Re-attach the original project directory after recovery to restore processing metadata | same |
| Live session shows "Stale" or "out of date" sizes | Live data management | Refresh project / session stats from the Actions column | `docs/per_page/application-guide__managing-data.md` |
| `TIFFReadDirectory ... Input/output error` on Live worker | Raw data filesystem, not CryoSPARC | Worker `dmesg`, `mount`; sshfs/NFS flakiness | `17_error_lookup.md` |
| Multi-user can read but cannot modify each other's exports | Filesystem permissions | Shared `cryosparc` group + group-write on the relevant directories | `…unix-permissions-and-data-access-control.md` |
| User reports "I deleted the cache and now jobs are slow" | Cache (intentional purge) | Normal — cache re-warms on next run; no data loss | `…tutorial-ssd-particle-caching-in-cryosparc.md` FAQ |
| User reports "I deleted intermediate results and downstream re-run fails" | Intermediate-results semantics | Final-iteration data should be kept by *Clear Intermediate Results*; if downstream depended on an *intermediate* iteration explicitly, that path was always fragile | `…guide-data-cleanup-v4.3.md` |
| User reports "I `rm -rf`'d a project and now the GUI is broken" | Wrong cleanup primitive | The GUI assumed the directory existed (continuous export); detach if still possible, otherwise *Delete Project from Database* on the detached stub (v4.1.2+) | `docs/per_page/application-guide__managing-data.md` warning |
| Repeated Reference-Based Motion Correction + refinement appears to mix half-sets | Workflow bug fixed in version | v4.5.3 changed refinement defaults to inherit half-set split from input particles | `reference/release_notes/markdown/v4.5.md` |

---

## 11. Advisor defaults and red flags

Defaults that should be the agent's recommendation absent a specific reason:

- **Treat the project directory as durable, the SSD cache as ephemeral, and the database as the source of truth.**
- **Keep raw data outside the project directory** — and back it up independently. Archiving a CryoSPARC project does not save raw movies.
- **Use the GUI lifecycle actions** for every project move/delete; never `rm -rf` an attached project.
- **Mark finals before any cleanup.** No exceptions.
- **Take and copy off-master a `cryosparcm backup`** before every update / compact / restore / migration / risky cleanup.
- **Back up `cryosparc_master/run/cryosparc_instance_config_*.tar`** at the same cadence — without it, v5.0+ recovery is much harder (`…guide-instance-recovery-v5.0.md`).
- **Prefer Cleanup Data tool + final-marking** over direct CLI deletion. The tool's preview surfaces what changes; CLI deletion does not.
- **Restack before clearing extraction** if you want a particle subset to survive.
- **Compact the database only after clearing data**, and verify by comparing post-compact size to backup size.
- **Stay version-matched master ↔ worker**; recovery requires identical versions (`…guide-instance-recovery-v5.0.md`).

Red flags — stop the user before they continue:

- "I'll just delete `cs.lock` and re-attach" — only correct in the explicit rescue flow with the original instance demonstrably dead (`…guide-data-management-in-cryosparc-v4.0.md` §Rescuing).
- "I'll move the project directory while it's still attached" — corruption risk; archive first.
- "Let's `chmod -R 777`" — `…unix-permissions-and-data-access-control.md` documents shared-group approaches; the broad chmod is rarely the right tool and weakens isolation across labs.
- "Compact didn't help, let's repeat compact" — re-running `compact` does not unstick a fragmented DB; use backup-restore (`…guide-reduce-database-size-v4.3.md`).
- "Let's lower `CRYOSPARC_DB_MIN_SPACE_GB`" — solves the symptom, not the cause; free DB-volume space instead.
- "Let's edit files inside an archived project directory" — invalidates the unarchive guarantee (`…guide-data-management-in-cryosparc-v4.0.md` §Archive).
- "Let's clear preprocessing on a project whose raw data is gone" — preprocessing is only deterministic-and-recreatable *if the raw data is still there*.
- "Use the SSD path as the project directory" — eviction can corrupt apparent state.
- "Pre-cache via symlink to skip the copy" — supported (FAQ), but only when filesystems are stable; rarely worth the cleverness.

---

## 12. Cross-links

- `14_cli_admin.md` — exact `cryosparcm` / `cryosparcw` syntax, `cryosparcm backup` / `restore` / `compact` / `recover` flags, maintenance mode, update runbook.
- `21_gpu_lane_queue.md` — scheduler view of the cache (lane-scoped); `--ssdpath` / `--ssdquota` / `--ssdreserve` as worker attributes; how cache thrash *looks* like a scheduling problem.
- `13_cryosparc_tools_api.md` — `cryosparc-tools` Python access patterns for jobs/projects, programmatic download/export.
- `15_troubleshooting.md` — the five-bucket triage model; filesystem/path bucket is co-owned with this page.
- `18_decision_trees.md` — decision routing including the "do not chase parameters when the failure is storage/launch" anti-pattern.
- `17_error_lookup.md` — exact-string lookup for cache, symlink, permission, and DB-space errors.
- `25_cryosparc_live.md` — Live UI & session state; this page owns Live data sizing, compaction/restoration, and the session-cell action menu.
- `02_import.md` — Import job semantics (where the symlinks come from).
- `05_extraction_2d.md` — Restack Particles in workflow context.

---

## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

- `topic_plan.md`
- `plan.md`
- `13_cryosparc_tools_api.md`
- `14_cli_admin.md`
- `15_troubleshooting.md`
- `16_tuning_recipes.md`
- `18_decision_trees.md`
- `21_gpu_lane_queue.md`
- `17_error_lookup.md`
- `reference/release_notes/markdown/v4.0.md`
- `reference/release_notes/markdown/v4.1.md`
- `reference/release_notes/markdown/v4.2.md`
- `reference/release_notes/markdown/v4.3.md`
- `reference/release_notes/markdown/v4.4.md`
- `reference/release_notes/markdown/v4.5.md`
- `reference/release_notes/markdown/v4.6.md`
- `reference/release_notes/markdown/v5.0.md`
- `docs/per_page/application-guide__downloading-and-exporting-data.md`
- `docs/per_page/application-guide__inspecting-job-data.md`
- `docs/per_page/application-guide__managing-data.md`
- `docs/per_page/application-guide__projects-workspaces-and-live-sessions.md`
- `docs/per_page/guides-for-v3__tutorial-data-management-in-cryosparc.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__utilities__job-cache-particles-on-ssd.md`
- `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0__cryosparcm-reference-v5.0.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__cryosparc-live-session-data-management-4.7.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__guide-data-cleanup-v4.3.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__guide-data-management-in-cryosparc-v4.0.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__guide-instance-recovery-v5.0.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__guide-reduce-database-size-v4.3.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__tutorial-migrating-your-cryosparc-instance.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__tutorial-ssd-particle-caching-in-cryosparc.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__unix-permissions-and-data-access-control.md`
- `docs/per_page/setup-configuration-and-management__troubleshooting.md`
- `docs/forum_threads/digests/forum_troubleshooting.md`
- `docs/forum_threads/digests/forum_installation.md`
