# Reference 17 — cryoSPARC Error & Symptom Lookup

## Scope

Retrieval-first index of error strings, log lines, and symptom patterns observed in cryoSPARC, with the fastest checks and fixes. Not a tutorial. When an error string is generic ("NoneType", "IndexError"), the entry calls out the symptom pattern and tells you what else to confirm before acting.

## First-pass triage

Before opening an entry below, capture these three things — most of the false leads in the corpus come from skipping them:

1. **Which log first?**
   - Job runtime errors → `Event Log` tab in GUI, then `job.log` in the job directory.
   - Worker launch / "FAILED TO LAUNCH" / SSH issues → `cryosparcm log command_core`.
   - DB/supervisor/socket issues → `cryosparcm status`, `cryosparcm log database`, `cryosparcm log supervisord`.
   - cryosparc-tools / scripting failures → `cryosparcm log command_vis` and the Python traceback.
   - Live UI / RTP / streamlog issues → `cryosparcm log command_vis`, streamlog tab, browser console.
2. **Version of master, worker, and (if relevant) cryosparc-tools.** Many entries below are version-fixed; if you're more than two minor versions behind, update before deep debugging.
3. **Whether the same path/file is visible from the worker shell as the cryoSPARC owner user.** A surprising number of "file not found", "invalid path", and "cannot launch" reports are namespace/permission mismatches, not bugs.

If the symptom is "job stuck" with no obvious traceback: check the scheduler log on the cluster (SLURM/PBS) for OOM-kill *before* anything else — the master often only sees a heartbeat loss.

---

## 1. Launch / worker / SSH / shell / lanes

### `non-zero exit status 255` on worker launch
**Likely cause:** SSH from master to worker failed (auth, host key, banner output, MOTD, login shell errors).
**Checks:** Run the exact `ssh worker "true"` non-interactively as the cryoSPARC owner; inspect `cryosparcm log command_core`; confirm no `echo`/banner output in `.bashrc`/`.profile`.
**Fix:** Make login shell silent; ensure passwordless SSH master→worker; re-run worker test (`cryosparcw connect ...`).
**Version note:** v4.0 fixed a class of SSH/command failures caused by system library mismatch; v5.0 fixed worker launch on `tcsh` and extra shell-startup output causing failed jobs.

### `non-zero exit status 1`, `FAILED TO LAUNCH ON WORKER NODE return code 1`
**Likely cause:** SSH succeeded but the worker-side command itself failed (env, missing CUDA libs, wrong cryosparcw path).
**Checks:** `cryosparcm log command_core` for the actual command line; reproduce that command interactively as the cryoSPARC owner on the worker.
**Fix:** Repair worker env (CUDA path, conda activation, `cryosparcw newcuda` if CUDA moved); re-run `cryosparcw connect`.

### Observed exact worker-launch strings to match literally
If the log preserves a full SSH wrapper, classify it as launch/SSH before debugging the cryo-EM job itself. Examples from the corpus:

- `Command ‘[‘ssh’, u’emguest@cryogpu2’, ‘nohup’, u’/home/emguest/software/cryosparc2_worker/bin/cryosparcw run --project P1 --job J6 --master_hostname cryogpu2 --master_command_core_port 39002 > /net/cryogpu/data/cryosparc_output_data/J6/job.log 2>&1 & ‘]’ returned non-zero exit status 255`
- `Command ‘[‘ssh’, u’emguest@cryogpu2’, ‘nohup’, u’/home/emguest/software/cryosparc2_worker/bin/cryosparcw run --project P1 --job J10 --master_hostname cryogpu2 --master_command_core_port 39002 > /net/cryogpu/data/cryosparc_output_data/J10/job.log 2>&1 & ‘]’ returned non-zero exit status 1’`
- Same family with `CalledProcessError`, worker `cryogpu2`, user `emguest`, command-core port `39002`, project/job IDs such as `P1-J6`, `P1-J10`, `P2-J4`, `P2-J5`.

**Fastest checks:** `cryosparcm log command_core`; run the printed `ssh ... cryosparcw run ...` command manually as `emguest`; check shell (`bash` vs `tcsh`) and whether startup files print text.
**Fix:** repair SSH/shell/env first, then re-run or reconnect the worker. Do not tune reconstruction parameters until launch succeeds.

### `failed to connect link` (worker launch)
**Likely cause:** Worker process started but cannot reach `command_core`/`command_vis` (firewall, DNS, wrong master hostname, port collision).
**Checks:** From worker, `curl http://<master>:<command_core_port>/` and `nc -vz <master> <port>`; confirm `cryosparc_master/config.sh` ports.
**Fix:** Open ports / fix hostname resolution; re-register worker.

### `Job must be queued on the master node`
**Likely cause:** An interactive job/UI action (Select 2D, Curate Exposures, Volume Tools interactive, etc.) was queued to a non-master lane.
**Fix:** Queue interactive jobs on the master/default lane; this is required, not a bug.

### `database: ERROR (spawn error)` / `pymongo.errors.ServerSelectionTimeoutError ... Connection refused`
**Likely cause:** MongoDB did not start, or `cryosparcm` clients cannot reach it.
**Checks:** `cryosparcm status`, `cryosparcm log database`; look for lockfile, port collision, stale `mongod` process; disk full on DB volume.
**Fix:** Stop residual processes, free port, ensure data dir writable, restart; do **not** delete DB files without backup.

### `WiredTiger error`, `WT_PANIC`, `read checksum error`, `illegal file format`
**Likely cause:** MongoDB on-disk corruption (often disk fault, abrupt power loss, or filesystem issue).
**Symptom pattern:** Treat as data emergency — updating cryoSPARC will **not** fix this.
**Fix:** Stop all cryoSPARC processes, back up `cryosparc_database/` byte-for-byte, attempt `mongod --repair` on the backup, restore from snapshot if available. Contact admin before further writes.

### `socket.error: [Errno 98] Address already in use`
**Likely cause:** A previous `cryosparc_*` or `mongod` process is still bound to the port, or another service uses it.
**Checks:** `ps -ef | grep -E 'cryosparc|mongod'`, `lsof -i :<port>` / `ss -lntp`.
**Fix:** Stop the lingering process owned by the cryoSPARC user; only remove stale sockets after confirming no live PID.

### `unix:///tmp/cryosparc-supervisor-*.sock refused connection`
**Likely cause:** Stale supervisor socket from a dead instance, or supervisor crashed.
**Checks:** `ps -ef | grep supervisord`; `cryosparcm status`.
**Fix:** If no live supervisor PID, remove the stale socket and `cryosparcm start`; otherwise restart the actual supervisor — do not delete sockets owned by a running process.

### `Could not parse signed file`
**Likely cause:** Startup after a license ID change in older builds.
**Fix:** Update to v5.0+ (fixed there). As a workaround on older versions, reinstate the prior license ID.

### `ERROR: This command can only be called by the owner of this script`
**Likely cause:** `cryosparcm` invoked by a UNIX user that is not the cryoSPARC owner.
**Fix:** `sudo -u <cryosparc_owner> cryosparcm ...`; only set `CRYOSPARC_FORCE_USER=true` if your site policy explicitly allows multi-user invocation.

---

## 2. Filesystem / import / path / permissions / SSD cache

### `invalid path`, `file not found`, `OSError: [Errno 2] No such file or directory`
**Symptom pattern:** Master sees the path, worker does not — or the file was moved/symlinked.
**Checks:** As the cryoSPARC owner on the *worker*, `ls -l <path>`; confirm same mount/namespace as master; resolve symlinks (`readlink -f`).
**Fix:** Mount the path on the worker, fix symlinks, re-import with corrected path. For misleading permission/access reports, v5.0+ supports `CRYOSPARC_CLI_SKIP_ACCESS_CHECK=true` to bypass the pre-flight check that itself fails on some NFS setups.

### `Unable to delete P12: ServerError: validation error: lock file for P12 not found` / `cs.lock absent or otherwise inaccessible`
**Likely cause:** Project's `cs.lock` missing, owned by root or by a different cryoSPARC instance, or the project directory was moved/deleted out of band. Project locks were introduced in v4.
**Fix:** Run as the cryoSPARC owner; if the project folder exists, restore the lock file (`cs.lock`) with correct ownership; if the project was intentionally moved between instances, detach/attach properly rather than force-deleting.

### `Unable to delete Px: [Errno 2] No such file or directory: ... S1`
**Likely cause:** A Live session folder (`S<n>`) was manually deleted or renamed on disk; GUI delete then fails to clean up.
**Fix:** Recreate the missing session directory as an empty folder (matching name/owner) so the delete can complete, or restore the folder from backup before issuing the delete.

### `*** CommandClient ... get_project_file HTTP Error 422 UNPROCESSABLE ENTITY`, `Invalid file path` (from cryosparc-tools)
**Likely cause:** Project directory was a symlink — older versions rejected paths that resolved outside the registered root.
**Fix:** Update CryoSPARC and cryosparc-tools to ≥ v4.3 (fixed); as a workaround, register the resolved (non-symlink) project path.

### `Too many levels of symbolic links` / `OSError: [Errno 40]`
**Likely cause:** Symlink loop somewhere in the watched/imported path (often a self-referencing `raw/` link in Live).
**Fix:** `readlink -f` and `find -L <path> -maxdepth 4` to locate the loop; replace with a real path or non-looping symlink.

### `cache waiting for requested files to become unlocked`
**Likely cause:** Multiple jobs are caching overlapping files; one job holds the lock while another waits. May also be a stale lock left by a killed job.
**Checks:** Inspect SSD cache directory for `.lock` files; check which job currently caches the same particles.
**Fix:** Let the filling job finish — do not kill it. If clearly stale (no live job owns it), remove the lock and re-queue. Update to v4.4+/v4.5+ for cache robustness; v4.6 improved cluster-filesystem cache diagnostics.

### SSD cache: `cache does not have enough space for download` / hangs waiting for space
**Likely cause:** Reserve set too high vs. partition size; other jobs pinning files; non-cryoSPARC data filling the SSD.
**Checks:** `df -h` on SSD partition; size of `cryosparc_*/cache` and reserve in `config.sh`.
**Fix:** Lower reserve, evict old cache, reduce concurrent caching jobs, or disable SSD caching per-job to confirm the cache is the cause.
**Version note:** v4.2 fixed an SSD free-space calculation infinite hang and added network-timeout retries; v5.0 added a fallback for silent SSD copy failures and addressed an NFS permission edge case.

### Path looks present but import says missing only on some workers
**Symptom pattern:** Path namespace mismatch between lane workers.
**Fix:** Run `ls` of the import path under the cryoSPARC owner on every worker in the lane; mount missing workers consistently before retrying.

---

## 3. GPU / CPU / RAM / scheduling

### `cufftAllocFailed`, `cufftInternalError`, `pycuda._driver.MemoryError: cuMemAlloc failed: out of memory`, `cuMemHostAlloc failed`, `MemoryError: cuArrayCreate failed`
**Likely cause:** GPU (or host pinned) memory exhausted — typically box size × batch size × #GPUs exceeds VRAM, or another process holds VRAM. Exact variants include `pycuda._driver.MemoryError: cuMemHostAlloc failed: out of memory in v3.0` and forum shorthand like `CUDA memory error during 2D classification`.
**Checks:** `nvidia-smi` for current usage; job's box/crop, batch size, F-EM iterations, multi-GPU settings.
**Fix:** Reduce box (crop in extract), lower batch size, drop GPU count, or move to a higher-VRAM card. v4.1 reduced extraction GPU memory; older v3.0/v2.15 cases had specific patches.

### `Child process ... terminated unexpectedly with exit code -9`
**Likely cause:** Linux OOM-killer or scheduler killed the worker process — almost always host RAM, not GPU.
**Checks:** `dmesg | grep -iE 'oom|killed process'`, SLURM job log for `oom-kill` / `Out Of Memory`, requested vs. node RAM.
**Fix:** Increase RAM request, lower box/threads, run on a higher-memory node. The downstream heartbeat loss is a symptom, not the cause.

### Exact SLURM/cgroup OOM + heartbeat-loss pattern
**Symptom pattern:** The cryoSPARC event log may report command loss or heartbeat failure, while the scheduler log contains the real cause.

Observed exact strings/identifiers:
- `Connection to cryosparc command lost. Heartbeat failed 3 consecutive times at 2024-07-14 22:07:37.710743.`
- `slurmstepd-biomix10: error: Detected 1 oom-kill event(s) in StepId=679604.0. Some of your processes may have been killed by the cgroup out-of-memory handler.`
- `srun: error: biomix10: task 0: Out Of Memory`
- `slurmstepd-biomix10: error: Detected 1 oom-kill event(s) in StepId=679604.batch. Some of your processes may have been killed by the cgroup out-of-memory handler.`
- Example environment metadata seen with this family: run/document id `6693e74d03031811dbc0e16c`, `CUDA_version` `11.8`, `available_memory` `247.14GB`, CPU `Intel(R) Xeon(R) Silver 4410Y`, NVIDIA driver/CUDA runtime `12.3`, GPU `NVIDIA L40S`, PCI bus `0000:3d:00`, arch `x86_64`, host `biomix10`, kernel `5.15.0-105-generic #115-Ubuntu SMP Apr 15 09:52:04 UTC 2024`.

**Fastest checks:** scheduler stdout/stderr, `sacct`/`scontrol show job`, cgroup memory limit, requested RAM, node memory pressure.
**Fix:** increase memory request or reduce job memory footprint; treat heartbeat timestamps (`2024-07-14 22:07:17.665957`, `2024-07-14 22:07:17.674537`, `2024-07-14 22:07:27.684655`, `2024-07-14 22:07:27.692649`, `2024-07-14 22:07:37.702753`, `2024-07-14 22:07:37.710694`, `2024-07-14 22:07:37.710743`) as secondary evidence, not root cause.

### `BrokenPipeError`, "heartbeat failed" after OOM
**Symptom pattern:** Almost always downstream of a child process kill or command_core connectivity loss.
**Fix:** Read the *earlier* log lines; treat the BrokenPipe as a follow-on signal.

### `no heartbeat received in 30 second`
**Likely cause:** Job still running but its single update missed the window (e.g., long single-step computation, slow filesystem).
**Fix:** Verify the worker is still computing (`top`/`nvidia-smi`); set `CRYOSPARC_HEARTBEAT_SECONDS=180` in master `config.sh` if you regularly see false positives. Restart master after editing.

### GPUs present but jobs sit "waiting for resources" on CPU
**Likely cause:** Lane's CPU-per-GPU accounting too low for the job; CPU-bound steps starve.
**Checks:** Lane resource config and scheduler request; for multi-GPU 2D classification, v4.6 raised CPU requests — older builds may need a manual bump.
**Fix:** Adjust lane CPU-per-GPU; on clusters, raise `--cpus-per-task` in the submission script.

### `nvcc fatal : Value 'sm_75' is not defined`
**Likely cause:** CUDA toolkit older than the GPU architecture (sm_75 = Turing / RTX 20xx).
**Fix:** Install a CUDA toolkit that supports your GPU; point the worker at it with `cryosparcw newcuda /path/to/cuda`.

### `ImportError: libcurand.so.10` / `libcusparse.so.11` / `libcusolver.so.10` / `libcufft.so.10 cannot open`
**Likely cause:** Worker's CUDA library path differs from when it was last connected (CUDA upgraded, env changed).
**Checks:** `echo $LD_LIBRARY_PATH`; `ls /usr/local/cuda*/lib64/libcurand.so.10`.
**Fix:** `cryosparcw newcuda /path/to/cuda` matching the runtime; reinstall worker deps if the wrong CUDA was used during install.

### `ModuleNotFoundError: No module named 'pycuda'` during worker install
**Likely cause:** Worker dependency install was interrupted or used a stale env.
**Fix:** `cryosparcw forcedeps`; if that fails, remove `deps/` under the worker install and re-run `cryosparcw install ...`.

### Transparent hugepages (THP) hurting performance
**Symptom pattern:** Sluggishness/latency spikes correlated with large allocations.
**Fix:** v4.6+ asks the OS not to allocate THP and warns when THP is `always`. On older builds, set THP to `madvise` or `never` at the OS level.

---

## 4. Job-internal tracebacks and version-fixed bugs

### `'NoneType' object is not subscriptable`
**Symptom pattern:** Generic Python null deref — many distinct root causes. Don't infer cause from this string alone.
**Known contexts:** older Heterogeneous Refinement (workaround: enable intermediate plots); cryosparc-tools `import_movies` (API bug — see §6).
**Fix:** Check job type, cryoSPARC version, and the *preceding* log lines before acting.

### `TypeError: 'numpy.float64' object cannot be interpreted as an index`
**Likely cause:** Old cryoSPARC + an external numpy contaminating the bundled conda env.
**Fix:** Ensure no system `PYTHONPATH`/`numpy` overrides the bundled env; update cryoSPARC. Do not `pip install` into the master/worker env.

### `ValueError: could not broadcast input array from shape ... into shape ...` in Create Templates from imported volume
**Likely cause:** Imported map is non-cubic or has a box shape that violates the job's padding assumptions.
**Fix:** Use Volume Tools to repad to a cubic box matching expectations; re-run.

### `IndexError: index -1 is out of bounds` / `index 1 is out of bounds` in Patch CTF v3.1.0
**Likely cause:** Algorithm change in Patch CTF in v3.1.0.
**Fix:** Switch to classic CTF estimation as a workaround, or update to a newer cryoSPARC with the fix.

### `AssertionError: No output result named micrographs_fail.ctf` after CTFFIND4 failures
**Likely cause:** All CTFFIND runs failed, so the failed-output result was never created (output handling bug).
**Checks:** Look at the CTFFIND error log printed in the event log; verify CTFFIND OS deps (libtiff etc.).
**Fix:** Resolve CTFFIND deps below before relying on CTFFIND output.

### CTFFIND: `libtiff.so.3: cannot open shared object file`
**Likely cause:** Worker missing legacy libtiff after an OS update; or CTFFIND binary mismatched with worker deps.
**Fix:** `cryosparcw forcedeps`; if libtiff.so.3 is missing system-wide, install the compatibility package.

### CTFFIND: `Error: mode 12 MRC files not currently supported`
**Likely cause:** Input micrographs are in MRC mode 12 (float16), which CTFFIND4 cannot read.
**Fix:** Convert to mode 2 (float32) with `e2proc2d.py`/`relion_image_handler`, or use cryoSPARC's native Patch CTF instead.

### `wrong generation counter`
**Likely cause:** Long-running job hitting an internal counter race.
**Fix:** Fixed in v4.2; update.

### 3DFSC: `list index out of range`
**Fix:** Fixed in v4.2; update.

### 2D classification: blank/faint classes with multi-GPU
**Symptom pattern:** Classes appear empty or near-empty only when using >1 GPU.
**Fix:** Fixed in v4.2; run on single GPU as a temporary check, then update.

### 3D Classification: `KeyError` referencing CTF fields when "output results every F-EM iteration" is enabled
**Fix:** Fixed in v4.2; update or disable per-iteration output on older builds.

### 3D Classification: failures when re-ordering classes + outputting intermediate results
**Likely cause:** Two options that conflicted in earlier builds.
**Fix:** v4.2 made them mutually exclusive — pick one. Update if you need both effects.

### Local refinement: plotting failures at end of job
**Fix:** Fixed in v5.0; update. Job results are usually still valid on older builds — re-run only if plots/metadata are needed.

### `RuntimeError: Could not initialize missing alignments3D_multi ... missing dtype param 'K'`
**Likely cause:** Merging particle sets / passthrough edge case in jobs that produce `alignments3D_multi`.
**Fix:** Fixed in v5.0.6. For an existing near-complete job, mark-complete with caution; otherwise clone and rerun the upstream output(s) on a fixed version.

### `numpy.linalg.LinAlgError: Array must not contain infs or NaNs` in 3D Variability
**Likely cause:** NaN/Inf in particle metadata (e.g., bad scales) or pathological inputs.
**Checks:** Inspect particle dataset for NaN/Inf in scale/CTF columns.
**Fix:** One reported workaround: set per-particle scale default to `Optimal` rather than `Input`. Otherwise filter offending particles upstream.

---

## 5. cryoSPARC Live

### Live not seeing new exposures
**Symptom pattern:** Files exist on disk but session counters do not advance.
**Checks:** File pattern matches (gain/movie regex); raw data path resolves on the Live worker; file mtimes are advancing (sshfs/NFS sometimes lag); recursion settings; same files import successfully in a normal Import Movies job.
**Fix:** Adjust patterns; switch to direct NFS; restart session; v4.2 fixed a bug where Live could stop discovering new exposures.

### Live: `OSError: [Errno 40] Too many levels of symbolic links`
**Likely cause:** Symlink loop in the watched raw data path.
**Fix:** Replace looped symlink with a real path (see §2 entry).

### Live ice thickness/overview: `noUiSlider ... 'range' value isn't numeric`, NaN ice thickness
**Likely cause:** A movie produced NaN ice thickness (outlier/bad exposure); slider can't render NaN range.
**Checks:** Browser console for the offending exposure ID; inspect the movie; if needed use browser/UI error logs from https://guide.cryosparc.com/setup-configuration-and-management/troubleshooting#user-interface-error-logging.
**Fix:** Reject/exclude the bad exposure; reload the page.
**Observed source:** `docs/forum_threads/raw/app/10_10647_interactive-exposure-curation-failing.json`, thread https://discuss.cryosparc.com/t/interactive-exposure-curation-failing/10647, screenshot https://discuss.cryosparc.com/uploads/default/original/2X/e/e7b2d7d20ee72db7733dbcacd817f2bc38c3b370.png.

### Live preprocessing: `IndexError: index 3 is out of bounds for axis 0 with size 0`
**Likely cause:** A particle-picking threshold set to zero produced zero picks, breaking a downstream array shape.
**Fix:** Do not disable picking by setting thresholds to 0 — use the documented disable toggle instead; raise threshold above 0.

### `ERROR: This hostname is already registered! Remove it first.`
**Likely cause:** Stale Live lane/worker registration for the same hostname.
**Fix:** Remove the old registration in the lane config, then re-add.

### Live/RTP: `Error in RTP request: RequestError: Error: socket hang up`, `runVisExtern`
**Likely cause:** RTP/visualization worker dropped the connection — could be transient network, command_vis crash, or worker OOM.
**Checks:** `cryosparcm log command_vis`; RTP worker log; network between browser/master/worker.
**Fix:** Collect logs first; only then restart RTP worker / command_vis. Restarting blind throws away the diagnostic.

### `TIFFReadDirectory ... Input/output error` / `TIFFOpen ... Input/output error`
**Likely cause:** Live worker cannot reliably read movies over the current mount (sshfs flakiness, NFS stalls, storage I/O errors).
**Checks:** `dmesg` on the worker; `mount` output; file server health.
**Fix:** Switch from sshfs to NFS or direct mount; resolve storage I/O; do not blame Live until the path reads cleanly outside cryoSPARC.

### Live: preprocessing workers idle while queue grows
**Symptom pattern:** Not necessarily a crash. May be GPU-allocation/lane sizing rather than failure.
**Checks:** Streamlog for each worker — fetching/no work vs. actually stuck; lane GPU assignment; whether the session is paused.
**Fix:** Re-balance GPU assignment; resume if paused.

### Live sessions all paused after master restart (v4.2 and earlier)
**Fix:** v4.3 auto-pauses sessions on restart cleanly; update. On older builds, manually resume after restart.

---

## 6. cryosparc-tools / scripting / API

### `Cryosparctools failed to connect` / `assert cs.test_connection(), Connection to cryosparc failed`
**Likely cause:** Wrong host/port/license, user mismatch, command_vis down, or tools version mismatch with master.
**Checks:** `cryosparcm log command_vis`; verify host/port from `cryosparcm status`; cryosparc-tools version matches master series.
**Fix:** Use token-based auth on v5.0+ (not backported to 4.7 per issues digest); reinstall tools matching master.

### `ValidationError when running cs.api.sessions.find()`
**Fix:** Fixed in cryosparc-tools v5.0.2; update tools.

### `gainref_path` empty string becomes `.` in Import Movies `create_job`
**Symptom pattern:** Tools converts an empty string param to `.`, then import resolves to current dir.
**Fix:** Omit the `gainref_path` parameter entirely if there is no gain reference. (Open issue as of 2026-04-10.)

### `load_outputs` on partially complete jobs
**Symptom pattern:** Older tools raised on partially complete jobs.
**Fix:** Fixed in cryosparc-tools v4.3.0; update.

### `Job ... does not have any results for output all_exposures`
**Likely cause:** Output not present (job aborted, wrong output name, or wrong job type).
**Checks:** `job.doc()` / inspect output groups; confirm job status `completed`.
**Fix:** Load only outputs that the job actually produced.

### `AttributeError: 'Job' object has no attribute 'output_types'`
**Likely cause:** Tools/cryoSPARC version mismatch or stale script targeting a removed attribute.
**Fix:** Use the current cryosparc-tools API matching your master version; consult the version's docs rather than older blog/forum snippets.

### `ServerError: 'NoneType' object is not subscriptable` connecting `import_movies` output / `HTTP Error 500` / `Did not receive a JSON response from get_job`
**Likely cause:** Known `import_movies` API path bug (see issues digest).
**Workaround:** Use the `Job` object returned by `create_job` directly rather than re-fetching by UID; inspect `cryosparcm log command_core` for the underlying exception; update when fixed.

### `IndexError: list index out of range` while loading particles
**Likely cause:** One output slot's dataset file is missing — typically because the job didn't complete fully.
**Workaround:** Load only the slots you need (e.g., `job.load_output('particles', slots=['blob','ctf'])`) instead of all slots.

### `HTTP Error 422 UNPROCESSABLE ENTITY` from `get_project_file`
**Likely cause:** Project directory is a symlink.
**Fix:** Update CryoSPARC + tools to ≥ v4.3 (fixed).

### `pip install -e .[dev]` / Python 3.11 issues installing cryosparc-tools
**Likely cause:** Python 3.11 incompatibility with some pinned deps (e.g., `python-snappy`).
**Fix:** Install on Python ≤ 3.10; use conda for `python-snappy` if needed.

### Creating a project programmatically via tools
**Symptom pattern:** Not an error — just under-documented.
**How:** Use `cs.cli.create_empty_project(...)` (lower-level CLI bridge) when the public `cs.create_project` isn't sufficient.

---

## 7. Workflow misuse symptoms

### RBMC: `AssertionError: All movies must have the same number of frames`
**Likely cause:** Mixed/truncated movies in the input set.
**Fix:** Re-import with movie-header checking enabled; use `failed_movies` to identify bad files; exclude inconsistent ones. Ensure every movie that contributes particles is in the RBMC input.

### RBMC fails because input is not raw movies
**Symptom pattern:** RBMC requires raw movies, not motion-corrected micrographs.
**Fix:** Connect raw movies (and matching particles) to RBMC; re-run Patch Motion if needed.

### `AssertionError: Could not find match for r170-2-00001.mrc`
**Likely cause:** Importing motion-corrected micrographs whose names/paths don't match the raw movies they were derived from.
**Fix:** Adjust path suffix/trim parameters in the import so micrograph names align with movie names exactly.

### 3D Classification: `Non-optional inputs ... particles.alignments3D ... not connected`
**Likely cause:** Connected particles lack `alignments3D` — e.g., directly from a 2D job or freshly imported.
**Fix:** Run a refinement/reconstruction first; connect those aligned particles into 3D Classification.

### Imported particles/micrographs don't align (cryoSPARC ↔ RELION)
**Symptom pattern:** Picks visualized on the wrong micrographs, or coordinates off by a constant offset.
**Checks:** Micrograph path trimming/prefix; coordinate origin convention; passthrough completeness in `csparc2star`.
**Fix:** Match path strings byte-for-byte; preserve passthroughs end-to-end.

### `csparc2star`: `KeyError: 'rlnMicrographName'`, `passthrough is required`, `ValueError: Columns must be same length as key`
**Likely cause:** Missing passthrough or particle count mismatch between the passed `_particles.cs` and `_passthrough.cs`.
**Fix:** Provide the matching passthrough file from the same job; ensure the particle file you pass corresponds to the same dataset.

### `No particles corresponding to input micrographs were found`
**Likely cause:** Picks/particles don't reference any of the connected micrographs, or zero picks were produced.
**Checks:** Picker outputs non-empty; micrograph UIDs match between picks and connected exposures.
**Fix:** Re-pick / fix linkage; confirm non-zero picks in the picker job.

### Topaz: `Cannot determine topaz version`
**Likely cause:** Topaz conda env or wrapper invokes the wrong Python / inherits cryoSPARC's env.
**Fix:** Write a wrapper script that `conda deactivate`s the cryoSPARC env, activates Topaz's env, and execs `topaz "$@"`. Test `topaz --version` as the cryoSPARC worker user.

### Topaz: `Argument list too long`
**Likely cause:** Too many micrograph paths in the single command line.
**Fix:** Split exposures into subsets (~5000 per job is a safe upper bound; depends on OS `ARG_MAX`).

### DeepPicker: `Input number of GPUs must be <= available GPUs`
**Symptom pattern:** Often *not* an actual GPU-count problem — it's TensorFlow/CUDA failing to load and reporting 0 GPUs.
**Checks:** Joblog for `libcusparse`/`libcusolver` load errors.
**Fix:** Fix CUDA library path on the worker; re-test.

### DeepPicker: `ValueError: need more than 1 value to unpack`, `cannot reshape array of size 0`
**Likely cause:** Empty or pathological micrograph hit DeepPicker, or a DeepPicker edge case.
**Fix:** Split the dataset to isolate the first failing micrograph; inspect joblog; exclude the bad micrograph or fix its motion correction.

---

## 8. Index by failure bucket

| Bucket | Entries (jump targets) |
| --- | --- |
| Can't start cryoSPARC | DB spawn error, WiredTiger panic, address in use, supervisor socket refused, parse signed file, owner-of-script |
| Worker won't launch | exit 255 / 1, FAILED TO LAUNCH, failed to connect link, libcurand/cusparse/cusolver/cufft, sm_75 |
| Wrong place to run | Job must be queued on master |
| Path/permission feels wrong | invalid path, lock file P12, Px no such S1, get_project_file 422, too many symlinks |
| SSD cache problems | waiting for unlocked, not enough space, NFS perms |
| OOM/scheduler kill | exit code -9, BrokenPipe, heartbeat 30s |
| GPU memory | cufftAllocFailed, cuMemAlloc, cuArrayCreate |
| Resource starvation | GPUs idle waiting on CPU |
| THP performance | hugepages warning |
| CTF failures | Patch CTF index, CTFFIND fail output, libtiff.so.3, mode 12 MRC |
| 2D / 3D Class / 3DFSC / Local refine bugs | blank classes, CTF KeyError, reorder+intermediate, list index 3DFSC, plotting v5.0, alignments3D_multi K |
| 3D Var | LinAlgError NaN/Inf |
| Live ingestion | not seeing data, symlink loop, NaN ice slider, threshold-0 IndexError, duplicate hostname, RTP socket hang up, TIFF I/O error, workers idle |
| Tools/API | connect fail, ValidationError sessions, gainref empty, load_outputs partial, all_exposures missing, output_types AttributeError, import_movies ServerError, particles list-index, 422 symlink, py3.11 install, create_empty_project |
| Workflow misuse | RBMC frames/raw, micrograph match, alignments3D not connected, passthrough/path mismatch, csparc2star KeyError, no particles for micrographs, Topaz version/argv, DeepPicker CUDA/empty |

---

## 9. Sources

- `15_troubleshooting.md`
- `docs/forum_threads/digests/forum_troubleshooting.md`
- `docs/forum_threads/digests/forum_import.md`
- `docs/forum_threads/digests/forum_cryo-em-data-processing.md`
- `docs/forum_threads/digests/forum_3d-reconstruction.md`
- https://discuss.cryosparc.com/t/error-while-running-a-job-non-zero-exit-status-255/2030
- `docs/forum_threads/raw/app/10_10647_interactive-exposure-curation-failing.json`
- https://discuss.cryosparc.com/t/interactive-exposure-curation-failing/10647
- https://discuss.cryosparc.com/uploads/default/original/2X/e/e7b2d7d20ee72db7733dbcacd817f2bc38c3b370.png
- https://guide.cryosparc.com/setup-configuration-and-management/troubleshooting#user-interface-error-logging
- `docs/forum_threads/digests/forum_hardware-and-performance.md`
- `docs/forum_threads/digests/forum_data-management.md`
- `docs/forum_threads/digests/forum_cryosparc-live.md`
- `docs/forum_threads/digests/forum_scripting.md`
- `docs/forum_threads/digests/forum_features-and-functionality.md`
- `docs/forum_threads/digests/forum_ctf-estimation.md`
- `docs/forum_threads/digests/forum_2d-classification.md`
- `docs/forum_threads/digests/forum_motion-correction.md`
- `docs/forum_threads/digests/forum_particle-picking.md`
- `docs/forum_threads/digests/forum_3d-var.md`
- `docs/forum_threads/digests/forum_3d-classification.md`
- `docs/forum_threads/digests/forum_particle-curation.md`
- `docs/forum_threads/digests/forum_app.md`
- `reference/cryosparc-tools-meta/issues_digest.md`
- `reference/release_notes/markdown/v4.0.md`
- `reference/release_notes/markdown/v4.1.md`
- `reference/release_notes/markdown/v4.2.md`
- `reference/release_notes/markdown/v4.3.md`
- `reference/release_notes/markdown/v4.4.md`
- `reference/release_notes/markdown/v4.5.md`
- `reference/release_notes/markdown/v4.6.md`
- `reference/release_notes/markdown/v5.0.md`
