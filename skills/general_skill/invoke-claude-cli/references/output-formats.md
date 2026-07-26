# Output formats — full schema details

Read this when you are: parsing `claude` output programmatically, debugging a malformed response, or
choosing between `json` and `stream-json`. Verified against `claude` 2.1.220.

## `text` (default)

Plain prose written to stdout. No envelope, no metadata.

```
The plan looks reasonable. One concern: …
```

Use only when a human will read it. Don't grep, don't regex — Claude's phrasing changes between model
versions and across runs.

## `json` (single-object result)

One JSON object on a single line, terminated by newline, then exit. Real shape captured from 2.1.207
(field names are stable across the 2.1.x series; new timing/usage fields are additive):

```jsonc
{
  "type": "result",          // always "result" for --output-format json
  "subtype": "success",      // "success" | "error_max_turns" | "error_during_execution" | ...
  "is_error": false,         // true on auth failure, budget/turn cap, API error, schema-invalid, etc.
  "api_error_status": null,  // upstream HTTP status if the Anthropic API itself errored

  "result": "…",             // the answer text; with --json-schema, the schema JSON as a *string*
  "structured_output": { },  // present ONLY when --json-schema was used AND the model complied;
                             //   the answer already parsed into an object
  "stop_reason": "end_turn", // "end_turn" (prose) | "tool_use" (schema answer) | "max_tokens" | "refusal"

  "session_id": "uuid",      // resume with --resume <this>
  "uuid": "uuid",            // per-invocation ID, distinct from session_id

  "num_turns": 2,            // internal turns Claude took
  "duration_ms": 8723,       // total wall time including tool calls
  "duration_api_ms": 9882,   // time spent in Anthropic API calls
  "ttft_ms": 3089,           // time to first token
  "ttft_stream_ms": 1706,    // time to first streamed token
  "time_to_request_ms": 20,  // client-side setup time before the first request

  "total_cost_usd": 0.0185,  // billed cost in USD (3p providers may report 0)
  "usage": {                 // token counts (populated with real values)
    "input_tokens": 20,
    "output_tokens": 520,
    "cache_creation_input_tokens": 7321,
    "cache_read_input_tokens": 7081,
    "server_tool_use": { "web_search_requests": 0, "web_fetch_requests": 0 },
    "service_tier": "standard",
    "cache_creation": { "ephemeral_1h_input_tokens": 7321, "ephemeral_5m_input_tokens": 0 },
    "iterations": [ { "input_tokens": 10, "output_tokens": 317, "type": "message" } ],
    "speed": "standard"
  },
  "modelUsage": {            // per-model breakdown, keyed by full model ID
    "claude-haiku-4-5-20251001": {
      "inputTokens": 540, "outputTokens": 531,
      "cacheReadInputTokens": 7081, "cacheCreationInputTokens": 7321,
      "costUSD": 0.0185, "contextWindow": 200000, "maxOutputTokens": 32000
    }
  },

  "permission_denials": [],  // tool calls Claude attempted but was denied
  "terminal_reason": "completed", // "completed" | "interrupted" | "error"
  "fast_mode_state": "off"   // "on" | "off"
}
```

### Robust parsing pattern

```python
import json, subprocess

proc = subprocess.run(
    ["claude", "-p", "--output-format", "json", "--bare", "--tools", "", prompt],
    input=stdin_data, capture_output=True, text=True, timeout=600,
)
if proc.returncode != 0:
    raise RuntimeError(f"claude crashed: {proc.stderr}")

envelope = json.loads(proc.stdout)

# Always check is_error before trusting the answer
if envelope.get("is_error"):
    raise RuntimeError(f"claude reported error: {envelope.get('result')}")

cost = envelope.get("total_cost_usd", 0.0)       # for accounting
session_id = envelope["session_id"]              # save for --resume

# --- reading the answer ---
if "structured_output" in envelope:
    answer = envelope["structured_output"]       # already a dict/list — preferred
else:
    # No schema, OR schema was used but the model replied in prose (clarify/refuse).
    answer = envelope["result"]                  # treat as text; do NOT blindly json.loads
```

### Schema-validated structured output — where it lands

`--json-schema '<JSON Schema>'` gives Claude a `StructuredOutput` tool (present even with `--tools ""`).

- **Compliant path** — Claude calls the tool. Envelope gains `structured_output` (parsed object);
  `result` holds the same JSON as a string; `stop_reason == "tool_use"`.
- **Non-compliant path** — Claude answers in prose (clarifying question, refusal, or conversational
  reply). **No `structured_output`**; `result` is prose; `is_error: false`; `stop_reason: "end_turn"`.

So the schema constrains the *tool-call* shape, not whether the model chooses to call it. Never assume
`result` is schema-valid JSON — branch on the presence of `structured_output` (as above).

The **schema itself** is validated at startup (since 2.1.205): an invalid schema exits non-zero with
`Error: --json-schema is not a valid JSON Schema` plus the validator diagnostic. Before 2.1.205 an
invalid schema was silently ignored and returned unstructured text. The `format` keyword is accepted
but treated as an annotation and not enforced.

```bash
# Extract the structured answer with jq:
claude -p "Extract the exported function names from auth.py" \
  --output-format json \
  --json-schema '{"type":"object","properties":{"functions":{"type":"array","items":{"type":"string"}}},"required":["functions"]}' \
  | jq '.structured_output'
```

Use schemas aggressively for machine-consumed answers — they remove the whole class of "Claude phrased
it differently this time" failures, as long as you handle the prose fallback.

## `stream-json` (event stream)

Newline-delimited JSON events, one per line, emitted as Claude works. In `-p` mode, pair it with
`--verbose` for the full turn-by-turn stream (and `--include-partial-messages` for token deltas):

```bash
claude -p "Explain recursion" --output-format stream-json --verbose --include-partial-messages
```

Use it when you want to surface progress to a user before Claude is done, pipe into another streaming
consumer, or get token-by-token output.

Event types you'll see, in approximate order:

| `type` (`subtype`) | When it fires | Useful fields |
|---|---|---|
| `system` (`init`) | Session start | `session_id`, model, tools, MCP servers, plugins, `capabilities` (2.1.205+), `mcp_server_errors` (2.1.219+) |
| `system` (`api_retry`) | A retryable API error before a retry | `attempt`, `max_retries`, `retry_delay_ms`, `error`, `error_status` |
| `user` | Each user-role message Claude internally sends | `message.content` |
| `assistant` | Each assistant-role message | `message.content`, `message.stop_reason` |
| `stream_event` | Incremental deltas (with `--include-partial-messages`) | `event.delta.text` |
| `result` | Final — equals the single object you'd get from `--output-format json` | (full envelope) |

The **last** event is always a `result` with the same schema as single-shot `json`. A streaming
consumer can render `assistant`/`stream_event` deltas live, then capture `session_id`,
`total_cost_usd`, `structured_output`, etc. from the final `result`.

The `system/init` event's optional `capabilities` array (strings like `interrupt_receipt_v1`, present
from 2.1.205) lets you feature-detect protocol behaviors instead of comparing version strings — ignore
values you don't recognize.

In 2.1.219+, inspect `mcp_server_errors` before treating a supplied `--mcp-config` server as
available. It lists configuration entries skipped by validation. For nested-agent observability,
`--forward-subagent-text` forwards subagent text and thinking only with
`-p --output-format stream-json`, keyed by the spawning tool-use ID. Current releases allow nested
subagents up to depth 3 by default; set `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` when nesting is
not intended, and bound fan-out with `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`.

### Streaming parser sketch

```python
import json, subprocess
proc = subprocess.Popen(
    ["claude", "-p", "--output-format", "stream-json", "--verbose", "--include-partial-messages", prompt],
    stdout=subprocess.PIPE, text=True,
)
final = None
for line in proc.stdout:
    event = json.loads(line)
    if event["type"] == "stream_event" and event.get("event", {}).get("delta", {}).get("type") == "text_delta":
        render_delta(event["event"]["delta"]["text"])
    elif event["type"] == "result":
        final = event
        break
```

### `--include-hook-events`

With stream-json you can additionally request that all hook lifecycle events (PreToolUse, PostToolUse,
etc.) appear in the stream. Use it to debug a hook you suspect is mutating Claude's behavior.

## `--input-format stream-json`

The mirror image: instead of taking one prompt and exiting, you feed JSON messages on stdin and Claude
responds to each. Combine with `--output-format stream-json` for a bidirectional channel:

```bash
claude -p --input-format stream-json --output-format stream-json --verbose
```

Orchestrators wanting a persistent Claude subprocess use this. For most agent use cases, separate
one-shot calls with `--session-id`/`--resume` are simpler.

## Choosing between formats

| Goal | Format |
|---|---|
| Get an answer, parse it, exit | `--output-format json` |
| Get a strict structured answer | `--output-format json --json-schema '...'` → read `.structured_output` |
| Show progress in a UI | `--output-format stream-json --verbose` |
| Token-by-token streaming | `--output-format stream-json --verbose --include-partial-messages` |
| Persistent multi-message subprocess | `--input-format stream-json --output-format stream-json --verbose` |
| Human-only display | `--output-format text` (default) |
