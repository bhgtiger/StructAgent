# Codex prompt contracts

Reusable delegation contracts for the prompt you pipe into `codex exec`. A recipe in [`task-recipes.md`](task-recipes.md) picks the route and flags; the contract here fills the `$PROMPT` it sends.

**Core rule:** give Codex an **objective + boundaries + acceptance criteria + how to verify**, then let it read the repository itself. Do **not** paste the whole codebase into the prompt — Codex has file tools and a sandbox; pasting wastes tokens, goes stale, and hides the real files from its own inspection. Name the paths and let Codex open them. A prompt that specifies *what done looks like* and *what is off-limits* beats a longer prompt that dumps context.

Pipe the contract on stdin so shell escaping and prompt-injection can't bite:

```bash
printf '%s' "$CONTRACT" | timeout 300 codex -C "$REPO" -s read-only exec -
```

## Contents

- [Contract template](#contract-template)
- [analyze-only](#analyze-only)
- [diagnose-only](#diagnose-only)
- [implement-and-verify](#implement-and-verify)
- [review](#review)
- [structured-extraction](#structured-extraction)
- [continuation](#continuation)

---

## Contract template

Fill these fields. Drop a field only when it truly does not apply; never drop **Edits permitted** or **Acceptance criteria**.

```text
Outcome:            One sentence — what must be true when you finish.
Relevant context:   Point to files/dirs/tickets. Name paths; do not paste them.
In scope:           The files or behavior you may read/change.
Out of scope:       What to leave untouched. "Do not wander" belongs here.
Edits permitted:    YES (within scope) or NO (read-only).
Evidence vs hypotheses:
                    EVIDENCE — only what you confirmed from code or read-only commands.
                    HYPOTHESES — suspicions, each with the file:line that would confirm it.
                    Keep the two lists separate; never present a guess as a fact.
Acceptance criteria: Testable conditions that define success (be specific).
Commands to run:    Build/test/inspection commands Codex should actually run.
Final report format: The exact sections/shape you want back.
Stop conditions:    When to stop and ask the user instead of guessing.
```

Two rules that make contracts trustworthy: keep **evidence separate from hypotheses** (so you can tell what Codex verified from what it assumed), and make **acceptance criteria checkable** (so your own verification step has something concrete to test). Enforcement of "no edits" comes from the sandbox (`-s read-only`), not the prose — the contract only reinforces it; see [`security-and-config.md`](security-and-config.md).

---

## analyze-only

Read-only understanding. Pair with recipe 1, 6, 8, or 9 (`-s read-only`).

```text
You are analyzing this repository. Read-only: do NOT modify, create, or delete any file.

Outcome: <e.g. "a map of how an HTTP request flows from router to database">.
Relevant context: start from <path/entrypoint>; the subsystem lives under <dir>.
In scope: <paths>. Out of scope: everything else — do not wander into unrelated modules.
Edits permitted: NO. Use only read-only inspection (rg, sed -n, ls, git log --stat).
Acceptance: the report names concrete files, functions, and call edges — not generic advice.
Final report format:
  1. Entry points
  2. Call path (caller -> callee, with file:line)
  3. Key files, one line each
  4. Open questions / risks
Stop and ask if: the named subsystem is absent or the scope is ambiguous. Do not guess.
```

## diagnose-only

Find the root cause; change nothing. Pair with recipe 2 (`-s read-only`).

```text
Diagnose the bug below. DO NOT fix it and DO NOT edit any file. Read-only only.

Symptom: <observed behavior / exact error text / failing input>.
Reproduction: <command or steps>, if known.
In scope: <paths most likely involved>. Out of scope: unrelated refactors.
Edits permitted: NO.
Keep separate:
  EVIDENCE — only what you confirmed by reading code or running read-only commands.
  HYPOTHESES — ranked suspected causes, each with the file:line that would confirm it.
Acceptance: root cause pinned to a specific file:line with the mechanism explained; no fix applied.
Final report format: Evidence / Root cause (file:line) / Why it happens / Suggested fix (describe, do NOT apply) / Confidence (high|medium|low).
Stop and ask if: you cannot reproduce, or the evidence contradicts the reported symptom.
```

## implement-and-verify

Bounded change plus proof. Pair with recipe 3, 10, or 11 (`-s workspace-write`).

```text
Implement the change below. You may edit files in this workspace, within scope only.

Outcome: <the behavior that must hold when done>.
Relevant context: <ticket / prior decision / the function to change>.
In scope: <paths/behavior you may change>. Out of scope: <do-not-touch files>; no unrelated reformatting.
Edits permitted: YES, within scope.
Acceptance criteria:
  - <criterion 1, testable>
  - <criterion 2, testable>
Commands to run: <build cmd>; <test cmd, e.g. `pytest tests/auth -q`>. Make them pass; paste their output.
Keep separate: what you changed (diff summary) vs. what you assumed.
Final report format: Summary / Files changed / Commands run + results / Residual risks.
Stop and ask if: a criterion conflicts with existing behavior, or a test needs network/credentials you lack. Do not weaken or delete tests to pass.
```

## review

Independent critique of changes. Pair with recipe 5 (`exec review`, `-s read-only`).

```text
Review the changes in this repository. Read-only: do NOT edit.

Focus: correctness, security, missing tests, and regressions in <area>.
Out of scope: style nits unless they cause bugs.
Edits permitted: NO.
For each finding return: severity (blocker|major|minor), file:line, why it is wrong, and a concrete fix.
Acceptance: every blocker/major cites a specific line and a mechanism — not a vague concern.
Final report format: findings as an ordered list (blockers first), then an overall verdict: approve | revise | reject.
Stop and ask if: the diff is empty or the intended behavior is unstated.
```

Machine-readable review: `exec review` returns a plain `agent_message`, not a stable findings array. If you must parse findings, add `--output-schema` (see [structured-extraction](#structured-extraction) and [`automation-and-sessions.md`](automation-and-sessions.md)).

## structured-extraction

JSON out, grounded in the code. Pair with recipe 7 and `--output-schema schema.json -o out.json`.

```text
Extract the requested facts from this repository. Read-only: do NOT edit.
Return ONLY the JSON described by the output schema — no prose, no markdown fence.

In scope: <what to extract, e.g. "every REST route: method, path, handler, source file, auth requirement">.
Source of truth: the code under <path>. Do not invent items not present in the code.
Acceptance: every array item is grounded in a real file; include the file path per item.
```

Matching JSON Schema — pass as `--output-schema schema.json`:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["routes"],
  "properties": {
    "routes": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["method", "path", "handler", "file", "auth_required"],
        "properties": {
          "method":        { "type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"] },
          "path":          { "type": "string" },
          "handler":       { "type": "string" },
          "file":          { "type": "string" },
          "auth_required": { "type": "boolean" }
        }
      }
    }
  }
}
```

Run with `--output-schema schema.json -o out.json`: the final message conforms to this schema, and `-o` writes exactly those bytes with **no trailing newline**. Validate `out.json` against the schema yourself before branching on it — conformance is model-enforced, not version-guaranteed (see [`automation-and-sessions.md`](automation-and-sessions.md)).

## continuation

Next turn of the same thread. Pair with recipe 4 (`exec resume <thread-id>`).

```text
Continue the previous task in this same session.

Prior state: <what the last turn accomplished — one or two lines>.
This turn's outcome: <the next increment>.
Constraints unchanged: same in-scope paths, same edits-permitted setting, same acceptance style as before.
Before new work: confirm the prior turn's changes are still present (git status), then proceed.
Final report format: what changed this turn / cumulative state / next suggested step.
Stop and ask if: the working tree diverged from what you left (someone else edited it).
```

Send with `codex -C "$REPO" -s <mode> exec resume <thread-id> -`. Keep `-s`/`-C` in **global** position — `exec resume` rejects them after the subcommand. Capture `<thread-id>` from the first run's `thread.started.thread_id` in the `--json` stream (see [`automation-and-sessions.md`](automation-and-sessions.md)).

---

**See also:** [`task-recipes.md`](task-recipes.md) for the route + flags each contract pairs with · [`command-map.md`](command-map.md) for flag positions · [`security-and-config.md`](security-and-config.md) for how the sandbox enforces "edits permitted".
