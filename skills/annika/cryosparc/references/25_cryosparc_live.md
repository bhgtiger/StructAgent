# Topic 25 — cryoSPARC Live

## Scope
How to use cryoSPARC Live effectively during acquisition or immediate post-collection triage: session setup, preprocessing, picker transitions, streaming jobs, export/handoff, and common failure modes.

## What Live is best for
CryoSPARC Live is best treated as a real-time decision layer:
- check whether data collection is working
- identify bad exposures early
- verify picking behavior
- watch 2D classes / first 3D map emerge
- decide whether to keep collecting, change conditions, or stop

It is not the end of the pipeline. The normal handoff is:
Live for rapid feedback -> main cryoSPARC jobs for final refinement and deeper branching.

## Standard operating model
1. Start the session as early as possible during collection.
2. Configure raw-data paths carefully.
3. Run preprocessing first: motion correction + CTF.
4. Start with blob picking.
5. As soon as blob-picked 2D classes are good enough, generate templates and switch to template picking.
6. Start streaming 2D classification early.
7. Start ab initio / streaming refinement once enough particles accumulate.
8. Export accepted exposures / particles into the main project for downstream processing.

## Setup heuristics
### Session organization
Keep Live sessions in clean projects. Later export, sharing, and handoff are project-scoped, so messy project organization makes downstream work harder.

### Lane / GPU planning
Use one consistent lane when possible for simplicity. Historically, Live had several lane/worker quirks, but modern versions are more flexible.

General advice:
- small setups: one lane for everything is fine
- if throughput lags, increase preprocessing workers
- if 2D/3D jobs starve preprocessing, re-balance GPU allocation or split work more explicitly

### File watching
A large fraction of Live failures are actually file-discovery problems, not cryo-EM problems.
Check:
- correct wildcard
- correct recursion setting
- correct movie type vs already motion-corrected files
- timestamps not in the future
- symlink sanity
- multiple simultaneous sessions not contending for the same incoming data in unexpected ways

## Preprocessing guidance
### Motion / CTF first
Live is most valuable when motion correction and CTF are stable and quick. Even if you do not intend to trust Live particle outputs, on-the-fly motion/CTF and exposure curation are already worth it.

### Fourier crop
Use Fourier crop deliberately. The walkthrough example uses a cropped box that preserves enough signal for fast screening without pretending to be the final-resolution workflow.

### Denoiser logic
When using micrograph denoising in the broader cryoSPARC workflow, use denoised micrographs for picking only, but extract from original micrographs.

## Picking workflow
### Start with blob picking
Blob picking is the robust default for bootstrapping a Live session.
Use it to:
- verify particle size assumptions
- judge contamination / junk rate
- get first-pass 2D classes for template generation

### Switch to template picking once justified
Do not activate templates blindly. First verify:
- templates are genuinely representative
- particle diameter is correct
- test adjustments look sensible on a single exposure

Then activate for all or future exposures depending on whether you want reprocessing.

### Thresholding
High-value particle thresholds in Live:
- NCC
- power
- edge distance

These thresholds are for triage, not perfection. Over-tight thresholds too early can silently bias the session.

## Reprocessing model
One of Live’s biggest strengths is selective reprocessing.
If you change a parameter, Live can rerun only the required downstream stages rather than forcing a full restart.

Practical use:
- adjust picker thresholds
- regenerate templates
- re-run affected downstream steps
- keep the session intact instead of nuking it

## Streaming jobs
### Streaming 2D classification
Start this early. It is the fastest sanity check for:
- whether picks are real
- whether orientation coverage is terrible
- whether junk is dominating
- whether the denoiser / picker helped or hurt

### Ab initio / streaming refinement
Useful as first-cut structural feedback, but treat early maps cautiously. They are decision aids, not final products.

A good Live habit:
- use streaming outputs to decide whether the dataset is worth continuing
- do final branching and best-map production later in normal cryoSPARC jobs

## Handoff to main cryoSPARC
Recommended default:
- export accepted exposures or particles
- continue in standard jobs for the serious branch
- use NU refinement / local refinement / heterogeneity workflows outside Live

Live is the screening and control room; the main interface is the production bench.

## Common failure modes and fixes
### 1. Live does not see new exposures
Check in this order:
- wrong path / wildcard / recursion
- timestamps incorrect or in the future
- broken or looping symlinks
- stale session state -> restart session / create new exposure group
- command_rtp / service issue -> restart relevant services if administratively allowed
- known version bug -> update / patch if your version matches a known fixed bug

Important version notes:
- v4.2 and v4.3 both include fixes for Live stopping discovery of new exposures

### 2. Live sees files in normal cryoSPARC import, but not in Live
Usually means file-watching / session-state logic rather than path permissions alone. Known causes include timestamp issues, session state needing reset, or Live-specific bugs.

### 3. Particle picking set to zero breaks downstream behavior
Historical gotcha: setting thresholds so aggressively that zero picks are produced can break expected downstream displays / behavior in Live. Better to let picking succeed and then threshold appropriately rather than forcing pathological zero-pick logic.

### 4. UI plots freeze or behave strangely
Especially around ice-thickness / threshold plots, historical bugs included NaN-derived failures and browser-side slider crashes. If this appears:
- inspect whether a pathological exposure created NaN or absurd values
- check release notes for your version
- be cautious about interpreting extreme outliers as real

### 5. Multiple preprocessing workers stop helping
Older versions had worker / lane / file-system edge cases. If workers idle unexpectedly:
- check whether the queue is genuinely accumulating
- inspect file-system behavior
- prefer stable filesystems over fragile mounts
- note that newer versions improved worker handling substantially

### 6. Template picker or export oddities
Several Live issues were version-specific and later fixed, including:
- one-template selection failures
- export failures without gain refs
- odd behavior loading source 2D classes

So advisor mode should always be version-aware before giving strong operational advice.

## Version-aware highlights
### Major behavior changes / fixes
- v4.0: Live integrated into the main interface; free-form threshold input improved; main Live UI modernization
- v4.1: fixed NCC slider zero behavior, NaN ice-thickness bug, failed-exposure double counting
- v4.2: fixed “Live stops finding new exposures” and some gain-reference handling issues
- v4.3: Live auto-pauses on instance restart; more robust session behavior; compaction/restoration introduced
- v4.4: more flexible custom Streaming job parameters; multiple worker and stability fixes; lower DB/storage overhead; isolated file-watch errors between sessions
- v4.5: arbitrary number of preprocessing GPU workers; better export metadata; large-session scrolling fixes
- v4.6: Live data-management tab deprecated in favor of compaction/restoration workflows
- v5.0: auto-start / auto-pause improvements, multiple workers per GPU, session cloning, better export / template-source robustness, faster low-mag patch motion

## Advisor defaults
If a user asks “how should I run Live?”
1. start early
2. verify file discovery before touching advanced settings
3. run motion/CTF immediately
4. begin with blob picking
5. switch to template picking only after good 2D classes exist
6. start streaming 2D classification early
7. use thresholds conservatively at first
8. export accepted data and move to standard cryoSPARC for the serious refinement branch

## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

- `videos/notes/07_cryosparc_live_walkthrough.notes.md`
- `docs/forum_threads/digests/forum_cryosparc-live.md`
- `reference/release_notes/markdown/v4.0.md`
- `reference/release_notes/markdown/v4.1.md`
- `reference/release_notes/markdown/v4.2.md`
- `reference/release_notes/markdown/v4.3.md`
- `reference/release_notes/markdown/v4.4.md`
- `reference/release_notes/markdown/v4.5.md`
- `reference/release_notes/markdown/v4.6.md`
- `reference/release_notes/markdown/v5.0.md`
