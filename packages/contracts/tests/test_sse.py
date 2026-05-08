"""Tests for the SSE event contract — Story 4.6 / extended in Story 7.4."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts.sse import SseEvent


def test_decision_committed_event_round_trips() -> None:
    obj = SseEvent(
        event="decision.committed",
        data={"case_id": "case_01ABCDEFGHJKMNPQRSTVWXYZ12", "decision_id": "dec_test_123"},
    )
    parsed = SseEvent.model_validate_json(obj.model_dump_json())
    assert parsed.event == "decision.committed"
    assert parsed.data["decision_id"] == "dec_test_123"


def test_decision_sealed_event_round_trips() -> None:
    obj = SseEvent(
        event="decision.sealed",
        data={
            "case_id": "case_01ABCDEFGHJKMNPQRSTVWXYZ12",
            "decision_id": "dec_test_123",
            "ledger_entry_id": "led_01ABCDEFGHJKMNPQRSTVWXYZ12",
        },
    )
    parsed = SseEvent.model_validate_json(obj.model_dump_json())
    assert parsed.event == "decision.sealed"
    assert parsed.data["ledger_entry_id"].startswith("led_")


def test_decision_undone_event_round_trips() -> None:
    obj = SseEvent(
        event="decision.undone",
        data={
            "case_id": "case_01ABCDEFGHJKMNPQRSTVWXYZ12",
            "decision_id": "dec_test_123",
            "reason": "officer_changed_mind",
        },
    )
    parsed = SseEvent.model_validate_json(obj.model_dump_json())
    assert parsed.event == "decision.undone"
    assert parsed.data["reason"] == "officer_changed_mind"


def test_unknown_event_name_rejected() -> None:
    with pytest.raises(ValidationError):
        SseEvent(event="decision.bogus", data={})  # type: ignore[arg-type]
