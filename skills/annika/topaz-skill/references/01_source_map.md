# 01 — Source map (how this skill is grounded)

## Pin
- Repo: `https://github.com/tbepler/topaz`
- Commit: `58fe52370f4accb8215525df2ea8f2c7ee6d340a`
- Tag/branch: **v0.3.20** (= `master` HEAD), `git describe --tags` → `v0.3.20`
- Fetched: 2026-06-05 (shallow clone)
- License: **GPLv3**; PyPI dist `topaz-em`; import `topaz`; entry point `topaz.main:main`
- Python supported: `>=3.8,<=3.13` [sourced 0.3.20 @ 58fe5237: setup.py:45] (README: 3.8–3.12)

Full raw capture lives in the **project** (not shipped in the installed skill):
`references/source/SNAPSHOT.md`, `references/source/source_inventory.md`,
`references/web/source_map.md`, `references/cli/…`, `references/data_model/…`,
and the working clone `references/source/topaz_clone/`.

## Validated against installed binary (trust-ladder #1 evidence)
This is now the **top rung** of the trust ladder, not pending. Topaz **0.3.20** was
installed and validated end-to-end on Linux + NVIDIA on **2026-06-06**:
- **Version**: `_version.txt` reports **`0.3.20`** (matches the pin) — captured during
  validation (project-side, not shipped).
- **Live `--help` per subcommand**: captured
  as `topaz.<cmd>.help.txt` (e.g. `topaz.extract.help.txt`, `topaz.train.help.txt`,
  `topaz.help.txt`). **Every CLI flag / default / subcommand / format claim in refs
  02–09 must match these files exactly.** Label such facts
  `[validated topaz 0.3.20 — captured: topaz.<cmd>.help.txt]`.
- **GPU smoke**: real `preprocess` / `convert` / `denoise` / `train` / `extract` jobs
  ran on GPU (a Linux + NVIDIA GPU host, torch 2.9.1+cu128, cuda=True). Label output-layout / runtime-behavior
  facts proven there `[smoke]`.
- **Probe verdict**: `scripts/topaz_env_probe.py --check-torch` reported
  `validation_status = valid`, `cuda_usable_here = True`, with
  `topaz_mps_supported = False` (see the probe report).
  The probe stays **generic / per-machine** — it computes support per host and must
  never hardcode any one host's verdict.

Source-only facts (no live binary needed) are labeled `[sourced 0.3.20 @ 58fe5237: <path>]`;
method claims `[paper]`.

## Primary sources behind each skill reference
| Skill ref | Grounded in (pinned source) | Validated against (captured live help / smoke) |
|---|---|---|
| 02 config/device | `topaz/cuda.py`, `topaz/torch.py`, `topaz/extract.py`, `topaz/denoise.py`, `topaz/training.py`, README "Prerequisites", per-command `--device` | per-subcommand `--device` defaults in `topaz.<cmd>.help.txt`; cuda=True `[smoke]` |
| 03 CLI | `topaz/main.py`, `topaz/commands/*.py` (`name`/`help`/`add_arguments`) | `topaz.help.txt` (command groups) + `topaz.<cmd>.help.txt` (flags/defaults) |
| 04 formats | `topaz/mrc.py`, `topaz/commands/convert.py`, `topaz/training.py`, README "File formats" | `topaz.convert.help.txt`, `topaz.split.help.txt`; `[smoke]` output columns/layout |
| 05 workflows | README usage, `docs/source/tutorial.md`, `docs/source/commands/*`, `tutorial/*.ipynb` | `[smoke]` preprocess→convert→denoise→train→extract chain |
| 08 validation | Nat Methods 2019 paper, denoising preprint, `test/` | `[paper]` method claims; smoke loaded pretrained `unet_L2_v0.2.2.sav` on GPU |
| 09 troubleshooting | `topaz/cuda.py` CudaWarning, install docs, requirements | `[smoke]` gotchas (e.g. `--save-prefix DIR` must pre-exist; cu130-vs-cu12x torch) |

## External pointers (secondary to pinned source)
- Docs site: https://topaz-em.readthedocs.io/en/latest/
- Discussions: https://github.com/tbepler/topaz/discussions
- Method paper: https://doi.org/10.1038/s41592-019-0575-8
- Denoising preprint: https://doi.org/10.1101/838920
- Conda channel: https://anaconda.org/tbepler/topaz
- PyTorch install: https://pytorch.org/get-started/locally/

## Re-grounding procedure (when pin changes)
1. Re-clone at the new tag; update `references/source/SNAPSHOT.md`.
2. Update `scripts/topaz_env_probe.py` `SOURCE_EVIDENCE` (commit/tag + device evidence).
3. Re-verify device dispatch (`grep -i mps topaz/`), `--device` defaults, CLI help.
   - At **0.3.20** the device defaults are validated against live help, with the evidence
     basis noted per command: `train` and `denoise` print `(default: 0)`; `segment` prints
     `(default: GPU if available)`; `extract` prints **no** numeric default (its value is
     GPU-if-available / `0` per source + the smoke run, not from the help text);
     `normalize = -1`, `preprocess = -1`, `denoise3d = -2 (multi-GPU)`
     [validated topaz 0.3.20 — captured: topaz.train.help.txt, topaz.denoise.help.txt,
     topaz.segment.help.txt, topaz.normalize.help.txt, topaz.preprocess.help.txt,
     topaz.denoise3d.help.txt; extract default per source + smoke, see ref 02/03]. The `grep -i mps topaz/` check
     confirms **zero MPS code paths** in the Python source at 58fe5237 (matches
     `topaz_mps_supported = False` per the probe) → on Apple Silicon Topaz is
     CPU-only; pass `-d -1` [sourced 0.3.20 @ 58fe5237: topaz/]. Re-capture live help and
     update these values if the pin changes.
4. Update skill refs 02/03/04 and this file, and re-capture `topaz.<cmd>.help.txt` +
   re-run the GPU smoke. Bump SKILL.md `metadata.topaz_pin` and `metadata.grounded_on`.
