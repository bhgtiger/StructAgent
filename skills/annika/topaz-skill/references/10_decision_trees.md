# 10 — Decision trees

## DT-0: Every Topaz request starts here (config gate)
```
Is there a fresh config report (site_config.local.md / probe output)?
├─ NO  → Offer the read-only probe (ask first). Block concrete commands.
│        Explain Topaz / templates only, labeled "NOT validated against local binary".
└─ YES → Is it stale? (TTL passed, env/GPU/path/version changed — ref 02)
         ├─ YES → Offer a cheap re-probe before concrete advice.
         └─ NO  → Read validation_status:
                  ├─ valid   → proceed (v1 concrete commands allowed if user gives paths)
                  ├─ partial → templates only; surface blocked_capabilities
                  └─ blocked → explain + remediation only
```

## DT-1: Install or not?
```
topaz.installed == true?
├─ YES → capture live `topaz --version`/`--help`; reconcile with ref 03; proceed.
└─ NO  → user wants to install?
         ├─ NO  → explain workflows from source; templates only.
         └─ YES → python in 3.8–3.13?
                  ├─ NO  → recommend dedicated conda/venv @3.10 FIRST.
                  └─ YES → propose exact conda/pip command + risks; REQUIRE confirmation.
                           Never auto-install.
```

## DT-2: Which device? (CUDA-or-CPU only — no MPS)
```
NVIDIA GPU present (nvidia-smi) AND torch CUDA build?
├─ YES → GPU: -d 0 (or >=0). Good for training-heavy work.
└─ NO  → CPU only.  Apple Silicon? -> still CPU (no MPS; M-GPU unused).
         Use -d -1 to avoid the CudaWarning.
         Heavy training? -> recommend NVIDIA/HPC/cloud.
```

## DT-3: Train a model or use a bundled one?
```
Do you have labeled particles AND a non-standard particle/poor pretrained recall?
├─ YES → topaz train (resnet8/16; --pretrained warm-start) → use the saved model.
└─ NO  → use bundled resnet16 directly in `topaz extract -m resnet16`.
```

## DT-4: Picking pipeline routing
```
Goal?
├─ pick particles      → preprocess → (train?) → extract → convert(scale)→ STAR
├─ denoise micrographs → topaz denoise (-d -1 on CPU)
├─ denoise tomograms   → topaz denoise3d
├─ convert coords      → topaz convert / split / particle_stack
└─ evaluate a model    → topaz precision_recall_curve
```

## DT-5: Private data / execution request
```
Request involves running a job, writing files, or moving/uploading micrographs?
├─ upload/move/delete private data → refuse by default; ask explicit confirmation; keep local.
├─ run a Topaz job                 → v0–v1: do NOT run; explain + template. v2+: fixtures + confirm.
└─ write a file (e.g. probe output)→ allowed only for the intended output path, after asking.
```
