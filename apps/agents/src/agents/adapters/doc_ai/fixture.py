"""Fixture Doc-AI impl — deterministic, offline. Story 3.4 / AC #4.

The fixture path is the demo's reliability backbone: it never hits the
network. Two modes:

* **Smart mode** (``text`` is provided): the per-case PDF templates
  (Story 4 hardening — see ``tools/scripts/generate_sample_pdfs.py``)
  carry case-correct labels like ``Name: Ananya Iyer``,
  ``PAN: AAFPI4567Q``. The fixture runs lightweight regex against the
  PDF text and returns case-correct ExtractedFields. No LLM call, no
  pre-baked stubs leaking other cases' data.

* **Stub mode** (``text`` is ``None`` or unparseable): falls back to the
  static ``_FIXTURE_EXTRACTIONS`` map. This keeps the existing offline
  test suite working without per-case PDFs on disk and provides
  graceful degradation when the regex fails to find a label (e.g. a
  document the templates don't model yet).

Confidence band distribution (asserted in tests): across the 9 demo
filenames, at least one extraction lands in each of LOW, MEDIUM_LOW,
MEDIUM_HIGH, and HIGH so Story 3-7's ConfidencePill can demo all four
bands without staging.
"""

from __future__ import annotations

import re
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


# Each filename maps to the list of fields the fixture will return when no
# PDF text is supplied. Confidences are intentionally varied to cover all 4
# ConfidenceBand values.
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


# ───────────────────────── smart-mode regex registry ────────────────────────
#
# Each taxonomy field maps to a list of label patterns the per-case PDF
# template uses (see ``tools/scripts/generate_sample_pdfs.py``). Patterns
# match a label prefix; the captured value is everything to the end of the
# line. Order matters — first hit wins. New filenames added in future
# stories just need a label entry here to participate in smart mode.

_LABEL_PATTERNS: dict[str, tuple[str, ...]] = {
    "name": ("Name:",),
    "company_name": ("Company name:", "Name:"),
    "cin": ("Corporate Identification Number (CIN):", "CIN:"),
    "pan": ("PAN:",),
    "incorporation_date": ("Date of Incorporation:",),
    "registered_address": ("Registered Office:",),
    "address": ("Address:", "located at:"),
    "din": ("Director Identification Number (DIN):", "DIN:"),
    "director_name": ("Director Name:",),
    "aadhaar_last4": ("Aadhaar last 4 digits:",),
    "annual_income_inr": ("Annual Income (INR):",),
    "account_holder_name": ("Account Holder:",),
    "account_number": ("Account Number:",),
}

# Confidences calibrated so Story 3-7's ConfidencePill keeps exercising all
# four bands across the demo's 9 filenames in smart mode:
#   * format-validated patterns (PAN, CIN) → HIGH
#   * proper-noun matches (Name, Address) → MED-HIGH
#   * inferred / structural matches (DIN, summaries, low-confidence) → mid/low

_FIELD_CONFIDENCE: dict[str, float] = {
    "pan": 0.92,
    "cin": 0.92,
    "din": 0.62,
    "name": 0.82,
    "company_name": 0.84,
    "registered_address": 0.80,
    "address": 0.78,
    "incorporation_date": 0.84,
    "director_name": 0.78,
    "aadhaar_last4": 0.30,  # LOW band — kept for ConfidencePill range coverage
    "annual_income_inr": 0.70,
    "account_holder_name": 0.82,
    "account_number": 0.66,
    "ubo_chain": 0.60,
    "shareholder_summary": 0.55,
}


def _coerce_value(raw: str, field_type: str) -> FieldValue | None:
    """Turn a captured string into the shape the contract wants for ``type``."""
    if raw is None:
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    if field_type == "int":
        # Strip thousands separators (commas, INR-style "24,00,000", spaces).
        digits = re.sub(r"[^\d-]", "", cleaned)
        try:
            return int(digits) if digits else None
        except ValueError:
            return None
    # str + date — keep as-is. The contract is permissive about ISO date strings.
    return cleaned


def _extract_simple_field(spec: FieldSpec, text: str) -> tuple[FieldValue, float] | None:
    """Try to find ``spec.field_name`` in ``text`` via the label registry."""
    patterns = _LABEL_PATTERNS.get(spec.field_name)
    if not patterns:
        return None
    for label in patterns:
        # Match the label, then capture everything to end-of-line.
        match = re.search(re.escape(label) + r"\s*([^\n\r]+)", text)
        if match is None:
            continue
        coerced = _coerce_value(match.group(1), spec.type)
        if coerced is None:
            continue
        return coerced, _FIELD_CONFIDENCE.get(spec.field_name, 0.70)
    return None


def _extract_ubo_chain(text: str) -> tuple[FieldValue, float] | None:
    """UBO declarations carry the full chain on one line with ``→`` arrows."""
    match = re.search(r"([^\n]+→[^\n]+→[^\n]+)", text)
    if match is None:
        return None
    return match.group(1).strip(), _FIELD_CONFIDENCE["ubo_chain"]


def _extract_shareholder_summary(text: str) -> tuple[FieldValue, float] | None:
    """Shareholder pattern PDFs lead with ``N shareholders`` and a paragraph."""
    match = re.search(r"(\d+\s+shareholders[^\n]*)", text)
    if match is None:
        return None
    return match.group(1).strip(), _FIELD_CONFIDENCE["shareholder_summary"]


def _extract_from_text(spec: FieldSpec, text: str) -> tuple[FieldValue, float] | None:
    """Dispatcher: pick the right extractor for this field."""
    if spec.field_name == "ubo_chain":
        return _extract_ubo_chain(text)
    if spec.field_name == "shareholder_summary":
        return _extract_shareholder_summary(text)
    return _extract_simple_field(spec, text)


class FixtureDocAILLM:
    """Offline doc-AI impl. Smart mode when ``text`` is supplied; stub fallback otherwise."""

    model_id: str = "fixture"

    async def extract(
        self,
        *,
        document_ref: str,
        text: str | None,
        taxonomy: list[FieldSpec],
    ) -> list[ExtractedField]:
        captured_at = datetime.now(UTC)

        # Smart mode — extract directly from the case's PDF text.
        if text and text.strip():
            extracted = self._smart_extract(
                text=text,
                document_ref=document_ref,
                taxonomy=taxonomy,
                captured_at=captured_at,
            )
            if extracted:
                return extracted
            # Smart mode found nothing → fall through to stub mode rather than
            # return an empty result. Mostly defensive: catches PDFs whose
            # template doesn't carry recognisable labels.

        # Stub mode — pre-baked, filename-keyed.
        stubs = _FIXTURE_EXTRACTIONS.get(document_ref)
        if stubs is None:
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

    @staticmethod
    def _smart_extract(
        *,
        text: str,
        document_ref: str,
        taxonomy: list[FieldSpec],
        captured_at: datetime,
    ) -> list[ExtractedField]:
        """Run regex extraction against the taxonomy; return only what matched."""
        out: list[ExtractedField] = []
        for spec in taxonomy:
            hit = _extract_from_text(spec, text)
            if hit is None:
                continue
            value, confidence = hit
            out.append(
                _build_field(
                    field_name=spec.field_name,
                    document_ref=document_ref,
                    value=value,
                    confidence=confidence,
                    captured_at=captured_at,
                )
            )
        return out


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
