# Safety: dangerous flag combinations and sandbox patterns

Read this whenever you are about to grant Claude any tool capability beyond pure Q&A — especially when
designing automation that will run unattended. Verified against `claude` 2.1.207.

## The threat model

`claude` in a subprocess can — if you let it — do anything the calling user can do:

- Modify or delete files anywhere in the cwd (and any `--add-dir` paths)
- Run arbitrary Bash commands
- Make network requests via WebFetch / WebSearch
- Read credentials from the environment, keychain, or files
- Push to git remotes the user is authenticated for
- Spend money on API calls

Tool gating + permission modes exist to shrink this surface. The flags below *expand* it; treat each
as a deliberate, audited choice.

## The dangerous flags

### `--dangerously-skip-permissions`

Bypasses every permission check. Claude can use any tool without being prompted or denied. As a last
circuit breaker, `rm -rf /` and `rm -rf ~` still prompt even here — but do not rely on that.

**Acceptable when, and only when:**
- Running inside a sandbox (Docker container, ephemeral VM, fresh worktree) with no network egress to
  anything sensitive
- Filesystem is disposable
- No credentials are mounted (no `.aws/`, `.ssh/`, `GITHUB_TOKEN`, etc.)
- Output is reviewed before being applied to a real system

**Never use it:**
- On a developer workstation with real credentials
- With cwd inside a repo containing uncommitted work
- Against any path containing `~/`, `/etc`, `/Users/<you>`, or production data
- In any code path that could be triggered by user input (prompt-injection territory)

### `--allow-dangerously-skip-permissions`

Enables `--dangerously-skip-permissions` as an *option* for the session (not on by default). Same
threat model.

### `--permission-mode bypassPermissions`

Functionally equivalent to `--dangerously-skip-permissions`: skips prompts except explicit `ask`
rules; `rm -rf /` / `~` still prompt as a circuit breaker. Also skips prompts for writes to sensitive
dirs (`.git`, `.claude`, `.ssh`-adjacent config, etc.). Same rules apply — sandbox only.

### `--system-prompt` / `--system-prompt-file` (replacing, not appending)

The default system prompt carries Claude Code's tool conventions and safety scaffolding. Replacing it
removes those; Claude may emit malformed tool calls, ignore file-edit conventions, or behave
unexpectedly. **Prefer `--append-system-prompt[-file]`** for nearly all agent use cases. Only replace
when you own the full prompt and are deliberately repurposing the CLI as a generic Anthropic client.

### `--disallowedTools` without `--allowedTools`

Denylists fail open: any tool Claude Code adds in a future version is auto-allowed. If you care about
the tool surface, use `--allowedTools` (allowlist) instead.

### `--add-dir /` or `--add-dir $HOME`

Extends tool access to broad parts of the filesystem. Acceptable for narrow, named directories;
pathological at filesystem roots. Note: `--add-dir` also loads skills/subagents from the added dir's
`.claude/`, so it is more than a file-access grant.

### Missing `--max-budget-usd` / `--max-turns`

A Claude stuck in a tool loop (retrying a failing Bash command, recursively reading a huge directory)
keeps burning API calls. For any unattended invocation set **both** a budget and a turn cap:
`--max-budget-usd 0.50 --max-turns 8` is a reasonable starting point; raise based on observed usage.

### Missing subprocess timeout

Independent of the budget/turn caps. Always pass `timeout=` to `subprocess.run` (or equivalent).
Suggest 600s for execution tasks, 120s for plan critique.

## Bash permission-rule pitfalls

`--allowedTools` Bash rules are string-prefix matchers, not a shell sandbox. Know their limits:

- **Compound commands split.** `Bash(safe *)` does NOT authorize `safe && rm -rf .`; each subcommand
  (`&&`, `||`, `;`, `|`, `&`, newline) must match a rule independently. This is a *feature* — but it
  means an over-broad single rule doesn't accidentally grant a chained destructive command.
- **Process wrappers are stripped** (`timeout`, `time`, `nice`, `nohup`, `stdbuf`, bare `xargs`), so
  `Bash(npm test *)` also matches `timeout 30 npm test`. Fine, but be aware.
- **Environment runners are transparent and dangerous.** `Bash(devbox run *)`, `npx`, `docker exec`
  execute their arguments — such a rule effectively allows anything after `run`. Write specific rules
  (`Bash(devbox run npm test)`), one per inner command.
- **Argument-constraining rules are fragile.** `Bash(curl https://github.com/ *)` won't stop
  `curl -L http://bit.ly/x` (redirect), `URL=…; curl $URL`, or extra spaces. For network control,
  deny `curl`/`wget` and use `WebFetch(domain:github.com)` instead, or a PreToolUse hook.

For OS-level enforcement that survives prompt injection, use Claude Code sandboxing in addition to
permission rules — sandboxing restricts the Bash tool's filesystem/network at the OS level.

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
         --max-budget-usd 1.00 --max-turns 12 \
         "$PROMPT"
```

Key properties:
- `--network=none` blocks all egress (WebFetch fails, exfiltration impossible)
- `tmpfs` or scratch volume — nothing persists after exit
- `--bare` strips host integrations; auth is `ANTHROPIC_API_KEY` only
- Only `ANTHROPIC_API_KEY` is mounted; no other credentials

### 2. Git worktree

For automation that needs to modify a real repo but you want to review before merging:

```bash
git worktree add /tmp/claude-work HEAD
cd /tmp/claude-work
claude -p --permission-mode dontAsk \
         --allowedTools "Edit Read Bash(git status *) Bash(git diff *)" \
         --max-budget-usd 1.00 --max-turns 12 \
         "$PROMPT"
# Review the diff, then merge or discard the worktree
```

Claude edits files inside the worktree without touching the main checkout. `claude` also has a
built-in `-w`/`--worktree` flag that creates one for the session.

### 3. Restricted shell user

For server-side automation, run `claude` as an OS user that owns nothing important and has no write
access outside `/tmp/claude-work/`. Then even a fully-unleashed `--dangerously-skip-permissions` is
bounded by Unix permissions.

## The safe defaults

If you're not sure, start from this baseline and add capability deliberately:

```bash
claude -p \
  --bare \
  --no-session-persistence \
  --output-format json \
  --tools "" \
  --max-turns 2 \
  --max-budget-usd 0.10 \
  --fallback-model haiku \
  --model haiku
```

This invocation has no tool access (pure Q&A — note `--bare` alone would still leave Bash/Read/Edit
available, so `--tools ""` is what disables them), doesn't save sessions, uses the cheapest model,
caps spend and turns, and has zero side effects on the host. It's the right starting point for "I want
Claude to review this text." Add `--allowedTools` + `--permission-mode dontAsk` when you need execution.

## Authentication in `--bare` mode

`--bare` disables keychain and OAuth token reads. Authentication must come from one of:

- `ANTHROPIC_API_KEY` environment variable (direct API key)
- `apiKeyHelper` configured via `--settings` (a script that prints an API key)
- 3rd-party providers (Bedrock, Vertex, Foundry) using their own credentials

For CI/containers set `ANTHROPIC_API_KEY` explicitly (or use an `apiKeyHelper` via `--settings`).
Don't rely on the host user's interactive login inside `--bare`. Note that `claude setup-token` mints
a *subscription* OAuth token stored in the credentials store — the exact path `--bare` disables — so a
setup-token is **not** a substitute for `ANTHROPIC_API_KEY` here; it's for non-bare, keychain-based
auth.

## Audit logging

For any production agent:

1. Log the full command line (prompt redacted if sensitive).
2. Log `session_id`, `total_cost_usd`, `modelUsage`, `num_turns`, `permission_denials`, `is_error`
   from the response envelope.
3. If `permission_denials` is non-empty, Claude tried something you didn't expect — review the prompt
   and tool allowlist.
4. Stream `stream-json` events (with `--verbose`, optionally `--include-hook-events`) to a log file if
   you need full traceability of tool calls.
