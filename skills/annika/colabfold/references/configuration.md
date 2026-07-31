# Workstation configuration

## Location and privacy

Resolve the config in this order:

1. `COLABFOLD_SKILL_CONFIG`;
2. `${XDG_CONFIG_HOME:-~/.config}/colabfold-skill/site-config.json`.

Keep it outside the skill so copying or archiving the portable package cannot leak workstation paths. Protect it as a private file; the probe writes mode `0600`.

## Generate a config

The default probe inspects files, PATH, host identity, scheduler availability, parameter files, and visible GPUs without running ColabFold. `--live-help` invokes the launcher with `--help`; it performs no prediction but can start a container and can initialize cache files such as a Matplotlib font cache. Keep it opt-in. `--evidence-manifest` may import a structured prior validation receipt; the probe verifies version, launcher, image path, and recorded SHA rather than trusting `COMPLETE` alone.

```text
python3 scripts/colabfold_env_probe.py \
  --launcher /path/to/colabfold_batch \
  --runtime-version 1.6.2 \
  --container-image /path/to/colabfold.sif \
  --container-sha256 <64-hex> \
  --params-dir /path/to/params \
  --scheduler slurm --gpu-partition <partition> \
  --host-pattern '*.cluster.example' \
  --msa-policy deny_remote \
  --live-help \
  --output ~/.config/colabfold-skill/site-config.json
```

Use `--hash-container` only when hashing a potentially multi-gigabyte image is intended. The output parent is created only because `--output` explicitly requests a write. Existing configs are not replaced unless `--force` is passed.

## State machine

- `ready`: launcher exists, expected/runtime versions agree, and a matching structured CPU/GPU fixture receipt is complete.
- `probed`: launcher/environment facts exist but fixture/GPU evidence is incomplete.
- `blocked`: launcher is missing/unusable or an explicitly requested live hash fails/mismatches.
- `stale`: runtime version, host pattern, launcher/image identity, or receipt no longer matches.
- `unknown`: evidence is insufficient.

Re-probe after a runtime/container/weight change, scheduler change, or host/profile mismatch. A timestamp alone cannot prove freshness.

## Important fields

- `host`: hostname, OS, architecture, allowed hostname glob patterns.
- `runtime`: launcher, runtime/expected version, help state/hash, container path and expected/observed hash.
- `paths`: parameter inventory, cache, and default result root.
- `scheduler`: local/slurm, submit command, account, partition/GRES, CPU/memory/time/scratch defaults.
- `compute`: GPU visibility/details observed during the probe.
- `msa`: `deny_remote`, `per_job_approval`, or `local_only`; endpoint and local-database state.
- `validation`: state, reasons, evidence path, receipt consistency, and exact fixture model/MSA/GPU scope.

Never put API credentials or private sequence content in this config.