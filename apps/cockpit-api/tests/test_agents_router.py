"""Tests for the ADK-facing agent invocation router — Story 3.4 ADK integration."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from contracts.agent_action import AgentActionLedgerEntry
from contracts.cases import VORA_CAPITAL_ID
from contracts.confidence import ConfidenceBand, to_band
from contracts.ledger import LedgerEntry
from httpx import ASGITransport, AsyncClient

from cockpit_api.main import app
from cockpit_api.services import ledger_service
from cockpit_api.services.ledger_service import LedgerReader, LedgerWriter


@pytest.fixture
def tmp_writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[LedgerWriter]:
    """Bind the ledger to a tmp file for the duration of the test."""
    path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path)
    ledger_service.get_ledger_writer.cache_clear()
    monkeypatch.setattr(ledger_service, "get_ledger_writer", lambda: writer)
    import agents.supervisor.action_decorator as deco

    monkeypatch.setattr(deco, "get_ledger_writer", lambda: writer)
    yield writer


async def _read(writer: LedgerWriter) -> list[LedgerEntry]:
    return await LedgerReader(writer._path).read_all()


async def test_extract_endpoint_runs_agent_and_writes_ledger(
    tmp_writer: LedgerWriter,
) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/agents/document_intelligence/extract",
            json={
                "case_id": VORA_CAPITAL_ID,
                "document_refs": ["incorporation_certificate.pdf", "pan_card.pdf"],
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["case_id"] == VORA_CAPITAL_ID
    field_names = {f["field_name"] for f in body["extracted_fields"]}
    assert {"company_name", "cin", "pan"} <= field_names
    for f in body["extracted_fields"]:
        confidence = f["value"]["provenance"]["confidence"]
        assert f["value"]["provenance"]["confidence_band"] == to_band(confidence).value

    entries = await _read(tmp_writer)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.action == "agent.completed"
    assert isinstance(entry.payload, AgentActionLedgerEntry)
    assert entry.payload.agent_id == "document_intelligence"
    assert entry.payload.status == "ok"


async def test_extract_endpoint_rejects_invalid_case_id() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/agents/document_intelligence/extract",
            json={
                "case_id": "not-a-case-id",
                "document_refs": ["incorporation_certificate.pdf"],
            },
        )
    assert resp.status_code == 422


async def test_extract_endpoint_unknown_filename_returns_low_confidence_field(
    tmp_writer: LedgerWriter,
) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/agents/document_intelligence/extract",
            json={
                "case_id": VORA_CAPITAL_ID,
                "document_refs": ["mystery_file.pdf"],
            },
        )
    assert resp.status_code == 200
    fields = resp.json()["extracted_fields"]
    assert len(fields) == 1
    assert fields[0]["field_name"] == "raw_text"
    assert fields[0]["value"]["provenance"]["confidence_band"] == ConfidenceBand.LOW.value
