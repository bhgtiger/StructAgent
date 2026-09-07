# cryoSPARC Agent Skill

**Consult workflows, inspect results, launch jobs safely.**

This folder contains the portable CryoSPARC agent skill: a concise `SKILL.md` router, 40 on-demand references, reusable automation and mask helpers, and example configurations. Release guidance is verified through CryoSPARC **v5.0.7** as of **2026-09-07**. This is documentation coverage; live execution requires configuration and validation on your own installation.

This is an independent, unofficial project. It is not affiliated with, endorsed by, sponsored by, or approved by Structura Biotechnology Inc. cryoSPARC and CryoSPARC Live are trademarks of Structura Biotechnology Inc. Users are responsible for complying with cryoSPARC licensing, documentation terms, and citation requirements.

Public example page: https://bhgtiger.github.io/StructAgent/cryosparc_skill_example/

## Sources and future updates

This repository maintains the general-purpose skill at `skills/annika/cryosparc/`. Copy it into your agent's skill directory and configure connection details locally. Preserve local settings and lessons when updating an existing installation.

[Maintenance instructions](references/maintenance.md) list authoritative sources and explain how to refresh this skill without loading the whole corpus. Ask: **“Use the cryosparc skill to update its own release guidance and official tutorials, keeping loading lightweight.”**

The current refresh adds [Complex I heterogeneity](references/case_studies_and_tutorials.md), [CAK/GPCR automated workflows](references/automated_workflow_tutorials.md), tools v5 migration notes, and current symmetry/FSC resources. The main entrypoint is 650 words; substantial guidance stays in on-demand references. Keep site configurations, credentials, private lessons, source archives, and run logs outside public commits.

## What is included

```text
skills/annika/cryosparc/
├── README.md
├── SKILL.md                         # entrypoint, routing, safety rules
├── lessons.md                       # local/site lessons placeholder
├── references/                      # markdown reference files (incl. 20_masks.md + 20a_mask_generation_chimerax.md)
├── assets/                          # small static assets (e.g. mask_skill_overview.svg)
└── scripts/
    ├── cryosparc_harness.py         # dry-run-first helper for cautious cryoSPARC automation
    └── masks/                       # headless ChimeraX mask-base generators (file-local, no cryoSPARC)
        ├── README.md
        ├── make_mask_from_model.py      # molmap → binarize/dilate/soft → resample → .mrc + .json
        ├── make_mask_from_map.py        # no-model fallback: Gaussian blur + threshold + soft
        └── make_complement_mask.py      # full − region → particle-subtraction mask
```

The `Source basis` sections inside reference files are provenance notes from skill construction, not runtime dependencies. The raw source corpus is intentionally not bundled.

## Install

### Claude Code-style skill directory

```bash
git clone https://github.com/bhgtiger/StructAgent.git
mkdir -p ~/.claude/skills
cp -R StructAgent/skills/annika/cryosparc ~/.claude/skills/
```

### Generic agent runtime

Copy this folder into the runtime's skill/tool-instruction location, then map:

| This folder | Agent-runtime equivalent |
|---|---|
| `SKILL.md` | instruction module / router target for cryoSPARC tasks |
| `description` frontmatter | trigger text for cryoSPARC workflows, errors, and automation requests |
| `references/` | on-demand knowledge files |
| `lessons.md` | writable local memory for confirmed site lessons |
| `scripts/cryosparc_harness.py` | approved tool wrapper with queue/start safety gates |
| local `site_config.md` | deployment-specific config; create locally, do not publish secrets |

## First use on a new site

Create a local `site_config.md` next to `SKILL.md` after probing the deployment:

```md
# site_config.md

## cryoSPARC instance
- master_url: http://<host>:<base-port>
- master_version: v5.0.x
- cryosparc_tools_python: ~/.venvs/cs-tools-v5/bin/python
- default_lane: <gpu-lane-name>

## Access rules
- Prefer read-only inspection first.
- Queue only after explicit confirmation of project_uid, workspace_uid, lane, and dry-run vs real queue.
- Never store passwords, API keys, session tokens, or private dataset details here.
```

Keep `site_config.md` local if it contains hostnames, lane names, private project IDs, or other deployment-specific information.

## Usage pattern

1. **Consult** — load the smallest relevant reference file(s), then answer workflow/parameter questions with version caveats.
2. **Inspect** — use read-only `cryosparc-tools` calls to inspect projects, jobs, params, assets, plots, and logs.
3. **Plan** — show the exact proposed job type, inputs, params, project/workspace, and lane.
4. **Confirm** — ask the user to explicitly confirm `project_uid`, `workspace_uid`, lane, and dry-run vs queue.
5. **Launch** — queue/start jobs only after confirmation; record resulting job IDs.

## Safety rules

Ask before:

- queueing or starting jobs;
- deleting jobs, projects, workspaces, cache, or raw data;
- restarting/stopping cryoSPARC services;
- changing cluster/worker/lane configuration;
- running long GPU jobs that consume shared resources;
- exporting private datasets outside the project.

Never commit credentials, cryoSPARC session tokens, private hostnames if they should not be public, unpublished dataset details, maps, particle stacks, or downloaded job assets.

## Helper script

The bundled helper is intentionally dry-run-first:

```bash
python scripts/cryosparc_harness.py doctor
python scripts/cryosparc_harness.py list-projects
python scripts/cryosparc_harness.py inspect-job --project-uid P1 --job-uid J1

# default: prints a dry-run plan only
python scripts/cryosparc_harness.py create-job \
  --project-uid P1 --workspace-uid W1 --job-type new_local_refine \
  --params-json '{"use_alignment_prior": true}'

# real queue requires explicit commit + queue + lane + confirmation word
python scripts/cryosparc_harness.py create-job \
  --project-uid P1 --workspace-uid W1 --job-type new_local_refine \
  --lane gpu --commit --queue --queue-confirm QUEUE
```

Live use requires a compatible `cryosparc-tools` install and valid local access to a cryoSPARC instance.

### Mask generation helpers (ChimeraX, file-local)

`scripts/masks/` bundles headless ChimeraX (`--nogui --exit --script`) helpers for generating cryoSPARC mask bases off-instance. They read `.mrc`/`.cif`/`.pdb`, write `.mrc` + a `<out>.mrc.json` sidecar (`{"ok": bool, "params": ..., "stats": ...}`), and do **not** touch any cryoSPARC instance. The sidecar is the only reliable success signal — ChimeraX exit codes can be misleading. See `references/20a_mask_generation_chimerax.md` for the full workflow, parameters, and ChimeraX command caveats.

```bash
# locate ChimeraX (macOS example)
CHIMERAX=$(ls -1d /Applications/ChimeraX-*.app/Contents/MacOS/ChimeraX 2>/dev/null | sort -V | tail -1)

# model → mask base (primary path)
"$CHIMERAX" --nogui --exit --script scripts/masks/make_mask_from_model.py -- \
  --model model.cif --selection "/A:120-340" \
  --target-map refined_map.mrc --resolution 16 --out mask_base.mrc
```
