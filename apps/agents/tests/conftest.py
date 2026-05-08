"""Shared fixtures for agent tests — Stories 3.2/3.5/5.1."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from cockpit_api.db.models import Base
from cockpit_api.services import ledger_service
from cockpit_api.services.ledger_service import LedgerReader, LedgerWriter
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import agents.supervisor.action_decorator as deco
import agents.supervisor.case_supervisor as supervisor_mod


@pytest.fixture
def tmp_writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[LedgerWriter]:
    """Bind ledger singletons to a tmp file for the duration of the test.

    Both the action decorator (which writes ``agent.completed`` /
    ``agent.failed`` entries) and the supervisor (which writes the
    ``case.intake_*`` system entries) are patched to the same tmp file so
    a single test can assert the full transcript.
    """
    path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path)
    reader = LedgerReader(path)
    ledger_service.get_ledger_writer.cache_clear()
    ledger_service.get_ledger_reader.cache_clear()
    monkeypatch.setattr(ledger_service, "get_ledger_writer", lambda: writer)
    monkeypatch.setattr(ledger_service, "get_ledger_reader", lambda: reader)
    monkeypatch.setattr(deco, "get_ledger_writer", lambda: writer)
    monkeypatch.setattr(supervisor_mod, "get_ledger_writer", lambda: writer)
    monkeypatch.setattr(supervisor_mod, "get_ledger_reader", lambda: reader)
    yield writer


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    """In-memory SQLite engine with the demo schema applied."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest.fixture
def make_test_session(engine: AsyncEngine) -> Any:
    """Yields a session-factory tied to the test's engine."""
    factory = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def _factory() -> AsyncIterator[AsyncSession]:
        async with factory() as s:
            yield s

    return _factory
