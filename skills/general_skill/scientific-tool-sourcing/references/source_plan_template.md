# `<TARGET>` source plan

> Fill every `<...>`. Delete rows that do not apply but list them under "Not collected"
> with a reason. Keep it short: this plan steers gathering. It is not the skill design.

- **Target:** `<name>` — `<one line: what it is>` · type: package / CLI / GUI+scripting /
  database / API / file format / pipeline / instrument / protocol
- **Canonical upstream:** `<URL>` (checked against: `<paper code-availability / PyPI / org>`)
- **Version to pin:** `<latest release tag>` (also note: latest pre-release `<…>`, default-branch HEAD date `<…>`)
- **Gathering host:** `<this machine; probe output in logs/gathering_host.txt>`
- **Target runtime:** `<server/GPU/OS if known, else "unknown — config-first skill">`
- **Author / date:** `<…>` · **Executor:** inline / Claude subagents / Codex

## 1. What the future skill must do (drives priorities)
```text
First user tasks (2–4):
Safety level of v0: read-only / generates commands / writes files / runs jobs
Neighbouring tools / interop that matter:
Out of scope for the skill:
```

## 2. Trust ladder (default; note any target-specific change)
1 live behavior · 2 pinned source/schema · 3 docs source · 4 rendered docs ·
5 peer-reviewed papers · 6 first-party talks · 7 community · 8 LLM summaries (navigation only).
`<e.g. "closed-source API: no rank 2; live responses + API docs are top evidence">`

## 3. Source requirement matrix
| Skill area | Source/schema | Docs | Live | Formats | Models/data | Fixtures | Env | Papers | Videos | Community | License/egress | Wrappers |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| install / environment | | | | | | | | | | | | |
| core command / query | | | | | | | | | | | | |
| input formats | | | | | | | | | | | | |
| output formats | | | | | | | | | | | | |
| core workflow + parameters | | | | | | | | | | | | |
| troubleshooting | | | | | | | | | | | | |
| interop | | | | | | | | | | | | |
| validation / benchmarks | | | | | | | | | | | | |
| licensing / privacy | | | | | | | | | | | | |

Cells: P0 / P1 / P2 / Out.

## 4. Known gaps and risks before gathering
| Gap / risk | Why it matters | Priority | How a gatherer resolves it |
|---|---|---|---|

## 5. Task split
| Task | Area / output folder | Inputs | Executor | Runs after |
|---|---|---|---|---|
| A pinned source | `sources/source/` | — | | — |
| B wrappers/forks | `sources/<name>/` | — | | — |
| C docs/terms/papers/community | `sources/web/`, `sources/papers/`, `sources/community/` | A SNAPSHOT if present | | — |
| D live capture | `sources/live/` | host + user OK | | A |
| E cross-check + gaps | `sources/crosscheck/` | A–D | | A–D |

## 6. Not collected (deliberately)
- `<class or item>` — `<reason: e.g. weights > 50 MB; video P2; no host with the tool>`

## 7. Checkpoint for the user (before launching gatherers)
- Tasks to run, executor, concurrency, rough time/cost: `<…>`
- Network access needed: `<domains>`; nothing installed; nothing > 50 MB downloaded.
- Decisions needed: `<…>`
