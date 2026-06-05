# Lessons (running log)

## 2026-06-05 — v0 build, grounded on Topaz v0.3.20 @ 58fe5237
- **Device/MPS settled by source, not inference.** `topaz/cuda.py set_device()` consults
  only `torch.cuda`; zero `mps`/`backends.mps` references in `topaz/`. → `topaz_mps_supported=false`.
  Apple Silicon = **CPU-only** for Topaz. This is the single most important fact the skill
  must not get wrong (audit A P0-1). Probe encodes it as static `SOURCE_EVIDENCE`.
- **`--device` defaults differ per command** (train/extract/denoise=0, normalize=-1,
  denoise3d=-2). On CPU machines recommend `-d -1` to avoid the `CudaWarning` fallback.
- **Pretrained models are bundled** in the wheel (`topaz/pretrained/…`, loaded
  `map_location='cpu'`) — no download for the standard detectors/denoisers.
- **Python range 3.8–3.13.** Dev machine runs 3.14.5 → outside range; probe flags it.
  Any install must go into a dedicated conda/venv at ≤3.13.
- **v0 boundary reconciled** (audit A P0-2): v0 = placeholder templates only; v1 = concrete
  paths; v2 = fixtures; v3 = real jobs. SKILL.md + ref 00 state this consistently.
- **PyPI name is `topaz-em`**, import is `topaz`, CLI is `topaz`, license **GPLv3**.

## Open decisions (carry forward)
- Installed skill folder name: `topaz-skill` (frontmatter `name`) vs dev folder
  `topaz_skill`. Confirm with `openclaw skills check` before install.
- v1 first slice: concrete-command generation only, or also tiny CPU fixture smoke tests?
- Should the skill ever *install* Topaz, or only detect/report existing installs?

## To verify when Topaz is actually installed
- Capture live `topaz --version` / `topaz <cmd> --help`; reconcile with ref 03.
- Confirm exact `extract`/`train` output filenames and coordinate column order on a fixture.
