---
name: "cryoatom"
description: "Portable, config-first assistant for CryoAtom2 — automatic atomic model building for proteins, RNA, DNA and protein-nucleic-acid complexes from cryo-EM density maps. Carries no host facts: it probes the machine it is running on, writes a site config, and only then makes machine-specific claims. Use whenever the user wants to install, configure, port, understand, plan, or run CryoAtom/CryoAtom2 on any system: standing up a new install (container or native conda), staging and pinning the six model weights, writing a build command, choosing sequence vs no-sequence mode, picking -pf/-nf databases, reading the output mmCIF and its confidence field, comparing against ModelAngelo, or troubleshooting weights/CUDA/OOM/getp errors. It never installs, downloads, or runs anything without explicit per-action confirmation. Triggers: cryoatom, CryoAtom2, cryoatom build, install cryoatom on a new cluster, atomic model building from cryo-EM map, protein-nucleic acid model building, RUNet/CryoNet checkpoints, CryoAtom weight cache."
---

# CryoAtom2 — portable skill

CryoAtom2 builds atomic models for proteins, nucleic acids, and their complexes
directly from a cryo-EM density map, with or without sequence input. Its
post-processing is adapted from ModelAngelo.

**This package contains no host facts.** No hostname, account, partition, home
path, or image hash is baked in. Every machine-specific statement must come from
a *site config* generated on the target machine. State the evidence level and
the version before any implementation guidance, and never present a predicted
model as experimentally validated.

## 1. Resolve the site config before any host-specific claim

```bash
# resolution order
$CRYOATOM_SKILL_CONFIG
${XDG_CONFIG_HOME:-~/.config}/cryoatom-skill/site-config.json
```

- Config present → validate it, then speak within its state (§2).
  ```bash
  python3 scripts/cryoatom_env_probe.py --validate-config <path>
  ```
- Config absent → run the read-only probe and show the result. This inspects
  PATH, host identity, container runtime, scheduler, GPUs, and the weight cache.
  It runs nothing from CryoAtom unless `--live-version` is passed (that only
  executes `cryoatom --version`, which never opens a checkpoint).
  ```bash
  python3 scripts/cryoatom_env_probe.py            # read-only; writes nothing
  ```
  To *record* what it found, re-run it with the full flag set for this machine
  (`--route`, `--image`/`--conda-env-prefix`, `--launcher`, `--weights-cache`,
  `--scheduler`, …) plus `--output`. The probe builds the config from its
  arguments and never merges into an existing one, so a short command yields a
  thin config — see `references/01_configuration.md` and
  `references/02_install_routes.md` § 6.
- Nothing installed yet → this is an **install** request. Go to
  `references/02_install_routes.md` and `templates/install_plan.md`.

Configuration records facts. It never grants permission.

## 2. The state controls what may be claimed

| State | Meaning | What you may do |
|---|---|---|
| `ready` | Launcher runs, version matches the pin, all six weights verified, and a public-fixture run passed on this host | Plan concrete commands with real paths; execute only after per-action approval |
| `probed` | Facts collected, but some evidence is missing (no live version, no fixture, GPU not visible from a login node) | Give gap-aware plans; name the missing gate; do not claim run readiness |
| `blocked` | A required runtime, launcher, image, or weight file is absent or unusable | Explain the blocker and route to the install or recovery section; do not improvise |
| `stale` | Hostname, version, image hash, or weight pin no longer matches what was recorded | Make no host-specific claim from it; regenerate the config per `references/01_configuration.md` § Re-probe when, passing the full flag set |
| `unknown` | No trustworthy config | General guidance only; no host-specific claim |

A timestamp is not freshness. Re-probe after any image rebuild, weight change,
scheduler change, or host change.

## 3. Route the request

| Request | Read |
|---|---|
| What this skill may and may not do; escalation | `references/00_scope_and_trust.md` |
| Config path, schema, state machine, portability | `references/01_configuration.md` |
| **Installing on a new system** (container / native / module) | `references/02_install_routes.md` |
| Flags, inputs, outputs, the confidence field | `references/03_cli_and_outputs.md` |
| Version pin, v1 vs v2, hardware requirements | `references/04_versions_and_requirements.md` |
| Paper and benchmark interpretation | `references/05_scientific_evidence.md` |
| Licenses, TLS, network, cloud, data handling | `references/06_safety_privacy_licensing.md` |
| Day-to-day running, recovery table, performance | `references/07_operations_and_troubleshooting.md` |
| Install request | `templates/install_plan.md` |
| Readiness assessment | `templates/readiness_report.md` |
| Command request on a **`ready`** host | `templates/run_command_plan.md` |
| Command request on any other host | `templates/not_run_command_outline.md` |
| Validating this skill package | `scripts/validate_skill.py`, `examples/trigger_tests.md` |

## 4. Tools in this package

| Tool | Purpose | Writes anything? |
|---|---|---|
| `scripts/cryoatom_env_probe.py` | Probe the host, emit/validate the site config | Only with `--output` |
| `scripts/check_cryoatom_weights.py` | Verify the six weights by size or SHA-256 | No |
| `scripts/stage_cryoatom_weights.sh` | Download, lay out, pin, verify, link, fixture | Yes — needs confirmation |
| `scripts/cryoatom_launcher.sh` | Config-driven launcher (apptainer/singularity/docker/podman/native/module) | Creates a temp dir; the job it starts writes results |
| `scripts/render_job_template.py` | Fill a job template from the site config | Only with `--output` |
| `scripts/summarize_cryoatom_output.py` | Read-only summary of an output tree | No |
| `scripts/validate_skill.py` | Static + self-test validation of this package | No |
| `install/cryoatom.def` | Pinned Apptainer recipe (commit + tree verified in `%post`) | Build only |
| `install/Dockerfile` | The same recipe for Docker/Podman | Build only |

## 5. Response workflow

1. **State evidence level and version first.** Separate *verified on this host*
   (observed from this install, per the config) from *static source inspection*
   (read from the pinned code) from *preprint claim*. Anything in this package
   that is not in the site config is **not** host evidence.
2. **Check readiness before giving a runnable command** — the version check and
   the weight check, now, not remembered from earlier. Weight caches rot.
3. **For an install**, use `templates/install_plan.md`: pick a route, name the
   gates, get confirmation for each downloading or building step separately.
4. **For a command on a `ready` host**, use `templates/run_command_plan.md`:
   real paths from the config, a fresh isolated output directory, an explicit
   confirmation step before anything is submitted.
5. **For a command on any other host**, use
   `templates/not_run_command_outline.md` with its DO-NOT-EXECUTE banner.
6. **Never run without explicit confirmation.** Building an image, downloading
   ~5.1 GiB of weights, submitting a job, and writing into an output directory
   are four separate approvals.
7. **Keep the evidence tiers separate.** CryoAtom v1 is peer-reviewed and
   protein-focused. CryoAtom2's protein/RNA/DNA claims come from an unreviewed
   preprint that does not map to a code commit. Never call v2 RNA/DNA support
   peer reviewed, and never transfer a v1 result to a v2 runtime claim.
8. **Explain the output honestly.** The mmCIF B-factor column carries model
   confidence, not an experimental B-factor and not proof of correctness. A
   predicted model still needs density fit, geometry, and expert review.

## 6. Hard limits

- Never reuse an existing output directory. CryoAtom creates the directory with
  `exist_ok`, moves and replaces files under it, and deletes intermediates
  unless `-k` is given — a reused directory silently mixes runs.
- Never suggest `wget --no-check-certificate` or another TLS bypass. Upstream's
  `install.sh` uses one; it is not needed and must not be reintroduced.
- Never upload a map or sequence to Colab or any other service. That is a
  separate privacy/retention decision, not a convenience.
- Never invent flags. The verified flag set is in
  `references/03_cli_and_outputs.md`; there is no `--protein-fasta` and no
  `--hmm-db`.
- Never pass a partial sequence set. `-ps` alone on a map containing nucleic acid
  **silently deletes every nucleotide** — built, then masked out at write time,
  with no warning. Pass every class the map contains, or use the fully
  sequence-free mode. See `references/03_cli_and_outputs.md` § *A partial
  sequence set silently deletes the other polymer classes*.
- Never relax the pinned dependency set to make a build succeed. A pruned
  `pytorch=2.1.0=py3.9_cuda11.8_cudnn8.7.0_0` is a genuine upstream
  reproducibility failure and should be reported as one.
- Never write host facts, private paths, accounts, or sequences into this
  package. They belong in the external site config only.

## 7. Portability contract

Ship one canonical package; keep the filled site config outside it. Another
machine needs this package, a generated config, an install produced by
`references/02_install_routes.md`, and its own fixture run. Validation on one
machine never transfers to another.
