# Operations and troubleshooting

## Readiness check — run before any claim of readiness

```bash
cryoatom --version                                                  # expect: CryoAtom 2.1.1
python3 scripts/check_cryoatom_weights.py --cache <CACHE> --mode size
python3 scripts/cryoatom_env_probe.py --validate-config <CONFIG>
```

`--version` and `build -h` never open a checkpoint, so they work on a login node
with no cache staged. **Everything else needs a GPU.**

## Running

Interactive on a GPU node (Slurm example — substitute your site's syntax):

```bash
srun -A <ACCOUNT> -p <GPU_PARTITION> --gpus=1 --cpus-per-task=<N> --mem=<MEM> \
     -t 04:00:00 --pty bash
cryoatom build -v map.mrc -ps protein.fasta -o <SCRATCH>/run_fresh
```

Batch: render `templates/run_cryoatom.sbatch.template` with
`scripts/render_job_template.py`, check it, then submit.

Sizing rules of thumb:

- One GPU per run; CryoAtom2 does not scale across GPUs here.
- CPUs and memory: match the site's per-GPU share (a common convention is
  ~1/4 of the node per GPU on a 4-GPU node).
- Outputs on scratch, never home.
- `--export=NONE` (Slurm) is worth using: it proves the launcher does not depend
  on an inherited `APPTAINER_BINDPATH` or `PATH`. If a job then fails to see its
  inputs, the launcher's bind list is incomplete — fix `install.extra_binds`
  rather than re-exporting the environment.

## Performance expectations

The public fixture (EMD-33198 / 7XHT; ~131 MB map; one 496-aa protein chain, one
RNA, two DNA) is **small**. The `running_time.log` shipped inside upstream's
fixture archive records **161 s** for it — that is upstream's number on
upstream's hardware, and 2.1.1 does not write such a log itself, so time your own
runs (`/usr/bin/time`, or the job's elapsed field).

The pipeline is RU-Net (stage 1) then CryoNet over 3 rounds (stage 2) then
post-processing; stage 2 dominates. Scale expectations by map size and chain
count, then add margin. Do not quote a fixture time as an expected runtime for a
real map, and never quote another machine's timings as this machine's — this
package ships no measured host timings, by design.

## Launcher switches

| Variable | Effect |
|---|---|
| `CRYOATOM_SKILL_CONFIG` | Path to the site config the launcher should read |
| `CRYOATOM_SIF` / `CRYOATOM_CACHE` | Override image and weight cache without a config. `CRYOATOM_SIF` is a file for apptainer/singularity, an image reference for docker/podman |
| `CRYOATOM_BINDS` | Extra binds, space-separated; an entry may be `/src:/dst[:opts]` |
| `CRYOATOM_MODULE_LOAD` | Module route: the command that puts `cryoatom` on PATH |
| `CRYOATOM_VERIFY_WEIGHTS=1` | Full SHA-256 re-hash against the pin before running (~5.1 GiB read). Fails closed if no pin or no python3 is available. Default is presence + size |
| `CRYOATOM_FORCE_NV=1` | Force `--nv` even without visible NVIDIA devices |
| `CRYOATOM_NO_NV=1` | Suppress `--nv` |
| `CRYOATOM_DEBUG=1` | Print the resolved runtime command instead of hiding it |

## Recovery table

| Symptom | Likely cause | Fix |
|---|---|---|
| `cryoatom: missing weight file: …` | Cache not staged, moved, or partially deleted | `stage_cryoatom_weights.sh --cache <CACHE> weights` |
| `weight cache FAILED (size…)` | Truncated or replaced weight | Re-run `weights`; it re-fetches anything whose size is wrong |
| `weight cache FAILED (sha256…)` | Corrupted or substituted weight | Delete the named file, re-run `weights`, then `pin` only if you intend to accept new content |
| `cryoatom: image file not found` | Image missing or path changed (apptainer/singularity) | Rebuild (`install/cryoatom.def`) or fix `install.image_path`; re-probe |
| docker/podman: `Unable to find image ... locally` | `install.image_path` holds a path where a **reference** belongs | Use the tag you built (`cryoatom:2.1.1`); references are resolved from the image store, not the filesystem |
| Outputs owned by root under rootless podman | `-u` was forced instead of `--userns=keep-id` | The shipped launcher handles this; if you hand-rolled the command, drop `-u` and add `--userns=keep-id` |
| `no such file or directory: /opt/conda/envs/CryoAtom2/bin/cryoatom` | Host filesystem overlay shadows the image's `/opt` | Set `install.no_mount_hostfs: true` and list site filesystems in `extra_binds` (see `references/01_configuration.md`) |
| Job cannot see the map or writes nothing | Input/output path outside every bind | Add its filesystem to `install.extra_binds` and re-render the job |
| CUDA OOM | Map too large for this GPU | Larger-VRAM GPU, or crop/mask with `-m` |
| `CUDA error: no kernel image is available` | Driver/GPU architecture predates the pinned cu118 build | Use a supported GPU; do not repin torch casually |
| `Segmentation fault` in Stage 1 | `getp` binary mismatch with the host | Ensure `getp` was **compiled** in the install (`install/cryoatom.def` step [4/7]); rebuild if in doubt |
| Build fails in `%post` step `[3/7]` | The exact `pytorch=2.1.0=py3.9_cuda11.8_cudnn8.7.0_0` pin was pruned from the channel | Report it as an upstream reproducibility failure. **Do not relax the pin** |
| Build fails with "no space left" / quota | Apptainer sandbox on home | Point `APPTAINER_TMPDIR`/`APPTAINER_CACHEDIR` at node-local scratch |
| Outputs owned by root (Docker route) | Missing `-u $(id -u):$(id -g)` | Add it; re-run into a fresh directory |
| `-pf`/`-nf` run gives poor assignment | Database does not cover every sequence in the map | Widen the database. This fails **silently**, not loudly |
| Output has no RNA/DNA although the map clearly contains it | `-ps` was passed without `-rs`/`-ds`, so `flood_fill.py:169-173` masked every nucleotide out at write time | Pass the missing class, or drop to fully sequence-free mode. Assert the expected polymer classes appear in the output |
| Results look mixed / files from an old run | Output directory was reused | Never reuse. Re-run into a fresh path |
| `cryoatom --version` disagrees with the config | Image or environment changed | Re-probe; the config is `stale` until it agrees |

## When something is genuinely broken

1. Capture the exact command, the full stderr, and `cryoatom --version`.
2. Re-run the weight verification in `sha256` mode.
3. Reproduce on the **public fixture**. A fixture failure is an install problem;
   a fixture success with a user-map failure is a data or resource problem.
4. Only then consider a rebuild — and record the new image hash in the config,
   because a rebuild changes it by design.
