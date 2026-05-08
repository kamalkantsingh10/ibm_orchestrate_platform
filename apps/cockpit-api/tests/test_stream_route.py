"""Integration tests for ``GET /v1/cases/{case_id}/stream`` — Story 4.6 AC #10."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest_asyncio
from contracts.cases import (
    Case,
    CaseState,
    CustomerMetadata,
)
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
from cockpit_api.services.sse_registry import get_sse_registry


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
    # Wipe the registry between tests to avoid bleed-through.
    get_sse_registry.cache_clear()


async def _seed(session_factory: async_sessionmaker[AsyncSession], case: Case) -> None:
    async with session_factory() as s:
        await CaseRepo.insert(s, case)
        await s.commit()


# ───────────── 404 / auth ─────────────


async def test_400_without_auth(client: AsyncClient) -> None:
    case = _make_case(case_id=_case_id())
    resp = await client.get(f"/v1/cases/{case.id}/stream")
    assert resp.status_code == 400


async def test_400_with_unknown_user(client: AsyncClient) -> None:
    case = _make_case(case_id=_case_id())
    resp = await client.get(
        f"/v1/cases/{case.id}/stream?as=00000000-0000-4000-8000-000099999999",
    )
    assert resp.status_code == 400


async def test_404_for_missing_case(client: AsyncClient) -> None:
    resp = await client.get(
        f"/v1/cases/{_case_id()}/stream?as={ANALYST_ID}",
    )
    assert resp.status_code == 404


# ───────────── happy path ─────────────


# Live streaming behavior (200 + connected frame, registry register/unregister
# on disconnect, fan-out delivery) is intentionally NOT exercised here:
# httpx + ASGITransport's stream-mode lifecycle does not terminate cleanly
# against an open SSE generator, leading to deterministic test hangs. The
# fan-out semantics are unit-tested in ``test_sse_registry``; the live
# streaming path is covered by the headed Playwright smoke (Epic 4 final).
