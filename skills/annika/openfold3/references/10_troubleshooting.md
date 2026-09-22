# 10 — Troubleshooting

Each row gives symptom → likely cause → check → fix. Pins: `openfold-3@v0.5.0` (`c4771653`) and
`uplifting-biomolecular-modeling@f4f62fa:openfold3_ob0/`. Labels: **[source]** pinned code, **[docs]** upstream or kit
docs, **[live]** captured on a real install, **[measured]** the validated Slurm site (A100-SXM4 40 GB / H100 94 GB,
2026-09-22), **[community]** upstream issue `#N (YYYY-MM)` (`https://github.com/aqlaboratory/openfold-3/issues/N`, collected
2026-09-22; reports, not tested fixes), **[inferred]** reasoning only. Re-probe first (`scripts/openfold3_env_probe.py
--json`). Any fix that installs, downloads, sends sequences off the host or submits a GPU job needs per-action consent.

## Triage order

1. **Exit code and the kit's exit-rule line** (grep `exit rule ->`; census lines follow it). For example
   `pred --mode exact: exit rule -> 0 (ok; structures 5/5; templates_dropped=0; partial=False; allow_template_drop=False)`
   **[live]**. Codes: 0 ok, 1 failed or `incomplete`,
   2 usage, 3 NOT ACTIVE or pins, 5 templates dropped (`03_cli_reference.md` §8).
2. **Stock rc 0 is not success.** Upstream catches OOM and per-query exceptions, logs `OOM for query_id(s) …` or
   `Failed for query_id(s) …`, skips the query and still exits 0 **[source]** (`projects/of3_all_atom/runner.py`,
   `core/runners/writer.py`). Read `<out>/summary.txt` (`Failed Queries: …`) and `<out>/logs/predict_err_rank0.log` (an
   empty `logs/` is deleted), or run `scripts/summarize_openfold3_output.py <out> --expect-seeds M --expect-samples N`
   (rc 1 = incomplete). OOM → the OOM ladder below; input errors → `04_input_query_format.md` "Common errors". Finish by
   rerunning the fixed queries into a fresh `--output-dir`, or resume the same dir with runner YAML
   `experiment_settings: {skip_existing: true}` (`05_core_workflows.md` workflow 6).
3. **Kit stderr lines** (`WEIGHTS`, `ACTIVE`/`NOT ACTIVE`, `TEMPLATES DECLARED`, `LEVER …`, exit census `fallbacks=`):
   meanings in `06_kit_modes_and_multigpu.md` §7.
4. **The node:** `nvidia-smi` inside the job shows card, driver, free memory and other processes.
5. If the cause is host-level (driver, image, environment, kit version), stop and re-probe (`11_decision_trees.md` §8).

## Install and environment

| Symptom | Likely cause | Check | Fix |
|---|---|---|---|
| `Setting accelerator to CPU` **[live]**; `No supported gpu backend found!` #182 (2026-04); `libcuda.so.1: cannot open shared object file` **[live]** | No GPU in the job, Docker without `--gpus all`, or Apptainer without `--nv` | `nvidia-smi` in the job | Request a GPU; add `--gpus all` (plus the NVIDIA Container Toolkit) or `--nv`. Harmless on a CPU node that only runs `--help` or `check` **[live]**. CPU/MPS is pixi-only and not validated |
| Errors at the first CUDA call, driver too old **[unverified wording]** | Driver older than 570 under the CUDA 12.8 stack | `nvidia-smi` driver version | Driver ≥ 570 (admin) |
| Kit mode exits 3 naming the compute capability **[docs]**; stock `RuntimeError: Unsupported GPU and data type combination` #21 (2025-10, V100 with DS4Sci on) | Compute capability < 8.0 | `nvidia-smi --query-gpu=compute_cap --format=csv` | Use an A100/H100-class card. The fp32 / DS4Sci-off workaround in #21 was never tested by its reporter |
| `Unable to JIT load the evoformer_attn op …` #218 (2026-05); `…/evoformer_attn.so: cannot open shared object file` #17 (2025-10), #23, #62 | A runner YAML set `use_deepspeed_evo_attention: true` without CUTLASS/nvcc. The v0.5.0 default is `false` **[source]**; the docs kernels page example sets it `true` **[docs]** | grep every runner YAML, including `$OPENFOLD_CACHE/runner.yml` | Set it `false` (Triton triangle kernels are the default; `use_cueq_triangle_kernels: true` selects cuEquivariance). To keep DS4Sci, set `CUDA_HOME` and `CUTLASS_PATH` (upstream Installation, "Environment variables") |
| `No such file or directory: '/usr/local/cuda/bin/nvcc'`; `/usr/bin/ld: cannot find -lcurand` **[docs]**; `No module named 'cutlass_library'` #15 (2025-10, open) | Extension JIT without the CUDA toolkit or CUTLASS | `echo $CUDA_HOME; which nvcc` | Turn DS4Sci off, or set `CUDA_HOME`, `LIBRARY_PATH`, `CUTLASS_PATH`. The kit image is a CUDA 12.8 `devel` image with nvcc |
| DS4Sci runner YAML on A100 in the kit image: `no kernel image is available for execution on the device` **[docs]** (`configs/a100.env`) | The kit Dockerfile builds the op for sm_90 only | the image's `TORCH_CUDA_ARCH_LIST` | Keep DS4Sci off (off in the stock configuration and every mode; how each mode treats a DS4Sci overlay: `06_kit_modes_and_multigpu.md` §10), or rebuild the op with `8.0;9.0` |
| Kit route C run ends inside upstream with no structures **[docs]** | `cuequivariance-torch` / `cuequivariance-ops-torch-cu12` 0.10.0 missing; the kit's stock configuration uses them | `python -m pip show cuequivariance-torch` | Install the pins in `environment/requirements.lock` |
| Load error naming `GLIBCXX_3.4.32` or `GLIBC_2.32` **[docs]** | Host libstdc++/glibc older than the kit's prebuilt sm_90a extensions (`common/opt_core/README.md`) | `strings "$(g++ -print-file-name=libstdc++.so.6)" \| grep -c GLIBCXX_3.4.32`; `ldd --version` | Use the kit image. Read the `LEVER` lines for kernels not served **[unverified: failure form]** |
| `ImportError: libXrender.so.1` #130 (2026-03) | RDKit drawing libraries imported via `pdbeccdutils` on a headless host | `ldconfig -p \| grep libXrender` | Install `libxrender1 libxext6 libsm6` (admin, kit `STOCK.md`) or use a container |
| pixi solve errors or broken CUDA envs: #283 (2026-06), #352 (2026-08) | pixi older than the manifest requires | `pixi --version` | pixi ≥ 0.73 (`requires-pixi` in v0.5.0 `pixi.toml`) |
| `run.sh: install takes no --config / --mode (usage: …)` rc 2 **[live]** | Kit README prose shows `--config` on every command; `install` rejects it | the command line | Drop `--config`/`--mode` (cards belong to `pred`/`check`/`warm`): `run.sh install --weights DIR` (consent: 2.3 GB, plus wheel, source, CCD if missing) |
| `run.sh: openfold3 is not installed at its pin, file for file (stock/PINS.json)` rc 3 | Another openfold3 version, an editable checkout, a patched file, or the wrong `python` on PATH | `python -I stock/check_pins.py` names the file; `which python` | Reinstall the pinned wheel (`run.sh install`). Never edit `stock/`. Keep patched upstream in a separate env |
| `NOT ACTIVE: reason=package_missing` rc 3 | The kit package is not in this interpreter | `python -c "import openfold3_ob0_opt"` | Activate the kit env or image; `run.sh install` |
| `NOT ACTIVE: the kit's hook is not live at interpreter start …` rc 3 | Env route (`OPENFOLD3_OB0_OPT=<mode>`) with the `.pth` hook absent, stale, or only on `PYTHONPATH` | the diagnosis text says which | `pip install -e ../common/opt_core -e opt` into that interpreter, or use `run.sh pred --mode <m>` |
| Any Python process, plain `run_openfold` included, exits 3 with `NOT ACTIVE: undeclared variable(s) OPENFOLD3_OB0_OPT_…` **[live]** | An `OPENFOLD3_OB0_OPT*` name the kit package does not declare (typo), or a value it does not run **[docs]** | `env \| grep ^OPENFOLD3_OB0_OPT` | Unset it |

## Containers, paths and caches

| Symptom | Likely cause | Check | Fix |
|---|---|---|---|
| A kit variable set on the host is ignored: no `ACTIVE` line, no `levers_off=`, or `no checkpoint: pass --ckpt or set OPENFOLD3_OB0_CKPT` rc 2 | `apptainer --cleanenv` drops host variables; a fixed forward list dropped 21 kit variables at the measured site **[measured]** | `apptainer exec <sif> env \| grep -E '^(OPENFOLD\|OF3\|MODEL_OPT)'` | Forward by prefix (`APPTAINERENV_<name>`): `OPENFOLD3_OB0_OPT*`, `OF3TP_*`, `OF3O_*`, `MODEL_OPT_*`, plus `OPENFOLD3_OB0_CKPT`, `OPENFOLD_CACHE` and the cache variables. Unset stale `APPTAINERENV_`/`SINGULARITYENV_` copies first |
| Image directories under `/opt` (e.g. the kit's `/opt/jit_cache`) are empty or foreign at run time | The site's Apptainer config mounts host `/opt` over the image's (`hostfs`), as at the measured site | `apptainer exec --no-mount hostfs <sif> ls /opt`, then without the flag | `--no-mount hostfs` plus an explicit `--bind` for each path the job needs |
| `Read-only file system` or `Permission denied` on outputs or inputs | Under `apptainer run`, relative paths resolve under `/kit/openfold3_ob0`: the runscript `cd`s there inside the read-only image **[source]** (`environment/apptainer.def`) | the path in the error | Use absolute host paths on a bound, writable filesystem |
| `run.sh install --weights <dir>` fails inside the image | In the image pip is skipped ("installed from this tree already") and the CCD only checked **[source]**; the checkpoint is fetched only when absent, so `<dir>` must then be a writable bind | install output | Bind a writable weights directory, or place the checked checkpoint there first (install then only verifies it) |
| Home over quota or inode limit: `~/.triton`, `~/.cache/torch_extensions`, `~/.cache/openfold3_ob0_opt`, `~/.openfold3` grow | Stock route: Triton, torch extensions and `OPENFOLD_CACHE` default to home; kit without `--config`: the Triton cache is not keyed, so it goes to `~/.triton` **[source]**; kit: the digest memo goes to `$XDG_CACHE_HOME` (also written by `check`). JIT is 668–1 013 files / 40–65 MB per job **[measured]** | `du -sh ~/.triton ~/.cache/* ~/.openfold3` | Point `MODEL_OPT_JIT_ROOT`, `TRITON_CACHE_DIR`, `TORCH_EXTENSIONS_DIR`, `XDG_CACHE_HOME` and `TMPDIR` at node-local job storage; always pass `--config`. Keep weights on project storage (`02_install_and_environment.md` Route 3). Delete old caches only after the user confirms (`11_decision_trees.md` §9) |
| A home-cache audit "fails" although every prediction succeeded **[measured]** | Other processes on a shared account write to `~/.cache` | inspect the new paths | Filter the audit by tool pattern: openfold, triton, torch_extensions, opt_core |
| `jit cache: <dir> refused (another owner, open to group or others, a symbolic link, or not creatable)` | The per-user JIT root `${TMPDIR:-/tmp}/model_opt_jit-uid<uid>` failed the kit's private-directory rule **[source]** | `ls -ld <dir>` | Use a directory you own, mode 0700, not a symlink |
| `PermissionError` in shared `/tmp` dirs #150 (2026-03, fixed shared paths before 0.5.0); leftover `of3-of-<user>/` after crashes #342 (2026-07) | MSA and template workspaces live in `<tmpdir>/of3-of-<user>/` **[source]** | `ls -ld ${TMPDIR:-/tmp}/of3-of-$USER` | Set `TMPDIR` to a job-private directory and delete it at job end |

## Weights and CCD

| Symptom | Likely cause | Check | Fix |
|---|---|---|---|
| `Default checkpoint openbind-2025-06-30-174k not found in <dir>, cowardly refusing to perform inference.` | v0.5.0 never downloads at predict time, whatever `--help` says **[source]**. No checkpoint, or `<dir>` comes from a stale `ckpt_root` pointer | `cat $OPENFOLD_CACHE/ckpt_root; ls <dir>` | `setup_openfold --config setup.json` or `run.sh install --weights DIR` (consent, 2.3 GB), or pass `--inference-ckpt-path`. Fix or remove a stale `ckpt_root` |
| `Invalid value for '--inference-ckpt-path' … does not exist` (rc 2) or `Provided checkpoint path … does not exist` (path from a runner YAML) **[source]**; kit `no such checkpoint:` / `no checkpoint: …` rc 2 | Typo, path not bound into the container, or variable not forwarded | `ls -l` inside the container | Use an absolute, bound path; set and forward `OPENFOLD3_OB0_CKPT` |
| `Selected checkpoint openfold3-p2-155k is not compatible with the currently installed OpenFold3 version 0.5.0` or `… not found in checkpoint registry` **[source]** | Legacy name (`>=0.4,<0.4.4dev0`) or the release-note typo `openbind-2025-06-03-174k` | registry in `07_msa_templates_weights.md` §8 | Use `openbind-2025-06-30-174k`. Preview-2 needs openfold3 0.4.x (the 0.4.1 kit) |
| "Where is the new .pt file?" #378 (2026-08) | Old package or old setup | `pip show openfold3` | Update to ≥ 0.5.0, then re-run `setup_openfold` (the collaborator's answer) |
| `WARNING: WEIGHTS unknown sha256=… proceeding` | Not the pinned OpenBind-0 bytes: another checkpoint, a truncated download, or a fine-tune | `sha256sum` → `bd43301c…8e29e4`, 2 287 872 989 B | Move the bad file aside (consent), then `run.sh install --weights DIR` fetches and verifies; with a file present it only checks and refuses a mismatch **[source]**. A finished run is not a digest check |
| `setup_openfold` in a batch job fails with `EOFError: EOF when reading a line`, or waits on a terminal | Without `--config`/`--non-interactive` it prompts with plain `input()` **[source]** | — | `setup_openfold --config setup.json` (`--non-interactive` ignores `$OPENFOLD_CACHE`; `03_cli_reference.md` §4) |
| `PermissionError` creating `$OPENFOLD_CACHE` or writing `ckpt_root` | Cache unset (default `~/.openfold3`) or read-only in the container. Predict creates the cache directory on every call **[source]** | `echo $OPENFOLD_CACHE` | Set a writable `OPENFOLD_CACHE`. `--inference-ckpt-path` avoids only the `ckpt_root` write |
| Settings appear that nobody passed (presets, templates, server URL) | `$OPENFOLD_CACHE/runner.yml` is deep-merged under every `--runner-yaml` **[source]** | `ls $OPENFOLD_CACHE/runner.yml`; the kit names it on stderr | Remove or edit that file |
| `KeyError: No atom information found for residue '<X>' in CCD` (biotite) | Full CCD not installed in this env's biotite; the bundled subset lacks the code **[docs]** (kit `STOCK.md`), or the code does not exist | `run.sh install` (CCD sha256 check) | `setup_openfold` or `run.sh install [--ccd FILE]`; both write into biotite, so the env must be writable. Otherwise give the ligand as SMILES |

## Inputs (full list: `04_input_query_format.md`, "Common errors")

| Symptom | Cause → fix |
|---|---|
| `Option '--use-msa-server' requires an argument.` or `'--output-dir' is not a valid boolean` rc 2; kit `unrecognized arguments: --use_msa_server false` rc 2 **[live]** | Bare boolean → `--use-msa-server false`; the kit accepts only the hyphen spelling |
| `chains.0.use_msas  Extra inputs are not permitted`; #172 (2026-04, open), #27 (2025-11) | MSA switches placed in a chain, as the docs example does → move them to query level |
| `Extra inputs are not permitted` on any other key | Field not in the v0.5.0 schema → remove it. Validate with `scripts/make_query.py --validate FILE` |
| `Multiple CCD codes for a single chain are not yet supported.` / `SDF format for ligands is not yet supported.` | NotImplemented at v0.5.0 **[source]** → one CCD code per chain, or SMILES |
| `covalent_bonds` accepted, but no bond forms | Schema only at v0.5.0; #219 (2026-05, open) → do not promise covalent ligands |
| `ConformerGenerationError` on organometallics such as HEM #110 (2026-02, closed 2026-06) | RDKit conformer generation (120 s timeouts **[source]**) → use the CCD code and check the SMILES |
| Some CCD codes fail but SMILES works #94 (2026-01); custom `ccd_file_path` ignored #109 (2026-02, open) | Biotite's CCD is used → give custom compounds as SMILES |
| `UnpicklingError` with `--use-templates false` **[docs]** | Template keys still in the query → remove the keys |

## MSA server and MSAs

| Symptom | Likely cause | Check | Fix |
|---|---|---|---|
| Job sits for hours with repeated `Timeout while submitting to MSA server. Retrying...`, or `Sleeping for <n>s. Reason: RATELIMIT` | Packets to `api.colabfold.com` dropped (6.02 s timeouts retried with no cap), or throttling (resubmit every 5–10 s, no cap) **[source]**. Refused connections instead fail after 5 retries (`Error while fetching result from MSA server`) | `curl -sI https://api.colabfold.com` from the node | Cancel the job. Run `run_openfold align-msa-server` on a node with internet (approved sequences only), then predict offline with `--use-msa-server false` (`05_core_workflows.md` workflow 7) |
| `RuntimeError: Failed to fetch chain ID mappings from RCSB …` **[source]** | The node reaches the MSA server but not `data.rcsb.org`; the template-hit chain remap runs in the MSA step, even with `--use-templates false` (`07_msa_templates_weights.md` §2) | `curl -sI https://data.rcsb.org` | Allow RCSB as well, or compute MSAs where both are reachable |
| `MMseqs2 API is giving errors.…` or `…undergoing maintenance` **[source]** | Server error or maintenance, or a non-protein sequence | the sequence letters | Retry later, or use precomputed MSAs |
| `SSLCertVerificationError` on `api.colabfold.com` #119 (2026-02, open) | Host CA store | a plain `requests.get` to the server | Fix the CA bundle (`REQUESTS_CA_BUNDLE`). Never disable verification |
| Sequences left the host although the query had `use_msas: false` | Query-level flags do not stop the collector **[source]** (`07_msa_templates_weights.md` §2) | — | Only `--use-msa-server false` keeps sequences local. If private data went out, tell the user |
| `Expected MSA file for chain A of type PROTEIN … A dummy MSA with only the query sequence will be used for this chain.` **[live]** | Single-sequence run: expected with `--use-msa-server false` and no MSA paths | query MSA paths | Expected. If you supplied MSAs, the paths or layout are wrong (07 §4) |
| MSA format errors: #188 (2026-04, open), #55 (2025-11) | a3m/sto files not in the expected layout | 07 §4 | Follow the precomputed layout; test on one chain first |
| Precomputed paired MSAs dropped #371 (2026-08) | Bug in earlier releases; the fix (PR #373) is in v0.5.0 history **[source]** | `pip show openfold3` | Use 0.5.0 |
| A rerun fails with `FileNotFoundError …/colabfold_msas/raw/paired/…/pair.a3m` #269 (2026-06); stale raw folder reused #39 (2025-11) | Leftover MSA workspace under `<tmpdir>/of3-of-<user>` | list it | Use a fresh `TMPDIR` per job and delete leftovers |
| `Template preprocessing TIMED OUT after 60s` **[source]**; #164 (2026-04) | Slow template path | log | Runner YAML `template_preprocessor_settings: {preprocess_timeout: <s>}`. The log's `--preprocess-timeout` hint is not a `predict` flag **[source]** |

## Runtime: memory, speed, kit gates

| Symptom | Likely cause | Check | Fix |
|---|---|---|---|
| `OOM for query_id(s) …`: stock exits 0, kit exits 1 `incomplete` | GPU memory | peak `nvidia-smi`; token count (04) | OOM ladder below |
| Kit rc 1 with `structures k/N` on the exit-rule line | A query failed inside upstream (OOM, ligand error, writer) | `summary.txt`, `logs/predict_err_rank0.log` | Fix that query; rerun it alone into a fresh `--output-dir` |
| OOM despite `low_mem` #71 (2025-12, open) | The reporter used 100 samples; the confidence head moves the whole `[samples, N, N, C_z]` pair tensor to the GPU at once, so memory scales with samples, and `low_mem` does not cover it (contributors' comments) | `--num-diffusion-samples` | Keep the default 5 samples (the reporter's fix); add seeds instead |
| OOM in `get_token_frame_atoms` on huge inputs #225 (2026-05, open) | O(N_atom²) distance intermediate; reported for a 5 247-residue / 41 842-atom monomer that failed only after smaller queries in the same call | atom count; query order | Run such a query alone in its own call; else split or crop. Kit `big` is untested at this size |
| `DataLoader worker exited unexpectedly` / worker segfault #149 (2026-03, open) | Host RAM or shared memory too small **[inferred]**; the reporter's job had 20 GB and 10 workers on 2 suggested | job `--mem`, `/dev/shm`, Docker `--shm-size`/`--ipc=host` | More host memory than the default 10 loader workers need (no measured minimum). Lower `data_module_args.num_workers` (default 10) in a runner YAML |
| Every call takes ≥ ~35 s, even for tiny inputs | ≈ 45 s of Python start-up plus the 2.3 GB checkpoint load, per call, in every mode (kit README) **[docs]**; measured whole calls ≤ 200 tokens took 33–55 s **[measured]** | — | Put many queries, and all seeds, into one call |
| The first `fast` call is slow | Triton compile (~20 s) plus a one-time fused-kernel self-check (seconds on H100, up to ~30 s on A100) **[docs]**; measured +22–39 s | cache directory contents | `run.sh warm --config <card> --mode fast --out DIR [--tiling 2to2,4to4,6to6]`; reuse a JIT root; compare modes on a second call. `--no-compile` changes nothing |
| rc 3 `NOT ACTIVE: …` at `pred` | Pins, package or core, hook, partial line, cc < 8.0, `--z-dtype bf16 --conf-dtype fp32`, fewer GPUs than `--n_gpu` | the reason text | Causes and fixes: `06_kit_modes_and_multigpu.md` §8. Never wrap kit calls in `set -e` |
| rc 5 `TEMPLATES DROPPED: query=… declared chains_templated=<n> real_slots=0 …` | On an offline host the RCSB structure fetch raised a connection error; upstream dropped the whole alignment and would have exited 0 (kit note `OB0-001`) **[docs]** | log `Preprocessing templates: 0/1` | Runner YAML `template_preprocessor_settings: {structure_directory: <mmCIF dir>, structure_file_format: cif, fetch_missing_structures: false}`, or remove the template keys. `--allow-template-drop` only as a recorded decision |
| Templates seem to have no effect: #294 (2026-07), #262; #406 (2026-09, open: CIF-direct coordinates come from `<structure_directory>/<stem>.cif` or are fetched from the PDB); #420 (2026-09, open) | Template bugs; weak influence in single-sequence runs #234 | `TEMPLATES DECLARED … files_resolved=` and the `templ distinct census` line | Do not promise template steering. Name CIF files by their entry, or point `structure_directory` at your files **[community]** |
| `run.sh: --mode exact disagrees with OPENFOLD3_OB0_OPT=fast …` rc 2 | Mode variable exported elsewhere | `env \| grep OPENFOLD3_OB0_OPT` | Unset one of them |
| A "stock" run prints `ACTIVE mode=…` | An exported `OPENFOLD3_OB0_OPT` arms the kit inside plain `run_openfold` **[live]** | env | `unset OPENFOLD3_OB0_OPT`, or use `run.sh pred --mode off` |
| `ValueError: zip() argument 2 is longer than argument 1` in `chunk_utils.py` | Kernel-flags-off configuration with a ≤ 750-token query ahead of a larger one in one process (kit note `OB0-002`) **[docs]** | traceback | Kit `fast` handles it (`tuner_guard`); `off`/`exact` never reach it. For custom kernels-off YAMLs, run small and large queries in separate calls |
| A Slurm job hangs in Lightning #47 (2025-11, open) | Lightning's SLURM autodetection spawns too many processes | tasks vs GPUs | One task per single-GPU job (`-n 1`, one GPU) **[inferred]** |

**OOM ladder.**
- **Stock:** (1) drop samples back to 5 (#71). (2) Add a runner YAML with `model_update: {presets: [predict, low_mem]}`: it sets the
  per-sample and offload cutoffs to 0 **[source]** and trades runtime for memory; of the memory options only bf16 would
  change quality (#25, 2025-11). (3) Use a larger card. (4) Split the complex.
- **Kit:** (1) `off`/`exact` → `fast`, which halves peak memory at ≥ 500 tokens **[measured]**. (2) → `big`: row blocks
  start at 1 401 polymer tokens, below that gate `big` is `fast`; `OF3O_MIN_TOKENS=<n>` lowers the gate **[docs]**,
  unvalidated on 40 GB. (3) → `big --n_gpu 2|4|8` on one host **[docs]**, untested here. (4) Use a larger card. Record
  what fit.

## Multi-GPU (kit `big --n_gpu P`; nothing multi-GPU was tested at the measured site)

Mechanics and variables: `06_kit_modes_and_multigpu.md` §5.

| Symptom | Cause → fix |
|---|---|
| `--n_gpu` refused by name | P not 2, 4 or 8, or the mode is not `big` (rc 2); fewer than P visible GPUs (rc 3, `pred` only) → `--mode big --n_gpu P` with P GPUs of one node, one task |
| `NOTE chunk plan table (CHUNK_PLAN) is for >=79 GB cards; using it on <m> GB … may OOM` | Card below 79 GB → a note, not a refusal. Tune with `OF3TP_CHUNK=<chunk>` **[source]** and test first |
| The query ran on one GPU: `fallbacks=tp:small_n_unsharded=1` or `tp:pocket_unsharded=1` | Small or pocket-constrained query → expected; it runs as stock on one GPU |
| `feats_ranks_differ` | Ranks featurised differently → report it; run on one GPU |
| Errors missing from the main log | Rank logs are in `<out>/_tp/` |
| Upstream `pl_trainer_args.devices: N` does not speed up one large prediction | Upstream spreads queries across GPUs; it does not shard one structure **[docs]** |

## Outputs and results

| Symptom | Cause → fix |
|---|---|
| Fewer `*_model.cif` than queries × seeds × samples | Failed queries (see triage), or stale files from an earlier run → always use a fresh `--output-dir` and check with the summarizer |
| `seed_2746317213/` instead of `seed_42/` | `--num-model-seeds N` draws seeds from start seed 42 **[source]** → omit it for seed 42, or list `experiment_settings.seeds` in a runner YAML |
| Low pLDDT/pTM in a single-sequence run | No MSA; measured mean pLDDT was ~31–92 across single-sequence inputs **[measured]** → get MSAs through an approved route before judging (`08_outputs_and_confidence.md`) |
| "Irregular cloud of amino acids" #120 (2026-02) | Broken environment → run the ubiquitin fixture and check pins |
| `fast` model differs from `off` by many Å | bf16 and fused-kernel numerics, amplified on low-confidence inputs (29.4/29.9 Å top-model CA RMSD **[measured]**) → judge against stock's seed spread (09); use `exact`/`--det 1` when outputs must not move |
| Implausible ligand geometry (sp2 not planar) #136 (2026-03, open) | A known failure mode of AF3-class models → check ligand geometry; do not over-interpret |
| Nucleotide PAE frames questioned #247 (2026-06, open) | Frame atom order vs the AF3 SI → treat nucleotide PAE with care |

## Benign lines (do not chase)

**[live]**: `DeprecationWarning: torch.jit.script…`; `ResourceWarning: unclosed file …`; Lightning "Tip:" lines;
`SLURM auto-requeueing enabled. Setting signal handlers.`; `OpenFold3 Triton evoformer kernel is running on a non-HIP
backend with default, untuned Triton config … Correctness holds`; `Warning: No template data provided for chain […] …,
skipping...`; `No chains with templates to preprocess.`; `Removing empty log directory...`; `LEVER … state=off
reason=not_in_line`. **[docs]**: `NAMED_FALLBACK:apb …` census lines under `fast`/`big`; per-call `fallback:<reason>=<n>`
with rc 0. **[source]**: `RLIMIT_NOFILE hard limit … is less than the desired limit` (raise `ulimit -n` or lower
`num_workers` only if "Too many open files" follows). `leaked semaphore objects to clean up at shutdown` after a
finished run #268 (2026-06) **[inferred]** benign.

## Most-discussed community issues (112 issues collected 2026-09-22; Discussions disabled)

| Issue | Theme (comments) | State | What it means at v0.5.0 |
|---|---|---|---|
| #294 (2026-07) | CIF templates ignored (22) | closed | Template influence is fragile; see #406/#420 (open) |
| #283 (2026-06) | pixi CUDA envs broken (20) | closed | pixi ≥ 0.73 |
| #279 (2026-06) | macOS inference (20) | closed | MPS through pixi; not validated |
| #17 (2025-10) | missing `evoformer_attn.so` (19) | closed | DS4Sci is off by default; if on, set `CUTLASS_PATH` |
| #149 (2026-03) | DataLoader worker exited (13) | open | Host memory, shm, workers |
| #31 (2025-11) | raw ColabFold outputs deleted (12) | open | Save settings (`07_msa_templates_weights.md` §6) |
| #188 (2026-04) | MSA format incompatible (11) | open | Precomputed layout (07 §4) |
| #136 / #110 | ligand sp2 geometry / HEM conformer (8 each) | open / closed | Check ligand geometry; prefer CCD codes |

The kit is labelled an unmaintained reference release: report reproducible bugs upstream, reproduced with `--mode off`.

## What to capture when asking for help

1. Probe report: `scripts/openfold3_env_probe.py --json` (add `--deep` only with consent). Remove the hostname, user
   name and Slurm fields before posting it anywhere public.
2. The exact command with private paths replaced by `<placeholders>`, the rc, and the last ~50 stderr lines.
3. Kit lines: `WEIGHTS`, `ACTIVE`/`NOT ACTIVE`, `TEMPLATES DECLARED`/`DROPPED`, `LEVER … fallback`, `exit rule`, plus
   `run.sh check --config <card> --mode <m> --json <file>`.
4. `summary.txt`, `logs/predict_err_rank0.log`, the summarizer output, and the output tree listing.
5. Versions: `openfold3` (`pip show`), torch with its CUDA build, driver, card and memory (`nvidia-smi`), compute
   capability, kit commit, and the `check_pins.py` result.
6. The query JSON (sequences redacted if private) and the token count; every runner YAML, including
   `$OPENFOLD_CACHE/runner.yml`.
7. Route (Docker/Apptainer/venv/pixi), binds, and the forwarded variables:
   `env | grep -E '^(OPENFOLD|OF3|MODEL_OPT|TRITON|CUDA)'`.
8. Where to report: reproduce with bare stock or `--mode off` first, then file an upstream GitHub issue with OS, GPU and
   memory, Python version and install route. Never post unpublished sequences, account names or site paths.
