# Topic 15 — Troubleshooting

## Scope
How to troubleshoot cryoSPARC systematically: what to check first, how to separate user/setup/version problems from real algorithmic problems, where to pull evidence from, and what fixes are commonly high-yield.

## Core mindset
Most cryoSPARC failures are not mysterious. They usually fall into one of five buckets:
1. **version-fixed bug**
2. **worker / shell / SSH / environment problem**
3. **filesystem / path / permission problem**
4. **GPU / CPU / RAM / scheduling problem**
5. **workflow misuse or mismatched inputs**

The fastest progress comes from identifying the bucket first, not from rerunning the same failed job blindly.

## First-pass triage
When a user says “it failed”, check in this order:
1. **What job type failed?**
2. **What exact error text or traceback appeared?**
3. **What changed recently?**
   - updated version
   - new worker
   - new GPU driver
   - moved project/storage
   - imported data from another package
4. **Is this likely old-version behavior already fixed upstream?**
5. **Is the failure reproducible on restart, or was it transient?**

If the error text is missing, troubleshooting quality drops hard. Exact strings matter because many cryoSPARC failures are recurring and version-specific.

## What evidence matters most
Highest-value evidence:
- exact error message / traceback as text
- cryoSPARC version
- job type and non-default parameters
- whether failure is on master, worker, or Live session
- relevant logs:
  - `cryosparcm log command_core`
  - `cryosparcm joblog Px Jx`
  - `cryosparcm log webapp`
  - `cryosparcm log database`
- worker environment facts:
  - shell type
  - driver version
  - CUDA compatibility
  - `nvidia-smi`
  - CPU / RAM availability

Practical rule: a pasted traceback is far more useful than a screenshot of red text.

## The shortest useful troubleshooting loop
1. **Read the exact error**
2. **Classify the failure bucket**
3. **Check whether the version is old enough that the bug may already be fixed**
4. **Try the smallest safe corrective action**
   - restart job
   - clear and rerun
   - restart cryoSPARC if system-level behavior looks stale
   - reduce resource demands if failure smells like memory/scheduling
5. **Escalate to environment or data-path debugging only if the small fix fails**

This is better than immediately rewriting parameters or rebuilding the whole pipeline.

## Failure buckets and what to do

### 1. Version-fixed bugs
This is common enough that it should be checked early, not late.

Strong clues:
- failure is weird, brittle, or UI-specific
- forum thread ends with “fixed in vX.Y”
- failure depends on optional plotting, slider behavior, or edge-case output ordering
- issue affects older Live sessions, imports, or classification internals

Examples from collected sources:
- older heterogeneous refinement / classification failures tied to plotting behavior
- Live sessions stopping discovery of new exposures, fixed in later releases
- import failures for specific file types or edge-case metadata
- local refinement plotting failures fixed in v5.0
- worker-launch failures related to shell behavior fixed in v5.0

Advisor default:
- if the instance is substantially behind and the symptom matches a known fix, **recommend update before deep manual debugging**

### 2. Worker launch / shell / SSH problems
These are classic “job never really started correctly” failures.

Typical symptoms:
- `non-zero exit status 255`
- SSH launch failure
- worker test failures
- job marked failed immediately on launch
- restart/queue behavior looks wrong before any real computation happens

Common causes:
- SSH connectivity or key setup problems
- shell init files printing unexpected text
- unsupported / problematic shell behavior
- environment variables not propagating to worker or cluster submission
- library mismatch on the worker

High-yield checks:
- run worker tests
- inspect `command_core` logs
- confirm the worker account can SSH non-interactively
- confirm shell startup is quiet
- check whether the instance version predates shell/launch fixes

Important version-aware notes:
- v4.0 fixed some SSH / command failures caused by system library mismatch
- v5.0 fixed cases where extra shell output could mark jobs as failed
- v5.0 fixed jobs failing to launch on worker nodes using `tcsh`

### 3. Filesystem / path / permission problems
This is one of the most common operational buckets.

Typical symptoms:
- invalid path
- import fails unexpectedly
- file not found during caching
- symlinked or network-backed paths behave inconsistently
- permissions look wrong even though storage is mounted

Common causes:
- wildcard/path mismatch
- symlink oddities
- network filesystem semantics not matching POSIX expectations
- imported job or project paths moved or partially detached
- cache locking / distributed filesystem issues

What to check:
- path exists exactly as configured
- master and worker see the same path namespace
- symlink targets resolve on the worker
- filesystem supports the locking/permission assumptions cryoSPARC expects
- whether the problem disappears on local SSD / simpler path layout

Version-aware notes:
- v4.4 and v4.5 materially improved SSD cache robustness
- v5.0 improved fallback for silent SSD-cache copy failures and fixed some NFS permission issues
- v5.0 added `CRYOSPARC_CLI_SKIP_ACCESS_CHECK=true` for environments where reported UNIX permissions are misleading

### 4. GPU / CPU / RAM / scheduling problems
These often masquerade as algorithmic failure.

Typical symptoms:
- queued forever waiting on CPU despite idle GPUs
- out-of-memory or CUDA allocation errors
- one or more GPUs appear unused
- jobs fail only at larger box size or multi-GPU count
- Live or classification performance collapses under throughput

Common causes:
- not enough CPUs per GPU
- GPU VRAM too small for chosen box size / batch size
- scheduler lane under-provisioned
- transparent hugepages or cache behavior hurting stability/performance
- multi-GPU bugs in older versions

What to try:
- reduce GPUs or reduce box size / memory pressure
- inspect CPU requests and lane resource accounting
- verify driver compatibility with the installed cryoSPARC version
- compare single-GPU vs multi-GPU behavior
- benchmark if the system behavior is suspiciously poor rather than clearly broken

Useful examples:
- some older systems effectively stalled because CPU allocation, not GPU count, was the real bottleneck
- `cufftAllocFailed` / `cufftInternalError` can reflect over-aggressive GPU memory use during extraction
- older multi-GPU classification issues were fixed upstream

Version-aware notes:
- v4.1 reduced pathological GPU memory use in Extract From Micrographs (GPU)
- v4.2 fixed blank/faint 2D classes in some multi-GPU cases
- v4.6 improved CPU requests for multi-GPU 2D classification
- v5.0 surfaces lane/target resource exhaustion more clearly in the UI

### 5. Workflow misuse / mismatched inputs
A lot of “software bugs” are actually input mismatches.

Typical symptoms:
- imported particles do not align with source micrographs
- RBMC fails because inputs are not raw movies
- local refinement / classification outputs are nonsense because masks or upstream references are wrong
- imported results pass initial checks but fail downstream

Common causes:
- wrong path-suffix trimming when linking imported particles to micrographs
- trying to do movie-dependent jobs from imported micrographs instead of raw movies
- importing data from RELION with orientation/path assumptions that do not transfer directly
- using a workflow branch before prerequisite upstream cleanup/refinement is good enough

Practical rule:
Before treating odd output as a crash, ask whether the inputs really satisfy the job’s assumptions.

## A decision ladder by symptom

### Job fails immediately on queue or launch
Think:
- worker / SSH / shell / command-core
- wrong lane / missing resources
- version-specific launch bug

First checks:
- `cryosparcm log command_core`
- worker connection / shell cleanliness
- queue target resources

### Job runs, then dies with traceback
Think:
- version-fixed job bug
- bad parameter edge case
- memory exhaustion
- malformed input metadata

First checks:
- exact traceback
- version
- whether same job type has release-note fixes nearby
- whether simpler parameters or smaller scale succeed

### Job completes, but result is obviously wrong
Think:
- workflow misuse
- imported coordinate/path mismatch
- wrong handedness/orientation assumption
- overaggressive thresholds or masking
- continuous heterogeneity being forced into a discrete branch

First checks:
- input provenance
- upstream assumptions
- whether the chosen job type matches the scientific question

### Live session stops behaving sensibly
Think:
- file watching / timestamps / recursion / stale session state
- version-specific Live bug
- gain-ref edge case
- worker/lane throughput mismatch

First checks:
- is Live still discovering files?
- do normal import jobs see the same files?
- has the instance been restarted?
- does the version match known Live fixes?

### cryosparcm start / stop / restart behaves inconsistently
Think:
- orphaned process
- stale supervisor socket
- partial shutdown after crash

First checks:
- confirm whether processes are actually still running
- inspect `/tmp/cryosparc-supervisor-*.sock`
- only remove stale socket files after confirming no related process is active

This is a real pattern, not a rare corner case.

## High-yield concrete patterns

### Pattern: `non-zero exit status 255`
Interpret first as **launch-path problem**, not a reconstruction problem.
Most likely surface:
- SSH / worker command launch
- shell / environment propagation
- worker configuration issue

### Pattern: `'NoneType' object is not subscriptable`
Do not over-interpret the Python text itself.
Ask:
- which job type?
- which version?
- is this an old known bug?
- is an optional plotting or output setting triggering it?

In collected troubleshooting material, an old hetero-refine failure of this type was resolved by enabling intermediate plots and later fixed upstream.

### Pattern: Live no longer finds new exposures
Treat as one of:
- wrong path / recursion / timestamps
- stale session state
- known Live bug

This exact class of issue appears in release-note fixes across multiple versions, so version-awareness matters a lot.

### Pattern: import worked, but downstream movie-linked job fails
Think mismatch between:
- raw movies vs motion-corrected micrographs
- imported particle coordinates vs micrograph naming/path trimming
- TIFF/MRC orientation assumptions across packages

### Pattern: GPUs are present, but jobs wait on CPU
Do not trust GPU count alone.
CryoSPARC often needs enough CPUs per GPU to launch and sustain work. What looks like a GPU problem may really be lane CPU starvation.

## Restart, clear, or update?

### Restart the job
Good when:
- likely transient heartbeat / worker hiccup
- inputs and configuration are probably fine
- failure is not clearly deterministic

### Clear and rerun
Good when:
- output state may be partial or stale
- a parameter was corrected
- import/link metadata changed

### Restart cryoSPARC instance
Good when:
- system behavior is stale or contradictory
- Live/file-watching state looks stuck
- services partially died or webapp/command behavior diverges

### Update cryoSPARC
Good when:
- the symptom matches a documented fix
- the current version is meaningfully behind
- repeated debugging would just be working around a solved bug

## What not to do
- do not keep rerunning the same failed job without changing the diagnosis
- do not assume every traceback means user error
- do not assume every strange result means a software bug
- do not delete socket or state files before confirming the related processes are dead
- do not debug import / interop issues without checking path/orientation conventions
- do not give strong advice without checking version when the symptom is obviously version-shaped

## Advisor defaults
If a user asks “how do I debug this?”
1. get the **exact error text**
2. identify **job type + version**
3. classify into:
   - launch/env
   - filesystem/path
   - resource/scheduling
   - workflow mismatch
   - known version bug
4. try the **smallest corrective action** first
5. update before deep workaround-hunting if a matching fix already exists upstream

## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

- `docs/forum_threads/digests/forum_troubleshooting.md`
- `docs/forum_threads/digests/forum_import.md`
- `docs/forum_threads/digests/forum_hardware-and-performance.md`
- `reference/release_notes/markdown/v4.0.md`
- `reference/release_notes/markdown/v4.1.md`
- `reference/release_notes/markdown/v4.2.md`
- `reference/release_notes/markdown/v4.3.md`
- `reference/release_notes/markdown/v4.4.md`
- `reference/release_notes/markdown/v4.5.md`
- `reference/release_notes/markdown/v4.6.md`
- `reference/release_notes/markdown/v5.0.md`
