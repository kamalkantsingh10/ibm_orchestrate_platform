"""Tests for Provenance — Story 3.3 / AC #1, #3, #8."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError
from ulid import ULID

from contracts.confidence import ConfidenceBand, to_band
from contracts.provenance import Provenance


def _now() -> datetime:
    return datetime.now(UTC)


def _ledger_id() -> str:
    return f"led_{ULID()!s}"


def _make(**overrides: Any) -> Provenance:
    confidence = float(overrides.pop("confidence", 0.91))
    band = overrides.pop("confidence_band", to_band(confidence))
    defaults: dict[str, Any] = {
        "source_agent": "document_intelligence",
        "source_system": "fixture_doc_ai",
        "confidence": confidence,
        "confidence_band": band,
        "evidence_ids": [],
        "captured_at": _now(),
    }
    defaults.update(overrides)
    return Provenance(**defaults)


# ───────────── round-trip ─────────────


def test_provenance_round_trips_through_json() -> None:
    p = _make(evidence_ids=[_ledger_id(), _ledger_id()], confidence=0.72)
    revived = Provenance.model_validate_json(p.model_dump_json())
    assert revived == p


# ───────────── confidence range ─────────────


@pytest.mark.parametrize("bad", [-0.01, 1.01])
def test_confidence_out_of_range_raises(bad: float) -> None:
    with pytest.raises(ValidationError):
        Provenance(
            source_agent="x",
            source_system="y",
            confidence=bad,
            confidence_band=ConfidenceBand.LOW,
            evidence_ids=[],
            captured_at=_now(),
        )


# ───────────── evidence_ids validation ─────────────


def test_evidence_ids_accept_valid_ledger_ids() -> None:
    p = _make(evidence_ids=[_ledger_id()])
    assert len(p.evidence_ids) == 1


def test_evidence_ids_reject_invalid_format() -> None:
    with pytest.raises(ValidationError):
        _make(evidence_ids=["not-a-led-id"])


def test_evidence_ids_empty_list_allowed() -> None:
    p = _make(evidence_ids=[])
    assert p.evidence_ids == []


# ───────────── band-vs-confidence consistency ─────────────


@pytest.mark.parametrize(
    ("confidence", "wrong_band"),
    [
        (0.62, ConfidenceBand.HIGH),
        (0.30, ConfidenceBand.MEDIUM_HIGH),
        (0.95, ConfidenceBand.LOW),
        (0.50, ConfidenceBand.HIGH),
    ],
)
def test_inconsistent_band_raises(confidence: float, wrong_band: ConfidenceBand) -> None:
    with pytest.raises(ValidationError, match="inconsistent"):
        _make(confidence=confidence, confidence_band=wrong_band)


@pytest.mark.parametrize("confidence", [0.0, 0.39, 0.40, 0.64, 0.65, 0.84, 0.85, 1.0])
def test_consistent_band_accepted(confidence: float) -> None:
    p = _make(confidence=confidence, confidence_band=to_band(confidence))
    assert p.confidence_band == to_band(confidence)


# ───────────── captured_at tz-awareness ─────────────


def test_captured_at_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError):
        _make(captured_at=datetime(2026, 4, 30, 12, 0, 0))
