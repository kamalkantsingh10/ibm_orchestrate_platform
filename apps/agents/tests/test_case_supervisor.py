"""Tests for CaseSupervisor — Story 3.5 / AC #10."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from cockpit_api.db.models import Base
from cockpit_api.repositories.case_repo import CaseRepo
from cockpit_api.repositories.intake_repo import IntakeRepo
from cockpit_api.services import ledger_service
from cockpit_api.services.ledger_service import LedgerReader, LedgerWriter
from contracts.cases import (
    SHREE_VENKAT_ID,
    VORA_CAPITAL_ID,
    Case,
    CaseState,
    CustomerMetadata,
    get_demo_case_fixtures,
)
from contracts.document_intelligence import DocumentIntelligenceOutput
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import agents.supervisor.case_supervisor as supervisor_mod
from agents.supervisor.action_decorator import AgentExecutionError
from agents.supervisor.case_supervisor import (
    CaseNotFoundError,
    CaseNotIntakeReadyError,
    CaseSupervisor,
    _fill_evidence_ids,
)


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest.fixture
def tmp_writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[LedgerWriter]:
    """Bind ledger singletons to a tmp file for the test."""
    path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path)
    reader = LedgerReader(path)
    ledger_service.get_ledger_writer.cache_clear()
    ledger_service.get_ledger_reader.cache_clear()
    monkeypatch.setattr(ledger_service, "get_ledger_writer", lambda: writer)
    monkeypatch.setattr(ledger_service, "get_ledger_reader", lambda: reader)
    import agents.supervisor.action_decorator as deco

    monkeypatch.setattr(deco, "get_ledger_writer", lambda: writer)
    # The supervisor imports get_ledger_writer / get_ledger_reader by name,
    # so patching the source module isn't enough — patch the binding inside
    # the supervisor module too.
    monkeypatch.setattr(supervisor_mod, "get_ledger_writer", lambda: writer)
    monkeypatch.setattr(supervisor_mod, "get_ledger_reader", lambda: reader)
    yield writer


def _session_factory_for(
    engine: AsyncEngine,
) -> Any:
    factory = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def _f() -> AsyncIterator[AsyncSession]:
        async with factory() as s:
            yield s

    return _f


async def _seed_case(engine: AsyncEngine, *, state: CaseState = CaseState.INTAKE_SCHEDULED) -> Case:
    """Insert one demo case into the DB and return its contract."""
    cases = get_demo_case_fixtures(datetime.now(UTC))
    target = next(c for c in cases if c.id == VORA_CAPITAL_ID)
    if state is not CaseState.INTAKE_SCHEDULED:
        target = target.model_copy(update={"state": state})
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await CaseRepo.insert(session, target)
        await session.commit()
    return target


# ───────────── happy path ─────────────


async def test_happy_path_completes_and_persists(engine: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    case = await _seed_case(engine)
    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    outcome = await supervisor.run_intake(case.id)

    assert outcome.status == "completed"
    assert outcome.agents_run == ["document_intelligence"]
    assert outcome.fields_extracted > 0
    assert outcome.failed_agent is None

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        refreshed = await CaseRepo.get(session, case.id)
        assert refreshed is not None
        assert refreshed.state is CaseState.DECISION_READY
        row = await IntakeRepo.get_one(session, case.id, "document_intelligence")
        assert row is not None
        revived = DocumentIntelligenceOutput.model_validate(row)
        assert len(revived.extracted_fields) == outcome.fields_extracted
        for f in revived.extracted_fields:
            assert len(f.value.provenance.evidence_ids) == 1
            assert f.value.provenance.evidence_ids[0].startswith("led_")


# ───────────── agent failure ─────────────


async def test_agent_failure_via_agent_execution_error(
    engine: AsyncEngine, tmp_writer: LedgerWriter, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = await _seed_case(engine)

    async def boom(_: Any) -> Any:
        raise AgentExecutionError(
            agent_id="document_intelligence",
            case_id=case.id,
            original=ValueError("doc-ai down"),
        )

    monkeypatch.setattr(supervisor_mod, "document_intelligence", boom)

    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    outcome = await supervisor.run_intake(case.id)

    assert outcome.status == "blocked"
    assert outcome.failed_agent == "document_intelligence"
    assert "doc-ai down" in (outcome.error_message or "")
    assert outcome.fields_extracted == 0

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        refreshed = await CaseRepo.get(session, case.id)
        assert refreshed is not None
        assert refreshed.state is CaseState.ESCALATED
        assert refreshed.customer_metadata.extra.get("blocked_agent") == "document_intelligence"
        assert "doc-ai down" in refreshed.customer_metadata.extra.get("block_reason", "")


# ───────────── empty document_refs ─────────────


async def test_empty_document_refs_completes_with_zero_fields(engine: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    # Build a case with no document_refs
    now = datetime.now(UTC)
    case = Case(
        id=SHREE_VENKAT_ID,
        state=CaseState.INTAKE_SCHEDULED,
        customer_metadata=CustomerMetadata(customer_name="Empty Co", extra={}),
        created_at=now,
        updated_at=now,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await CaseRepo.insert(session, case)
        await session.commit()

    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    outcome = await supervisor.run_intake(case.id)

    assert outcome.status == "completed"
    assert outcome.agents_run == []  # spec.requires returned False; agent skipped
    assert outcome.fields_extracted == 0


# ───────────── missing case ─────────────


async def test_missing_case_raises(engine: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    with pytest.raises(CaseNotFoundError):
        await supervisor.run_intake(VORA_CAPITAL_ID)


# ───────────── wrong state ─────────────


async def test_wrong_state_raises(engine: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    case = await _seed_case(engine, state=CaseState.DECISION_READY)
    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    with pytest.raises(CaseNotIntakeReadyError):
        await supervisor.run_intake(case.id)


# ───────────── idempotency ─────────────


async def test_second_run_raises_not_intake_ready(engine: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    case = await _seed_case(engine)
    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    first = await supervisor.run_intake(case.id)
    assert first.status == "completed"
    with pytest.raises(CaseNotIntakeReadyError):
        await supervisor.run_intake(case.id)


# ───────────── _fill_evidence_ids helper ─────────────


def test_fill_evidence_ids_helper(tmp_writer: LedgerWriter) -> None:
    from contracts.confidence import to_band
    from contracts.document_intelligence import ExtractedField
    from contracts.provenance import Provenance, ProvenancedField
    from ulid import ULID

    led_id = f"led_{ULID()!s}"
    pf: ProvenancedField[str | int | float | bool | None] = ProvenancedField(
        value="X",
        provenance=Provenance(
            source_agent="document_intelligence",
            source_system="fixture_doc_ai",
            confidence=0.9,
            confidence_band=to_band(0.9),
            evidence_ids=[],
            captured_at=datetime.now(UTC),
        ),
    )
    out = DocumentIntelligenceOutput(
        case_id=VORA_CAPITAL_ID,
        extracted_fields=[
            ExtractedField(field_name="x", document_ref="a.pdf", value=pf),
            ExtractedField(field_name="y", document_ref="b.pdf", value=pf),
        ],
    )
    filled = _fill_evidence_ids(out, led_id)
    assert all(f.value.provenance.evidence_ids == [led_id] for f in filled.extracted_fields)
    # Original unchanged (frozen)
    assert all(f.value.provenance.evidence_ids == [] for f in out.extracted_fields)


# ───────────── ledger entries ─────────────


async def test_completed_writes_intake_completed_entry(engine: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    case = await _seed_case(engine)
    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    await supervisor.run_intake(case.id)

    reader = LedgerReader(tmp_writer._path)
    entries = await reader.read_for_case(case.id)
    actions = [e.action for e in entries]
    assert "case.intake_completed" in actions
    completed_entry = next(e for e in entries if e.action == "case.intake_completed")
    assert completed_entry.actor_id == "case_supervisor"
    assert isinstance(completed_entry.payload, dict)
    assert completed_entry.payload.get("agents") == ["document_intelligence"]


async def test_blocked_writes_intake_blocked_entry(
    engine: AsyncEngine, tmp_writer: LedgerWriter, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = await _seed_case(engine)

    async def boom(_: Any) -> Any:
        raise AgentExecutionError(
            agent_id="document_intelligence",
            case_id=case.id,
            original=RuntimeError("nope"),
        )

    monkeypatch.setattr(supervisor_mod, "document_intelligence", boom)

    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    await supervisor.run_intake(case.id)

    reader = LedgerReader(tmp_writer._path)
    entries = await reader.read_for_case(case.id)
    actions = [e.action for e in entries]
    assert "case.intake_blocked" in actions


# ───────────── notify hook ─────────────


async def test_notify_hook_called_on_completion(engine: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    case = await _seed_case(engine)
    calls: list[tuple[str, str, dict[str, Any]]] = []

    async def notify(case_id: str, event: str, payload: dict[str, Any]) -> None:
        calls.append((case_id, event, payload))

    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine), notify=notify)
    await supervisor.run_intake(case.id)

    assert len(calls) == 1
    assert calls[0][0] == case.id
    assert calls[0][1] == "case.intake_completed"
