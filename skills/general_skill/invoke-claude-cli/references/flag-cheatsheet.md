# Flag cheatsheet (alphabetical)

Every flag the skill discusses, with one-line semantics. Verified against `claude --help` for version 2.1.x.

| Flag | One-line meaning |
|---|---|
| `--add-dir <dirs...>` | Extend tool-accessible roots beyond cwd. |
| `--agent <name>` | Use a named agent definition for the session. |
| `--agents <json>` | Define custom agents inline as JSON. |
| `--allow-dangerously-skip-permissions` | Enable `--dangerously-skip-permissions` as an option (not on by default). |
| `--allowedTools / --allowed-tools <tools...>` | Permission allowlist for non-bypass modes. Do not treat as safety boundary when `bypassPermissions` is used. |
| `--append-system-prompt <prompt>` | Append text after the default system prompt. **Preferred for role-setting in agents.** |
| `--bare` | Strip hooks, LSP, plugin sync, auto-memory, keychain, CLAUDE.md discovery. Sets `CLAUDE_CODE_SIMPLE=1`. |
| `--betas <names...>` | API beta headers (API-key users only). |
| `--brief` | Enable SendUserMessage tool for agent-to-user communication. |
| `--chrome` | Enable Claude in Chrome integration. |
| `-c, --continue` | Resume the most recent session in cwd. Fragile for agents. |
| `--dangerously-skip-permissions` | Bypass all permission checks. Sandbox-only. |
| `-d, --debug [filter]` | Debug mode with optional category filter. |
| `--debug-file <path>` | Write debug logs to file. |
| `--disable-slash-commands` | Disable all skills. |
| `--disallowedTools / --disallowed-tools <tools...>` | Denylist of tools. Fails open on new tools. |
| `--effort <level>` | Reasoning effort: low / medium / high / xhigh / max; Xiaohu rollout defaults to `--effort max`. |
| `--exclude-dynamic-system-prompt-sections` | Move cwd/env/memory/git-status to first user message for better cache reuse. |
| `--fallback-model <model>` | Auto-fallback if primary overloaded. **`-p` only.** |
| `--file <specs...>` | Download resources at startup. Format: `file_id:relative_path`. |
| `--fork-session` | When resuming, branch off with a new session ID. |
| `--from-pr [value]` | Resume session linked to a PR. |
| `-h, --help` | Help. |
| `--ide` | Auto-connect to IDE on startup. |
| `--include-hook-events` | Include hook lifecycle events in `stream-json`. |
| `--include-partial-messages` | Include partial message chunks for token streaming. `-p` + `stream-json` only. |
| `--input-format <fmt>` | `text` (default) or `stream-json`. `-p` only. |
| `--json-schema <schema>` | Constrain structured answer output; current CLI returns it in `structured_output`. **Highly recommended for agent calls.** |
| `--max-budget-usd <amount>` | Hard spend cap. `-p` only. Required for unattended runs. |
| `--mcp-config <configs...>` | Load MCP servers from JSON. |
| `--mcp-debug` | Deprecated MCP debug mode; use `--debug` instead. |
| `--model <model>` | Model alias (`sonnet`, `opus`, `haiku`; alias resolves to the latest in the family, e.g. `opus` → Opus 4.8) or full ID (`claude-opus-4-8`). Literal `opus4.8` is rejected. |
| `-n, --name <name>` | Display name for the session. |
| `--no-chrome` | Disable Claude in Chrome integration. |
| `--no-session-persistence` | Don't save session to disk. `-p` only. |
| `--output-format <fmt>` | `text` (default), `json`, or `stream-json`. `-p` only. |
| `-p, --print` | Non-interactive mode: print response and exit. **Required for subprocess use.** |
| `--permission-mode <mode>` | `default`, `plan`, `acceptEdits`, `dontAsk`, `bypassPermissions`, `auto`; Xiaohu rollout uses `bypassPermissions` for all headless calls. |
| `--plugin-dir <path>` | Load plugin from directory or .zip. Repeatable. |
| `--plugin-url <url>` | Fetch plugin .zip from URL. Repeatable. |
| `--remote-control [name]` | Start an interactive session with Remote Control enabled. |
| `--remote-control-session-name-prefix <prefix>` | Prefix for auto-generated Remote Control session names. |
| `--replay-user-messages` | Echo user messages back on stdout. `stream-json` I/O only. |
| `-r, --resume [value]` | Resume by session ID. **Preferred for multi-turn agents.** |
| `--session-id <uuid>` | Set the session UUID up-front. |
| `--setting-sources <list>` | Comma-separated: `user`, `project`, `local`. |
| `--settings <file-or-json>` | Load extra settings. |
| `--strict-mcp-config` | Ignore MCP configs outside `--mcp-config`. |
| `--system-prompt <prompt>` | **Replaces** default system prompt. Use sparingly. |
| `--tmux` | Create a tmux session for a `--worktree` session. |
| `--tools <tools...>` | Specify available tools. `""` disables all; with bypass use explicit tool names for execution. |
| `--verbose` | Verbose output. |
| `-v, --version` | Print version. |
| `-w, --worktree [name]` | Create git worktree for the session. |
