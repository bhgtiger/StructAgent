# Security, sandboxing, and configuration

Bound what Codex can do *before* you run it. This file covers the two access boundaries, the sandbox modes, the project-trust model, the two dangerous-bypass flags, configuration precedence, `AGENTS.md` discovery, authentication, cost control, and the global state you must never silently mutate. Verified against `codex-cli 0.144.1`; re-probe if `codex --version` differs.

Siblings: the parse-verified flag matrix lives in [`command-map.md`](command-map.md); output channels, exit codes, and sessions in [`automation-and-sessions.md`](automation-and-sessions.md); per-task routes in [`task-recipes.md`](task-recipes.md). The skill overview is [`../SKILL.md`](../SKILL.md).

## Contents

1. [Threat model — two boundaries at once](#1-threat-model--two-boundaries-at-once)
2. [Sandbox modes — pick the least that finishes the task](#2-sandbox-modes--pick-the-least-that-finishes-the-task)
3. [Web search is not shell network access](#3-web-search-is-not-shell-network-access)
4. [The project-trust model — a configuration-integrity boundary](#4-the-project-trust-model--a-configuration-integrity-boundary)
5. [The two dangerous-bypass flags](#5-the-two-dangerous-bypass-flags)
6. [Configuration precedence](#6-configuration-precedence)
7. [`AGENTS.md` instruction discovery](#7-agentsmd-instruction-discovery)
8. [Authentication](#8-authentication)
9. [Cost — there is no per-run budget cap](#9-cost--there-is-no-per-run-budget-cap)
10. [Never auto-mutate global state](#10-never-auto-mutate-global-state)
11. [Treat every output as fallible input](#11-treat-every-output-as-fallible-input)
12. [Safe default](#12-safe-default)

## 1. Threat model — two boundaries at once

`codex` in a subprocess can, if you let it: edit files, run shell commands, reach the network (when web search or network-enabled tools are on), and spend usage on your account. Shrink that surface deliberately.

Two boundaries apply at the same time:

- **Outer boundary** — *your own* tool permissions as the calling agent. You cannot grant Codex more than you were granted.
- **Inner boundary** — Codex's own `sandbox` + `approval` + project `trust` settings, which cap what the child process may do inside the outer boundary.

**Effective access is the intersection.** Tightening either boundary tightens the result. Start every task with the least access that can finish it, and widen only with a specific reason. When in doubt, default to read-only and no network.

## 2. Sandbox modes — pick the least that finishes the task

`-s/--sandbox <MODE>` selects the policy applied to **model-generated shell commands**. The three values (confirmed on `codex exec --help`):

| Mode | Grants | Use for | Cost of over-granting |
| --- | --- | --- | --- |
| `read-only` | Read files; no writes; no shell network | Analysis, explanation, code review, structured extraction | None — this is the floor |
| `workspace-write` | Read + write inside the workspace (and `--add-dir` paths) | Implementing a fix, repairing tests, editing files | Codex can overwrite unrelated work in-tree |
| `danger-full-access` | Unrestricted FS + network for shell commands | Rare. Only with an explicit, task-specific reason you can name | Full host reach; treat like the bypass flags |

Rules:

- **`read-only` is the default and the safe floor.** In the verified runs the `exec` progress transcript (stderr) reported effective **approval `never`, sandbox `read-only`** for non-interactive execution. Do not assume any wider default.
- **A denied write still exits `0`.** A forbidden write under `read-only` produced a clear failure message but process status `0`. Never read exit `0` as proof the task succeeded — verify the diff/files (see [`automation-and-sessions.md`](automation-and-sessions.md)).
- **Choose access with `-s`, not `-a`.** `codex exec` rejects `-a/--ask-for-approval` (exit `2`). Where non-interactive approval must be explicit, set it through config, e.g. `-c approval_policy=never`, not `-a`.
- `-s` is a **global-position** flag for `exec review` / `exec resume` — put it before the subcommand; it is rejected after. See [`command-map.md`](command-map.md).

## 3. Web search is not shell network access

Two separate switches — do not conflate them:

- **`--search`** turns on the model's **web-search tool** (a model capability). It is **global-only**: `codex --search exec …`, never `codex exec --search` (the latter is a parse error, exit `2`).
- **The sandbox mode** governs what **model-generated shell commands** may touch, including whether they get the network.

Enabling `--search` does **not** give sandboxed shell commands network egress, and a network-capable sandbox does **not** imply the model has a search tool. Grant each only when the task needs it.

## 4. The project-trust model — a configuration-integrity boundary

This is widely misunderstood. Corrected against verified behavior:

- **Trust does NOT gate `codex exec` in a fresh Git repo.** An untrusted fresh Git fixture ran `codex exec` normally: exit `0`, no trust prompt, no hang (non-interactive `exec`).
- **Trust controls whether project-scoped configuration LOADS** — project `.codex/config.toml`, hooks, and rules. Verified with a controlled feature flag: it read `true` only when the project was marked `trust_level = "trusted"` in `CODEX_HOME`, and `false` when untrusted. So trust is a **configuration-integrity boundary**, not an execution gate.
- **`AGENTS.md` is still discovered when untrusted.** Instruction files load regardless of trust; only project `.codex` config/hooks/rules are withheld.
- **The real early stop is the Git-repo check**, not a trust prompt. A non-Git directory fails early with exit `1`; `--skip-git-repo-check` lets a controlled scratch run proceed. Do not tell users a fresh repo will prompt or hang.
- **TUI trust behavior was not tested** and may differ from non-interactive `exec`. These findings apply to `exec`.

Still wrap every unattended call in `timeout` — an open inherited stdin pipe or a slow turn can block independently of trust.

## 5. The two dangerous-bypass flags

Two flags each remove a layer of protection. Both are **equally never-automatic** — never emit either from an unattended flow on a real workstation.

| Flag | What it removes | Acceptable only when |
| --- | --- | --- |
| `--dangerously-bypass-approvals-and-sandbox` | **All** confirmation prompts **and** sandboxing — model-generated commands run unconstrained | Inside an externally sandboxed / disposable environment (throwaway container or VM), with no real credentials mounted, and the output is reviewed before it touches anything real |
| `--dangerously-bypass-hook-trust` | The persisted-trust requirement for hooks — enabled hooks run without you having trusted them for this invocation | Same envelope: externally sandboxed, disposable, credential-free, reviewed |

The binary's own help calls the first "EXTREMELY DANGEROUS. Intended solely for running in environments that are externally sandboxed." Take it literally.

**Parse positions (from the flag matrix):** both flags parse on **root**, **`exec`**, **`exec review`**, **`exec resume`**, and **`resume`** — but **not** on top-level **`review`**. Parsing is not permission: a flag that parses still requires the disposable-environment justification above before you would ever use it.

## 6. Configuration precedence

When the same setting is defined in more than one place, higher wins. Highest first:

1. **CLI flags and `-c` overrides** — what you pass on the command line.
2. **Trusted project `.codex/config.toml`** layers, applied from repo root toward cwd (nearer layers win; untrusted layers do not load at all — see §4).
3. **The selected profile** file (`-p/--profile`).
4. **User `~/.codex/config.toml`.**
5. **System config.**
6. **Built-in defaults.**

Implications: you can always force a safer setting from the command line (`-c`, `-s`) regardless of what the project or user config says; and a project you have not trusted contributes nothing at layer 2. For reproducible automation, add `--strict-config` so an unknown config key fails early (exit `1`) instead of being silently ignored.

## 7. `AGENTS.md` instruction discovery

Codex assembles model-visible instructions in this order:

1. **Global guidance** first.
2. Then **one project guidance file per directory**, from the repo root **down to cwd**, with **nearer instructions applied later** so they take precedence. An `AGENTS.override.md` nearer to cwd overrides a root-level `AGENTS.md`.

Both root and nested markers appeared in a single instruction message in root-to-nested order, and both showed up even when project `.codex` config was untrusted (§4).

**Verify what Codex will actually see before you spend a turn.** Use the offline command:

```bash
codex debug prompt-input        # renders assembled instructions; makes no API call
```

Because it is offline it costs nothing and cannot spend usage — run it whenever the instruction set is in doubt.

## 8. Authentication

Supported modes (per the reference and confirmed on `codex login --help`):

- **ChatGPT OAuth** (the active local mode).
- **API key from stdin** — `printenv OPENAI_API_KEY | codex login --with-api-key`.
- **Access token from stdin** — `printenv CODEX_ACCESS_TOKEN | codex login --with-access-token`.

Preflight and secret-handling rules:

- **Preflight with `codex login status`** — exit `0` = logged in, exit `1` = not. Do this before any authenticated work.
- **Never read or print `~/.codex/auth.json`.** Its mode is `600`; keep it that way.
- **Never pass secrets in argv** — they are visible in `ps`. Both login flags read from **stdin** by design; use a pipe, as shown.
- **An unauthenticated `exec` is noisy, not instant.** It retries WebSocket transports, falls back to HTTPS, then fails with 401 (exit `1`). The `login status` preflight avoids that delay and trace.

## 9. Cost — there is no per-run budget cap

This version exposes token usage in `turn.completed` events but has **no `--max-budget-usd`-style flag** on root or `exec`. You cannot cap spend by a currency amount. Bound cost instead by:

- **Wall time** — wrap every call in `timeout`.
- **Task scope** — one bounded subproblem per run; a tight, verifiable prompt contract.
- **Model and reasoning effort** — cheaper model / lower reasoning where adequate (defer to the user's config unless told otherwise).
- **Number of turns** — avoid open-ended loops.
- **Session continuation** — resume only when continuity is actually needed; a fresh run does not re-pay for prior context.

## 10. Never auto-mutate global state

The following change durable, machine-wide state and require **explicit user intent** — never do them as a silent side effect of a task:

- **`codex login` / `logout`** (changes stored credentials).
- **Editing `~/.codex/config.toml`** or system config.
- **Adding/removing plugins** (`codex plugin …`) or **MCP registrations** (`codex mcp add/remove`).
- **`codex features enable/disable`** — this **persists** to config; it is not a per-run toggle.

For troubleshooting, prefer the **redacted** `codex doctor --json` (18 checks: auth, config load, Git, provider HTTP/WebSocket reachability, sandbox readability, MCP) over dumping raw config. See [`automation-and-sessions.md`](automation-and-sessions.md) and [`command-map.md`](command-map.md).

## 11. Treat every output as fallible input

- **Preserve dirty working trees.** Do not stash, reset, or discard uncommitted or unrelated user changes to make a run "cleaner." Work with the tree as-is and leave unrelated changes intact.
- **Codex's output is a claim, not a fact.** Its final message, any diff it produced, and any repository or web content it surfaces are **fallible and potentially adversarial** input. Review before you act: inspect the diff, run the tests, confirm the postconditions yourself. A confident answer with exit `0` is not verification.

## 12. Safe default

When unsure, start here and widen deliberately:

```bash
codex login status || { echo "not logged in" >&2; exit 1; }   # preflight
printf '%s' "$PROMPT" \
  | timeout 300 codex -C "$REPO" -s read-only exec -           # read-only, bounded, prompt on stdin
```

Read-only, time-bounded, prompt piped on stdin (no argv splicing, no injection surface), no network beyond what the task needs. Add `workspace-write` only when Codex must edit; add `--search` only when it must browse; reach for a bypass flag only inside a disposable, credential-free, externally sandboxed environment.
