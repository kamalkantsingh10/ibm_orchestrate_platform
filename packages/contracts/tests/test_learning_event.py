"""Tests for learning-event contracts — Story 5.5 / AC #1, #2, #14."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from contracts.cases import VORA_CAPITAL_ID
from contracts.learning_event import (
    LearningEventInput,
    LearningEventLedgerPayload,
    LearningEventResponse,
)
from contracts.ledger import ActorType, LedgerEntry

VORA_ROOT = "ubo_e_u67120mh2024ptc444789"
COASTAL = "ubo_e_coastal_equity_partners_pte_ltd"


def test_input_round_trips() -> None:
    inp = LearningEventInput(
        edge_kind="owns",
        from_id=COASTAL,
        original_to_id=VORA_ROOT,
        new_to_id=VORA_ROOT,
        correction_tag="real_ubo",
        evidence_note="RM email 2024-11 disclosed offshore family trust",
        opt_in_for_retraining=True,
    )
    revived = LearningEventInput.model_validate_json(inp.model_dump_json())
    assert revived == inp


def test_input_rejects_empty_evidence_note() -> None:
    with pytest.raises(ValidationError):
        LearningEventInput(
            edge_kind="owns",
            from_id=COASTAL,
            original_to_id=VORA_ROOT,
            new_to_id=VORA_ROOT,
            correction_tag="real_ubo",
            evidence_note="",
            opt_in_for_retraining=False,
        )


def test_input_rejects_evidence_note_over_500_chars() -> None:
    with pytest.raises(ValidationError):
        LearningEventInput(
            edge_kind="owns",
            from_id=COASTAL,
            original_to_id=VORA_ROOT,
            new_to_id=VORA_ROOT,
            correction_tag="real_ubo",
            evidence_note="x" * 501,
            opt_in_for_retraining=False,
        )


def test_input_rejects_invalid_node_id_pattern() -> None:
    with pytest.raises(ValidationError):
        LearningEventInput(
            edge_kind="owns",
            from_id="not-a-ubo-id",
            original_to_id=VORA_ROOT,
            new_to_id=VORA_ROOT,
            correction_tag="real_ubo",
            evidence_note="test",
            opt_in_for_retraining=False,
        )


def test_response_round_trips() -> None:
    resp = LearningEventResponse(
        ledger_entry_id="led_01KR2AJKNXSCYKYYBQ3FFS3PNC",
        case_id=VORA_CAPITAL_ID,
        recorded_at=datetime.now(UTC),
    )
    revived = LearningEventResponse.model_validate_json(resp.model_dump_json())
    assert revived == resp


def test_payload_round_trips_in_ledger_entry() -> None:
    """LedgerEntry.payload union includes LearningEventLedgerPayload (Story 5.5 AC2)."""
    payload = LearningEventLedgerPayload(
        edge_kind="owns",
        from_id=COASTAL,
        original_to_id=VORA_ROOT,
        new_to_id=VORA_ROOT,
        correction_tag="real_ubo",
        evidence_note="test",
        opt_in_for_retraining=True,
    )
    entry = LedgerEntry(
        id="led_01KR2AJKNXSCYKYYBQ3FFS3PNC",
        actor_type=ActorType.OFFICER,
        actor_id="user_analyst",
        case_id=VORA_CAPITAL_ID,
        action="ubo.edge_corrected",
        payload=payload,
        recorded_at=datetime.now(UTC),
    )
    revived = LedgerEntry.model_validate_json(entry.model_dump_json())
    assert isinstance(revived.payload, LearningEventLedgerPayload)
    assert revived.payload.correction_tag == "real_ubo"
    assert revived.payload.kind == "learning_event"


def test_dict_payload_still_validates() -> None:
    """Backward-compat: dict-shaped payloads (system events) still validate."""
    entry = LedgerEntry(
        id="led_01KR2AJKNXSCYKYYBQ3FFS3PNC",
        actor_type=ActorType.SYSTEM,
        actor_id="case_supervisor",
        case_id=VORA_CAPITAL_ID,
        action="case.intake_completed",
        payload={"agents": ["document_intelligence"], "fields_extracted": 9},
        recorded_at=datetime.now(UTC),
    )
    revived = LedgerEntry.model_validate_json(entry.model_dump_json())
    assert isinstance(revived.payload, dict)
    assert revived.payload["agents"] == ["document_intelligence"]
