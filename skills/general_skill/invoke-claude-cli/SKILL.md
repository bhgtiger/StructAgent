---
name: invoke-claude-cli
description: Authoritative guide for invoking the `claude` CLI as a subprocess from a host agent — for code review, plan critique, executing approved plans, multi-turn refinement, background/parallel delegation, or any programmatic hand-off to Claude Code. Use this skill whenever you are about to write or modify a call to `claude` (e.g. `claude -p`, `subprocess.run(["claude", ...])`, `Popen`, a Bash pipeline, an n8n/LangGraph/AutoGen/CrewAI node that shells out to Claude, or a Codex/GPT/Gemini orchestrator driving Claude Code). Triggers on phrases like "shell out to claude", "call claude -p", "have Claude review/execute this plan", "hand off to claude code", "spawn claude subprocess", "claude headless", "claude --print", "non-interactive claude", "background claude agent", or whenever a non-Claude agent or orchestrator drives Claude Code. Covers headless invocation, output formats, structured output, session resumption, tool/permission gating, background agents, system-prompt injection, model + cost controls, the dangerous-flag matrix, and worked agent-to-CLI handoff patterns. Consult BEFORE writing the subprocess call — flag choices change the safety envelope and the wrong combination silently leaks tools or fails to parse.
---

# Invoking the `claude` CLI from another agent

> **Verified against `claude` 2.1.220 (July 2026).** Where behavior changed across the 2.1.x
> series, the version is noted inline. Re-check with `claude --version` and `claude --help`
> before relying on any exact field name or flag — the CLI ships almost daily. Current rolling
> aliases: `fable` (Fable 5; availability/usage policy is account-specific), `opus` (Opus 5,
> 1M context), `sonnet` (Sonnet 5, 1M context), and `haiku` (latest Haiku family).

## Mental model

You — the calling agent — are the **orchestrator**. You spawn `claude` as a child process to do one of:

1. **Critique** a plan or diff you produced (read-only, fast).
2. **Execute** an approved plan inside a sandboxed tool set.
3. **Continue a session** for multi-turn refinement.
4. **Dispatch background work** and poll it while you do other things (`--background` + `claude agents`).

The flag set you choose determines *what Claude is allowed to do, what it costs, how you parse the
answer, and whether it can be resumed*. Pick flags from the decision tree below; do not copy-paste a
generic command and hope.

## Decision tree (read this first)

```
What do you need from Claude?
├─ Just an answer (review / plan critique / analysis)
│   → claude -p --bare --output-format json --tools ""
│   → No tool flags fire (no tools by default for pure Q&A); --tools "" makes that explicit + cheaper
│   → Want a strict shape? add --json-schema and read .structured_output (see below)
│
├─ Claude must touch files / run commands (execute a plan)
│   → claude -p --permission-mode dontAsk
│   → --allowedTools "Edit Read Bash(git status *)"   ← always allowlist, never blanket-allow
│   → --output-format json so you can detect is_error and permission_denials
│   → --max-turns N and --max-budget-usd X to bound cost
│
├─ Multi-turn refinement (you'll iterate)
│   → First call:  --session-id <uuid> + --output-format json
│   → Later calls: --resume <same-uuid> (or --continue for "most recent in this cwd")
│   → Keep the same --allowedTools across turns
│
└─ Fire-and-poll / parallel fan-out
    → claude --bg "<task>" ... to launch and return immediately (prompt is positional; NOT -p)
    → poll with claude agents --json ; see references/background-agents.md
```

## Minimum viable invocation

```bash
echo "Review this plan: rewrite auth in Go" | claude -p --output-format json
```

`-p` (a.k.a. `--print`) makes Claude run non-interactively: read the prompt from argv or stdin,
print one response, and exit. **Without `-p`, `claude` opens an interactive TUI and an agent
subprocess will hang forever.**

The prompt can be passed three ways — pick whichever your host language makes cleanest:

| Method | Example | When to use |
|---|---|---|
| Positional arg | `claude -p "your prompt"` | Short prompts. Watch shell escaping. |
| stdin | `echo "..." \| claude -p` | Multi-line, file contents, diffs. **Preferred for agents.** |
| Both | `cat plan.md \| claude -p "Review this plan"` | Argv = instruction, stdin = data. Argv text is appended to the stdin content. |

> **stdin is capped at 10 MB** (since 2.1.128). Larger inputs exit non-zero with a clear error —
> write the content to a file and reference the path in your prompt instead of piping it.

## Output formats

`--output-format` is only honored with `-p`. Options:

- **`text`** (default) — plain prose. Fine for human eyes, fragile for parsing.
- **`json`** — one JSON object on a single line. **Use this for all programmatic calls.**
- **`stream-json`** — newline-delimited JSON events as Claude works. In `-p` mode you must also pass
  `--verbose` to get the full turn-by-turn stream (add `--include-partial-messages` for token deltas).

### The `json` envelope

A `--output-format json` response looks like this (real shape captured from `claude` 2.1.207;
trimmed for readability):

```jsonc
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "api_error_status": null,
  "result": "…the actual response text…",
  "structured_output": { /* present only when --json-schema is used AND the model complied */ },
  "stop_reason": "end_turn",       // "tool_use" when a --json-schema answer was produced
  "session_id": "8df5d8f2-…",
  "uuid": "100c6327-…",            // per-invocation ID, distinct from session_id
  "num_turns": 2,
  "duration_ms": 8723,
  "duration_api_ms": 9882,
  "ttft_ms": 3089,                 // time-to-first-token (2.1.x)
  "total_cost_usd": 0.0185,
  "usage": { "input_tokens": 20, "output_tokens": 520, "cache_read_input_tokens": 7081, … },
  "modelUsage": { "claude-haiku-4-5-20251001": { "inputTokens": 540, "costUSD": 0.0185, … } },
  "permission_denials": [],
  "terminal_reason": "completed",
  "fast_mode_state": "off"
}
```

Fields the calling agent cares about:

| Field | Why you read it |
|---|---|
| `result` | The answer text. With `--json-schema`, also the schema JSON *as a string*. |
| `structured_output` | The schema answer *already parsed into an object*. **Prefer this over `result` when you used `--json-schema`.** Absent if the model answered in prose instead. |
| `is_error` | `true` on auth failure, budget/turn cap exceeded, API error, etc. **Always check before using `result`.** |
| `session_id` | Save this if you might `--resume` later (or set it yourself with `--session-id`). |
| `total_cost_usd` / `modelUsage` | Per-invocation and per-model spend for your orchestrator's accounting. |
| `num_turns` | Internal turns Claude took (high = Claude struggled or looped). |
| `permission_denials` | Tool calls Claude tried but wasn't allowed. Tune your `--allowedTools` from these. |
| `stop_reason` | `end_turn` (normal prose), `tool_use` (a `--json-schema` answer landed), `max_tokens`, etc. |

### Structured output with `--json-schema`

Pass a JSON Schema to force Claude's *answer* (not the envelope) into a known shape:

```bash
claude -p \
  --output-format json \
  --json-schema '{"type":"object","properties":{"verdict":{"enum":["approve","reject","revise"]},"reasons":{"type":"array","items":{"type":"string"}}},"required":["verdict","reasons"],"additionalProperties":false}' \
  "Review this plan and return your verdict."
```

Under the hood this hands Claude a `StructuredOutput` tool (available even with `--tools ""`). When
Claude calls it, the CLI populates two fields:

- **`structured_output`** — the answer as a parsed JSON object. Read this directly. `jq '.structured_output'`.
- **`result`** — the same content as a JSON string (`json.loads` it if you prefer).

and `stop_reason` becomes `"tool_use"`.

> **`--json-schema` is NOT a hard guarantee.** If Claude decides to answer in prose instead — a
> refusal, a clarifying question, or just conversational output — the CLI returns `is_error: false`,
> `stop_reason: "end_turn"`, **no `structured_output` field**, and prose in `result`. Robust callers
> must handle this: prefer `structured_output`, and if it's missing, treat `result` as prose (don't
> blindly `json.loads` it). See `references/output-formats.md` for the exact parse pattern.

The *schema itself* is validated at startup (since 2.1.205): an invalid schema exits with
`Error: --json-schema is not a valid JSON Schema`. The `format` keyword (e.g. `"format":"email"`) is
accepted but treated as an annotation, not enforced. This is still the single most useful flag for
agent-to-agent handoffs — it removes most parsing fragility.

## Session lifecycle

Sessions persist to disk by default and can be resumed.

| Flag | Effect |
|---|---|
| (none) | One-shot. New session each call, still saved under `~/.claude/projects/<cwd-slug>/` unless `--no-session-persistence`. |
| `--session-id <uuid>` | Set a known session ID up-front so you can resume by ID without scraping the response. Must be a valid UUID. **Use this in agents.** |
| `-c, --continue` | Resume the most recent session in the current directory. Convenient interactively, fragile for agents (depends on cwd state). |
| `-r, --resume <uuid>` | Resume by session ID (or name). **Preferred for agents.** |
| `--fork-session` | When resuming, branch off with a new ID instead of mutating the original. Explore alternatives without losing the trunk. |
| `--no-session-persistence` | Ephemeral; nothing written to disk. `-p` only. Use for stateless one-shots in CI. |

Session-ID lookup for `--resume`/`--continue` is scoped to the current project directory and its git
worktrees — run resume calls from the same cwd you started in.

```bash
SESSION=$(uuidgen | tr 'A-Z' 'a-z')   # generate up-front
claude -p --session-id "$SESSION" --output-format json "First message" > turn1.json
claude -p --resume "$SESSION"        --output-format json "Follow-up"   > turn2.json
```

## Tool gating

Claude has built-in tools (Read, Edit, Write, Bash, Grep, Glob, WebFetch, etc.). For agent-driven
runs you almost always want to **constrain** what Claude can do.

### Three flags, three meanings

- **`--allowedTools "Edit Read Bash(git status *)"`** — allowlist. Anything not listed requires
  permission (and in `-p` mode that means it gets auto-denied unless the permission mode approves it).
  Prefer this. Uses permission-rule syntax (below).
- **`--disallowedTools "Bash WebFetch"`** — denylist. Use when the default set is fine except for a
  few. Riskier — tools added in future versions are allowed by default.
- **`--tools "Edit,Read,Bash"`** — *replaces* the built-in tool list entirely. `"default"` = all
  tools, `""` = no tools. The strictest scoping mechanism.

> `--bare` does **not** disable tools — in bare mode Claude still has Bash, file-read, and file-edit
> tools. To run pure Q&A with no tools, add `--tools ""`.

### Bash sub-command syntax (permission rules)

`--allowedTools` entries use Claude Code's permission-rule syntax:

- **`Bash(git status *)`** — space + `*` allows `git status` followed by anything. The space enforces
  a word boundary: `Bash(ls *)` matches `ls -la` but **not** `lsof`. Wildcards may appear anywhere:
  `Bash(git * main)`, `Bash(* --version)`.
- **`Bash(git status:*)`** — `:*` is an equivalent shorthand for a **trailing** wildcard only. It is
  recognized only at the end; `Bash(git:* push)` treats the colon as a literal and won't match.
- **`Bash(npm run build)`** — exact match, no wildcard.

Two footguns to know:
- **Compound commands are split.** `Bash(safe-cmd *)` does **not** authorize `safe-cmd && rm -rf .`;
  each subcommand (`&&`, `||`, `;`, `|`, `&`, newline) must match a rule independently.
- **Environment runners are transparent.** `Bash(devbox run *)`, `npx`, `docker exec` execute their
  arguments, so such a rule effectively allows anything after `run`. Write specific rules
  (`Bash(devbox run npm test)`), one per inner command.

A built-in read-only command set (`ls`, `cat`, `grep`, `find`, `pwd`, `head`, `tail`, `wc`, `diff`,
read-only `git`, …) runs without a prompt in **every** mode, so you don't need to allowlist those.

### Read-only critique (no tools fire)

If you only need an answer about pasted text — like reviewing a diff — pass `--tools ""` to disable
all tools. Faster, cheaper, no risk of file writes.

```bash
git diff main...HEAD | claude -p --bare --tools "" --output-format json \
  "Review this diff. List bugs, security issues, and missing tests."
```

### Programmatic approval: `--permission-prompt-tool`

Instead of a static allow/deny list, point Claude at an MCP tool that decides each permission request
at runtime: `--permission-prompt-tool mcp__approver__approve`. Your orchestrator implements the
approver and can apply arbitrary policy (rate limits, human-in-the-loop, path checks) per tool call.
Use this when a flat allowlist can't express your rules.

## Permission modes

`--permission-mode` sets the baseline for what happens when Claude wants a tool:

| Mode | Behavior | Use case |
|---|---|---|
| `default` | Prompts on first use of each tool. **In `-p` mode a prompt auto-denies** — Claude can't ask. CLI-labeled **Manual**; `manual` is an accepted alias (2.1.200+). | Interactive; or `-p` when you want everything not pre-approved to be denied. |
| `plan` | Read-only. Claude reads files and runs read-only shell commands but cannot edit or run write commands. | Plan generation, exploration. **Safest "tell me what you'd do".** |
| `acceptEdits` | Auto-approves file edits *and* common filesystem commands (`mkdir`, `touch`, `mv`, `cp`) in the working dir. Other Bash/network still needs an allow rule. | Trusted, scoped execution. |
| `dontAsk` | Auto-**denies** any tool not in your `permissions.allow` rules / `--allowedTools` / the read-only set. | Headless agent execution with a tight `--allowedTools`. |
| `auto` | Auto-approves tool calls with background safety checks that verify actions match your request. | Semi-trusted automation where you want momentum with a guardrail. |
| `bypassPermissions` | Skips prompts (except explicit `ask` rules). `rm -rf /` / `rm -rf ~` still prompt as a circuit breaker. Same as `--dangerously-skip-permissions`. | **Only inside an isolated sandbox.** See safety section. |

The intended pairing for agent-driven execution: **`--permission-mode dontAsk --allowedTools "..."`**.
Headless behavior with an explicit, auditable tool surface.

## System prompt injection

- **`--append-system-prompt "..."`** adds your instruction *after* Claude Code's default system
  prompt. Use it to set Claude's role in your orchestration ("You are called by an external planner.
  Return only the schema."). **Prefer this 99% of the time.**
- **`--append-system-prompt-file <path>`** — same, loaded from a file. Cleaner for long prompts and
  for `--bare` runs.
- **`--system-prompt "..."` / `--system-prompt-file <path>`** — **replace** the default prompt
  entirely. Claude loses awareness of its tools, conventions, and safety scaffolding. Avoid unless you
  own the full prompt and are deliberately repurposing the CLI as a generic client.
- **`--append-subagent-system-prompt "..."`** — appended to every subagent Claude spawns.

## Model and cost controls

| Flag | What it does |
|---|---|
| `--model fable` / `opus` / `sonnet` / `haiku` | Pick the newest supported member of a model family. Pass one explicitly in unattended work. |
| `--model claude-opus-5` / `claude-fable-5` | Pick a fixed current model ID when a reproducibility requirement justifies pinning. |
| `--fallback-model sonnet,haiku` | Ordered fallback list for a primary model that is overloaded or unavailable; retries the primary at the start of each turn. **`-p` only.** |
| `--max-budget-usd 0.50` | Hard spend cap; run aborts if exceeded. `-p` only. Use on any unattended automation. |
| `--max-turns 8` | Hard cap on agentic turns; stops a tool loop even if the budget isn't hit. |
| `--effort low\|medium\|high\|xhigh\|max` | Reasoning effort for the session. |

### Choose the model deliberately

| Need | Preferred model | Why |
|---|---|---|
| Hardest implementation, deep review, or large-codebase reasoning | `opus` | Claude Code 2.1.219 makes this Claude Opus 5 (`claude-opus-5`), the current Opus model with a 1M-token context window. This is the normal serious-execution default. |
| Strong balanced implementation and ordinary multi-turn work | `sonnet` | Rolling newest Sonnet alias. Claude Code 2.1.197 introduced Sonnet 5 with a 1M-token context window. |
| Intentional frontier-model experiment with confirmed availability and usage policy | `fable` | Claude Fable 5 (`claude-fable-5`) has a 1M-token context window. Do not select it merely because it is newer. |
| Cheap high-volume triage or pasted-text classification | `haiku` | Keep it tool-free, structured, and tightly budgeted. |

Do not rely on the CLI's default model: account, organization, role, and user settings can alter it.
The release notes do not establish a universal Fable-versus-Opus quality ordering. Treat Fable as an
availability-checked choice; use Opus as the normal high-end default unless the task or user specifies
otherwise. Use aliases when you want the current family model, and exact IDs only when a true version
pin is required. Never use informal stale strings such as `opus4.8`.

Fallback is an approved quality downgrade, not merely an availability trick. For an ordinary Opus
task, `--fallback-model sonnet` is sensible. For a Fable task, use an explicit fallback only if the
task permits it (normally `opus`). Omit fallback for work that must not silently degrade in quality;
return a typed unavailable or needs-feedback result instead. Do not silently substitute Haiku for a
quality-critical file-modifying task.

For high-volume critique, `--model haiku --max-budget-usd 0.05 --max-turns 2` is a sane default.
For an auditable run, record the canonical model in the JSON envelope's `modelUsage`. Opus 5 supports
fast mode; treat that as an account/session setting and inspect `fast_mode_state` rather than assuming
it is enabled.

## Clean, hermetic runs: `--bare`

`--bare` skips hooks, LSP, plugin sync, attribution, auto-memory, background prefetches, keychain
reads, and `CLAUDE.md` auto-discovery (sets `CLAUDE_CODE_SIMPLE=1`). It gives you a reproducible call
with zero side effects from the host environment. **It does not disable tools** (add `--tools ""` for
that) and it **does not** load project/user context — pass what you need explicitly via
`--system-prompt[-file]`, `--append-system-prompt[-file]`, `--add-dir`, `--mcp-config`, `--settings`,
`--agents`, `--plugin-dir`.

In `--bare` mode Anthropic auth is strictly `ANTHROPIC_API_KEY` or an `apiKeyHelper` passed via
`--settings` (OAuth and keychain are never read). For CI and non-Claude orchestrators, `--bare` is the
right baseline — and per the docs it will become the **default for `-p`** in a future release, so
adopting it now future-proofs your calls.

## Working directory and scope

`claude` operates in the current working directory by default; tools can only touch files inside that
tree (plus any `--add-dir` roots).

- `--add-dir /path/a /path/b` — extend the tool-accessible roots.
- `cd /target/repo && claude -p ...` — preferred for orchestrators; explicit and easy to audit.
- `-w, --worktree [name]` — run in a fresh git worktree so edits stay isolated from the main checkout.

If your agent calls `claude` from one repo to operate on another, **always set cwd** — don't rely on
`--add-dir` as the only mechanism.

## Background agents (fire-and-poll)

For fan-out or long jobs, launch Claude as a background session and keep working. **`--bg` conflicts
with `-p`** — the prompt is a positional argument and you do *not* pass `--print`:

```bash
claude --bg --permission-mode dontAsk --allowedTools "Read Edit Bash(pytest *)" \
  "Fix the failing tests in tests/."
claude agents --json          # list active sessions as JSON (scriptable, no TTY needed)
```

`--bg`/`--background` returns immediately; `claude agents` opens the management view and
`claude agents --json` prints active sessions for polling. Because `--bg` runs a full (non-print)
session, the `--print`-only cost flags (`--max-budget-usd`, `--fallback-model`,
`--no-session-persistence`) don't apply — bound background cost with tool gating, model choice, and by
stopping runaway sessions from `claude agents`. Finer-grained lifecycle subcommands
(`claude logs/attach/stop/respawn <id>`) appear in current docs but are **not** present in the
2.1.220 top-level help verified for this refresh —
check `claude --help` and `claude agents --help` on your installed build. See
`references/background-agents.md`.

## Exit codes and error handling

`claude -p` exits:
- **0** — ran to completion. **Note: `is_error: true` in the JSON still exits 0** — always check the
  envelope, not just the exit code.
- **non-zero** — process-level failure (bad flags, oversized stdin, OOM, signal). Treat as catastrophic.

```python
result = subprocess.run([...], capture_output=True, text=True, timeout=600)
if result.returncode != 0:
    raise RuntimeError(f"claude crashed: {result.stderr}")
envelope = json.loads(result.stdout)
if envelope["is_error"]:
    raise RuntimeError(f"claude reported error: {envelope['result']}")
answer = envelope.get("structured_output", envelope["result"])
```

**Always set a subprocess `timeout`.** A confused Claude can churn for tens of minutes if `--max-turns`
and `--max-budget-usd` are absent.

## Safety: the dangerous-flag matrix

Some flag combinations expand the blast radius substantially. Reason about every call with this table:

| Combination | Risk | Acceptable when |
|---|---|---|
| `--dangerously-skip-permissions` | Any tool, no checks — `rm -rf`, `git push --force`, exfiltrate via WebFetch. (`rm -rf /` and `~` still prompt as a circuit breaker.) | Inside a Docker/VM sandbox with no network, no credentials, disposable filesystem. **Never on a dev workstation.** |
| `--allow-dangerously-skip-permissions` | Enables the above as an opt-in (not on by default). | Same as above. |
| `--permission-mode bypassPermissions` | Equivalent to `--dangerously-skip-permissions`. | Same as above. |
| `--system-prompt` / `--system-prompt-file` | Strips default safety scaffolding. | Custom agents in trusted environments where you own the full prompt. |
| `--disallowedTools` alone (no `--allowedTools`) | Future tool additions auto-allowed. | Almost never — prefer allowlist. |
| `--add-dir /` or large parent dirs | Expands tool-accessible filesystem. | Only when truly needed and the dir is non-sensitive. |
| No `--max-budget-usd` / `--max-turns` in unattended automation | Runaway cost / tool loops. | Manual / interactive runs. |
| No subprocess timeout | Process can hang. | Never acceptable. Always set one. |

**Rule of thumb — the safest agent-driven invocation:**
`claude -p --bare --no-session-persistence --output-format json --tools "" --max-turns 2 --max-budget-usd 0.10 --model haiku`.
Add capabilities back one flag at a time as you need them.

## Worked examples

The patterns an orchestrating agent uses most are bundled as runnable scripts in `scripts/`. Read them
before implementing a similar handoff:

- **`scripts/01-plan-review.sh`** — pass a plan/diff, get a structured verdict. Read-only, cheap.
- **`scripts/02-execute-plan.sh`** — pass an approved plan with a tight tool allowlist for execution.
- **`scripts/03-multi-turn.sh`** — iterative refinement loop with `--session-id` / `--resume`.
- **`scripts/claude_client.py`** — a Python wrapper showing how a non-Claude orchestrator (Codex,
  GPT, Gemini, LangGraph) calls all three patterns, reading `structured_output` and bounding cost.

## Common pitfalls

1. **Forgetting `-p`** — Claude opens an interactive TUI and the subprocess hangs forever. Always
   include `-p` for non-interactive use.
2. **Reading `.result` as JSON after `--json-schema`** — read `.structured_output` (already parsed);
   fall back to treating `.result` as prose if it's absent. The model can answer in prose with
   `is_error: false`.
3. **Trusting `text` output** — model phrasing changes. Use `--output-format json` and parse.
4. **Confusing `--allowedTools` and `--tools`** — `--tools` *replaces* the built-in set;
   `--allowedTools` *gates* what fires. The most common foot-gun.
5. **Using `--continue` in stateless CI** — depends on cwd + most-recent-session heuristic. Use
   `--session-id` + `--resume`.
6. **Skipping `--max-budget-usd` / `--max-turns`** — a confused Claude in a tool loop burns dollars.
7. **Reading `result` without checking `is_error`** — error runs still produce a `result` (the error
   message) and still exit 0.
8. **`stream-json` without `--verbose` in `-p`** — you won't get the full turn-by-turn stream.
9. **Piping >10 MB to stdin** — capped since 2.1.128; write to a file and reference the path.
10. **Assuming `--bare` disables tools** — it doesn't; add `--tools ""`.
11. **Passing secrets in argv** — argv is visible in `ps`. Use env vars or stdin.

## Further reading

- `references/output-formats.md` — full schema details for `text`, `json`, `stream-json`; the
  `structured_output` parse pattern; and stream event types.
- `references/safety.md` — when each "dangerous" flag is actually acceptable, and sandbox patterns.
- `references/flag-cheatsheet.md` — alphabetical reference of every flag this skill mentions.
- `references/background-agents.md` — dispatching and polling background/parallel Claude sessions.
