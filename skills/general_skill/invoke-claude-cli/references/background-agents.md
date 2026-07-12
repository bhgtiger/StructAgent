# Background agents — dispatch and poll parallel Claude sessions

Read this when your orchestrator wants to launch Claude work and keep going — fan-out across many
tasks, or a long-running job you'll check on later — rather than blocking on a single `claude -p`.
Verified against `claude` 2.1.207; the CLI surface here is younger and moving faster than the
`-p` flags, so **confirm subcommands with `claude --help` and `claude agents --help` on your build.**

## When to use this vs. plain `claude -p`

| You want… | Use |
|---|---|
| One answer, now, and you'll wait for it | `claude -p` (blocking) — see SKILL.md |
| Several independent jobs running at once | launch each with `claude --bg "<task>" …`, then poll |
| A long job you'll check on later | `claude --bg "<task>" …` then `claude agents --json` |
| Your own concurrency/queueing across many prompts | keep using blocking `claude -p` from your own worker pool — often simpler and easier to reason about |

For most orchestrators, a pool of blocking `claude -p` subprocesses that you manage yourself is the
simplest, most portable design. Reach for background agents when you specifically want the CLI to own
session lifecycle and let you attach/inspect later.

## What exists on 2.1.207

- **`--bg`, `--background`** — start the session as a background agent and return immediately. The
  prompt is a **positional argument**, and `--bg` **conflicts with `-p`/`--print`** (the binary rejects
  the combination at parse time — `--print` never starts the session `claude agents` attaches to, so
  the job would be unattachable). Gate it with the usual session flags (`--permission-mode`,
  `--allowedTools`/`--tools`, `--model`, `--name`). Note that `--print`-only flags
  (`--max-budget-usd`, `--fallback-model`, `--no-session-persistence`) do **not** apply here.
- **`claude agents`** — the background-agent management view. With `--json` it prints active sessions
  as a JSON array and exits (no TTY required — this is the scriptable entry point). Add `--all` to
  include completed sessions.
- `claude agents` also accepts defaults applied to *dispatched* sessions:
  `--model`, `--permission-mode`, `--effort`, `--mcp-config`, `--settings`, `--agent`, `--plugin-dir`,
  `--dangerously-skip-permissions`, and `--add-dir`. Note `--add-dir` grants additional **directory**
  access to dispatched sessions — it is *not* a tool allowlist. `claude agents` exposes no per-view
  tool-allowlist default; gate tools at launch time via the top-level `--allowedTools`/`--tools`.

```bash
# Launch three independent background jobs, tightly gated.
# Note: --bg takes the prompt as a positional arg and must NOT be combined with -p.
for area in auth billing search; do
  claude --bg \
    --permission-mode dontAsk \
    --allowedTools "Read Edit Bash(pytest *)" \
    --model sonnet \
    --name "fix-$area" \
    "Fix the failing tests under tests/$area/."
done

# Poll: list active sessions as JSON your orchestrator can parse.
claude agents --json | jq '.[] | {id, name, status}'
```

> Per-run cost caps like `--max-budget-usd` are `--print`-only and are ignored by `--bg`. Bound
> background spend with tool gating, model choice, session-level `settings`, and by stopping runaway
> jobs from `claude agents`. If you need hard per-run budget/turn caps, prefer a self-managed pool of
> blocking `claude -p` workers instead.

## What is documented but NOT on 2.1.207

Current docs describe finer-grained lifecycle subcommands. They are **absent from the 2.1.207
binary** — do not script against them without checking your version first:

- `claude attach <id>` — attach to a background session in this terminal
- `claude logs <id>` — print recent output from a background session
- `claude stop <id>` / `claude respawn <id>` / `claude rm <id>` — stop / restart / remove a session
- `claude daemon status` / `claude daemon stop --any` — inspect/stop the background supervisor

Until your installed build exposes these, poll with `claude agents --json` and drive lifecycle through
that view, or use the SDK.

## Background tasks at process exit (blocking `-p`)

Relevant even without `--background`: if a `claude -p` run starts a background **Bash** task (a dev
server, a watch build), that shell is terminated ~5 seconds after Claude returns its final result and
stdin closes (behavior since v2.1.163 — before that a never-exiting process could hold the invocation
open forever). Background **subagents/workflows** are waited on because their result is part of the
output; from v2.1.182 that wait is capped at 10 minutes by default. Tune with the
`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS` env var (`0` = wait without limit).

## Prefer the Agent SDK for heavy orchestration

If you're building substantial parallel orchestration, the **Claude Agent SDK** (Python / TypeScript)
gives you the same agent loop with native session objects, tool-approval callbacks, and structured
outputs — without shelling out and parsing JSON. The CLI (`claude -p` / `--background`) is ideal for
scripts, CI, and language-agnostic hand-offs; the SDK is ideal when the orchestrator is itself a
long-lived Python/TS program. See the Agent SDK docs (`code.claude.com/docs/en/agent-sdk/overview`).
