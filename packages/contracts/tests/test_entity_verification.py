"""Tests for EntityVerification contracts — Story 5.1 / AC #1, #13."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from contracts.cases import VORA_CAPITAL_ID
from contracts.confidence import ConfidenceBand, to_band
from contracts.entity_verification import (
    EntityVerificationInput,
    EntityVerificationResult,
    FieldMismatch,
)
from contracts.mca import MCAStatus
from contracts.provenance import Provenance, ProvenancedField

VORA_CIN = "U67120MH2024PTC444789"


def _provenance(c: float = 0.95) -> Provenance:
    return Provenance(
        source_agent="entity_verification",
        source_system="mca_mock",
        confidence=c,
        confidence_band=to_band(c),
        evidence_ids=[],
        captured_at=datetime.now(UTC),
    )


def test_input_round_trips() -> None:
    inp = EntityVerificationInput(case_id=VORA_CAPITAL_ID, cin=VORA_CIN)
    assert EntityVerificationInput.model_validate_json(inp.model_dump_json()) == inp


def test_input_rejects_invalid_cin() -> None:
    with pytest.raises(ValidationError):
        EntityVerificationInput(case_id=VORA_CAPITAL_ID, cin="not-a-cin")


def test_result_round_trips_with_provenanced_status() -> None:
    pf: ProvenancedField[MCAStatus] = ProvenancedField(value="active", provenance=_provenance())
    result = EntityVerificationResult(
        case_id=VORA_CAPITAL_ID,
        cin=VORA_CIN,
        mca_status=pf,
        mismatches=[],
    )
    revived = EntityVerificationResult.model_validate_json(result.model_dump_json())
    assert revived == result
    assert revived.mca_status.provenance.confidence_band == ConfidenceBand.HIGH


def test_result_round_trips_with_mismatches() -> None:
    pf: ProvenancedField[MCAStatus] = ProvenancedField(value="active", provenance=_provenance())
    result = EntityVerificationResult(
        case_id=VORA_CAPITAL_ID,
        cin=VORA_CIN,
        mca_status=pf,
        mismatches=[
            FieldMismatch(
                field_name="company_name",
                case_value="Vora Capital",
                mca_value="Vora Capital Holdings Pvt Ltd",
                severity="warning",
            ),
            FieldMismatch(
                field_name="incorporation_date",
                case_value="2024-08-22",
                mca_value="2024-09-01",
                severity="critical",
                notes="date drift",
            ),
        ],
    )
    revived = EntityVerificationResult.model_validate_json(result.model_dump_json())
    assert revived == result
    assert revived.mismatches[1].severity == "critical"


def test_field_mismatch_defaults() -> None:
    fm = FieldMismatch(field_name="company_name")
    assert fm.severity == "warning"
    assert fm.case_value is None
    assert fm.mca_value is None


def test_result_rejects_invalid_status_literal() -> None:
    """Pydantic re-validates the inner Literal at the result level."""
    with pytest.raises(ValidationError):
        EntityVerificationResult.model_validate(
            {
                "case_id": VORA_CAPITAL_ID,
                "cin": VORA_CIN,
                "mca_status": {
                    "value": "not_a_status",
                    "provenance": _provenance().model_dump(mode="json"),
                },
                "mismatches": [],
            }
        )
