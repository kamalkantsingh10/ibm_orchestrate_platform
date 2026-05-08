"""Integration tests for ``GET /v1/cases/{id}/agent-mesh-state`` — Story 4.5 AC #9."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest_asyncio
from contracts.agent_action import AgentActionLedgerEntry
from contracts.cases import (
    Case,
    CaseState,
    CustomerMetadata,
)
from contracts.ledger import ActorType, LedgerEntry
from contracts.users import ANALYST_ID
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from ulid import ULID

from cockpit_api.db.models import Base
from cockpit_api.db.session import get_session
from cockpit_api.main import app
from cockpit_api.repositories.case_repo import CaseRepo
from cockpit_api.services.ledger_service import get_ledger_reader


def _case_id() -> str:
    return f"case_{ULID()!s}"


def _make_case(*, case_id: str, **overrides: Any) -> Case:
    now = datetime.now(UTC)
    defaults: dict[str, Any] = {
        "id": case_id,
        "state": CaseState.INTAKE_SCHEDULED,
        "customer_metadata": CustomerMetadata(customer_name="Acme"),
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return Case(**defaults)


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture(autouse=True)
async def isolate_ledger(tmp_path: Path) -> AsyncIterator[None]:
    """Pin the ledger to a per-test file so writes don't pollute the global one."""
    from cockpit_api.services import ledger_service  # noqa: PLC0415

    pinned = tmp_path / "ledger.jsonl"
    real_reader = ledger_service.LedgerReader(pinned)
    real_writer = ledger_service.LedgerWriter(pinned)

    original_reader = ledger_service.get_ledger_reader
    original_writer = ledger_service.get_ledger_writer
    ledger_service.get_ledger_reader = lambda: real_reader  # type: ignore[assignment]
    ledger_service.get_ledger_writer = lambda: real_writer  # type: ignore[assignment]
    try:
        yield
    finally:
        ledger_service.get_ledger_reader = original_reader
        ledger_service.get_ledger_writer = original_writer


@pytest_asyncio.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as s:
            yield s
            await s.commit()

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _seed_case(session_factory: async_sessionmaker[AsyncSession], case: Case) -> None:
    async with session_factory() as s:
        await CaseRepo.insert(s, case)
        await s.commit()


def _stub_agent_entry(*, case_id: str, actor_id: str, status: str) -> LedgerEntry:
    now = datetime.now(UTC)
    payload = AgentActionLedgerEntry(
        agent_id=actor_id,
        input={},
        output=None,
        started_at=now,
        completed_at=now,
        duration_ms=10,
        status=status,  # type: ignore[arg-type]
    )
    return LedgerEntry(
        id=f"led_{ULID()!s}",
        actor_type=ActorType.AGENT,
        actor_id=actor_id,
        case_id=case_id,
        action="agent.completed",
        payload=payload,
        recorded_at=now,
    )


# ───────────── empty ledger ─────────────


async def test_returns_eight_idle_agents_for_a_seeded_case_with_no_ledger_entries(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    case = _make_case(case_id=_case_id())
    await _seed_case(session_factory, case)
    resp = await client.get(
        f"/v1/cases/{case.id}/agent-mesh-state",
        headers={"X-Cockpit-Demo-User": ANALYST_ID},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["case_id"] == case.id
    assert len(body["agents"]) == 8
    for agent in body["agents"]:
        assert agent["state"] == "idle"


# ───────────── derived states ─────────────


async def test_status_ok_renders_complete(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    case = _make_case(case_id=_case_id())
    await _seed_case(session_factory, case)
    writer = get_ledger_reader  # placeholder access to confirm import path
    _ = writer
    from cockpit_api.services.ledger_service import get_ledger_writer  # noqa: PLC0415

    await get_ledger_writer().append(
        _stub_agent_entry(case_id=case.id, actor_id="document_intelligence", status="ok"),
    )

    resp = await client.get(
        f"/v1/cases/{case.id}/agent-mesh-state",
        headers={"X-Cockpit-Demo-User": ANALYST_ID},
    )
    assert resp.status_code == 200
    by_slug = {a["agent_slug"]: a for a in resp.json()["agents"]}
    assert by_slug["document-intelligence"]["state"] == "complete"
    assert by_slug["screening"]["state"] == "idle"


async def test_status_error_renders_blocked(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    case = _make_case(case_id=_case_id())
    await _seed_case(session_factory, case)
    from cockpit_api.services.ledger_service import get_ledger_writer  # noqa: PLC0415

    await get_ledger_writer().append(
        _stub_agent_entry(case_id=case.id, actor_id="screening", status="error"),
    )

    resp = await client.get(
        f"/v1/cases/{case.id}/agent-mesh-state",
        headers={"X-Cockpit-Demo-User": ANALYST_ID},
    )
    by_slug = {a["agent_slug"]: a for a in resp.json()["agents"]}
    assert by_slug["screening"]["state"] == "blocked"


# ───────────── 404 / auth ─────────────


async def test_404_for_missing_case(client: AsyncClient) -> None:
    missing = _case_id()
    resp = await client.get(
        f"/v1/cases/{missing}/agent-mesh-state",
        headers={"X-Cockpit-Demo-User": ANALYST_ID},
    )
    assert resp.status_code == 404


async def test_400_without_demo_user_header(client: AsyncClient) -> None:
    resp = await client.get(f"/v1/cases/{_case_id()}/agent-mesh-state")
    assert resp.status_code == 400
