"""Decision contracts — Story 7.7 (refined by Story 7.9).

Owns the persistence-shaped ``Decision`` plus the request/response
shapes for ``POST /v1/cases/{case_id}/decisions``. Story 7.9 promoted
``DecisionOutcome`` from a ``Literal`` to a ``StrEnum``; the wire
format is unchanged (lowercase snake_case strings) — Pydantic v2
serializes ``StrEnum`` by value natively.

Naming: enum members are UPPERCASE (Python convention); wire values
are lowercase snake_case (architecture § Format Patterns). Tests
verify both forms validate cleanly under Pydantic.

The bank-buyer scope had Ed25519 signing on commit; the demo cuts
that — officer identity is the session user, the audit anchor is the
typed ``OfficerDecisionCommittedPayload`` ledger entry containing a
SHA-256 hash of ``rationale_html``. See ``architecture.md`` § Demo
Scope Addendum (2026-04-29).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from contracts.cases import CaseId, CaseState
from contracts.ledger import LedgerEntryId


class DecisionOutcome(StrEnum):
    """The four mutually-exclusive decision outcomes — Story 7.9 / AC #1.

    Story 7.7 declared this as a ``Literal``; promoting to ``StrEnum``
    keeps the wire format identical (Pydantic v2 serializes by value)
    and lets Python callers reach for ``DecisionOutcome.APPROVE``
    instead of stringly-typed literals.
    """

    APPROVE = "approve"
    DECLINE = "decline"
    APPROVE_WITH_CONDITIONS = "approve_with_conditions"
    ESCALATE_TO_EDD = "escalate_to_edd"


class CommitDecisionRequest(BaseModel):
    """POST body for ``/v1/cases/{case_id}/decisions``."""

    model_config = {"frozen": True}

    outcome: DecisionOutcome
    conditions: list[str] = Field(default_factory=list, max_length=10)
    rationale_html: str = Field(min_length=20, max_length=20_000)

    @model_validator(mode="after")
    def _validate_conditions_against_outcome(self) -> CommitDecisionRequest:
        # Story 7.9 / AC #8 — conditions must match outcome exclusively.
        if self.outcome == DecisionOutcome.APPROVE_WITH_CONDITIONS and not self.conditions:
            raise ValueError("approve_with_conditions requires at least one condition")
        if self.outcome != DecisionOutcome.APPROVE_WITH_CONDITIONS and self.conditions:
            raise ValueError(
                f"{self.outcome.value!r} must not include conditions; only approve_with_conditions accepts them"
            )
        for c in self.conditions:
            stripped = c.strip()
            if not stripped:
                raise ValueError("each condition must be non-blank")
            if len(c) > 200:
                raise ValueError("each condition must be ≤ 200 chars")
        return self


class CommitDecisionResponse(BaseModel):
    """201 response shape for ``POST /v1/cases/{case_id}/decisions``."""

    model_config = {"frozen": True}

    case_id: CaseId
    decision_id: str = Field(min_length=1)
    case_state: CaseState
    seal_at: datetime
    ledger_entry_id: LedgerEntryId


class Decision(BaseModel):
    """Persistence-shaped record. One row per (case_id, commit attempt)."""

    model_config = {"frozen": True}

    decision_id: str = Field(min_length=1)
    case_id: CaseId
    outcome: DecisionOutcome
    conditions: list[str] = Field(default_factory=list)
    rationale_html: str
    committed_by_user_id: str = Field(min_length=1)
    committed_at: datetime
    sealed_at: datetime | None = None
    sealed_ledger_entry_id: LedgerEntryId | None = None
    committed_ledger_entry_id: LedgerEntryId
