# 00 — Scope, safety model, trust ladder, license

## What this skill is (v1.0, installation-scoped)

A **config-first, executing** assistant for *installing and setting up*
ModelAngelo (`3dem/model-angelo`). It explains the tool's environment needs,
decides whether a *target* machine can run it, chooses an install route, runs the
official installer and weight download, and verifies the result — **on the local
machine, with a matching config, and only after confirming each mutating
action.** The machine the skill runs on may be a dev host, not the runtime; it
never assumes (the user configures per device later).

### In scope
- Explain ModelAngelo's purpose, environment requirements, weights, and the
  install routes from captured sources.
- Enforce a config/environment session before machine-specific advice or any
  action (`references/02`).
- Inspect (or guide inspection of) a target: OS/arch, Python/conda/mamba, `git`,
  an existing `model_angelo` install, NVIDIA GPU/CUDA, disk free, `TORCH_HOME`,
  and `hhblits` (optional). Classify config `state`.
- **Install** ModelAngelo via the official `install_script.sh`, wrapped for a
  pinned tag and a chosen route (`scripts/install_modelangelo.sh`) — with
  confirmation.
- **Download** the ~10 GB weights + ESM-1b language model — with confirmation
  (network + write) and a planned `TORCH_HOME`.
- **Verify** the install (`scripts/verify_modelangelo.sh`): version, subcommand
  help, torch+CUDA, dependency imports, weight-cache location.
- Explain and fix install/environment failure modes (`references/06`).

### Out of scope / never do
- **Do not run production model-building jobs.** This skill stops at a verified
  install + a smoke test (`model_angelo build -h`, `--version`). Actual `build` /
  `build_no_seq` / `hmm_search` runs on real maps are a *separate* concern,
  deferred until a target and a known-good fixture are validated. (`build -h` is
  fine; `build -v map.mrc ...` is not this skill's job.)
- **ModelAngelo is not a validation tool.** Never present a built `.cif`, or its
  per-residue confidence/B-factor, as validated structure. Always route to
  refinement (Servalcat/Phenix) + independent validation
  (MolProbity/Q-score/EMRinger/manual inspection).
- **No install, clone, weight download, or `chmod` without explicit user
  confirmation** for that specific action, with the command echoed first.
- **Never download the user's maps or bundle map data into the skill.** This
  skill installs *software and weights* only.
- No site `sbatch`/`module` lines as fact until a site config captures that
  environment (module names, partitions, GPU types differ per cluster).

### The confirmation model

The skill **acts**, but every mutating or network action is gated on (a) a
current, identity-matched config in the right `state`, and (b) explicit user
go-ahead for that action, with the command echoed back first:

| Action | Gate | How |
|---|---|---|
| Read environment facts | none (read-only) | `scripts/modelangelo_env_probe.py` (default run is side-effect-free) |
| Install / build env | confirm + Linux host + `state: ready`/`partial` | `scripts/install_modelangelo.sh` (refuses without `--yes`/prompt) |
| Download weights (~10 GB) | confirm + `TORCH_HOME` + ≥10 GB free | `install_modelangelo.sh --download-weights` or `model_angelo setup_weights` |
| Verify install | confirm (cheap, but imports torch) | `scripts/verify_modelangelo.sh` |
| HPC/container job wiring | confirm + site config | described only; not auto-created (`references/03`, `07`) |

"Plan it" ≠ "run it". Do not cross a gate silently.

## Source trust ladder (precedence when sources conflict)

1. **Live target behavior** — `model_angelo --version`/`-h`, `conda`/`git`
   presence, `nvidia-smi`, actual installed package + weight files **on the
   configured target**. Authoritative for *that* machine.
2. **Pinned source** at tag `v1.0.18`, commit `994945b` — `install_script.sh`,
   `setup.py` pins, the argparse surface, `torch_utils.py` weight logic.
   Authoritative for "what the code does" when the README is vaguer.
3. **Official GitHub README** (v1.0.18) — install narrative, usage examples,
   compute requirements, FAQs.
4. **First-party operational docs** — RELION 5 ModelBuilding, CCP-EM tutorial.
5. **Managed-distribution docs** — SBGrid title page, NIH Biowulf app page (for
   route patterns; site specifics are not universal).
6. **Papers** (Nature 2024, ICLR 2023) — method rationale and limits, **not**
   CLI/flags/versions.
7. **Community blogs / search snippets** — navigation only; never the source of
   truth for flags or paths.

**Conflicts to surface:** `setup_weights`' own CLI default is `--bundle-name
original`, but `build`/`refine` default to `nucleotides` and `build_no_seq` to
`nucleotides_no_seq`; `install_script.sh --download-weights` fetches the
`nucleotides*` pair, not `original`. A bare `model_angelo setup_weights` fetches
the wrong bundle for the default build path (`references/04`). Also, only the
`nucleotides`/`nucleotides_no_seq` bundles ship runnable model definitions in
this tree.

## License & compliance

- **MIT License** (repo `LICENSE`, Kiarash Jamali, 2022). Permits
  use/modification/redistribution with attribution; provided "as is."
- This skill **redistributes no ModelAngelo code** — it installs the upstream
  package from the official GitHub repo and downloads weights from the upstream
  Zenodo / FAIR-ESM records.

## Privacy & data safety

- The skill installs software and weights only. It does not upload, download,
  move, or delete the user's cryo-EM maps.
- **`configs/site_config.local.md` is per-environment and private** (hostname,
  arch, GPU, paths). Git-ignored and excluded from any packaged copy. Only
  `configs/site_config.template.md` ships. The probe redacts the home path.
- The weight download is **network + ~10 GB write**; it requires explicit
  confirmation and a destination.
