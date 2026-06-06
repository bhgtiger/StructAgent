# 00 — Scope and source trust

## What this skill does

- Explains cryoDRGN's scope, inputs, outputs, CLI namespace, data formats,
  workflows, interoperability, and troubleshooting, grounded in pinned
  **cryoDRGN 4.2.1** sources and in live `--help`/`--version` captured on a
  validated Linux+NVIDIA host.
- Enforces a **mandatory config/environment session** before any
  machine-specific claim, concrete command, or workflow recommendation
  (`references/02_config_session_and_environment.md`).
- Inspects (read-only) or guides inspection of the target environment via
  `scripts/cryodrgn_env_probe.py`, and reports whether cryoDRGN is
  ready / partial / blocked / absent / stale / unknown there.
- Emits **validated** commands. On a `ready` host it emits concrete commands
  with the user's real paths, and may run real cryoDRGN jobs — but only after
  explicit user confirmation (`SKILL.md` §4).

## What this skill does NOT do

- No blind installs/upgrades/source checkouts; no conda/pip env changes without
  the user's explicit go-ahead.
- No moving/uploading/converting/deleting private particle stacks, `.star`/`.cs`,
  `.pkl`, or outputs without confirmation; no silent network calls.
- No running on the user's real data until the environment is captured (config
  session) and the user has explicitly confirmed the concrete command.
- No benchmark/performance claims beyond what captured docs/papers and the smoke
  log state, with version context.

Execution is **gated by `config_state` + explicit user confirmation**, not by a
version ladder. On a probe-`ready` machine the skill may emit concrete commands
with the user's real paths and run real jobs once the user confirms; on
`partial`/`blocked`/`absent`/`stale`/`unknown` it explains the gap first.

## Source trust ladder (highest wins on conflict)

1. **Live cryoDRGN executable/package behavior on the configured target host**
   (`cryodrgn --version`, `cryodrgn -h`, `cryodrgn <cmd> -h`, package metadata) —
   authoritative for *that installed executable's* flags/version/output. This is
   the **realized #1 source**: captured **2026-06-06 on a Linux + NVIDIA GPU host**
   (cryoDRGN 4.2.1) — see the captured `*.help.txt` files. On any other host, re-run
   the probe with `--live-help` to refresh this source.
2. **Pinned source / packaging** at tag `4.2.1`, commit `23ae1a33…`
   (`pyproject.toml`, `cryodrgn/command_line.py`, module docstrings).
3. **Official documentation** (GitBook user guide) — rendered pages captured
   2026-06-05; treat as source class 3 until a docs-source repo is pinned.
4. **Release notes / PyPI metadata.**
5. **Peer-reviewed method/protocol/benchmark papers** — for scientific
   assumptions and validation, *not* exact CLI syntax.
6. **First-party talks/tutorials** — heuristics/pitfalls only.
7. **Community issues/forums/HPC notes** — failure modes, after cross-checking.
8. **LLM summaries** — navigation aids only.

Key consequence: **installed CLI help wins for exact flags**, but docs/source
still govern the *supported platform* and *intended workflow*. For flags and
defaults, use the **captured 4.2.1 help (`[VALIDATED: cryoDRGN 4.2.1]`)** — it
was confirmed live and is authoritative. If the user's installed cryoDRGN is a
*different* version, defer to that executable's own `-h` (re-probe with
`--live-help`) rather than the captured 4.2.1 text.

Supported platform is a **general, sourced, probe-driven** fact, not a hardcoded
per-machine verdict: cryoDRGN's packaging ships the classifier
`Operating System :: POSIX :: Linux`
[src: `sources/source/cryodrgn_4.2.1/pyproject.toml`], and the installation docs
require a Linux workstation/cluster with NVIDIA GPUs. The probe computes
support per host; the skill never asserts that any one machine is "blocked"
on its own.

## Version pin (summary; full detail in `01_source_map.md`)

```text
Target stable version : cryoDRGN 4.2.1   (this skill targets stable 4.2.1)
Repo                  : https://github.com/ml-struct-bio/cryodrgn
Tag                   : 4.2.1
Tag object (annotated): 2f4db4c02021fd136c53f03a572684921369b268
Commit (dereferenced) : 23ae1a3303b1e623f421b816fc7ea426c9d5b580
PyPI latest captured  : 4.2.1   (2026-06-05)
Newer/other versions  : a beta 4.3.0-b2 exists (repo main HEAD cb28f71… at capture).
                        This skill targets stable 4.2.1; for a different installed
                        version, defer to that executable's own `-h`.
License               : GPLv3 (cryoDRGN). This skill ships no cryoDRGN code/data.
```
