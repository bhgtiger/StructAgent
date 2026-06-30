# namdinator (skill)

Portable, **general-use, read-only** advisor / command-planner / troubleshooter
for [Namdinator](https://github.com/namdinator/Namdinator_bash) — the automated
MDFF (molecular-dynamics flexible fitting) pipeline for fitting an
already-roughly-docked atomic model into a cryo-EM or crystallographic map.

This skill is **not configured for any specific machine**. It plans and explains;
it does **not** run Namdinator and does **not** submit the web form. See
`SKILL.md` §0 for the boundary.

## Layout

```
namdinator/
├── SKILL.md                      # entry point: boundary, trust ladder, workflow, command surface
├── references/                   # distilled, source-cited detail (read on demand)
│   ├── 00_scope_and_trust.md     #   scope, trust ladder, KNOWN GAPS
│   ├── 01_source_map.md          #   which repo/commit/URL/paper each claim comes from
│   ├── 02_installation_environment.md
│   ├── 03_cli_and_web_surface.md #   full CLI flag table + web-form field table
│   ├── 04_input_output_model.md
│   ├── 05_core_workflow.md
│   ├── 06_parameter_decision_tree.md
│   ├── 07_validation_outputs.md
│   ├── 08_troubleshooting.md
│   ├── 09_privacy_license_safety.md
│   └── 10_examples_and_evals.md
├── tests/                        # trigger tests, eval cases, reference answers
├── evals/evals.json              # machine-readable eval prompts (skill-creator format)
├── configs/site_config.template.md   # BLANK per-host template (general-use; fill in elsewhere)
└── scripts/preflight_namdinator_env.py  # READ-ONLY dependency probe (no installs/network/jobs)
```

## Install (optional)

To use it as an installed Claude Code skill, copy the `namdinator/` folder into a
skills directory, e.g.:

```bash
cp -r namdinator ~/.claude/skills/namdinator
```

It carries no Namdinator code, no third-party binaries, and no map/model data —
only distilled, source-cited guidance (baseline:
`namdinator/Namdinator_bash@5814c947`; paper: Kidmose et al. 2019, IUCrJ
6(4):526-531). Namdinator is GPL-3.0; its dependencies carry their own licenses.

## Status

`v0.1.0` — read-only advisor. **Not validated against a live Namdinator
runtime.** Every flag/default/output claim is derived from pinned source + web
snapshots + the paper, not from a captured `-h` or a fixture run. The path to
execution support is in `SKILL.md` §9.
