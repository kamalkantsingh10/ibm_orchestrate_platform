"""Typed agent-action ledger payload — Story 3.3.

``AgentActionLedgerEntry`` is the typed shape that ``LedgerEntry.payload``
takes when an agent invocation is recorded. The bank-buyer scope's
``prev_hash``/``chain_hash``/``platform_signature`` fields are absent (no
hash chain or signing in the demo).

The ``kind`` literal is the discriminator that lets ``LedgerEntry``'s
``payload`` union round-trip cleanly between the typed arm and the plain
``dict`` fallback.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from contracts.reasoning_trace import ReasoningTrace


class ErrorInfo(BaseModel):
    """Error metadata recorded on failure-path agent actions."""

    model_config = {"frozen": True}

    type: str = Field(min_length=1)
    message: str = Field(max_length=500)


PromptHash = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
"""SHA-256 hex digest, lowercase. Used by Story 3.4's watsonx prompt hashing."""


class AgentActionLedgerEntry(BaseModel):
    """Typed payload for ``agent.completed``/``agent.failed`` ledger entries."""

    model_config = {"frozen": True, "use_enum_values": False}

    kind: Literal["agent_action"] = "agent_action"
    agent_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1, default="stub")
    prompt_template_id: str | None = None
    prompt_hash: PromptHash | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    input: dict[str, Any]
    output: dict[str, Any] | None = None
    started_at: datetime
    completed_at: datetime
    duration_ms: int = Field(ge=0)
    status: Literal["ok", "error"]
    error: ErrorInfo | None = None
    # Story 6.4 — optional 4-section reasoning trace. None when the agent
    # didn't attach one; required-shape (all four sections min-length 12)
    # when present.
    reasoning_trace: ReasoningTrace | None = None

    @field_validator("started_at", "completed_at")
    @classmethod
    def _timestamps_must_be_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("agent action timestamps must be timezone-aware (UTC)")
        return value
