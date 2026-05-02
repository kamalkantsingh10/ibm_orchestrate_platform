"""End-to-end smoke for @agent_action — Story 3.2 / AC #11."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from cockpit_api.services import ledger_service
from cockpit_api.services.ledger_service import LedgerReader, LedgerWriter
from contracts.agent_action import AgentActionLedgerEntry
from contracts.cases import SHREE_VENKAT_ID, CaseId
from contracts.ledger import ActorType
from pydantic import BaseModel

from agents.supervisor.action_decorator import agent_action


class StubIn(BaseModel):
    case_id: CaseId


class StubOut(BaseModel):
    bar: int


@pytest.fixture
def tmp_writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[LedgerWriter]:
    path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path)
    ledger_service.get_ledger_writer.cache_clear()
    monkeypatch.setattr(ledger_service, "get_ledger_writer", lambda: writer)

    import agents.supervisor.action_decorator as deco

    monkeypatch.setattr(deco, "get_ledger_writer", lambda: writer)
    yield writer


async def test_real_writer_round_trip(tmp_writer: LedgerWriter) -> None:
    @agent_action(
        agent_id="document_intelligence",
        model_id="stub",
        prompt_template_id="stub/v1",
    )
    async def fake_doc_intelligence(_: StubIn) -> StubOut:
        return StubOut(bar=42)

    await fake_doc_intelligence(StubIn(case_id=SHREE_VENKAT_ID))

    reader = LedgerReader(tmp_writer._path)
    entries = await reader.read_all()
    assert len(entries) == 1
    e = entries[0]
    assert e.actor_type == ActorType.AGENT
    assert e.actor_id == "document_intelligence"
    assert e.case_id == SHREE_VENKAT_ID
    assert isinstance(e.payload, AgentActionLedgerEntry)
    assert e.payload.status == "ok"
    assert e.payload.model_id == "stub"
    assert e.payload.prompt_template_id == "stub/v1"
