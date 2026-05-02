"""Integration tests for ``CaseRepo`` against in-memory SQLite — Story 2.1 AC #9."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from contracts.cases import (
    Case,
    CaseState,
    CaseStateTransitionError,
    CustomerMetadata,
)
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from ulid import ULID

from cockpit_api.db.models import Base
from cockpit_api.repositories.case_repo import CaseRepo


def _case_id() -> str:
    return f"case_{ULID()!s}"


def make_case(
    *,
    state: CaseState = CaseState.INTAKE_SCHEDULED,
    created_at: datetime | None = None,
    **overrides: Any,
) -> Case:
    """Build a ``Case`` with sensible defaults; override per test."""
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
    """Fresh in-memory SQLite engine per test (function scope)."""
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s


# ─────────────────────────── tests ────────────────────────────


async def test_insert_then_get_round_trips_a_case(session: AsyncSession) -> None:
    case = make_case(
        customer_metadata=CustomerMetadata(
            customer_name="Acme Pte Ltd",
            customer_type="company",
            country="SG",
            extra={"demo_tag": "fixture-1"},
        ),
        assigned_to_user_id="dc2aaaa3-555b-4636-89d0-6047dc205220",
        risk_band="medium_low",
    )
    await CaseRepo.insert(session, case)
    await session.commit()

    fetched = await CaseRepo.get(session, case.id)
    assert fetched is not None
    assert fetched.id == case.id
    assert fetched.state == case.state
    assert fetched.customer_metadata == case.customer_metadata
    assert fetched.assigned_to_user_id == case.assigned_to_user_id
    assert fetched.risk_band == case.risk_band


async def test_get_unknown_id_returns_none(session: AsyncSession) -> None:
    assert await CaseRepo.get(session, _case_id()) is None


async def test_list_ordered_by_created_at_desc_returns_newest_first(
    session: AsyncSession,
) -> None:
    base = datetime(2026, 4, 30, 12, 0, 0, tzinfo=UTC)
    older = make_case(created_at=base - timedelta(hours=2))
    middle = make_case(created_at=base - timedelta(hours=1))
    newest = make_case(created_at=base)

    # Insert in shuffled order to prove ORDER BY drives the result.
    for c in (middle, newest, older):
        await CaseRepo.insert(session, c)
    await session.commit()

    rows = await CaseRepo.list_ordered_by_created_at_desc(session)
    assert [r.id for r in rows] == [newest.id, middle.id, older.id]


async def test_transition_intake_to_decision_ready(session: AsyncSession) -> None:
    case = make_case(state=CaseState.INTAKE_SCHEDULED)
    await CaseRepo.insert(session, case)
    await session.commit()

    updated = await CaseRepo.transition(session, case.id, CaseState.DECISION_READY)
    assert updated.state == CaseState.DECISION_READY
    assert updated.id == case.id
    assert updated.closure_date is None


async def test_transition_from_closed_to_intake_raises(session: AsyncSession) -> None:
    case = make_case(
        state=CaseState.CLOSED,
        closure_date=datetime.now(UTC),
    )
    await CaseRepo.insert(session, case)
    await session.commit()

    with pytest.raises(CaseStateTransitionError):
        await CaseRepo.transition(session, case.id, CaseState.INTAKE_SCHEDULED)


async def test_transition_to_closed_populates_closure_date(
    session: AsyncSession,
) -> None:
    case = make_case(state=CaseState.DECISION_READY)
    await CaseRepo.insert(session, case)
    await session.commit()

    before = datetime.now(UTC)
    # Yield once so the event loop can timestamp later than `before`.
    await asyncio.sleep(0)
    updated = await CaseRepo.transition(session, case.id, CaseState.CLOSED)
    assert updated.state == CaseState.CLOSED
    assert updated.closure_date is not None
    assert updated.closure_date >= before
