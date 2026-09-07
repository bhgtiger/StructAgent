# Coot docs and source usage

If available, use the optional historical project corpus in:
`<LOCAL_COOT_DOCS_DIR>/`. It is not distributed or required. Without it, use the official manual, release-tagged source and tutorial routes below; never invent a corpus path.

## Primary generated references
- `00-coot-system-map.md` — top-level mental model
- `10-manual-structure.md` — chapter/section navigation
- `20-capability-atlas.md` — what Coot can do
- `30-scripting-surface.md` — documented callable/documented automation surface
- `31-function-index.md` — exact function lookup
- `40-data-and-chemistry.md` — dictionaries/restraints/chemistry-sensitive features
- `50-workflow-patterns.md` — reconstructed practical workflows
- `60-gaps-and-ambiguities.md` — what is still unclear
- `coot-all-in-one.md` — fallback search blob only

## How to use docs vs source

Use the docs to answer:
- what capability families exist
- what workflows are Coot-native
- which scripting interfaces are documented

Use the source to answer:
- whether the feature is actually implemented in the lane you want
- whether the task is GUI-only, classic-scriptable, headless-capable, or external-helper-driven
- which entry points, wrappers, helper layers, and arguments are real

## Practical rule

For any nontrivial module:
1. locate the capability in `20-capability-atlas.md` if available, otherwise the official manual
2. inspect callable candidates in the optional scripting indexes or the official source/API documentation
3. reconcile against source before claiming robust support
4. prefer runtime smoke tests for high-value workflows

## Caution

Do not overclaim headless support from the online docs alone.
The mirrored online API docs strongly reflect the classic documented scripting interface, but not full newer/headless coverage.

## Current release and tutorial routing (2026-09-07)

[Upstream releases](https://github.com/pemsley/coot/releases) identify **1.3.3**, released 2026-08-13, as the newest non-prerelease. It fixes mouse interaction after Edit Chi Angles. For that symptom, check the running build before treating the edit as failed. Version 1.3.2 adds a command terminal, PDBQT I/O and Chapi chemistry helpers; these are documented upstream capabilities, not coverage validated by this skill's classic wrappers.

Keep desktop Coot, classic embedded Python, Chapi/libcootapi and the command terminal distinct. A command such as `list models` belongs to the [command reference](https://pemsley.github.io/coot/doc/command-reference.html), not to Python. In a supported terminal, inspect `list models` and `list maps` before selecting explicit molecule IDs. Do not switch existing scripts to the new interface merely because a release advertises AI support.

For manual building, use the [2023 tutorial](https://pemsley.github.io/coot/blog/2023/05/05/coot-tutorial-in-2023.html) to practice sequence inspection, local corrections and checking the result. Locate exact classic functions in the [manual](https://www2.mrc-lmb.cam.ac.uk/personal/pemsley/coot/web/docs/coot.html), then reconcile with the source tag matching the installed build. For cryo-EM model preparation and map extraction, follow the Part 1–3 links from the [official tutorial/blog index](https://pemsley.github.io/coot/). Tutorial menu names and graphics settings are version-specific examples.

The [CCP4 update table](https://www.ccp4.ac.uk/ccp4-9-0-updates/) bundles Coot 1.2 in update 9.0.016. Do not infer upstream 1.3 APIs from a CCP4 9 installation. Historical local successes/failures in `SKILL.md` remain evidence for their original runtime, not a claim that 1.3.3 has been tested here.
