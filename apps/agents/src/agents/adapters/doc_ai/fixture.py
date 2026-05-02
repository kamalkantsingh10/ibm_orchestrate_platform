"""Fixture Doc-AI impl — deterministic, offline. Story 3.4 / AC #4.

The fixture path is the demo's reliability backbone: it never hits the
network, never depends on a PDF on disk, and produces deterministic
extractions keyed by filename.

Confidence band distribution (asserted in tests): across the 9 demo
filenames, at least one extraction lands in each of LOW, MEDIUM_LOW,
MEDIUM_HIGH, and HIGH so Story 3-7's ConfidencePill can demo all four
bands without staging.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from contracts.confidence import to_band
from contracts.document_intelligence import ExtractedField, FieldValue
from contracts.provenance import Provenance, ProvenancedField

from agents.jurisdictions.india import FieldSpec


@dataclass(frozen=True)
class _Stub:
    """A pre-baked extraction for a (document_ref, field_name) pair."""

    field_name: str
    value: FieldValue
    confidence: float


# Each filename maps to the list of fields the fixture will return.
# Confidences are intentionally varied to cover all 4 ConfidenceBand values.
_FIXTURE_EXTRACTIONS: dict[str, tuple[_Stub, ...]] = {
    "incorporation_certificate.pdf": (
        _Stub("company_name", "Vora Capital Holdings Pvt Ltd", 0.92),
        _Stub("cin", "U67120MH2024PTC444789", 0.95),
        _Stub("incorporation_date", "2024-08-22", 0.78),
        _Stub(
            "registered_address",
            "Suite 402, Sea Breeze Heights, Bandra West, Mumbai 400050",
            0.86,
        ),
    ),
    "pan_card.pdf": (
        _Stub("pan", "AAFCV1234R", 0.94),
        _Stub("name", "Vora Capital Holdings Pvt Ltd", 0.71),
    ),
    "address_proof.pdf": (
        _Stub(
            "address",
            "Suite 402, Sea Breeze Heights, Bandra West, Mumbai",
            0.78,
        ),
    ),
    "director_id.pdf": (
        _Stub("din", "08234567", 0.55),  # MEDIUM_LOW band
        _Stub("director_name", "Devansh Vora", 0.83),
    ),
    "ubo_declaration.pdf": (
        _Stub(
            "ubo_chain",
            "Vora Capital Holdings Pvt Ltd → Coastal Equity Partners Pte Ltd (SG) → Anchor Trust Services (BVI)",
            0.62,
        ),  # MEDIUM_LOW
    ),
    "shareholder_pattern.pdf": (
        _Stub(
            "shareholder_summary",
            "5 shareholders; majority Devansh Vora (62%), remaining 4 holding ≤15%.",
            0.50,
        ),  # MEDIUM_LOW
    ),
    "bank_statement_q1.pdf": (
        _Stub("account_holder_name", "Vora Capital Holdings Pvt Ltd", 0.81),
        _Stub("account_number", "0123456789012", 0.69),
    ),
    "aadhaar.pdf": (
        _Stub("aadhaar_last4", "4567", 0.30),  # LOW — fixture is honest about doubt
        _Stub("name", "Ananya Iyer", 0.88),
    ),
    "income_proof.pdf": (
        _Stub("annual_income_inr", 24_000_000, 0.66),  # MEDIUM_HIGH
    ),
}


class FixtureDocAILLM:
    """Offline doc-AI impl backed by the ``_FIXTURE_EXTRACTIONS`` table."""

    model_id: str = "fixture"

    async def extract(
        self,
        *,
        document_ref: str,
        text: str | None,  # ignored; fixture has no PDF dependency
        taxonomy: list[FieldSpec],
    ) -> list[ExtractedField]:
        stubs = _FIXTURE_EXTRACTIONS.get(document_ref)
        captured_at = datetime.now(UTC)

        if stubs is None:
            # Fallback: unknown filename. Surface a single low-confidence
            # raw_text field so the analyst's intake is non-empty.
            return [
                _build_field(
                    field_name="raw_text",
                    document_ref=document_ref,
                    value=None,
                    confidence=0.20,
                    captured_at=captured_at,
                )
            ]

        return [
            _build_field(
                field_name=stub.field_name,
                document_ref=document_ref,
                value=stub.value,
                confidence=stub.confidence,
                captured_at=captured_at,
            )
            for stub in stubs
        ]


def _build_field(
    *,
    field_name: str,
    document_ref: str,
    value: FieldValue,
    confidence: float,
    captured_at: datetime,
) -> ExtractedField:
    provenance = Provenance(
        source_agent="document_intelligence",
        source_system="fixture_doc_ai",
        confidence=confidence,
        confidence_band=to_band(confidence),
        evidence_ids=[],  # back-filled by Story 3-5 supervisor (AC8)
        captured_at=captured_at,
    )
    pf: ProvenancedField[FieldValue] = ProvenancedField(value=value, provenance=provenance)
    return ExtractedField(
        field_name=field_name,
        document_ref=document_ref,
        value=pf,
    )
