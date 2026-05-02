"""Unit tests for seed_dev helpers (Story 1.5 + Story 2.4)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest_asyncio
from contracts.cases import (
    ANANYA_IYER_ID,
    SHREE_VENKAT_ID,
    VORA_CAPITAL_ID,
    CustomerMetadata,
    get_demo_case_fixtures,
)
from scripts.seed_dev import _missing_table_error, _seed_cases
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
)

from cockpit_api.db.models import Base


def _op_error(msg: str) -> OperationalError:
    """Build an OperationalError with a controlled message."""
    return OperationalError(statement=None, params=None, orig=Exception(msg))


def test_missing_table_error_matches_sqlite_message() -> None:
    err = _op_error("no such table: tenants")
    assert _missing_table_error(err, "tenants")


def test_missing_table_error_is_table_specific() -> None:
    err = _op_error("no such table: tenants")
    assert not _missing_table_error(err, "officers")


def test_missing_table_error_returns_false_for_unrelated_op_error() -> None:
    err = _op_error("disk I/O error")
    assert not _missing_table_error(err, "tenants")


# ───────────── Story 2.4 — _seed_cases ─────────────


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        await eng.dispose()


_FROZEN_NOW = datetime(2026, 4, 30, 12, 0, 0, tzinfo=UTC)


async def test_seed_inserts_three_cases(engine: AsyncEngine) -> None:
    fixtures = get_demo_case_fixtures(_FROZEN_NOW)
    async with engine.begin() as conn:
        result = await _seed_cases(conn, fixtures)
        assert result is True

    async with engine.connect() as conn:
        rows = (await conn.execute(text("SELECT id FROM cases"))).all()
        ids = {r.id for r in rows}
    assert ids == {SHREE_VENKAT_ID, VORA_CAPITAL_ID, ANANYA_IYER_ID}


async def test_seed_cases_idempotent(engine: AsyncEngine) -> None:
    fixtures = get_demo_case_fixtures(_FROZEN_NOW)
    async with engine.begin() as conn:
        await _seed_cases(conn, fixtures)
    async with engine.begin() as conn:
        await _seed_cases(conn, fixtures)

    async with engine.connect() as conn:
        count = (await conn.execute(text("SELECT COUNT(*) AS n FROM cases"))).scalar_one()
    assert count == 3


async def test_seed_cases_skips_when_table_missing() -> None:
    """When the table is absent, _seed_cases logs and returns False."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    try:
        # Note: deliberately NOT running Base.metadata.create_all.
        async with eng.begin() as conn:
            result = await _seed_cases(conn, get_demo_case_fixtures(_FROZEN_NOW))
        assert result is False
    finally:
        await eng.dispose()


async def test_seed_cases_customer_metadata_round_trips(engine: AsyncEngine) -> None:
    fixtures = get_demo_case_fixtures(_FROZEN_NOW)
    async with engine.begin() as conn:
        await _seed_cases(conn, fixtures)

    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT customer_metadata FROM cases WHERE id = :id"),
                {"id": SHREE_VENKAT_ID},
            )
        ).first()

    assert row is not None
    raw = row.customer_metadata
    payload = raw if isinstance(raw, dict) else json.loads(raw)
    revived = CustomerMetadata.model_validate(payload)
    assert revived.customer_name == "Shree Venkat Trading"


async def test_seed_cases_ordering(engine: AsyncEngine) -> None:
    fixtures = get_demo_case_fixtures(_FROZEN_NOW)
    async with engine.begin() as conn:
        await _seed_cases(conn, fixtures)

    async with engine.connect() as conn:
        rows = (await conn.execute(text("SELECT id FROM cases ORDER BY created_at DESC"))).all()
    ids = [r.id for r in rows]
    assert ids == [ANANYA_IYER_ID, VORA_CAPITAL_ID, SHREE_VENKAT_ID]


async def test_seed_cases_partial_state_recovers(engine: AsyncEngine) -> None:
    """If only one fixture is present, INSERT OR IGNORE inserts the other two."""
    fixtures = get_demo_case_fixtures(_FROZEN_NOW)
    # Pre-insert just Shree by hand.
    shree = next(c for c in fixtures if c.id == SHREE_VENKAT_ID)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO cases (id, state, customer_metadata, created_at, updated_at) "
                "VALUES (:id, :state, :md, :ts, :ts)"
            ),
            {
                "id": shree.id,
                "state": shree.state.value,
                "md": shree.customer_metadata.model_dump_json(),
                "ts": shree.created_at,
            },
        )

    async with engine.begin() as conn:
        await _seed_cases(conn, fixtures)

    async with engine.connect() as conn:
        rows = (await conn.execute(text("SELECT id FROM cases"))).all()
    assert {r.id for r in rows} == {SHREE_VENKAT_ID, VORA_CAPITAL_ID, ANANYA_IYER_ID}
