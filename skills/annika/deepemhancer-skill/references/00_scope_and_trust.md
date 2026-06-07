# 00 — Scope, safety model, trust ladder, license & privacy

## What this skill is (v1.0)

A **config-first, executing** assistant for DeepEMhancer (`rsanchezgarc/deepEMhancer`). It explains the tool, decides whether a *target* machine can run it, installs and configures the environment, and runs maps — **on the local machine, with the right config, and only after confirming each mutating action.** The machine it runs on may be a development host, not the runtime; it never assumes.

### In scope
- Explain DeepEMhancer's purpose, inputs, models, outputs, and limitations from captured sources.
- Enforce a config/environment session before machine-specific advice or any run (`references/02`).
- Inspect (or guide inspection of) a target: OS/arch, Python/conda, executable/package, TensorFlow/GPU/CUDA, model files, optional live CLI help.
- Classify config `state` (`ready`/`partial`/`blocked`/`unknown`/`stale`) with citations.
- **Install** a working DeepEMhancer environment with the verified recipe (`scripts/setup_deepemhancer_env.sh`, `references/09`) — with confirmation.
- **Download** model weights — with confirmation (network + ~705 MB).
- **Run** `deepemhancer` on the user's local map via `scripts/run_deepemhancer.sh` — with confirmation.
- Explain and fix failure modes (wrong input, missing models, stale flag names, TF/CUDA/cuDNN mismatch, GPU OOM, multi-GPU/batch bug, CryoSPARC env conflicts).

### Out of scope / never do
- **Never upload, copy, move, or delete the user's map data.** Maps are processed only in place on the local machine; nothing is sent to any external service. (This is permanent, not a version gate.)
- No map processing, install, model download, or scheduler/CryoSPARC job **without explicit user confirmation** for that specific action.
- No CryoSPARC wrapper-file creation / `chmod` / job submission, and no site `sbatch`/`module` lines, until a site config (`references/07`) captures that environment and the user confirms.
- No benchmark/performance claims beyond paper/README context; no guarantee that the output improves a map (`references/08`).

### The confirmation model (replaces the old read-only ladder)

The skill **acts**, but every mutating or heavyweight action is gated on (a) a current, identity-matched config in the right `state`, and (b) an explicit user go-ahead for that action, with the command echoed back first:

| Action | Gate | How |
|---|---|---|
| Read environment facts | none (read-only) | `scripts/deepemhancer_env_probe.py` (default run is side-effect-free) |
| Install / build env | confirm + a Linux host | `scripts/setup_deepemhancer_env.sh` (refuses without `--yes`/prompt) |
| Download models | confirm + destination | `setup_deepemhancer_env.sh --download-models` |
| Run a map (GPU) | confirm + `state: ready`; in `partial`, only after closing any TF/GPU/CUDA gap (re-probe to `ready`) — never run while those are untested or absent (EC-4) | `scripts/run_deepemhancer.sh` |
| CryoSPARC/HPC job | confirm + site config | described only; not auto-created (`references/07`) |

Do not cross a gate silently. "Plan it" ≠ "run it"; obtain the go-ahead.

## Source trust ladder (precedence when sources conflict)

1. **Live target behavior** — `deepemhancer --version`/`-h`, package metadata, TensorFlow/GPU check, actual model files **on the configured target**. Authoritative for *that* installed runtime. (Heavyweight; see `references/02`.)
2. **Pinned source** at commit `961f028ca609017990de4473ab368cf1787e8282` — parser/options/defaults and packaging. Authoritative for "what the code does" when README disagrees.
3. **Official GitHub README** — install/usage narrative and scientific caveats.
4. **Official package metadata** — Anaconda channel / conda `meta.yaml`, model-record metadata.
5. **Peer-reviewed paper** — scientific rationale, validation context, limitations. **Not** exact CLI/flags/versions.
6. **First-party integration docs** — CryoSPARC wrapper conventions.
7. **Community/HPC docs** — Biowulf etc. for failure modes/examples; **cross-check** against live help; never the source of truth for flags.
8. **LLM summaries / search snippets** — navigation only.

**Binding conflict to surface:** the README example uses `--deepLearningModelDir`; source/live help use `--deepLearningModelPath`. Source/live wins; flag the README example as stale rather than copying it. See `references/03`.

## License & compliance

- **Apache License 2.0** (SPDX `Apache-2.0`). Evidenced by the repository `LICENSE` ("Apache License, Version 2.0, January 2004"), `setup.py` (`license='Apache 2.0'`), and conda `meta.yaml` (`license: Apache 2.0`, `license_family: APACHE`). See `references/01`.
- Apache 2.0 permits use/modification/redistribution with attribution and license/NOTICE retention; provided "as is" without warranty. This skill redistributes **no** DeepEMhancer code — it only references behavior and installs the upstream package from its own distribution channels.

## Privacy & data safety

- **Cryo-EM maps may be unpublished or proprietary.** The skill never uploads, downloads, moves, deletes, or transmits map data; it processes maps only in place, locally. The probe and config touch only environment metadata, never map data.
- **`configs/site_config.local.md` is per-environment and private** (hostname, arch, GPU, paths). It is git-ignored and excluded from any packaged/installed copy of the skill. Only `configs/site_config.template.md` ships. See `references/02` and the repo `.gitignore`.
- The probe **redacts the home-directory path** from its output.
- The model-download action is **network + write**; it requires explicit confirmation and a destination, and is performed only via `setup_deepemhancer_env.sh --download-models`.

## Heavyweight-call warning (carry everywhere)

Any `deepemhancer` invocation and any `import tensorflow` loads the full TensorFlow/CUDA stack (pinned `config.py` does `import tensorflow as tf` at module top level; the entry point imports it transitively). These can be slow, can initialize a CUDA context, and can hang on a driver/TF mismatch. So:
- Never run them inline to "just check the version"; the probe isolates them in a timed subprocess with `CUDA_VISIBLE_DEVICES=""`, only on opt-in.
- A successful import/`--version` proves only that the **import chain loaded** — never that map processing will succeed or that a map will improve. Model loading and cube inference (a real run) exercise much more (e.g. the `keras_contrib` checkpoint path, `references/09`).
