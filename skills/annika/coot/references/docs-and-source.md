# Coot docs and source usage

Use the project corpus in:
`<LOCAL_COOT_DOCS_DIR>/`

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
1. locate the capability in `20-capability-atlas.md`
2. inspect callable candidates in `30-scripting-surface.md` and `31-function-index.md`
3. reconcile against source before claiming robust support
4. prefer runtime smoke tests for high-value workflows

## Caution

Do not overclaim headless support from the online docs alone.
The mirrored online API docs strongly reflect the classic documented scripting interface, but not full newer/headless coverage.
