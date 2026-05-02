"""Async SQLAlchemy engine + session — Story 2.1.

A single engine is created lazily on first ``get_session()`` call. The
``get_session`` FastAPI dependency yields an ``AsyncSession`` that is
committed on success, rolled back on exception, and always closed.

Tests override ``get_session`` with a fixture that builds an in-memory
SQLite engine — see ``apps/cockpit-api/tests/test_case_repo.py``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from cockpit_api.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _ensure_engine() -> async_sessionmaker[AsyncSession]:
    global _engine, _sessionmaker
    if _sessionmaker is None:
        settings = get_settings()
        _engine = create_async_engine(settings.database_url, future=True)
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _sessionmaker


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Public accessor for the process-wide sessionmaker.

    Used by Story 3.5's CaseSupervisor route handler, which needs to spin
    up its own session inside the supervisor's context-manager protocol
    (rather than reusing the FastAPI request session, which commits on
    exit and would interfere with the supervisor's transactional flow).
    """
    return _ensure_engine()


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding an ``AsyncSession``.

    Commits on clean exit, rolls back on exception, always closes.
    """
    factory = _ensure_engine()
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def dispose_engine() -> None:
    """Tear down the engine — used in tests and shutdown hooks."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None
