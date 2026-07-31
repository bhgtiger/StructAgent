# Site configuration

## Location and privacy

Resolve the config in this order:

1. `$CRYOATOM_SKILL_CONFIG`
2. `${XDG_CONFIG_HOME:-~/.config}/cryoatom-skill/site-config.json`

Keep it **outside** this package so copying or archiving the package cannot leak
a workstation's paths, account codes, or partitions. The probe writes mode
`0600`. `scripts/cryoatom_launcher.sh` and `scripts/render_job_template.py`
resolve the config the same way, so one file configures the whole package.

## Generate a config

The default probe is read-only: it inspects host identity, PATH, container
runtimes, the scheduler, visible GPUs, the launcher, and the weight cache. It
never runs a prediction.

```bash
python3 scripts/cryoatom_env_probe.py \
  --profile my-cluster \
  --route container \
  --image /path/to/cryoatom.sif \
  --launcher /path/to/bin/cryoatom \
  --weights-cache /path/to/cryoatom_cache \
  --scheduler auto \
  --account <ACCOUNT> \
  --gpu-partition <GPU_PARTITION> \
  --scratch-root /path/to/scratch \
  --host-pattern 'login*.example.org' --host-pattern 'gcn*' \
  --live-version \
  --output ~/.config/cryoatom-skill/site-config.json
```

Useful additions:

| Flag | Effect |
|---|---|
| `--live-version` | Runs `<launcher> --version`. Safe anywhere: it never opens a checkpoint. Without it, `version.observed` stays `null` and the state cannot reach `ready`. |
| `--hash-image` | SHA-256 of the image. Multi-GiB read — opt in deliberately. |
| `--image-sha256 <hex>` | Record the expected image hash so drift becomes detectable. |
| `--verify-weights sha256` | Full weight re-hash during the probe (~5.1 GiB read). Default is presence + size. |
| `--no-mount-hostfs` | Record that the container must be started with `--no-mount hostfs` (see below). |
| `--extra-bind /gpfs` | A site filesystem the container must see. Repeatable. |
| `--record-fixture …` | Record a passed public-fixture run; required to reach `ready`. |
| `--force` | Overwrite an existing config. Without it, an existing file is never replaced. |

Validate an existing config against the machine you are on:

```bash
python3 scripts/cryoatom_env_probe.py --validate-config ~/.config/cryoatom-skill/site-config.json
```

`templates/site-config.example.json` is the annotated skeleton for manual
editing. Every value in it is a placeholder.

## State machine

Computed by the probe, not asserted by hand:

- **`ready`** — launcher exists and is executable; `version.observed` equals
  `version.expected`; all six weight files present and matching their pin (or
  their expected sizes when no pin exists); a GPU meeting the ≥14 GiB VRAM
  requirement is visible **or** the scheduler is configured to reach one; and
  `validation.fixture_validated` is true for this install.
- **`probed`** — facts collected but a gate is missing: no live version, no
  fixture receipt, or no GPU evidence yet.
- **`blocked`** — a hard requirement is absent or unusable: no launcher, no
  image, no container runtime for the container route, no Linux, no NVIDIA path
  at all, or an explicitly requested hash check failed.
- **`stale`** — the config no longer describes this machine: hostname matches no
  pattern, observed version differs from expected, image hash differs from the
  recorded one, or weights differ from the pin.
- **`unknown`** — no config, unreadable config, or unsupported schema version.

A login node with no visible GPU but a configured GPU route is **not** blocked —
it is a normal submit host. "Configured GPU route" means `scheduler.gpu_partition`
is set, or a non-local scheduler has a `scheduler.gpu_flag` (for sites that select
GPUs by generic resource rather than by partition).

A fixture receipt is evidence that a reachable GPU ran the job; it does **not**
excuse a host whose only visible GPUs are under the 14 GiB floor and which has no
queue to reach a bigger one. That combination stays `blocked`.

## Schema, field by field

| Group | Field | Meaning |
|---|---|---|
| `host` | `hostname`, `patterns`, `os`, `os_release`, `kernel`, `architecture` | Identity, plus the hostname globs this config is allowed to describe. The probe defaults `patterns` to this host **and its domain** (`*.dom.ain`), so a config written on a login node still covers the compute nodes; override with `--host-pattern` |
| `install` | `route` | `container` \| `native` \| `module` \| `preinstalled` |
| | `container_runtime`, `container_runtime_version` | `apptainer` \| `singularity` \| `docker` \| `podman` |
| | `image_path` | **apptainer/singularity:** a file path. **docker/podman:** an image reference such as `cryoatom:2.1.1` — resolved from the image store, never stat'ed |
| | `image_sha256`, `image_observed_sha256` | Image identity and drift detection |
| | `no_mount_hostfs` | Start the container with `--no-mount hostfs` (Apptainer/Singularity only) |
| | `extra_binds` | Site filesystems that must be visible inside the container |
| | `launcher` | Absolute path to the wrapper the user actually calls |
| | `in_image_binary`, `in_image_checkpoint_dir` | Where the entry point and the checkpoint bind target live inside the image |
| | `conda_env_prefix` | Native route: the launcher runs `<prefix>/bin/cryoatom` |
| | `module_load` | Module route: the command the launcher evaluates before resolving `cryoatom` on PATH (it refuses to resolve back to itself) |
| `version` | `expected`, `observed`, `source_commit`, `source_tree`, `checked_at` | The pin and what was actually seen |
| `weights` | `cache_root`, `pin_file`, `files`, `complete`, `verified_mode` | The external weight cache and its verification state |
| `compute` | `gpu_visible`, `gpus`, `min_vram_gib_required`, `meets_vram_requirement` | GPUs seen at probe time |
| `scheduler` | `type`, `submit_command`, `account`, `gpu_partition`, `build_partition`, `gpu_flag`, `cpus_per_task`, `memory_gb`, `default_time`, `scratch_root`, `extra_directives` | Enough to render a real job script |
| | `detected_from`, `gpu_flag_confirmed` | How the scheduler was identified, and whether its GPU syntax was actually confirmed. A `qsub` on PATH may be PBS Pro, OpenPBS, Torque, or SGE — the recorded flag is a guess until you confirm it |
| `paths` | `results_root`, `fixture_dir`, `log_dir`, `build_tmp_root` | Where outputs, fixtures, logs, and build sandboxes go |
| `validation` | `state`, `reasons`, `fixture_validated`, `fixture_job`, `fixture_elapsed_s`, `validated_gpu`, `validated_at`, `evidence` | The verdict and why |

## Why `no_mount_hostfs` exists

Some sites configure the container runtime to overlay the host filesystem into
the container. When that happens, the host's `/opt` shadows the image's `/opt`,
so `/opt/conda/envs/CryoAtom2/bin/cryoatom` disappears and the launcher fails
with "no such file or directory" even though the image is intact. The fix is to
start the container with `--no-mount hostfs`.

Detect it before assuming it:

```bash
apptainer exec <image> ls /opt/conda/envs/CryoAtom2/bin/cryoatom      # fails if shadowed
apptainer exec --no-mount hostfs <image> ls /opt/conda/envs/CryoAtom2/bin/cryoatom   # succeeds
```

`--no-mount hostfs` also drops the automatic bind of everything except `$HOME`
and `$PWD` — which is why `install.extra_binds` must then list every site
filesystem holding maps, sequences, or output directories.

## Re-validate vs. regenerate

`--validate-config` is **read-only**: it re-checks the launcher, the container
runtime, the weights, and the GPUs on the machine you are on, recomputes the
state, and prints it without touching the file. Run it freely.

Regenerating is a different action: the probe builds a config from the flags you
pass and **does not merge** with what is already there, so pass the full flag set
(and `--force`) every time. A short command produces a thin config, not an
updated one. An existing file is never overwritten without `--force`.

## Re-probe when

- The image is rebuilt or replaced (its SHA-256 changes by design).
- Weights are re-staged, moved, or re-pinned.
- The scheduler, account, or partition changes.
- The host changes, or the config's hostname patterns stop matching.
- The launcher or conda environment is edited.

## Never put in the config

API credentials, sequence content, map data, or anything the user has not agreed
to write to disk. The config records *where things are*, not *what they contain*.
