"""Writing agent tests — Story 7.3 / AC #11."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cockpit_api.services import ledger_service
from cockpit_api.services.ledger_service import LedgerReader, LedgerWriter
from contracts.agent_action import AgentActionLedgerEntry
from contracts.cases import VORA_CAPITAL_ID, Case, CaseState, CustomerMetadata
from contracts.confidence import to_band
from contracts.document_intelligence import DocumentIntelligenceOutput, ExtractedField
from contracts.ledger import LedgerEntry
from contracts.provenance import Provenance, ProvenancedField
from contracts.writing import CitedClaim, WritingAgentInput

from agents.adapters.writing import (
    FixtureWritingLLM,
    WritingLLMError,
    get_default_writing_llm,
)
from agents.adapters.writing.base import RawRationaleDraft
from agents.decision.writing import _wrap_html_with_citations, writing
from agents.supervisor.action_decorator import (
    _runtime_model_id,
    _runtime_prompt_hash,
)

VORA_DOC_INTEL_LED = "led_01ABCDEFGHJKMNPQRSTVWXYZ12"
VORA_EV_LED = "led_01HXY3GHJKMNPQRSTVWXYZ7HX2"
VORA_UBO_LED = "led_01HXY4GHJKMNPQRSTVWXYZ7HX3"
VORA_SCREEN_LED = "led_01HXY5GHJKMNPQRSTVWXYZ7HX4"
VORA_RISK_LED = "led_01HXY6GHJKMNPQRSTVWXYZ7HX5"


@pytest.fixture
def tmp_writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[LedgerWriter]:
    path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path)
    reader = LedgerReader(path)
    ledger_service.get_ledger_writer.cache_clear()
    ledger_service.get_ledger_reader.cache_clear()
    monkeypatch.setattr(ledger_service, "get_ledger_writer", lambda: writer)
    monkeypatch.setattr(ledger_service, "get_ledger_reader", lambda: reader)
    import agents.supervisor.action_decorator as deco

    monkeypatch.setattr(deco, "get_ledger_writer", lambda: writer)
    _runtime_model_id.set(None)
    _runtime_prompt_hash.set(None)
    yield writer


def _make_vora_case() -> Case:
    return Case(
        id=VORA_CAPITAL_ID,
        state=CaseState.DECISION_READY,
        customer_metadata=CustomerMetadata(
            customer_name="Vora Capital Holdings Pvt Ltd",
            customer_type="company",
            country="IN",
        ),
        created_at=datetime(2026, 5, 1, tzinfo=UTC),
        updated_at=datetime(2026, 5, 8, tzinfo=UTC),
    )


def _make_doc_intel() -> DocumentIntelligenceOutput:
    captured = datetime(2026, 5, 8, tzinfo=UTC)
    provenance = Provenance(
        source_agent="document_intelligence",
        source_system="fixture_doc_ai",
        confidence=0.85,
        confidence_band=to_band(0.85),
        evidence_ids=[],
        captured_at=captured,
    )
    pf: ProvenancedField[str | int | float | bool | None] = ProvenancedField(
        value="Vora Capital Holdings Pvt Ltd",
        provenance=provenance,
    )
    field = ExtractedField(field_name="company_name", document_ref="x.pdf", value=pf)
    return DocumentIntelligenceOutput(case_id=VORA_CAPITAL_ID, extracted_fields=[field])


def _vora_ledger_ids() -> dict[str, str]:
    return {
        "document_intelligence": VORA_DOC_INTEL_LED,
        "entity_verification": VORA_EV_LED,
        "ubo_graph": VORA_UBO_LED,
        "screening": VORA_SCREEN_LED,
        "risk_scoring": VORA_RISK_LED,
    }


async def _read_entries(writer: LedgerWriter) -> list[LedgerEntry]:
    reader = LedgerReader(writer._path)
    return await reader.read_all()


# ───────────── happy path ─────────────


async def test_happy_path_with_fixture_llm_emits_html_with_citations(
    tmp_writer: LedgerWriter,
) -> None:
    case = _make_vora_case()
    output = await writing(
        _input_with(),
        case=case,
        doc_intel=_make_doc_intel(),
        entity_verification=None,
        ubo=None,
        screening=None,
        risk=None,
        ledger_ids=_vora_ledger_ids(),
        llm=FixtureWritingLLM(),
    )
    # Fixture's Vora draft contains 3 paragraphs and several citations.
    assert 2 <= len(output.paragraphs) <= 4
    assert output.html.count('<span data-ledger-id="') >= 1
    # All cited ledger IDs must come from the input map.
    cited = {claim.evidence_ledger_id for claim in output.cited_claims}
    assert cited.issubset(set(_vora_ledger_ids().values()))
    assert output.model_id == "fixture-writing-v1"
    assert output.prompt_template_id == "rationale_draft_v1"


async def test_default_writing_llm_is_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WRITING_LLM_PROVIDER", raising=False)
    impl = get_default_writing_llm()
    assert isinstance(impl, FixtureWritingLLM)


async def test_unknown_writing_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WRITING_LLM_PROVIDER", "bogus")
    with pytest.raises(ValueError, match="Unknown WRITING_LLM_PROVIDER"):
        get_default_writing_llm()


async def test_watsonx_provider_without_credentials_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for env_key in ("WATSONX_APIKEY", "WATSONX_API_KEY", "WATSONX_PROJECT_ID"):
        monkeypatch.delenv(env_key, raising=False)
    monkeypatch.setenv("WRITING_LLM_PROVIDER", "watsonx")
    with pytest.raises(WritingLLMError, match="WATSONX_APIKEY"):
        get_default_writing_llm()


async def test_reasoning_trace_is_recorded_in_ledger(tmp_writer: LedgerWriter) -> None:
    case = _make_vora_case()
    await writing(
        _input_with(),
        case=case,
        doc_intel=_make_doc_intel(),
        entity_verification=None,
        ubo=None,
        screening=None,
        risk=None,
        ledger_ids=_vora_ledger_ids(),
        llm=FixtureWritingLLM(),
    )
    entries = await _read_entries(tmp_writer)
    # First entry is agent.completed for writing.
    completed = next(e for e in entries if e.action == "agent.completed")
    assert isinstance(completed.payload, AgentActionLedgerEntry)
    trace = completed.payload.reasoning_trace
    assert trace is not None
    assert "Document Intelligence" in trace.what_searched
    assert "ledger entries" in trace.what_hit


async def test_html_wrapping_escapes_special_chars() -> None:
    raw = RawRationaleDraft(
        paragraphs=["The customer used <script>alert(1)</script> & friends."],
        cited_claims=[
            CitedClaim(
                text="<script>alert(1)</script> & friends",
                evidence_ledger_id=VORA_DOC_INTEL_LED,
            ),
        ],
    )
    html = _wrap_html_with_citations(raw)
    # Raw script tag must NOT survive — it should be escaped before being
    # wrapped in the citation span.
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    # Citation span (the only HTML the wrapper adds) must be present.
    assert f'data-ledger-id="{VORA_DOC_INTEL_LED}"' in html


async def test_html_wrapping_emits_paragraph_tags_and_citation_class() -> None:
    raw = RawRationaleDraft(
        paragraphs=["First paragraph claim text here."],
        cited_claims=[CitedClaim(text="claim text", evidence_ledger_id=VORA_DOC_INTEL_LED)],
    )
    html = _wrap_html_with_citations(raw)
    assert html.startswith("<p>")
    assert html.endswith("</p>")
    assert 'class="citation-token"' in html


async def test_set_runtime_model_id_propagates_to_ledger(tmp_writer: LedgerWriter) -> None:
    case = _make_vora_case()
    await writing(
        _input_with(),
        case=case,
        doc_intel=_make_doc_intel(),
        entity_verification=None,
        ubo=None,
        screening=None,
        risk=None,
        ledger_ids=_vora_ledger_ids(),
        llm=FixtureWritingLLM(),
    )
    entries = await _read_entries(tmp_writer)
    completed = next(e for e in entries if e.action == "agent.completed")
    assert isinstance(completed.payload, AgentActionLedgerEntry)
    # set_runtime_model_id was called with FixtureWritingLLM.model_id.
    assert completed.payload.model_id == "fixture-writing-v1"


def _input_with() -> WritingAgentInput:
    return WritingAgentInput(case_id=VORA_CAPITAL_ID)
