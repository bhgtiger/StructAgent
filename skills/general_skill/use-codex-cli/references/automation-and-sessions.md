# Automation, output, and sessions

Purpose: run `codex exec` unattended and read its result correctly — which stream carries the answer, the observed `--json` event contract, when to reach for `-o` / `--output-schema` / `--json`, what each exit code proves (and does not), and how `--strict-config`, stdin ownership, and explicit-thread resume keep runs deterministic. Verified against `codex-cli 0.144.1`. Start from [`../SKILL.md`](../SKILL.md); every flag position lives in [`command-map.md`](command-map.md); the sandbox / trust / auth model lives in [`security-and-config.md`](security-and-config.md).

- [Output channels](#output-channels)
- [The observed JSONL event contract](#the-observed-jsonl-event-contract)
- [Output mode decision](#output-mode-decision)
- [Exit codes](#exit-codes)
- [Strict config and loose vs strict overrides](#strict-config-and-loose-vs-strict-overrides)
- [stdin ownership](#stdin-ownership)
- [Sessions](#sessions)
- [Timeouts](#timeouts)

## Output channels

`codex exec` splits its two outputs cleanly:

- **stdout** — the final agent message, and nothing else. Under `--json` it is the JSONL event stream instead. This is the only channel you parse.
- **stderr** — a human progress transcript: startup banner, resolved settings, the echoed prompt, agent progress, and a closing token count.

Real stderr from a read-only run (prompt `Reply with exactly: OK`):

```text
Reading additional input from stdin...
OpenAI Codex v0.144.1
--------
workdir: /var/folders/kl/f_26j6hj7lv3h865kh1g3q5m0000gn/T/codex-cli-probe.XXXXXX.3Sl2V7QlSD/fixture
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: max
reasoning summaries: none
session id: 019f525a-edd4-7821-8906-3cfe0b70d72e
--------
user
Reply with exactly: OK
codex
OK
tokens used
4,521
```

Two things this transcript proves:

- The `exec` defaults are printed in the header: **`approval: never`** and **`sandbox: read-only`**. That is what an unattended `codex exec` runs as unless you override `-s` (and set `approval_policy` via `-c` where it is consulted).
- The final answer `OK` is *also* echoed here, after the `codex` header — so stderr contains the result buried in progress noise. **Never parse stderr for the answer.** On this run stdout was 3 bytes (`OK\n`); take the result from stdout (or `-o`), never from the transcript.

## The observed JSONL event contract

Add `--json` (an `exec`-only flag — also valid on `exec review` / `exec resume`, never after top-level `review`) to get newline-delimited JSON events on stdout. A full 7-line successful run (the prompt asked for one filename):

```json
{"type":"thread.started","thread_id":"019f525a-fc70-7b03-812c-11511714c1c2"}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"I’ll inspect the repository and return one filename."}}
{"type":"item.started","item":{"id":"item_1","type":"command_execution","command":"/bin/zsh -lc 'rg --files | head -n 1'","aggregated_output":"","exit_code":null,"status":"in_progress"}}
{"type":"item.completed","item":{"id":"item_1","type":"command_execution","command":"/bin/zsh -lc 'rg --files | head -n 1'","aggregated_output":"app.py\n","exit_code":0,"status":"completed"}}
{"type":"item.completed","item":{"id":"item_2","type":"agent_message","text":"app.py"}}
{"type":"turn.completed","usage":{"input_tokens":27160,"cached_input_tokens":22016,"output_tokens":178,"reasoning_output_tokens":54}}
```

**Event types observed** (the top-level `type`): `thread.started`, `turn.started`, `item.started`, `item.completed`, `turn.completed`.

**Item types observed** (`item.type`): `agent_message`, `command_execution`.

**Fields worth reading:**

- `thread.started.thread_id` — capture this to resume the session later.
- `item.id`, `item.type` — item identity and kind.
- `agent_message.text` — a chunk of the model's prose.
- `command_execution.{command, aggregated_output, exit_code, status}` — what the agent ran, its combined output, its numeric exit, and `in_progress` / `completed`. Note `exit_code` is `null` while `status` is `in_progress`.
- `turn.completed.usage.{input_tokens, cached_input_tokens, output_tokens, reasoning_output_tokens}` — token accounting for the turn.

**Failure runs** add `error` items and end with `turn.failed`, and the process exits `1`. A missing-auth run emitted repeated `error` events (including an `item.completed` whose `item.type` is `error`, representing a transport fallback) and terminated with `turn.failed`; `turn.failed.error.message` held the terminal error.

**Documented by OpenAI but NOT observed in these runs** — treat as possible, not verified here: `reasoning`, `file-change`, `mcp-call`, `web-search`, `plan-update` item families. Do not build a parser that *requires* them, and do not assume they are absent either.

### Robust parsing contract

The observed order was thread start, turn start, zero or more item events, then turn completion — but that is an **observation, not a guarantee**. Parse defensively:

1. **Read line-delimited JSON.** One object per line; skip blank lines; tolerate unknown `type` / `item.type` values.
2. **The answer is the LAST `agent_message` item's `text`.** The sample has *two* `agent_message` items — a preamble (`I’ll inspect the repository…`) and the actual answer (`app.py`). Take the last, not the first.
3. **Detect failure structurally:** any line with `type == "error"` or `type == "turn.failed"`, or an `item.completed` whose `item.type == "error"` — together with a nonzero process exit.
4. **Do not assume ordering, cardinality, or that every item has an `item.started`.** In the sample, both `agent_message` items appear only as `item.completed`, while `command_execution` appears as `item.started` then `item.completed` under the same `item.id`.
5. **Do not assume `exec review` emits a stable findings array.** In the review probe it emitted `command_execution` items then an `agent_message` — no special finding object. Give review its own result contract (an `--output-schema`) if you need structured findings. Its `turn.completed.usage` counters read **all zeros** despite real model work — a runtime anomaly; do not use review usage for billing.

Extraction that follows the contract (validated against the sample above):

```bash
# answer = text of the LAST agent_message item
answer=$(jq -rc 'select(.type=="item.completed" and .item.type=="agent_message") | .item.text' out.jsonl | tail -n 1)

# failure = any error / turn.failed line (also check the process exit code separately)
fail=$(jq -rc 'select(.type=="error" or .type=="turn.failed" or (.type=="item.completed" and .item.type=="error")) | .type' out.jsonl)
[ -n "$fail" ] && printf 'codex reported failure: %s\n' "$fail" >&2
```

## Output mode decision

All three capture flags are **`exec`-only** (also valid on `exec review` / `exec resume`; never after top-level `review`). They compose.

| Need | Flag | Result |
|---|---|---|
| Just the final answer | `-o <file>` | Writes **only** the final agent message to the file. Prefer this for "just the answer." |
| Branch on fields in code | `--output-schema <file>` | Constrains the final message to a JSON Schema; a valid JSON object is returned. |
| The event trace / progress | `--json` | JSONL events on stdout (see the contract above). |

- `-o` writes the final message with **no trailing newline**. In the schema probe, `-o` produced 15 bytes — exactly `{"answer":"OK"}` — while stdout carried the same content plus a newline (16 bytes). Do not assume `-o` output is newline-terminated.
- `--output-schema` returned a valid JSON object in the probe (`{"answer":"OK"}`). Use it whenever code keys off fields rather than prose.
- Reach for `--json` **only** when you also need the trace; for "just the answer," `-o` is simpler and unambiguous.

They stack — this writes the schema-constrained object, and nothing else, to `out.json`:

```bash
printf '%s' "$PROMPT" | timeout 300 codex -C "$REPO" -s read-only exec --output-schema schema.json -o out.json -
```

## Exit codes

Reproduced verbatim from the dossier (§9):

| Situation | Exit | Interpretation |
| --- | ---: | --- |
| Successful standard/JSON/schema/review/resume run | 0 | Process completed |
| Read-only write denied but agent handled/reported it | 0 | Task can fail while process succeeds |
| Loose unknown `-c` key | 0 | Ignored without strict config; may spend usage |
| Strict unknown config field | 1 | Pre-model config failure |
| Missing authentication | 1 | Transport/API failure after retries |
| Non-Git directory without bypass | 1 | Pre-model repository guard |
| `exec -` with closed empty stdin | 1 | Missing prompt |
| Unsupported/mispositioned flag | 2 | CLI parse error |
| External GNU `timeout` expiry | 124 | Wrapper timeout, not a Codex-defined status |

The process status alone is not the task outcome. **Check more than `$?`**, in order:

1. Process exit status.
2. Presence of `turn.failed` / `error` in JSONL, if used.
3. Schema-valid final result or explicit success field.
4. Requested filesystem / diff / test postconditions.

Exit `0` with a denied write is a real observed case: a forbidden write under `-s read-only` failed the *task* while the *process* returned `0`. Exit `124` is the GNU `timeout` wrapper firing, not a Codex status.

## Strict config and loose vs strict overrides

`--strict-config` makes automation reproducible by turning silent config tolerance into an early, loud failure.

- **Without** strict mode, a `-c` value that is not valid TOML **falls back to a literal string**, and **unknown keys are ignored**. The probe `-c 'broken=[unclosed'` did **not** fail — Codex treated it as a literal, ignored the unknown key, **spent a real model call, and exited `0`**.
- **With** `--strict-config`, an unknown field fails **early, before any model call**: `--strict-config -c 'broken=true'` exited `1` with a config error and no model output.

So the "malformed config always fails" intuition is **wrong** — malformed-looking values are tolerated. The reliable early-failure probe is `--strict-config -c 'broken=true'`. Use `--strict-config` for unattended runs where a bad override should stop the run cheaply instead of silently spending usage. Caveat: a globally-parsed flag can still be rejected by the chosen subcommand at runtime (`--strict-config` is not supported by `codex debug`, for example), so prefer the exact command's `--help`.

## stdin ownership

`exec -` reads the prompt from stdin and keeps reading **until its stdin producer closes**. Two failure shapes:

- **Closed / empty stdin** (`codex ... exec - </dev/null`) exits **`1` immediately** with `No prompt provided via stdin.` — it does not hang.
- **An open, incomplete pipe** (for example stdin inherited from a parent that never closes it) **can block indefinitely**. This is why an external `timeout` is mandatory even for `-`.

Own both the producer and the EOF. The safe form pipes a controlled producer that closes cleanly:

```bash
printf '%s' "$PROMPT" | timeout 300 codex -C "$REPO" -s read-only exec -
```

`printf` writes exactly `$PROMPT` and closes, delivering EOF; `timeout` bounds the call regardless. Do not point `exec -` at an interactive terminal or a long-lived pipe you do not close.

## Sessions

### Independent second opinion

Use `--ephemeral` (`exec`-only) so the run leaves **no session file on disk** — ideal for an unbiased second opinion with nothing to resume or leak:

```bash
printf '%s' "$PROMPT" | timeout 300 codex -C "$REPO" -s read-only exec --ephemeral -
```

### Continue a session (resume by explicit thread id)

1. Capture the id from the first run's `thread.started` event:

```bash
thread_id=$(jq -rc 'select(.type=="thread.started") | .thread_id' first.jsonl)
```

2. Resume it. The thread id is positional after `exec resume`; `-C` / `-s` stay in **global** position (`exec resume` rejects them after the subcommand):

```bash
printf '%s' "$FOLLOWUP" | timeout 300 codex -C "$REPO" -s read-only exec resume "$thread_id" -
```

Resume was verified: the resumed thread **kept the same thread id** and **retained a token across turns** (G1/G2). Prefer the explicit id — **`--last` is cwd-filtered** and can pick an unrelated session in the same directory.

Other session verbs exist as **top-level** commands — `fork`, `archive`, `unarchive`, `delete` (and a top-level `resume`). Their exact flag positions are in [`command-map.md`](command-map.md); route selection per task type is in [`task-recipes.md`](task-recipes.md).

## Timeouts

Wrap **every** unattended `codex` call in `timeout` (GNU `timeout`, e.g. from Homebrew on macOS). A blocked model call, a stalled transport retry, or an open stdin pipe would otherwise hang your session forever. When `timeout` fires it kills Codex and returns **`124`** — the wrapper's timeout, **not** a Codex-defined exit status, so read `124` as "we gave up," not as a Codex result. Size the bound to the task (a read-only question needs far less than a multi-file implementation), and keep it on resume and review calls too.
