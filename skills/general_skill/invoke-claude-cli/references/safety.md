# Safety: dangerous flag combinations and sandbox patterns

Read this whenever you are about to grant Claude any tool capability beyond pure Q&A — especially when designing automation that will run unattended.

## The threat model

`claude` running in a subprocess can — if you let it — do anything the calling user can do. That includes:

- Modifying or deleting files anywhere in the cwd (and any `--add-dir` paths)
- Running arbitrary Bash commands
- Making network requests via WebFetch / WebSearch
- Reading credentials from the environment, keychain, or files
- Pushing to git remotes the user is authenticated for
- Spending money on API calls

In Xiaohu's rollout, `--permission-mode bypassPermissions` is deliberately used for all headless subprocess calls so Claude CLI never stalls on internal permission UI. That moves the safety boundary to the **parent agent**: approved plan, explicit cwd/worktree/sandbox, budget, timeout, `--effort max`, logs, and user feedback handling.

## The dangerous flags

### `--dangerously-skip-permissions`

Bypasses every permission check. Claude can use any tool without being prompted or denied.

**Acceptable when, and only when:**
- Running inside a sandbox (Docker container, ephemeral VM, fresh worktree) with no network egress to anything sensitive
- Filesystem is disposable
- No credentials are mounted (no `.aws/`, `.ssh/`, `GITHUB_TOKEN`, etc.)
- Output is reviewed before being applied to a real system

**Never use it:**
- On a developer workstation with real credentials
- With cwd inside a repo containing uncommitted work
- Against any path containing `~/`, `/etc`, `/Users/<you>`, or production data
- In any code path that could be triggered by user input (prompt-injection territory)

### `--allow-dangerously-skip-permissions`

Enables `--dangerously-skip-permissions` as an *option* for the session (not on by default). Same threat model.

### `--permission-mode bypassPermissions`

Functionally equivalent blast radius to `--dangerously-skip-permissions`, but it is the default for Xiaohu's headless agent rollout to avoid approval deadlocks.

**Required guardrails:**
- Parent agent approves the plan before invoking Claude.
- Use an explicit intended `cwd`; for risky/untrusted work use a disposable git worktree, container, or VM.
- Always set `--output-format json`, `--effort max`, a timeout, and `--max-budget-usd`.
- Use `--tools ""` for pure critique; add execution tools only when needed.
- Never combine with broad `--add-dir /`, `$HOME`, production data, or uncontrolled user-provided shell objectives.
- If Claude returns `status="needs_feedback"`, ask the user and resume; do not guess.

### `--system-prompt "..."` (replacing, not appending)

The default system prompt contains Claude Code's tool conventions and safety scaffolding. Replacing it removes those. Claude may produce malformed tool calls, ignore the file-edit conventions, or behave in unexpected ways.

**Prefer `--append-system-prompt`** for nearly all agent use cases. Only use `--system-prompt` when you have your own complete prompt and are deliberately repurposing the CLI as a generic Anthropic client.

### `--disallowedTools` without `--allowedTools`

Denylists fail open: any tool Claude Code adds in a future version is auto-allowed. Under the bypass rollout, prefer explicit `--tools` availability plus cwd/sandbox boundaries instead.

### `--add-dir /` or `--add-dir $HOME`

Extends tool access to broad parts of the filesystem. Acceptable for narrow, named directories. Pathological at filesystem roots.

### Missing `--max-budget-usd`

A Claude that's stuck in a tool loop (e.g. repeatedly retrying a failing Bash command, or recursively reading a huge directory) will keep burning API calls. For any unattended invocation, set a budget. Under Xiaohu's rollout policy, delegated review/execution work caps at `--max-budget-usd 20` (Opus/Sonnet, meaningful tool surface), pure haiku critiques cap at `--max-budget-usd 0.05`–`0.10`. Pick the tier that matches the work, not a one-size cap; do not bump toy critique baselines toward 20.

### Missing subprocess timeout

Independent of `--max-budget-usd`. Always pass `timeout=` to `subprocess.run` (or equivalent). Suggest 600s for execution tasks, 120s for plan critique.

## Sandbox patterns

If you legitimately need broad capabilities, isolate them. Three common approaches:

### 1. Docker / OCI container

```bash
docker run --rm \
  -v "$(mktemp -d)":/workspace \
  -w /workspace \
  -e ANTHROPIC_API_KEY \
  --network=none \
  claude-runner:latest \
  claude -p --dangerously-skip-permissions \
         --bare --no-session-persistence \
         --max-budget-usd 1.00 \
         "$PROMPT"
```

Key properties:
- `--network=none` blocks all egress (WebFetch fails, exfiltration impossible)
- `tmpfs` or scratch volume — nothing persists after exit
- `--bare` strips all host integrations
- Only `ANTHROPIC_API_KEY` is mounted; no other credentials

### 2. Git worktree

For automation that needs to modify a real repo but you want to review before merging:

```bash
git worktree add /tmp/claude-work HEAD
cd /tmp/claude-work
claude -p --permission-mode bypassPermissions \
         --effort max \
         --tools "Edit" "Read" "Write" "Grep" "Glob" "Bash" \
         --output-format json \
         --max-budget-usd 1.00 \
         "$PROMPT"
# Review the diff, then merge or discard the worktree
```

Claude can edit files freely inside the worktree without touching the main checkout. The host repo is untouched until you choose to merge.

`claude` also has a built-in `--worktree` / `-w` flag that does this for you in an interactive session.

### 3. Restricted shell user

For server-side automation, run `claude` as an OS user that owns nothing important and has no write access outside `/tmp/claude-work/`. Then even a fully-unleashed `--dangerously-skip-permissions` is bounded by Unix permissions.

## The safe defaults

If you're not sure, start from this baseline and add capability deliberately:

```bash
claude -p \
  --permission-mode bypassPermissions \
  --effort max \
  --no-session-persistence \
  --output-format json \
  --tools "" \
  --max-budget-usd 0.10 \
  --model haiku
```

Add `--bare` only when the runner authenticates with `ANTHROPIC_API_KEY` or an `apiKeyHelper` supplied through `--settings`. Desktop Claude Max / claude.ai logins rely on OAuth/keychain state; `--bare` disables that and returns `is_error: true` / `Not logged in` even though the process exits 0.

If you omit `--bare`, Claude Code still sees dynamic cwd/env/git context. For pasted-text critique, run from an empty temp directory so repo state does not bias the answer.

This invocation:
- Uses bypass mode so it cannot stall on permission UI
- Uses highest reasoning effort (`--effort max`) by default
- Has no tool access (pure Q&A)
- Doesn't save sessions
- Uses cheapest model
- Caps spend at 10 cents
- Has zero tool side effects on the host

It's the right starting point for "I want Claude to review this text." For execution, add a deliberate `--tools` set and run only after parent-agent approval in an intended cwd/worktree/sandbox.

## Authentication in `--bare` mode

`--bare` disables keychain and OAuth token reads. Authentication must come from one of:

- `ANTHROPIC_API_KEY` environment variable (direct API key)
- `apiKeyHelper` configured via `--settings` (script that prints an API key)
- 3rd-party providers (Bedrock, Vertex, Foundry) using their own credentials

For agent runners in CI/containers, set `ANTHROPIC_API_KEY` explicitly. Don't rely on the host user's interactive login. For local OpenClaw agents using Xiaohu's Claude Max / claude.ai login, omit `--bare` unless an API key/helper has been configured for that agent.

## Audit logging

For any production agent:

1. Log the full command line (with prompt redacted if sensitive).
2. Log `session_id`, `total_cost_usd`, `num_turns`, `permission_denials`, `is_error` from the response envelope.
3. If `permission_denials` is non-empty, that's a signal Claude tried something you didn't expect — review the prompt and tool allowlist.
4. Log structured `status`; if `needs_feedback`, log the questions and `session_id` before asking the user.
5. Stream `stream-json` events to a log file if you need full traceability of tool calls.
