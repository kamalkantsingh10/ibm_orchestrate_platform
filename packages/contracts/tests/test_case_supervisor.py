"""Tests for CaseIntakeOutcome — Story 3.5 / AC #5."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from contracts.case_supervisor import CaseIntakeOutcome
from contracts.cases import VORA_CAPITAL_ID


def _now() -> datetime:
    return datetime.now(UTC)


def test_completed_outcome_round_trips() -> None:
    outcome = CaseIntakeOutcome(
        case_id=VORA_CAPITAL_ID,
        status="completed",
        agents_run=["document_intelligence"],
        fields_extracted=12,
        completed_at=_now(),
    )
    revived = CaseIntakeOutcome.model_validate_json(outcome.model_dump_json())
    assert revived == outcome


def test_blocked_outcome_round_trips() -> None:
    outcome = CaseIntakeOutcome(
        case_id=VORA_CAPITAL_ID,
        status="blocked",
        agents_run=["document_intelligence"],
        failed_agent="document_intelligence",
        error_message="bad input",
        completed_at=_now(),
    )
    revived = CaseIntakeOutcome.model_validate_json(outcome.model_dump_json())
    assert revived == outcome


def test_blocked_status_requires_failed_agent() -> None:
    with pytest.raises(ValidationError, match="failed_agent"):
        CaseIntakeOutcome(
            case_id=VORA_CAPITAL_ID,
            status="blocked",
            agents_run=[],
            failed_agent=None,
            completed_at=_now(),
        )


def test_completed_status_must_not_set_failed_agent() -> None:
    with pytest.raises(ValidationError, match="must not set failed_agent"):
        CaseIntakeOutcome(
            case_id=VORA_CAPITAL_ID,
            status="completed",
            failed_agent="document_intelligence",
            completed_at=_now(),
        )


def test_completed_at_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError):
        CaseIntakeOutcome(
            case_id=VORA_CAPITAL_ID,
            status="completed",
            completed_at=datetime(2026, 4, 30, 12, 0, 0),
        )


def test_fields_extracted_must_be_non_negative() -> None:
    with pytest.raises(ValidationError):
        CaseIntakeOutcome(
            case_id=VORA_CAPITAL_ID,
            status="completed",
            fields_extracted=-1,
            completed_at=_now(),
        )
