"""Tests for DecisionRepo — Story 7.7 / AC #11."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from contracts.cases import VORA_CAPITAL_ID
from contracts.decision import Decision
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from cockpit_api.db.models import Base
from cockpit_api.repositories.decision_repo import DecisionRepo


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine: AsyncEngine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def _make_decision(**overrides: object) -> Decision:
    base: dict[str, object] = {
        "decision_id": "dec_test_1",
        "case_id": VORA_CAPITAL_ID,
        "outcome": "approve",
        "conditions": [],
        "rationale_html": "<p>Approve based on the screening hits.</p>",
        "committed_by_user_id": "user_analyst",
        "committed_at": datetime.now(UTC),
        "committed_ledger_entry_id": "led_01ABCDEFGHJKMNPQRSTVWXYZ12",
    }
    base.update(overrides)
    return Decision(**base)  # type: ignore[arg-type]


async def test_insert_and_fetch_by_id_round_trip(session: AsyncSession) -> None:
    decision = _make_decision()
    await DecisionRepo.insert(session, decision)
    await session.commit()
    fetched = await DecisionRepo.fetch_by_id(session, decision.decision_id)
    assert fetched is not None
    assert fetched.decision_id == decision.decision_id
    assert fetched.case_id == decision.case_id
    assert fetched.outcome == "approve"
    assert fetched.rationale_html == decision.rationale_html


async def test_fetch_latest_by_case_returns_most_recent(session: AsyncSession) -> None:
    older = _make_decision(decision_id="dec_old", committed_at=datetime.now(UTC) - timedelta(hours=1))
    newer = _make_decision(decision_id="dec_new", committed_at=datetime.now(UTC))
    await DecisionRepo.insert(session, older)
    await DecisionRepo.insert(session, newer)
    await session.commit()
    latest = await DecisionRepo.fetch_latest_by_case(session, VORA_CAPITAL_ID)
    assert latest is not None
    assert latest.decision_id == "dec_new"


async def test_update_sealed_populates_seal_fields(session: AsyncSession) -> None:
    decision = _make_decision()
    await DecisionRepo.insert(session, decision)
    await session.commit()
    seal_at = datetime.now(UTC)
    await DecisionRepo.update_sealed(
        session,
        decision.decision_id,
        seal_at,
        "led_01HXY3GHJKMNPQRSTVWXYZ7HX2",
    )
    await session.commit()
    fetched = await DecisionRepo.fetch_by_id(session, decision.decision_id)
    assert fetched is not None
    assert fetched.sealed_at is not None
    assert fetched.sealed_ledger_entry_id == "led_01HXY3GHJKMNPQRSTVWXYZ7HX2"


async def test_delete_by_id_removes_row(session: AsyncSession) -> None:
    decision = _make_decision()
    await DecisionRepo.insert(session, decision)
    await session.commit()
    await DecisionRepo.delete_by_id(session, decision.decision_id)
    await session.commit()
    assert await DecisionRepo.fetch_by_id(session, decision.decision_id) is None


async def test_fetch_by_id_returns_none_for_missing(session: AsyncSession) -> None:
    assert await DecisionRepo.fetch_by_id(session, "dec_missing") is None
