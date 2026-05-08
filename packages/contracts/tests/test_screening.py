"""Tests for Screening contracts — Story 6.1 / AC #9."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from contracts.cases import VORA_CAPITAL_ID
from contracts.confidence import ConfidenceBand, to_band
from contracts.provenance import Provenance, ProvenancedField
from contracts.screening import (
    ScreeningHit,
    ScreeningRequest,
    ScreeningSubject,
)


def _provenance(c: float = 0.73) -> Provenance:
    return Provenance(
        source_agent="screening",
        source_system="screening_mock",
        confidence=c,
        confidence_band=to_band(c),
        evidence_ids=[],
        captured_at=datetime.now(UTC),
    )


def _hit(score: float = 0.73, subject_id: str = "ubo_p_09876544") -> ScreeningHit:
    pf: ProvenancedField[float] = ProvenancedField(value=score, provenance=_provenance(score))
    return ScreeningHit(
        hit_id="hit_mock_abc123def456",
        subject_id=subject_id,
        matched_name="Patel R.",
        name_match_score=pf,
        date_of_birth=date(1961, 5, 12),
        categories=["sanctions"],
        source_lists=["OFAC SDN"],
    )


def test_request_rejects_empty_subjects() -> None:
    with pytest.raises(ValidationError):
        ScreeningRequest(case_id=VORA_CAPITAL_ID, subjects=[])


def test_request_rejects_too_many_subjects() -> None:
    subjects = [
        ScreeningSubject(
            subject_kind="director",
            subject_id=f"ubo_p_{i:08d}",
            full_name=f"Person {i}",
        )
        for i in range(51)
    ]
    with pytest.raises(ValidationError):
        ScreeningRequest(case_id=VORA_CAPITAL_ID, subjects=subjects)


def test_hit_rejects_empty_categories() -> None:
    pf: ProvenancedField[float] = ProvenancedField(value=0.7, provenance=_provenance(0.7))
    with pytest.raises(ValidationError):
        ScreeningHit(
            hit_id="hit_mock_x",
            subject_id="ubo_p_09876544",
            matched_name="X",
            name_match_score=pf,
            categories=[],
        )


def test_hit_disposition_defaults_to_open() -> None:
    hit = _hit()
    assert hit.disposition == "open"
    assert hit.dismissal_rationale is None


def test_hit_round_trips_through_json() -> None:
    hit = _hit(score=0.88)
    revived = ScreeningHit.model_validate_json(hit.model_dump_json())
    assert revived == hit
    assert revived.name_match_score.provenance.confidence_band == ConfidenceBand.HIGH


def test_subject_rejects_overlong_name() -> None:
    with pytest.raises(ValidationError):
        ScreeningSubject(
            subject_kind="director",
            subject_id="ubo_p_09876544",
            full_name="x" * 201,
        )


def test_request_round_trips() -> None:
    req = ScreeningRequest(
        case_id=VORA_CAPITAL_ID,
        subjects=[
            ScreeningSubject(
                subject_kind="director",
                subject_id="ubo_p_09876544",
                full_name="Rohan Mehta",
                date_of_birth=date(1978, 1, 1),
            )
        ],
    )
    revived = ScreeningRequest.model_validate_json(req.model_dump_json())
    assert revived == req


def test_hit_with_dismissal_rationale_round_trips() -> None:
    pf: ProvenancedField[float] = ProvenancedField(value=0.55, provenance=_provenance(0.55))
    hit = ScreeningHit(
        hit_id="hit_mock_low",
        subject_id="ubo_p_x",
        matched_name="Low Match",
        name_match_score=pf,
        categories=["sanctions"],
        disposition="dismissed_by_agent",
        dismissal_rationale="below 0.65 threshold",
    )
    revived = ScreeningHit.model_validate_json(hit.model_dump_json())
    assert revived == hit
    assert revived.dismissal_rationale == "below 0.65 threshold"
