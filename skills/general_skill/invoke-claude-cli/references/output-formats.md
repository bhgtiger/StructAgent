# Output formats — full schema details

Read this when you are: parsing `claude` output programmatically, debugging a malformed response, or choosing between `json` and `stream-json`.

## `text` (default)

Plain prose written to stdout. No envelope, no metadata.

```
The plan looks reasonable. One concern: …
```

Use only when a human will read it. Don't grep, don't regex — Claude's phrasing changes between model versions and across runs.

## `json` (single-object result)

One JSON object on a single line, terminated by newline, then exit. Schema (verified on `claude` 2.1.167; field names are stable across the 2.x series):

```jsonc
{
  "type": "result",          // always "result" for --output-format json
  "subtype": "success",      // "success" | "error_max_turns" | "error_during_execution" | ...
  "is_error": false,         // true on auth failure, budget exceeded, refusal, schema violation, etc.
  "api_error_status": null,  // upstream HTTP status if the Anthropic API itself returned an error

  "result": "…",             // answer text; may be empty when --json-schema is used
  "structured_output": null,   // object/array when --json-schema is used on current Claude Code
  "stop_reason": "end_turn", // "end_turn" | "max_tokens" | "tool_use" | "stop_sequence" | "refusal"

  "session_id": "uuid",      // resume with --resume <this>
  "uuid": "uuid",            // per-invocation ID, distinct from session_id

  "num_turns": 3,            // internal turns Claude took
  "duration_ms": 14233,      // total wall time including tool calls
  "duration_api_ms": 12100,  // time spent in Anthropic API calls

  "total_cost_usd": 0.0241,  // billed cost in USD (3p providers may report 0)
  "usage": {                 // token counts
    "input_tokens": 0,
    "output_tokens": 0,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
    "server_tool_use": { "web_search_requests": 0, "web_fetch_requests": 0 },
    "service_tier": "standard",
    "cache_creation": { "ephemeral_1h_input_tokens": 0, "ephemeral_5m_input_tokens": 0 },
    "inference_geo": "",
    "iterations": [],
    "speed": "standard"
  },
  "modelUsage": {},          // per-model breakdown for multi-model sessions

  "permission_denials": [],  // tool calls Claude attempted but was denied
  "terminal_reason": "completed", // "completed" | "interrupted" | "error"
  "fast_mode_state": "off"   // "on" | "off"
}
```

### Robust parsing pattern

```python
import json, subprocess

proc = subprocess.run(
    ["claude", "-p", "--output-format", "json", prompt],
    capture_output=True, text=True, timeout=600,
)
if proc.returncode != 0:
    raise RuntimeError(f"claude crashed: {proc.stderr}")

envelope = json.loads(proc.stdout)

# Always check is_error before trusting result
if envelope.get("is_error"):
    raise RuntimeError(f"claude reported error: {envelope['result']}")

# Surface cost for accounting
cost = envelope.get("total_cost_usd", 0.0)

# If you used --json-schema, current Claude Code puts the answer in
# .structured_output. Older builds used a JSON string in .result.
if used_schema:
    answer = envelope.get("structured_output")
    if answer is None:
        answer = json.loads(envelope["result"])
else:
    answer = envelope["result"]

# Save session for resumption
session_id = envelope["session_id"]
```

### Schema-validated structured output

`--json-schema '<JSON Schema>'` constrains the answer to match the schema. Current Claude Code (2.1.167) returns that parsed object in `structured_output`; older builds returned a JSON string in `.result`. The CLI validates before exiting; a non-conforming output causes `is_error: true` with a validation message.

```bash
claude -p --permission-mode bypassPermissions --effort max --output-format json \
  --json-schema '{"type":"object","properties":{"verdict":{"enum":["approve","reject","revise"]},"reasons":{"type":"array","items":{"type":"string"}}},"required":["verdict","reasons"],"additionalProperties":false}' \
  "Review and respond per schema."
```

Then in your code:

```python
envelope = json.loads(proc.stdout)
answer = envelope.get("structured_output")
if answer is None:
    answer = json.loads(envelope["result"])
assert answer["verdict"] in ("approve", "reject", "revise")
```

Use schemas aggressively — they remove the entire class of "Claude phrased it differently this time" failures.

## `stream-json` (event stream)

Newline-delimited JSON events, one per line, emitted as Claude works. Use when:

- You want to surface progress to a user before Claude is done (live UI).
- You're piping into another streaming consumer.
- You want token-by-token incremental output (`--include-partial-messages`).

Event types you'll see, in approximate order:

| `type` | When it fires | Useful fields |
|---|---|---|
| `system` (subtype `init`) | Session start | `session_id`, model, tools |
| `user` | Each user-role message Claude internally sends | `message.content` |
| `assistant` | Each assistant-role message | `message.content`, `message.stop_reason` |
| `tool_use` | Claude invoked a tool | `name`, `input`, `id` |
| `tool_result` | Tool returned | `tool_use_id`, `content`, `is_error` |
| `prompt_suggestion` | Only when `--prompt-suggestions` is enabled in print/SDK mode | predicted next user prompt; ignore for result parsing |
| `result` | Final, equivalent to the single object you'd get from `--output-format json` | (full envelope) |

The **last** event is always a `result` event with the same schema as single-shot `json` output. So a streaming consumer can:

1. Render `assistant` deltas in real time.
2. On `result`, capture `session_id`, `total_cost_usd`, etc.

Leave `--prompt-suggestions` off for normal orchestration. If someone enables it, treat `prompt_suggestion` as advisory UI data, not as Claude's answer or the final envelope.

### Streaming parser sketch

```python
import json, subprocess
proc = subprocess.Popen(
    ["claude", "-p", "--output-format", "stream-json", "--include-partial-messages", prompt],
    stdout=subprocess.PIPE, text=True,
)
for line in proc.stdout:
    event = json.loads(line)
    if event["type"] == "assistant":
        render_delta(event["message"]["content"])
    elif event["type"] == "result":
        final = event
        break
```

### `--include-hook-events`

With stream-json, you can additionally request that all hook lifecycle events (PreToolUse, PostToolUse, etc.) appear in the stream:

```bash
claude -p --permission-mode bypassPermissions --effort max --output-format stream-json --include-hook-events ...
```

Use for debugging when you suspect a hook is mutating Claude's behavior.

### `--include-partial-messages`

Splits each `assistant` message into chunked deltas as tokens arrive. Required for true token-by-token UI streaming. Only works with `-p` + `--output-format stream-json`.

## `--input-format stream-json`

The mirror image: instead of taking one prompt and exiting, you feed JSON messages on stdin and Claude responds to each. Combine with `--output-format stream-json` for a bidirectional channel:

```bash
claude -p --permission-mode bypassPermissions --effort max --input-format stream-json --output-format stream-json
```

This is what orchestrators wanting a persistent Claude subprocess use. The input schema mirrors the output `user`/`assistant` event shapes. For most agent use cases, separate one-shot calls with `--session-id`/`--resume` are simpler.

## Choosing between formats

| Goal | Format |
|---|---|
| Get an answer, parse it, exit | `--output-format json` |
| Get a strict structured answer | `--output-format json --json-schema '...'` |
| Show progress in a UI | `--output-format stream-json` |
| Token-by-token streaming | `--output-format stream-json --include-partial-messages` |
| Persistent multi-message subprocess | `--input-format stream-json --output-format stream-json` |
| Human-only display | `--output-format text` (default) |

## Non-interactive caveats

`-p` and non-TTY stdout skip Claude Code's workspace-trust dialog. Only parse output from runs launched in a cwd you already trust or in a disposable sandbox/worktree.

In `-p` mode, settings files that fail validation are silently ignored with no error dialog. Do not rely on `--settings` / `--setting-sources` as the only way to enforce budgets, tool policy, permission mode, or auth; keep those guardrails explicit on the command line and validate the JSON envelope (`is_error`, `total_cost_usd`, `permission_denials`) after every run.
