"""Tests for `contracts.decision` — Story 7.7 / AC #12."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from contracts.cases import VORA_CAPITAL_ID, CaseState
from contracts.decision import (
    CommitDecisionRequest,
    CommitDecisionResponse,
    Decision,
    DecisionOutcome,
)


def test_commit_request_round_trip() -> None:
    body = CommitDecisionRequest(
        outcome=DecisionOutcome.APPROVE,
        conditions=[],
        rationale_html="<p>Approve based on screening hits.</p>",
    )
    parsed = CommitDecisionRequest.model_validate_json(body.model_dump_json())
    assert parsed == body


def test_commit_request_rejects_short_rationale() -> None:
    with pytest.raises(ValidationError):
        CommitDecisionRequest(
            outcome=DecisionOutcome.APPROVE,
            conditions=[],
            rationale_html="<p>x</p>",
        )


def test_approve_with_conditions_requires_conditions() -> None:
    with pytest.raises(ValidationError, match="approve_with_conditions"):
        CommitDecisionRequest(
            outcome=DecisionOutcome.APPROVE_WITH_CONDITIONS,
            conditions=[],
            rationale_html="<p>Approve with conditions, but no conditions supplied.</p>",
        )


def test_blank_condition_rejected() -> None:
    with pytest.raises(ValidationError):
        CommitDecisionRequest(
            outcome=DecisionOutcome.APPROVE_WITH_CONDITIONS,
            conditions=["   "],
            rationale_html="<p>Approve with conditions text long enough.</p>",
        )


def test_too_many_conditions_rejected() -> None:
    with pytest.raises(ValidationError):
        CommitDecisionRequest(
            outcome=DecisionOutcome.APPROVE_WITH_CONDITIONS,
            conditions=[f"c{i}" for i in range(11)],
            rationale_html="<p>Approve with conditions text long enough.</p>",
        )


def test_unknown_outcome_rejected() -> None:
    with pytest.raises(ValidationError):
        CommitDecisionRequest(
            outcome="bogus",  # type: ignore[arg-type]
            conditions=[],
            rationale_html="<p>Approve based on screening hits.</p>",
        )


def test_decision_round_trip_through_json() -> None:
    obj = Decision(
        decision_id="dec_test_1",
        case_id=VORA_CAPITAL_ID,
        outcome=DecisionOutcome.APPROVE,
        conditions=[],
        rationale_html="<p>Approve based on screening hits.</p>",
        committed_by_user_id="user_analyst",
        committed_at=datetime.now(UTC),
        committed_ledger_entry_id="led_01ABCDEFGHJKMNPQRSTVWXYZ12",
    )
    parsed = Decision.model_validate_json(obj.model_dump_json())
    assert parsed == obj


def test_commit_response_carries_pending_seal_state() -> None:
    obj = CommitDecisionResponse(
        case_id=VORA_CAPITAL_ID,
        decision_id="dec_x",
        case_state=CaseState.PENDING_SEAL,
        seal_at=datetime.now(UTC),
        ledger_entry_id="led_01ABCDEFGHJKMNPQRSTVWXYZ12",
    )
    assert obj.case_state == CaseState.PENDING_SEAL


# ───────────── Story 7.9 — DecisionOutcome StrEnum ─────────────


def test_decision_outcome_str_enum_string_equivalence() -> None:
    from contracts.decision import DecisionOutcome

    # StrEnum members are str subclasses; equality with the wire value
    # must hold (Pydantic relies on this to round-trip through JSON).
    assert DecisionOutcome.APPROVE.value == "approve"
    assert DecisionOutcome("approve") is DecisionOutcome.APPROVE
    assert DecisionOutcome("escalate_to_edd") is DecisionOutcome.ESCALATE_TO_EDD


def test_decision_outcome_rejects_unknown_value() -> None:
    from contracts.decision import DecisionOutcome

    with pytest.raises(ValueError):
        DecisionOutcome("foo")


def test_pydantic_serializes_outcome_as_lowercase_string() -> None:
    body = CommitDecisionRequest(
        outcome=DecisionOutcome.ESCALATE_TO_EDD,
        conditions=[],
        rationale_html="<p>Escalate the case to EDD for the layered UBO chain.</p>",
    )
    dump = body.model_dump_json()
    assert '"outcome":"escalate_to_edd"' in dump
    assert "ESCALATE_TO_EDD" not in dump


def test_pydantic_accepts_string_or_enum_member() -> None:
    from contracts.decision import DecisionOutcome

    # Pydantic v2 accepts either the wire string or the enum member
    # (both produce DecisionOutcome.APPROVE on the model).
    via_str = CommitDecisionRequest(
        outcome="approve",  # type: ignore[arg-type]
        conditions=[],
        rationale_html="<p>Approve based on screening hits.</p>",
    )
    via_enum = CommitDecisionRequest(
        outcome=DecisionOutcome.APPROVE,
        conditions=[],
        rationale_html="<p>Approve based on screening hits.</p>",
    )
    assert via_str.outcome == via_enum.outcome
    assert via_str.outcome == DecisionOutcome.APPROVE


def test_conditions_rejected_for_non_approve_with_conditions_outcome() -> None:
    """Story 7.9 / AC #8 — tightened validator: conditions must match outcome."""
    with pytest.raises(ValidationError, match="must not include conditions"):
        CommitDecisionRequest(
            outcome=DecisionOutcome.APPROVE,
            conditions=["enhanced monitoring 6mo"],
            rationale_html="<p>Approve based on screening hits.</p>",
        )
