# Troubleshooting: a layer-by-layer diagnostic

Work top-down. Each layer is **symptom → cause → fix**, ordered the way a `codex exec` call actually fails: the binary must exist before the command can parse, the command must parse before the repo guard runs, the guard must pass before auth, and so on. Stop at the first layer whose symptom matches. Every fact is grounded in `codex-cli 0.144.1` observations, and every command respects the parse-verified flag positions in [`command-map.md`](command-map.md).

## Contents

1. [Binary, path, version](#1-binary-path-version)
2. [Command syntax and flag placement](#2-command-syntax-and-flag-placement)
3. [Working directory and Git root](#3-working-directory-and-git-root)
4. [Authentication](#4-authentication)
5. [Config, profile, and trust conflicts](#5-config-profile-and-trust-conflicts)
6. [Sandbox, hooks, rules, and denials](#6-sandbox-hooks-rules-and-denials)
7. [Required MCP server startup](#7-required-mcp-server-startup)
8. [Session lookup and resume mismatch](#8-session-lookup-and-resume-mismatch)
9. [JSONL, schema, and output-file parsing](#9-jsonl-schema-and-output-file-parsing)
10. [Timeout, interruption, rate limit, upstream](#10-timeout-interruption-rate-limit-upstream)
11. [First resort: codex doctor](#11-first-resort-codex-doctor)
12. [Symptom to layer lookup](#12-symptom-to-layer-lookup)

## 1. Binary, path, version

- **Symptom:** `command not found`, or behavior that contradicts this skill.
- **Cause:** `codex` is not installed / not on `PATH`, or the installed version differs from the `0.144.1` baseline.
- **Fix:**
  ```bash
  command -v codex        # resolves the binary (baseline: /opt/homebrew/bin/codex)
  codex --version         # expect: codex-cli 0.144.1
  ```
  If the version differs, treat the installed `--help` as authoritative and re-probe ([`command-map.md`](command-map.md)).

## 2. Command syntax and flag placement

- **Symptom:** exit **2** with `unexpected argument` on stderr; no model call happened.
- **Cause:** a flag in the wrong position. Placement is per-subcommand and a misplaced flag is a **hard parse error, not a fallback**. Classic cases: `-a` after `exec`; `-s` / `-C` / `--add-dir` / `-p` after `exec review` or `exec resume`; `--json` / `-o` / `--output-schema` on bare `codex` or `resume`.
- **Fix:** consult the matrix in [`command-map.md`](command-map.md) and respect global-vs-subcommand position:
  ```
  Direct exec:  codex [-C dir] [-s mode] exec [--json|-o|--output-schema] -
  Review:       codex [-C dir] [-s mode] exec review [--uncommitted|--base B] [--json|-o]
  Resume:       codex [-C dir] [-s mode] exec resume <thread-id> [--json|-o] -
  ```
  A flag can parse globally yet still be rejected at runtime by the chosen command — prefer the exact command's `--help`.

## 3. Working directory and Git root

- **Symptom:** exit **1** almost immediately, before any model output; stderr mentions a repository / trusted-directory guard.
- **Cause:** the target directory is not a Git repository. `exec` enforces the Git check before execution.
- **Fix:** run inside a repo, or bypass deliberately (the bypass is an `exec`-only flag):
  ```bash
  printf '%s' "$PROMPT" | codex -C "$SCRATCH" -s read-only exec --skip-git-repo-check -
  ```
  `--skip-git-repo-check` removes a guard — use it only for a directory you control. A **fresh** Git repo does *not* stop here; it runs normally. Trust governs project config, not whether `exec` executes (layer 5).

## 4. Authentication

- **Symptom:** exit **1** after a noticeable delay; stderr shows WebSocket retries, an HTTPS fallback, then a `401`. Under `--json`, repeated `error` items end in `turn.failed`.
- **Cause:** no usable credentials. `exec` does **not** open an interactive login; it retries transports and fails.
- **Fix:** preflight before any authenticated call:
  ```bash
  codex login status      # exit 0 = logged in; exit 1 = fix auth first
  ```
  Never print or pass `~/.codex/auth.json` (mode `600`); never place a secret in argv. Supported modes: ChatGPT OAuth, API key on stdin, access token on stdin.

## 5. Config, profile, and trust conflicts

- **Symptom:** "my project config / hooks / rules aren't applying," or an override that silently does nothing.
- **Cause & fix** — three distinct cases:

  | Symptom | Cause | Fix |
  |---|---|---|
  | Project `.codex/config.toml`, hooks, rules ignored | Project is **untrusted** — Codex silently drops project-scoped config | Mark the project trusted (verified: an untrusted fixture reported the feature `false`, trusted reported `true`). "Config isn't applying" usually means untrusted. |
  | Unknown config field silently ignored, call still ran | Loose `-c` tolerates unknown keys — and may **spend a model call** anyway | Add `--strict-config` to fail an unknown field **early, exit 1**, before the model call |
  | `-c 'x=[unclosed'` didn't error | Unparseable TOML falls back to a literal string | Don't rely on malformed `-c` to fail; use `--strict-config -c 'known=badtype'` to force a real error |

  `AGENTS.md` is discovered even in an untrusted project, so its presence is **not** proof that trust or project config loaded. Precedence and trust details: [`security-and-config.md`](security-and-config.md).

## 6. Sandbox, hooks, rules, and denials

- **Symptom:** Codex reports "couldn't write / permission denied," yet the **process exited 0**; or noisy macOS denial lines during a read-only review.
- **Cause:** the sandbox denied an action the model attempted. A denied write under `-s read-only` is a *task* failure, not a *process* failure — **exit 0 does not mean success**. Under read-only, macOS Git also fails to write Xcode/cache files; those denials are expected noise.
- **Fix:**
  1. Check **postconditions, not `$?`**: inspect the actual `git diff`, run the tests, confirm the files exist.
  2. Reproduce/inspect the exact denials with the local seatbelt runner (no model call, macOS):
     ```bash
     codex sandbox --log-denials -- git status
     ```
  3. If the task legitimately needs to write, raise the sandbox to `-s workspace-write` deliberately. Benign macOS Git cache write-denials under read-only can be ignored.

  `codex sandbox` details: [`mcp-and-advanced.md`](mcp-and-advanced.md). Sandbox/approval model: [`security-and-config.md`](security-and-config.md).

## 7. Required MCP server startup

- **Symptom:** a run that depends on an external MCP tool stalls at startup or reports the tool missing.
- **Cause:** a configured external MCP server failed to launch, or none is registered (the verified `codex doctor` baseline had **no MCP servers configured**).
- **Fix:** list and inspect registrations; confirm the server command runs on its own:
  ```bash
  codex mcp list          # what's registered
  codex mcp get <name>    # one server's config
  ```
  Add a server only when the task explicitly needs it (`codex mcp add` mutates global config). MCP tool **call-time** behavior was not exercised live — verify independently. See [`mcp-and-advanced.md`](mcp-and-advanced.md).

## 8. Session lookup and resume mismatch

- **Symptom:** `exec resume` continues the wrong conversation, or loses context you expected.
- **Cause:** `--last` is **cwd-filtered** and can select an unrelated recent session.
- **Fix:** resume by explicit id. Capture it from the first run's `thread.started` event (field `thread.started.thread_id`) and pass it positionally:
  ```bash
  printf '%s' "$FOLLOWUP" | codex -C "$REPO" -s read-only exec resume "$THREAD_ID" -
  ```
  Explicit id beats `--last` every time. (Verified: an explicit resume reused the same thread id and retained the earlier token.)

## 9. JSONL, schema, and output-file parsing

- **Symptom:** empty/garbled parse; a "missing" answer; a trailing-newline mismatch; review output with no findings array.
- **Cause & fix:**
  - The answer is the **last `agent_message`** item, after `thread.started` → `turn.started` → `item.*`. A successful run ends in `turn.completed`; a failure ends in `error` / `turn.failed`.
  - `-o <file>` writes the final message with **no trailing newline** — do not assert one.
  - `--output-schema` constrains the final message; validate it. Schema-violation handling was **not** observed live (dossier §15).
  - `exec review --json` emits command/agent items, **not** a stable findings object — supply your own `--output-schema` if you need structured findings; do not assume a review array.

  Full observed JSONL contract and exit-code table: [`automation-and-sessions.md`](automation-and-sessions.md).

## 10. Timeout, interruption, rate limit, upstream

- **Symptom:** exit **124**; or a hang; or a failure you suspect is quota / rate-limit / provider-side.
- **Cause:** exit `124` is the **external GNU `timeout` wrapper**, not a Codex status. A pipe whose producer stays open can still block, even though `exec -` with closed stdin exits fast.
- **Fix:** always wrap unattended calls in `timeout` and own the stdin producer/EOF (`printf … | codex … exec -`). **Quota exhaustion, rate limiting, provider outage, signals, and model refusal were NOT tested (dossier §15)** — do not assume their exit codes; treat them as unknown and verify empirically before relying on any specific status.

## 11. First resort: codex doctor

Before dumping config into a bug report, run the built-in diagnostic:

```bash
codex doctor --json     # 18 checks; redact before sharing
```

The verified baseline returned overall `warning` (one benign local rollout-file / state-database parity note; everything else `ok`), and it confirms: auth configured, config loaded, Git available, provider HTTP **and** WebSocket reachable, sandbox readable, and the MCP server count. Prefer this **redacted** report over pasting `~/.codex/config.toml` — it answers layers 1, 4, 5, and 7 at once without leaking secrets.

## 12. Symptom to layer lookup

| Symptom | Start at layer |
|---|---|
| `command not found` / contradicts this skill | 1 |
| exit **2**, `unexpected argument` | 2 |
| exit **1** immediately, repo/trust guard | 3 |
| exit **1** after delay, `401` / retries | 4 |
| project config / hooks / rules ignored | 5 |
| unknown `-c` key ignored; want a hard fail | 5 |
| "write denied" but exit **0** | 6 |
| noisy macOS denial lines (read-only) | 6 |
| MCP tool missing / startup stall | 7 |
| `resume` picked the wrong session | 8 |
| answer missing / `-o` newline / no findings array | 9 |
| exit **124** / hang | 10 |
| suspected quota / rate-limit / outage | 10 (untested — verify) |
| don't know where to start | 11 (doctor) |
