"""Tests for the Document Intelligence agent — Story 3.4 / AC #10."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cockpit_api.services import ledger_service
from cockpit_api.services.ledger_service import LedgerReader, LedgerWriter
from contracts.agent_action import AgentActionLedgerEntry
from contracts.cases import (
    ANANYA_IYER_ID,
    SHREE_VENKAT_ID,
    VORA_CAPITAL_ID,
    get_demo_case_fixtures,
)
from contracts.confidence import ConfidenceBand, to_band
from contracts.document_intelligence import DocumentIntelligenceInput
from contracts.ledger import LedgerEntry

from agents.adapters.doc_ai.fixture import FixtureDocAILLM
from agents.intake.document_intelligence import (
    _classify,
    document_intelligence,
)


@pytest.fixture
def tmp_writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[LedgerWriter]:
    path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path)
    ledger_service.get_ledger_writer.cache_clear()
    monkeypatch.setattr(ledger_service, "get_ledger_writer", lambda: writer)
    import agents.supervisor.action_decorator as deco

    monkeypatch.setattr(deco, "get_ledger_writer", lambda: writer)
    yield writer


async def _read(writer: LedgerWriter) -> list[LedgerEntry]:
    reader = LedgerReader(writer._path)
    return await reader.read_all()


# ───────────── happy path ─────────────


async def test_happy_path_fixture_extraction(tmp_writer: LedgerWriter) -> None:
    out = await document_intelligence(
        DocumentIntelligenceInput(
            case_id=VORA_CAPITAL_ID,
            document_refs=["incorporation_certificate.pdf", "pan_card.pdf"],
        )
    )
    field_names = {f.field_name for f in out.extracted_fields}
    assert {"company_name", "cin", "incorporation_date", "registered_address", "pan", "name"} <= field_names
    for f in out.extracted_fields:
        prov = f.value.provenance
        assert prov.source_agent == "document_intelligence"
        assert prov.source_system == "fixture_doc_ai"
        assert 0.0 <= prov.confidence <= 1.0
        assert prov.confidence_band == to_band(prov.confidence)


# ───────────── empty input ─────────────


async def test_empty_document_refs_returns_empty_output(
    tmp_writer: LedgerWriter,
) -> None:
    out = await document_intelligence(DocumentIntelligenceInput(case_id=VORA_CAPITAL_ID, document_refs=[]))
    assert out.extracted_fields == []
    entries = await _read(tmp_writer)
    assert len(entries) == 1
    assert isinstance(entries[0].payload, AgentActionLedgerEntry)
    assert entries[0].payload.output is not None
    assert entries[0].payload.output["extracted_fields"] == []


# ───────────── unknown ref fallback ─────────────


async def test_unknown_document_ref_fallback(tmp_writer: LedgerWriter) -> None:
    out = await document_intelligence(
        DocumentIntelligenceInput(case_id=VORA_CAPITAL_ID, document_refs=["mystery_file.pdf"])
    )
    assert len(out.extracted_fields) == 1
    f = out.extracted_fields[0]
    assert f.field_name == "raw_text"
    assert f.value.value is None
    assert f.value.provenance.confidence < 0.40  # LOW band


# ───────────── confidence-band distribution ─────────────


async def test_band_distribution_covers_all_four_bands(
    tmp_writer: LedgerWriter,
) -> None:
    """Across all distinct demo filenames, fixture extractions span every band."""
    cases = get_demo_case_fixtures(datetime.now(UTC))
    refs: set[str] = set()
    for case in cases:
        refs.update(case.customer_metadata.extra.get("document_refs", []))

    out = await document_intelligence(DocumentIntelligenceInput(case_id=VORA_CAPITAL_ID, document_refs=sorted(refs)))
    bands = {f.value.provenance.confidence_band for f in out.extracted_fields}
    expected = {
        ConfidenceBand.LOW,
        ConfidenceBand.MEDIUM_LOW,
        ConfidenceBand.MEDIUM_HIGH,
        ConfidenceBand.HIGH,
    }
    assert bands == expected, f"missing bands: {expected - bands}"


# ───────────── ledger entry shape ─────────────


async def test_ledger_entry_records_typed_payload(
    tmp_writer: LedgerWriter,
) -> None:
    inp = DocumentIntelligenceInput(
        case_id=ANANYA_IYER_ID,
        document_refs=["pan_card.pdf"],
    )
    await document_intelligence(inp)
    entries = await _read(tmp_writer)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.action == "agent.completed"
    assert entry.actor_id == "document_intelligence"
    assert isinstance(entry.payload, AgentActionLedgerEntry)
    assert entry.payload.agent_id == "document_intelligence"
    assert entry.payload.model_id == "fixture"
    assert entry.payload.prompt_template_id == "document_intelligence/extract_v1"
    assert entry.payload.input["case_id"] == ANANYA_IYER_ID
    assert entry.payload.input["document_refs"] == ["pan_card.pdf"]
    assert entry.payload.output is not None
    assert "extracted_fields" in entry.payload.output


# ───────────── classifier ─────────────


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("incorporation_certificate.pdf", "incorporation_certificate"),
        ("pan_card.pdf", "pan_card"),
        ("bank_statement_q1.pdf", "bank_statement"),
        ("director_id.pdf", "director_id"),
        ("ubo_declaration.pdf", "ubo_declaration"),
        ("aadhaar.pdf", "aadhaar"),
        ("income_proof.pdf", "income_proof"),
        ("address_proof.pdf", "address_proof"),
        ("shareholder_pattern.pdf", "shareholder_pattern"),
        ("mystery_file.pdf", "unknown"),
    ],
)
def test_classify_filename(filename: str, expected: str) -> None:
    assert _classify(filename) == expected


# ───────────── prompt template determinism ─────────────


def test_prompt_template_is_deterministic(tmp_writer: LedgerWriter) -> None:
    """Rendering the same inputs twice produces byte-identical output."""
    from agents.adapters.doc_ai.watsonx import render_prompt
    from agents.jurisdictions.india import get_india_taxonomy

    taxonomy = get_india_taxonomy()
    specs = taxonomy.categories["incorporation_certificate"]
    text = "Some PDF text"
    a = render_prompt(document_ref="incorporation_certificate.pdf", text=text, taxonomy=specs)
    b = render_prompt(document_ref="incorporation_certificate.pdf", text=text, taxonomy=specs)
    assert a == b
    digest = hashlib.sha256(a.encode("utf-8")).hexdigest()
    assert len(digest) == 64


# ───────────── fixture model_id propagates to ledger ─────────────


async def test_fixture_model_id_recorded_in_ledger(
    tmp_writer: LedgerWriter,
) -> None:
    await document_intelligence(
        DocumentIntelligenceInput(
            case_id=SHREE_VENKAT_ID,
            document_refs=["incorporation_certificate.pdf"],
        ),
        llm=FixtureDocAILLM(),
    )
    entries = await _read(tmp_writer)
    assert isinstance(entries[0].payload, AgentActionLedgerEntry)
    assert entries[0].payload.model_id == "fixture"
    # Fixture path does not set prompt_hash.
    assert entries[0].payload.prompt_hash is None


# ───────────── watsonx skip without creds ─────────────


@pytest.mark.skipif(
    not os.environ.get("WATSONX_API_KEY"),
    reason="watsonx creds not configured",
)
def test_watsonx_impl_imports() -> None:
    from agents.adapters.doc_ai.watsonx import WatsonxDocAILLM

    inst = WatsonxDocAILLM()
    assert inst.model_id


# ───────────── watsonx error path (mocked) ─────────────


async def test_watsonx_http_error_propagates_as_doc_ai_error(
    tmp_writer: LedgerWriter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mocked watsonx HTTP failure surfaces as ``DocAILLMError`` and writes a failed entry."""
    monkeypatch.setenv("WATSONX_API_KEY", "stub")
    monkeypatch.setenv("WATSONX_PROJECT_ID", "stub")
    from agents.adapters.doc_ai.watsonx import WatsonxDocAILLM
    from agents.supervisor.action_decorator import AgentExecutionError

    class _BoomLLM(WatsonxDocAILLM):
        async def _call(self, prompt: str) -> str:
            import httpx as _httpx

            raise _httpx.RequestError("boom")

    boom_llm = _BoomLLM(api_key="stub", project_id="stub")

    with pytest.raises(AgentExecutionError):
        await document_intelligence(
            DocumentIntelligenceInput(
                case_id=VORA_CAPITAL_ID,
                document_refs=["incorporation_certificate.pdf"],
            ),
            llm=boom_llm,
        )

    # Need a PDF file or the call fails earlier — let's also verify that path:
    # we expect the error path to hit on _read_pdf_text returning None first
    # (file_not_found WARN), and watsonx.extract raising on text=None.
    entries = await _read(tmp_writer)
    assert len(entries) == 1
    assert entries[0].action == "agent.failed"
    assert isinstance(entries[0].payload, AgentActionLedgerEntry)
    assert entries[0].payload.status == "error"
