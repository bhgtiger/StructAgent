---
name: use-codex-cli
description: >-
  Authoritative guide for driving the OpenAI Codex CLI (the `codex` binary and `codex exec`)
  as a subprocess from another agent — for repository analysis, focused implementation,
  independent code review, debugging, structured JSON extraction, and multi-turn delegation.
  Use this skill whenever you are about to run or script `codex` — codex exec, codex exec
  review, codex exec resume, or codex mcp-server — and whenever the user says "use Codex",
  "ask Codex", "get a second opinion from Codex", "have Codex review this", or "delegate
  this to Codex". Covers non-interactive invocation, the exact per-subcommand flag
  positions, the sandbox and project-trust model, JSONL and last-message and JSON-schema
  output, session resume, exit codes, and verifying Codex's work. Consult BEFORE writing the
  command because flag placement and sandbox choice change what Codex can do and whether the
  call parses. Do not invoke for trivial work the agent can do directly, and never launch the
  bare `codex` TUI from automation.
---

# Driving the OpenAI Codex CLI from another agent

## Mental model

You — the calling agent — are the **orchestrator**. You spawn `codex` as a child process to own one bounded subproblem: analyze a subsystem, implement a focused fix, review a diff, or give an independent second opinion. Then you **independently inspect** its output, its working-tree changes, and its verification evidence. A confident final message from Codex is not proof — you verify.

Two boundaries apply at once: your own tool permissions (the outer boundary) and Codex's sandbox + approval + trust settings (the inner boundary). Effective access is the intersection. Start with the least access that can finish the task.

> Baseline: this skill is verified against `codex-cli 0.144.1`. If `codex --version` differs, treat the installed `--help` as authoritative and re-probe (see `references/command-map.md`).

## Decision tree (read this first)

```
What do you need from Codex?
├─ An answer only (explain code / architecture / second opinion)
│   → codex -C <repo> -s read-only exec -        (prompt on stdin)
│   → capture with -o <file>; add --output-schema if you'll branch on fields
│
├─ An independent REVIEW of changes (uncommitted / base branch / commit)
│   → codex -C <repo> -s read-only exec review --uncommitted --json
│   → NOTE: put -C/-s in GLOBAL position; exec review rejects them after the subcommand
│
├─ Codex must EDIT files / run commands (implement, fix, repair tests)
│   → codex -C <repo> -s workspace-write exec -
│   → then inspect the diff and run the tests yourself
│
├─ CONTINUE the same investigation (multi-turn)
│   → first run: note the thread_id from JSONL; then
│   → codex -C <repo> -s <mode> exec resume <thread-id> -
│
└─ Structured data you will parse
    → codex -C <repo> -s read-only exec --output-schema schema.json -o out.json -
```

Full recipes with prompt contracts and verification steps: `references/task-recipes.md`.

## Preflight (once)

```bash
codex --version                      # confirm binary + capture baseline
codex login status                   # exit 0 = logged in; exit 1 = no auth (fix before running)
git -C "$REPO" rev-parse --show-toplevel   # codex needs a Git repo unless --skip-git-repo-check
```

Skipping the `login status` check means an unauthenticated `exec` will retry transports and only fail after a noisy delay (exit 1).

## Minimum viable invocation

```bash
printf '%s' 'Explain the authentication flow. Do not edit anything.' \
  | timeout 300 codex -C "$REPO" -s read-only exec -
```

That is the whole pattern: `exec` runs non-interactively, `-s read-only` forbids edits, the prompt arrives on **stdin** (the trailing `-`), and `timeout` guarantees the call cannot block your session forever. Without `exec`, bare `codex` opens the interactive TUI and an automation subprocess hangs.

## The five rules that keep automation safe

1. **`codex exec`, never bare `codex`.** Bare `codex` is the human TUI; it will hang an unattended flow.
2. **Flag position is per-subcommand.** A misplaced flag is a hard parse error (exit 2), not a fallback. See the composition rules below and the full matrix in `references/command-map.md`.
3. **Govern access with `-s/--sandbox`, not `-a`.** `codex exec` rejects `-a/--ask-for-approval`. Choose `read-only` (default), `workspace-write`, or — rarely, deliberately — `danger-full-access`.
4. **Wrap every call in `timeout` and own the stdin.** `exec -` reads until its stdin producer closes; a `printf | codex` pipe closes cleanly, an inherited open pipe can block.
5. **Exit 0 is not success.** A model-level failure (e.g. a write denied by a read-only sandbox) still exits 0. Verify the actual outcome (see below).

## Flag position — the top foot-gun

Some flags are **global** (before the subcommand); some are **subcommand-only** (after it). The composition rules that cover most work:

```
Direct exec:       codex [-C dir] [-s mode] [--search] exec [--json|--output-schema|-o|-i|-m] -
Automated review:  codex [-C dir] [-s mode] exec review [--uncommitted|--base B|--commit SHA] [--json|--output-schema|-o]
Automated resume:  codex [-C dir] [-s mode] exec resume <thread-id> [--json|--output-schema|-o] -
```

- **`--search`, `-a` are global-only** (before `exec`); `codex exec --search` and `codex exec -a` both fail to parse.
- **`--json`, `--output-schema`, `-o`, `--ephemeral`, and the git/config/rules bypasses live on the `exec` family only** (`exec`, `exec review`, `exec resume`) — not on the interactive `codex`/`resume` or top-level `review`.
- **`exec review` and `exec resume` reject `-s`, `-C`, `--add-dir`, `-p`** — set those in global position instead. They were verified to take effect there.
- **Top-level `codex review`** has no `--json`/`--output-schema`/`-o`/`-m`/`-s` — it is a human wrapper. For any parseable review use `codex exec review`.

The complete 6-column, parse-verified matrix is in `references/command-map.md`.

## Passing the prompt

| Method | Example | When |
|---|---|---|
| stdin (`-`) | `printf '%s' "$PROMPT" \| codex ... exec -` | **Preferred.** Multiline or generated prompts; avoids shell-escaping and injection. |
| Positional arg | `codex ... exec 'short prompt'` | Short, static, hand-written prompts. |
| Piped context + arg | `git diff \| codex ... exec 'Review this diff'` | Arg = instruction, stdin = data; Codex appends stdin as a `stdin` block. |

Do not splice untrusted or generated text into the command line. Pipe it.

## Getting the answer out

- **stderr = progress** (workdir, model, sandbox, session id, token count); **stdout = the final message** (or the JSONL event stream under `--json`). Never parse stderr for the result.
- **`-o <file>`** writes only the final agent message to a file — the most robust capture. Note: **no trailing newline.**
- **`--output-schema <file>`** constrains the final message to a JSON Schema; use it when your code branches on fields.
- **`--json`** emits JSONL events; the answer is the last `agent_message` item, a successful run ends with `turn.completed`, a failed run ends with `turn.failed`. Use it only when you also need the trace.

Details, the real event shapes, and the exit-code table are in `references/automation-and-sessions.md`.

## Verify — never trust exit 0

After any run, check in order:

1. **Process exit status** (2 = parse error, 1 = pre-model failure / auth / non-git / strict-config, 0 = process completed).
2. **If `--json`:** absence of `error` / `turn.failed` events.
3. **If `--output-schema`:** the final message is present and schema-valid.
4. **The requested postconditions:** inspect the actual `git diff`, run the tests, confirm the files/behavior. Exit 0 with a denied write is a real, observed case.

## Sessions

- **Independent second opinion →** fresh or `--ephemeral` run (no anchoring, no session file on disk).
- **Continuation →** capture the `thread_id` from the first run's JSONL, then `exec resume <thread-id>`. Explicit id beats `--last` (which is cwd-filtered and can select an unrelated session).
- See `references/automation-and-sessions.md` for resume/fork/archive.

## Common pitfalls

1. **Forgetting `exec`** — bare `codex` opens the TUI and hangs. Always `codex exec`.
2. **`-a` after `exec`** — parse error. Use `-s`; set `approval_policy` via `-c` only where it's consulted.
3. **`-s`/`-C` after `exec review`/`exec resume`** — parse error. Put them before the subcommand.
4. **Parsing stderr for the answer** — the result is on stdout (or in the `agent_message` JSONL item). stderr is progress.
5. **Assuming `-o` output ends in a newline** — it does not.
6. **Treating exit 0 as task success** — verify diffs/tests/postconditions.
7. **Splicing a generated prompt into argv** — pipe it via stdin instead.
8. **Hardcoding a model** — defer to the user's `config.toml`; enumerate with `codex debug models` if needed.
9. **Assuming a fresh Git repo will prompt for trust** — it runs; trust governs whether project `.codex`/hooks/rules load, not whether `exec` executes. A non-Git dir is the real early stop (exit 1 without `--skip-git-repo-check`).

## Worked examples

Runnable, copy-and-adapt Bash scripts in `scripts/` (each is `bash -n` clean; not a wrapper you must call):

- **`scripts/01-analyze-readonly.sh`** — read-only explanation, captured to a file.
- **`scripts/02-implement-and-verify.sh`** — workspace-write fix, then independent diff + test inspection.
- **`scripts/03-review-uncommitted.sh`** — automated `exec review` of uncommitted changes with JSONL.
- **`scripts/04-structured-extract.sh`** — `--output-schema` extraction with schema validation.
- **`scripts/05-resume-continuation.sh`** — two-turn `exec` then `exec resume` by thread id.

## Further reading (`references/`)

- **`command-map.md`** — every command (including the hidden `execpolicy`), the full parse-verified flag matrix, and capability discovery.
- **`task-recipes.md`** — route + access + session + output + prompt contract + verification per task type.
- **`prompt-contracts.md`** — reusable delegation contracts (analyze-only, diagnose-only, implement-and-verify, review, extract, continuation).
- **`automation-and-sessions.md`** — stdout/stderr, the observed JSONL contract, exit codes, output modes, stdin ownership, sessions, `--strict-config`.
- **`security-and-config.md`** — outer/inner boundaries, sandbox modes, the project-trust model, dangerous-bypass flags, config precedence, `AGENTS.md` discovery, auth, absence of a budget cap.
- **`mcp-and-advanced.md`** — `codex mcp-server` (the `codex` / `codex-reply` tools), consuming external MCP servers, and the experimental surfaces.
- **`troubleshooting.md`** — a layer-by-layer diagnostic sequence from binary to output parsing.
