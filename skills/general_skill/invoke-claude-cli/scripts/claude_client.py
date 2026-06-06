"""
Minimal Python client for invoking the `claude` CLI as a subprocess.

Designed for use inside a non-Claude orchestrator (OpenAI, Gemini, LangGraph,
AutoGen, custom). Demonstrates the patterns covered in SKILL.md:

  - structured output via --json-schema
  - headless execution via --permission-mode bypassPermissions
  - highest reasoning effort by default via --effort max
  - feedback handling via structured status=needs_feedback payloads
  - multi-turn refinement via --session-id / --resume
  - hard subprocess timeouts and budget caps
  - robust envelope parsing (always check is_error)

Note: `claude -p` / non-TTY mode skips workspace-trust prompts, and invalid
settings files can be silently ignored. The parent orchestrator must choose a
trusted cwd/sandbox and keep critical guardrails on the command line.

Requires: `claude` CLI on $PATH and Python 3.10+. If you enable `--bare`,
provide `ANTHROPIC_API_KEY` or an apiKeyHelper; desktop Claude Max / claude.ai
login works only for non-bare calls. See references/safety.md.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from typing import Any


class ClaudeError(RuntimeError):
    """Raised when claude reports is_error=True or the subprocess fails."""


EXECUTE_FEEDBACK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {"enum": ["completed", "needs_feedback", "blocked"]},
        "summary": {"type": "string"},
        "questions": {"type": "array", "items": {"type": "string"}},
        "changed_files": {"type": "array", "items": {"type": "string"}},
        "verification": {"type": "array", "items": {"type": "string"}},
        "next_steps": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["status", "summary"],
    "additionalProperties": False,
}


@dataclass
class ClaudeResult:
    """Parsed result from a `claude -p --output-format json` call."""
    text: str                       # raw text, or JSON dump of structured output
    parsed: Any | None              # json.loads(text) if a schema was used, else None
    session_id: str
    cost_usd: float
    num_turns: int
    permission_denials: list[dict[str, Any]] = field(default_factory=list)
    raw_envelope: dict[str, Any] = field(default_factory=dict)
    status: str | None = None
    questions: list[str] = field(default_factory=list)

    @property
    def needs_feedback(self) -> bool:
        return self.status == "needs_feedback"

    @property
    def blocked(self) -> bool:
        return self.status == "blocked"


def _run(cmd: list[str], stdin_data: str | None, timeout_s: int, cwd: str | None = None) -> dict[str, Any]:
    """Run claude and return the parsed JSON envelope. Raises on failure."""
    proc = subprocess.run(
        cmd,
        input=stdin_data,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        cwd=cwd,
    )
    if proc.returncode != 0:
        raise ClaudeError(
            f"claude exited {proc.returncode}: {proc.stderr.strip() or '(no stderr)'}"
        )
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise ClaudeError(f"could not parse claude stdout as JSON: {e}; stdout={proc.stdout[:500]!r}")
    if envelope.get("is_error"):
        raise ClaudeError(f"claude reported error: {envelope.get('result')}")
    return envelope


def _envelope_to_result(envelope: dict[str, Any], schema_used: bool) -> ClaudeResult:
    if schema_used:
        parsed = envelope.get("structured_output")
        if parsed is None:
            parsed = json.loads(envelope["result"])
        text = json.dumps(parsed, ensure_ascii=False)
    else:
        text = envelope["result"]
        parsed = None

    status = parsed.get("status") if isinstance(parsed, dict) else None
    questions = parsed.get("questions", []) if isinstance(parsed, dict) else []
    return ClaudeResult(
        text=text,
        parsed=parsed,
        session_id=envelope["session_id"],
        cost_usd=envelope.get("total_cost_usd", 0.0),
        num_turns=envelope.get("num_turns", 0),
        permission_denials=envelope.get("permission_denials", []),
        raw_envelope=envelope,
        status=status,
        questions=questions,
    )


def critique(
    text: str,
    *,
    role: str = "You are a code reviewer being called by an external agent.",
    schema: dict[str, Any] | None = None,
    model: str = "haiku",
    budget_usd: float = 0.05,
    timeout_s: int = 120,
    effort: str = "max",
    bare: bool | None = None,
    isolate_cwd: bool = True,
) -> ClaudeResult:
    """
    Pattern 1: read-only critique. No tools, no session persistence, cheap model.

    `schema` is a JSON Schema dict — if provided, the answer is taken from
    `.structured_output` on current Claude Code, with `.result` fallback for
    older builds (and ClaudeResult.parsed will be populated).

    bare=None means auto: use --bare only when ANTHROPIC_API_KEY is present.
    This avoids breaking desktop Claude Max / claude.ai auth, which --bare disables.
    isolate_cwd=True runs from an empty temp directory so non-bare calls do not
    inherit cwd/git dynamic context from the orchestrator repo.
    """
    if bare is None:
        bare = bool(os.environ.get("ANTHROPIC_API_KEY"))
    base_args = ["--no-session-persistence"]
    if bare:
        base_args.insert(0, "--bare")

    cmd = [
        "claude", "-p",
        *base_args,
        "--tools", "",
        "--permission-mode", "bypassPermissions",
        "--effort", effort,
        "--model", model,
        "--max-budget-usd", str(budget_usd),
        "--append-system-prompt", role,
        "--output-format", "json",
    ]
    if model != "haiku":
        cmd += ["--fallback-model", "haiku"]
    if schema is not None:
        cmd += ["--json-schema", json.dumps(schema)]
    cmd.append("Review the content on stdin and respond accordingly.")

    if isolate_cwd:
        with tempfile.TemporaryDirectory() as cwd:
            envelope = _run(cmd, stdin_data=text, timeout_s=timeout_s, cwd=cwd)
    else:
        envelope = _run(cmd, stdin_data=text, timeout_s=timeout_s)
    return _envelope_to_result(envelope, schema_used=schema is not None)


def execute(
    plan: str,
    *,
    allowed_tools: list[str] | None = None,
    role: str = "You are an executor agent invoked by an external planner. The plan is on stdin.",
    model: str = "sonnet",
    effort: str = "max",
    budget_usd: float = 20.0,
    timeout_s: int = 600,
    cwd: str | None = None,
    feedback_schema: dict[str, Any] | None = EXECUTE_FEEDBACK_SCHEMA,
) -> ClaudeResult:
    """
    Pattern 2: headless execution. Always uses bypassPermissions so Claude CLI
    never stalls on permission UI. The calling agent/cwd/sandbox is the safety
    gate. The session ID is generated up-front and returned in
    ClaudeResult.session_id so the caller can resume after user feedback.

    allowed_tools is now the `--tools` availability list, not a fine-grained
    Bash allowlist. Default: ["Edit", "Read", "Write", "Grep", "Glob", "Bash"].
    If feedback_schema is set, ClaudeResult.status/questions are populated;
    when result.needs_feedback is true, ask the user then resume the session.
    """
    session_id = str(uuid.uuid4())
    if allowed_tools is None:
        allowed_tools = ["Edit", "Read", "Write", "Grep", "Glob", "Bash"]
    cmd = [
        "claude", "-p",
        "--session-id", session_id,
        "--append-system-prompt", (
            role
            + "\nIf you need human feedback, credentials, external approval, or a scope decision, "
              "return status=needs_feedback with concise questions and stop."
        ),
        "--tools", *allowed_tools,
        "--permission-mode", "bypassPermissions",
        "--effort", effort,
        "--model", model,
        "--max-budget-usd", str(budget_usd),
        "--output-format", "json",
        "Execute the plan provided on stdin.",
    ]
    if feedback_schema is not None:
        cmd[-1:-1] = ["--json-schema", json.dumps(feedback_schema)]
    if model != "haiku":
        cmd[-1:-1] = ["--fallback-model", "haiku"]
    envelope = _run_with_cwd(cmd, stdin_data=plan, timeout_s=timeout_s, cwd=cwd)
    return _envelope_to_result(envelope, schema_used=feedback_schema is not None)


def _run_with_cwd(cmd: list[str], *, stdin_data: str | None, timeout_s: int, cwd: str | None):
    """Variant of _run that honors a cwd. Kept separate to keep _run minimal."""
    proc = subprocess.run(
        cmd, input=stdin_data, capture_output=True, text=True,
        timeout=timeout_s, cwd=cwd,
    )
    if proc.returncode != 0:
        raise ClaudeError(f"claude exited {proc.returncode}: {proc.stderr.strip() or '(no stderr)'}")
    envelope = json.loads(proc.stdout)
    if envelope.get("is_error"):
        raise ClaudeError(f"claude reported error: {envelope.get('result')}")
    return envelope


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
        effort: str = "max",
        budget_per_turn_usd: float = 0.20,
        timeout_s: int = 300,
        allowed_tools: list[str] | None = None,
        permission_mode: str = "bypassPermissions",
        session_id: str | None = None,
        resume_existing: bool = False,
        feedback_schema: dict[str, Any] | None = None,
    ) -> None:
        self.session_id = session_id or str(uuid.uuid4())
        self._role = (
            role
            + "\nIf you need human feedback, credentials, external approval, or a scope decision, "
              "return status=needs_feedback with concise questions and stop."
        )
        self._model = model
        self._effort = effort
        self._budget = budget_per_turn_usd
        self._timeout = timeout_s
        self._allowed_tools = allowed_tools or []
        self._permission_mode = permission_mode
        self._feedback_schema = feedback_schema
        self._first = not resume_existing

    def send(self, prompt: str) -> ClaudeResult:
        cmd = ["claude", "-p"]
        if self._first:
            cmd += ["--session-id", self.session_id]
            self._first = False
        else:
            cmd += ["--resume", self.session_id]
        cmd += [
            "--append-system-prompt", self._role,
            "--effort", self._effort,
            "--model", self._model,
            "--max-budget-usd", str(self._budget),
            "--output-format", "json",
            "--permission-mode", self._permission_mode,
        ]
        if self._allowed_tools:
            cmd += ["--tools", *self._allowed_tools]
        else:
            cmd += ["--tools", ""]
        if self._feedback_schema is not None:
            cmd += ["--json-schema", json.dumps(self._feedback_schema)]
        cmd.append(prompt)
        envelope = _run(cmd, stdin_data=None, timeout_s=self._timeout)
        return _envelope_to_result(envelope, schema_used=self._feedback_schema is not None)


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
    print(f"verdict: {r.parsed['verdict']}")
    print(f"reasons: {r.parsed['reasons']}")
    print(f"cost: ${r.cost_usd:.4f}, turns: {r.num_turns}, session: {r.session_id}")
