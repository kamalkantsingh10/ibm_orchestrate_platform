"""Ledger entry contract — Story 3.1 / Story 3.3.

The append-only ledger is the audit-trail backbone of the demo. Every agent
invocation, supervisor decision, and seeded fixture event lands as one
``LedgerEntry`` line in ``./data/ledger.jsonl``.

Demo simplification (2026-04-29 re-scope): the bank-buyer scope's hash-chain
+ Ed25519 signature primitives are absent. Append-only semantics are enforced
in Python via ``LedgerWriter``'s public surface — see
``cockpit_api.services.ledger_service``.

Story 3.3 upgraded ``payload`` from a plain ``dict`` to a discriminated union
with ``AgentActionLedgerEntry`` as the typed arm. Pydantic resolves the union
left-to-right (typed model first, dict fallback) so existing dict-shaped
seed-loader payloads continue to validate without change.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from contracts.agent_action import AgentActionLedgerEntry, ErrorInfo
from contracts.cases import CaseId

_CorrectionTag = Literal["real_ubo", "nominee", "director", "removed"]


class CockpitChatToolLedgerPayload(BaseModel):
    """Typed ``LedgerEntry.payload`` arm for cockpit_chat tool invocations.

    Story 6.7. Every tool call from the Cockpit Chat agent —
    `get_case`, `get_reasoning_trace`, `re_run_agent`, `query_ledger` —
    writes one of these. Architecture § P4 (tool calls ledgered) adapted
    for the demo's chat agent. Tool routes use the
    ``ledger_chat_tool_call`` async context manager (cockpit-api
    services/cockpit_chat_ledger.py) to record entries.
    """

    model_config = {"frozen": True}

    kind: Literal["cockpit_chat_tool"] = "cockpit_chat_tool"
    tool_name: Literal[
        "get_case",
        "get_reasoning_trace",
        "re_run_agent",
        "query_ledger",
    ]
    request_args: dict[str, Any] = Field(default_factory=dict)
    result_summary: str = Field(min_length=1, max_length=500)
    duration_ms: int = Field(ge=0)
    status: Literal["ok", "error"]
    error: ErrorInfo | None = None


class OfficerDecisionUndonePayload(BaseModel):
    """Typed ``LedgerEntry.payload`` arm for officer undo events.

    Story 7.5. Officer hits Undo on a pending_seal decision; we cancel
    Story 7.4's timer, revert the case to ``decision_ready``, and write
    one of these. The reason is required (≥ 40 chars) so the audit
    record carries the why; NFR-T6 carries through demo scope.
    """

    model_config = {"frozen": True}

    kind: Literal["officer_decision_undone"] = "officer_decision_undone"
    decision_id: str = Field(min_length=1)
    reason: str = Field(min_length=40, max_length=2000)


class OfficerDecisionCommittedPayload(BaseModel):
    """Typed ``LedgerEntry.payload`` arm for officer commits — Story 7.7.

    No Ed25519 signature: the bank-buyer scope's signing primitive is
    cut from the demo per the 2026-04-29 re-scope. The audit anchor is
    the ``rationale_hash`` (SHA-256 hex of the raw ``rationale_html``
    UTF-8 bytes); changing the rationale post-hoc would invalidate the
    hash without rewriting the ledger entry.
    """

    model_config = {"frozen": True}

    kind: Literal["officer_decision_committed"] = "officer_decision_committed"
    decision_id: str = Field(min_length=1)
    outcome: Literal["approve", "decline", "approve_with_conditions", "escalate_to_edd"]
    conditions: list[str] = Field(default_factory=list)
    rationale_hash: str = Field(min_length=64, max_length=64)


class DecisionSealedPayload(BaseModel):
    """Typed ``LedgerEntry.payload`` arm for the SYSTEM-emitted seal —
    Story 7.7. Written by ``decision_service.seal_decision`` when
    Story 7.4's timer elapses; ``actor_type`` is ``SYSTEM`` and
    ``actor_id`` is ``platform``. Distinct from agent / officer entries.
    """

    model_config = {"frozen": True}

    kind: Literal["decision_sealed"] = "decision_sealed"
    decision_id: str = Field(min_length=1)
    outcome: Literal["approve", "decline", "approve_with_conditions", "escalate_to_edd"]


class LearningEventLedgerPayload(BaseModel):
    """Typed ``LedgerEntry.payload`` arm for officer-originated UBO corrections.

    Story 5.5. Lives here (not in ``contracts.learning_event``) to avoid a
    circular import between ledger ↔ ubo ↔ provenance ↔ ledger. Node-id
    fields are typed as plain ``str`` here; pattern validation happened
    upstream at ``LearningEventInput``.
    """

    model_config = {"frozen": True}

    kind: Literal["learning_event"] = "learning_event"
    edge_kind: Literal["owns", "director", "beneficial"]
    from_id: str = Field(min_length=1)
    original_to_id: str = Field(min_length=1)
    new_to_id: str = Field(min_length=1)
    correction_tag: _CorrectionTag
    evidence_note: str
    opt_in_for_retraining: bool


# ───────────────────────────── identifier ──────────────────────────────────

# Crockford-Base32 excludes I, L, O, U. ULID body is 26 chars. Mirror of the
# CaseId pattern from Story 2.1 with a different prefix.
_LEDGER_ID_PATTERN = r"^led_[0-9A-HJKMNP-TV-Z]{26}$"

LedgerEntryId = Annotated[
    str,
    StringConstraints(pattern=_LEDGER_ID_PATTERN, min_length=30, max_length=30),
]
"""``led_<26-char Crockford-Base32 ULID>``."""

_ledger_id_re = re.compile(_LEDGER_ID_PATTERN)


def is_valid_ledger_entry_id(value: str) -> bool:
    """Return True if ``value`` matches the ``led_<ULID>`` shape."""
    return bool(_ledger_id_re.match(value))


# ───────────────────────────── actor type ──────────────────────────────────


class ActorType(StrEnum):
    """Who originated the ledger entry. See architecture.md § P4."""

    AGENT = "agent"
    OFFICER = "officer"
    SYSTEM = "system"


# ───────────────────────────── ledger entry ────────────────────────────────


class LedgerEntry(BaseModel):
    """One append-only ledger event.

    The writer overwrites ``id`` and ``recorded_at`` server-side at
    ``append`` time, so caller-supplied values are ignored. Pass any
    pattern-valid ID and any tz-aware ``datetime`` — they will be replaced.
    """

    model_config = {"frozen": True, "use_enum_values": False}

    id: LedgerEntryId
    actor_type: ActorType
    actor_id: str = Field(min_length=1)
    case_id: CaseId | None = None
    action: str = Field(min_length=1, max_length=80)
    # Discriminated union (Stories 3.3 + 5.5 + 6.4): typed arms first, then
    # plain dict fallback. ``union_mode="left_to_right"`` forces Pydantic to
    # try the typed arms first and only fall through to the dict on a real
    # validation error — Pydantic v2's default "smart" mode loses the tiebreak
    # to ``dict[str, Any]`` once the typed payload grows nested fields like
    # ``reasoning_trace`` (Story 6.4).
    payload: (
        AgentActionLedgerEntry
        | CockpitChatToolLedgerPayload
        | LearningEventLedgerPayload
        | OfficerDecisionUndonePayload
        | OfficerDecisionCommittedPayload
        | DecisionSealedPayload
        | dict[str, Any]
    ) = Field(default_factory=dict, union_mode="left_to_right")
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def _recorded_at_must_be_tz_aware(cls, value: datetime) -> datetime:
        """Reject naive datetimes — wire format requires explicit UTC."""
        if value.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware (UTC)")
        return value
