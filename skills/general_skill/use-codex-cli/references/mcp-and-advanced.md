# MCP and advanced surfaces

Codex *as* an MCP server, Codex *consuming* external MCP servers, and the experimental command surfaces past `codex exec` — each with a maturity flag and the "probe before use" rule. For the default subprocess route see [`../SKILL.md`](../SKILL.md) and [`automation-and-sessions.md`](automation-and-sessions.md); this file is everything beyond it.

## Contents

1. [Two different MCPs](#two-different-mcps)
2. [Codex as an MCP server](#codex-as-an-mcp-server)
3. [When MCP beats a subprocess](#when-mcp-beats-a-subprocess)
4. [Consuming external MCP servers](#consuming-external-mcp-servers)
5. [Advanced and experimental surfaces](#advanced-and-experimental-surfaces)
6. [The `codex sandbox` runner](#the-codex-sandbox-runner)
7. [The hidden `execpolicy` command](#the-hidden-execpolicy-command)
8. [Feature flags and config persistence](#feature-flags-and-config-persistence)
9. [Official guide](#official-guide)

## Two different MCPs

They share three letters and nothing else. Pick the direction first.

| Direction | Command | Meaning |
|---|---|---|
| Codex **is** the server | `codex mcp-server` | Another agent/host drives Codex over stdio through the `codex` / `codex-reply` tools. |
| Codex **is** the client | `codex mcp {list,get,add,remove,login,logout}` | Codex registers and calls *external* MCP servers as extra tools during its own runs. |

## Codex as an MCP server

`codex mcp-server` starts Codex as a stdio MCP server ("Start Codex as an MCP server (stdio)"). An **offline** `initialize` + `tools/list` handshake — no model call — advertised:

- protocol version `2025-03-26`
- server version `0.144.1`
- exactly **two** tools: `codex` and `codex-reply`

> Verified offline only. The handshake and tool schemas were captured; **actual tool calls were not exercised** (they spend usage). Treat call-time behavior as documented-but-not-observed.

### Tool `codex` — start a thread

| | Fields |
|---|---|
| **Required input** | `prompt` |
| **Optional input** | `approval-policy` (`untrusted` \| `on-request` \| `never`), `base-instructions`, `compact-prompt`, `config`, `cwd`, `developer-instructions`, `model`, `sandbox` (`read-only` \| `workspace-write` \| `danger-full-access`) |
| **Output requires** | `threadId`, `content` |

### Tool `codex-reply` — continue a thread

| | Fields |
|---|---|
| **Required input** | `prompt` |
| **Thread selection** | `threadId` (preferred); `conversationId` (deprecated compatibility alias) |
| **Output requires** | `threadId`, `content` |

Note the hyphenated parameter names (`approval-policy`, not the CLI's `-a`). The `sandbox` enum matches `-s`, but `approval-policy` uses MCP-specific values (`untrusted`/`on-request`/`never`). Capture `threadId` from the first `codex` result and pass it to every `codex-reply`.

## When MCP beats a subprocess

The skill's default is `codex exec` as a child process; MCP is optional. Reach for the server only when the extra machinery pays for itself.

| Factor | Direct subprocess (`codex exec`) | `codex mcp-server` |
|---|---|---|
| Lifecycle | One process per task | One long-lived server, many turns |
| Turn model | Re-invoke + `exec resume <id>` | `codex` starts, `codex-reply` continues, in-session |
| Setup | None beyond the binary | Client must be configured to launch and speak MCP |
| Surface | Small, fully verified here | Larger; call-time behavior unverified here |
| Best for | Bounded analyze / implement / review / extract | A persistent multi-turn orchestrator that already speaks MCP |

- **Keep it optional.** Do **not** auto-install or auto-configure the MCP server as a side effect of any task.
- If a one-shot or a few `exec resume` turns will do, use the subprocess route — smaller and fully verified ([`automation-and-sessions.md`](automation-and-sessions.md)).

## Consuming external MCP servers

`codex mcp` manages *external* servers that Codex may call as tools:

| Subcommand | Purpose |
|---|---|
| `list` | Show configured external MCP servers |
| `get` | Show one server's configuration |
| `add` | Register a server |
| `remove` | Unregister a server |
| `login` / `logout` | Manage a server's auth |

`add` / `remove` / `login` / `logout` **mutate persistent config** under `~/.codex`. The verified `codex doctor` baseline reported **no MCP servers configured**; registering one changes global state for every later run. Do not register servers on the user's behalf without an explicit request.

## Advanced and experimental surfaces

Beyond `exec` / `review` / `resume`, Codex ships preview surfaces. Maturity below is quoted from each command's own `--help` header. **Probe `--help` and the maturity marker before using any of these — they change between versions,** and several were never exercised live (dossier §15 lists cloud, app-server, remote-control, and exec-server as untested).

| Command | Maturity (from `--help`) | Nested commands | State change |
|---|---|---|---|
| `codex app-server` | `[experimental]` | `daemon`, `proxy`, `generate-ts`, `generate-json-schema` | Runs / daemonizes a server |
| `codex remote-control` | `[experimental]` | `start`, `stop`, `pair` | Starts the daemon with remote control |
| `codex cloud` | `[EXPERIMENTAL]` | `exec`, `status`, `list`, `apply`, `diff` | `apply` writes diffs locally |
| `codex exec-server` | `[EXPERIMENTAL]` | (none; `--listen <URL>`) | Runs a standalone service |
| `codex plugin` | (unmarked) | `add`, `list`, `marketplace`, `remove` | `add` / `remove` mutate plugin config |
| `codex sandbox` | (unmarked) | runs a command under seatbelt | Executes the given command |
| `codex execpolicy` | hidden; docs say experimental | `check` | Read-only rule check |

Do not build a workflow on any of these without your own probe. The full command inventory and parse-verified flag matrix live in [`command-map.md`](command-map.md).

## The `codex sandbox` runner

`codex sandbox [OPTIONS] [COMMAND]...` runs an arbitrary command under Codex's OS sandbox (seatbelt on macOS) — **no model call**. Use it to reproduce and inspect the same filesystem/network denials an `exec` run hits, without spending usage.

Key flags (verified via `--help`):

- `--log-denials` — **macOS only**; capture sandbox denials via `log stream` and print them after the command exits. The fastest way to see *what* a read-only run was denied.
- `-P, --permission-profile <NAME>` — apply a named permissions profile from the active config stack.
- `-p/--profile`, `-C/--cd`, `-c` — profile, working directory, and config overrides, as elsewhere.

```bash
# Show exactly what `git status` touches under the sandbox (macOS)
codex sandbox --log-denials -- git status
```

Use this for [`troubleshooting.md`](troubleshooting.md) layer 6 — explaining the benign macOS Git cache write-denials that appear under a read-only sandbox.

## The hidden `execpolicy` command

`codex execpolicy` is installed and works but is **absent from `codex --help`**; official docs mark it experimental. It evaluates Starlark execution-policy rules and reports a verdict — it does **not** run the command.

```bash
# Check whether a command would be allowed by a rules file (read-only)
codex execpolicy check --rules ./rules.star -- rm -rf /tmp/x
```

`codex execpolicy check` requires `--rules <PATH>` (repeatable) plus command tokens; `--pretty` formats the JSON verdict. Because it is hidden, discover it by probe, not from the root list ([`command-map.md`](command-map.md)).

## Feature flags and config persistence

- `codex features list` — **read-only**; 92 records across Stable (29), Experimental (3), Under development (27), Deprecated (3), Removed (30).
- `codex features enable <name>` / `disable <name>` — **write `config.toml`** and persist across runs.

Treat `enable` / `disable` as configuration surgery, not a per-call toggle. For a one-off, prefer the equivalent non-persistent override on the single command — `-c features.<name>=true` (or `--enable <name>` / `--disable <name>`, both `== -c features.<name>=…`) — instead of mutating the user's config. Feature **stage** is not command **availability**: a `removed` feature row can coexist with a live command (e.g. the `remote_control` feature vs the `remote-control` command). See [`security-and-config.md`](security-and-config.md) for config precedence and trust.

## Official guide

Codex MCP server reference: <https://developers.openai.com/codex/mcp-server>. Re-read it and re-probe `codex mcp-server` whenever `codex --version` changes from the `0.144.1` baseline.
