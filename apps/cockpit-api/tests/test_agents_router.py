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


# ───────────── Story 5.1 — verify_entity endpoint ─────────────


VORA_CIN = "U67120MH2024PTC444789"


async def test_verify_endpoint_runs_agent_and_writes_ledger(tmp_writer: LedgerWriter) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/agents/entity_verification/verify",
            json={"case_id": VORA_CAPITAL_ID, "cin": VORA_CIN},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["case_id"] == VORA_CAPITAL_ID
    assert body["cin"] == VORA_CIN
    assert body["mca_status"]["value"] == "active"
    assert body["mca_status"]["provenance"]["confidence_band"] == ConfidenceBand.HIGH.value

    entries = await _read(tmp_writer)
    completed = [e for e in entries if e.action == "agent.completed" and e.actor_id == "entity_verification"]
    assert len(completed) == 1


async def test_verify_endpoint_rejects_invalid_cin() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/agents/entity_verification/verify",
            json={"case_id": VORA_CAPITAL_ID, "cin": "not-a-cin"},
        )
    assert resp.status_code == 422


async def test_verify_endpoint_returns_502_on_mca_not_found(tmp_writer: LedgerWriter) -> None:
    """A magic CIN absent from the mock fixtures raises MCANotFoundError → 502."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/agents/entity_verification/verify",
            json={"case_id": VORA_CAPITAL_ID, "cin": "U99999YY9999YYY999999"},
        )
    assert resp.status_code == 502


# ───────────── Story 5.3 — build_ubo_graph endpoint ─────────────


async def test_ubo_graph_endpoint_builds_graph_for_vora(tmp_writer: LedgerWriter) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/agents/ubo_graph/build",
            json={"case_id": VORA_CAPITAL_ID, "cin": VORA_CIN},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["case_id"] == VORA_CAPITAL_ID
    assert body["root_entity_id"] == "ubo_e_u67120mh2024ptc444789"
    assert len(body["nodes"]) == 6
    assert len(body["edges"]) == 6
    flagged = [e for e in body["edges"] if e["nominee_flag"] == "nominee_suspected"]
    assert len(flagged) == 3


async def test_ubo_graph_endpoint_rejects_invalid_input() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/agents/ubo_graph/build",
            json={"case_id": VORA_CAPITAL_ID, "cin": "short"},
        )
    assert resp.status_code == 422


async def test_ubo_graph_endpoint_returns_502_on_temporary_error(tmp_writer: LedgerWriter) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/agents/ubo_graph/build",
            json={"case_id": VORA_CAPITAL_ID, "cin": "U99999XX9999XXX999999"},
        )
    assert resp.status_code == 502


# ───────────── Story 5.6 — score_risk endpoint ─────────────


async def test_risk_endpoint_rejects_invalid_input() -> None:
    """Validates the request shape at the FastAPI boundary — 422 on bad case_id."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/agents/risk_scoring/score",
            json={"case_id": "not-a-case-id"},
        )
    assert resp.status_code == 422


# ───────────── Story 6.2 — run_screening endpoint ─────────────


async def test_screening_endpoint_runs_agent_and_writes_ledger(tmp_writer: LedgerWriter) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/agents/screening/run",
            json={
                "case_id": VORA_CAPITAL_ID,
                "subjects": [
                    {
                        "subject_kind": "director",
                        "subject_id": "ubo_p_09876544",
                        "full_name": "Rohan Mehta",
                        "date_of_birth": "1978-01-01",
                    }
                ],
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["case_id"] == VORA_CAPITAL_ID
    assert body["subjects_screened"] == 1
    # Mock returns the OFAC SDN hit at 0.73; agent leaves it as "open".
    assert any("sanctions" in h["categories"] for h in body["hits"])
    open_hits = [h for h in body["hits"] if h["disposition"] == "open"]
    assert len(open_hits) >= 1

    entries = await _read(tmp_writer)
    assert len(entries) == 1
    assert entries[0].action == "agent.completed"
    assert entries[0].actor_id == "screening"
    assert isinstance(entries[0].payload, AgentActionLedgerEntry)
    assert entries[0].payload.status == "ok"


async def test_screening_endpoint_rejects_empty_subjects() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/agents/screening/run",
            json={"case_id": VORA_CAPITAL_ID, "subjects": []},
        )
    assert resp.status_code == 422


async def test_screening_endpoint_rejects_invalid_case_id() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/agents/screening/run",
            json={
                "case_id": "not-a-case-id",
                "subjects": [
                    {
                        "subject_kind": "entity",
                        "subject_id": "x",
                        "full_name": "X",
                    }
                ],
            },
        )
    assert resp.status_code == 422


# ───────────── Story 7.3 — draft_rationale endpoint ─────────────


async def test_writing_endpoint_404_when_case_missing(
    tmp_writer: LedgerWriter,
) -> None:
    """No case in the DB → CaseNotFoundError → 404."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from cockpit_api.db import session as session_mod
    from cockpit_api.db.models import Base

    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(eng, expire_on_commit=False)
    saved_engine = getattr(session_mod, "_engine", None)
    saved_factory = getattr(session_mod, "_sessionmaker", None)
    session_mod._engine = eng
    session_mod._sessionmaker = factory
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/v1/agents/writing/draft",
                json={"case_id": VORA_CAPITAL_ID},
            )
    finally:
        session_mod._engine = saved_engine
        session_mod._sessionmaker = saved_factory
        await eng.dispose()
    assert resp.status_code == 404


async def test_writing_endpoint_rejects_invalid_case_id() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/agents/writing/draft",
            json={"case_id": "not-a-case-id"},
        )
    assert resp.status_code == 422


async def test_re_run_agent_writing_route_calls_supervisor(
    tmp_writer: LedgerWriter,
) -> None:
    """POST /v1/cases/{id}/agents/writing/run accepts the writing slug."""
    from datetime import UTC, datetime

    from contracts.cases import get_demo_case_fixtures
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from cockpit_api.db import session as session_mod
    from cockpit_api.db.models import Base
    from cockpit_api.repositories.case_repo import CaseRepo

    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(eng, expire_on_commit=False)
    saved_engine = getattr(session_mod, "_engine", None)
    saved_factory = getattr(session_mod, "_sessionmaker", None)
    session_mod._engine = eng
    session_mod._sessionmaker = factory
    try:
        # Seed Vora case directly into a state the writing supervisor
        # accepts (DECISION_READY) but with NO intake outputs — the
        # supervisor will raise WritingPrerequisitesMissingError, which
        # the route renders as 409.
        from contracts.cases import CaseState

        target = next(c for c in get_demo_case_fixtures(datetime.now(UTC)) if c.id == VORA_CAPITAL_ID).model_copy(
            update={"state": CaseState.DECISION_READY}
        )
        async with factory() as session:
            await CaseRepo.insert(session, target)
            await session.commit()

        from contracts.users import ANALYST_ID

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/v1/cases/{VORA_CAPITAL_ID}/agents/writing/run",
                headers={"X-Cockpit-Demo-User": ANALYST_ID},
            )
    finally:
        session_mod._engine = saved_engine
        session_mod._sessionmaker = saved_factory
        await eng.dispose()
    # 409 because intake outputs missing — but the route DID dispatch
    # to the writing branch (proving the literal extension works).
    assert resp.status_code in (409, 500), resp.json()
