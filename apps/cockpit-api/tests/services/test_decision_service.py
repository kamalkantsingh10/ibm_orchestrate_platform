"""Tests for ``decision_service`` — Story 7.7 / AC #9."""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from contracts.agent_action import AgentActionLedgerEntry
from contracts.cases import VORA_CAPITAL_ID, Case, CaseState, CustomerMetadata
from contracts.decision import CommitDecisionRequest
from contracts.ledger import (
    DecisionSealedPayload,
    OfficerDecisionCommittedPayload,
)
from contracts.sse import SseEvent
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from cockpit_api.db.models import Base
from cockpit_api.repositories.case_repo import CaseRepo
from cockpit_api.repositories.decision_repo import DecisionRepo
from cockpit_api.services import ledger_service
from cockpit_api.services.decision_service import (
    CaseNotFoundError,
    DecisionConflictError,
    commit_decision,
    seal_decision,
)
from cockpit_api.services.decision_timer import DecisionTimerService
from cockpit_api.services.ledger_service import LedgerReader, LedgerWriter


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s


@pytest.fixture
def writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LedgerWriter:
    p = tmp_path / "ledger.jsonl"
    w = LedgerWriter(p)
    ledger_service.get_ledger_writer.cache_clear()
    monkeypatch.setattr(ledger_service, "get_ledger_writer", lambda: w)
    return w


def _seed_decision_ready_case() -> Case:
    now = datetime.now(UTC)
    return Case(
        id=VORA_CAPITAL_ID,
        state=CaseState.DECISION_READY,
        customer_metadata=CustomerMetadata(
            customer_name="Vora Capital Holdings Pvt Ltd",
            customer_type="company",
            country="IN",
        ),
        created_at=now,
        updated_at=now,
    )


def _make_body(**overrides: Any) -> CommitDecisionRequest:
    base: dict[str, Any] = {
        "outcome": "approve",
        "conditions": [],
        "rationale_html": "<p>Approve based on screening hits.</p>",
    }
    base.update(overrides)
    return CommitDecisionRequest(**base)


def _make_publish() -> tuple[list[tuple[str | None, SseEvent]], Any]:
    calls: list[tuple[str | None, SseEvent]] = []

    async def publish(case_id: str | None, event: SseEvent) -> None:
        calls.append((case_id, event))

    return calls, publish


def _make_timer_stub() -> tuple[list[tuple[str, str]], DecisionTimerService]:
    calls: list[tuple[str, str]] = []

    async def _noop(case_id: str, decision_id: str) -> None:
        return None

    timer = DecisionTimerService(on_seal=_noop, window_seconds=60)
    original_schedule = timer.schedule

    def _record_schedule(case_id: str, decision_id: str) -> None:
        calls.append((case_id, decision_id))
        original_schedule(case_id, decision_id)

    timer.schedule = _record_schedule  # type: ignore[method-assign]
    return calls, timer


# ───────────── commit_decision ─────────────


async def test_commit_happy_path_writes_ledger_persists_row_schedules_timer(
    session: AsyncSession,
    writer: LedgerWriter,
) -> None:
    case = _seed_decision_ready_case()
    await CaseRepo.insert(session, case)
    await session.commit()

    sse_calls, publish = _make_publish()
    timer_calls, timer = _make_timer_stub()

    response = await commit_decision(
        session=session,
        case_id=case.id,
        body=_make_body(),
        user_id="user_analyst",
        writer=writer,
        sse_publish=publish,
        timer=timer,
    )
    assert response.case_state == CaseState.PENDING_SEAL
    assert response.decision_id.startswith("dec_")
    assert response.ledger_entry_id.startswith("led_")
    assert response.seal_at - datetime.now(UTC) > timedelta(seconds=110)

    refreshed = await CaseRepo.get(session, case.id)
    assert refreshed is not None and refreshed.state is CaseState.PENDING_SEAL

    decision = await DecisionRepo.fetch_by_id(session, response.decision_id)
    assert decision is not None
    assert decision.outcome == "approve"
    assert decision.committed_ledger_entry_id == response.ledger_entry_id

    assert timer_calls == [(case.id, response.decision_id)]
    timer.cancel(case.id)

    assert any(evt.event == "decision.committed" for _, evt in sse_calls)

    entries = await LedgerReader(writer._path).read_for_case(case.id)
    committed = [e for e in entries if isinstance(e.payload, OfficerDecisionCommittedPayload)]
    assert len(committed) == 1
    payload = committed[0].payload
    assert isinstance(payload, OfficerDecisionCommittedPayload)
    expected_hash = hashlib.sha256(b"<p>Approve based on screening hits.</p>").hexdigest()
    assert payload.rationale_hash == expected_hash


async def test_commit_rejects_intake_scheduled(
    session: AsyncSession,
    writer: LedgerWriter,
) -> None:
    case = _seed_decision_ready_case().model_copy(update={"state": CaseState.INTAKE_SCHEDULED})
    await CaseRepo.insert(session, case)
    await session.commit()
    _, publish = _make_publish()
    _, timer = _make_timer_stub()
    with pytest.raises(DecisionConflictError):
        await commit_decision(
            session=session,
            case_id=case.id,
            body=_make_body(),
            user_id="user_analyst",
            writer=writer,
            sse_publish=publish,
            timer=timer,
        )


async def test_commit_rejects_pending_seal(
    session: AsyncSession,
    writer: LedgerWriter,
) -> None:
    case = _seed_decision_ready_case().model_copy(update={"state": CaseState.PENDING_SEAL})
    await CaseRepo.insert(session, case)
    await session.commit()
    _, publish = _make_publish()
    _, timer = _make_timer_stub()
    with pytest.raises(DecisionConflictError):
        await commit_decision(
            session=session,
            case_id=case.id,
            body=_make_body(),
            user_id="user_analyst",
            writer=writer,
            sse_publish=publish,
            timer=timer,
        )


async def test_commit_rejects_committed(
    session: AsyncSession,
    writer: LedgerWriter,
) -> None:
    case = _seed_decision_ready_case().model_copy(update={"state": CaseState.COMMITTED})
    await CaseRepo.insert(session, case)
    await session.commit()
    _, publish = _make_publish()
    _, timer = _make_timer_stub()
    with pytest.raises(DecisionConflictError):
        await commit_decision(
            session=session,
            case_id=case.id,
            body=_make_body(),
            user_id="user_analyst",
            writer=writer,
            sse_publish=publish,
            timer=timer,
        )


async def test_commit_raises_case_not_found_when_case_missing(
    session: AsyncSession,
    writer: LedgerWriter,
) -> None:
    _, publish = _make_publish()
    _, timer = _make_timer_stub()
    with pytest.raises(CaseNotFoundError):
        await commit_decision(
            session=session,
            case_id=VORA_CAPITAL_ID,
            body=_make_body(),
            user_id="user_analyst",
            writer=writer,
            sse_publish=publish,
            timer=timer,
        )


async def test_commit_rationale_hash_is_sha256_of_body(
    session: AsyncSession,
    writer: LedgerWriter,
) -> None:
    case = _seed_decision_ready_case()
    await CaseRepo.insert(session, case)
    await session.commit()
    _, publish = _make_publish()
    _, timer = _make_timer_stub()
    rationale = "<p>Specific rationale text the hash anchors against.</p>"
    response = await commit_decision(
        session=session,
        case_id=case.id,
        body=_make_body(rationale_html=rationale),
        user_id="user_analyst",
        writer=writer,
        sse_publish=publish,
        timer=timer,
    )
    timer.cancel(case.id)
    entries = await LedgerReader(writer._path).read_for_case(case.id)
    payload = next(e.payload for e in entries if isinstance(e.payload, OfficerDecisionCommittedPayload))
    assert isinstance(payload, OfficerDecisionCommittedPayload)
    assert payload.rationale_hash == hashlib.sha256(rationale.encode()).hexdigest()
    # Decision row stored too.
    assert (await DecisionRepo.fetch_by_id(session, response.decision_id)) is not None


# ───────────── seal_decision ─────────────


async def test_seal_decision_writes_sealed_entry_and_transitions_state(
    engine: AsyncEngine,
    session: AsyncSession,
    writer: LedgerWriter,
) -> None:
    case = _seed_decision_ready_case()
    await CaseRepo.insert(session, case)
    await session.commit()
    _, commit_publish = _make_publish()
    _, timer = _make_timer_stub()
    response = await commit_decision(
        session=session,
        case_id=case.id,
        body=_make_body(),
        user_id="user_analyst",
        writer=writer,
        sse_publish=commit_publish,
        timer=timer,
    )
    timer.cancel(case.id)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def _session_factory() -> AsyncIterator[AsyncSession]:
        async with factory() as s:
            yield s

    seal_calls, seal_publish = _make_publish()
    await seal_decision(
        case_id=case.id,
        decision_id=response.decision_id,
        session_factory=_session_factory,
        writer=writer,
        sse_publish=seal_publish,
    )

    refreshed = await CaseRepo.get(session, case.id)
    assert refreshed is not None and refreshed.state is CaseState.COMMITTED

    decision = await DecisionRepo.fetch_by_id(session, response.decision_id)
    assert decision is not None and decision.sealed_at is not None
    assert decision.sealed_ledger_entry_id is not None

    entries = await LedgerReader(writer._path).read_for_case(case.id)
    sealed = [e for e in entries if isinstance(e.payload, DecisionSealedPayload)]
    assert len(sealed) == 1
    assert any(evt.event == "decision.sealed" for _, evt in seal_calls)


async def test_seal_decision_idempotent_when_already_sealed(
    engine: AsyncEngine,
    session: AsyncSession,
    writer: LedgerWriter,
) -> None:
    case = _seed_decision_ready_case()
    await CaseRepo.insert(session, case)
    await session.commit()
    _, publish = _make_publish()
    _, timer = _make_timer_stub()
    response = await commit_decision(
        session=session,
        case_id=case.id,
        body=_make_body(),
        user_id="user_analyst",
        writer=writer,
        sse_publish=publish,
        timer=timer,
    )
    timer.cancel(case.id)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def _session_factory() -> AsyncIterator[AsyncSession]:
        async with factory() as s:
            yield s

    seal_calls, seal_publish = _make_publish()
    await seal_decision(
        case_id=case.id,
        decision_id=response.decision_id,
        session_factory=_session_factory,
        writer=writer,
        sse_publish=seal_publish,
    )
    # Second call — no double-seal.
    await seal_decision(
        case_id=case.id,
        decision_id=response.decision_id,
        session_factory=_session_factory,
        writer=writer,
        sse_publish=seal_publish,
    )
    entries = await LedgerReader(writer._path).read_for_case(case.id)
    sealed = [e for e in entries if isinstance(e.payload, DecisionSealedPayload)]
    assert len(sealed) == 1
    # SSE only fires once.
    seal_events = [evt for _, evt in seal_calls if evt.event == "decision.sealed"]
    assert len(seal_events) == 1


async def test_seal_decision_idempotent_when_decision_missing(
    engine: AsyncEngine,
    writer: LedgerWriter,
) -> None:
    factory = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def _session_factory() -> AsyncIterator[AsyncSession]:
        async with factory() as s:
            yield s

    seal_calls, publish = _make_publish()
    await seal_decision(
        case_id=VORA_CAPITAL_ID,
        decision_id="dec_does_not_exist",
        session_factory=_session_factory,
        writer=writer,
        sse_publish=publish,
    )
    assert seal_calls == []


def _ignore_unused() -> None:
    # Silence unused-import warnings for AgentActionLedgerEntry which is
    # referenced in some test variants but not in the final shape here.
    _ = AgentActionLedgerEntry
