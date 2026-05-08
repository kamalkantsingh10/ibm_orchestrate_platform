"""Tests for ReasoningTrace contracts — Story 6.4 / AC #9."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from contracts.agent_action import AgentActionLedgerEntry
from contracts.confidence import ConfidenceBand, to_band
from contracts.reasoning_trace import (
    ConfidenceWithRationale,
    IncompleteReasoningTraceError,
    ReasoningTrace,
)


def _conf(value: float = 0.85, rationale: str = "Mean of 3 hit scores; clean signal.") -> ConfidenceWithRationale:
    return ConfidenceWithRationale(value=value, rationale=rationale, band=to_band(value))


def _trace() -> ReasoningTrace:
    return ReasoningTrace(
        what_searched="Screened 3 subjects against the configured screening provider.",
        what_hit="Returned 1 match: Patel R. (sanctions) at score 0.73.",
        confidence_self_rating=_conf(),
        counterfactual="Disposition would change if officer DOB confirms a different person.",
    )


def test_trace_round_trips() -> None:
    t = _trace()
    revived = ReasoningTrace.model_validate_json(t.model_dump_json())
    assert revived == t


def test_what_searched_too_short_raises() -> None:
    with pytest.raises(ValidationError):
        ReasoningTrace(
            what_searched="short",
            what_hit="long enough now",
            confidence_self_rating=_conf(),
            counterfactual="long enough now",
        )


def test_what_hit_too_short_raises() -> None:
    with pytest.raises(ValidationError):
        ReasoningTrace(
            what_searched="long enough now",
            what_hit="short",
            confidence_self_rating=_conf(),
            counterfactual="long enough now",
        )


def test_counterfactual_too_short_raises() -> None:
    with pytest.raises(ValidationError):
        ReasoningTrace(
            what_searched="long enough now",
            what_hit="long enough now",
            confidence_self_rating=_conf(),
            counterfactual="n/a",
        )


def test_confidence_rationale_too_short_raises() -> None:
    with pytest.raises(ValidationError):
        ConfidenceWithRationale(value=0.5, rationale="ok", band=ConfidenceBand.MEDIUM_LOW)


def test_confidence_value_out_of_range_raises() -> None:
    with pytest.raises(ValidationError):
        ConfidenceWithRationale(value=1.5, rationale="x" * 12, band=ConfidenceBand.HIGH)


def test_confidence_band_must_match_value() -> None:
    with pytest.raises(ValidationError):
        ConfidenceWithRationale(value=0.9, rationale="x" * 12, band=ConfidenceBand.LOW)


def test_confidence_with_rationale_round_trips() -> None:
    c = _conf()
    revived = ConfidenceWithRationale.model_validate_json(c.model_dump_json())
    assert revived == c


def _entry(reasoning_trace: ReasoningTrace | None) -> AgentActionLedgerEntry:
    return AgentActionLedgerEntry(
        agent_id="screening",
        input={"x": 1},
        output={"y": 2},
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        duration_ms=42,
        status="ok",
        reasoning_trace=reasoning_trace,
    )


def test_agent_action_default_trace_is_none() -> None:
    e = _entry(None)
    revived = AgentActionLedgerEntry.model_validate_json(e.model_dump_json())
    assert revived.reasoning_trace is None


def test_agent_action_with_trace_round_trips() -> None:
    e = _entry(_trace())
    revived = AgentActionLedgerEntry.model_validate_json(e.model_dump_json())
    assert revived.reasoning_trace == _trace()


def test_legacy_entry_without_reasoning_trace_field_loads() -> None:
    """Backward compat — old JSONL rows lacking reasoning_trace must validate."""
    legacy_json = (
        '{"kind": "agent_action", "agent_id": "document_intelligence", '
        '"model_id": "fixture", "input": {}, "output": {}, '
        f'"started_at": "{datetime.now(UTC).isoformat()}", '
        f'"completed_at": "{datetime.now(UTC).isoformat()}", '
        '"duration_ms": 10, "status": "ok"}'
    )
    revived = AgentActionLedgerEntry.model_validate_json(legacy_json)
    assert revived.reasoning_trace is None


def test_incomplete_reasoning_trace_error_message_lists_failing_sections() -> None:
    err = IncompleteReasoningTraceError(
        agent_id="screening",
        errors=[
            {"loc": ("what_searched",), "msg": "too short", "type": "value_error"},
            {"loc": ("what_hit",), "msg": "too short", "type": "value_error"},
        ],
    )
    assert "screening" in str(err)
    assert "what_searched" in str(err)
    assert "what_hit" in str(err)
