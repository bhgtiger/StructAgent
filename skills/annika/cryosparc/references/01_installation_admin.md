# Topic 01 — Installation and Administration Orientation

## Scope
This page is an **advisor/admin orientation** for a cryoSPARC instance, not a substitute for the official installer. It is meant to give an agent (and the user it is helping) a fast, conservative mental model of how cryoSPARC is laid out on disk and on the network, what the install/connect/update flow actually requires, where the typical failure modes are, and which adjacent topic owns the next layer of detail.

What this page does **not** duplicate:

- Full `cryosparcm` / `cryosparcw` flag reference, log layout, restart/maintenance/backup runbook syntax, version-specific CLI differences — `14_cli_admin.md` and the version-matched references under `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0/…` and `…__management-and-monitoring-4.7/…`.
- Lane / queue / GPU / SSD-cache *scheduling behavior*, multi-user contention, GPU-not-visible debugging — `21_gpu_lane_queue.md`.
- Project directory tree, MongoDB sizing, SSD planning, archive/compact/restore, raw-data symlink hygiene — `24_disk_and_storage.md`.
- Python automation via `cryosparc-tools`, programmatic project/job orchestration — `13_cryosparc_tools_api.md`.
- Error-string lookup and symptom-pattern triage — `17_error_lookup.md`.
- General troubleshooting mental model — `15_troubleshooting.md`.

**Standing version disclaimer.** The bundled docs in this skill cover roughly v4.0 through **v5.0 BETA** (released 2026-01-27, see `reference/release_notes/markdown/v5.0.md`). Two version-specific facts dominate everything else on this page:

1. v5.0+ and ≤v4.7 have **separate management/monitoring reference pages** in the upstream docs. Before quoting an exact `cryosparcm` flag or environment variable, check `cryosparcm status` for the installed version and consult the version-matched page in `docs/per_page/`.
2. v4 → v5 is a one-way migration in practice (downgradeable only to v4.4+), and v5 has stricter OS/driver/GPU requirements than v4. See `docs/per_page/setup-configuration-and-management__software-system-guides__guide-updating-to-cryosparc-v5.md`.

## Install mental model

cryoSPARC is split into **master** processes and **worker** processes that share project storage. Both halves are part of one logical instance and *must* be the same version (`docs/per_page/setup-configuration-and-management__troubleshooting.md` flags "Version mismatch! Worker and master versions are not the same" as a recurring symptom).

| Layer | What runs there | Where it lives |
|---|---|---|
| Master node | Web app, command_core, command_vis, command_rtp, app_api, supervisor, MongoDB database | `cryosparc_master/` install dir; DB at `$CRYOSPARC_DB_PATH`; ~4 CPUs / 16 GB RAM / 250 GB HDD minimum |
| Worker node(s) | GPU compute (`cryosparc_worker` Python + bundled CUDA in v4.4+) | `cryosparc_worker/` install dir on each GPU host; NVIDIA driver required |
| Shared project storage | All project directories, raw data, intermediates | Filesystem path(s) reachable from both master and every worker at the **same absolute path** |
| SSD cache (worker-local) | Particle cache to avoid network reads | A per-worker `cache_path` / SSD path configured at `cryosparcw connect` time |

Master process list shown by `cryosparcm status` (see `docs/per_page/setup-configuration-and-management__management-and-monitoring-4.7__cryosparcm-4.7.md`):

```
app             app_api         command_core    command_rtp
command_vis     database        app_legacy (optional, off by default in v4+)
```

Supported topologies (`docs/per_page/setup-configuration-and-management__hardware-and-system-requirements.md`):

| Topology | Use when | Notes |
|---|---|---|
| **Single workstation** | One GPU host, one user / small lab | Master and worker on the same machine; simplest install. |
| **Master + standalone worker(s)** | Several GPU servers, shared LAN, shared storage | Master node may or may not run jobs itself. Heavy GPU load on the master node can hang the web app/DB. |
| **Master + cluster** | Existing HPC scheduler (SLURM, PBS, UGE, LSF…) | `cryosparcm cluster connect`; CryoSPARC submits scripts, the cluster owns GPU/CPU allocation. |
| **Hybrid** | Mix of standalone workers and cluster lanes | cryoSPARC supports a heterogeneous mix in one instance. |

Hard requirements for any non-trivial setup (`docs/per_page/setup-configuration-and-management__hardware-and-system-requirements.md`):

1. **All nodes share a filesystem** at the same path so jobs can read/write intermediate results.
2. **Master has passwordless SSH** to each worker (for standalone workers); the bundled docs use `ssh-copy-id remote_user@remote_host`.
3. **Workers have TCP access** to ten consecutive ports on the master (default 61000–61009).

## Preflight checklist

Run through this before recommending or executing *any* install/connect step. Each row points at the source that owns the detail.

| # | Check | What to verify | Source |
|---|---|---|---|
| 1 | **License** | Non-profit academic? Use the cryosparc.com/download form to get a `LICENSE_ID`. Commercial use requires `sales@structura.bio`. | `docs/per_page/licensing.md`, `docs/per_page/setup-configuration-and-management__how-to-download-install-and-configure__obtaining-a-license-id.md` |
| 2 | **OS** | v5.0+: GLIBC 2.28+ (Rocky/RHEL 8, Ubuntu 20.04+; Ubuntu 22.04+ recommended). v4.x: older Linux is OK. | `docs/per_page/setup-configuration-and-management__software-system-guides__guide-updating-to-cryosparc-v5.md` |
| 3 | **NVIDIA driver** | v5.0+: **≥570.26**, Blackwell needs the open driver. v4.4–v4.7: ≥520.61.05. ≤v4.4: also needs a system CUDA toolkit (recommend 11.8). | `docs/per_page/setup-configuration-and-management__cryosparc-installation-prerequisites.md` |
| 4 | **GPU compute capability** | v5.0+ supports CC 5.0 (Maxwell) → 12.0 (Blackwell). v5 drops Kepler (CC 3.5). Bundled CUDA: 12.8 (v5.0+), 11.8.0 (v4.4–4.7). | Same as #3 |
| 5 | **UNIX user** | One non-root account, same numeric UID on master and all workers. **Never use root** to install/update/manage. | `docs/per_page/setup-configuration-and-management__cryosparc-installation-prerequisites.md` |
| 6 | **Hostnames** | Master must be reachable by a stable hostname; `hostname -f` should match `$CRYOSPARC_MASTER_HOSTNAME`. | `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0__cryosparcm-reference-v5.0.md` |
| 7 | **TCP ports** | Pick 10 consecutive free ports outside the kernel ephemeral range (`cat /proc/sys/net/ipv4/ip_local_port_range`) and outside any other cryoSPARC instance. Default base is 61000. | `docs/per_page/setup-configuration-and-management__cryosparc-installation-prerequisites.md` |
| 8 | **Passwordless SSH** | `ssh-copy-id <user>@<worker_host>` from master for every worker (standalone topology only). | Same |
| 9 | **Shared filesystem** | Project directory path identical from master *and* every worker shell, owned/writable by the cryoSPARC UNIX account. | `docs/per_page/setup-configuration-and-management__hardware-and-system-requirements.md` |
| 10 | **SSD cache** | Per-worker fast-local path with enough room for the biggest particle stacks the user expects to run; needed for almost all 2D/3D jobs. | `24_disk_and_storage.md`; `cryosparcw connect --ssdpath …` |
| 11 | **Cluster scheduler** | If integrating: SLURM/PBS/UGE/LSF binaries available on the master node; GPU GRES / cgroup configured to actually fence GPUs per job. | `docs/per_page/setup-configuration-and-management__how-to-download-install-and-configure__cryosparc-cluster-integration-script-examples.md` |
| 12 | **Install path** | Absolute path to `cryosparc_master/` after dereferencing symlinks must be **≤83 characters**. | `docs/per_page/setup-configuration-and-management__how-to-download-install-and-configure__downloading-and-installing-cryosparc.md` |
| 13 | **Disk headroom** | ≥15 GB to download/install. DB grows ~100 MB–5 GB per project; plan ≥500 GB for ~200 medium projects. | Same; `docs/per_page/setup-configuration-and-management__hardware-and-system-requirements.md` |
| 14 | **Shell environment** | Deactivate any active conda environment before install/update; cryoSPARC bundles its own Python and is known to be derailed by an inherited conda env. | `docs/per_page/setup-configuration-and-management__troubleshooting.md`, `docs/forum_threads/digests/forum_installation.md` |

Default ports (base 61000) and which workers need to reach which (`docs/per_page/setup-configuration-and-management__cryosparc-installation-prerequisites.md`):

| Port | Service | Worker access needed |
|---|---|---|
| 61000 | Web application | Browsers only |
| 61001 | MongoDB | **Workers** |
| 61002 | REST API | v4 and older: **workers**; v5: master-internal |
| 61003 | command_vis | Master-internal |
| 61004 | Redis cache / coordination | **Workers** |
| 61005 | Supervisor | Master-internal |
| 61006 | Web app API | Master-internal |
| 61007–61009 | Reserved | — |

## Download and install flow (master)

High-level only — exact steps live in `docs/per_page/setup-configuration-and-management__how-to-download-install-and-configure__downloading-and-installing-cryosparc.md`.

1. Log in as the dedicated non-root UNIX account on the master host.
2. `cd` into the chosen install parent directory (path ≤83 chars after symlink resolution).
3. Download both packages with the user's license ID. The current pattern (per the bundled doc) is:

   ```bash
   VERSION="latest"   # or e.g. "v4.7.1" for the last v4 line
   curl -L https://get.cryosparc.com/download/master-$VERSION/$LICENSE_ID -o cryosparc_master.tar.gz
   curl -L https://get.cryosparc.com/download/worker-$VERSION/$LICENSE_ID -o cryosparc_worker.tar.gz
   tar -xf cryosparc_master.tar.gz cryosparc_master
   tar -xf cryosparc_worker.tar.gz cryosparc_worker
   ```

   The `cryosparc2_worker/` artifact, if present after extract, is a legacy-compatibility stub and can be deleted.
4. Run `cryosparc_master/install.sh` with the documented flags — license, base port, DB path, hostname, and (for single workstation) the worker install flags. The exact flag set differs between v4.x and v5.x; always read the version-matched install page rather than reciting flags from memory.
5. Once `cryosparcm start` finishes, create the first administrator user via the install script's prompt (or `cryosparcm createuser` documented in the v5 reference).
6. Set up a recurring **database backup** (`cryosparcm backup …`) before letting any user touch the instance.
7. Verify the install end-to-end with `cryosparcm test install` and `cryosparcm test workers` — these are the canonical post-install smoke tests in v4.0+ and the green-tick list in `docs/per_page/setup-configuration-and-management__software-system-guides__guide-installation-testing-with-cryosparcm-test.md` is the success criterion.

## Worker connection flow

There are two distinct worker connection paths and they should not be conflated.

### Standalone worker (`cryosparcw connect`)
Run *on the worker*, as the cryoSPARC UNIX account, against an already-running master:

```bash
cd /path/to/cryosparc_worker
bin/cryosparcw connect \
    --worker $(hostname -f) \
    --master csmaster.local \
    --port 61000 \
    --ssdpath /scratch/cryosparc_cache \
    --lane $(hostname -s) \
    --newlane
```

(Source: `docs/per_page/setup-configuration-and-management__management-and-monitoring-4.7__cryosparcw-4.7.md`; v5 equivalent is documented in `cryosparcw-reference-v5.0.md`.)

Common flags to be aware of:

- `--worker` — the hostname the master should use to reach this worker (must resolve).
- `--master` / `--port` — must match the master's `$CRYOSPARC_MASTER_HOSTNAME` and base port.
- `--ssdpath`, `--ssdquota`, `--ssdreserve` — SSD cache config (`24_disk_and_storage.md`).
- `--lane` / `--newlane` — scheduler lane (`21_gpu_lane_queue.md`).
- `--gpus 0,1,2` / `--nogpu` — restrict which GPUs are visible to cryoSPARC.
- `--cpus` / `--rams` — cap CPU cores and 8 GiB RAM slots.
- `--update` — re-register an existing worker after CUDA/path/IP changes.

### Cluster worker (`cryosparcm cluster connect`)
Run *on the master* with a `cluster_info.json` and a `cluster_script.sh` Jinja template. The bundled SLURM example (`docs/per_page/setup-configuration-and-management__how-to-download-install-and-configure__cryosparc-cluster-integration-script-examples.md`) is a useful starting pattern but **must be adapted to the local cluster** — partition names, GPU GRES type, time limits, memory accounting, container/conda activations, license-server proxying, and `worker_bin_path` are all site-specific:

```json
{
    "name": "slurm-lane1",
    "worker_bin_path": "/path/to/cryosparc_worker/bin/cryosparcw",
    "send_cmd_tpl": "{{ command }}",
    "qsub_cmd_tpl": "/opt/slurm/bin/sbatch {{ script_path_abs }}",
    "qstat_cmd_tpl": "/opt/slurm/bin/squeue -j {{ cluster_job_id }}",
    "qdel_cmd_tpl": "/opt/slurm/bin/scancel {{ cluster_job_id }}",
    "qinfo_cmd_tpl": "/opt/slurm/bin/sinfo"
}
```

```bash
#!/usr/bin/env bash
#SBATCH --job-name cryosparc_{{ project_uid }}_{{ job_uid }}
#SBATCH --cpus-per-task={{ num_cpu }}
#SBATCH --gres=gpu:{{ num_gpu }}
#SBATCH --mem={{ ram_gb|int }}G
#SBATCH --output={{ job_dir_abs }}/{{ project_uid }}_{{ job_uid }}_slurm.out
#SBATCH --error={{ job_dir_abs }}/{{ project_uid }}_{{ job_uid }}_slurm.err
{{ run_cmd }}
```

PBS and UGE templates are in the same docs page. Critical caveats:

- **CryoSPARC numbers GPUs from 0** inside the job. The scheduler **must** set `CUDA_VISIBLE_DEVICES` (e.g. SLURM cgroups + GRES) so a 2-GPU job really gets 2 fenced GPUs rather than racing with other tenants.
- `num_cpu` / `num_gpu` / `ram_gb` are CryoSPARC-supplied; you can wrap them with custom variables (`ram_multiplier`, partition selectors, etc.) per `docs/per_page/setup-configuration-and-management__software-system-guides__guide-configuring-custom-variables-for-cluster-job-submission-scripts.md`.
- Clusters **do not auto-update workers** — see the Updates section below.

## Access, reverse proxy, and security

After startup `cryosparcm start` prints the access URLs (see `docs/per_page/setup-configuration-and-management__how-to-download-install-and-configure__accessing-cryosparc.md`):

```
From this machine:            http://localhost:61000
From the same network:        http://csserver.lab:61000
```

The defining security warning from `docs/per_page/setup-configuration-and-management__hardware-and-system-requirements.md` is worth repeating verbatim:

> CryoSPARC is designed to be run only within a trusted private network. CryoSPARC instances are not security-hardened against malicious actors on the network and should never be hosted directly on the internet or an untrusted network without a separate controlled authentication layer.

Practical access patterns to recommend, in increasing order of operational weight:

1. **Same LAN** — open `http://csmaster.lab:61000` directly. Default for a single lab.
2. **VPN** — log in to the institutional VPN, then access as if on LAN.
3. **SSH local port forwarding** — `ssh -L 62222:localhost:61000 user@csserver.lab`, then `http://localhost:62222` on the workstation. Good fallback when no VPN.
4. **Reverse proxy** — optional. nginx or Apache fronted by HTTPS + institutional SSO. The docs page `…__optional-hosting-cryosparc-through-a-reverse-proxy.md` gives nginx and Apache configs *as starting points*; HTTPS, valid CA cert, and an upstream auth layer are non-negotiable. Never expose the bare master ports to the public internet.

Site-local policy worth recording for any advisor session (so you can re-route on the next question without re-asking):

- Whether the user is on LAN, VPN, SSH tunnel, or reverse proxy.
- The master hostname and base port (`cryosparcm status` reveals both).
- Whether reverse proxy is in place and which auth layer fronts it.
- Whether `CRYOSPARC_FORCE_HOSTNAME` / `CRYOSPARC_INSECURE` have been touched (these mute safety checks and should not be flipped lightly).

## CLI / admin surfaces — what they own, where to go for details

The bundled docs split `cryosparcm` (master) and `cryosparcw` (worker) cleanly. This page summarises **what each surface owns**; for exact flags use `cryosparcm COMMAND --help` on the live host and the version-matched references in `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0/` or `…__management-and-monitoring-4.7/` and `14_cli_admin.md`.

| Command family | What it owns | Always run as | Notes |
|---|---|---|---|
| `cryosparcm status` | Process roster + license check + key env vars | Install owner on master host | First command to run for any "instance broken?" question. |
| `cryosparcm start` / `stop` / `restart` | Lifecycle of all master services | Install owner on master host | Stop = all subprocesses; verify with `ps`/`pgrep` per `…__troubleshooting.md` (incomplete shutdown is a known cause of failed updates). |
| `cryosparcm log <service>` | Tail of master logs: `database`, `command_core`, `command_vis`, `command_rtp`, `supervisord`, `webapp` | Install owner | First place to look on startup or login failures. |
| `cryosparcm test install` / `test workers` / `test pytorch` / `test tensorflow` | Post-install / post-update verification | Install owner | The 14-step checklist in `…__guide-installation-testing-with-cryosparcm-test.md` is the success criterion. |
| `cryosparcm update [--check / --list / --download / --install]` | Master + auto worker update | Install owner | Cluster workers are **not** auto-updated. See Updates section. |
| `cryosparcm patch` | Apply latest patch for installed version | Install owner | Same workflow as update; for clusters use `--download` + `--install`. |
| `cryosparcm maintenancemode on / off / status` | Pause new job dispatch while letting running jobs finish | Install owner | Use before updates / scheduled maintenance. |
| `cryosparcm backup` / `cryosparcm restore` | DB backup/restore | Install owner | **Always** before update or risky admin op. |
| `cryosparcm recover` (v5.0+) | Rebuild DB from project dirs + recent `cryosparc_instance_config_*.tar` | Install owner | See `…__guide-instance-recovery-v5.0.md` and the recovery runbook below. |
| `cryosparcm snaplogs` | Bundle logs into a tgz for forum/support | Install owner | Preferred way to share diagnostic state. |
| `cryosparcm cli "api.…(…)"` (v5.0+) / `cryosparcm cli "<fn>(…)"` (v4) | Inline programmatic operations | Install owner | **Syntax differs between v4 and v5** — v5 uses `api.<namespace>.<fn>`; v4 uses bare functions. See `…__management-and-monitoring-v5.0__cryosparcm-cli-reference-v5.0.md` and `13_cryosparc_tools_api.md`. |
| `cryosparcm icli` / `cryosparcm mongo` | Interactive Python / Mongo shells | Install owner | Mongo direct access is for emergencies / advanced edits only. |
| `cryosparcw info --gpu` / `gpulist` | GPU detection on the worker | Worker UNIX user | First check when "GPU not visible". |
| `cryosparcw connect [--update]` | Register/refresh a standalone worker | Worker UNIX user | Re-run with `--update` after CUDA path / SSD path / GPU layout changes. |
| `cryosparcw env` | Print worker env (CUDA paths, PATH) | Worker UNIX user | Useful diagnostic before debugging CUDA `ImportError`s. |
| `cryosparcw newcuda <path>` (≤v4.3 only) | Point worker at a system CUDA toolkit | Worker UNIX user | v4.4+ bundles CUDA; this command no longer exists. |
| `cryosparcw patch` / `cryosparcw update` | Apply patch / update tarball that was prepared on master | Worker UNIX user | Used in cluster updates. |

Key environment variables to know (v5.0 file is `…__management-and-monitoring-v5.0__environment-variables-v5.0.md`; v4.7 file is `…__management-and-monitoring-4.7__environment-variables-v4.7.md`):

- `cryosparc_master/config.sh` (restart required after changes):
  - `CRYOSPARC_LICENSE_ID`, `CRYOSPARC_MASTER_HOSTNAME`, `CRYOSPARC_DB_PATH`, `CRYOSPARC_BASE_PORT` — set at install.
  - `CRYOSPARC_HEARTBEAT_SECONDS` (default 180) — raise on busy/slow workers to reduce spurious "did not receive heartbeat" failures.
  - `CRYOSPARC_FORCE_HOSTNAME` / `CRYOSPARC_FORCE_USER` — relax the host/user safety check; default `false`, leave alone unless you understand the trade-off.
  - `CRYOSPARC_INSECURE` — allows HTTP-only license checks; only set in environments behind an SSL-injecting corporate proxy.
  - `CRYOSPARC_DB_MIN_SPACE_GB` (default 5) — minimum free space MongoDB requires.
  - `CRYOSPARC_LICENSE_SERVER_ADDR` / `REQUESTS_CA_BUNDLE` — for restricted networks that route through a proxy.
  - `CRYOSPARC_AUTO_EXPORT_INSTANCE_CONFIG_DIR` (v5.0+) — where the 60-minute instance-config exports go (needed for recovery).
- `cryosparc_worker/config.sh` (no restart required):
  - `CRYOSPARC_CACHE_NUM_THREADS` (v4.3+) — particle cache copy concurrency; default 2.

## Updates and migrations

Three distinct things live under "update": patches (small, in-version), updates (minor/major within the same line), and migrations (v4 → v5).

### Patches and minor updates
Per `docs/per_page/setup-configuration-and-management__software-updates.md` and the v5/v4 `cryosparcm` references:

1. Announce the update to users (Message of the Day, `cryosparcm cli "set_instance_banner(…)"`; see `…__guide-maintenance-mode-and-configurable-user-facing-messages.md`).
2. Turn on maintenance mode: `cryosparcm maintenancemode on`. Pause running CryoSPARC Live sessions manually (maintenance mode doesn't pause them).
3. Wait for active jobs to complete (or `kill` them via the Resource Manager if explicitly approved).
4. **Backup the database** (`cryosparcm backup …`).
5. *Completely* shut down: `cryosparcm stop`, then verify no orphan processes are left (incomplete shutdown is the canonical cause of failed updates).
6. Confirm headroom: ≈6 GB free in `cryosparc_master/` and ≈5 GB in `cryosparc_worker/` (v4.7+). If install and DB share a volume, also keep DB headroom intact.
7. `cryosparcm update` (or `cryosparcm patch`). For clusters add `--download` then `cryosparcw update` / `cryosparcw patch` on the worker side because clusters do not auto-propagate.
8. `cryosparcm start`.
9. `cryosparcm test install` and `cryosparcm test workers` — go/no-go.
10. Maintenance mode off; clear the banner.

### v4 → v5 migration
Source: `docs/per_page/setup-configuration-and-management__software-system-guides__guide-updating-to-cryosparc-v5.md`.

- Must already be on v4.0+. v3 must go through v4 first.
- OS must support GLIBC 2.28+ (Rocky/RHEL 8, Ubuntu 20.04+, recommend 22.04+).
- NVIDIA driver ≥570.26; CC ≥5.0 (Kepler dropped); Blackwell needs the open driver.
- v5 introduces a **database upgrade step** that validates every document. For large instances expect up to ~1 hour during which the UI is unavailable. The upgrade runs in two phases:
  1. Dry-run validation, with the option to detach invalid projects.
  2. Upgrade write phase, with results written to `cryosparc_master/run/upgrade_results_*.json`.
- v5 → v4 downgrade is possible **only to v4.4+** (and to ≤v4.3 only by stopping at v4.7 first).
- `cryosparcm cli` syntax changes from v4's bare functions to v5's `api.<namespace>.<fn>(…)`. Any in-house scripts using v4 CLI calls must be updated; `cryosparc-tools` ≥ the new version is backwards-compatible.

### v3 → v4 migration
Per `…__guide-updating-to-cryosparc-v4.md`: a standard `cryosparcm update` from v3.4+ is sufficient, but **once on v4 the MongoDB version makes downgrading below v3.4.0 impossible**. Back up first.

**Do not update blindly mid-project.** Treat any active 3D refinement, Live session, or long-running 3DFlex job as a blocker. Use maintenance mode rather than killing jobs unless the user explicitly authorises it.

## Common failure modes and red flags

The forum digests and `17_error_lookup.md` consistently surface the same families. Triage in this order:

| Symptom / error | Likely cause | First check / fix |
|---|---|---|
| `Couldn't connect to host` / `Could not resolve host` / `tar: This does not look like a tar archive` during install | License server unreachable, wrong `LICENSE_ID`, conda env active | `echo $LICENSE_ID`; `curl https://get.cryosparc.com/checklicenseexists/$LICENSE_ID`; deactivate conda; check firewall whitelist for `get.cryosparc.com`. (`docs/per_page/setup-configuration-and-management__troubleshooting.md`) |
| `Version mismatch! Worker and master versions are not the same` | Patch or update applied to master but not to a (cluster) worker | Re-run worker update with `cryosparcw update` / `cryosparcw patch -f …`. |
| `nvcc fatal : Value 'sm_75' is not defined` | System CUDA older than the installed GPU | Install a CUDA toolkit that supports the GPU and `cryosparcw newcuda /path/to/cuda` (≤v4.3 only); for v4.4+ update CryoSPARC instead. |
| `ImportError: libcurand.so.10` / `libcusolver.so.10` / `libcufft.so.10` | Worker's CUDA path changed since `cryosparcw connect` | `cryosparcw env`; re-`connect` or `newcuda` to match. (`17_error_lookup.md`) |
| Worker registered but jobs sit in queue forever | Lane CPU-per-GPU too low, or no lane assignment, or master cannot reach worker hostname | `21_gpu_lane_queue.md`; check `cryosparcw connect --update --worker $(hostname -f)`. |
| GUI says `User not found` on login | Email typo or stray whitespace in the user record | `cryosparcm listusers`; fix via `cryosparcm mongo` per the troubleshooting page. |
| `cryosparcm status` shows DB stopped or supervisord errors | DB volume out of space, host renamed since install, port collision | Check disk free vs `CRYOSPARC_DB_MIN_SPACE_GB`; check `$CRYOSPARC_MASTER_HOSTNAME` vs `hostname -f`; check ports vs ephemeral range. |
| `did not receive heartbeat` job failures | Slow worker FS or single long step exceeding 180 s | Raise `CRYOSPARC_HEARTBEAT_SECONDS`, restart master. |
| Path resolves on master but not from the worker shell | Different mount layout, NFS automounter, symlink in master path that doesn't exist on worker | Open a shell as the cryoSPARC UNIX account on each side and stat the path; do not patch by adding new symlinks under `cryosparc_master/`. |
| `OSError: [Errno 40] Too many levels of symbolic links` | Self-referencing or broken raw-data symlink (frequent with EPU export setups) | Fix the symlink in raw data; do not work around inside cryoSPARC. (`docs/forum_threads/digests/forum_cryosparc-live.md`) |
| 500 GB-class `collection-*.wt` file in DB volume | MongoDB has not released deleted space | DB compaction routine in `…/docs/forum_threads/digests/forum_data-management.md`; **always back up first**; `24_disk_and_storage.md`. |
| Multi-GPU job sees fewer GPUs than expected | Hyperthreading off; or scheduler not exposing all GPUs to the job | Confirm `nvidia-smi` from inside the job; turn HT on (forum-confirmed fix); on clusters confirm GRES and `CUDA_VISIBLE_DEVICES`. |
| Reverse proxy returns 502 / loses websocket | Missing `Upgrade: websocket` headers, request buffering on, max body size too small | Compare against the nginx/Apache examples in `…__optional-hosting-cryosparc-through-a-reverse-proxy.md`. |
| Install/update breakage after `pip install`-ing third-party packages into the cryoSPARC env | Bundled Python now inconsistent | **Do not install third-party packages into the cryoSPARC env.** Use `cryosparc-tools` from a *separate* environment instead (`13_cryosparc_tools_api.md`). |

**Red flags that should stop any admin action until the user explicitly approves the next step:**

- DB is full or the DB volume is shared with the install tree and approaching capacity.
- The user has a running 3D refinement, 3DFlex, or Live session that the proposed action would interrupt.
- The user cannot produce a recent DB backup, *and* the proposed action (update, recover, mongo edit, restart during a long job) could lose state.
- Project directories are on storage you do not understand (e.g. snapshotted ZFS, GPFS with non-standard locking, an NFS export that may be remounted).
- The hostname returned by `hostname -f` no longer matches `$CRYOSPARC_MASTER_HOSTNAME`.
- Symbols you do not recognise have been added under `cryosparc_master/` (custom patches, manually edited `config.sh`, externally injected service files).

## Advisor defaults and first questions

When an install/admin question lands, lead with these:

1. "What does `cryosparcm status` show?" — establishes version, hostname, DB path, base port, lane health.
2. "Is this a single workstation, master + standalone worker(s), or a cluster?" — choses which install path is relevant.
3. "Which UNIX account owns the installation? Are you logged in as that account right now?" — most admin commands silently refuse otherwise.
4. "Do you have a recent DB backup? When?" — gate for any update/recovery/destructive op.
5. "Is anything actively running (jobs, Live sessions)?" — gate for restarts and updates.
6. "What does the live `cryosparcm test install` say?" — fastest end-to-end check.

Default advisor recommendations when no strong reason exists to deviate:

| Question | Default | Why |
|---|---|---|
| New install, single lab, 1–4 GPUs | Single workstation, v4.7.1 if stability matters, v5.0+ if compatible with OS/driver/GPUs | v5 is still labelled BETA in the bundled docs; single-workstation simplifies almost everything. |
| New install, shared GPU server + small group | Master on a separate lightweight host, worker on the GPU host | Avoids GPU OOM hanging the web app/DB. |
| New install on an HPC | Master on a small login-adjacent VM, cluster lane via `cryosparcm cluster connect` | Lets the scheduler own GPU/CPU; CryoSPARC just submits scripts. |
| Should I install CUDA system-wide? | v4.4+: no — bundled. ≤v4.3: yes, 11.8 + matching driver. v5.0+: no — bundled 12.8. | `…__cryosparc-installation-prerequisites.md`. |
| Should I install third-party Python packages into the cryoSPARC env? | No. Use cryosparc-tools from a separate venv/conda env. | Breakage from incompatible deps is one of the top reproducible install failures (`docs/forum_threads/digests/forum_installation.md`). |
| Should I expose the GUI to the public internet? | No. LAN, VPN, SSH tunnel, or HTTPS reverse proxy behind SSO only. | The hardware-requirements page is explicit about this. |

## Runbooks

### R1. New single-workstation install
1. Preflight checklist (license, OS, driver/GPU, user, hostname, ports, shell env, install path length, disk).
2. `cryosparcm test install` will be run at the end — don't skip it.
3. Download and extract `cryosparc_master` + `cryosparc_worker` as the cryoSPARC UNIX account; install via the single-workstation script with `--license`, `--hostname`, `--port`, `--dbpath`, and worker flags (`--worker_path`, `--ssdpath`, `--cudapath` for ≤v4.3 only). Use the bundled doc for exact flags for the installed version.
4. `cryosparcm start` (or it will be started automatically by the installer).
5. Create the first admin user when prompted (or via `cryosparcm createuser`).
6. Configure a recurring DB backup (cron + `cryosparcm backup`).
7. `cryosparcm test install` and `cryosparcm test workers` → all checks green.
8. Log access URL and credentials. Confirm with the user how they want to reach the GUI (LAN / VPN / SSH tunnel).

### R2. Add a standalone worker to an existing master
1. Verify master version with `cryosparcm status`; the worker package must match.
2. On the master: `ssh-copy-id <user>@<worker_host>` for passwordless SSH. Confirm the same UNIX UID exists on the worker.
3. Confirm the shared filesystem mounts at the same path on the worker.
4. On the worker: download/extract the matching `cryosparc_worker` package; run `bin/cryosparcw connect --worker $(hostname -f) --master <master_host> --port <base> --ssdpath /scratch/cryosparc_cache --lane <lane> [--newlane]`.
5. `cryosparcw gpulist` to confirm GPU detection.
6. From the master: `cryosparcm test workers --target <worker_host>` to validate end-to-end.

### R3. Cluster integration
1. Build a `cluster_info.json` and `cluster_script.sh` adapted from the SLURM/PBS/UGE templates in `…__cryosparc-cluster-integration-script-examples.md`.
2. Verify the template renders the run command correctly with `num_cpu`, `num_gpu`, `ram_gb`, `job_dir_abs`, `project_dir_abs`, `worker_bin_path`, `run_cmd`.
3. Confirm GPU fencing: SLURM GRES + cgroups, PBS GPU selector, or equivalent; otherwise concurrent jobs will race on the same GPU.
4. `cryosparcm cluster connect` from the master directory containing the JSON + script.
5. Submit a tiny test job (e.g. a small T20S import + Patch CTF) and watch `squeue`/`qstat` and `cryosparcm log command_core` together.
6. Confirm cache path is on a node-local fast disk reachable by every job-receiving node.
7. Tell the user: cluster workers do **not** auto-update; updates require the manual `--download`/`--install` pattern.

### R4. Update an instance
See "Updates and migrations" above. Treat the 10-step sequence as the runbook.

### R5. Recovery of a failed instance (v5.0+)
Per `…__guide-instance-recovery-v5.0.md`:
1. Stop CryoSPARC; verify no orphan processes (see `…__troubleshooting.md` incomplete-shutdown section).
2. Locate the latest `cryosparc_master/run/cryosparc_instance_config_*.tar` (auto-exported every 60 minutes by default).
3. **Copy** that file *outside* the `cryosparc_master/` tree so it survives later changes (e.g. `/home/cryosparcuser/latest_cryosparc_instance_config.tar`).
4. `mkdir /path/to/recovered_cryosparc_database`.
5. Edit `cryosparc_master/config.sh` so `CRYOSPARC_DB_PATH` points at the new directory.
6. `cryosparcm start` → empty UI, that's expected.
7. `cryosparcm recover -f /home/cryosparcuser/latest_cryosparc_instance_config.tar`.
8. Project directories must already be mounted at their original absolute paths, otherwise re-attach will fail and `cs.lock` will be left behind (do not bulk-delete `cs.lock` without confirming the attach attempt is finished).
9. After completion: re-run `cryosparcm test install`, then verify a few projects open as expected.

If a recent instance config export is not available, the fall-back is a fresh install + re-attach all projects manually; no `recover` shortcut exists in that case.

### R6. Permissions / storage problem
1. Confirm everyone in the user's group can read CryoSPARC project files (`ls -l` on the project dir; check group ownership).
2. For a shared instance, follow the `g+ws` + `umask 0002` pattern from `…__unix-permissions-and-data-access-control.md` — chown to the cryoSPARC group, set `chmod g+ws`, add researchers to that group.
3. For multi-team isolation, set up per-team Linux groups and per-team project subtrees; the cryoSPARC owner still has full access (this is required for cryoSPARC to function and cannot be removed).
4. For DB bloat / huge `collection-*.wt`: back up first, then use the Mongo compaction routine documented in `docs/forum_threads/digests/forum_data-management.md`. Do **not** touch Mongo files while cryoSPARC is running. Cross-link `24_disk_and_storage.md`.
5. For SSD cache running out: confirm `--ssdpath` is on a real local SSD, review `CRYOSPARC_CACHE_NUM_THREADS`, and consider raising the per-worker SSD quota.

## Safety boundaries

- **Never run destructive cleanup unprompted.** `rm` against a project tree, `db.dropDatabase()`, deleting `cryosparc_db_*`, or wiping `cryosparc_master/run/` is the canonical way to destroy weeks of work.
- **Stop / start / restart / update only with explicit user approval on a live instance.** A user with running jobs may not know what they will lose.
- **Preserve backups and logs before any risky operation.** `cryosparcm backup` first, then `cryosparcm snaplogs` for diagnostics. Keep both somewhere outside `cryosparc_master/`.
- **Do not amend config.sh casually.** Especially `CRYOSPARC_MASTER_HOSTNAME`, `CRYOSPARC_DB_PATH`, `CRYOSPARC_BASE_PORT`, `CRYOSPARC_FORCE_HOSTNAME`, `CRYOSPARC_FORCE_USER`, `CRYOSPARC_INSECURE`. Each of these has knock-on effects (worker reconnections, license server reachability, multi-instance port collisions).
- **Do not bypass version-matched docs.** `cryosparcm cli` syntax, environment variables, and worker connect flags differ between ≤v4.7 and v5.0+. Always start from `cryosparcm status` and the matching `docs/per_page/setup-configuration-and-management__management-and-monitoring-*` page.
- **Do not install third-party Python packages into the cryoSPARC env.** Use `cryosparc-tools` from a separate environment for scripting (`13_cryosparc_tools_api.md`).
- **Confirm before exposing the GUI more widely.** Reverse proxy / VPN / SSH tunnel configurations have security implications that depend on institutional policy; record what the user already has rather than re-deploying it.

## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

- `docs/per_page/readme.md`
- `docs/per_page/licensing.md`
- `docs/per_page/resources__questions-and-support.md`
- `docs/per_page/setup-configuration-and-management__cryosparc-installation-prerequisites.md`
- `docs/per_page/setup-configuration-and-management__hardware-and-system-requirements.md`
- `docs/per_page/setup-configuration-and-management__how-to-download-install-and-configure.md`
- `docs/per_page/setup-configuration-and-management__how-to-download-install-and-configure__downloading-and-installing-cryosparc.md`
- `docs/per_page/setup-configuration-and-management__how-to-download-install-and-configure__obtaining-a-license-id.md`
- `docs/per_page/setup-configuration-and-management__how-to-download-install-and-configure__accessing-cryosparc.md`
- `docs/per_page/setup-configuration-and-management__how-to-download-install-and-configure__cryosparc-cluster-integration-script-examples.md`
- `docs/per_page/setup-configuration-and-management__how-to-download-install-and-configure__optional-hosting-cryosparc-through-a-reverse-proxy.md`
- `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0.md`
- `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0__cryosparcm-reference-v5.0.md`
- `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0__cryosparcm-cli-reference-v5.0.md`
- `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0__cryosparcw-reference-v5.0.md`
- `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0__environment-variables-v5.0.md`
- `docs/per_page/setup-configuration-and-management__management-and-monitoring-4.7__cryosparcm-4.7.md`
- `docs/per_page/setup-configuration-and-management__management-and-monitoring-4.7__cryosparcw-4.7.md`
- `docs/per_page/setup-configuration-and-management__management-and-monitoring-4.7__environment-variables-v4.7.md`
- `docs/per_page/setup-configuration-and-management__software-updates.md`
- `docs/per_page/setup-configuration-and-management__troubleshooting.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__guide-installation-testing-with-cryosparcm-test.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__guide-updating-to-cryosparc-v5.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__guide-updating-to-cryosparc-v4.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__guide-instance-recovery-v5.0.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__unix-permissions-and-data-access-control.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__guide-lane-assignments-and-restrictions.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__guide-maintenance-mode-and-configurable-user-facing-messages.md`
- `docs/per_page/setup-configuration-and-management__software-system-guides__guide-configuring-custom-variables-for-cluster-job-submission-scripts.md`
- `docs/per_page/application-guide__admin-panel.md`
- `docs/per_page/application-guide__instance-management.md`
- `docs/per_page/processing-data__cryosparc-tools.md`
- `docs/forum_threads/digests/forum_installation.md`
- `docs/forum_threads/digests/forum_hardware-and-performance.md`
- `docs/forum_threads/digests/forum_troubleshooting.md`
- `docs/forum_threads/digests/forum_data-management.md`
- `docs/forum_threads/digests/forum_cryosparc-live.md`
- `docs/forum_threads/digests/forum_scripting.md`
- `17_error_lookup.md`
- `reference/release_notes/markdown/v4.0.md`
- `reference/release_notes/markdown/v4.1.md`
- `reference/release_notes/markdown/v4.2.md`
- `reference/release_notes/markdown/v4.3.md`
- `reference/release_notes/markdown/v4.4.md`
- `reference/release_notes/markdown/v4.5.md`
- `reference/release_notes/markdown/v4.6.md`
- `reference/release_notes/markdown/v5.0.md`
- `00_overview.md`
- `13_cryosparc_tools_api.md`
- `14_cli_admin.md`
- `15_troubleshooting.md`
- `21_gpu_lane_queue.md`
- `24_disk_and_storage.md`
- `23_external_jobs.md`
- `18_decision_trees.md`
