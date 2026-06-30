---
name: namdinator
description: >-
  Read-only advisor, command-planner, and troubleshooter for Namdinator — the
  automated MDFF (molecular-dynamics flexible fitting) pipeline that fits an
  already-roughly-docked atomic model into a cryo-EM or crystallographic map
  (VMD + NAMD2 + Phenix; optional Rosetta), via the local Namdinator_Generic.sh
  CLI or the namdinator.au.dk web service. Use whenever
  the user names Namdinator or namdinator.au.dk; asks whether it suits a
  model/map; wants a Namdinator command or web-form plan; asks what its flags do
  (-p -m -r -x -l -g -s -i ...); is losing ligands/metals/waters/HETATM in
  fitting; hits its errors (Bad global bond count, AutoPSF fails, atoms moving
  too fast, VMD/NAMD2 not found); needs to read last_frame.pdb / CC / clashscore
  / Ramachandran outputs; or is weighing automated MDFF against ISOLDE/Coot/
  Phenix. Also for "should I MDFF-fit this into my map" even when unnamed. It
  PLANS and EXPLAINS only — never runs Namdinator, never submits the web form,
  and is not validated on any live runtime.
metadata:
  version: 0.1.0
  status: read-only advisor (v0) — not validated against any live runtime
  baseline: namdinator/Namdinator_bash@5814c9474a41f7cbcca785ce83027227073d656f
  license_note: >-
    Namdinator itself is GPL-3.0 (repos namdinator/Namdinator_bash and
    rukibuki/Namdinator). Its dependencies (VMD, NAMD, Phenix, Rosetta,
    CHARMM36) each carry their own licenses and access terms. This skill ships
    no Namdinator code, no third-party binaries, and no map/model data — only
    distilled, source-cited guidance. See references/09_privacy_license_safety.md.
---

# Namdinator skill — read-only advisor / command-planner / troubleshooter

Namdinator automates **MDFF (molecular-dynamics flexible fitting)**: it takes an
atomic model that is *already roughly docked* into a density map, prepares it
with VMD AutoPSF, runs a short NAMD2 molecular-dynamics simulation steered by a
map-derived potential, writes the last trajectory frame as a PDB, and uses
Phenix for map checks, ADP/B-factor processing, validation metrics, and
optionally coordinate real-space refinement via `-x`. It exists
as a local Bash pipeline (`Namdinator_Generic.sh`) and as a public web service
(`namdinator.au.dk`). It targets low- to medium-resolution cryo-EM and
crystallographic maps.

This skill helps a user **decide whether to use Namdinator, prepare inputs, plan
a command or web-form submission, choose conservative parameters, interpret
outputs and logs, and triage failures** — grounded in pinned source and the
method paper, not in guesswork.

## 0. The boundary — read this first, every time

This skill is **read-only and advisory**. It does the thinking *around* a
Namdinator run; it does not perform the run.

It MUST NOT, in this version:

- run `Namdinator_Generic.sh` (or any Namdinator script) on the user's machine;
- submit, POST to, or automate the `namdinator.au.dk` web form;
- modify the user's model or map files;
- claim a result is publication-ready or "correct."

It MAY: explain Namdinator; assess suitability; generate command text and
web-field plans for the user to run themselves; build preflight checklists;
read/interpret logs and output the user pastes in; and run the read-only
environment probe in `scripts/preflight_namdinator_env.py` (presence/version
inspection only — it never executes `vmd`/`namd2`, never installs or downloads,
makes no network calls, and runs no Namdinator job; it may write a report file
if you pass `--output`).

**Why the boundary is here, not further out.** Namdinator is a 2019-era,
untagged Bash pipeline with a heavy and brittle dependency stack
(VMD 1.93 + plugins, NAMD2 2.12 CUDA, Phenix, Rosetta). Its exact current
behavior has **not** been captured from a live `-h` run or a validated fixture
on this project's hosts — every flag, default, and output name below comes from
**reading the pinned source, README, web snapshots, and paper**, not from
running it. Executing an unvalidated MD pipeline on real data, or uploading data
to a third-party server, are decisions for the user to make deliberately with
their own runtime — not actions to automate blind. If the user wants real
execution, see §9 (Escalation path).

## 1. Source trust ladder + what is validated vs. gap

When a fact about Namdinator's behavior is in question, prefer evidence in this
order (higher beats lower):

1. **Live executable / runtime behavior** in the user's actual environment
   (a captured `-h`, a real run). *Not available to this skill — treat as the
   missing top of the ladder.*
2. **Pinned source** `namdinator/Namdinator_bash` @ commit
   `5814c9474a41f7cbcca785ce83027227073d656f` (2019-10-16). Default baseline for
   flags, defaults, output filenames, and processing steps.
3. **Current `namdinator.au.dk`** form / manual / terms snapshots (2026-06-30).
   Authoritative for *web-service* fields, limits, and privacy only.
4. **Kidmose et al. 2019** (IUCrJ 6(4):526-531). Authoritative for *intended
   use, limitations, and benchmark claims* — not for current exact syntax.
5. **Historical repo** `rukibuki/Namdinator` @ `f713537…` (2018-09-14). Older
   behavior; cite explicitly if used, and note it differs from the baseline.
6. Dependency docs (VMD/NAMD/Phenix/Rosetta). 7. Community (thin — 0 GitHub
   issues found). 8. LLM memory (lowest; verify before stating).

**Honesty rule:** the CLI surface here is *extracted from source*, not from a
live run. When a user needs exactness (a flag's precise effect, an output
format, current dependency compatibility), say so and point them to capture
`-h` and a fixture run on a real host. Anything that is in *neither* the source
nor the snapshots is a **gap** — label it; never invent it. Known gaps are
listed in `references/00_scope_and_trust.md`.

## 2. When to use Namdinator (and when not to)

Namdinator is a good fit when **all** of these hold; flag any that fail:

- there is **one atomic model and one map**, and the model is **already
  roughly placed** in the density (Namdinator is *flexible fitting*, not blind
  docking or map building from scratch);
- the map is **low-to-medium resolution** (roughly > ~3 Å) and the model has
  geometry/fit problems MDFF can plausibly relax — register shifts, loop/domain
  nudges, stereochemistry cleanup;
- the needed motion is **modest** (rotations beyond ~40–45° are poor MDFF
  targets without manual domain splitting);
- the map is in **P1** (crystallographic maps must be expanded to P1 first).

Be cautious / steer elsewhere when:

- the model is **already a well-built, high-resolution full-atom model**
  (≲ 3 Å). The paper's five all-metric non-improvers (6b44, 5ni1, 5sy1, 5n9y,
  3j9c) were exactly these. Expected benefit is low; a metric may even regress.
- the user needs **interactive, guided** fixing → suggest the **isolde** skill
  (ISOLDE = interactive MDFF in ChimeraX) or **coot** for local rebuilding.
- the user needs **reciprocal-space / final refinement & validation** →
  **phenix** (real_space_refine or refine) / **ccp4**.
- the model needs **rigid-body placement first** → fit in ChimeraX
  (**chimerax** skill) / Coot / PyMOL, *then* Namdinator.
- the user is **choosing a strategy** across tools → **structural-strategy**.

Namdinator's real value is as a fast, low-effort *triage and improvement* pass
and as a codified MDFF workflow — not as an automatic correctness guarantee.
Every output still needs human inspection and independent validation.

## 3. The advisory workflow

Walk the user through these stages. Pull the matching reference file into
context when you reach a stage that needs detail.

1. **Suitability** (§2 above; `references/05_core_workflow.md`). Confirm
   model+map+resolution exist and the model is pre-fitted. Surface any
   show-stoppers before discussing commands.
2. **Local CLI vs. web service** — *always establish this explicitly.* They have
   different inputs, defaults, limits, and risk profiles. Decide with
   `references/03_cli_and_web_surface.md`; gate web use on privacy (§5).
3. **Input preflight** (`references/04_input_output_model.md`): file formats,
   the **non-ATOM-records-removed-by-default** warning (§6), P1 expansion for
   crystallographic maps, sane filenames for web upload.
4. **Environment preflight** for local runs
   (`references/02_installation_environment.md`): the script hard-exits without
   **VMD, NAMD2, or Phenix** (Phenix is required even without `-x`); Rosetta is
   optional. Offer `scripts/preflight_namdinator_env.py`.
5. **Parameter choice** (`references/06_parameter_decision_tree.md`): start from
   defaults; justify any change (`-x`, `-g`, `-s`, `-e`, `-i`, `-l`).
6. **Command / web-field plan** (§4): produce concrete text for the user to run
   — and stop there.
7. **Output & validation interpretation**
   (`references/07_validation_outputs.md`): what the files and metrics mean, and
   the "better CC can hide worse geometry" caveat.
8. **Troubleshooting** (`references/08_troubleshooting.md`): map error text or
   user description to a source-backed cause and fix.

## 4. Command surface (baseline: Namdinator_Generic.sh @ 5814c947)

Canonical local invocation (from README):

```bash
./Namdinator_Generic.sh -p input.pdb -m map.mrc -r 3.5 -x
```

Required: `-p` model, `-m` map, `-r` resolution. The most decision-relevant
flags (full table + cautions in `references/03_cli_and_web_surface.md`):

| Flag | Default | What it does / when to touch it |
|---|---|---|
| `-p` | — (req) | Input model. Source path = standard **PDB**. Web also accepts `.cif`, `.pdb.gz`; **local CIF/GZ support is unverified** — confirm before promising it. |
| `-m` | — (req) | Input map: `.mrc`, `.ccp4`, `.map`, `.situs` (per help). |
| `-r` | — (req) | Map resolution (Å). Drives CC and Phenix real-space refinement. |
| `-x` | off | Add **Phenix coordinate real-space refinement** on the fitted frame. README/manual recommend it for many cryo-EM cases → produces `last_frame_rsr.pdb`. Phenix is required even without `-x`; `-x` adds a `PHENIXMASTERDIR`/`phenix_env.sh` path requirement. |
| `-g` | `0.3` | **G-scale** (map pulling force). Higher pulls harder but destabilizes; lower for difficult/low-res cases. |
| `-s` | `20000` | Simulation steps. Help suggests `20000–500000` for large changes; **web caps at 200000**. |
| `-e` | `2000` | Minimization steps. Increase if atoms move too fast / run is unstable. |
| `-l` | off | **Keep HETATM** for AutoPSF/simulation. Help warns it *often fails* and does not play well with `-x`. Do not present as a reliable way to keep ligands. |
| `-i` | off | GBIS implicit solvent. May slightly improve geometry but is **~7× slower**. |
| `-b` | `20` | B-factor set via Phenix pdbtools (org repo). |
| `-t`/`-f` | `300`/`300` | Initial / final temperature (K). *(Web UI defaults to 298.)* |
| `-c` | `5` | Phenix real-space-refinement macrocycles. |
| `-n` | `lscpu` | Processor count. Default is **Linux-specific** (`lscpu`); set explicitly off Linux. |
| `-h` | — | Help. **Capture this on a real host** to refresh exact text — it is the missing top of the trust ladder. |

Environment note: regardless of which flags you choose, the generic script
hard-exits unless **VMD, NAMD2, and Phenix** are all on PATH — Phenix is required
even without `-x` (it runs map info, ADP/B-factor processing, model-map CC, and
validation on every run). Rosetta is optional.

When you produce a command, also produce: a one-line **rationale** for each
non-default flag, a **preflight checklist** (inputs + environment), and an
explicit note that the user runs it themselves and inspects the output.

For the **web service**, plan the *form fields* instead (action
`…/assets/scripts/prepare.php`, fields `pdb_file`/`pdb_file_fetch`,
`map_file`/`map_file_fetch`, `map_res`, `g_scale`, `sim_steps`, etc., with their
limits) — see `references/03_cli_and_web_surface.md` — and apply the privacy
gate first.

## 5. Privacy gate for the web service (mandatory before recommending it)

The `namdinator.au.dk` terms page states uploaded and processed data are
**stored on the server for 14 days** before automatic deletion, reachable via a
randomized link with a "remove from site" button. So, **before** recommending or
detailing web-service use, ask whether the model and map are **public / safe to
upload**. If the data are unpublished, embargoed, proprietary, patient-derived,
or otherwise sensitive, recommend **local** planning instead and say plainly why.
Also: the upload JS rejects filenames containing spaces or characters like
`( ) # &` — suggest simple names. Details in
`references/09_privacy_license_safety.md`.

## 6. The chemistry warning you must surface (HETATM loss)

By default Namdinator **removes all non-ATOM records** before simulation —
ligands, metals, ions, waters, glycans, and other HETATMs do **not** enter the
default run and are **absent from `last_frame.pdb`**. `UNK` residues are
converted to alanine. AutoPSF adds hydrogens/missing atoms using CHARMM36.
The `-l` flag tries to retain HETATM but, per the help text, *often fails* and
conflicts with `-x`.

Practical consequence to tell the user: if their model has ligands/metals/
waters that matter, plan to **reinsert them manually afterward** (and validate
that geometry separately), or reconsider whether MDFF auto-fitting is the right
tool. Never promise Namdinator will preserve them. The output may also be
**full-atom even if the input was pruned/polyalanine** — so compare metrics
fairly. See `references/04_input_output_model.md`.

## 7. Reading the outputs honestly

A run writes `data_files/`, `log_files/`, `scripts/`, `namdinator_stdout.log`,
`last_frame.pdb` (last MD frame, hydrogens removed), `last_frame_rsr.pdb` (with
`-x`), `simulation-step1.dcd` (trajectory), `visualize_trj.tcl` (VMD viewer),
plus validation logs — model-map CC / `CC_mask` (`phenix.map_model_cc`),
clashscore, Ramachandran (`phenix.ramalyze`), rotamers, Cβ deviations,
cis-peptides, optional Rosetta scores (only if `ROSETTA_BIN` is set), and a
clashscore-vs-frame plot. Full list:
`references/07_validation_outputs.md`.

Interpretation caveats to always carry: **better CC can accompany worse
geometry**, and vice-versa; the paper's "34/39 improved" counts a case as
improved if **any one** of CC / clashscore / Ramachandran got better, so it is a
*permissive* success criterion, not a guarantee that the whole model improved.
MDFF is **stochastic** — two runs differ; recommend repeats for important cases.
Treat Namdinator output as a **draft to inspect and validate**, not a finished
model.

## 8. Reference map — read the right file at the right time

| Read this | When |
|---|---|
| `references/00_scope_and_trust.md` | Scope boundary, trust ladder, the full list of known gaps / unverified claims. |
| `references/01_source_map.md` | Which repo/commit/URL/paper a claim comes from; baseline vs. historical repo differences. |
| `references/02_installation_environment.md` | Local stack, versions, env vars, hardware, compatibility risks. |
| `references/03_cli_and_web_surface.md` | Full CLI flag table **and** the web-form field/limit table. |
| `references/04_input_output_model.md` | Accepted formats, internal transforms (HETATM/UNK), P1 expansion, output files. |
| `references/05_core_workflow.md` | End-to-end pipeline and the suitability decision. |
| `references/06_parameter_decision_tree.md` | How to choose `-x`/`-g`/`-s`/`-e`/`-i`/`-l` and rescue hard cases. |
| `references/07_validation_outputs.md` | Output files + every validation metric and how to read it. |
| `references/08_troubleshooting.md` | Error/symptom → source-backed cause → fix. |
| `references/09_privacy_license_safety.md` | Web 14-day retention, upload rules, licenses, execution-safety rules for any future executor. |
| `references/10_examples_and_evals.md` | Repo fixture, paper benchmark cases, worked decision examples. |

`tests/` holds trigger tests, eval cases, and reference answers used to validate
this skill. `configs/site_config.template.md` is a **blank** template a user
fills in on whatever Linux host they eventually run Namdinator on — it is
intentionally generic (this skill is not configured for any specific machine).

## 9. Escalation path (beyond read-only)

If the user genuinely wants Namdinator to *run* (not just be planned), that is
out of this version's scope and requires, in order:

1. a real **Linux** host with a **validated** VMD 1.93 + plugins / NAMD2 2.12
   CUDA / Phenix / (optional Rosetta) / gnuplot stack (run
   `scripts/preflight_namdinator_env.py` to inventory it);
2. a captured live `./Namdinator_Generic.sh -h` and a successful **fixture run**
   (the repo ships `3jd8.pdb` + `emd_6640.map/.mrc` = full-length human NPC1 at
   **4.43 Å**, so use `-r 4.43`; the README's `emd_6644` is a confirmed typo —
   EMD-6644 is an unrelated entry — see `references/10_examples_and_evals.md`);
3. an executor that writes only to a dedicated output dir, never overwrites
   inputs, captures stdout/stderr + versions, and requires explicit user
   confirmation per run (`references/09_privacy_license_safety.md`).

Until that exists, keep to planning and explanation, and say so plainly rather
than improvising an execution path.

## How to deliver a recommendation

Default response shape for a "should I / what command" question:

```
Verdict        — is Namdinator appropriate here? (with the deciding reasons)
Mode           — local CLI or web service, and why
Preflight      — input + environment items to fix/confirm first
Command/plan   — concrete command text or web-field values, each non-default justified
Watch-outs     — HETATM loss, privacy (if web), failure modes likely for this case
After the run  — which outputs/metrics to check and how to read them
```

Keep it honest and proportionate: lead with the verdict, never oversell, and
flag every place where a claim depends on a live run this skill has not seen.
