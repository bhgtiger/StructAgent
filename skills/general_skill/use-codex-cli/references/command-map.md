# Codex command map

Map of every `codex` subcommand for `codex-cli 0.144.1`: what each does, whether it is safe to drive from automation, whether it mutates state, and exactly where each flag may sit. Facts here are live-probed against the installed binary. Re-probe when `codex --version` changes — treat the installed `--help` as authoritative over this file and over online docs. The orchestration model, the five safety rules, and the decision tree live in [`../SKILL.md`](../SKILL.md); this file is the command/flag reference behind them.

## Contents

1. [Root command inventory](#1-root-command-inventory)
2. [Daily stable paths](#2-daily-stable-paths)
3. [Advanced / experimental surfaces](#3-advanced--experimental-surfaces)
4. [Flag-placement matrix](#4-flag-placement-matrix)
5. [Composition rules](#5-composition-rules)
6. [Parse ≠ accept: the runtime caveat](#6-parse--accept-the-runtime-caveat)
7. [Capability discovery](#7-capability-discovery)
8. [Model catalog](#8-model-catalog)
9. [Official reference](#9-official-reference)

## 1. Root command inventory

Visible root commands, verbatim from `codex --help`:

```text
exec review login logout mcp plugin mcp-server app-server remote-control
app completion update doctor sandbox debug apply resume archive delete
unarchive fork cloud exec-server features help
```

Plus one hidden command that works but is **absent from `codex --help`** (documented as experimental): `execpolicy` (subcommand `check`). Do not expect to discover it from root help — probe it directly.

Nested subcommands (all confirmed by `codex <cmd> --help`):

| Parent | Subcommands |
|---|---|
| `exec` | `resume`, `review` |
| `login` | `status` |
| `mcp` | `list`, `get`, `add`, `remove`, `login`, `logout` |
| `plugin` | `add`, `list`, `marketplace`, `remove` |
| `app-server` | `daemon`, `proxy`, `generate-ts`, `generate-json-schema` |
| `remote-control` | `start`, `stop`, `pair` |
| `debug` | `models`, `app-server`, `prompt-input` |
| `cloud` | `exec`, `status`, `list`, `apply`, `diff` |
| `features` | `list`, `enable`, `disable` |
| `execpolicy` (hidden) | `check` |

Interactive / local-management roots — real, but **not automation entry points**: bare `codex` (the TUI), top-level `review` (non-interactive but has no machine-output flags — prefer `exec review`), `resume`/`fork`/`archive`/`delete`/`unarchive` (interactive session management), `apply` (git-apply Codex's last diff), `login`/`logout`, `mcp` (external MCP-server config), `app`, `completion`, `update`. Manage config and sessions with these by hand; do not wire them into an unattended flow.

## 2. Daily stable paths

The routes an orchestrator should reach for first. "Mutates state" means the working tree, config, or a persistent process — not the session file every run writes.

| Command | Purpose | Maturity | Mutates state? | Typical caller | When NOT to use |
|---|---|---|---|---|---|
| `codex exec` | Run one non-interactive turn | Stable | Only under `-s workspace-write`/`danger-full-access` (read-only is the default) | Orchestrator delegating a bounded subtask | For interactive human work (bare `codex` TUI) or trivial work you can do yourself |
| `codex exec review` | Non-interactive review of a diff / base branch / commit | Stable | No (read-only review) | Orchestrator or CI gate | When you need a stable findings schema — it emits generic events; add `--output-schema` |
| `codex exec resume` | Continue a prior thread non-interactively | Stable | Same as `exec` (sandbox-governed) | Orchestrator continuing a multi-turn investigation | For a fresh independent opinion (start a new thread or `--ephemeral`) |
| `codex login status` | Report auth state (exit 0 = logged in, 1 = no auth) | Stable | No | Preflight before any authenticated call | To log in — that is interactive `codex login` |
| `codex doctor` | Diagnose install, config, auth, runtime health (`--json`) | Stable | No | Troubleshooting a failing environment | As a substitute for reading a task's own error text |
| `codex features list` | List features with stage + effective state | Stable | No | Capability / trust discovery | To infer which commands exist — see [§7](#7-capability-discovery) |
| `codex debug prompt-input` | Render the model-visible prompt-input list as JSON | Stable (debug) | No | Debugging `AGENTS.md` / instruction assembly | In a hot path — it materializes the full instruction context |
| `codex debug models` | Render the raw model catalog as JSON | Stable (debug) | No | Model discovery | To dump wholesale (~271 KB) — extract only needed fields |

## 3. Advanced / experimental surfaces

Powerful or preview surfaces. Most are not exercised in the ground-truth dossier; keep them out of the skill's default path and read the exact `--help` before use. Details for the MCP server are in [`mcp-and-advanced.md`](mcp-and-advanced.md).

| Command | Purpose | Maturity | Mutates state? | Typical caller | When NOT to use |
|---|---|---|---|---|---|
| `codex mcp-server` | Start Codex as a stdio MCP server exposing the `codex` / `codex-reply` tools | Stable surface | Yes — serves live, sandbox-governed sessions | An MCP host embedding Codex as a tool | For one-shot runs — use `codex exec` |
| `codex sandbox` | Run an arbitrary command under Codex's seatbelt sandbox | Stable | Depends entirely on the wrapped command | Testing sandbox policy; confining a command | When you want a model turn — this runs no agent |
| `codex app-server` | [experimental] Run the app server; generate protocol bindings/schema (`daemon`, `proxy`, `generate-ts`, `generate-json-schema`) | Experimental | Yes — daemon lifecycle; generators write files | Desktop / IDE integrations | For scripted agent delegation |
| `codex remote-control` | [experimental] Manage the app-server daemon with remote control (`start`, `stop`, `pair`) | Experimental | Yes — daemon + pairing state | Driving a remote TUI | For headless automation |
| `codex cloud` | [EXPERIMENTAL] Browse/submit Codex Cloud tasks, apply diffs locally (`exec`, `status`, `list`, `apply`, `diff`) | Experimental | Yes — `apply` writes the working tree; `exec` submits cloud tasks | Cloud-task workflows | As a local substitute for `codex exec` |
| `codex exec-server` | [EXPERIMENTAL] Run the standalone exec-server service | Experimental | Yes — long-running service | Service integrations | In the skill's default path — unverified in the dossier |
| `codex execpolicy check` | Check execpolicy (Starlark rule) files against a command | Experimental, **hidden** from root help | No | Authoring / validating execution rules | Expecting to find it in `codex --help` — probe it directly |
| `codex plugin` | Manage plugins from marketplace snapshots (`add`, `list`, `marketplace`, `remove`) | Stable | Yes — `add`/`remove` change local plugin config + cache | Plugin management | Inside an automated `exec` run |

## 4. Flag-placement matrix

Flag placement is command-specific. Verified by **156 parse probes**, each ending in `--help`: exit `0` = the route accepted the flag before help printed; exit `2` = the route rejected it. A misplaced flag is a hard parse error, not a fallback. `✓` = accepted in that position, `✗` = rejected. `exec review`/`exec resume` are the non-interactive nested forms used for automation; top-level `review`/`resume` are the human-oriented forms.

| Flag group | Root `codex` | `exec` | `exec review` | `exec resume` | `review` | `resume` |
| --- | :---: | :---: | :---: | :---: | :---: | :---: |
| `-c`, `--enable`, `--strict-config` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `-m/--model` | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| `-s/--sandbox` | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ |
| `-a/--ask-for-approval` | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ |
| `-C/--cd`, `--add-dir` | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ |
| `-i/--image` | ✓ | ✓ | ✗ | ✓ | ✗ | ✓ |
| `-p/--profile`, `--oss`, `--local-provider` | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ |
| `--search` | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ |
| `--json`, `--output-schema`, `-o` | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| `--ephemeral`, Git/config/rules bypasses | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Both dangerous bypass flags | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Review target flags | ✗ | ✗ | ✓ | ✗ | ✓ | ✗ |

Read the columns together with the rules below — e.g. `-s` is `✓` on `exec` but `✗` on `exec review`/`exec resume`, so it belongs in **global** position for those routes.

## 5. Composition rules

Straight from the verified matrix:

- Direct exec: `codex [global flags] exec [exec flags] ...`
- Automated review: `codex -C <repo> -s read-only exec review [review/output flags]`
- Automated resume: `codex -C <repo> -s <mode> exec resume <thread-id> [resume/output flags]`
- Do not pass `-a` after `exec`.
- Do not pass `-s`, `-C`, `--add-dir`, or `-p` after `exec review` or `exec resume`.

Govern non-interactive access with `-s/--sandbox` (plus an `approval_policy` config value if approval behavior must be explicit), never with `-a` — `exec` rejects it. Sandbox and output modes are covered in [`security-and-config.md`](security-and-config.md) and [`automation-and-sessions.md`](automation-and-sessions.md).

## 6. Parse ≠ accept: the runtime caveat

A global flag can parse yet still be **rejected at runtime** by the chosen command. `codex --strict-config ... debug prompt-input` parses cleanly, then fails with `` `--strict-config` is not supported for `codex debug` ``. The matrix proves only that a flag is accepted *before help prints* — it does not prove the command honors it. Prefer the exact command's `--help`, and be ready to handle runtime incompatibility even after a clean parse.

## 7. Capability discovery

Probe; do not assume. Online docs may list commands absent from a given release (and vice versa — see the hidden `execpolicy`), so the installed binary is the source of truth.

- `codex --version` — confirm the binary and baseline. If it is not `0.144.1`, re-verify everything here.
- `codex <cmd> --help` — the authoritative, offline syntax for any command; `--help` short-circuits before any API call.
- `codex features list` — stage + effective state of 92 feature records. **Feature stage/state is NOT command availability.** A *removed* feature row can coexist with a working *experimental* command (e.g. a removed `remote_control` feature alongside the experimental `remote-control` command). Never infer the command surface from the feature table.
- `codex debug models` — the model catalog as JSON. It is ~271 KB and embeds full base-instruction templates; extract only the fields you need (id, priority, reasoning), never dump or log it wholesale.

## 8. Model catalog

`codex debug models` returned eight entries (seven visible in normal model lists):

```text
gpt-5.6-sol            # priority 1, catalog default reasoning "medium" — the default model
gpt-5.6-terra
gpt-5.6-luna
gpt-5.5
gpt-5.4
gpt-5.4-mini
gpt-5.3-codex-spark
codex-auto-review      # hidden
```

`gpt-5.6-sol` is the default (priority 1, catalog reasoning `medium`), but the user's `config.toml` may select a different model or reasoning effort (the probed environment selected reasoning `max`). **Policy: defer to the user's `config.toml`; never hardcode a model or reasoning level.** Enumerate with `codex debug models` only when you must, and override with `-m/--model` only when the user asks.

## 9. Official reference

Full, upstream CLI reference: <https://developers.openai.com/codex/cli/reference>. Reconcile it against the installed `--help` — this release differs from the docs in at least one place (the hidden `execpolicy`).
