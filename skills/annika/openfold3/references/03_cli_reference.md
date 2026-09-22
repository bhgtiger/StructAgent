# 03 — CLI reference (`run_openfold`, `setup_openfold`, kit `run.sh`)

Pins: upstream `aqlaboratory/openfold-3` tag **v0.5.0** (`c4771653`); kits from `anthropics/uplifting-biomolecular-modeling`
@ `f4f62fa` (`openfold3_ob0/` = 0.5.0 + OpenBind-0, `openfold3/` = legacy 0.4.1 + preview-2). Generate commands ONLY from the
options below; for anything else capture live `--help` on the target first (read trap 5 before you do).

Labels: **[live]** = shown in help or error output captured on a real install (kit image, OpenFold3 0.5.0 + `openfold3_ob0`
0.8.18.1, 2026-09-22; help and usage-error probes run on a CPU node); **[source]** = pinned code only; **[docs]** = kit or
upstream docs. Commands are templates unless marked [live]. Mode semantics: [06_kit_modes_and_multigpu.md](06_kit_modes_and_multigpu.md).

## 1. Upstream console scripts (`openfold-3@v0.5.0:pyproject.toml [project.scripts]`)

| Script | Entry point | What it is | |
|---|---|---|---|
| `run_openfold` | `openfold3.run_openfold:cli` | click group: `predict`, `align-msa-server`, `train` | [live] |
| `setup_openfold` | `openfold3.setup_openfold:main` | downloads weights + CCD, writes `ckpt_root` (section 4) | [source] |
| `validate-openfold3-rocm` | `openfold3.entry_points.validate_rocm:main` | no options; AMD ROCm environment check printing PASS/FAIL | [source] |

## 2. `run_openfold predict` (`openfold-3@v0.5.0:openfold3/run_openfold.py`)

| Flag (both spellings accepted) | Type | Code default → effective | Notes | |
|---|---|---|---|---|
| `--query-json`, `--query_json` | FILE, must exist | **required** | Query JSON: [04_input_query_format.md](04_input_query_format.md) | [live] |
| `--inference-ckpt-path`, `--inference_ckpt_path` | PATH (file or dir), must exist | None → `<param dir>/of3-ob-2025-06-30-174k.pt` | param dir = path in `$OPENFOLD_CACHE/ckpt_root`, else `$OPENFOLD_CACHE`. Help says "will attempt to find or **download**": v0.5.0 does NOT download, it raises (trap 4) | [live] |
| `--inference-ckpt-name`, `--inference_ckpt_name` | TEXT | None → `openbind-2025-06-30-174k` | Used only without a path. Names incompatible with the installed version (preview `openfold3-p2-155k`, `-p2-145k`, `-p1` on 0.5.0) raise [source] | [live] |
| `--num-diffusion-samples`, `--num_diffusion_samples` | INTEGER | None → **5** | Structures per seed | [live] |
| `--num-model-seeds`, `--num_model_seeds` | INTEGER | None → runner-YAML `experiment_settings.seeds`, else `[42]` | Given N, the seeds are N draws after `random.seed(42)`, not 42, 43, …: `--num-model-seeds 1` writes `seed_2746317213/` [source] | [live] |
| `--runner-yaml`, `--runner_yaml` | FILE, must exist | None | Deep-merged over `$OPENFOLD_CACHE/runner.yml` if that file exists | [live] |
| `--use-msa-server`, `--use_msa_server` | BOOLEAN, **takes a value** | None → runner YAML → **True** | True sends the query's protein sequences to `https://api.colabfold.com` (an RNA chain without MSA files then gets no MSA features; 07 §2). Unpublished sequence: `false` + precomputed MSAs, or single-sequence ([07_msa_templates_weights.md](07_msa_templates_weights.md)) | [live] |
| `--use-templates`, `--use_templates` | BOOLEAN, takes a value | None → runner YAML → **True** | `false` on a query that still has template keys fails (trap 13) | [live] |
| `--output-dir`, `--output_dir` | PATH | None → runner YAML → `./` | Omitted = writes into the current directory; created if missing | [live] |
| `--use_tf32` (**underscore only**) | BOOLEAN | **True** | `torch.set_float32_matmul_precision("high")`. `--use-tf32` → rc 2 `No such option '--use-tf32'` [live] | [live] |

BOOLEAN values (click 8.4.2 in the kit image, [live]): `true|false`, `1|0`, `yes|no`, `on|off`, `t|f`, `y|n`. Write
`true` / `false`. Other defaults when nothing overrides them [source]: 3 recycles, 200 diffusion steps, `predict` preset
(`model_setting_presets.yml` at v0.5.0 has `train`, `predict`, `low_mem`, `mps`).

**At upstream 0.4.1** (the legacy kit's pin) [source]: `--use-msa-server` / `--use-templates` default to `True` in the CLI itself
(the runner YAML cannot turn them off); `--use_tf32` does not exist; `setup_openfold` is interactive only.

## 3. `run_openfold align-msa-server` — MSAs only, no model, no GPU

| Flag | Type | Default | |
|---|---|---|---|
| `--query-json`, `--query_json` | FILE, must exist | required | [source] |
| `--output-dir`, `--output_dir` | DIR | required | [source] |
| `--msa-computation-settings-yaml`, `--msa_computation_settings_yaml` | FILE | None | [source] |

Sends the protein sequences of every query to the ColabFold server and template-hit PDB ids to RCSB (same privacy boundary as
`--use-msa-server true`, 07 §2), saves the
alignments under `--output-dir`, and writes `<output-dir>/query_msa.json`: the same queries with alignment paths filled in — feed
it to `predict --use-msa-server false`. Per-run scratch `$TMPDIR/of3-of-<user>/msa-<user>-<time>-<hex>/`, removed at the end.
Settings YAML keys (`MsaComputationSettings`, unknown keys rejected): `msa_file_format` (`npz`|`a3m`, default `npz`),
`server_url` (default `https://api.colabfold.com`; point it at a self-hosted MMseqs2 server), `server_user_agent` (`openfold`),
`save_mappings` (true), `save_colabfold_outputs` (true), `colabfold_output_dir`, `cleanup_msa_dir` (true). `msa_output_directory`
must equal `--output-dir` or be absent (else ValueError); `save_openfold_outputs` is forced true. The command appears in the
live group help [live]; its options are [source].

## 4. `setup_openfold` (`openfold-3@v0.5.0:openfold3/setup_openfold.py`)

| Invocation | Effect | |
|---|---|---|
| `setup_openfold` | Interactive prompts (cache dir, param dir, which weights, force, tests) | [source] |
| `setup_openfold --non-interactive` | All defaults: cache **and** params in `~/.openfold3`, default checkpoint, no tests. **Ignores `$OPENFOLD_CACHE`** | [source] |
| `setup_openfold --config setup.json` | Non-interactive from a JSON `OpenFoldSetupConfig`; wins over `--non-interactive` | [source] |

| Config JSON field | Default | Meaning |
|---|---|---|
| `openfold_cache` | `~/.openfold3` | Cache root; `ckpt_root` and `setup_config.json` are written here |
| `param_directory` | `~/.openfold3` | Where checkpoints land; its path is written to `<openfold_cache>/ckpt_root` |
| `selected_parameters` | `"default"` | `"default"` (OpenBind-0), `"all"` (every non-legacy entry), or one registry name |
| `force_download_parameters` | `false` | Re-download even if present |
| `run_integration_tests` | `false` | Runs upstream's inference tests; needs `pytest` (`openfold3[dev]`), else downgraded with a warning |

Every invocation downloads from public S3 (`openfold3-data`, key `openfold3-parameters/<file>`) without a further prompt and
refreshes the CCD inside the installed `biotite` package; it never writes `runner.yml`. Needs network and explicit user
approval (≈2.3 GB). Behaviour, example JSON and checksum: [02_install_and_environment.md](02_install_and_environment.md).

## 5. `run_openfold train`

Training from a prepared dataset cache (`--runner-yaml` required, `--seed`, `--data-seed`, `--use_tf32` default false). Out of
scope for this skill [source].

## 6. Kit entry point `run.sh pred | check | warm | install`

`bash run.sh <verb> …` from the kit directory, or `apptainer run --nv <image>.sif <verb> …` (the runscript does
`cd /kit/openfold3_ob0` first, so pass **absolute** paths). `run.sh` itself takes the verb, `--config` and `--mode` (as
`--opt V` or `--opt=V`, anywhere in argv); everything else goes to `python -m openfold3_ob0_opt <verb>` (argparse: an option
not registered for that verb exits 2, e.g. `unrecognized arguments: --use_msa_server false` [live]). Bare `run.sh` and
`run.sh --version` print the usage and exit 2 [live]; the version is `python -m openfold3_ob0_opt --version` [live].

| Verb | What it does | |
|---|---|---|
| `pred` | ONE `run_openfold predict` call on one query JSON under the mode (`--mode off` = stock in a clean subprocess). Exception: `big` on a query set straddling its item gate (1 401 polymer tokens on A100/H100) runs as two calls [docs] | [live] |
| `check` | Dry run: resolves the mode, pins, GPU gate; prints `DRY-RUN mode=…`; rc 0 even with `gpu=none` on a GPU-less node — not a GPU proof. Not side-effect free: with a checkpoint named it re-hashes it (2.3 GB read) and rewrites the digest memo; `run.sh` may create its JIT root | [live] |
| `warm` | One public-input prediction (barnase–barstar; forces MSA server off, templates off, 1 seed, 1 sample) to build JIT caches. `warm --mode off` → rc 2 [live] | [live] |
| `install` | Editable install of kit + shared core, pinned upstream wheel/source, pin check, CCD into Biotite; `--weights DIR` also fetches/verifies the checkpoint. `install --config …` / `--mode …` → rc 2 [live] | [live] |

Options per verb. Spellings are exactly those registered; "hyphen only" means the underscore form exits 2.

| Option | Verbs | `openfold3_ob0` (0.5.0) | `openfold3` (0.4.1 kit; [source]) | Label (ob0) |
|---|---|---|---|---|
| `--config a100\|h100\|h200\|b200\|b300` | pred check warm | sources `configs/<card>.env` (deployment only); missing file → rc 2 | same five cards | [live] |
| `--mode exact\|fast\|big\|off` | pred check warm | else `$OPENFOLD3_OB0_OPT`, else **`fast`**; unknown mode → rc 2 | else `$OPENFOLD3_OPT`, else `fast` | [live] |
| `--n_gpu 1\|2\|4\|8` (underscore only) | pred check | 2/4/8 only with `--mode big`, GPUs of one host; else rc 2. Default `$OPENFOLD3_OB0_OPT_N_GPU`, else 1. `warm` accepts it and ignores it | same (`$OPENFOLD3_OPT_N_GPU`) | [live] |
| `--query-json`, `--query_json` | pred | required | same | [live] |
| `--output-dir`, `--output_dir` | pred | **required** (upstream: optional) | same | [live] |
| `--num-model-seeds N` (hyphen only) | pred | passed through; omitted → upstream default | same | [live] |
| `--num-diffusion-samples S` (hyphen only) | pred | passed through; omitted → 5 | same | [live] |
| `--use-msa-server true\|false` (hyphen only) | pred | omitted → upstream **True** (public server) | same | [live] |
| `--use-templates true\|false` (hyphen only) | pred | omitted → upstream True | same | [live] |
| `--runner-yaml Y` (hyphen only, repeatable) | pred check | overlay on the mode's configuration, merged in order, `off` included; on `exact`/`fast`/`big` the mode's keys win (a DS4Sci key is overridden, named on a `note:` line [live]); on `off` your keys win. Missing file → rc 2 | same | [live] |
| `--det 0\|1` | pred check | default 0; anything else → rc 2 [live]. `1` = deterministic recipe; `exact --det 1` == `off --det 1` byte for byte | same | [live] |
| `--no-compile` | pred check warm | accepted **no-op** (no mode compiles) | same | [live] |
| `--ckpt`, `--inference-ckpt-path` (no underscore form) | pred check warm | default `$OPENFOLD3_OB0_CKPT`; hashed against the pinned sha256 (other bytes: WARNING, proceeds); absent file → rc 2 [live] | default `$OPENFOLD3_CKPT` | [source] |
| `--inference-ckpt-name`, `--inference_ckpt_name` | pred | registry name resolved by upstream under `$OPENFOLD_CACHE`, not hashed; wins over `$OPENFOLD3_OB0_CKPT`; with `--ckpt` → rc 2 [live] | absent | [source] |
| `--use_tf32`, `--use-tf32` | pred | passed through as upstream `--use_tf32` | absent | [source] |
| `--z-dtype bf16\|fp32`, `--conf-dtype bf16\|fp32` | pred check (warm: accepted, not applied) | override the mode's dtype; `--z-dtype bf16 --conf-dtype fp32` → rc 3 [live]: for fp32 confidence pass `--z-dtype fp32` too | absent | [source] |
| `--graphs-max-tokens N\|always\|0\|off` | pred check (warm: accepted, not applied) | sampler CUDA-graph size cap (`0`/`off`/`never` = never capture) | same | [source] |
| `--allow-template-drop` (flag) | pred | accept exit 5 as 0 (recorded) | same | [source] |
| `--upstream-fix ID[,ID]` | pred warm | no fix registered: every ID → rc 2 (`unknown upstream fix … known: none`) [live] | `OF3-001` (needs `--use-templates true`, else rc 2) | [live] |
| `--json FILE` | check | write the dry-run report | same | [source] |
| `--out DIR` | warm | required | same | [live] |
| `--tiling 1to1…6to6[,…]` | warm | public input size, default `1to1` (199 tokens); `6to6` = 1 194 | same | [source] |
| `--weights DIR` / `--weights=DIR` | install | fetch the pinned checkpoint into DIR if absent, else sha256-check | same | [live] |
| `--ccd FILE`, `--wheel FILE`, `--src TARBALL` | install | offline copies of the CCD / pinned wheel / pinned source, each sha256-checked | **absent** (install takes only `--weights`) | [live] |

There is no `--allow-partial` (or similar): a partial mode is rc 3 by design. To run a mode without a lever, name it in
`MODEL_OPT_LEVERS_OFF` (the `ACTIVE` line then shows `levers_off=…`; details in 06 §11).

## 7. Environment variables

| Variable | Read by | Default | Effect | |
|---|---|---|---|---|
| `OPENFOLD_CACHE` | upstream | `~/.openfold3/` | Checkpoint root via the one-line `ckpt_root` file (written on first use if absent); a `runner.yml` there is merged into every predict. Kit: defaults to the checkpoint's directory; the kit passes a checkpoint path, so `ckpt_root` is unused unless you pass `--inference-ckpt-name` | [source] |
| `TMPDIR` | upstream MSA client; kit `run.sh` | system tmp | MSA scratch `$TMPDIR/of3-of-<user>/`; kit's private JIT root `${TMPDIR:-/tmp}/model_opt_jit-uid<uid>` | [source] |
| `OPENFOLD3_OB0_CKPT` (`OPENFOLD3_CKPT` in 0.4.1 kit) | kit | none | **Required** unless `--ckpt` (or, for `pred`, `--inference-ckpt-name`); `pred`/`warm` exit 2 without it | [live] |
| `OPENFOLD3_OB0_OPT` (`OPENFOLD3_OPT`) | kit + its `.pth` hook | unset | Mode when `--mode` absent. Any mode other than `off` also **arms the kit inside a plain `run_openfold predict`** in that environment (trap 10); `off` installs no hook; an unsupported value is refused (rc 3) | [live] [source] |
| `OPENFOLD3_OB0_OPT_N_GPU`, `…_GRAPHS_MAX_TOKENS`, `…_Z_DTYPE`, `…_CONF_DTYPE` | kit | 1 / per mode | Environment forms of `--n_gpu`, `--graphs-max-tokens`, `--z-dtype`, `--conf-dtype` (flag wins) | [docs] |
| `OPENFOLD3_OB0_OPT_ROLLOUT_MIN_TOKENS` | kit `fast`/`big` | 0 (no gate: bf16 roll-out at every size) | Opt-in threshold (all tokens): inputs below it keep upstream's fp32 roll-out, counted `gated=`. Kit `STOCK.md` and a `modes.py` comment say 600; the code (`cells/rollout.py` `MIN_TOKENS_DEFAULT = 0`) and live censuses (`min_tokens=0 gated=0`) say 0 | [source] [live] |
| `OF3O_MIN_TOKENS` | kit `big` | 1 401 (A100, H100, others) | Item gate in polymer tokens; `<int>` or `none` (always engaged) | [source] |
| `OPENFOLD3_OB0_OPT_REACH_GATE` | kit `big` | 4 500 | Reach gate in polymer tokens; `<int>` or `none` (never) | [source] |
| `MODEL_OPT_LEVERS_OFF` | kit | unset | Comma list of lever names to leave off for one run | [docs] |
| `MODEL_OPT_JIT_ROOT` | kit | `${TMPDIR:-/tmp}/model_opt_jit-uid<uid>` (0700) | Compiled-kernel cache root; keep node-local, never in an inode-limited home | [live] |
| `MODEL_OPT_STACK_KEY` | kit | probed, e.g. `torch2.10.0-cu128-sm80`; `unknown` without a GPU | Cache key; preset it to source a card file on a GPU-less node | [live] |
| `TRITON_CACHE_DIR`, `TORCH_EXTENSIONS_DIR` | Triton / torch | `$MODEL_OPT_JIT_ROOT/<stack key>/{triton,torch_extensions}` when a card file is sourced with the root set | Preset value wins; otherwise Triton uses `~/.triton/cache` | [docs] |
| `MODEL_OPT`, `MODEL_OPT_TARGET_GPU`, `PYTHONDONTWRITEBYTECODE=1` | kit | set by `run.sh` / the card file | Kit directory; target card (`A100` … `B300`; a mismatch with the real card is a note); no `.pyc` | [source] |
| `XDG_CACHE_HOME` | kit | `~/.cache` | Weights digest memo `$XDG_CACHE_HOME/openfold3_ob0_opt/weights_digests.json` | [source] |
| `OPT_CORE_VERDICT_DIR` | shared core | JIT root, then XDG, home, tmp | Stamps of the one-time kernel self-check; `0`/`off` = re-check every process | [source] |
| `MODEL_OPT_JIT_IMAGE`, `MODEL_OPT_JIT_SEED_MAX_FILES` | kit `run.sh` | `/opt/jit_cache` / 5000 | Image cache to seed from; seed size limit | [source] |
| `OF3TP_ADDR`, `OF3TP_PORT`, `OF3TP_CHUNK`, `OF3TP_STRUCTURE_FIRST`, `OF3TP_DATA_FORM` | kit `big --n_gpu` | loopback, free port, chunk plan, 1, `rank0_bcast` | Rank rendezvous; chunk override; structure-first write; who featurises (06 §5) | [source] |

Set by the kit itself, do not set by hand: `CUBLAS_WORKSPACE_CONFIG` (`--det 1`), `PYTORCH_CUDA_ALLOC_CONF` (on the `fast`
line [live]) and the per-lever switches. The `--mode off` stock subprocess strips every name starting with `OF3_`, `OF3T_`,
`OF3O_`, `OF3TP_`, `BFTP_`, `ROWPAIR_`, `FPF_TRIMUL_V4_`, `OPENFOLD3_OPT`, `OPENFOLD3_OB0_OPT`, `CUBLAS_WORKSPACE_CONFIG`,
`CUDA_MPS_`, `CUTLASS_PATH`, `CUEQ_` (`stock/PINS.json` `stock_environment`), except upstream's own `OF3_TRITON_DYNAMIC_SHAPES`
/ `OF3_TRITON_EXP2`, which pass through. An `OPENFOLD3_OB0_OPT*` name the package does not declare, or an unsupported value, is
refused (rc 3) at interpreter start in any Python process of the environment [live]. Under `apptainer --cleanenv` or a
wrapper, forward by prefix (`OPENFOLD3_OB0_OPT*`, `OF3TP_*`, `OF3O_*`, `MODEL_OPT_*`) plus the single names above, or the
container silently runs without them [live].

## 8. Exit codes

| rc | Upstream `run_openfold` / `setup_openfold` | Kit `run.sh` (both kits) |
|---|---|---|
| 0 | success; also when queries failed or ran out of memory inside predict (caught per query: `summary.txt`, `logs/predict_err_rank<r>.log`) [source] | ok; `--allow-template-drop` acceptance; `check` DRY-RUN ok (also with `gpu=none`) |
| 1 | uncaught Python exception: missing default checkpoint, schema-invalid query JSON, errors outside the per-query step; setup: bad interactive choice, failed tests | prediction failed, incl. `incomplete` (fewer `*_model.cif` than queries × seeds × samples, or confidences not written); pip failure in `install` |
| 2 | click usage error: unknown option, BOOLEAN without a value, `--query-json` / `--runner-yaml` / `--inference-ckpt-path` path missing | usage [live unless noted]: unknown verb/option or underscore spelling, `--det` not 0/1, unknown mode, `--mode` ≠ set mode variable, `--n_gpu` > 1 without `big` or P ∉ {2, 4, 8}, `install --config/--mode`, `warm --mode off`, no or missing checkpoint, `--ckpt` + `--inference-ckpt-name`, unknown `--upstream-fix`, missing config file, missing `--runner-yaml` file [source] |
| 3 | — | NOT ACTIVE: pins not met, package or core missing, env-route hook not live, partial line (a lever unavailable), conflicting switches (e.g. `--z-dtype bf16 --conf-dtype fp32` [live]), undeclared `OPENFOLD3_OB0_OPT*` variable [live], card below cc 8.0, fewer visible GPUs than `--n_gpu` (`pred`), ranks ≠ P, `--mode off` DS4Sci runner YAML without DeepSpeed's `evoformer_attn` op; `install` with no `python` or a failed pin check |
| 5 | — | declared templates dropped before the model (`--allow-template-drop` → 0; remove template keys for an intentionally untemplated query) |

rc 3 and 5 are results, not crashes: never wrap kit calls in `set -e`; branch on `$?` and grep stderr for the verdict line
`pred --mode <m>: exit rule -> <rc> (…)`, e.g. `(ok; structures 5/5; templates_dropped=0; partial=False; …)` [live] (LEVER
census lines follow it, so it is not the last line).
The 0.4.1 kit's `run.sh` header omits 5, but its CLI defines it too [source]. rc 3 causes and fixes: 06 §8.

## 9. Known traps

1. **Booleans take a value.** `--use-msa-server false`, never a bare `--use-msa-server` (rc 2: `Option '--use-msa-server'
   requires an argument.`; before another flag: `'--output-dir' is not a valid boolean`) [live]. Docs examples showing a bare
   flag are wrong.
2. **The MSA server is ON unless you say otherwise**, in upstream and in kit `pred` (the kit passes nothing when omitted).
   Always emit `--use-msa-server false` unless the user approved the public server or the query carries MSAs.
3. **Spellings differ between layers.** Upstream accepts hyphen and underscore for everything except `--use_tf32`
   (underscore only). The kits accept underscores only for `--query_json`, `--output_dir`, `--inference_ckpt_name`,
   `--use_tf32`, and `--n_gpu` is underscore-only. `run.sh pred --use_msa_server false` and `run_openfold predict
   --use-tf32 false` both exit 2 [live].
4. **Help text vs code:** `--inference-ckpt-path` "will attempt to … download" — v0.5.0 raises `Default checkpoint … not found
   in <dir>, cowardly refusing to perform inference` (rc 1) [source]. Run `setup_openfold` or `run.sh install --weights DIR` first.
5. **`run_openfold --help` can show almost nothing.** On a GPU node the kit image printed only
   `usage: run_openfold [-h] [--disable-cutlass-package-imports]` (an import-time argparse in the bundled `cutlass_library`
   takes over `--help`); on a GPU-less node it printed the three subcommands [live]. Whether `predict --help` is also hijacked
   on a GPU node is [unverified]: capture help on a CPU node, or use this file.
6. **`setup_openfold --non-interactive` ignores `$OPENFOLD_CACHE`** and fills `~/.openfold3`; use `--config` (section 4).
7. **`run.sh install` rejects `--config` / `--mode`** (rc 2 [live]), whatever README prose suggests; the 0.4.1 kit's
   install has only `--weights`.
8. **The kit passes through only what it registers.** New or unlisted upstream flags exit 2; change model settings with
   `--runner-yaml` overlays. In the other direction, plain `run_openfold predict` rejects kit flags (`--det`, `--mode`, …) with rc 2.
9. **Mode vs environment disagreement is refused:** `--mode exact` while `OPENFOLD3_OB0_OPT=fast` is exported → rc 2
   (`--mode exact disagrees with OPENFOLD3_OB0_OPT=fast`) [live]. Unset one.
10. **An exported `OPENFOLD3_OB0_OPT` turns "stock" into a kit run.** The installed `.pth` hook arms any mode but `off` in
    any `run_openfold` process [live]. For a stock baseline use `run.sh pred --mode off` or `unset OPENFOLD3_OB0_OPT`.
11. **Checkpoint absent or wrong:** upstream rc 1 (trap 4); kit rc 2 (`no checkpoint: pass --ckpt or set OPENFOLD3_OB0_CKPT`,
    or `no such checkpoint: <path>`) [live]. Preview-2 weights (`of3-p2-155k.pt`) do not run on 0.5.0: they belong to the 0.4.1 kit.
12. **`check` rc 0 proves nothing about the GPU** on a node without one (`gpu=none`) [live]. Run `check` on the GPU node.
13. **`--use-templates false` on a query that still has template keys** fails inside upstream (`UnpicklingError`) [docs];
    remove the keys instead.
14. **`--num-model-seeds 1` is not the default seed**: directories become `seed_2746317213/`, not `seed_42/` [source].
15. **Omitting upstream `--output-dir`** writes into the current directory; always pass it.
16. **`--det` accepts only `0|1`; `--n_gpu 2|4|8` only with `--mode big`** on one host: rc 2 under exact/fast/off or for
    another P [live], rc 3 with fewer visible GPUs [source]. `--no-compile` changes nothing in either kit.
