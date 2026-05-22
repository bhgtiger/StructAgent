# Reference — cryoSPARC Version Caveats

## Scope / how to use

Retrieval-first map of version-specific cryoSPARC behavior, compatibility cliffs, fixed bugs, and stale-advice traps for advisor and automation workflows.

Use this when:
- a user reports an error and their installed version may matter;
- a forum answer predates v4/v5 interface or CLI changes;
- writing automation against `cryosparcm`, cryosparc-tools, Live, Workflows/Blueprints, or job parameters;
- deciding whether to debug deeply or recommend updating first.

Always confirm the installed **master version**, **worker version**, **GPU driver/CUDA context**, and **cryosparc-tools version** before applying version-specific advice. If the installed version is older than the source note cited here, verify against installed release notes rather than assuming current behavior.

Source note: original synthesis from public cryoSPARC guide/release notes/forum/tutorial materials and public `cryosparc-tools` documentation/API material; consult upstream documentation for authoritative details.

---

## Fast version triage checklist

1. **Identify exact version**
   - Ask for `cryosparcm status` / About page version.
   - For automation, inspect whether the instance is v4-style or v5-style before issuing CLI commands.
2. **If v5.0.0–v5.0.2 and upgrade/attach validation failed**
   - Check for fixed v5.0.1/v5.0.3 migration bugs before debugging project data manually.
3. **If v4 → v5 upgrade**
   - Check OS GLIBC, NVIDIA driver, GPU compute capability, v5 CLI incompatibility, Live profile compatibility, and performance-benchmark compatibility.
4. **If CUDA/driver error**
   - v4.4 bundled CUDA 11.8 and requires newer driver; v5 uses CUDA 12.8 and NVIDIA driver 570.26+.
5. **If Live issue**
   - Many Live behaviors changed between v4.0, v4.4–v4.6, and v5.0; old Live forum advice can be stale.
6. **If SSD cache / file I/O issue**
   - Check v4.2, v4.4, v4.5, v4.6, and v5.0 cache changes before assuming a site filesystem bug.
7. **If Deep Picker / Topaz issue**
   - Deep Picker is deprecated/removed in v5; Topaz behavior changed in v4.5/v5.0.
8. **If masks/refinement changed after update**
   - v5 introduced a new dynamic refinement-mask method and related parameters.

---

## Compatibility / upgrade cliffs

| Cliff | Affected versions | What changed | Advisor action | Source |
|---|---:|---|---|---|
| v4.0 major UI/data model transition | v3 → v4.0+ | New interface, integrated Live, project locks, changed project/job output filename behavior, new data-management guide. | Treat v3 UI/forum instructions as suspect; prefer v4+ docs for project locks, Live access, job cards, table/tree views. | `public cryoSPARC release notes v4.0` |
| Legacy web app removed | v4.4+ | Legacy web app that could be started via `cryosparcm start app_legacy` is no longer bundled. | Do not recommend legacy app fallback on v4.4+. | `public cryoSPARC release notes v4.4` |
| CUDA/driver requirement shift | v4.4+ | CryoSPARC bundles CUDA Toolkit 11.8; separate CUDA Toolkit no longer required for worker app; NVIDIA driver 520.61.05+ required. | On driver/CUDA errors, check driver first; do not assume missing local CUDA toolkit is the root cause. | `public cryoSPARC release notes v4.4` |
| CentOS 7 deprecation | v4.6 | CentOS 7 support deprecated; future versions will not support it. | Warn CentOS 7 users before upgrade; plan OS migration. | `public cryoSPARC release notes v4.6` |
| v5 OS/GPU hard requirements | v5.0+ | Requires GLIBC 2.28+; oldest compatible OS families include Rocky/RHEL 8 and Ubuntu 20.04; Ubuntu 22.04+ recommended. Requires NVIDIA driver 570.26+; uses CUDA 12.8; supports GPU compute capability 5.0–12.0. | Before v5 upgrade, audit OS, driver, and GPU architecture. Kepler compute 3.5 is no longer supported. | `public cryoSPARC release notes v5.0` |
| v5 CLI incompatibility | v5.0+ | New improved `cryosparcm` CLI is not compatible with v4 `cli` commands; scripts using v4 CLI need updates, including Live session management. | Automation must branch on version; never blindly run v4 CLI command forms on v5. | `public cryoSPARC release notes v5.0`, `14_cli_admin.md` |
| cryosparc-tools v5 compatibility | v5.0+ | New backwards-compatible cryosparc-tools version available for scripting with v5; previous scripts continue to function as before per release note. | Still pin/check tools version when debugging scripting failures; update tools alongside major instance upgrade. | `public cryoSPARC release notes v5.0` |
| Live configuration profiles | v5.0+ | Live configuration profiles in v5 are not backwards compatible; new v5 profiles are not retained when downgrading to v4. | Export/document Live configs before downgrade; do not promise profile round-trip. | `public cryoSPARC release notes v5.0`, `25_cryosparc_live.md` |
| Performance benchmarks | v5.0+ | v5 performance benchmarking system is not backwards compatible; new benchmarks can be recorded in v5 but not retained when downgrading to v4. | Treat benchmark comparisons across v4/v5 as non-equivalent unless re-run. | `public cryoSPARC release notes v5.0` |
| Deep Picker removal | v5.0+ | Deep Picker Train and Deep Picker Inference deprecated and no longer present in v5; previously-run jobs remain visible. | Recommend Topaz/newer alternatives for v5 workflows; do not suggest creating new Deep Picker jobs on v5. | `public cryoSPARC release notes v5.0` |
| Dynamic refinement masks | v5.0+ | New automatic mask generation method and “Use dynamic refinement mask” refinement parameter. | Mask/refinement advice differs from v4; check whether dynamic masks are enabled before recommending manual static-mask tuning. | `public cryoSPARC release notes v5.0`, `20_masks.md` |

---

## Version-by-version caveat table

| Version family | High-value caveats | Fixed / changed behavior to remember | Source |
|---|---|---|---|
| v4.0 | Major v4 interface; Live integrated into main app at `BASE_PORT`; legacy v3.3 app no longer starts by default; project locks introduced; output files no longer prefixed with project numeric identifiers on disk. Gctf became a legacy job. NU refinement gained optional Ewald sphere correction. | v4.0.x fixed SSH/system-library issues, Topaz errors, Live session edge cases, libtiff/LD_PRELOAD issues, and cluster-connect output behavior. | `public cryoSPARC release notes v4.0` |
| v4.1 | Introduced 3DFlex beta; multi-select actions and restart-job action; owner restrictions for some `cryosparcm` commands. | Fixed 3DFlex dependency build issue, 3DVA display/component bugs, scheduler jump bug after restarting GPU jobs, Live/CLI retrieval bugs, Gctf local CTF failures, and several interactive-job issues. | `public cryoSPARC release notes v4.1` |
| v4.2 | CUDA 11.8 support for Hopper/Ada GPUs; project-level intermediate-results output control. | Fixed SSD cache free-space infinite hang, cache network-timeout retries, multiple jobs using same SSD cache space, 3D Classification CTF-field KeyError, Live exposure discovery issues. | `public cryoSPARC release notes v4.2` |
| v4.3 | Added Data Cleanup Tools, Performance Benchmarking Utilities, Extensive Validation benchmark mode, `cryosparcm compact`, UI improvements. CTFFIND4 updated to v4.1.14. | Fixed Topaz Extract denoised-micrograph default, 3DFlex Generate frame count, worker test without SSD, Live lane-change and exposure discovery issues, Import Result Group Topaz failure, Job PDF parameter/version issues. | `public cryoSPARC release notes v4.3` |
| v4.4 | Bundles CUDA 11.8; driver 520.61.05+ required. Introduced Workflows/Blueprints, RBMC improvements, faster NU refinement, 3DFlex Reconstruction CTF-aberration support and lower-RAM cache/project read option, experimental improved SSD cache, BILD export for viewing directions. Legacy web app removed. | Fixed Live sessions created before v4.4, template picking in Live with one template, PatchCTF high-magnification assertion, Particle Subtraction half-set bug, 3DVA tile order, hand-flip axis bug, auto batchsize OOM-control parameter, background subtraction bug. | `public cryoSPARC release notes v4.4` |
| v4.5 | Workflows improved; browser local upload; Rebalance Orientations job; cFSC summary plots during refinement; improved SSD cache enabled by default with distributed locking strategy; Topaz defaults/resources updated. | Fixed v4.4 Patch Motion rerun empirical-dose-weight issue, motion/CTF freeze after abnormal child termination, 2D hard-classification posterior-count bug, 2D duplicate-removal pixel-size override for pre-v4.5 datasets, 3D Classification focus-mask plotting offset, 3DFlex segmentation-loading issues, SSD symlink failures, Live memory leak/export/worker issues. | `public cryoSPARC release notes v4.5` |
| v4.6 | CentOS 7 deprecated. New high-performance I/O system gives major particle read speedups; job tree/card/table views rebuilt; job groups; Inspect Particle Picks auto-cluster; local upload supports `.seg`; Live data-management tab deprecated in favor of compaction/restoration. | Fixed Falcon C EER import, high-performance I/O edge cases, SSD cache robustness on cluster filesystems, EER upsampling pixel-size display in Live, 3DFlex MRC segmentation off-by-one, Deep Picker workflow restrictions. | `public cryoSPARC release notes v4.6` |
| v5.0 | Major compatibility jump: GLIBC 2.28+, driver 570.26+, CUDA 12.8, GPU compute capability 5.0–12.0, new incompatible `cryosparcm` CLI, dynamic refinement masks, Job Dashboard/Comparison View, new Live run configuration/auto-start/auto-pause/workers-per-GPU, instance recovery via `cryosparcm recover`, per-result file deletion CLI endpoint. Deep Picker jobs removed. | v5.0.1–v5.0.3 fixed several v5.0.0 upgrade validation/project detach issues. v5.0.2–v5.0.5 fixed many Live export/template/auto-pause/config/profile issues, Topaz Cross Validation parameter handling, SSD copy fallback, local refinement SSD use in Extensive Validation. | `public cryoSPARC release notes v5.0` |

---

## Stale advice map

| Old advice pattern | Why it may be stale | Use instead |
|---|---|---|
| “Open Live at `BASE_PORT + 6`” | Since v4.0, Live is integrated into the main web application at `BASE_PORT`; `liveapp` service no longer has the old separate access pattern. | Access Live through the main cryoSPARC interface. (public cryoSPARC release notes v4.0) |
| “Start the legacy v3 web app to work around UI issues” | Legacy app is no longer bundled in v4.4+. | Use current v4/v5 UI paths; update stale screenshots. (public cryoSPARC release notes v4.4) |
| “Install/fix local CUDA Toolkit on workers” | v4.4+ bundles CUDA Toolkit 11.8 for worker app; v5 uses CUDA 12.8. Driver compatibility is often the real cliff. | Check NVIDIA driver and GPU compute capability first. (public cryoSPARC release notes v4.4, public cryoSPARC release notes v5.0) |
| “Gctf is a normal visible job” | In v4.0, Gctf is legacy and hidden unless legacy jobs are shown. | Prefer Patch CTF unless specifically using legacy Gctf; enable legacy jobs if needed. (public cryoSPARC release notes v4.0) |
| “Use Deep Picker Train/Inference for new picking work” | Deep Picker is deprecated/removed from v5 job creation. | Use Topaz or other current picking workflow for v5. (public cryoSPARC release notes v5.0) |
| “Use v4 `cryosparcm cli` command forms in scripts” | v5 CLI is not compatible with v4 `cli` commands. | Branch scripts by version and update Live/CLI automation for v5. (public cryoSPARC release notes v5.0) |
| “Live configuration profiles can be moved/downgraded freely” | v5 Live profiles are not backwards compatible and are not retained when downgrading to v4. | Export/document profiles before migration; rebuild profiles after downgrade. (public cryoSPARC release notes v5.0) |
| “Manual static masks are the normal refinement default” | v5 introduced a new automatic dynamic refinement-mask method. | Check dynamic-mask parameter and version before tuning mask dilation/soft edge. (public cryoSPARC release notes v5.0, `20_masks.md`) |
| “SSD cache bugs are site-specific; just disable cache” | Multiple cache fixes landed v4.2, v4.4, v4.5, v4.6, v5.0. | Check version-specific cache fixes before disabling cache permanently. (public cryoSPARC release notes v4.2–public cryoSPARC release notes v5.0, `24_disk_and_storage.md`) |
| “Forum workaround for v5.0.0 project detach validation is data corruption” | Several v5.0.0–v5.0.2 migration validation failures were fixed in v5.0.1/v5.0.3. | Upgrade to latest v5 patch before manual DB/project intervention. (public cryoSPARC release notes v5.0) |

---

## Advisor implications by workflow area

### Install / admin
- v4.4+: check NVIDIA driver 520.61.05+ before blaming missing CUDA Toolkit. (public cryoSPARC release notes v4.4)
- v4.6: CentOS 7 is deprecated; do not plan long-lived production upgrades on CentOS 7. (public cryoSPARC release notes v4.6)
- v5.0+: audit GLIBC 2.28+, OS family, NVIDIA driver 570.26+, and GPU compute capability 5.0–12.0 before upgrade. (public cryoSPARC release notes v5.0)
- v5.0+: v4 `cryosparcm cli` script snippets may be wrong; prefer v5 CLI reference. (public cryoSPARC release notes v5.0, `14_cli_admin.md`)
- v5.0+: `cryosparcm recover`, `worker connect`, `worker disconnect`, and `delete_output_result_files` expand admin automation surfaces. (public cryoSPARC release notes v5.0)

### CryoSPARC Live
- v4.0 moved Live into the primary interface; separate old Live access advice is stale. (public cryoSPARC release notes v4.0)
- v4.4–v4.6 changed Live storage, plotting, session management, lane behavior, data-management tab, and compaction/restoration recommendations. (public cryoSPARC release notes v4.4, public cryoSPARC release notes v4.6)
- v5.0 added auto-start/auto-pause, delay worker startup, multiple sessions with different raw-data directories, and workers-per-GPU. (public cryoSPARC release notes v5.0, `25_cryosparc_live.md`)
- v5 Live configuration profiles are not backwards compatible. (public cryoSPARC release notes v5.0)

### Import / EER / file handling
- v4.6.2 fixed Falcon C EER import failures. If a Falcon C EER import bug appears on older v4.6/v4.5, update first. (public cryoSPARC release notes v4.6)
- v4.6 fixed Live exposure pixel size display with EER upsampling. (public cryoSPARC release notes v4.6)
- v5 improved detection/reporting of truncated movie/micrograph/particle corruption. (public cryoSPARC release notes v5.0)
- For path/permission issues, combine version lookup with `17_error_lookup.md`; many “file not found” cases are worker namespace problems, not version bugs.

### Picking / deep picking
- v4.0–v4.5 changed Topaz setup, error messages, project-level executable path, resource defaults, downsampling mode, and extraction-radius handling. (public cryoSPARC release notes v4.0, public cryoSPARC release notes v4.5)
- v4.6 adds Inspect Particle Picks auto-cluster for denoised micrographs. (public cryoSPARC release notes v4.6)
- v5 removes Deep Picker Train/Inference from new job creation; previously-run jobs remain visible. (public cryoSPARC release notes v5.0)
- v5.0.4/v5.0.5 fixed Topaz Cross Validation parameter issues and decimal-value launch failures. (public cryoSPARC release notes v5.0)

### Motion / CTF / RBMC
- v4.4 introduced major RBMC improvements, empirical dose weights, and multi-class motion estimation. (public cryoSPARC release notes v4.4)
- v4.5 fixed Patch Motion rerun failure from missing empirical dose weights and freezes in motion/CTF jobs after abnormal child termination. (public cryoSPARC release notes v4.5)
- v5 added hot-pixel threshold to Patch Motion Correction and RBMC. (public cryoSPARC release notes v5.0)
- CTFFIND4 updated in v4.3; Gctf is legacy from v4.0 onward. (public cryoSPARC release notes v4.3, public cryoSPARC release notes v4.0)

### Refinement / masks
- v4.0 NU refinement gained optional Ewald sphere correction. (public cryoSPARC release notes v4.0)
- v4.4 made NU refinement faster and added batch-size/OOM-related behavior fixes. (public cryoSPARC release notes v4.4)
- v4.5 refinement jobs gained cFSC summary plots at every iteration. (public cryoSPARC release notes v4.5)
- v5 dynamic refinement mask changes mean mask advice must branch by version and parameter state. (public cryoSPARC release notes v5.0, `20_masks.md`)

### Classification / heterogeneity
- v4.1 introduced 3DFlex beta; later releases fixed multiple 3DFlex/3DVA issues. (public cryoSPARC release notes v4.1, public cryoSPARC release notes v4.3, public cryoSPARC release notes v4.5, public cryoSPARC release notes v4.6)
- v4.5 fixed 3D Classification class re-ordering failure when classes >12 and focus-mask plotting offset. (public cryoSPARC release notes v4.5)
- v5.0.1 fixed 3D Classification required-parameter validation after v5.0.0 upgrade. (public cryoSPARC release notes v5.0)
- v4.4 3DFlex Reconstruction supports CTF aberrations and lower-RAM particle access via SSD cache/project directories. (public cryoSPARC release notes v4.4)

### Storage / cache / data management
- v4.0 project locks changed attach/detach/delete failure modes. (public cryoSPARC release notes v4.0, `17_error_lookup.md`)
- v4.2 fixed SSD free-space infinite hang and cache timeout retries. (public cryoSPARC release notes v4.2)
- v4.4 introduced improved SSD cache experimentally; v4.5 enabled the new cache by default with distributed locking strategy; v4.6 improved cluster filesystem diagnostics; v5 added fallback for silent SSD copy failures. (public cryoSPARC release notes v4.4–public cryoSPARC release notes v5.0, `24_disk_and_storage.md`)
- v4.3 introduced Data Cleanup Tools and `cryosparcm compact`; v5 added more cleanup controls and per-result deletion endpoint. (public cryoSPARC release notes v4.3, public cryoSPARC release notes v5.0)

### Automation / API / CLI
- v5 CLI incompatibility is the main automation hazard. Branch commands by version. (public cryoSPARC release notes v5.0, `14_cli_admin.md`)
- cryosparc-tools v5 is described as backwards compatible, but tools/package version still matters for scripting failures. (public cryoSPARC release notes v5.0)
- Workflows/Blueprints arrive in v4.4 and expand templating automation, but Deep Picker restrictions and v5 CLI changes affect reusable workflows. (public cryoSPARC release notes v4.4, public cryoSPARC release notes v4.6, public cryoSPARC release notes v5.0)
- For Live automation, v5 uses updated Live CLI/session-management paths and profiles are not v4-backwards compatible. (public cryoSPARC release notes v5.0, `25_cryosparc_live.md`)

---

## Automation guardrails

Before running or generating scripts:

```text
if cryosparc_major >= 5:
    use v5 cryosparcm reference
    do not use v4 `cryosparcm cli` command forms without verification
    require OS/driver/GPU compatibility for admin recommendations
    treat Live profiles and performance benchmarks as v5-only/non-downgradeable
    account for dynamic refinement mask parameter
    do not create Deep Picker Train/Inference jobs
else:
    use v4 CLI/admin patterns
    do not assume v5 endpoints such as recover/delete_output_result_files exist
    do not assume dynamic refinement mask behavior exists
```

Concrete checks:
- **CLI scripts:** gate v5-only CLI endpoints (`recover`, updated worker connect/disconnect forms, `delete_output_result_files`) behind version detection.
- **Live scripts:** gate v5 Live auto-start/auto-pause/config-profile operations behind version detection; warn on downgrade.
- **Refinement templates:** include version/parameter check for dynamic refinement masks before applying static-mask recipes.
- **Picking workflows:** if v5, avoid new Deep Picker jobs; route to Topaz/current pickers.
- **Cache troubleshooting:** if version < v4.6 and cluster filesystem cache errors occur, consider update before deep filesystem surgery.
- **Upgrade handling:** for v5.0.0–v5.0.2 attach/detach validation failures, recommend patch update first.

---

## “If user is on version X, recommend…” quick actions

| User version | Default recommendation |
|---|---|
| v4.0.x | Use v4 UI/docs; beware early v4 Live/Topaz/SSH/libtiff issues. If debugging odd behavior already fixed later, update within v4 first. |
| v4.1.x | Good enough for early 3DFlex beta, but many 3DFlex/3DVA/Live fixes landed later. Update before serious 3DFlex troubleshooting. |
| v4.2.x | Has CUDA 11.8 support but earlier cache/Live fixes may matter. For SSD cache hangs or Live exposure discovery, update. |
| v4.3.x | Data cleanup/benchmarking available. For Topaz import, 3DFlex, Live, cache, or UI-scale issues, check later v4 fixes. |
| v4.4.x | Check driver 520.61.05+. Good for Workflows/RBMC/NU speedups; for cache/Live/2D/3D classification fixes, v4.5+ may help. |
| v4.5.x | Strong v4 baseline; if EER import, high-performance I/O, tree/card scale, or CentOS migration planning matters, check v4.6/v5. |
| v4.6.x | Last major v4 family in this corpus; warn that CentOS 7 is deprecated and v5 has hard OS/driver/GPU cliffs. |
| v5.0.0 | Patch update before diagnosing migration validation failures. Check 3D Classification required-parameter and project-attach validation fixes in v5.0.1/v5.0.3. |
| v5.0.1–v5.0.2 | Patch to v5.0.3+ if project attach/detach validation errors involve large ints, empty titles, or similar migration validation issues. |
| v5.0.3–v5.0.5 | Check latest v5 patch for Live auto-pause, SSD copy fallback, Topaz CV, and Live config fixes. |
| v5.0.6+ | Use v5 CLI and v5 docs; still verify installed release notes for site-specific patch level. |

---

## Sources consulted

This reference is original synthesized workflow guidance prepared from public cryoSPARC guide pages, public release notes, public forum reports, public tutorials/webinars, relevant papers, and public `cryosparc-tools` documentation/API material. Raw upstream documents, transcripts, forum posts, screenshots, and datasets are not bundled here. For authoritative and current details, consult the official cryoSPARC documentation, release notes, discussion forum, and upstream project documentation.
