---
name: cryolo-skill
description: >-
  Config-first assistant for SPHIRE-crYOLO, the cryo-EM particle picker. Use when
  the user asks whether/how to install, configure, or run crYOLO (cryolo_gui.py,
  cryolo_predict.py, training, general-model picking, config JSON, BOX/STAR/CBOX
  outputs), whether their machine (macOS/Apple Silicon, Linux, NVIDIA/CUDA) can run
  crYOLO, how to plan crYOLO commands, crYOLO licensing/commercial-use questions, or
  troubleshooting (GPU not used, slow picking). Before any concrete command,
  device/support claim, or workflow recommendation it REQUIRES reading or running a
  local environment/config probe. The skill is VALIDATED against crYOLO 1.9.9 on
  Linux + NVIDIA; on a probe verdict of supported/partial it emits concrete commands
  with the user's real paths and may run real jobs after explicit user confirmation;
  it still performs no blind installs or model downloads.
version: 1.0.0
license_note: >-
  This skill describes SPHIRE-crYOLO, which is distributed under a Complimentary
  Science Software License (non-commercial academic/research use only). This skill
  ships no crYOLO code or model weights. See references/07_safety_license_privacy.md.
---

# crYOLO skill (config-first, per-machine gated)

This skill helps reason about, configure, and run **SPHIRE-crYOLO** — a fast cryo-EM
particle picker. It is **config-first**: the local environment must be probed/read before
any machine-specific advice, concrete command, or job. It is **per-machine gated**: what it
will do (explain → emit concrete commands → run jobs) is decided by the local probe verdict
plus your explicit confirmation, never by a hardcoded assumption about any one host.

Factual ground truth has two layers, both authoritative:

- **Captured live `--help` + version** from an installed crYOLO **1.9.9**
  (the captured `*.help.txt` files and `_versions.txt`), plus a GPU smoke run. Every flag,
  default, subcommand, file format, and output-folder claim in this skill matches those
  captures and is marked **VALIDATED against crYOLO 1.9.9**.
- The captured source inventory in `references/01_source_map.md` (crYOLO docs
  `cryolo.readthedocs.io/en/stable/`, source pin `MPI-Dortmund/cryolo` tag `1.9.9` /
  commit `30039bde…`, fetched 2026-06-05) for facts the CLI help does not cover.

Anything in *neither* layer is a genuine **gap** and must be labeled, not invented.

---

## 0. STOP — the config-first gate (read this first, every time)

Before you give **any** of the following, you MUST have a current local config report:

- a concrete or runnable crYOLO command with the user's real paths,
- a claim that this machine *can*, *cannot*, *is supported*, or *is not supported* to run crYOLO,
- a recommendation of which crYOLO workflow to use here,
- device/GPU/CUDA/driver advice tied to this machine,
- actually launching a crYOLO config/train/predict/evaluation job.

**Gate procedure:**

1. Look for `configs/site_config.local.md` (or a JSON probe report the user points to).
2. If it is **missing**, or its `generated_at` is older than `stale_after_days` (default
   14) or older than the user's last hardware/OS/conda/crYOLO change → the config is
   **absent or stale**.
3. When absent/stale, you may **only**: (a) explain crYOLO at a high level from the
   references, and (b) **offer to run the read-only probe**:
   `python3 scripts/cryolo_env_probe.py --format markdown --output configs/site_config.local.md`
   (the probe is read-only — no installs, downloads, network calls, or jobs; see
   `scripts/cryolo_env_probe.py` header). Do **not** produce machine-specific content above
   until a current report exists or the user pastes one.
4. **Once a current report exists**, act on its `support_assessment.status`:
   - **supported / partial** → you may state suitability, recommend a workflow, and emit
     concrete commands with the user's real paths. You may **run** a config/train/predict/
     evaluation job *only after the user explicitly confirms* (see §3 and §5.6).
   - **blocked / unknown** → keep to explanation plus the sourced per-platform reason from
     the report (e.g. macOS is officially unsupported); do not emit run-here commands.
5. Never fabricate a config result. If you cannot read or generate one, say so and stop
   at high-level explanation.

What is **allowed without** a config report: general explanations of what crYOLO is,
what its workflows mean, what the license says, what file formats exist — all from the
references, all clearly marked as general (not machine-specific) guidance.

---

## 1. Support-status rule (do not get this wrong)

Official **installation requirements govern support status**. A crYOLO script that
merely *runs* locally does **not** make the configuration *supported*. The probe encodes
these rules and computes a verdict **per host** — treat the outcome as the probe's, not as
a fixed statement about any particular machine.

- Captured docs (installation page, fetched 2026-06-05) state verbatim: *"As the GPU
  accelerated version of tensorflow does not support MacOS, crYOLO does not support it
  either."* Officially supported OSes listed: Ubuntu 18.04/20.04, CentOS 7; Windows is
  "not tested … should run". Listed GPUs are all **NVIDIA**; crYOLO "depends on CUDA
  Toolkit and the cuDNN library." (See `references/02_config_session_and_environment.md`,
  installation docs **S1**.)
- Therefore when the probe runs **on macOS / Apple Silicon** it reports **officially
  unsupported**: Apple GPU / Metal / MPS is **not** CUDA and does not satisfy crYOLO's
  dependency. If a crYOLO build is somehow present and runs there, describe it as *"locally
  runnable but officially unsupported/untested"* — never "supported". This is a true,
  sourced per-platform fact, surfaced only as a probe-driven outcome.
- On **Linux + NVIDIA** the probe reports **supported** (the validation run used a Linux host
  with an NVIDIA GPU). The probe records the
  verdict in `support_assessment` (status: supported|partial|blocked|unknown) with a sourced
  reason for each.

---

## 2. Triggers / non-triggers

**Use this skill when** the user asks to: check if this machine can run crYOLO;
install/configure crYOLO; build a `config.json`; run general-model / trained-model
picking; train/refine a model; evaluate a model; understand BOX/STAR/CBOX/EMAN/DISTR/
CRYOSPARC outputs; plan or run a `cryolo_gui.py`/`cryolo_predict.py`/`cryolo_train.py`
command; export crYOLO picks to RELION (STAR) or cryoSPARC; understand crYOLO licensing
for academic vs commercial use; or troubleshoot GPU/CUDA/slow picking.

**Do not use / hand off when:** the task is unrelated to crYOLO; or it is generic
cryo-EM processing with no crYOLO step.

crYOLO ↔ RELION/cryoSPARC **interoperability is supported, not deferred**: crYOLO natively
writes RELION-style STAR (columns `_rlnCoordinateX`/`_rlnCoordinateY`, confirmed in
`out/STAR/synth_0001.star`) and a cryoSPARC coordinate export (predict.log line 15:
`Write cryoSPARC coordinates`; the `out/CRYOSPARC/` folder is created). See
`references/06_interoperability.md`.

---

## 3. Capability boundary (execution-capable, probe-gated)

| The skill MAY (probe supported/partial + your confirmation) | The skill must NOT |
|---|---|
| Read/run the read-only config probe (always allowed) | Install conda/pip packages or modify the env (no blind installs of system-level deps) |
| Explain crYOLO workflows from captured help + sources | Download general models / reference data / weights |
| State local suitability from `support_assessment` | Auto-launch the boxmanager/napari GUI |
| Emit **concrete commands with the user's real paths** | Run jobs without an explicit user confirmation |
| Run `config` / `train` / `predict` / `evaluation` jobs **after** the user confirms | Act on the user's private micrographs/data without confirmation |
| Export/convert picks the way crYOLO natively does (STAR, cryoSPARC) | Give legal guarantees; move/delete/upload user data |
| Route license/privacy questions to ref 07 | Run anything when the probe verdict is blocked/unknown |

**Execution model (replaces the old version ladder):** what the skill does is gated by
**(a) the per-machine probe verdict** and **(b) explicit user confirmation before touching
real data**.

1. No current report → high-level explanation only; offer the read-only probe.
2. Report = **blocked/unknown** → explanation + the sourced per-platform reason; no run-here
   commands.
3. Report = **supported/partial** → emit concrete commands with the user's real paths;
   describe exactly what a job will read/write.
4. User explicitly confirms → run the job (config/train/predict/evaluation). The probe
   itself never needs this confirmation because it is read-only.

There is no artificial "never execute" rule. The only hard stops are: blind installs/
downloads, GUI auto-launch, and acting on private data without confirmation.

---

## 4. Routing — question → reference

| User intent | Read |
|---|---|
| Scope, safety ladder, trust ladder | `references/00_scope_and_trust.md` |
| What sources back a claim? versions/pins | `references/01_source_map.md` |
| "Can this machine run crYOLO?" / config session / schema | `references/02_config_session_and_environment.md` |
| CLI scripts, flags, command templates | `references/03_cli_reference.md` |
| config.json fields, input/output formats, coordinates | `references/04_data_model_and_formats.md` |
| Picking / training / evaluation / visualization workflows | `references/05_core_workflows.md` |
| RELION / cryoSPARC / napari import-export | `references/06_interoperability.md` |
| License, commercial use, privacy, model-weight terms | `references/07_safety_license_privacy.md` |
| Benchmarks, papers, validation claims | `references/08_validation_and_benchmarks.md` |
| Errors, GPU-not-used, slow picking | `references/09_troubleshooting.md` |
| Step-by-step branching (gate, support, workflow choice) | `references/10_decision_trees.md` |

---

## 5. Hard authoring rules (apply to every answer)

1. **Captured help is the source of truth for the CLI.** Flags, defaults, subcommands,
   file formats, the meaning of positionals, and the output-folder layout are now
   **resolved** by the live captures and the smoke log — do not relabel them as gaps. The
   crYOLO front end is `cryolo_gui.py {config,train,predict,evaluation,boxmanager}`
   (`cryolo_gui.py.help.txt`); standalone `cryolo_predict.py`, `cryolo_train.py`,
   `cryolo_evaluation.py`, `janni_denoise.py {config,train,denoise}` all exist
   (`_versions.txt`). `config` positionals are exactly `config_out_path boxsize` — the
   integer is the **box size**, which crYOLO writes into `model.anchors`
   (`cryolo_gui.config.help.txt`; `config_cryolo.json` shows `"anchors": [160,160]`,
   `max_box_per_image` default 700). For anything the help *still* does not cover, say
   "not captured / source gap" — do not guess.
2. **Mark CLI behavior VALIDATED against crYOLO 1.9.9.** When you give a command, config
   field, or output path, mark it **VALIDATED against crYOLO 1.9.9** and cite the captured
   help file (e.g. `cryolo_predict.py.help.txt`, `cryolo_gui.config.help.txt`). Do not use
   "live-unverified" or "placeholder" — live `--help` is captured for this version.
3. **Cite.** Attach the source (captured help filename, docs page + fetch date, or the
   local config report) to each concrete claim.
4. **Support ≠ runs.** Apply §1; the verdict is the probe's per-host outcome.
5. **License + privacy.** For any install/use/commercial question, surface the
   non-commercial restriction and "not legal advice" from ref 07. Never package or download
   crYOLO weights or models — a general model such as `gmodel_phosnet_201912_N63.h5` is the
   user's own artifact to supply. Treat `configs/site_config.local.md` and any micrographs
   as local/private; never upload, move, delete, or convert user data.
6. **Jobs only after verdict + confirmation.** Run `config`/`train`/`predict`/`evaluation`
   only when the probe verdict is **supported/partial** AND the user explicitly confirms,
   and only after you have stated what the job reads/writes. The probe itself stays
   read-only and needs no confirmation. No GUI auto-launch.

---

## 6. The probe (read-only)

```bash
# Generate a local config report (read-only; writes only the output file):
python3 scripts/cryolo_env_probe.py --format markdown --output configs/site_config.local.md

# Machine-readable form:
python3 scripts/cryolo_env_probe.py --format json

# Opt-in version probe of an already-installed crYOLO (still no jobs):
python3 scripts/cryolo_env_probe.py --cryolo-exec --format markdown --output configs/site_config.local.md
```

The probe never installs, downloads, makes network calls, or starts crYOLO jobs/GUI;
by default it does not even execute crYOLO scripts, and `--cryolo-exec` only reads
`--version`/`--help` (still no jobs). It computes `support_assessment` **per host** and
redacts the home directory from path-like values. `configs/site_config.local.md` is
**local/private** — do not upload or commit it (see `.gitignore` and ref 07).

Running a real crYOLO job is a **separate, confirmed step** taken only after the probe
reports supported/partial (see §3) — the validated reference invocations were
`cryolo_gui.py config config_cryolo.json 160 --filter NONE` (config_gen.log) and
`cryolo_predict.py -c config_cryolo.json -w <general_model.h5> -i mics/ -o out/ -g 0 --otf -t 0.2`
(command_predict_20260606-131938.txt), producing `out/{EMAN,STAR,CBOX,CRYOSPARC,DISTR}`.
