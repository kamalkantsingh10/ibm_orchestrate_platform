"""Tests for risk-scoring contracts — Story 5.6 / AC #1, #12."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from contracts.cases import VORA_CAPITAL_ID
from contracts.confidence import to_band
from contracts.provenance import Provenance, ProvenancedField
from contracts.risk import (
    RiskComponent,
    RiskScore,
    band_for_total,
)


def _score_provenance(total: int) -> ProvenancedField[float]:
    confidence = 0.85
    prov = Provenance(
        source_agent="risk_scoring",
        source_system="deterministic",
        confidence=confidence,
        confidence_band=to_band(confidence),
        evidence_ids=[],
        captured_at=datetime.now(UTC),
    )
    return ProvenancedField(value=total / 100.0, provenance=prov)


_BASE_COMPONENTS = [
    RiskComponent(name="country", value=10.0, weight=0.15, contribution=1.5, rationale="IN"),
    RiskComponent(
        name="entity_type",
        value=70.0,
        weight=0.20,
        contribution=14.0,
        rationale="company foreign holders",
    ),
    RiskComponent(
        name="ownership_clarity",
        value=70.0,
        weight=0.30,
        contribution=21.0,
        rationale="3 nominee_suspected edges",
    ),
    RiskComponent(name="screening", value=0.0, weight=0.20, contribution=0.0, rationale="No hit"),
    RiskComponent(
        name="adverse_media",
        value=0.0,
        weight=0.15,
        contribution=0.0,
        rationale="No adverse media signal",
    ),
]


def test_band_for_total_thresholds() -> None:
    assert band_for_total(0) == "low"
    assert band_for_total(34) == "low"
    assert band_for_total(35) == "medium"
    assert band_for_total(69) == "medium"
    assert band_for_total(70) == "high"
    assert band_for_total(100) == "high"


def test_score_round_trips() -> None:
    score = RiskScore(
        case_id=VORA_CAPITAL_ID,
        total=37,
        band="medium",
        components=_BASE_COMPONENTS,
        score_provenance=_score_provenance(37),
    )
    revived = RiskScore.model_validate_json(score.model_dump_json())
    assert revived == score


def test_validator_rejects_weights_not_summing_to_one() -> None:
    bad = [
        RiskComponent(name="country", value=10.0, weight=0.5, contribution=5.0, rationale="x"),
        RiskComponent(name="entity_type", value=10.0, weight=0.4, contribution=4.0, rationale="x"),
        # sum = 0.9, off by 0.1
    ]
    with pytest.raises(ValidationError):
        RiskScore(
            case_id=VORA_CAPITAL_ID,
            total=9,
            band="low",
            components=bad,
            score_provenance=_score_provenance(9),
        )


def test_validator_rejects_band_mismatch() -> None:
    with pytest.raises(ValidationError):
        RiskScore(
            case_id=VORA_CAPITAL_ID,
            total=10,
            band="medium",  # mismatch — total=10 should be low
            components=_BASE_COMPONENTS,
            score_provenance=_score_provenance(10),
        )


def test_validator_rejects_total_diverging_from_contributions() -> None:
    with pytest.raises(ValidationError):
        RiskScore(
            case_id=VORA_CAPITAL_ID,
            total=80,  # contributions sum to ~36.5
            band="high",
            components=_BASE_COMPONENTS,
            score_provenance=_score_provenance(80),
        )


def test_validator_rejects_inconsistent_score_provenance_value() -> None:
    bad_prov = ProvenancedField(
        value=0.99,  # inconsistent with total=37 (expects 0.37)
        provenance=Provenance(
            source_agent="risk_scoring",
            source_system="deterministic",
            confidence=0.85,
            confidence_band=to_band(0.85),
            evidence_ids=[],
            captured_at=datetime.now(UTC),
        ),
    )
    with pytest.raises(ValidationError):
        RiskScore(
            case_id=VORA_CAPITAL_ID,
            total=37,
            band="medium",
            components=_BASE_COMPONENTS,
            score_provenance=bad_prov,
        )


def test_component_rejects_overshooting_value() -> None:
    with pytest.raises(ValidationError):
        RiskComponent(name="country", value=101.0, weight=0.15, contribution=15.15, rationale="x")
