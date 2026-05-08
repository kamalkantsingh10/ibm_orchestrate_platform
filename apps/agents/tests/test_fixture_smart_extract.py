"""Tests for FixtureDocAILLM smart-mode extraction — Story 4 hardening.

Smart mode kicks in when the caller passes the per-case PDF text. The
fixture should pull case-correct fields out of the text via regex labels,
not return the static "Vora" stubs.

Stub mode (text=None) is still tested by the existing
``test_document_intelligence.py`` happy path.
"""

from __future__ import annotations

import pytest
from contracts.confidence import ConfidenceBand

from agents.adapters.doc_ai.fixture import FixtureDocAILLM
from agents.jurisdictions.india import get_india_taxonomy


def _taxonomy_for(category: str) -> list:  # type: ignore[type-arg]
    return get_india_taxonomy().categories[category]


# ─────────────────────── PAN card — Ananya, not Vora ───────────────────────


@pytest.mark.asyncio
async def test_smart_pan_card_extracts_case_name() -> None:
    """The whole point of this story: Ananya's pan_card must NOT say Vora."""
    text = (
        "INCOME TAX DEPARTMENT — GOVERNMENT OF INDIA\n"
        "Permanent Account Number Card\n"
        "Name: Ananya Iyer\n"
        "PAN: AAFPI4567Q\n"
        "Date of Birth: 1985-11-04\n"
    )
    llm = FixtureDocAILLM()
    fields = await llm.extract(
        document_ref="pan_card.pdf",
        text=text,
        taxonomy=_taxonomy_for("pan_card"),
    )
    by_name = {f.field_name: f for f in fields}
    assert by_name["name"].value.value == "Ananya Iyer"
    assert by_name["pan"].value.value == "AAFPI4567Q"
    # No "Vora" anywhere in the output.
    assert all("vora" not in str(f.value.value).lower() for f in fields)


@pytest.mark.asyncio
async def test_smart_pan_card_for_company_extracts_company_name() -> None:
    text = "Permanent Account Number Card\nName: Vora Capital Holdings Pvt Ltd\nPAN: U6712V1234R\n"
    llm = FixtureDocAILLM()
    fields = await llm.extract(
        document_ref="pan_card.pdf",
        text=text,
        taxonomy=_taxonomy_for("pan_card"),
    )
    by_name = {f.field_name: f for f in fields}
    assert by_name["name"].value.value == "Vora Capital Holdings Pvt Ltd"
    assert by_name["pan"].value.value == "U6712V1234R"


# ─────────────────────── Incorporation certificate ─────────────────────────


@pytest.mark.asyncio
async def test_smart_incorporation_certificate_extracts_cin_and_address() -> None:
    text = (
        "CERTIFICATE OF INCORPORATION\n"
        "Vora Capital Holdings Pvt Ltd is incorporated.\n"
        "Corporate Identification Number (CIN): U67120MH2024PTC444789\n"
        "Date of Incorporation: 2024-08-22\n"
        "Registered Office: Suite 402, Sea Breeze Heights, Bandra West, Mumbai 400050\n"
    )
    llm = FixtureDocAILLM()
    fields = await llm.extract(
        document_ref="incorporation_certificate.pdf",
        text=text,
        taxonomy=_taxonomy_for("incorporation_certificate"),
    )
    by_name = {f.field_name: f for f in fields}
    assert by_name["cin"].value.value == "U67120MH2024PTC444789"
    assert by_name["incorporation_date"].value.value == "2024-08-22"
    assert "Bandra West" in str(by_name["registered_address"].value.value)


# ─────────────────────── Aadhaar — case-specific name ──────────────────────


@pytest.mark.asyncio
async def test_smart_aadhaar_extracts_case_name() -> None:
    text = (
        "AADHAAR — UNIQUE IDENTIFICATION AUTHORITY OF INDIA\n"
        "Name: Ananya Iyer\n"
        "Aadhaar last 4 digits: 4567\n"
        "Date of Birth: 1985-11-04\n"
    )
    llm = FixtureDocAILLM()
    fields = await llm.extract(
        document_ref="aadhaar.pdf",
        text=text,
        taxonomy=_taxonomy_for("aadhaar"),
    )
    by_name = {f.field_name: f for f in fields}
    assert by_name["name"].value.value == "Ananya Iyer"
    assert by_name["aadhaar_last4"].value.value == "4567"


# ─────────────────────── Income proof — int coercion ───────────────────────


@pytest.mark.asyncio
async def test_smart_income_proof_coerces_int() -> None:
    text = (
        "INCOME TAX RETURN — ASSESSMENT YEAR 2024-25\n"
        "Name: Ananya Iyer\n"
        "PAN: AAFPI4567Q\n"
        "Annual Income (INR): 24,000,000\n"
    )
    llm = FixtureDocAILLM()
    fields = await llm.extract(
        document_ref="income_proof.pdf",
        text=text,
        taxonomy=_taxonomy_for("income_proof"),
    )
    by_name = {f.field_name: f for f in fields}
    # Comma-separated INR string coerces to plain int.
    assert by_name["annual_income_inr"].value.value == 24_000_000
    assert isinstance(by_name["annual_income_inr"].value.value, int)


# ─────────────────────── UBO declaration — chain match ─────────────────────


@pytest.mark.asyncio
async def test_smart_ubo_declaration_extracts_chain() -> None:
    text = (
        "ULTIMATE BENEFICIAL OWNER DECLARATION\n"
        "Vora Capital Holdings Pvt Ltd (India)"
        " → Coastal Equity Partners Pte Ltd (Singapore, 100%)"
        " → Anchor Trust Services (BVI) (BVI, 100%)\n"
        "Effective date: 2024-08-22.\n"
    )
    llm = FixtureDocAILLM()
    fields = await llm.extract(
        document_ref="ubo_declaration.pdf",
        text=text,
        taxonomy=_taxonomy_for("ubo_declaration"),
    )
    assert len(fields) == 1
    chain = str(fields[0].value.value)
    assert "Vora" in chain
    assert "Coastal Equity" in chain
    assert "Anchor Trust" in chain


# ─────────────────────── Bank statement ────────────────────────────────────


@pytest.mark.asyncio
async def test_smart_bank_statement_extracts_account_holder() -> None:
    text = (
        "HDFC BANK — STATEMENT OF ACCOUNT\n"
        "Account Holder: Vora Capital Holdings Pvt Ltd\n"
        "Account Number: 0123456789012\n"
        "Period: Q1 FY 2024-25\n"
    )
    llm = FixtureDocAILLM()
    fields = await llm.extract(
        document_ref="bank_statement_q1.pdf",
        text=text,
        taxonomy=_taxonomy_for("bank_statement"),
    )
    by_name = {f.field_name: f for f in fields}
    assert by_name["account_holder_name"].value.value == "Vora Capital Holdings Pvt Ltd"
    assert by_name["account_number"].value.value == "0123456789012"


# ─────────────────────── Stub mode unchanged ───────────────────────────────


@pytest.mark.asyncio
async def test_text_none_falls_back_to_stub_mode() -> None:
    """Existing offline tests pass text=None — must keep returning stubs."""
    llm = FixtureDocAILLM()
    fields = await llm.extract(
        document_ref="pan_card.pdf",
        text=None,
        taxonomy=_taxonomy_for("pan_card"),
    )
    # Stub mode produces both PAN and name, with the static "Vora" name.
    by_name = {f.field_name: f for f in fields}
    assert by_name["pan"].value.value == "AAFCV1234R"  # static stub
    assert by_name["name"].value.value == "Vora Capital Holdings Pvt Ltd"


@pytest.mark.asyncio
async def test_empty_text_falls_back_to_stub_mode() -> None:
    """``text=""`` is treated as "no text available" → stub fallback."""
    llm = FixtureDocAILLM()
    fields = await llm.extract(
        document_ref="aadhaar.pdf",
        text="",
        taxonomy=_taxonomy_for("aadhaar"),
    )
    assert len(fields) == 2  # static stubs


# ─────────────────────── Smart mode finds nothing → stub ────────────────────


@pytest.mark.asyncio
async def test_smart_mode_no_labels_falls_back_to_stub() -> None:
    """If the PDF text doesn't carry ANY recognised label, fall through."""
    text = "Some unrelated body text with no structured labels at all."
    llm = FixtureDocAILLM()
    fields = await llm.extract(
        document_ref="pan_card.pdf",
        text=text,
        taxonomy=_taxonomy_for("pan_card"),
    )
    # Stubs returned — defensive fallback.
    by_name = {f.field_name: f for f in fields}
    assert "pan" in by_name


# ─────────────────────── Provenance contract preserved ─────────────────────


@pytest.mark.asyncio
async def test_smart_mode_stamps_fixture_doc_ai_provenance() -> None:
    text = "Name: Test Name\nPAN: TEST12345Z\n"
    llm = FixtureDocAILLM()
    fields = await llm.extract(
        document_ref="pan_card.pdf",
        text=text,
        taxonomy=_taxonomy_for("pan_card"),
    )
    for f in fields:
        assert f.value.provenance.source_system == "fixture_doc_ai"
        assert f.value.provenance.source_agent == "document_intelligence"
        # PAN format-validated → HIGH; Name proper-noun → MED-HIGH.
        assert f.value.provenance.confidence > 0
        assert f.value.provenance.confidence_band in {
            ConfidenceBand.HIGH,
            ConfidenceBand.MEDIUM_HIGH,
            ConfidenceBand.MEDIUM_LOW,
            ConfidenceBand.LOW,
        }
