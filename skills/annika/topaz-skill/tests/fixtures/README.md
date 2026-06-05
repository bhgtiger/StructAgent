# Fixtures

**Status (v0): no binary fixtures included.** v0 is explanation + placeholder templates
only, so no micrographs/coordinates are shipped or required. This keeps the skill free of
large/private data and avoids any execution.

## Why empty now
- No Topaz execution happens in v0–v1, so fixtures aren't yet needed as run inputs.
- Real cryo-EM micrographs are large and often **private** — never vendor user data here.

## What to add for v2 (execution) — sourced, tiny, public only
When execution is enabled, add **tiny, public, non-sensitive** fixtures and oracles drawn
from the Topaz repo itself (pinned v0.3.20 @ 58fe5237):
- Synthetic/tiny inputs used by `test/test_commands_simple.py`, `test/test_example.py`,
  and `test/topaz/test_mrc.py` / `test_predict.py` / `test_denoise.py`.
- A 2–3 line coordinate table (`image_name<TAB>x_coord<TAB>y_coord`) + a small MRC for a
  `convert`/`denoise -d -1` smoke test on CPU.
- Record provenance (repo path + commit) and expected output for each fixture.

## Hard rules
- No private/unpublished micrographs. No data moved out of the user's project.
- Fixtures must be runnable on **CPU** (`-d -1`) since the dev machine is Apple-Silicon (CPU-only for Topaz).
- Keep each fixture < a few MB; cite its source.
