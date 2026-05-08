"""Tests for the Risk recalc background task — Story 5.8 / AC #7."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from contracts.cases import (
    VORA_CAPITAL_ID,
    Case,
    get_demo_case_fixtures,
)
from contracts.sse import SseEvent
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from cockpit_api.db import session as session_mod
from cockpit_api.db.models import Base
from cockpit_api.repositories.case_repo import CaseRepo
from cockpit_api.repositories.intake_repo import IntakeRepo
from cockpit_api.services import ledger_service, sse_registry
from cockpit_api.services.ledger_service import LedgerReader, LedgerWriter
from cockpit_api.services.risk_recalc_service import run_risk_recalc
from tests.fixtures.ubo_graph_vora import (
    COASTAL_ID,
    make_vora_graph,
)


@pytest_asyncio.fixture
async def engine_with_app(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(eng, expire_on_commit=False)
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

    monkeypatch.setattr(deco, "get_ledger_writer", lambda: writer)
    yield writer


def _session_factory(engine: AsyncEngine):  # type: ignore[no-untyped-def]
    factory = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def _f() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    return _f


async def _seed_vora_with_intake(engine: AsyncEngine) -> Case:
    """Seed Vora's case + a pre-built UBO graph (3 nominee_suspected edges) +
    an initial risk_scoring row matching pre-correction state."""
    fixtures = get_demo_case_fixtures(datetime.now(UTC))
    target = next(c for c in fixtures if c.id == VORA_CAPITAL_ID)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await CaseRepo.insert(session, target)
        await IntakeRepo.upsert(session, target.id, "ubo_graph", make_vora_graph())
        await session.commit()
    return target


# ───────────── happy path ─────────────


async def test_recalc_persists_new_score(engine_with_app: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    case = await _seed_vora_with_intake(engine_with_app)
    await run_risk_recalc(
        case_id=case.id,
        session_factory=_session_factory(engine_with_app),
    )
    factory = async_sessionmaker(engine_with_app, expire_on_commit=False)
    async with factory() as session:
        row = await IntakeRepo.get_one(session, case.id, "risk_scoring")
        assert row is not None
        # Pre-correction Vora has 3 nominee_suspected → ownership_clarity 70 → band medium.
        assert row["band"] == "medium"
        # cases.risk_band denormalized: medium → medium_high
        case_after = await CaseRepo.get(session, case.id)
        assert case_after is not None
        assert case_after.risk_band == "medium_high"


async def test_recalc_after_correction_drops_band_to_low(
    engine_with_app: AsyncEngine, tmp_writer: LedgerWriter
) -> None:
    """Officer flips Coastal to officer_corrected → recalc → band low."""
    case = await _seed_vora_with_intake(engine_with_app)
    factory = async_sessionmaker(engine_with_app, expire_on_commit=False)

    # Mutate the persisted graph to flip Coastal.
    graph = make_vora_graph()
    new_edges = []
    for edge in graph.edges:
        if edge.from_id == COASTAL_ID and edge.kind == "owns":
            new_edges.append(edge.model_copy(update={"nominee_flag": "officer_corrected"}))
        else:
            new_edges.append(edge)
    corrected = graph.model_copy(update={"edges": new_edges})
    async with factory() as session:
        await IntakeRepo.upsert(session, case.id, "ubo_graph", corrected)
        await session.commit()

    await run_risk_recalc(
        case_id=case.id,
        session_factory=_session_factory(engine_with_app),
    )
    async with factory() as session:
        row = await IntakeRepo.get_one(session, case.id, "risk_scoring")
        assert row is not None
        assert row["band"] == "low"
        case_after = await CaseRepo.get(session, case.id)
        assert case_after is not None
        assert case_after.risk_band == "low"


# ───────────── ledger entries ─────────────


async def test_recalc_writes_new_agent_completed_entry(engine_with_app: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    case = await _seed_vora_with_intake(engine_with_app)
    # First recalc.
    await run_risk_recalc(
        case_id=case.id,
        session_factory=_session_factory(engine_with_app),
    )
    # Second recalc — appends a fresh entry; doesn't rewrite the first.
    await run_risk_recalc(
        case_id=case.id,
        session_factory=_session_factory(engine_with_app),
    )
    entries = await LedgerReader(tmp_writer._path).read_for_case(case.id)
    risk_entries = [e for e in entries if e.action == "agent.completed" and e.actor_id == "risk_scoring"]
    assert len(risk_entries) == 2


# ───────────── missing UBO graph guard ─────────────


async def test_recalc_silent_on_missing_ubo_graph(engine_with_app: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    """No UBO graph in IntakeRepo — recalc logs + returns without raising."""
    fixtures = get_demo_case_fixtures(datetime.now(UTC))
    target = next(c for c in fixtures if c.id == VORA_CAPITAL_ID)
    factory = async_sessionmaker(engine_with_app, expire_on_commit=False)
    async with factory() as session:
        await CaseRepo.insert(session, target)
        await session.commit()
    # No exception raised.
    await run_risk_recalc(
        case_id=target.id,
        session_factory=_session_factory(engine_with_app),
    )
    # No risk_scoring row persisted.
    async with factory() as session:
        row = await IntakeRepo.get_one(session, target.id, "risk_scoring")
        assert row is None


# ───────────── missing case ─────────────


async def test_recalc_silent_on_missing_case(engine_with_app: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    await run_risk_recalc(
        case_id=VORA_CAPITAL_ID,
        session_factory=_session_factory(engine_with_app),
    )


# ───────────── SSE event ─────────────


async def test_recalc_publishes_sse_event(engine_with_app: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    captured: list[tuple[str | None, SseEvent]] = []

    class _CapturingRegistry:
        async def publish(self, case_id: str | None, event: SseEvent) -> None:
            captured.append((case_id, event))

    sse_registry.get_sse_registry.cache_clear()
    case = await _seed_vora_with_intake(engine_with_app)

    # Patch the global registry getter so publish_safe routes here.
    import cockpit_api.services.sse_registry as sse_mod

    original = sse_mod.get_sse_registry
    sse_mod.get_sse_registry = lambda: _CapturingRegistry()  # type: ignore[assignment]
    try:
        await run_risk_recalc(
            case_id=case.id,
            session_factory=_session_factory(engine_with_app),
        )
    finally:
        sse_mod.get_sse_registry = original

    risk_events = [e for cid, e in captured if e.event == "case.risk_recalculated"]
    assert len(risk_events) == 1
    payload: dict[str, Any] = risk_events[0].data
    assert payload["case_id"] == case.id
    assert payload["band"] in ("low", "medium", "high")
    assert isinstance(payload["total"], int)


# ───────────── idempotency ─────────────


async def test_recalc_is_deterministic(engine_with_app: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    case = await _seed_vora_with_intake(engine_with_app)
    factory = async_sessionmaker(engine_with_app, expire_on_commit=False)

    await run_risk_recalc(
        case_id=case.id,
        session_factory=_session_factory(engine_with_app),
    )
    async with factory() as session:
        first = await IntakeRepo.get_one(session, case.id, "risk_scoring")
        assert first is not None
        first_total = first["total"]

    await run_risk_recalc(
        case_id=case.id,
        session_factory=_session_factory(engine_with_app),
    )
    async with factory() as session:
        second = await IntakeRepo.get_one(session, case.id, "risk_scoring")
        assert second is not None
        assert second["total"] == first_total
        assert second["band"] == first["band"]


# ───────────── error swallowing ─────────────


async def test_recalc_swallows_agent_execution_error(
    engine_with_app: AsyncEngine,
    tmp_writer: LedgerWriter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = await _seed_vora_with_intake(engine_with_app)

    async def boom(*_args: Any, **_kwargs: Any) -> Any:
        from agents.supervisor.action_decorator import AgentExecutionError

        raise AgentExecutionError(
            agent_id="risk_scoring",
            case_id=case.id,
            original=RuntimeError("forced"),
        )

    import cockpit_api.services.risk_recalc_service as recalc_mod

    monkeypatch.setattr(recalc_mod, "risk_scoring", boom)
    # Doesn't raise.
    await run_risk_recalc(
        case_id=case.id,
        session_factory=_session_factory(engine_with_app),
    )
