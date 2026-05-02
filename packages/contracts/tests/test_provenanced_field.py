"""Tests for ProvenancedField[T] generic — Story 3.3 / AC #8."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from contracts.confidence import to_band
from contracts.provenance import Provenance, ProvenancedField


def _prov(c: float = 0.91) -> Provenance:
    return Provenance(
        source_agent="document_intelligence",
        source_system="fixture_doc_ai",
        confidence=c,
        confidence_band=to_band(c),
        evidence_ids=[],
        captured_at=datetime.now(UTC),
    )


# ───────────── round-trip across multiple T ─────────────


@pytest.mark.parametrize(
    ("value", "type_"),
    [
        ("Vora Capital Holdings Pvt Ltd", str),
        (42, int),
        (3.14, float),
        (True, bool),
        (["a", "b", "c"], list[str]),
        ({"k": "v", "n": 1}, dict[str, Any]),
        (datetime(2026, 4, 30, tzinfo=UTC), datetime),
    ],
)
def test_provenanced_field_round_trips(value: Any, type_: type) -> None:
    pf: Any = ProvenancedField[type_](value=value, provenance=_prov())  # type: ignore[valid-type]
    payload = pf.model_dump_json()
    revived = ProvenancedField[type_].model_validate_json(payload)  # type: ignore[valid-type]
    assert revived.value == value
    assert revived.provenance == pf.provenance


def test_provenanced_field_optional_str() -> None:
    pf: ProvenancedField[str | None] = ProvenancedField[str | None](value=None, provenance=_prov())
    revived = ProvenancedField[str | None].model_validate_json(pf.model_dump_json())
    assert revived.value is None
