# Topic 21 — GPU, Lanes, Queue, and Worker Assignment

## Scope
How CryoSPARC schedules and runs work: the master / worker / lane / target / queue / SSD-cache model, where each resource is configured, how to route everyday operational questions (stuck queued job, worker offline, GPU not visible / missing GPU, OOM, slow job, multi-user contention), and which adjacent page actually owns the underlying mechanic so this topic does not duplicate them.

What lives elsewhere:

- `cryosparcm` / `cryosparcw` command surface, restart and instance-state runbooks, log layout, and the *exact* CLI syntax disclaimer — `14_cli_admin.md` and the version-matched references under `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0/…` and `…__management-and-monitoring-4.7/…`.
- SSD and project storage planning, sizing, archival, cleanup — `24_disk_and_storage.md` (this page only covers cache *behavior* visible to the scheduler).
- Python orchestration via `cryosparc-tools` — `13_cryosparc_tools_api.md`.
- Install / connect-worker mechanics end-to-end and worker prerequisites — `01_installation_admin.md`.
- Algorithmic parameter tuning (do *not* tune parameters to compensate for a scheduling problem) — `16_tuning_recipes.md`.
- Error-string lookup → `17_error_lookup.md`; decision-tree routing → `18_decision_trees.md`; debugging mental model → `15_troubleshooting.md`.

Exact CLI flags differ between v5.0+ and v4.7-and-earlier (`docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0__cryosparcm-cli-reference-v5.0.md` notes that `cryosparcm cli` arguments may change between versions). When a recipe requires precise syntax, identify the instance version first and then read `cryosparcm COMMAND --help` / `cryosparcw COMMAND --help` on the target host.

---

## 1. Mental model

The CryoSPARC scheduler has five layers that are easy to confuse. Naming them up front makes every later question route faster.

| Layer | What it is | Where it is configured | Where it is visible |
|---|---|---|---|
| **Master** | Web app + core API + MongoDB. Schedules jobs, owns the database, dispatches over SSH or a cluster submission template. | Single host (4+ CPU, 16GB+ RAM, 250GB+ HDD recommended) | `cryosparcm status`, web UI |
| **Worker** | A host with `cryosparc_worker` installed, registered to a master. May be the same machine as master. Holds GPUs, CPU slots, RAM slots, and an optional SSD cache path. | `cryosparcw connect …` on the worker | `cryosparcm resources`, Instance Information tab |
| **Lane (scheduler target)** | A named group of one or more workers, *or* a single cluster submission template. A worker belongs to *no more than one* lane. | `--lane` on `cryosparcw connect`; for clusters, `name` in `cluster_info.json` | Queue Modal "lane" dropdown; Resource Manager → Instance Information |
| **Queue** | Per-lane FIFO modulated by **priority** (descending) and queue-entry time (ascending tiebreaker). | Per-job priority in the Queue Modal; default user/instance priorities in the admin panel | Resource Manager → Current Jobs, Job History |
| **Resource accounting** | Each worker advertises GPU device IDs, CPU cores, RAM slots (8GiB each), and SSD quota / reserve. The scheduler picks the first lane / target whose free slots satisfy the job's request. | `--cpus`, `--rams`, `--gpus`, `--ssdpath`, `--ssdquota`, `--ssdreserve` on `cryosparcw connect` | `cryosparcm resources [LANE_NAME]` |

Two consequences fall out of the model and are worth committing to memory:

1. **A job queued to lane X stays queued to X even if a different lane has idle resources.** That is intentional. Multi-node lanes pool resources; single-node lanes give predictable placement at the cost of cross-lane idle time (`docs/per_page/setup-configuration-and-management__hardware-and-system-requirements.md`).
2. **GPUs are addressed by index from `0` on the worker.** When CryoSPARC requests N GPUs from a cluster, it will internally try device IDs `[0, … N-1]`. The cluster is responsible for setting `CUDA_VISIBLE_DEVICES` (e.g. via SLURM GRES + cgroups) so the right physical devices are exposed (`docs/per_page/setup-configuration-and-management__how-to-download-install-and-configure__cryosparc-cluster-integration-script-examples.md`).

---

## 2. What this page owns vs adjacent pages

| Question type | Owned by |
|---|---|
| "Why is my job queued?" / "Why are GPUs idle while jobs wait?" / "Why isn't lane X visible?" / "How do I add a worker?" | **this page** |
| "Why is the master / Mongo / supervisor unhealthy?", "What's the exact restart command?", "Where is `command_core` log?" | `14_cli_admin.md` |
| "How big should my SSD be?", "How do I clean up `cryosparc_cache`?", "Project size is growing too fast" | `24_disk_and_storage.md` |
| "Can I script this without clicking through the UI?" | `13_cryosparc_tools_api.md` |
| "What does *this* error string mean?" | `17_error_lookup.md` |
| "I have a slow job — is it a parameter problem?" | first this page (rule out scheduling), then `16_tuning_recipes.md` |
| "Live throughput dropped" | this page for lane/GPU assignment; `25_cryosparc_live.md` for Live session mechanics |

Operational rule: **if a parameter change is being proposed to fix something the user described as "slow" or "stuck", confirm it is not a lane / queue / cache problem first.**

---

## 3. Where to look first

| Surface | Use it for | Source |
|---|---|---|
| Resource Manager → **Current Jobs** | Running and queued jobs, per-job priority, kill button | `docs/per_page/guides-for-v3__user-interface-and-usage-guide__resource-manager.md` |
| Resource Manager → **Instance Information** | Lanes, worker bin path, host name, SSD cache path, cache quota | same |
| Resource Manager → **Job History** | Past job priority and lane assignment | same |
| Job card status color | Purple = building, teal = queued, gray = started, blue = running, green = complete, orange = killed, red = failed | `docs/per_page/guides-for-v3__user-interface-and-usage-guide__queue-job-inspect-job-and-other-job-actions.md` |
| `cryosparcm resources [LANE_NAME]` | Formatted table of scheduler targets and their declared resources | `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0__cryosparcm-reference-v5.0.md` |
| `cryosparcm status` | Master process / supervisor / DB state | same |
| `cryosparcm log command_core` | Worker launch / scheduler / SSH attempts | `17_error_lookup.md` |
| `cryosparcw info --gpu` (on worker) | Lists the GPUs the worker can see | `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0__cryosparcw-reference-v5.0.md` |
| `cryosparcw env` (on worker) | Dumps the env vars the worker uses (`eval $(cryosparcw env)` to activate) | same |
| Cluster scheduler log (`squeue` / `qstat` / job `slurm.out`) | Anything cryoSPARC has handed off to a cluster — including OOM-kill, which the master sees only as a heartbeat loss | `17_error_lookup.md` |

**v5.0+** surfaces lane / target resource exhaustion more clearly in the UI than older versions did, so when triaging a queued job on a recent instance, check the Queue Modal / Resource Manager *before* opening logs (`reference/release_notes/markdown/v5.0.md`, `15_troubleshooting.md`).

---

## 4. Lanes — assignment and restriction

### Lane shape

- A lane can hold one or many workers; a worker belongs to one lane (`docs/per_page/setup-configuration-and-management__hardware-and-system-requirements.md`).
- The lane named `default` is created if no lane is specified at `cryosparcw connect` time (`--lane TEXT [default: default]`, `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0__cryosparcw-reference-v5.0.md`).
- Single-node lanes are preferable when hardware (GPU VRAM, RAM, CPU count) varies meaningfully between hosts — Hetero Refine on a 24GB card and a 11GB card on the same lane is asking for trouble.
- Multi-node lanes are preferable when hosts are homogeneous and you do not care which one runs a job.

### Per-user lane assignment (v4.1+)

CryoSPARC users have explicit lane access. New users inherit access to all lanes; new lanes are assigned to all users by default. Access is editable from the admin panel's "Lane Restrictions" tab and from the CLI (`docs/per_page/setup-configuration-and-management__software-system-guides__guide-lane-assignments-and-restrictions.md`):

| Operation | v5 | v4 |
|---|---|---|
| Get user's lanes | `cryosparcm cli "api.users.get_lanes('user@host')"` | `cryosparcm cli "get_user_lanes('user@host')"` |
| Set user's lanes | `cryosparcm cli "api.users.set_lanes('user@host', ['lane1'])"` | `cryosparcm cli "set_user_lanes('user@host', ['lane1'])"` |

A user who is not assigned to a lane cannot queue jobs there. This is one of the most common "why does my user not see lane X?" causes — check lane assignment before suspecting a worker problem.

### Live's three lane types

CryoSPARC Live operates against **three** task types that are mapped onto lanes per session (`docs/per_page/live__prerequisites-and-compute-resources-setup.md`):

1. **Preprocessing lane** — motion, CTF, picking, extraction. Each Live preprocessing worker pins one GPU. Memory bandwidth >100 GB/s is recommended.
2. **Reconstruction lane** — Streaming 2D / Streaming Refinement.
3. **Auxiliary lane** — transient jobs (template-creation 2D, ab-initio).

**v5.0+** adds a `Workers per GPU` setting for Live preprocessing — running more than one Live worker per GPU can improve throughput on some systems (`reference/release_notes/markdown/v5.0.md`).

### Verify before changing

Before changing a lane's worker membership or a user's lane access:

- [ ] `cryosparcm resources` shows the lane currently exists and lists which workers are in it.
- [ ] No active jobs are queued or running on the lane (or you are explicit about preempting them).
- [ ] The user actually wants to *lose* access to the other lanes — `set_lanes` overwrites the list, it does not add to it.
- [ ] For cluster lanes, the cluster's GPU/CPU/RAM accounting still matches the lane template after the change.

---

## 5. Worker registration concepts

`cryosparcw connect` is the registration entry point (run *on the worker*, as the cryoSPARC owner). The full option list is in `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0__cryosparcw-reference-v5.0.md`; the operationally important ones:

| Flag | What it declares |
|---|---|
| `--master`, `--port` | Where the master is (and the base port, default 61000) |
| `--worker` | Worker host name as the master will record it |
| `--sshstr` | Optional non-default SSH login string master → worker |
| `--lane` | Lane to join (created if it does not exist) |
| `--cpus` | CPU cores exposed to jobs; default = all cores |
| `--rams` | 8GiB RAM *slots* exposed; default = all |
| `--gpus` | Comma-separated device IDs (e.g. `0,1,2`); default = all |
| `--gpu / --no-gpu` | CPU-only worker (`--no-gpu`); cannot combine with `--gpus` |
| `--ssdpath`, `--ssdquota`, `--ssdreserve` | Local SSD scratch path; cache quota; minimum free space (default reserve 10000 MB) |

The official example (`docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0__cryosparcw-reference-v5.0.md`):

```bash
cryosparcw connect \
    --worker $(hostname -f) \
    --master csmaster.local \
    --port 61000 \
    --ssdpath /scratch/cryosparc_cache \
    --lane $(hostname -s)
```

Operational notes:

- **RAM is counted in 8GiB slots**, not bytes — `--rams 8` exposes 64GiB to the scheduler.
- **Omitting `--ssdpath` means no SSD caching on this worker**, which makes the worker unsuitable for refinement / classification / reconstruction unless you intentionally want every cache request to bypass.
- A worker that has no GPU (pre-processing-only) is registered with `--no-gpu` and should generally live in its own lane so users do not accidentally queue 3D refinements there.

### High-level worker-side environment variables

| Variable | Where | Purpose |
|---|---|---|
| `CRYOSPARC_LICENSE_ID` | `cryosparc_worker/config.sh` | License key |
| `CRYOSPARC_USE_GPU` | `cryosparc_worker/config.sh` | Enable GPU |
| `CRYOSPARC_CUDA_PATH` | `cryosparc_worker/config.sh` | CUDA install |
| `CRYOSPARC_SSD_PATH` | `cryosparc_worker/config.sh` | Cache path. Can be set to another shell variable (e.g. `$CUSTOM_DYNAMIC_SSD_PATH`) to use a per-job dynamically-allocated SSD path (`docs/per_page/setup-configuration-and-management__software-system-guides__tutorial-ssd-particle-caching-in-cryosparc.md`). |
| `CRYOSPARC_SSD_CACHE_LIFETIME_DAYS` | `cryosparc_master/config.sh` | Cache file lifetime (default 30 days; v3.3+) |
| `CRYOSPARC_CLI_SKIP_ACCESS_CHECK=true` | both master and worker (v5.0+) | Bypass UNIX-permission reachability checks when reported permissions are misleading (`reference/release_notes/markdown/v5.0.md`) |

**Deprecated**: `CRYOSPARC_DISABLE_IMPORT_ON_MASTER` is no longer used as of v4.3 — import / utility jobs can be launched on any worker lane (`reference/release_notes/markdown/v4.3.md`). If a recipe online still references it, the recipe is stale.

Do **not** invent env-var names; if a user proposes one not on the list above (or in the version-matched docs), look it up before applying it.

---

## 6. Cluster integration

For cluster lanes the lane is described by two files (`docs/per_page/setup-configuration-and-management__how-to-download-install-and-configure__cryosparc-cluster-integration-script-examples.md`):

- `cluster_info.json` — name, worker bin path, submit/poll/cancel/info command templates, optional cache path.
- `cluster_script.sh` — submission script template the master fills in per job.

The official documentation provides SLURM, PBS, and Gridengine examples; the agent should never improvise a new template, only adapt the documented example for the target site.

### Reserved cluster template variables

These variables are filled in by CryoSPARC and **cannot be overridden** by custom variables (`docs/per_page/setup-configuration-and-management__software-system-guides__guide-configuring-custom-variables-for-cluster-job-submission-scripts.md`):

```
{{ run_cmd }}           {{ num_cpu }}          {{ num_gpu }}
{{ ram_gb }}            {{ job_dir_abs }}      {{ project_dir_abs }}
{{ job_log_path_abs }}  {{ worker_bin_path }}  {{ run_args }}
{{ project_uid }}       {{ job_uid }}          {{ job_creator }}
{{ cryosparc_username }} {{ job_type }}        {{ command }}
```

### Custom variables (v4.1+)

User-defined variables can be injected into the cluster submission template at three scopes — **instance**, **target**, **job** — with job > target > instance precedence. Use them to adjust requested RAM / GPU type / queue partition / accounting key per job without rewriting the template (`docs/per_page/setup-configuration-and-management__software-system-guides__guide-configuring-custom-variables-for-cluster-job-submission-scripts.md`).

### GPU allocation rule on clusters

CryoSPARC requests `num_gpu` GPUs and then uses device indices starting from `0`. It is the cluster's job (SLURM GRES + cgroups, PBS `ngpus`, etc.) to set `CUDA_VISIBLE_DEVICES` so those indices map to the right physical devices and isolate them from other jobs. If two cryoSPARC jobs collide on the same physical GPU, look at the cluster's GPU isolation policy first, not at cryoSPARC.

---

## 7. Queue mechanics

### Queueing a job

1. Job Builder → Queue. Pick the lane (default: current active workspace's last-used lane on v4.4+). Optionally set priority. Click Create (`docs/per_page/guides-for-v3__user-interface-and-usage-guide__queue-job-inspect-job-and-other-job-actions.md`).
2. The scheduler matches the job's resource request against the lane's free slots in priority order.

### Job chaining

Downstream jobs can be queued before upstream outputs exist. They sit in **"Queued — waiting because inputs are not ready"** until the upstream job emits the relevant output group, then start automatically (`docs/per_page/guides-for-v3__user-interface-and-usage-guide__queue-job-inspect-job-and-other-job-actions.md`). This is the canonical way to assemble a multi-step pipeline through the GUI without `cryosparc-tools`.

### Status colors at a glance

Purple build / teal queued / gray started / blue running / green complete / orange killed / red failed.

### Killing / clearing a job

- Kill from Resource Manager → Current Jobs.
- "Clear" wipes results and outputs but preserves inputs and parameters — useful for re-running with one parameter change. Also resets queued jobs to building state (`docs/per_page/guides-for-v3__user-interface-and-usage-guide__queue-job-inspect-job-and-other-job-actions.md`).

---

## 8. Priority queue

Priority (v3.0+) is a per-job integer 0–100, sorted descending; ties broken by queue-entry time ascending (`docs/per_page/setup-configuration-and-management__software-system-guides__tutorial-priority-job-queuing.md`).

- New jobs inherit **user default** if set, else **instance default**, else 0.
- Admins control who can modify priority in the Admin Panel → Manage Users → "Job Priority Management" column.
- Visible in: Queue Modal (when allowed), Resource Manager → Current Jobs (green badge + exclamation mark), Job History → Priority column, Job Details panel, Metadata tab.
- Live sessions pass priority down: every job a session spawns (Live preprocessing worker, Streaming 2D, Streaming Refinement, Ab-Initio) inherits the session's priority.

Advisor framing for multi-user contention: priority is the right knob; **changing lane membership to "fix" priority is usually wrong**, because it permanently rebalances resources rather than just reordering the queue.

**v4.1.1 fix** worth remembering on older instances: prior to v4.1.1, restarted GPU jobs could jump to the front of the queue on the specified lane, defeating priority (`reference/release_notes/markdown/v4.1.md`). If a user is on a pre-v4.1.1 instance and asks why priority "doesn't work" after a restart, update before debugging.

---

## 9. SSD particle cache — behavior visible to the scheduler

(Storage sizing, cleanup policy, and disk-budget reasoning live in `24_disk_and_storage.md`. This section is only what affects scheduling and job runtime.)

### Which jobs use it

Cache is intended for "classification, refinement, and reconstruction jobs that deal with particles" — jobs with random-access patterns over the particle stack. Preprocessing nodes (motion, CTF, picking) do **not** need an SSD (`docs/per_page/setup-configuration-and-management__software-system-guides__tutorial-ssd-particle-caching-in-cryosparc.md`).

A dedicated **Cache Particles on SSD** utility job exists for pre-warming the cache without holding a GPU (`docs/per_page/processing-data__all-job-types-in-cryosparc__utilities__job-cache-particles-on-ssd.md`).

### Cache size rule of thumb

```
Dataset Size = (4 * box_size^2 + nsymbt + header_length) * num_particles
```

Example: 1,000,000 particles at box 256 ≈ 263.3 GB. 2TB SSDs are recommended for the largest stacks (`docs/per_page/setup-configuration-and-management__software-system-guides__tutorial-ssd-particle-caching-in-cryosparc.md`).

### Common runtime cache messages

| Message | Meaning | Action |
|---|---|---|
| `SSD cache : … waiting for unlocked files` | Another cryoSPARC job in the same project is currently copying the same particles. Job B waits, then re-uses the cached copy when Job A unlocks. | Wait. Do **not** delete locks unless you have verified the holding process is gone. |
| `SSD cache : cache does not have enough space for download… but there are no files that can be deleted` | Another cryoSPARC job (or a non-cryoSPARC file) is occupying the cache. | If non-cryoSPARC, clean manually; CryoSPARC will not delete files it does not own. |

The cache is read-only — files can be deleted at any time without corrupting state, and symlinks of the right size / mtime are honored (the cache uses path + size + mtime to decide whether to skip the copy).

### Cache lifetime

Default 30 days since last access (v3.3+). Adjustable via `CRYOSPARC_SSD_CACHE_LIFETIME_DAYS` in `cryosparc_master/config.sh`.

### Version-aware: do not deep-debug cache on old versions

The SSD cache layer was substantially rewritten:

- v4.1: "free SSD cache storage calculation" fix — prevents infinite cache hang when storage *is* available.
- v4.2: SSD cache retries up to 3× on network timeout.
- v4.3: cache speedups via fewer file lookups, better cache logging.
- v4.4 / v4.5 / v4.6: progressive robustness improvements on cluster filesystems; "File not found" during caching should no longer occur on v4.6.
- v5.0: silent SSD-cache copy-failure fallback improved; some NFS permission issues fixed; `CRYOSPARC_CLI_SKIP_ACCESS_CHECK=true` added for misleading-permissions environments.

If a user is more than two minor versions behind and reports a cache problem, update before debugging (`reference/release_notes/markdown/v4.1.md` … `v5.0.md`, `15_troubleshooting.md`).

---

## 10. GPU memory and box size

GPU OOM during refinement / reconstruction is almost always a box-size vs VRAM mismatch. The reference table for Homogeneous, Helical, and Local Refinement (with non-uniform regularization disabled) is (`docs/per_page/processing-data__tutorials-and-case-studies__performance-metrics.md`):

| GPU VRAM (GB) | Approx. max volume box size (px) |
|---|---|
| 4 | 682 |
| 8 | 872 |
| 11 | 976 |
| 12 | 1004 |
| 16 | 1110 |
| 24+ | 1126 |

Mitigation knobs (in order of preference):

1. **Reduce "GPU batch size of images" / "Computational minibatch size"** for the offending job type.
2. **Downsample Particles** to shrink the box (and maximum resolution) — only when downstream interpretation tolerates the new Nyquist.
3. **NU Refinement → enable "Low-memory mode"** to revert to the pre-v4.4 NU path (`16_tuning_recipes.md`).
4. Move the job to a worker with a larger VRAM card.

### Multi-GPU caveats and version notes

| Symptom | Cause / fix | Source |
|---|---|---|
| `cufftAllocFailed` / `cufftInternalError` during extraction | Pre-v4.1 Extract from Micrographs used excessive GPU memory. Update. | `reference/release_notes/markdown/v4.1.md`, `16_tuning_recipes.md` |
| Blank / faint 2D classes on multi-GPU | Pre-v4.2 multi-GPU 2D bug; v4.6 improves CPU requests for multi-GPU 2D classification. | `reference/release_notes/markdown/v4.2.md`, `v4.6.md` |
| Reference-Based Motion Correction fails on GPUs in `EXCLUSIVE_PROCESS` mode | Pre-v4.4.1+240110 bug; fixed. | `reference/release_notes/markdown/v4.4.md` |
| Worker processes slow / unstable on multi-GPU nodes with many simultaneous jobs | v4.6.2 changed workers to request *not always* transparent hugepages; the OS "always THP" setting also produces a job-log warning now. | `reference/release_notes/markdown/v4.6.md` |
| 3D Flex Generator OOM on large datasets | v4.5.3+240807 fixed an OOM in 3D Flex Generator. | `reference/release_notes/markdown/v4.5.md` |

---

## 11. Performance bottleneck diagnosis

When a user says "it's slow," resist the urge to tune algorithms first. The actual bottleneck almost always lives in one of the layers below.

| Layer | Symptoms | First checks |
|---|---|---|
| **GPU** | OOM, `cufft*` errors; long iterations on small datasets; can't fit box | Box vs VRAM table; batch size; `nvidia-smi`; multi-GPU compat for the version installed |
| **CPU** | GPUs idle but queue is long; multi-GPU jobs underperform | CPU starvation — cryoSPARC needs enough CPU per GPU to feed work. `cryosparcm resources` for declared CPU slots; per-job CPU request; v4.6 improved CPU requests for multi-GPU 2D (`16_tuning_recipes.md`, `reference/release_notes/markdown/v4.6.md`) |
| **RAM** | Job log warns about insufficient RAM; OS swaps; hostnode OOM-kills the process (cluster shows OOM-kill in scheduler log, master sees only heartbeat loss) | Job's declared `ram_gb`; lane RAM-slot accounting; OS / cgroup limits; transparent hugepages (`reference/release_notes/markdown/v4.6.md`) |
| **Disk / network / SSD cache** | Extraction is slower than expected; "waiting for unlocked files"; cache messages; long initial cache copy then fast iterations | Cache hit/miss; project filesystem vs SSD; cluster NFS latency; **older instances** had cache reliability issues (see §9) |
| **Box size / particle count** | Per-iteration time scales superlinearly when box grows; resolution near Nyquist | Box vs VRAM table; Downsample Particles; whether the question requires that box size |
| **Algorithm choice** | Slow but *correct* output | Last resort — only after the above are clean. Then `16_tuning_recipes.md`. |

### Use the Benchmark job before claiming "slow"

The **Benchmark** job (v4.3+) runs CPU, Filesystem, and GPU benchmarks in series on a worker lane and writes JSON + CSV results into the job directory. The benchmark data package (~17 GB) is auto-downloaded if missing (`docs/per_page/setup-configuration-and-management__software-system-guides__guide-performance-benchmarking-v4.3.md`).

- Compare to the Structura reference results and to past runs of your own.
- v4.4 added a `class3D-small` benchmark for minimum hardware (32GB DRAM, 11GB VRAM) — useful as a floor (`reference/release_notes/markdown/v4.4.md`).
- **v5.0+ benchmarks are not backward compatible**: downgrade drops them. Do not mix v4 and v5 benchmark results in a single comparison.

For end-to-end realism, the **Extensive Validation** job (formerly Extensive Workflow, v4.3+) exercises a full processing chain.

### Live throughput reference points

For comparison when a Live session feels slow (`docs/per_page/live__performance-metrics.md`):

- K3: 450+ exposures / hour / GPU (1,800+ on a 4-GPU machine).
- K2 / Falcon: 650+ exposures / hour / GPU.
- Sustained: one movie / 30 s ≈ 2,500 movies / GPU / day, up to ~8,000 on well-tuned systems.
- Minimum recommended: 4 GPUs for "seamless" Live.

If a Live instance is well below these per-GPU numbers and storage I/O is healthy, the bottleneck is usually CPU memory bandwidth (recommended >100 GB/s) or under-allocated preprocessing workers.

---

## 12. Failure modes — symptom → layer → first check

| Symptom | Likely layer | First check | Escalation / source |
|---|---|---|---|
| `non-zero exit status 255` on worker launch | SSH from master to worker — banner / MOTD / login-shell output | Run `ssh worker "true"` non-interactively as the cryoSPARC owner; inspect `cryosparcm log command_core` | Silence `.bashrc` / `.profile`; passwordless SSH; v5.0 fixed worker launch on `tcsh` and extra shell-startup output (`17_error_lookup.md`, `reference/release_notes/markdown/v5.0.md`) |
| `non-zero exit status 1` / `FAILED TO LAUNCH ON WORKER NODE return code 1` | Worker env / shell after SSH succeeded | `cryosparcm log command_core`; manually `eval $(cryosparcw env); bin/cryosparcw …` as cryoSPARC owner | `17_error_lookup.md` |
| `Job must be queued on the master node` | Interactive job (Select 2D, Curate Exposures, interactive Volume Tools) queued to a non-master lane | Route to the master lane | `18_decision_trees.md` |
| `pymongo … ServerSelectionTimeoutError`, `database: ERROR (spawn error)` | Master Mongo / supervisor | `cryosparcm status`; `cryosparcm log database`; `cryosparcm log supervisord` | `14_cli_admin.md` |
| Job "stuck" on cluster with no traceback | SLURM/PBS OOM-kill — master only sees heartbeat loss | `squeue` / `qstat`; cluster job's `.out`/`.err`; node OOM-killer logs | `17_error_lookup.md` |
| Job queued forever, workers idle in matched lane | Lane assignment / per-user lane access / resource slot mismatch | `cryosparcm resources`; user's lane list; required GPU / CPU / RAM vs declared | this page §4, `docs/per_page/setup-configuration-and-management__software-system-guides__guide-lane-assignments-and-restrictions.md` |
| Job queued forever, workers visibly busy | Working as intended — queue ordering or no free slots | Priority; running-job ETAs; consider a different lane | this page §8 |
| Lane visible to admin but not user | User not assigned to that lane (v4.1+) | `api.users.get_lanes(…)` / `get_user_lanes(…)` | this page §4 |
| GPU not detected on worker | Driver / CUDA / `--gpus` mask | `cryosparcw info --gpu`; `nvidia-smi`; check `--gpus` argument when worker was connected | `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0__cryosparcw-reference-v5.0.md` |
| Wrong GPU used on cluster | `CUDA_VISIBLE_DEVICES` not set by cluster; cryoSPARC starts at device 0 | Inspect cluster GRES / cgroup setup | `docs/per_page/setup-configuration-and-management__how-to-download-install-and-configure__cryosparc-cluster-integration-script-examples.md` |
| GPU OOM at large box | Box vs VRAM mismatch | Reduce batch size → Downsample → larger VRAM worker | this page §10 |
| `cufftAllocFailed` / `cufftInternalError` (extraction) | Pre-v4.1 GPU memory issue | Update | `reference/release_notes/markdown/v4.1.md` |
| Blank / faint 2D classes on multi-GPU | Pre-v4.2 multi-GPU bug; v4.6 CPU requests | Update | `reference/release_notes/markdown/v4.2.md`, `v4.6.md` |
| SSD cache hangs / "waiting for unlocked files" | Lock contention with another in-flight job (often legitimate) | Wait for holder; verify holding process; v4.4–v4.6 cache rewrites | this page §9 |
| `cache does not have enough space … nothing to delete` | Non-cryoSPARC file occupying SSD, or another active job | Manually clean non-cryoSPARC content; wait if cryoSPARC owns the space | this page §9 |
| "File not found" during caching on cluster filesystems | Pre-v4.6 NFS/cluster-FS cache bug | Update to v4.6+ | `reference/release_notes/markdown/v4.6.md` |
| Master and worker see different paths for the same string | Namespace / mount / permission mismatch — not a cryoSPARC bug | Resolve the path from the worker shell as the cryoSPARC owner; `CRYOSPARC_CLI_SKIP_ACCESS_CHECK=true` on v5.0+ if reported UNIX permissions are misleading | `17_error_lookup.md`, `reference/release_notes/markdown/v5.0.md` |
| Transparent hugepages warning in job log | OS set to "always" THP | v4.6.2 mitigation — worker now requests "not always THP"; OS warning is still surfaced | `reference/release_notes/markdown/v4.6.md` |

---

## 13. Runbooks

### Add a worker / GPU

1. Install `cryosparc_worker` on the host; set `CRYOSPARC_LICENSE_ID`, `CRYOSPARC_USE_GPU`, `CRYOSPARC_CUDA_PATH`, and (if applicable) `CRYOSPARC_SSD_PATH` in `cryosparc_worker/config.sh`.
2. Confirm GPUs are visible: `bin/cryosparcw info --gpu`.
3. From the master host, verify passwordless SSH: `ssh new-worker "true"` runs silently as the cryoSPARC owner.
4. Confirm master TCP ports (10 consecutive starting at the base port, default 61000) are reachable from the worker.
5. On the worker, run `cryosparcw connect …` with `--master`, `--port`, `--worker`, `--lane`, and explicit `--cpus`, `--rams`, `--gpus`, `--ssdpath` if you do not want defaults.
6. Verify in `cryosparcm resources [LANE_NAME]` that slots are advertised correctly.
7. Queue a small job (e.g. Patch Motion on a handful of movies, or the Benchmark job) to confirm end-to-end.

### Change lane restrictions (per user)

1. Get the current list: `api.users.get_lanes(…)` (v5) / `get_user_lanes(…)` (v4).
2. Decide the **complete** new list — `set_lanes` overwrites.
3. Confirm no in-flight job will be orphaned by the change.
4. Apply: `api.users.set_lanes(…, [new_list])` (v5) / `set_user_lanes(…, [new_list])` (v4).
5. Have the user reload the UI and re-confirm the lane dropdown.

### Triage a queued job

- [ ] Resource Manager → Current Jobs: still queued or just slow to start?
- [ ] Right lane? Re-open the Queue Modal and verify the lane selection.
- [ ] User assigned to that lane?
- [ ] `cryosparcm resources LANE` shows free GPU / CPU / RAM that meets the job request?
- [ ] Higher-priority jobs in front of it?
- [ ] For cluster lanes, `squeue` / `qstat` shows the submission accepted? Look there before the cryoSPARC logs.
- [ ] `cryosparcm log command_core` for launch attempts and SSH errors.
- [ ] If "Queued — waiting because inputs are not ready" — that is the chain mechanism; an upstream job has not produced the relevant output yet.

### Triage a GPU OOM / CUDA failure

- [ ] Capture the **exact** error text. Generic `RuntimeError` is not enough.
- [ ] Job type, box size, batch size / minibatch size, number of GPUs.
- [ ] `nvidia-smi` on the worker: which device, how much VRAM, is anything else using it.
- [ ] Cross-check box vs VRAM table (§10).
- [ ] Try in order: lower batch size → enable Low-memory mode (NU) → Downsample → larger-VRAM worker.
- [ ] If the error is `cufftAllocFailed` / `cufftInternalError`, blank/faint 2D on multi-GPU, or RBMC failure on `EXCLUSIVE_PROCESS` GPUs: check the instance version against §10 — update if behind.
- [ ] Confirm CUDA driver / library compatibility with the worker's installed cryoSPARC version (`15_troubleshooting.md`).

### Triage "the job is slow"

- [ ] Verify whether the user is comparing against a meaningful baseline (Benchmark job, past run of the *same* job, Live throughput numbers in §11).
- [ ] Is the bottleneck GPU (saturated `nvidia-smi`), CPU (idle GPU, busy CPU), I/O (idle GPU + CPU, busy disk / network), or RAM (swap, OOM-kill)?
- [ ] If GPUs are idle and queue is long → CPU starvation. Inspect declared CPU per GPU on the lane.
- [ ] If first iteration is slow but subsequent ones are fast → SSD cache copy on the first pass. Pre-cache via the **Cache Particles on SSD** utility job next time.
- [ ] If the instance is more than two minor versions behind, update before deeper debugging.
- [ ] If on a cluster, check that GPU isolation (GRES + cgroups for SLURM; `ngpus` for PBS) is actually constraining each cryoSPARC job to the GPUs it was allocated.

### Triage multi-user / priority queue contention

- [ ] Confirm priority is the actual lever — if so, set per-job priority or the user / instance default in the Admin Panel.
- [ ] Do not "fix" priority by changing lane membership.
- [ ] On pre-v4.1.1 instances, restarted GPU jobs were a known queue-jump source — update or do not restart contested jobs.
- [ ] Live sessions inherit priority; raising a session priority raises everything it spawns.

---

## 14. Advisor defaults and red flags

**Advisor defaults**

- The simplest setup (master + worker on one workstation, default lane) is fine until there are >1 GPU node or contested users. Do not introduce lane structure prematurely.
- Always configure an SSD path on workers that will run refinement / classification / reconstruction. Workers that will only do preprocessing do not need one.
- For new clusters: copy the documented SLURM / PBS / Gridengine example and adapt — do not write the template from scratch.
- For multi-user contention, reach for **priority** before lane changes.
- Before deep-debugging GPU / cache / launch issues, check the master and worker versions; if more than two minor versions behind a known fix, update first.
- Use the **Benchmark** job before declaring "slow" — and again after major changes (driver, OS, cluster config).
- When a user proposes an algorithm parameter change to fix a "slow" or "stuck" symptom, confirm the layer first (this page §11). Do not tune to compensate for a scheduling problem.

**Red flags — stop normal routing**

- `FAILED TO LAUNCH ON WORKER NODE` or `non-zero exit status 255` → SSH / banner / shell-startup, not the cryo-EM problem the user is asking about.
- Job text shows `Job must be queued on the master node` → interactive job on a non-master lane.
- `pymongo … ServerSelectionTimeoutError` / `database: ERROR (spawn error)` → master Mongo / supervisor — escalate to `14_cli_admin.md`.
- Cluster job "stuck" with no traceback → check scheduler OOM-kill *before* anything else.
- A path is "missing" but works from the master shell — verify it from the **worker** shell as the cryoSPARC owner.
- SSD cache "waiting for unlocked files" with no other cryoSPARC job in flight → stale lock; investigate before deleting.
- The user proposes inventing an environment variable not present in the version-matched docs → look it up before applying.
- The user mentions a forum recipe that references `CRYOSPARC_DISABLE_IMPORT_ON_MASTER` or older single-GPU-only behavior → assume stale (v4.3+).

---

## 15. Version-aware caveats (compact list)

| Version | Change relevant to lane / queue / GPU |
|---|---|
| v4.0 | SSH/launch fix class for system library mismatches; first applicable lane pre-selected when queueing from sidebar. |
| v4.1 | Lane assignment / restriction (Admin Panel + `api.users` CLI); custom cluster-submission variables (instance / target / job scope); cluster_info `cache_path`; SSD-cache retries up to 3× on network timeout (v4.1.x); Extract from Micrographs (GPU) memory pressure reduced; restarted GPU job no longer queue-jumps (v4.1.1). |
| v4.2 | Blank / faint 2D classes on multi-GPU fixed; further SSD-cache fixes. |
| v4.3 | Cache speedups via fewer file lookups + better logs; import / utility jobs now runnable on any worker lane (`CRYOSPARC_DISABLE_IMPORT_ON_MASTER` removed); Benchmark job introduced. |
| v4.4 | SSD-cache rewrite for cluster filesystems (continues into v4.5 / v4.6); RBMC on `EXCLUSIVE_PROCESS` GPUs fixed (v4.4.1+240110); Benchmark adds `class3D-small`; "last used lane" auto-selection when queueing via sidebar. |
| v4.5 | More cache robustness and NU memory paths. |
| v4.6 | Worker requests "not always" transparent hugepages; OS warning surfaced in job log; multi-GPU 2D CPU requests improved (v4.6); cluster-filesystem cache `File not found` should no longer occur. |
| v5.0 | Worker launch on `tcsh` and extra shell-startup output fixed; lane / target resource exhaustion surfaced more clearly in UI; `CRYOSPARC_CLI_SKIP_ACCESS_CHECK=true` for misleading-permissions environments; Live `Workers per GPU`; Benchmark format **not** backward compatible with v4. |

---

## 16. Cross-links

- `14_cli_admin.md` — `cryosparcm` / `cryosparcw` mental model, exact-syntax disclaimer, logs, restart runbooks.
- `24_disk_and_storage.md` — SSD sizing, project storage planning, cleanup.
- `13_cryosparc_tools_api.md` — scripted queueing, dataset I/O, automation boundary.
- `15_troubleshooting.md` — five-bucket triage; GPU/CPU/RAM/scheduling bucket overlaps heavily with this page.
- `16_tuning_recipes.md` — algorithmic parameter tuning *after* scheduling is ruled out.
- `18_decision_trees.md` — Tree 11 (troubleshooting escalation) and other "what next?" routes.
- `25_cryosparc_live.md` — Live session mechanics; this page covers Live's lane shape only.
- `01_installation_admin.md` — install / connect-worker end-to-end.
- `17_error_lookup.md` — error-string → first action.
- `version_caveats.md` — fuller per-version behavior changes.

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
- `17_error_lookup.md`
- `docs/per_page/setup-configuration-and-management__hardware-and-system-requirements.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__guide-lane-assignments-and-restrictions.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__tutorial-priority-job-queuing.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__tutorial-ssd-particle-caching-in-cryosparc.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__guide-performance-benchmarking-v4.3.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__guide-configuring-custom-variables-for-cluster-job-submission-scripts.md`
- `docs/per_page/setup-configuration-and-management__how-to-download-install-and-configure__cryosparc-cluster-integration-script-examples.md`
- `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0__cryosparcm-reference-v5.0.md`
- `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0__cryosparcw-reference-v5.0.md`
- `docs/per_page/guides-for-v3__user-interface-and-usage-guide__resource-manager.md`
- `docs/per_page/guides-for-v3__user-interface-and-usage-guide__queue-job-inspect-job-and-other-job-actions.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc__utilities__job-cache-particles-on-ssd.md`
- `docs/per_page/processing-data__tutorials-and-case-studies__performance-metrics.md`
- `docs/per_page/live__prerequisites-and-compute-resources-setup.md`
- `docs/per_page/live__performance-metrics.md`
- `reference/release_notes/markdown/v4.0.md`
- `reference/release_notes/markdown/v4.1.md`
- `reference/release_notes/markdown/v4.2.md`
- `reference/release_notes/markdown/v4.3.md`
- `reference/release_notes/markdown/v4.4.md`
- `reference/release_notes/markdown/v4.5.md`
- `reference/release_notes/markdown/v4.6.md`
- `reference/release_notes/markdown/v5.0.md`
- `docs/forum_threads/digests/forum_troubleshooting.md`
- `docs/forum_threads/digests/forum_installation.md`
