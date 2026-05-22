# AI Agent Skill for cryoSPARC

**Consult workflows, inspect results, launch jobs safely.**

This folder contains the StructAgent AI agent skill for cryoSPARC: a self-contained 36-file agent skill folder with `README.md`, `SKILL.md`, `lessons.md`, 32 on-demand Markdown references, and a dry-run-first Python helper for cautious `cryosparc-tools` automation. It is designed for Claude/Codex-style coding agents, but the pattern is runtime-agnostic: any agent can use it if it can load instructions, read reference files on demand, and run approved shell/Python tools.

This is an independent, unofficial project. It is not affiliated with, endorsed by, sponsored by, or approved by Structura Biotechnology Inc. cryoSPARC and CryoSPARC Live are trademarks of Structura Biotechnology Inc. Users are responsible for complying with cryoSPARC licensing, documentation terms, and citation requirements.

Public example page: https://bhgtiger.github.io/StructAgent/cryosparc_skill_example/

## What is included

```text
skills/annika/cryosparc/
├── README.md
├── SKILL.md                         # entrypoint, routing, safety rules
├── lessons.md                       # local/site lessons placeholder
├── references/                      # 32 markdown reference files
└── scripts/
    └── cryosparc_harness.py         # dry-run-first helper for cautious automation
```

The reference files are synthesized workflow guidance. Raw upstream documentation, forum posts, video transcripts, and release notes are intentionally not bundled. For authoritative and current details, consult the official cryoSPARC guide, release notes, discussion forum, and `cryosparc-tools` documentation.

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
