"""End-to-end tests for ``GET /v1/cases`` and ``GET /v1/cases/{case_id}`` — Story 2.2 AC #9."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from contracts.cases import (
    Case,
    CaseState,
    CustomerMetadata,
)
from contracts.users import ANALYST_ID, REGULATOR_ID, TEAM_LEAD_ID
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


def _case_id() -> str:
    return f"case_{ULID()!s}"


def _make_case(
    *,
    state: CaseState = CaseState.INTAKE_SCHEDULED,
    created_at: datetime | None = None,
    **overrides: Any,
) -> Case:
    now = created_at or datetime.now(UTC)
    defaults: dict[str, Any] = {
        "id": _case_id(),
        "state": state,
        "customer_metadata": CustomerMetadata(customer_name="Acme Pte Ltd"),
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
async def session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


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


async def _seed(
    session_factory: async_sessionmaker[AsyncSession],
    case: Case,
) -> None:
    async with session_factory() as s:
        await CaseRepo.insert(s, case)
        await s.commit()


# ───────────── single case ─────────────


async def test_get_case_returns_200_and_envelope(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    case = _make_case()
    await _seed(session_factory, case)

    resp = await client.get(
        f"/v1/cases/{case.id}",
        headers={"X-Cockpit-Demo-User": ANALYST_ID},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == case.id
    assert body["state"] == "intake_scheduled"
    assert body["_links"] == {"documents": None, "reasoning_traces": None}
    assert body["customer_metadata"]["customer_name"] == "Acme Pte Ltd"


async def test_get_case_returns_404_rfc7807_when_missing(client: AsyncClient) -> None:
    missing_id = _case_id()
    resp = await client.get(
        f"/v1/cases/{missing_id}",
        headers={"X-Cockpit-Demo-User": ANALYST_ID},
    )
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body == {
        "type": "about:blank",
        "title": "Not Found",
        "status": 404,
        "detail": f"Case {missing_id} not found",
        "instance": f"/v1/cases/{missing_id}",
    }


async def test_get_case_returns_422_when_path_malformed(client: AsyncClient) -> None:
    resp = await client.get(
        "/v1/cases/bogus",
        headers={"X-Cockpit-Demo-User": ANALYST_ID},
    )
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["status"] == 422
    assert body["title"] == "Unprocessable Entity"
    assert "case_id" in body["detail"]


async def test_get_case_returns_400_when_header_missing(client: AsyncClient) -> None:
    resp = await client.get(f"/v1/cases/{_case_id()}")
    assert resp.status_code == 400
    body = resp.json()
    assert body["status"] == 400
    assert "X-Cockpit-Demo-User" in body["detail"]


async def test_get_case_returns_400_when_header_unknown(client: AsyncClient) -> None:
    resp = await client.get(
        f"/v1/cases/{_case_id()}",
        headers={"X-Cockpit-Demo-User": "00000000-0000-4000-8000-000000999999"},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert "Unknown" in body["detail"]


@pytest.mark.parametrize("user_id", [ANALYST_ID, TEAM_LEAD_ID, REGULATOR_ID])
async def test_get_case_succeeds_for_each_demo_user(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: str,
) -> None:
    case = _make_case()
    await _seed(session_factory, case)

    resp = await client.get(
        f"/v1/cases/{case.id}",
        headers={"X-Cockpit-Demo-User": user_id},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == case.id


# ───────────── list ─────────────


async def test_list_cases_empty(client: AsyncClient) -> None:
    resp = await client.get(
        "/v1/cases",
        headers={"X-Cockpit-Demo-User": ANALYST_ID},
    )
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "next_cursor": None, "has_more": False}


async def test_list_cases_returns_newest_first(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    base = datetime(2026, 4, 30, 12, 0, 0, tzinfo=UTC)
    older = _make_case(created_at=base - timedelta(hours=2))
    middle = _make_case(created_at=base - timedelta(hours=1))
    newest = _make_case(created_at=base)
    for c in (older, middle, newest):
        await _seed(session_factory, c)

    resp = await client.get(
        "/v1/cases",
        headers={"X-Cockpit-Demo-User": ANALYST_ID},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert [item["id"] for item in body["items"]] == [newest.id, middle.id, older.id]
    assert body["next_cursor"] is None
    assert body["has_more"] is False
    # Every envelope still carries the _links placeholder.
    for item in body["items"]:
        assert item["_links"] == {"documents": None, "reasoning_traces": None}


async def test_list_cases_rejects_missing_header(client: AsyncClient) -> None:
    resp = await client.get("/v1/cases")
    assert resp.status_code == 400
    assert "X-Cockpit-Demo-User" in resp.json()["detail"]
