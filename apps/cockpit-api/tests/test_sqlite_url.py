"""Verify the SQLite + aiosqlite engine works end-to-end (Story 1.5 AC #2)."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.asyncio
async def test_sqlite_aiosqlite_engine_executes_select_one(tmp_path: pytest.TempPathFactory) -> None:
    db_file = tmp_path / "smoke.db"  # type: ignore[operator]
    url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_async_engine(url, future=True)
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1 AS v"))
            row = result.first()
            assert row is not None
            assert row.v == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_sqlite_engine_persists_data_across_connections(
    tmp_path: pytest.TempPathFactory,
) -> None:
    db_file = tmp_path / "persist.db"  # type: ignore[operator]
    url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_async_engine(url, future=True)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)"))
            await conn.execute(text("INSERT INTO t (id, name) VALUES (1, 'demo')"))
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT name FROM t WHERE id = 1"))
            row = result.first()
            assert row is not None
            assert row.name == "demo"
    finally:
        await engine.dispose()
