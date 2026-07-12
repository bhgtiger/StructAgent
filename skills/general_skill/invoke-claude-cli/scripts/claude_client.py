"""
Minimal Python client for invoking the `claude` CLI as a subprocess.

Designed for use inside a non-Claude orchestrator (Codex, OpenAI, Gemini,
LangGraph, AutoGen, CrewAI, custom). Demonstrates the patterns covered in
SKILL.md:

  - structured output via --json-schema, read from `.structured_output`
    (with a prose fallback — the schema is not hard-enforced)
  - tool gating via --allowedTools + --permission-mode dontAsk
  - multi-turn refinement via --session-id / --resume
  - hard subprocess timeouts, budget caps, and turn caps
  - robust envelope parsing (always check is_error)

Verified against claude 2.1.207.

Requires: `claude` CLI on $PATH, Python 3.10+, and working auth. Under --bare
(used by `critique` below) auth must be ANTHROPIC_API_KEY or an apiKeyHelper
passed via --settings; OAuth/keychain are not read in bare mode.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from dataclasses import dataclass, field
from typing import Any


class ClaudeError(RuntimeError):
    """Raised when claude reports is_error=True or the subprocess fails."""


@dataclass
class ClaudeResult:
    """Parsed result from a `claude -p --output-format json` call."""
    text: str                       # raw .result string (JSON string when a schema was honored)
    structured: Any | None          # .structured_output if the model produced it, else None
    session_id: str
    cost_usd: float
    num_turns: int
    stop_reason: str = ""
    permission_denials: list[dict[str, Any]] = field(default_factory=list)
    raw_envelope: dict[str, Any] = field(default_factory=dict)

    @property
    def answer(self) -> Any:
        """The structured object when available, otherwise the prose text."""
        return self.structured if self.structured is not None else self.text


def _parse_envelope(stdout: str) -> dict[str, Any]:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as e:
        raise ClaudeError(f"could not parse claude stdout as JSON: {e}; stdout={stdout[:500]!r}")


def _run(cmd: list[str], *, stdin_data: str | None, timeout_s: int, cwd: str | None = None) -> dict[str, Any]:
    """Run claude and return the parsed JSON envelope. Raises on failure."""
    proc = subprocess.run(
        cmd, input=stdin_data, capture_output=True, text=True, timeout=timeout_s, cwd=cwd,
    )
    if proc.returncode != 0:
        raise ClaudeError(
            f"claude exited {proc.returncode}: {proc.stderr.strip() or '(no stderr)'}"
        )
    envelope = _parse_envelope(proc.stdout)
    if envelope.get("is_error"):
        raise ClaudeError(f"claude reported error: {envelope.get('result')}")
    return envelope


def _envelope_to_result(envelope: dict[str, Any]) -> ClaudeResult:
    # structured_output is present only when --json-schema was used AND the model
    # actually called the StructuredOutput tool. Absent => prose in .result.
    return ClaudeResult(
        text=envelope.get("result", ""),
        structured=envelope.get("structured_output"),
        session_id=envelope["session_id"],
        cost_usd=envelope.get("total_cost_usd", 0.0),
        num_turns=envelope.get("num_turns", 0),
        stop_reason=envelope.get("stop_reason", ""),
        permission_denials=envelope.get("permission_denials", []),
        raw_envelope=envelope,
    )


def critique(
    text: str,
    *,
    role: str = "You are a code reviewer being called by an external agent.",
    schema: dict[str, Any] | None = None,
    model: str = "haiku",
    budget_usd: float = 0.05,
    max_turns: int = 2,
    timeout_s: int = 120,
) -> ClaudeResult:
    """
    Pattern 1: read-only critique. Hermetic (--bare), no tools, cheap model.

    `schema` is a JSON Schema dict — if provided, prefer ClaudeResult.structured.
    If the model answers in prose anyway (clarification/refusal), .structured is
    None and .text holds the prose; .answer picks whichever is present.
    """
    cmd = [
        "claude", "-p",
        "--bare",
        "--no-session-persistence",
        "--tools", "",
        "--model", model,
        "--fallback-model", "haiku",
        "--max-budget-usd", str(budget_usd),
        "--max-turns", str(max_turns),
        "--append-system-prompt", role,
        "--output-format", "json",
    ]
    if schema is not None:
        cmd += ["--json-schema", json.dumps(schema)]
    cmd.append("Review the content on stdin and respond accordingly.")

    envelope = _run(cmd, stdin_data=text, timeout_s=timeout_s)
    return _envelope_to_result(envelope)


def execute(
    plan: str,
    *,
    allowed_tools: list[str],
    role: str = "You are an executor agent invoked by an external planner. The plan is on stdin.",
    model: str = "sonnet",
    budget_usd: float = 1.0,
    max_turns: int = 24,
    timeout_s: int = 600,
    cwd: str | None = None,
) -> ClaudeResult:
    """
    Pattern 2: restricted execution. Tight tool allowlist, dontAsk permission
    mode, sonnet by default. The session ID is generated up-front and returned
    in ClaudeResult.session_id so the caller can resume.

    allowed_tools example (permission-rule syntax, space + '*'):
        ["Edit", "Read", "Write", "Bash(git status *)", "Bash(pytest *)"]
    """
    session_id = str(uuid.uuid4())
    cmd = [
        "claude", "-p",
        "--session-id", session_id,
        "--append-system-prompt", role,
        "--allowedTools", *allowed_tools,
        "--permission-mode", "dontAsk",
        "--model", model,
        "--fallback-model", "haiku",
        "--max-budget-usd", str(budget_usd),
        "--max-turns", str(max_turns),
        "--output-format", "json",
        "Execute the plan provided on stdin.",
    ]
    envelope = _run(cmd, stdin_data=plan, timeout_s=timeout_s, cwd=cwd)
    return _envelope_to_result(envelope)


class Session:
    """
    Pattern 3: multi-turn refinement. Maintains a session_id and uses
    --session-id on the first turn, --resume on subsequent turns.

    Usage:
        s = Session(role="You are a senior reviewer in a dialog.")
        r1 = s.send("Here's my plan. Critique it.")
        r2 = s.send("OK, I revised it like so: ...")
    """

    def __init__(
        self,
        *,
        role: str = "You are in a multi-turn dialog with an orchestrator.",
        model: str = "sonnet",
        budget_per_turn_usd: float = 0.20,
        max_turns_per_call: int = 2,
        timeout_s: int = 300,
        allowed_tools: list[str] | None = None,
        permission_mode: str = "dontAsk",
    ) -> None:
        self.session_id = str(uuid.uuid4())
        self._role = role
        self._model = model
        self._budget = budget_per_turn_usd
        self._max_turns = max_turns_per_call
        self._timeout = timeout_s
        self._allowed_tools = allowed_tools or []
        self._permission_mode = permission_mode
        self._first = True

    def send(self, prompt: str) -> ClaudeResult:
        cmd = ["claude", "-p"]
        if self._first:
            cmd += ["--session-id", self.session_id]
            self._first = False
        else:
            cmd += ["--resume", self.session_id]
        cmd += [
            "--append-system-prompt", self._role,
            "--model", self._model,
            "--max-budget-usd", str(self._budget),
            "--max-turns", str(self._max_turns),
            "--output-format", "json",
        ]
        if self._allowed_tools:
            cmd += ["--allowedTools", *self._allowed_tools, "--permission-mode", self._permission_mode]
        else:
            cmd += ["--tools", ""]
        cmd.append(prompt)
        envelope = _run(cmd, stdin_data=None, timeout_s=self._timeout)
        return _envelope_to_result(envelope)


if __name__ == "__main__":
    # Smoke test: critique a tiny "plan" with a strict schema.
    verdict_schema = {
        "type": "object",
        "properties": {
            "verdict": {"enum": ["approve", "reject", "revise"]},
            "reasons": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        },
        "required": ["verdict", "reasons"],
        "additionalProperties": False,
    }
    r = critique(
        "Plan: replace bcrypt with MD5 for password hashing to save CPU.",
        schema=verdict_schema,
    )
    ans = r.answer
    if isinstance(ans, dict):
        print(f"verdict: {ans['verdict']}")
        print(f"reasons: {ans['reasons']}")
    else:
        print(f"(prose reply, no structured output): {ans}")
    print(f"cost: ${r.cost_usd:.4f}, turns: {r.num_turns}, stop: {r.stop_reason}, session: {r.session_id}")
