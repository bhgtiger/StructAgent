# Changelog

## 2026-07-26 — refresh for Claude Code 2.1.220

Updated the skill against the official Claude Code changelog through 2.1.220 and the installed
2.1.220 CLI.

- **Current model policy.** Corrected the stale Opus 4.8 guidance: the "opus" alias now resolves to
  Claude Opus 5 ("claude-opus-5", 1M context). Documented the distinct current roles of Opus 5,
  Sonnet 5, Fable 5, and Haiku; aliases versus exact IDs; and why an implicit default is unsafe for
  unattended work.
- **Quality-aware fallback.** Documented ordered fallback lists and made clear that fallback is an
  approved quality downgrade, not a reason to silently route consequential execution to Haiku.
  The execution examples and Python client now default to Opus with an explicit Sonnet fallback;
  removed the redundant Haiku-to-Haiku fallback from the critique examples.
- **Headless observability.** Added 2.1.219 "mcp_server_errors" handling to stream-json guidance
  and documented "--forward-subagent-text", current nested-subagent depth, and fan-out controls.
- **Background guidance.** Refreshed "claude agents" details for 2.1.220, including "--cwd",
  while preserving the distinction between top-level "--bg" sessions and nested subagents.

## 2026-07-12 — refresh for Claude Code 2.1.207

Updated the whole skill against the live `claude` 2.1.207 binary. Highlights:

### Corrections (things the old version got wrong or stale)
- **Structured output moved.** `--json-schema` now returns the parsed object in a top-level
  **`structured_output`** field (with the JSON also present as a *string* in `.result`, and
  `stop_reason: "tool_use"`). The old guidance to `json.loads(.result)` was fragile.
- **`--json-schema` is not hard-enforced.** If the model answers in prose (clarification/refusal),
  `structured_output` is absent, `.result` is prose, and `is_error` stays `false`. The old claim that
  non-conforming output causes `is_error: true` was incorrect. All scripts/clients now branch on the
  presence of `structured_output`. (The *schema itself* is validated at startup since 2.1.205.)
- **Permission modes.** `--help` now advertises `acceptEdits, auto, bypassPermissions, manual,
  dontAsk, plan`. `default` is the canonical name, CLI-labeled `manual`, with `manual` accepted as an
  alias since 2.1.200. Mode semantics clarified (`acceptEdits` also allows `mkdir/touch/mv/cp`;
  `dontAsk` denies anything not pre-approved; `auto` = auto-approve with background safety checks).
- **Bash permission syntax.** Space-form `Bash(git status *)` is now canonical (wildcards allowed at
  any position, word-boundary semantics); `Bash(git status:*)` still works as a trailing-wildcard
  shorthand. Scripts updated to the space form.
- **Model aliases.** `fable` / `opus` / `sonnet` / `haiku` with full IDs like `claude-fable-5`;
  dropped the stale `claude-sonnet-4-6` example.
- **Envelope shape.** Documented the real 2.1.207 fields: `ttft_ms`, `ttft_stream_ms`,
  `time_to_request_ms`, populated `usage.iterations` and `modelUsage`.

### Additions
- `--max-turns` as a turn cap alongside `--max-budget-usd` (works on 2.1.207).
- `--permission-prompt-tool` for programmatic, per-call approval via an MCP tool.
- `--append-system-prompt-file` / `--system-prompt-file` / `--append-subagent-system-prompt`.
- 10 MB stdin cap (2.1.128+); `stream-json` in `-p` needs `--verbose`; `--bare` will become the `-p`
  default and does **not** disable tools.
- New `references/background-agents.md` — `--bg/--background` + `claude agents --json`, with an
  explicit version caveat that `logs/attach/stop/respawn/rm/daemon` subcommands are documented but
  absent on 2.1.207. **`--bg` conflicts with `-p`** (prompt is positional; `--print`-only cost flags
  don't apply to background sessions).
- Read-only command set, compound-command splitting, process-wrapper stripping, and environment-runner
  transparency in the tool-gating / safety notes.
- New evals: `structured-output-parsing-correctness` and `background-fanout-poll`.

### How this was verified
Ground truth came from `claude --version`, `claude --help`, subcommand `--help`, parse-time choice
validation, a handful of budgeted `claude -p` calls capturing the real JSON envelope, and the official
`code.claude.com/docs` CLI/permissions/headless references. Version-specific claims are dated inline.
