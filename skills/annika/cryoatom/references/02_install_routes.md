# Installing CryoAtom2 on a new system

Nothing here runs automatically. Each numbered step is a separate confirmation.
Use `templates/install_plan.md` to record the decisions before starting.

Order matters: **image/environment → weights → site config → launcher → fixture
→ final config**. The launcher and the job templates read the site config, so
the config has to exist before they are useful (§6), and it is updated once the
fixture has passed (§9).

## 0. Gates — check these before choosing a route

| Gate | How to check | If it fails |
|---|---|---|
| Linux x86-64 | `uname -sm` | Not an execution platform. Stop. |
| NVIDIA GPU with **≥14 GiB VRAM**, reachable directly or through a queue | `nvidia-smi --query-gpu=name,memory.total --format=csv` on a GPU node, or the site's partition documentation | Stop. Apple unified memory, Docker presence, and the source's `--device cpu` path are not evidence of support. |
| CUDA-capable driver for CUDA 11.8 (≥ 470 via the compat path; ≥ 525 recommended) | `nvidia-smi` header | Ask the site admins; do not downgrade the pinned torch. |
| ~5.1 GiB for weights + ~4.5 GiB for the image (container route) or ~8 GiB for a conda env | `df -h`, plus any **inode** quota (`df -i`, `quota -s`) | Put the cache on a filesystem with room; see § Filesystem policy. |
| `curl` and `unzip` on the host doing the download | `command -v curl unzip` | Install them, or stage the cache elsewhere and copy it in. |
| Outbound HTTPS to `github.com`, `yanglab.qd.sdu.edu.cn`, `dl.fbaipublicfiles.com`, and a conda mirror | `curl -fsSI <url>` | Stage on a connected host and copy in; never bypass TLS. |
| Python 3 on the *host* (for this package's scripts, not for CryoAtom) | `python3 -V` (3.7+) | Install one. |
| **Docker/Podman route only:** NVIDIA Container Toolkit (or CDI for rootless podman) | `docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi` | `--gpus all` cannot reach a GPU without it. Fix it before building anything. |

The probe checks most of this for you:

```bash
python3 scripts/cryoatom_env_probe.py --route container --scheduler auto
```

## 1. Choose a route

| Route | Use when | Cost | Notes |
|---|---|---|---|
| **A. Apptainer/Singularity image** (recommended on HPC) | Shared cluster, no root, inode quotas | ~4.5 GiB, ~10 inodes | Reproducible, self-describing, survives host library churn |
| **B. Native conda env** | Workstation you control, or a site without a container runtime | ~8 GiB, tens of thousands of inodes | Closest to upstream; exposed to host CUDA/driver drift |
| **C. Docker / Podman** | Workstation with a container engine | ~4.5 GiB image layer | `install/Dockerfile` mirrors the Apptainer recipe; needs the NVIDIA Container Toolkit |
| **D. Module / preinstalled** | The site already provides CryoAtom | none | Verify the version and the weight path before trusting it |

All routes share §§ 5–9 (weights, config, launcher, fixture, final config).

## 2. Route A — Apptainer/Singularity image

`install/cryoatom.def` is a complete recipe. It pins the upstream commit **and**
the tree hash and verifies both inside `%post`, pins the base image by digest,
compiles `getp` from source instead of trusting the committed prebuilt binary,
and refuses to bake weights into the image.

Interactive build (a workstation, or an interactive compute allocation):

```bash
apptainer build /path/to/cryoatom.sif install/cryoatom.def
```

Scheduler build (recommended on a cluster). No site config exists yet, so pass
every value explicitly and use `--strict` so an unfinished script is an error,
not a surprise:

```bash
python3 scripts/render_job_template.py templates/build_sif.sbatch.template \
  --set ACCOUNT=<ACCOUNT> --set BUILD_PARTITION=<CPU_PARTITION> \
  --set CPUS_PER_TASK=32 --set LOG_DIR=<LOG_DIR> \
  --set DEF_FILE="$PWD/install/cryoatom.def" \
  --set IMAGE_PATH=<CONTAINER_DIR>/cryoatom.sif \
  --set BUILD_TMP_ROOT=<NODE_LOCAL_SCRATCH> \
  --set CONTAINER_RUNTIME=apptainer \
  --strict --output ~/build_cryoatom_sif.sbatch
sbatch ~/build_cryoatom_sif.sbatch
```

Rules that matter:

- **Build on a build/compute node**, never a login node — the conda solve plus
  the PyTorch download is a long, I/O-heavy job.
- **Put the Apptainer sandbox and cache on node-local scratch**
  (`APPTAINER_TMPDIR`, `APPTAINER_CACHEDIR`). A build churns tens of thousands
  of files; on an inode-quota'd home that alone can fail the build. The template
  does this.
- **Stage the image on scratch and promote it only on success**, so a failed
  build never leaves a truncated image at the published path.
- `--fakeroot` if the site allows it; the template falls back to a plain build.
- A rebuild legitimately produces a **different SHA-256**: the `%post` conda
  solve is not frozen, so the image is a *content-addressed installed snapshot*
  (identified by its own SHA-256 plus the in-image `conda-explicit.txt` and
  `pip-freeze.txt`), not a byte-identical rebuild recipe. Record the new hash in
  the site config; do not describe the recipe as bit-reproducible.
- If `%post` step `[3/7]` fails on
  `pytorch=2.1.0=py3.9_cuda11.8_cudnn8.7.0_0`, that exact build was pruned from
  the channel. Report it as an upstream reproducibility failure. **Do not relax
  the pin.**

The image ships an **empty** checkpoint directory on purpose; `%test` fails the
build if a `.pth` is found there.

Singularity ≥ 3.x accepts the same recipe and flags; substitute `singularity`
for `apptainer` throughout, including in the site config.

## 3. Route B — native conda environment

Follow the recipe's logic, not upstream's `install.sh`:

```bash
git clone https://github.com/YangLab-SDU/CryoAtom /path/to/src/CryoAtom
cd /path/to/src/CryoAtom
git checkout --detach 856e250df7b784b854b892f1b619d32d51188cef
test "$(git rev-parse HEAD^{tree})" = 0058c0c68857b66962f9ad421756513e74de7518 \
  || { echo "TREE MISMATCH — stop, this is not the pinned revision"; exit 1; }

conda env create -f linux.yml            # creates env CryoAtom2 (python 3.9, torch 2.1.0/cu118)
conda activate CryoAtom2

# getp: compile from the pinned sources. Do not trust the committed prebuilt binary.
make -C CryoAtom2/src/getp clean || true
make -C CryoAtom2/src/getp
test -x CryoAtom2/src/getp/getp || { echo "getp did not build — stop"; exit 1; }

pip install --no-deps --no-build-isolation .
SITE=$(python -c 'import site;print(site.getsitepackages()[0])')
cp -a CryoAtom2/. "$SITE/CryoAtom2/"
mv "$SITE/CryoAtom2/utils/getp" "$SITE/CryoAtom2/utils/getp.upstream-prebuilt" 2>/dev/null || true
install -m 0755 CryoAtom2/src/getp/getp "$SITE/CryoAtom2/utils/getp"
python -c 'import torch, esm, fm, mrcfile, pyhmmer, Bio; print(torch.__version__, torch.version.cuda)'
```

Why each deviation:

1. **`install.sh` is not executed.** It downloads weights into the source tree so
   `setup.py package_data` bakes them into `site-packages` — which defeats an
   external weight cache — and it hard-fails if a `CryoAtom2` conda env already
   exists. It also uses `wget --no-check-certificate`.
2. **`pip install --no-deps .` replaces `python setup.py install`.** Legacy
   `setup.py install` was removed in setuptools ≥ 80, and it produces a
   *versioned* `.egg` directory, which would make the checkpoint path
   version-dependent.
3. **`getp` is compiled**, because the committed binary was built on an unknown
   host and upstream's own README anticipates segfaults from it. Pure
   g++/OpenMP, C++11 — no CUDA, so it builds on a CPU-only node.

A native install reads checkpoints from `<site-packages>/CryoAtom2/checkpoint`
and language models from `$TORCH_HOME`. Keep the cache external and link it in
(§5); `scripts/cryoatom_launcher.sh` sets `TORCH_HOME` from the configured cache
on every call, so it does not depend on the user's shell profile.

## 4. Route C — Docker / Podman

```bash
docker build -f install/Dockerfile -t cryoatom:2.1.1 install/    # or podman build
```

`install/Dockerfile` mirrors `install/cryoatom.def`: same pinned base digest,
same commit **and** tree verification, `getp` compiled from source, no weights
baked in, and a self-check at the end of the build.

Then run it — by hand:

```bash
docker run --rm --gpus all \
  -u "$(id -u):$(id -g)" \
  -v "$PWD":"$PWD" -w "$PWD" \
  -v <CACHE>/checkpoint:/opt/conda/envs/CryoAtom2/lib/python3.9/site-packages/CryoAtom2/checkpoint:ro \
  -v <CACHE>/torch:/torchhome:ro \
  -e TORCH_HOME=/torchhome -e MPLBACKEND=Agg \
  cryoatom:2.1.1 build -v map.mrc -o out_fresh
```

— or through `scripts/cryoatom_launcher.sh`, which emits the same invocation
from the site config.

Traps specific to this route:

- **`install.image_path` is an image *reference* here** (`cryoatom:2.1.1`,
  `localhost/cryoatom@sha256:…`), not a file path. The launcher and the probe
  only require a file on disk for apptainer/singularity.
- **Every input and output path must be inside a `-v` mount.** Nothing else is
  visible.
- **Ownership:** docker gets `-u $(id -u):$(id -g)` so outputs are not
  root-owned. Rootless **podman** instead gets `--userns=keep-id` — adding `-u`
  there breaks writes into bind-mounted host directories.
- **GPU:** `--gpus all` needs the NVIDIA Container Toolkit (rootless podman:
  CDI). Check it before the first real run.

## 5. Weights — all routes

Six files, ~5.1 GiB total, external to the image by design. ESM-2 and RNA-FM are
loaded **unconditionally**, including in the no-sequence path, so all six are
needed even for a protein-only run.

```bash
bash scripts/stage_cryoatom_weights.sh --cache <CACHE> plan      # writes nothing
bash scripts/stage_cryoatom_weights.sh --cache <CACHE> weights   # download + lay out + pin
bash scripts/stage_cryoatom_weights.sh --cache <CACHE> verify    # SHA-256 against the pin
```

Layout it produces:

```
<cache>/checkpoint/RUNet.pth                                   151,641,598 B
<cache>/checkpoint/CryoNet.pth                                 847,721,570 B
<cache>/checkpoint/CryoNet_no_seq.pth                          771,564,842 B
<cache>/torch/hub/checkpoints/RNA-FM_pretrained.pth          1,194,424,423 B
<cache>/torch/hub/checkpoints/esm2_t33_650M_UR50D.pt         2,604,537,549 B
<cache>/torch/hub/checkpoints/esm2_t33_650M_UR50D-contact-regression.pt  3,687 B
<cache>/weights.pin.json                                     sizes + SHA-256
```

Byte sizes are checked on download; `pin` records SHA-256; `verify` re-checks
both. Downloads use `curl -fL` over **verified TLS** — do not reintroduce
upstream's `--no-check-certificate`.

For the **native route**, link the three CryoAtom checkpoints into the package,
because `build.py` resolves them relative to the package directory and offers no
env-var override:

```bash
bash scripts/stage_cryoatom_weights.sh --cache <CACHE> link --site-packages "$SITE"
```

That symlinks `RUNet.pth`, `CryoNet.pth`, and `CryoNet_no_seq.pth` into
`<site-packages>/CryoAtom2/checkpoint`. It does **not** move ESM-2 or RNA-FM:
those are found through `TORCH_HOME=<CACHE>/torch`, which the launcher exports
for you (and which you must export yourself if you call the native
`cryoatom` binary directly).

Air-gapped sites: stage the cache on a connected host, verify it there, copy the
whole directory including `weights.pin.json`, and re-run `verify` on arrival.

## 6. Write the site config — before the launcher is useful

The launcher and the job templates read the config, so write it now, while the
fixture is still pending. The state will be `probed`; that is correct.

```bash
# Route A / C (container)
python3 scripts/cryoatom_env_probe.py \
  --profile <PROFILE> --route container \
  --container-runtime apptainer \
  --image <CONTAINER_DIR>/cryoatom.sif \
  --weights-cache <CACHE> \
  --scheduler auto --account <ACCOUNT> --gpu-partition <GPU_PARTITION> \
  --scratch-root <SCRATCH> --log-dir <LOG_DIR> --build-tmp-root <NODE_LOCAL_SCRATCH> \
  --output ~/.config/cryoatom-skill/site-config.json

# Route B (native conda)
python3 scripts/cryoatom_env_probe.py \
  --profile <PROFILE> --route native \
  --conda-env-prefix "$(conda info --base)/envs/CryoAtom2" \
  --weights-cache <CACHE> --scheduler auto --scratch-root <SCRATCH> \
  --output ~/.config/cryoatom-skill/site-config.json

# Route D (site module / preinstalled)
python3 scripts/cryoatom_env_probe.py \
  --profile <PROFILE> --route module \
  --module-load "module load cryoatom/2.1.1" \
  --weights-cache <CACHE> --scheduler auto \
  --output ~/.config/cryoatom-skill/site-config.json
```

Every later step re-runs this command with `--force` and more evidence. Add
`--no-mount-hostfs` and `--extra-bind <FS>` if the container needs them
(`references/01_configuration.md` explains when), and `--host-pattern` if the
default (this host plus its domain) is wrong for the cluster.

## 7. Launcher

`scripts/cryoatom_launcher.sh` is the launcher. It checks the six weights before
a `build` (and *only* before a `build` — `--version` and `build -h` stay usable
with no cache), sets `TORCH_HOME`, binds the cache, and adds a GPU flag only
when NVIDIA devices are actually present.

```bash
install -m 0755 scripts/cryoatom_launcher.sh <BINDIR>/cryoatom     # a dir on PATH
cryoatom --version          # expect: CryoAtom 2.1.1
cryoatom build -h           # flag surface; compare with references/03_cli_and_outputs.md
```

Then record it and re-check:

```bash
python3 scripts/cryoatom_env_probe.py ... --launcher <BINDIR>/cryoatom --live-version \
  --output ~/.config/cryoatom-skill/site-config.json --force
```

Keep `scripts/check_cryoatom_weights.py` beside the installed launcher (or keep
the whole package reachable) if you want `CRYOATOM_VERIFY_WEIGHTS=1` to do a
full SHA-256 pass; the launcher refuses rather than silently downgrading.

## 8. Fixture run — required before claiming readiness

The upstream public example (EMD-33198 / PDB 7XHT: one 496-aa protein chain, one
RNA, two DNA) is public data and a safe first run.

```bash
bash scripts/stage_cryoatom_weights.sh --cache <CACHE> fixture
```

With a scheduler:

```bash
python3 scripts/render_job_template.py templates/smoke_cryoatom.sbatch.template \
  --set OUTPUT_ROOT=<SCRATCH>/cryoatom_smoke \
  --strict --output ~/smoke_cryoatom.sbatch
sbatch ~/smoke_cryoatom.sbatch
```

Without one (workstation, or an interactive GPU allocation):

```bash
cryoatom build \
  -v  <CACHE>/fixture/emd_33198.map \
  -ps <CACHE>/fixture/protein.fasta \
  -rs <CACHE>/fixture/rna.fasta \
  -ds <CACHE>/fixture/dna.fasta \
  -o  <SCRATCH>/cryoatom_smoke_1
python3 scripts/summarize_cryoatom_output.py <SCRATCH>/cryoatom_smoke_1
```

Pass criteria are in `examples/fixture_expectations.json`: exit 0, an mmCIF with
several thousand atoms and ≥4 chains. Upstream's shipped `running_time.log` for
this fixture records 161 s; **2.1.1 does not write that file itself**, so judge
the run by its exit code and its model, not by a missing log.

## 9. Record the fixture in the config

```bash
python3 scripts/cryoatom_env_probe.py \
  --profile <PROFILE> --route container \
  --image <CONTAINER_DIR>/cryoatom.sif --launcher <BINDIR>/cryoatom \
  --weights-cache <CACHE> \
  --scheduler auto --account <ACCOUNT> --gpu-partition <GPU_PARTITION> \
  --scratch-root <SCRATCH> --log-dir <LOG_DIR> \
  --live-version --hash-image \
  --record-fixture --fixture-job <JOBID> --fixture-gpu "<GPU MODEL>" \
  --fixture-elapsed-s <SECONDS> \
  --output ~/.config/cryoatom-skill/site-config.json --force
```

The probe builds the config from the flags you pass, so pass the full set every
time — a shorter command produces a thinner config, not a merged one. Only now
may the state reach `ready`, and only for this machine.

## Filesystem policy

- **Weights and image**: a filesystem with space *and* inodes. One image plus an
  external cache costs a handful of inodes; a conda env costs tens of thousands.
- **Outputs**: scratch, never home. Models plus kept intermediates are large.
- **Build sandbox**: node-local scratch, cleaned up afterwards.
- **Never** put outputs inside the weight cache or beside the image.

## Non-Slurm schedulers

The templates are Slurm-shaped because that is the common case, and each one
declares `# render-scheduler: slurm`. `render_job_template.py` warns (and with
`--strict` refuses) when the site config says something else — it will not
quietly emit Slurm directives on a PBS site. Keep the *body* and port the
directives:

| Need | Slurm | PBS Pro | LSF |
|---|---|---|---|
| Submit | `sbatch` | `qsub` | `bsub <` |
| GPU | `--gpus=1` / `--gres=gpu:1` | `-l select=1:ngpus=1` | `-gpu "num=1"` |
| Queue | `-p <part>` | `-q <queue>` | `-q <queue>` |
| Account | `-A <acct>` | `-A <acct>` | `-P <project>` |
| Walltime | `-t 04:00:00` | `-l walltime=04:00:00` | `-W 4:00` |

The probe records `scheduler.detected_from` and leaves
`scheduler.gpu_flag_confirmed: false`: a `qsub` on PATH may be PBS Pro, OpenPBS,
Torque, or SGE, whose GPU syntax differs. Confirm the site's actual syntax
before submitting, then set `--gpu-flag` accordingly.

With no scheduler at all (`scheduler.type: local`), skip the templates and run
the commands directly on the GPU machine.
