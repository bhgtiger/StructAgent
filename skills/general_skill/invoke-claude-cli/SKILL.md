---
name: invoke-claude-cli
description: Guide for invoking Claude Code's `claude` CLI (minimum 2.1.158; verified against 2.1.167) as a headless subprocess from another agent or orchestrator. Use before writing or modifying calls like `claude -p`, `subprocess.run(["claude", ...])`, shell pipelines, LangGraph/n8n/AutoGen nodes, or handoffs where GPT/Gemini/local LLM asks Claude to review plans, execute approved changes, continue a session, or ask for user feedback. local operator rollout policy is `--permission-mode bypassPermissions --effort max` with `--max-budget-usd 20` as the delegated review/execution cap (toy/one-shot haiku critiques stay much cheaper); parent agent handles approval, cwd/sandbox safety, structured feedback, resume, JSON/stream parsing, auth/`--bare`, effort/model/budget limits, dangerous-flag rules, and gating of newer cloud/interactive surfaces (`ultrareview`, `--remote-control`, `--brief`, worktrees, `claude agents`).
---

# Invoking the `claude` CLI from another agent

## Mental model

You — the calling agent — are the **orchestrator**. You spawn `claude` as a child process to do one of:

1. **Critique** a plan or diff you produced (read-only, fast).
2. **Execute** an approved plan inside a sandboxed tool set.
3. **Continue a session** for multi-turn refinement.

The flag set you choose determines *what tools exist, what it costs, how you parse the answer, and whether it can be resumed*. local operator rollout policy: every subprocess call includes `--permission-mode bypassPermissions` and `--effort max` so Claude CLI never stalls on internal permission UI. The **parent agent**, not Claude CLI, is responsible for approval, safety boundaries, and asking the user for feedback.

## Decision tree (read this first)

```
What do you need from Claude?
├─ Just an answer (review / plan critique / analysis)
│   → `claude -p` + `--permission-mode bypassPermissions` + `--effort max` + `--output-format json`
│   → `--tools ""` when the answer only needs pasted input
│   → Parse `.result` from JSON (or `.structured_output` when using `--json-schema`)
│
├─ Claude must touch files / run commands (execute a plan)
│   → `claude -p` + `--permission-mode bypassPermissions` + `--effort max`
│   → `--tools "Edit" "Read" "Write" "Grep" "Glob" "Bash"`
│   → Run only in an approved cwd/worktree/sandbox; Bash is arbitrary under bypass
│   → `--output-format json` + feedback schema so you can detect `needs_feedback`
│
└─ Multi-turn refinement (you'll iterate)
    → First call: `--session-id <uuid>` + `--permission-mode bypassPermissions` + `--effort max` + `--output-format json`
    → Subsequent calls: `--resume <same-uuid>` (avoid `--continue` in agents)
    → Keep the same cwd/tool set across turns
```

Stay off these from `-p` orchestration: `--worktree`, `--tmux`, `--remote-control`, `--ide`, `--chrome`, `--brief`, and the `ultrareview` subcommand. They are interactive or cloud surfaces; see "Newer CLI workflows" below.

## Minimum viable invocation

```bash
echo "Review this plan: rewrite auth in Go" | claude -p --permission-mode bypassPermissions --effort max --output-format json
```

That's it. `-p` (a.k.a. `--print`) makes Claude run non-interactively, read the prompt from argv or stdin, print one response, and exit. Without `-p`, `claude` opens an interactive TUI and an agent subprocess will hang. Without `--permission-mode bypassPermissions`, a tool-using headless run can stall or auto-deny when Claude would normally ask for permission. Without `--effort max`, calls may run at lower reasoning depth than the operator wants for delegated work.

### Non-interactive trust & settings caveat (2.1.167)

`-p` and any non-TTY stdout mode skip Claude Code's workspace-trust dialog. For headless orchestration, the trust dialog is **not** a backstop: only run `claude` in a cwd you already trust, or in a disposable worktree/container/VM.

Also, in `-p` mode, settings files that fail validation are silently ignored — no interactive error dialog appears. That includes `--settings` and `--setting-sources`. Do **not** rely on a settings file as your only guardrail for tools, budget, permission mode, or auth. Keep the critical guardrails on the invocation itself: explicit cwd/sandbox, `--tools`, `--max-budget-usd`, subprocess timeout, and parent-agent approval.

The prompt can be passed three ways — pick whichever your host language makes cleanest:

| Method | Example | When to use |
|---|---|---|
| Positional arg | `claude -p "your prompt"` | Short prompts. Watch shell escaping. |
| stdin | `echo "..." \| claude -p` | Multi-line, file contents, diffs. **Preferred for agents.** |
| Both | `cat plan.md \| claude -p "Review this plan"` | Argv = instruction, stdin = data. Argv text is appended to stdin. |

## Output formats

`--output-format` is only honored with `-p`. Options:

- **`text`** (default) — plain prose. Fine for human eyes, fragile for parsing.
- **`json`** — one JSON object on a single line. **Use this for all programmatic calls.**
- **`stream-json`** — newline-delimited JSON events as Claude works. Use only when you need progress updates or token-by-token streaming.

Leave `--prompt-suggestions` off for orchestrated calls. If enabled in print/SDK mode, Claude emits an extra `prompt_suggestion` message after each turn; streaming/SDK consumers must ignore that event and wait for the final `result` envelope.

### The `json` envelope

A `--output-format json` response looks like this (real shape, captured from `claude` 2.1.x):

```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "result": "…the actual response text…",
  "structured_output": null,
  "session_id": "3af9b65c-4b56-4eb2-822e-4cb9739d3473",
  "duration_ms": 14233,
  "duration_api_ms": 12100,
  "num_turns": 3,
  "stop_reason": "end_turn",
  "total_cost_usd": 0.0241,
  "usage": { "input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, ... },
  "permission_denials": [],
  "terminal_reason": "completed",
  "uuid": "..."
}
```

Fields the calling agent cares about:

| Field | Why you read it |
|---|---|
| `result` | The actual answer text for ordinary JSON output; may be empty when `--json-schema` is used. |
| `structured_output` | Parsed schema-validated answer on current Claude Code when `--json-schema` is used. |
| `is_error` | `true` if anything went wrong (auth, budget, refusal). **Always check this before using output fields.** |
| `session_id` | Save this if you might want to `--resume` later. |
| `total_cost_usd` | For budget accounting in your orchestrator. |
| `num_turns` | How many internal turns Claude took (high = Claude struggled). |
| `permission_denials` | Should usually be empty under `bypassPermissions`; non-empty means a runtime/flag mismatch worth auditing. |
| `stop_reason` | `end_turn` (normal), `max_tokens`, `tool_use`, etc. |

### Structured output with `--json-schema`

If you want Claude's *answer itself* (not the envelope) to be structured, pass a JSON Schema:

```bash
claude -p \
  --output-format json \
  --json-schema '{"type":"object","properties":{"verdict":{"type":"string","enum":["approve","reject","revise"]},"reasons":{"type":"array","items":{"type":"string"}}},"required":["verdict","reasons"]}' \
  "Review this plan and return your verdict."
```

Current Claude Code returns schema-validated answers in `structured_output` and leaves `result` empty or textual. Older builds returned a JSON string in `result`. Parse defensively:

```python
answer = envelope.get("structured_output")
if answer is None:
    answer = json.loads(envelope["result"])
```

Schema validation is enforced by the CLI — non-conforming output is treated as an error.

This is the single most useful flag for agent-to-agent handoffs: it eliminates parsing fragility.

## Session lifecycle

Sessions persist to disk by default and can be resumed.

| Flag | Effect |
|---|---|
| (none) | One-shot. New session each call. Session is still saved to disk under `~/.claude/projects/<cwd-slug>/` unless `--no-session-persistence`. |
| `--session-id <uuid>` | Set a known session ID up-front so you can resume by ID without scraping the response. Must be a valid UUID (generate with `uuidgen`). **Use this in agents — don't rely on parsing `session_id` from the response.** |
| `-c, --continue` | Resume the most recent session in the current working directory. Convenient interactively, fragile for agents (depends on cwd state). |
| `-r, --resume <uuid>` | Resume by session ID. **Preferred for agents.** |
| `--fork-session` | When resuming, branch off with a new ID instead of mutating the original. Lets you explore alternatives without losing the trunk. |
| `--no-session-persistence` | Ephemeral; nothing written to disk. Only with `-p`. Use for stateless one-shots in CI. |

Pattern for multi-turn agents:

```bash
SESSION=$(uuidgen | tr 'A-Z' 'a-z')   # generate up-front
claude -p --session-id "$SESSION" --permission-mode bypassPermissions --effort max --output-format json "First message"  > turn1.json
claude -p --resume "$SESSION"    --permission-mode bypassPermissions --effort max --output-format json "Follow-up"   > turn2.json
```

## Feedback handling contract

Headless Claude cannot open an interactive permission/clarification UI for the parent agent. Every execution or multi-turn prompt should include this contract:

> If you need human feedback, credentials, external approval, or a scope decision, do not continue or guess. Return `status="needs_feedback"` with concise `questions`, preserve the `session_id`, and stop.

Use a JSON schema for execution-style calls:

```json
{
  "type": "object",
  "properties": {
    "status": {"enum": ["completed", "needs_feedback", "blocked"]},
    "summary": {"type": "string"},
    "questions": {"type": "array", "items": {"type": "string"}},
    "changed_files": {"type": "array", "items": {"type": "string"}},
    "verification": {"type": "array", "items": {"type": "string"}},
    "next_steps": {"type": "array", "items": {"type": "string"}}
  },
  "required": ["status", "summary"],
  "additionalProperties": false
}
```

Parent-agent behavior:

1. Parse the envelope and check `is_error` first.
2. Parse `structured_output` (or `.result` fallback on old CLI builds).
3. If `status == "needs_feedback"`, ask the user the listed questions and store `session_id`.
4. Resume with `claude -p --resume <session_id> --permission-mode bypassPermissions --effort max ...` after the user answers.
5. If `status == "blocked"`, report the blocker and do not retry blindly.

## Tool gating

Claude has built-in tools (Read, Edit, Write, Bash, Grep, Glob, WebFetch, etc.). In this rollout, `bypassPermissions` is always on, so Claude CLI's permission prompts are not a safety boundary. Constrain by choosing a deliberate `--tools` set, running from an approved cwd/worktree/sandbox, and making the parent agent review/approve the plan before execution.

### Three flags, three meanings

- **`--tools ""`** — disable all tools. Use for pure critique/analysis of pasted input.
- **`--tools "default"`** — expose the default built-in tool set. Avoid in orchestrators; prefer explicit tools.
- **`--tools "Edit" "Read" "Write" "Grep" "Glob" "Bash"`** — explicit tool availability for execution. With `bypassPermissions`, Bash is still arbitrary; this is not a command allowlist.
- **`--allowedTools ...` / `--allowed-tools ...`** — permission allowlist for non-bypass modes. Do not rely on it as the safety boundary in this rollout; use `--tools` + cwd/sandbox + parent-agent approval.
- **`--disallowedTools ...` / `--disallowed-tools ...`** — denylist. Avoid for agents; it fails open on future tools.

### Bash sub-command syntax

`Bash(git status:*)` style command allowlists are useful with `--allowedTools` in non-bypass modes. In local operator's bypass rollout, treat them as non-authoritative; use OS/container/worktree boundaries if Bash is available.

If you do use `--allowedTools` for a non-bypass experiment, quote each pattern or pass them as an array:

```bash
ALLOWED_TOOLS=("Edit" "Read" "Bash(git status:*)" "Bash(pytest:*)")
claude -p --allowedTools "${ALLOWED_TOOLS[@]}" ...
```

### Read-only critique (no tools fire)

If you only need an answer about pasted text — like reviewing a diff — pass `--tools ""` to disable all tools. Faster, cheaper, no risk of file writes.

```bash
git diff main...HEAD | claude -p --tools "" --permission-mode bypassPermissions --effort max --output-format json \
  "Review this diff. List bugs, security issues, and missing tests."
```

## Permission modes

`--permission-mode` controls what happens when Claude wants to use a tool. For local operator's agents, use `--permission-mode bypassPermissions` and `--effort max` on every subprocess call to avoid hidden prompt/approval deadlocks. The parent agent must decide whether the plan is approved before calling Claude.

| Mode | Behavior | Use case |
|---|---|---|
| `default` | Prompts user for risky tools. **In `-p` mode prompts auto-deny** — Claude can't ask. | Interactive only. |
| `plan` | Read-only. Claude can read files and analyze but cannot edit or run commands. | Plan generation, exploration. **Safest mode for "tell me what you'd do".** |
| `acceptEdits` | Auto-approve file edits (Edit/Write). Other tools still prompt. | Trusted, scoped execution. |
| `dontAsk` | Approve any tool on the allowlist without prompting. Denies anything else. | Headless agent execution with a tight `--allowedTools`. |
| `bypassPermissions` | Approve CLI tool use without prompting. Same blast radius as `--dangerously-skip-permissions`. | **Default for this rollout**, but only after parent-agent approval and in an intended cwd/worktree/sandbox. |
| `auto` | Routes via the built-in auto-mode classifier. | Mostly internal; don't rely on it for agents. |

The intended pairing for local operator's agent rollout: **`--permission-mode bypassPermissions --effort max --tools "..."`**. This gives headless behavior; the auditable safety boundary is the parent agent's approved plan, cwd/worktree/sandbox, timeout, budget, and logs.

## System prompt injection

`--append-system-prompt "..."` adds your instruction *after* Claude Code's default system prompt. Use this to tell Claude about its role in your orchestration ("You are being called by an external planning agent. Return only JSON matching the schema."). 99% of the time, prefer this over `--system-prompt`.

`--system-prompt "..."` **replaces** the default system prompt entirely. Claude loses awareness of its tools, conventions, and safety training context. Avoid unless you really know what you're doing.

## Model and cost controls

| Flag | What it does |
|---|---|
| `--model haiku` / `--model sonnet` / `--model opus` | Pick a model family by alias; the alias resolves to the latest model in that family (`opus` → Claude Opus 4.8 today). |
| `--model claude-sonnet-4-6` | Pick by exact model ID. |
| `--fallback-model haiku` | If the primary model is overloaded, fall back. **Only works with `-p`.** Accepts one model or a comma-separated list tried in order; the CLI retries the primary at the start of each user turn. Use a different model than `--model` — same-model fallback is a no-op. |
| `--max-budget-usd <amount>` | Hard cap on spend. Run aborts if exceeded. Only with `-p`. Required on any unattended automation. local operator policy: `--max-budget-usd 20` for delegated review/execution; `~0.05`–`0.10` for toy haiku critiques. |
| `--effort max` | Highest reasoning effort (CLI choices: `low`, `medium`, `high`, `xhigh`, `max`). **Default for local operator agents.** Lower only if local operator explicitly asks. |

> **Pass the `opus` alias, not `opus4.8`.** `--model opus` now resolves to Claude Opus 4.8 (reported as `claude-opus-4-8` in the run's model usage); the literal `--model opus4.8` is **rejected** by the CLI. Prefer the bare alias `opus` — it auto-tracks the latest Opus — and pin the full ID `claude-opus-4-8` only when you need an exact build. Same alias rule for `sonnet`/`haiku`. (`claude --help`'s own `--model` example is `claude-opus-4-8`.)

For all local operator agent calls, include `--effort max` by default. Two budget tiers apply:

- **Delegated review / execution (local operator policy default):** `--max-budget-usd 20` on Opus or Sonnet for any meaningful review or execution dispatched on local operator's behalf — e.g. `/ultrareview`-style multi-file critiques, headless plan execution, or anything the orchestrator can't redo cheaply. The cap is sized so a single high-effort Opus pass on a real diff can finish; the orchestrator still enforces approval, cwd/sandbox, timeout, and post-run accounting, so a runaway tool loop trips before the wallet does. Note the wallet/extra-usage limit on local operator's account may bite earlier than `$20` per call — read `total_cost_usd` after each run and back off if you see usage-limit errors (see "Usage-limit and partial-success handling" below).
- **Toy / high-volume one-shots:** Pure pasted-text critique with no tools and `--model haiku` can stay at `--max-budget-usd 0.05`–`0.10` per call. Do not bump these toward `20` — wider caps on cheap loops just mean a wider blast radius if Claude misbehaves.

Omit `--fallback-model` when the primary is already `haiku`; use `--fallback-model haiku` or an ordered comma list only for primary `sonnet`/`opus`. Escalate to `sonnet`/`opus` for execution tasks where reasoning matters.

## Clean, hermetic runs: `--bare`

`--bare` strips:

- Hook execution
- LSP integration
- Plugin sync
- Attribution
- Auto-memory loading
- Background prefetches
- Keychain reads (so you must use `ANTHROPIC_API_KEY` or `apiKeyHelper` via `--settings`)
- `CLAUDE.md` auto-discovery

It also sets `CLAUDE_CODE_SIMPLE=1`. Use it when you want a reproducible, cache-friendly call with zero side effects from the host environment. Skills still resolve via `/skill-name`, but you must explicitly pass context via `--system-prompt[-file]`, `--append-system-prompt[-file]`, `--add-dir`, `--mcp-config`, `--settings`, `--agents`, `--plugin-dir`.

**Auth warning:** `--bare` disables OAuth/keychain reads. If the host is logged in with Claude Max / claude.ai instead of `ANTHROPIC_API_KEY` or an `apiKeyHelper` passed via `--settings`, `claude -p --bare ...` exits 0 with `is_error: true` and `result: "Not logged in"`. Third-party providers (Bedrock, Vertex, Foundry) use their own credentials. For local OpenClaw agents on local operator's Mac, default to non-bare calls unless an API key/helper is explicitly configured. Because invalid settings are silently ignored under `-p`, a malformed `--settings` apiKeyHelper file usually surfaces as `is_error:true` / `Not logged in`, not as a settings-validation error.

For CI and for non-Claude orchestrators driving `claude` with API-key auth, `--bare` is the right baseline. For desktop agents using subscription login, prefer `--no-session-persistence` plus tight tools/budget without `--bare`.

Non-bare runs still receive Claude Code's dynamic cwd/env/git context. For pure pasted-text critique that should not be influenced by the caller repo, run `claude` from an empty temp directory (or set `cwd` deliberately) even when tools are disabled.

## Working directory and scope

`claude` operates in the current working directory by default. Tools can only touch files inside that tree.

- `--add-dir /path/to/other /path/to/another` — extend the tool-accessible roots.
- `cd /target/repo && claude -p ...` — preferred for orchestrators; explicit and easy to audit.

If your agent is calling `claude` from one repo to operate on another, **always set cwd**, don't rely on `--add-dir` as the only mechanism.

Remember: `-p` skips the workspace-trust dialog. Treat cwd selection as an explicit security decision, not an interactive prompt Claude will handle later.

## MCP and doctor caveats

`claude doctor` is not a harmless read-only probe in untrusted repos: in current Claude Code it skips the workspace-trust dialog and spawns stdio servers from `.mcp.json` during health checks. Those servers are arbitrary local processes. Do not run `claude doctor` or MCP health checks in untrusted/secret-bearing repositories.

For `claude mcp list` / `claude mcp get`, unapproved project-scoped `.mcp.json` servers are shown as pending and are not connected; approved servers may be health-checked. For hermetic child runs, pass explicit `--mcp-config` plus `--strict-mcp-config` so host/user/project MCP config is ignored.

## Exit codes and error handling

`claude -p` exits:
- **0** — ran to completion (note: `is_error: true` in JSON still exits 0; **always check the JSON envelope**, not just exit code).
- **non-zero** — process-level failure (bad flags, OOM, signal). Treat as catastrophic.

The agent contract:

```python
result = subprocess.run([...], capture_output=True, text=True, timeout=600)
if result.returncode != 0:
    raise RuntimeError(f"claude crashed: {result.stderr}")
envelope = json.loads(result.stdout)
if envelope["is_error"]:
    raise RuntimeError(f"claude reported error: {envelope['result']}")
answer = envelope["result"]
```

**Always set a `timeout`.** A confused Claude can churn for tens of minutes if `--max-budget-usd` is absent.

### Usage-limit and partial-success handling

Claude CLI usage-limit behavior can be non-obvious in orchestration:

- A `claude -p` run may successfully write the requested files/artifacts and then emit a usage-limit error such as “You're out of extra usage” during shutdown. Before classifying the task as failed or retrying, inspect and verify the expected artifacts. If they are complete, preserve them and report the run as a partial/late-limit success.
- Repeated “You're out of extra usage · resets <time>” responses can persist until the reset time. Do not churn retries. Preserve the prompt, cwd/job folder, logs, and session metadata, then retry only after the indicated reset window.

## Safety: the dangerous-flag matrix

Some flag combinations expand the blast radius substantially. Use this table to reason about every call:

| Combination | Risk | Acceptable when |
|---|---|---|
| `--dangerously-skip-permissions` | Claude can run any tool with no checks — `rm -rf`, `git push --force`, exfiltrate via WebFetch. | Inside a Docker/VM sandbox with no network, no credentials, and a disposable filesystem. **Never on a developer workstation.** |
| `--allow-dangerously-skip-permissions` | Enables the above as an opt-in flag (not on by default). | Same as above. |
| `--permission-mode bypassPermissions` | Equivalent blast radius to `--dangerously-skip-permissions`. | Default for local operator agents, but only after parent-agent approval and in intended cwd/worktree/sandbox with budget + timeout + `--effort max`. |
| `--system-prompt "..."` | Strips default safety scaffolding. | Custom agents in trusted environments with you owning the full prompt. |
| `--disallowedTools` alone | Future tool additions are auto-allowed. | Avoid. In this rollout prefer explicit `--tools` availability plus parent-agent approval. |
| `--add-dir /` or large parent dirs | Expands tool-accessible filesystem. | Only when truly needed and the directory is non-sensitive. |
| No `--max-budget-usd` in unattended automation | Runaway cost. | Manual / interactive runs. |
| No timeout on subprocess call | Process can hang. | Never acceptable. Always set one. |

**Rule of thumb (two baselines):**

- *Toy critique baseline* (cheap one-shot, pasted text): `claude -p --permission-mode bypassPermissions --effort max --output-format json --no-session-persistence --tools "" --model haiku --max-budget-usd 0.10`.
- *Delegated review / execution baseline* (local operator policy): swap to `--model opus` (or `sonnet`), bump to `--max-budget-usd 20`, and widen `--tools` only after the parent agent has approved the plan and cwd/worktree/sandbox.

Add `--bare` only when API-key/helper auth is configured. Both baselines still require a subprocess timeout and structured-feedback contract.

## Worked examples

The three patterns the orchestrating agent will most commonly use are bundled as runnable scripts in `scripts/`. Read them when you're about to implement a similar handoff:

- **`scripts/01-plan-review.sh`** — Agent passes a plan/diff, gets a structured critique. Read-only, cheap.
- **`scripts/02-execute-plan.sh`** — Agent passes an approved plan for bypass-mode execution with structured feedback handling.
- **`scripts/03-multi-turn.sh`** — Agent runs an iterative refinement loop with `--session-id` / `--resume` and `needs_feedback` status handling.

A Python wrapper showing how a non-Claude agent (e.g. GPT-based orchestrator) would call these is at `scripts/claude_client.py`.

## Newer CLI workflows (minimum 2.1.158; verified on 2.1.167)

The flags and subcommands below appear in `claude --help` on 2.1.167. They mostly target interactive / cloud / plugin surfaces; treat each as **opt-in for orchestrators** and prefer the OpenClaw equivalents where available. Always re-check with `claude --version` and `claude --help` before relying on a flag — the surface drifts release-to-release.

### Versioning (`claude update|upgrade`, `claude install`)

- `claude update` / `claude upgrade` checks for updates and installs when available.
- `claude install <stable|latest|version>` installs a native build target.
- Orchestrators should verify `claude --version` against a known-good build at startup and avoid auto-updating mid-run. If the CLI is upgraded, re-capture `claude --help` and re-audit this skill before relying on new flags.

### Worktrees and tmux (`--worktree`, `--tmux`)

- `claude -w/--worktree [name]` creates a fresh git worktree for the session; `--tmux` (or `--tmux=classic`) attaches it to a tmux/iTerm2 pane. Both are designed for **interactive** humans branching off without polluting the main checkout.
- For orchestrators, prefer OpenClaw `sessions_spawn` / ACP to launch an isolated child Claude. Reasons: parent already controls cwd, budget, JSON parsing, resume/fork, and audit trail; `--worktree` would add a tmux/UI surface and a worktree the orchestrator must clean up.
- Acceptable orchestrator use: a one-off human-in-the-loop spike where local operator explicitly wants a disposable branch. Even then, pair with explicit `cd` to the parent repo and clean up the worktree on exit.
- Do **not** combine `--worktree`/`--tmux` with `-p`; they imply an interactive session.

### Background / custom agents (`claude agents`, `--agent`, `--agents`)

- `claude agents` opens the background-agent dashboard; `claude agents --json` lists live background sessions for scripting. Useful for inspecting what other Claude sessions are running on the host before spawning more.
- `--agent <name>` selects a single named agent for the current session; `--agents '{"reviewer": {...}}'` injects custom agent definitions inline. Either can be combined with `-p` for headless calls and is handy when you want a tightly-scoped persona (e.g. "reviewer", "test-writer") without writing a full `--append-system-prompt`.
- Keep these subordinate to OpenClaw orchestration: the parent agent owns plan approval, cwd/sandbox, budget, and structured feedback. Custom agents are a prompt/role convenience, not a safety boundary — they still run under whatever `--permission-mode` and `--tools` you pass.

### Plugin vs skill terminology

- Claude Code skills are invoked as slash commands like `/skill-name`. In `--bare` mode, skills still resolve, but auto-memory and `CLAUDE.md` discovery do not.
- `--disable-slash-commands` disables **all skills** despite the name. Use it in hermetic child runs if you want to prevent accidental skill activation.
- `claude plugin` manages plugins; `claude plugin init|new <name>` scaffolds under `~/.claude/skills/<name>/` and auto-loads as `<name>@skills-dir` next session. Plugins and skills share this tree, so be precise about which surface you mean.

### `ultrareview` (cloud-hosted multi-agent review)

- `claude ultrareview [target]` runs a **cloud-hosted** multi-agent review of the current branch, a PR number, or a base branch and prints findings. `--json` dumps the raw bugs payload; `--timeout <minutes>` caps the wait (default 30).
- Safety/approval: this ships branch/PR code to Anthropic's cloud review pipeline. Treat it like any other external code-disclosure action — **never invoke it from an orchestrator without explicit user approval**, and never on repos containing secrets, customer data, or unreleased proprietary code. Confirm scope (branch vs PR number) before running.
- It is the user's billable action. The orchestrator should *describe* it and let the user run it, not silently spawn it. If the user explicitly asks the orchestrator to run it, log the target, capture `--json` output, and surface findings as structured results.

### `--remote-control` (interactive only)

- `--remote-control [name]` starts an interactive session that accepts remote control commands. It is **not** for `-p` / headless orchestrator calls — there is no JSON envelope to parse, and the session expects an external controller. Skip it for subprocess automation.

### `--brief` and SendUserMessage (child-to-human channel)

- `--brief` enables the `SendUserMessage` tool, letting the child Claude post messages directly to the human. In an OpenClaw rollout, the **parent orchestrator is the human's interface** — a child that talks to the human directly bypasses approval, logging, and budget UX.
- Default: omit `--brief`. Require the child to use the structured-feedback contract (`status="needs_feedback"` + `questions`). Only pass `--brief` when local operator (or the parent agent's policy) explicitly authorizes the child to communicate directly, e.g. for a long-running execution that needs to surface progress notes.

### Other flags worth knowing

| Flag | When useful for orchestrators |
|---|---|
| `--file <id:path> ...` | Stage file resources at session start (download by ID into the cwd). Use when the parent has already uploaded artifacts the child needs; otherwise pipe via stdin or `--add-dir`. |
| `--from-pr [value]` | Resume a session linked to a PR number/URL. Convenient for "continue the review we did on PR #123" handoffs; pair with `--resume` semantics. Verify PR access before invoking. |
| `-n, --name <name>` | Label a session for `/resume` picker and terminal title; useful for audit trails in spawned runs. |
| `--plugin-dir <path>` / `--plugin-url <url>` | Load a plugin from a directory/`.zip` or a URL for this session only (both repeatable). Useful for sandboxed experiments without mutating user-level plugin config. `--plugin-url` fetches over the network — gate it behind explicit approval. |
| `--chrome` / `--no-chrome` | Toggles the Chrome integration. Headless orchestrators should leave it off (default). |
| `--ide` | Auto-connects to a detected IDE on startup. Interactive convenience; do not pass in `-p` calls. |
| `--debug [filter]` / `--debug-file <path>` | Diagnose hung, over-budget, MCP, or hook-influenced calls. `--mcp-debug` is deprecated; use `--debug`. |
| `--include-hook-events` | Emits hook lifecycle events in the stream (only with `--output-format=stream-json`). Useful when debugging hook-driven workflows. |
| `--include-partial-messages` | Streams partial message chunks (only with `-p` + `--output-format=stream-json`). Use for token-level progress UIs; otherwise wastes bandwidth. |
| `--input-format stream-json` | Lets the parent feed events into the child in real time (only with `-p`). Pair with `--output-format=stream-json` for bidirectional streaming agents. Text input remains the default for one-shot calls. |
| `--prompt-suggestions [true|false]` | In print/SDK mode, emits a `prompt_suggestion` message after each turn. Leave off by default; ignore these events if enabled. |
| `--replay-user-messages` | Echoes user messages back on stdout for acknowledgment (requires `--input-format=stream-json` + `--output-format=stream-json`). Useful when the parent needs receipt confirmation in a streaming loop. |
| `--setting-sources <user,project,local>` | Restricts which settings layers load. Use with `--bare` or in hermetic CI runs to avoid surprises from project-local settings. |
| `--strict-mcp-config` | Use only MCP servers passed by `--mcp-config`; ignore other MCP configurations. Preferred for hermetic child runs. |
| `--exclude-dynamic-system-prompt-sections` | Moves cwd/env/git/memory blocks out of the system prompt into the first user message; improves cross-user prompt-cache reuse. Only applies with the default system prompt — silently ignored when `--system-prompt` replaces it. |
| `--betas <betas...>` | API beta headers for API-key users only; keep out of default orchestrator calls unless explicitly needed. |

### Informational subcommands

- `claude auth` manages authentication.
- `claude setup-token` creates a long-lived token for Claude subscription accounts; this can make `--bare` viable on a subscription-login Mac when paired with explicit settings/helper plumbing.
- `claude auto-mode` inspects the classifier behind `--permission-mode auto`; do not rely on `auto` as an orchestration safety boundary.
- `claude project` manages Claude Code project state.

## Common pitfalls

1. **Forgetting `-p`** — Claude opens an interactive TUI and the subprocess hangs forever. Always include `-p` (or `--print`) for non-interactive use.
2. **Quoting the prompt as one big argv** — shell escaping bites. Pipe via stdin instead.
3. **Trusting `text` output** — model phrasing changes. Use `--output-format json` and parse.
4. **Confusing `--allowedTools` and `--tools`** — under `bypassPermissions`, use `--tools` for tool availability; do not promise safety from `--allowedTools`.
5. **Using `--continue` in stateless CI** — it depends on cwd and the most-recent-session heuristic. Use `--session-id` + `--resume` instead.
6. **Skipping `--max-budget-usd`** — a confused Claude in a tool loop can burn dollars quickly.
7. **Reading `result` without checking `is_error`** — `is_error: true` runs still produce a `result` field (containing the error message). They also exit 0.
8. **Passing secrets in argv** — argv is visible in `ps`. Use env vars or stdin.
9. **Letting Claude ask vague questions** — require `status="needs_feedback"` with concrete `questions`, preserve `session_id`, ask the user, then resume.
10. **Assuming `-p` will show trust/settings errors** — it skips workspace trust, and invalid settings can be silently ignored. Run only in trusted cwd and keep guardrails on the CLI invocation.
11. **Running `claude doctor` in an untrusted repo** — it skips workspace trust and may spawn `.mcp.json` stdio servers. Treat it as code execution.
12. **Running `ultrareview` without approval** — it uploads branch/PR code to a cloud pipeline and is billable. Always confirm scope with the user before invoking; never wire it into an automatic orchestrator step.
13. **Passing `--brief` by default** — lets the child Claude talk to the human directly via `SendUserMessage`, bypassing parent orchestration. Omit unless the parent explicitly authorizes it; route everything through the structured-feedback contract instead.
14. **Using `--worktree`/`--tmux`/`--remote-control`/`--ide`/`--chrome` from `-p`** — these are interactive surfaces. Prefer OpenClaw `sessions_spawn`/ACP for isolated child sessions, and reserve worktree/tmux for explicit human-in-the-loop spikes.

## Further reading

- `references/output-formats.md` — full schema details for `text`, `json`, and `stream-json`, including the event types in stream mode.
- `references/safety.md` — extended discussion of when each "dangerous" flag is actually acceptable, and sandbox patterns.
- `references/flag-cheatsheet.md` — alphabetical reference of every flag this skill mentions, with one-line semantics.
