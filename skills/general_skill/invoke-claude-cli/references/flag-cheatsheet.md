# Flag cheatsheet (alphabetical)

Every flag the skill discusses, with one-line semantics. Current visible flags were checked against
`claude --help` 2.1.220. Flags marked **(2.1.207: works, hidden from `--help`)** have prior
executable evidence but are not listed in top-level help — confirm on your build before scripting.

| Flag | One-line meaning |
|---|---|
| `--add-dir <dirs...>` | Extend tool-accessible roots beyond cwd. |
| `--advisor <model>` | Enable a server-side advisor tool for the session. |
| `--agent <name>` | Use a named agent definition for the session. |
| `--agents <json>` | Define custom agents inline as JSON. |
| `--allow-dangerously-skip-permissions` | Enable `--dangerously-skip-permissions` as an option (not on by default). |
| `--allowedTools / --allowed-tools <tools...>` | Allowlist of tools. Anything not listed is denied in `-p` mode. Permission-rule syntax, e.g. `"Edit Read Bash(git status *)"`. |
| `--append-system-prompt <prompt>` | Append text after the default system prompt. **Preferred for role-setting in agents.** |
| `--append-system-prompt-file <path>` | Same, loaded from a file. |
| `--append-subagent-system-prompt <prompt>` | Append text to every subagent's system prompt. |
| `--ax-screen-reader` | Screen-reader-friendly output (flat text, no borders/animations). |
| `--bare` | Skip hooks, LSP, plugin sync, attribution, auto-memory, keychain, CLAUDE.md discovery. Sets `CLAUDE_CODE_SIMPLE=1`. Does NOT disable tools. Auth = `ANTHROPIC_API_KEY`/`apiKeyHelper` only. |
| `--betas <names...>` | API beta headers (API-key users only). |
| `--bg, --background` | Start as a background agent and return immediately (manage with `claude agents`). |
| `--brief` | Enable the `SendUserMessage` tool for agent-to-user communication. |
| `-c, --continue` | Resume the most recent session in cwd. Fragile for agents. |
| `--chrome` / `--no-chrome` | Enable/disable the Claude-in-Chrome integration. |
| `--cloud` | Create a new web session on claude.ai (cannot combine with `--print`). |
| `--dangerously-skip-permissions` | Bypass all permission checks. Sandbox-only. |
| `-d, --debug [filter]` | Debug mode with optional category filter (e.g. `"api,hooks"`). |
| `--debug-file <path>` | Write debug logs to a file (implies debug mode). |
| `--disable-slash-commands` | Disable all skills/commands. |
| `--disallowedTools / --disallowed-tools <tools...>` | Denylist of tools. Fails open on new tools. |
| `--effort <level>` | Reasoning effort: `low` / `medium` / `high` / `xhigh` / `max`. |
| `--exclude-dynamic-system-prompt-sections` | Move cwd/env/memory/git-status into the first user message for better cache reuse. |
| `--fallback-model <model[,model...]>` | Ordered fallback if primary is overloaded/unavailable; retries primary each turn. **`-p` only.** Choose only quality downgrades the task permits. |
| `--file <specs...>` | Download resources at startup. Format: `file_id:relative_path`. |
| `--fork-session` | When resuming, branch off with a new session ID. |
| `--forward-subagent-text` | Forward subagent text/thinking with its parent tool-use ID. Only with `-p --output-format stream-json`. |
| `--from-pr [value]` | Resume a session linked to a PR. |
| `-h, --help` | Help. |
| `--ide` | Auto-connect to an IDE on startup. |
| `--include-hook-events` | Include hook lifecycle events in `stream-json`. |
| `--include-partial-messages` | Include partial message chunks for token streaming. `-p` + `stream-json` only. |
| `--init-only` | Run Setup/SessionStart hooks, then exit without a conversation. |
| `--input-format <fmt>` | `text` (default) or `stream-json`. `-p` only. |
| `--json-schema <schema>` | Constrain the answer to a JSON Schema; result lands in `.structured_output`. Invalid schema errors (2.1.205+). **Highly recommended for agent calls.** |
| `--max-budget-usd <amount>` | Hard spend cap. `-p` only. Required for unattended runs. |
| `--max-turns <n>` | Hard cap on agentic turns. **(2.1.207: works, hidden from `--help`)** |
| `--mcp-config <configs...>` | Load MCP servers from JSON files or strings. |
| `--model <model>` | Model alias (`fable`, `opus`, `sonnet`, `haiku`) or full ID (`claude-opus-5`, `claude-fable-5`). Pass explicitly in unattended work. |
| `-n, --name <name>` | Display name for the session. |
| `--no-session-persistence` | Don't save the session to disk. `-p` only. |
| `--output-format <fmt>` | `text` (default), `json`, or `stream-json`. `-p` only. |
| `-p, --print` | Non-interactive: print response and exit. **Required for subprocess use.** |
| `--permission-mode <mode>` | `default` (labeled `manual`), `acceptEdits`, `plan`, `auto`, `dontAsk`, `bypassPermissions`. |
| `--permission-prompt-tool <mcp_tool>` | Route permission decisions to an MCP tool for programmatic approval. **(2.1.207: works, hidden from `--help`)** |
| `--plugin-dir <path>` | Load a plugin from a directory or .zip. Repeatable. |
| `--plugin-url <url>` | Fetch a plugin .zip from a URL. Repeatable. |
| `--prompt-suggestions` | In print/SDK mode, emit a `prompt_suggestion` message (predicted next prompt) after each turn. |
| `--replay-user-messages` | Echo user messages back on stdout. `stream-json` I/O only. |
| `-r, --resume [value]` | Resume by session ID or name. **Preferred for multi-turn agents.** |
| `--safe-mode` | Start with all customizations disabled (troubleshooting). Sets `CLAUDE_CODE_SAFE_MODE=1`. |
| `--session-id <uuid>` | Set the session UUID up-front. |
| `--setting-sources <list>` | Comma-separated: `user`, `project`, `local`. |
| `--settings <file-or-json>` | Load extra settings from a file or JSON string. |
| `--strict-mcp-config` | Ignore MCP configs outside `--mcp-config`. |
| `--system-prompt <prompt>` / `--system-prompt-file <path>` | **Replaces** the default system prompt. Use sparingly. |
| `--teleport` | Resume a web session in the local terminal. |
| `--tmux` | Create a tmux session for the worktree (requires `--worktree`). |
| `--tools <tools...>` | Specify the full available tool set. `""` disables all; `"default"` uses all. |
| `--verbose` | Verbose output; required for the full `stream-json` turn stream in `-p`. |
| `-v, --version` | Print version. |
| `-w, --worktree [name]` | Create a git worktree for the session. |

## Current rolling model aliases

| Alias | Current release state |
|---|---|
| `opus` | Claude Opus 5 (`claude-opus-5`) in Claude Code 2.1.219; 1M context. |
| `sonnet` | Rolling newest Sonnet; Claude Code 2.1.197 introduced Sonnet 5 with 1M context. |
| `fable` | Claude Fable 5 (`claude-fable-5`), introduced in 2.1.170; 1M context. |
| `haiku` | Rolling Haiku family alias for cheap, bounded tasks. |

Use aliases for newest-family behavior and exact IDs only for deliberate reproducibility. Do not assume
an organization or CLI default selects the intended family.

## Subcommands (2.1.220)

| Subcommand | Purpose |
|---|---|
| `claude agents` | Manage background agents (view/dispatch); `--json` prints active sessions for scripting. |
| `claude auth login\|logout\|status` | Manage authentication (`status` prints JSON). |
| `claude auto-mode` | Inspect the auto-mode classifier configuration. |
| `claude doctor` | Read-only install/settings diagnostics. |
| `claude gateway` | Run the enterprise auth/telemetry gateway. |
| `claude install [target]` | Install/reinstall the native binary (`stable`/`latest`/version). |
| `claude mcp` | Configure and manage MCP servers. |
| `claude plugin` | Manage plugins. |
| `claude project purge [path]` | Delete all local Claude Code state for a project. |
| `claude setup-token` | Generate a long-lived OAuth token for CI/scripts. |
| `claude ultrareview [target]` | Cloud-hosted multi-agent code review of a branch/PR. |
| `claude update` / `upgrade` | Check for and install updates. |

> Docs may list `claude attach/logs/stop/respawn/rm <id>` and `claude daemon status\|stop` for
> background-session lifecycle. They are not in the 2.1.220 top-level help verified for this refresh.
> Always confirm against your installed build before scripting lifecycle operations.
