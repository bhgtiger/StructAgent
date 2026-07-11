# Codex task recipes

One compact, copy-pasteable recipe per task type for driving `codex exec` from another agent. Each recipe states the **Route**, **Access start** (sandbox), **Session**, **Output**, the exact **Command shape**, the matching **Prompt contract** (defined in [`prompt-contracts.md`](prompt-contracts.md)), how to **Verify** (never trust exit 0), and the **Common failure**.

Every command below already reflects the parse-verified flag positions: globals (`-C`, `-s`, `--search`) go **before** `exec`; `--json` / `--output-schema` / `-o` / `-i` / `--ephemeral` go **after** it; `exec review` and `exec resume` accept only their own review/output flags. The full 6-column matrix and every flag's home live in [`command-map.md`](command-map.md). For the route decision itself, see the decision tree in [`../SKILL.md`](../SKILL.md).

Conventions: `$REPO` = absolute repo root, `$PROMPT` = the contract text, and `timeout` wraps every unattended call. Prompts arrive on stdin (`-`) — pipe them, never splice generated text into argv.

## Contents

1. [Explain or map a repository](#1-explain-or-map-a-repository)
2. [Diagnose a bug without fixing](#2-diagnose-a-bug-without-fixing)
3. [Focused implementation or fix](#3-focused-implementation-or-fix)
4. [Refactor or migrate in stages](#4-refactor-or-migrate-in-stages)
5. [Review uncommitted, base branch, or commit](#5-review-uncommitted-base-branch-or-commit)
6. [Independent second opinion](#6-independent-second-opinion)
7. [Structured extraction](#7-structured-extraction)
8. [Image analysis](#8-image-analysis)
9. [Web-assisted research](#9-web-assisted-research)
10. [Repair failing tests](#10-repair-failing-tests)
11. [CI or scripted automation](#11-ci-or-scripted-automation)
12. [Non-Git directory](#12-non-git-directory)
13. [Persistent multi-agent workflow](#13-persistent-multi-agent-workflow)

---

### 1. Explain or map a repository

**Route** `exec` · **Access** `read-only` · **Session** ephemeral · **Output** `-o` · **Contract** [analyze-only](prompt-contracts.md#analyze-only)

```bash
printf '%s' "$PROMPT" | timeout 300 codex -C "$REPO" -s read-only exec --ephemeral -o map.md -
```

- **Verify:** `git -C "$REPO" status --porcelain` is empty (read-only sandbox forbade edits) and `map.md` names real files/functions, not generic advice. `-o` output has **no trailing newline**.
- **Common failure:** treating the prose as ground truth — spot-check the cited files yourself before relying on the map.

### 2. Diagnose a bug without fixing

**Route** `exec` · **Access** `read-only` · **Session** ephemeral · **Output** `-o` · **Contract** [diagnose-only](prompt-contracts.md#diagnose-only)

```bash
printf '%s' "$PROMPT" | timeout 300 codex -C "$REPO" -s read-only exec --ephemeral -o diagnosis.md -
```

- **Verify:** working tree unchanged (`git status --porcelain` empty) **and** the report pins a root cause to a specific `file:line` with a mechanism — not a hunch. The read-only sandbox is the hard guard; the no-edit contract reinforces it.
- **Common failure:** a read-only write attempt still exits `0` (the agent reports it failed). Confirm nothing was written; do not read exit `0` as "diagnosed and safe".

### 3. Focused implementation or fix

**Route** `exec` · **Access** `workspace-write` · **Session** ephemeral (or resume for follow-ups) · **Output** stdout / `--json` · **Contract** [implement-and-verify](prompt-contracts.md#implement-and-verify)

```bash
printf '%s' "$PROMPT" | timeout 600 codex -C "$REPO" -s workspace-write exec -
```

- **Verify:** inspect the real change yourself — `git -C "$REPO" diff` — then run the build/tests independently. Codex's "done, tests pass" is a claim, not proof.
- **Common failure:** scope creep or unrelated reformatting. Bound scope in the contract; reject diffs that touch out-of-scope files.

### 4. Refactor or migrate in stages

**Route** `exec` then `exec resume <id>` · **Access** `workspace-write` · **Session** persistent (resume by id) · **Output** `--json` (to capture the id) · **Contract** [continuation](prompt-contracts.md#continuation)

```bash
# Turn 1 — capture the thread id from the JSONL event stream
printf '%s' "$PROMPT" | timeout 600 codex -C "$REPO" -s workspace-write exec --json - | tee turn1.jsonl
TID=$(grep -o '"thread_id":"[^"]*"' turn1.jsonl | head -1 | cut -d'"' -f4)
# Turn 2+ — resume; -s/-C stay in GLOBAL position (exec resume rejects them after the subcommand)
printf '%s' "$NEXT" | timeout 600 codex -C "$REPO" -s workspace-write exec resume "$TID" -
```

- **Verify:** checkpoint every turn — inspect the incremental `git diff` and run tests before sending the next prompt. Do not batch several migration steps into one unreviewed turn.
- **Common failure:** putting `-s`/`-C` after `exec resume` (parse error, exit `2`), or using `--last` instead of the id (`--last` is cwd-filtered and can select an unrelated session).

### 5. Review uncommitted, base branch, or commit

**Route** `exec review` · **Access** `read-only` (GLOBAL position) · **Session** fresh · **Output** `--json` · **Contract** [review](prompt-contracts.md#review)

```bash
# Pick ONE target flag:
timeout 300 codex -C "$REPO" -s read-only exec review --uncommitted --json > review.jsonl
# codex -C "$REPO" -s read-only exec review --base main --json > review.jsonl
# codex -C "$REPO" -s read-only exec review --commit "$SHA" --json > review.jsonl
```

- **Verify:** the run ends with `turn.completed`, not `turn.failed`/`error`. Review emits a plain `agent_message`, **not** a stable findings array — if you must parse findings, add `--output-schema`. Ignore review `usage` fields (observed all-zero; not billing-reliable).
- **Common failure:** passing `-s`/`-C`/`--add-dir`/`-p`/`-i` **after** `exec review` — hard parse error (exit `2`). They belong in global position (or, for `-i`, not at all — `exec review` has no image flag).

### 6. Independent second opinion

**Route** `exec` · **Access** `read-only` · **Session** ephemeral, always fresh · **Output** `-o` · **Contract** [analyze-only](prompt-contracts.md#analyze-only)

```bash
git -C "$REPO" diff | timeout 300 codex -C "$REPO" -s read-only exec --ephemeral -o opinion.md 'Give an independent review of this diff. Do not edit anything.'
```

- **Verify:** it is advisory — cross-check each claim against the code before acting. `--ephemeral` writes no session file, so nothing anchors a later run.
- **Common failure:** resuming a prior session for the "second" opinion — that reuses context and defeats independence. Always start fresh, never `resume`.

### 7. Structured extraction

**Route** `exec` · **Access** `read-only` · **Session** ephemeral · **Output** `--output-schema` + `-o` · **Contract** [structured-extraction](prompt-contracts.md#structured-extraction)

```bash
printf '%s' "$PROMPT" | timeout 300 codex -C "$REPO" -s read-only exec --output-schema schema.json -o out.json -
```

- **Verify:** validate `out.json` against `schema.json` yourself (e.g. a JSON-schema validator) — conformance is model-enforced, not guaranteed on every version. The `-o` file is the exact final bytes with **no trailing newline**; `jq . out.json` still parses it.
- **Common failure:** assuming the file ends in a newline, or assuming exit `0` proves schema-validity. Parse and validate before branching on fields.

### 8. Image analysis

**Route** `exec` · **Access** `read-only` · **Session** ephemeral · **Output** `-o` · **Contract** [analyze-only](prompt-contracts.md#analyze-only)

```bash
printf '%s' "$PROMPT" | timeout 300 codex -C "$REPO" -s read-only exec -i diagram.png --ephemeral -o notes.md -
```

- **Verify:** cross-check the description against the actual image and any code it references; models misread diagrams.
- **Common failure:** attaching `-i` to `exec review` — it has **no** image flag and will parse-error. `-i` is valid on `exec` and `exec resume` only.

### 9. Web-assisted research

**Route** `exec` with GLOBAL `--search` · **Access** `read-only` · **Session** ephemeral · **Output** `-o` · **Contract** [analyze-only](prompt-contracts.md#analyze-only)

```bash
printf '%s' "$PROMPT" | timeout 400 codex --search -C "$REPO" -s read-only exec --ephemeral -o research.md -
```

- **Verify:** treat findings as leads — open and confirm every cited source/URL. (`--search` behavior was not exercised live in the dossier; documented, not locally verified.)
- **Common failure:** `codex exec --search` — `--search` is **global-only** and fails to parse after `exec`. It must precede `exec`.

### 10. Repair failing tests

**Route** `exec` · **Access** `workspace-write` · **Session** ephemeral · **Output** stdout / `--json` · **Contract** [implement-and-verify](prompt-contracts.md#implement-and-verify) (test-repair variant)

```bash
printf '%s' "$PROMPT" | timeout 600 codex -C "$REPO" -s workspace-write exec -
```

- **Verify:** re-run the previously failing test yourself after the run — green from Codex is a claim. Read the diff: confirm it fixed the code, not the test.
- **Common failure:** Codex weakens or deletes the assertion to make the suite pass. Require in the contract that the test's intent is preserved; inspect the diff for edited test files.

### 11. CI or scripted automation

**Route** `exec` (or `exec review`) · **Access** minimal for the task · **Session** ephemeral · **Output** `--json` and/or `--output-schema` + `-o` · **Contract** [implement-and-verify](prompt-contracts.md#implement-and-verify) or [structured-extraction](prompt-contracts.md#structured-extraction)

```bash
printf '%s' "$PROMPT" | timeout 600 codex -C "$REPO" -s workspace-write exec \
  --strict-config --output-schema schema.json -o result.json --json - > events.jsonl
git -C "$REPO" diff > change.patch   # capture the artifact for review/apply
```

- **Verify:** check **all** of — process exit status, absence of `error`/`turn.failed` in `events.jsonl`, schema-valid `result.json`, and the actual `change.patch`/postconditions. `--strict-config` makes an unknown config field fail fast (exit `1`, pre-model) instead of being silently ignored.
- **Common failure:** trusting `$?` alone. Exit `0` with a denied write or a no-op is a real, observed case. `--strict-config` is accepted on `exec` but not on every command (e.g. `debug`) — pin it only where supported.

### 12. Non-Git directory

**Route** `exec` with `--skip-git-repo-check` · **Access** minimal · **Session** ephemeral · **Output** `-o` · **Contract** any of the above

```bash
printf '%s' "$PROMPT" | timeout 300 codex -C "$DIR" -s read-only exec --skip-git-repo-check --ephemeral -o out.md -
```

- **Warning:** `--skip-git-repo-check` **bypasses a safety guard**. The Git check normally stops Codex outside a repo (exit `1`, pre-model); skipping it removes the version-control boundary you would otherwise diff and revert against. Prefer `git init` in the directory when you can.
- **Verify:** with no VCS to diff, snapshot the directory before any `workspace-write` run and compare after. `--skip-git-repo-check` is exec-family only (`exec`, `exec review`, `exec resume`).
- **Common failure:** omitting the flag in a non-repo dir — early exit `1` ("not inside a trusted directory / Git repo"), no model call.

### 13. Persistent multi-agent workflow

**Route** `codex mcp-server` (tools `codex` / `codex-reply`) — not repeated cold `exec` · see [`mcp-and-advanced.md`](mcp-and-advanced.md)

When an orchestrator holds a long-lived relationship with Codex — many prompts, shared thread, tool-server semantics — drive the MCP server rather than spawning a fresh `exec` each time. Occasional continuation is fine with `exec resume` (recipe 4); a persistent, programmatic channel belongs in [`mcp-and-advanced.md`](mcp-and-advanced.md).

---

**See also:** [`prompt-contracts.md`](prompt-contracts.md) for the contract text each recipe names · [`automation-and-sessions.md`](automation-and-sessions.md) for JSONL, exit codes, and stdin ownership · [`security-and-config.md`](security-and-config.md) for sandbox modes, trust, and the dangerous-bypass flags · [`command-map.md`](command-map.md) for the full flag matrix.
