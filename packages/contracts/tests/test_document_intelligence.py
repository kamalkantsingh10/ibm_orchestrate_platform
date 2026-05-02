"""Tests for DocumentIntelligence contracts — Story 3.4 / AC #1."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from contracts.cases import VORA_CAPITAL_ID
from contracts.confidence import ConfidenceBand, to_band
from contracts.document_intelligence import (
    DocumentIntelligenceInput,
    DocumentIntelligenceOutput,
    ExtractedField,
)
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


def _field(name: str = "company_name", ref: str = "incorporation_certificate.pdf") -> ExtractedField:
    pf: ProvenancedField[str | int | float | bool | None] = ProvenancedField(
        value="Vora Capital",
        provenance=_prov(),
    )
    return ExtractedField(
        field_name=name,
        document_ref=ref,
        value=pf,
    )


def test_input_round_trips() -> None:
    inp = DocumentIntelligenceInput(
        case_id=VORA_CAPITAL_ID,
        document_refs=["a.pdf", "b.pdf"],
    )
    revived = DocumentIntelligenceInput.model_validate_json(inp.model_dump_json())
    assert revived == inp


def test_input_rejects_empty_filename() -> None:
    with pytest.raises(ValidationError):
        DocumentIntelligenceInput(
            case_id=VORA_CAPITAL_ID,
            document_refs=[""],
        )


def test_output_round_trips_with_extracted_fields() -> None:
    out = DocumentIntelligenceOutput(
        case_id=VORA_CAPITAL_ID,
        extracted_fields=[_field(), _field("cin", "incorporation_certificate.pdf")],
    )
    revived = DocumentIntelligenceOutput.model_validate_json(out.model_dump_json())
    assert revived == out
    assert revived.extracted_fields[0].value.provenance.confidence_band == ConfidenceBand.HIGH


def test_output_with_empty_fields_allowed() -> None:
    out = DocumentIntelligenceOutput(case_id=VORA_CAPITAL_ID, extracted_fields=[])
    assert out.extracted_fields == []
