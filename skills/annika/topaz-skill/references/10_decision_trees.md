# 10 — Decision trees

These trees are GENERIC and PER-MACHINE. Every verdict (`valid` / `ready` /
Apple-Silicon-CPU / uninstalled) comes from the read-only probe
(`scripts/topaz_env_probe.py`, ref 02) run on the current host — never from a
hardcoded host. Topaz 0.3.20 is INSTALLED and VALIDATED end-to-end on
Linux+NVIDIA (captured live help as `topaz.<cmd>.help.txt`; GPU
smoke runs), so on a probe-`valid`
host the skill emits concrete commands with the user's real paths and may run
real jobs after explicit confirmation.

## DT-0: Every Topaz request starts here (config gate)
```
Is there a fresh config report (site_config.local.md / probe output)?
├─ NO  → Offer the read-only probe (ask first). Until you have a verdict, do not
│        assume a device or run anything; you may still explain workflows using
│        the VALIDATED 0.3.20 facts (refs 03–09).
└─ YES → Is it stale? (TTL passed, env/GPU/path/version changed — ref 02)
         ├─ YES → Offer a cheap re-probe before concrete advice.
         └─ NO  → Read validation_status:
                  ├─ valid   → emit concrete commands with the user's real paths;
                  │            AND (after explicit user confirmation) run jobs,
                  │            with output safeguards (ref DT-5).
                  ├─ partial → emit concrete commands for the supported
                  │            capabilities; surface blocked_capabilities and
                  │            route blocked ones (e.g. heavy training) to DT-2.
                  ├─ blocked → explain + remediation only.
                  └─ uninstalled → offer install (confirmed; DT-1). You can still
                                   explain workflows from validated 0.3.20 facts.
```
The "valid" leaf was proven on a Linux + NVIDIA GPU host: the probe reported
`validation_status = valid, cuda_usable_here = True, blocked_capabilities none`,
and a full preprocess → train → extract chain ran on GPU [smoke].

## DT-1: Install or not?
```
topaz.installed == true?
├─ YES → capture live `topaz --version` / `--help` (matches captured
│        topaz.help.txt; _version.txt = 0.3.20); proceed with the VALIDATED facts.
└─ NO  → user wants to install on THIS host?
         ├─ NO  → explain workflows from the VALIDATED 0.3.20 facts (refs 03–09).
         │        These are confirmed against captured help, not unvalidated
         │        templates. Just don't emit run-on-real-data commands until the
         │        host is installed + probed.
         └─ YES → python in 3.8–3.13?  ([sourced 0.3.20 @ 58fe5237: setup.py:45,
                  python_requires '>=3.8,<=3.13'; README 3.8–3.12 tested])
                  ├─ NO  → recommend dedicated conda/venv @3.10 FIRST.
                  └─ YES → propose exact conda/pip command + risks; REQUIRE
                           confirmation. Never auto-install. Pin a cu12x torch
                           build (e.g. torch==2.9.1+cu128) — default PyPI torch is
                           CUDA-13 (cu130) and gives cuda=False on a CUDA-12 driver
                           [smoke]. See ref 03 for commands.
```

## DT-2: Which device? (CUDA-or-CPU only — no MPS)
```
Probe outcome for this host:
NVIDIA GPU present (nvidia-smi) AND torch CUDA build (cuda_usable_here == true)?
├─ YES → GPU: -d 0 (or >=0). Good for training-heavy work.
│        (Validated: probe cuda_usable_here = True; jobs ran on -d 0 [smoke].)
└─ NO  → CPU only.  If the probe reports Apple Silicon / no NVIDIA GPU, Topaz runs
         CPU-only; pass -d -1. Topaz has no MPS code path, so the Apple-Silicon GPU
         is unused [sourced 0.3.20 @ 58fe5237: zero mps refs in topaz/; probe
         topaz_mps_supported = False].
         Heavy training on CPU-only? -> recommend NVIDIA/HPC/cloud.
```
Note: per-subcommand device defaults differ — `train`/`extract`/`denoise`/
`segment` default `-d 0` (GPU if present), `preprocess`/`normalize` default
`-d -1`, `denoise3d` defaults `-d -2` (multi-GPU). See refs 05–08
[validated topaz 0.3.20 — captured: topaz.<cmd>.help.txt].

## DT-3: Train a model or use a bundled one?
```
Do you have labeled particles AND a non-standard particle / poor pretrained recall?
├─ YES → topaz train (-m default resnet8; resnet16 also available; --pretrained
│        warm-start) → use the saved <save-prefix>_epoch{N}.sav model.
└─ NO  → use the bundled resnet16 directly: `topaz extract` with default
         -m resnet16 (set -m none only if inputs are already segmented).
```
[validated topaz 0.3.20 — captured: topaz.train.help.txt (`-m/--model` default
resnet8), topaz.extract.help.txt (`-m/--model` default resnet16; `-m none` for
pre-segmented inputs)]. Checkpoint naming `<save-prefix>_epoch{N}.sav`
(e.g. model/topaz_smoke_epoch1.sav) and `--pretrained` warm-start [smoke].

## DT-4: Picking pipeline routing
```
Goal?
├─ pick particles      → preprocess → (train?) → extract → convert(scale) → STAR
├─ denoise micrographs → topaz denoise (-d 0 on GPU; -d -1 on CPU)
├─ denoise tomograms   → topaz denoise3d
├─ convert coords      → topaz convert / split / particle_stack
└─ evaluate a model    → topaz precision_recall_curve
```
[validated topaz 0.3.20 — captured: topaz.help.txt command groups (Particle
picking {train, segment, extract, precision_recall_curve}; Image processing
{downsample, normalize, preprocess, denoise, denoise3d}; File utilities {convert,
split, particle_stack, train_test_split})]. `topaz convert --to star -o
coords.star coords.txt` confirmed working [smoke]. For evaluation,
`precision_recall_curve` requires `--predicted`, `--targets`, and
`-r/--assignment-radius` [validated topaz 0.3.20 — captured:
topaz.precision_recall_curve.help.txt].

## DT-5: Private data / execution request
```
Request involves running a job, writing files, or moving/uploading micrographs?
├─ upload/move/delete private data → refuse by default; keep data local; only on
│                                    explicit user confirmation.
├─ run a Topaz job                 → on a probe-valid host, run AFTER explicit
│                                    user confirmation, with output safeguards
│                                    (write to a named output dir/path the user
│                                    agreed to; don't overwrite existing data).
│                                    Never run without confirmation. On a non-valid
│                                    host, emit the concrete command but don't run.
└─ write a file (e.g. probe output)→ allowed only for the intended output path,
                                      after asking.
```
Output-path safeguard / GOTCHA: `topaz train --save-prefix DIR/...` requires DIR
to ALREADY EXIST — Topaz does NOT create the parent directory; create it first
(see ref 09 troubleshooting) [smoke]. Extract output columns are
`image_name  x_coord  y_coord  score` [smoke].
