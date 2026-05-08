"""Tests for POST /v1/cases/{id}/intake — Story 3.5 / AC #9, #10."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from contracts.cases import (
    VORA_CAPITAL_ID,
    Case,
    CaseState,
    get_demo_case_fixtures,
)
from contracts.users import ANALYST_ID
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from cockpit_api.db import session as session_mod
from cockpit_api.db.models import Base
from cockpit_api.main import app
from cockpit_api.repositories.case_repo import CaseRepo
from cockpit_api.services import ledger_service
from cockpit_api.services.ledger_service import LedgerReader, LedgerWriter


@pytest_asyncio.fixture
async def engine_with_app(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[AsyncEngine]:
    """Bind the cockpit-api app to an in-memory SQLite for the test."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(eng, expire_on_commit=False)

    # Patch the global sessionmaker so the route handler picks up our engine.
    monkeypatch.setattr(session_mod, "_engine", eng)
    monkeypatch.setattr(session_mod, "_sessionmaker", factory)

    try:
        yield eng
    finally:
        await eng.dispose()


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
    import agents.supervisor.case_supervisor as supervisor_mod

    monkeypatch.setattr(deco, "get_ledger_writer", lambda: writer)
    monkeypatch.setattr(supervisor_mod, "get_ledger_writer", lambda: writer)
    monkeypatch.setattr(supervisor_mod, "get_ledger_reader", lambda: reader)
    yield writer


async def _seed_one_case(engine: AsyncEngine) -> Case:
    fixtures = get_demo_case_fixtures(datetime.now(UTC))
    target = next(c for c in fixtures if c.id == VORA_CAPITAL_ID)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await CaseRepo.insert(session, target)
        await session.commit()
    return target


HEADERS = {"X-Cockpit-Demo-User": ANALYST_ID}


# ───────────── happy path ─────────────


async def test_intake_route_completes_for_seeded_case(engine_with_app: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    case = await _seed_one_case(engine_with_app)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(f"/v1/cases/{case.id}/intake", headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["case_id"] == case.id
    assert body["status"] == "completed"
    # Story 6.2: five-agent fan-out (doc_intel → entity_verification → ubo_graph → screening → risk_scoring).
    assert body["agents_run"] == [
        "document_intelligence",
        "entity_verification",
        "ubo_graph",
        "screening",
        "risk_scoring",
    ]
    assert body["fields_extracted"] >= 1


# ───────────── 404 case not found ─────────────


async def test_intake_route_404_when_case_missing(engine_with_app: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(f"/v1/cases/{VORA_CAPITAL_ID}/intake", headers=HEADERS)
    assert resp.status_code == 404
    body = resp.json()
    assert "not found" in body["detail"].lower()


# ───────────── 409 wrong state ─────────────


async def test_intake_route_409_when_already_decision_ready(
    engine_with_app: AsyncEngine, tmp_writer: LedgerWriter
) -> None:
    case = await _seed_one_case(engine_with_app)
    # Manually transition past intake_scheduled
    factory = async_sessionmaker(engine_with_app, expire_on_commit=False)
    async with factory() as session:
        await CaseRepo.transition(session, case.id, CaseState.DECISION_READY)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(f"/v1/cases/{case.id}/intake", headers=HEADERS)
    assert resp.status_code == 409
    body = resp.json()
    assert "intake_scheduled" in body["detail"]


# ───────────── auth — intentionally none (tool surface) ─────────────


async def test_intake_route_no_auth_required_for_agent_tool_path(
    engine_with_app: AsyncEngine, tmp_writer: LedgerWriter
) -> None:
    """Intake is exposed as a tool to the cloud Orchestrate runtime, which
    does NOT send the demo-user header. The endpoint must respond with the
    case's own 404 (when the case doesn't exist) instead of a 400 missing-
    header gate. Mirrors the Story 4.1 contract for ``GET /v1/cases``.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(f"/v1/cases/{VORA_CAPITAL_ID}/intake")
    # No row was seeded → CaseSupervisor's CaseNotFoundError → 404.
    assert resp.status_code == 404
