# Validation and troubleshooting

## Validation ladder

1. Validate the skill package and config.
2. Capture the configured launcher `--help` and runtime version.
3. Confirm model weights/parameter paths and container/runtime identity.
4. Confirm GPU/JAX visibility on the actual compute node, not only a login node.
5. Run the bundled public, disposable, network-free GCN4-p1 fixture with `single_sequence` after explicit approval.
6. Record exact model/MSA mode, GPU, elapsed time, output inventory, and score keys.

A fixture validates only its recorded scope. Do not generalize one AlphaFold2-Multimer-v3/H100 result to every model type or GPU. Do not assert exact coordinates, scores, or wall time across hardware; use the structural/range contract in `../examples/smoke-expectations.json`.

## Common failures

- Launcher absent/help fails: treat config as `blocked`; inspect wrapper/container paths before changing anything.
- Version or receipt mismatch: mark `stale`; capture new help and revalidate before generating commands.
- JAX sees CPU on a GPU node: inspect scheduler allocation, container GPU exposure, driver/JAX compatibility, and launcher GPU flags.
- Params download or lookup: confirm the configured data/cache path and weight presence; do not silently download gigabytes.
- OOM/compile failure: record sequence length, model count, recycle/seed/ensemble settings, GPU memory, JAX/CUDA versions, and compile mode before changing one factor at a time.
- MSA timeout/rate limit: do not loop aggressively. Preserve error text, respect service fair use, and offer an approved retry/local route.
- Existing output: stop. Version the directory or obtain explicit replacement instructions.

## Required package checks

```text
python3 scripts/validate_skill.py <skill-folder>
python3 scripts/colabfold_env_probe.py --self-test
python3 scripts/summarize_colabfold_output.py --self-test
```

Then run the host probe/config validator and separate Claude trigger tests from runtime fixture tests. Neither a passing language-model eval nor a passing GPU fixture substitutes for the other.