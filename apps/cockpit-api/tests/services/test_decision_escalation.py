"""Tests for Story 8.7 — EDD outcome auto-enqueue for Lead approval."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import pytest
import pytest_asyncio
from contracts.cases import VORA_CAPITAL_ID, Case, CaseState, CustomerMetadata
from contracts.decision import CommitDecisionRequest
from contracts.ledger import EscalatedForApprovalPayload
from contracts.sse import SseEvent
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from cockpit_api.db.models import Base
from cockpit_api.repositories.case_repo import CaseRepo
from cockpit_api.services import ledger_service
from cockpit_api.services.decision_service import commit_decision
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


def _seed_case(
    *,
    risk_band: Literal["low", "medium_low", "medium_high", "high"] | None = None,
) -> Case:
    now = datetime.now(UTC)
    return Case(
        id=VORA_CAPITAL_ID,
        state=CaseState.DECISION_READY,
        customer_metadata=CustomerMetadata(
            customer_name="Vora Capital Holdings Pvt Ltd",
            customer_type="company",
            country="IN",
        ),
        risk_band=risk_band,
        created_at=now,
        updated_at=now,
    )


def _make_body(**overrides: Any) -> CommitDecisionRequest:
    base: dict[str, Any] = {
        "outcome": "escalate_to_edd",
        "conditions": [],
        "rationale_html": "<p>Escalating to EDD per upstream signal.</p>",
    }
    base.update(overrides)
    return CommitDecisionRequest(**base)


def _capture_publish() -> tuple[list[tuple[str | None, SseEvent]], Any]:
    calls: list[tuple[str | None, SseEvent]] = []

    async def publish(case_id: str | None, event: SseEvent) -> None:
        calls.append((case_id, event))

    return calls, publish


def _timer() -> tuple[list[tuple[str, str]], DecisionTimerService]:
    calls: list[tuple[str, str]] = []

    async def _on_seal(case_id: str, decision_id: str) -> None:
        return None

    timer = DecisionTimerService(on_seal=_on_seal, window_seconds=60)
    original = timer.schedule

    def record(case_id: str, decision_id: str) -> None:
        calls.append((case_id, decision_id))
        original(case_id, decision_id)

    timer.schedule = record  # type: ignore[method-assign]
    return calls, timer


# ─── AC #1, #2 — state-machine routing ──────────────────────────────────────


async def test_commit_with_escalate_to_edd_transitions_to_pending_lead_approval(
    session: AsyncSession,
    writer: LedgerWriter,
) -> None:
    case = _seed_case()
    await CaseRepo.insert(session, case)
    await session.commit()
    _calls, publish = _capture_publish()
    timer_calls, timer = _timer()

    response = await commit_decision(
        session=session,
        case_id=case.id,
        body=_make_body(outcome="escalate_to_edd"),
        user_id="user_analyst",
        writer=writer,
        sse_publish=publish,
        timer=timer,
    )

    assert response.case_state == CaseState.PENDING_LEAD_APPROVAL
    refreshed = await CaseRepo.get(session, case.id)
    assert refreshed is not None and refreshed.state is CaseState.PENDING_LEAD_APPROVAL
    # Escalating commits skip the seal timer.
    assert timer_calls == []


async def test_commit_with_approve_with_conditions_high_risk_transitions_to_pending_lead_approval(
    session: AsyncSession,
    writer: LedgerWriter,
) -> None:
    case = _seed_case(risk_band="high")
    await CaseRepo.insert(session, case)
    await session.commit()
    _calls, publish = _capture_publish()
    timer_calls, timer = _timer()

    response = await commit_decision(
        session=session,
        case_id=case.id,
        body=_make_body(
            outcome="approve_with_conditions",
            conditions=["enhanced monitoring"],
        ),
        user_id="user_analyst",
        writer=writer,
        sse_publish=publish,
        timer=timer,
    )

    assert response.case_state == CaseState.PENDING_LEAD_APPROVAL
    assert timer_calls == []


async def test_commit_with_approve_with_conditions_low_risk_does_not_transition(
    session: AsyncSession,
    writer: LedgerWriter,
) -> None:
    case = _seed_case(risk_band="low")
    await CaseRepo.insert(session, case)
    await session.commit()
    _calls, publish = _capture_publish()
    timer_calls, timer = _timer()

    response = await commit_decision(
        session=session,
        case_id=case.id,
        body=_make_body(
            outcome="approve_with_conditions",
            conditions=["enhanced monitoring"],
        ),
        user_id="user_analyst",
        writer=writer,
        sse_publish=publish,
        timer=timer,
    )

    assert response.case_state == CaseState.PENDING_SEAL
    # Non-escalating commits keep the 120s undo window via the seal timer.
    assert timer_calls == [(case.id, response.decision_id)]
    timer.cancel(case.id)


async def test_commit_with_approve_outcome_does_not_transition(
    session: AsyncSession,
    writer: LedgerWriter,
) -> None:
    case = _seed_case(risk_band="high")
    await CaseRepo.insert(session, case)
    await session.commit()
    _calls, publish = _capture_publish()
    _timer_calls, timer = _timer()

    response = await commit_decision(
        session=session,
        case_id=case.id,
        body=_make_body(outcome="approve"),
        user_id="user_analyst",
        writer=writer,
        sse_publish=publish,
        timer=timer,
    )
    assert response.case_state == CaseState.PENDING_SEAL
    timer.cancel(case.id)


# ─── AC #3 — ledger entry shape ─────────────────────────────────────────────


async def test_escalation_ledger_entry_appended_with_correct_payload_shape(
    session: AsyncSession,
    writer: LedgerWriter,
) -> None:
    case = _seed_case(risk_band="medium_high")
    await CaseRepo.insert(session, case)
    await session.commit()
    _calls, publish = _capture_publish()
    _timer_calls, timer = _timer()

    response = await commit_decision(
        session=session,
        case_id=case.id,
        body=_make_body(
            outcome="approve_with_conditions",
            conditions=["enhanced monitoring"],
        ),
        user_id="user_analyst",
        writer=writer,
        sse_publish=publish,
        timer=timer,
    )

    reader = LedgerReader(writer._path)
    entries = await reader.read_for_case(case.id)
    escalations = [e for e in entries if e.action == "case.escalated_for_approval"]
    assert len(escalations) == 1
    payload = escalations[0].payload
    assert isinstance(payload, EscalatedForApprovalPayload)
    assert payload.decision_id == response.decision_id
    assert payload.outcome == "approve_with_conditions"
    assert payload.escalation_reason == "high_risk_conditions"
    assert payload.prior_state == "decision_ready"
    assert payload.new_state == "pending_lead_approval"


# ─── AC #4 — SSE broadcast ──────────────────────────────────────────────────


async def test_sse_event_broadcast_on_escalation(
    session: AsyncSession,
    writer: LedgerWriter,
) -> None:
    case = _seed_case()
    await CaseRepo.insert(session, case)
    await session.commit()
    sse_calls, publish = _capture_publish()
    _timer_calls, timer = _timer()

    await commit_decision(
        session=session,
        case_id=case.id,
        body=_make_body(outcome="escalate_to_edd"),
        user_id="user_analyst",
        writer=writer,
        sse_publish=publish,
        timer=timer,
    )

    event_names = [evt.event for _, evt in sse_calls]
    assert "decision.committed" in event_names
    assert "case.escalated_for_approval" in event_names
    escalation_event = next(evt for _, evt in sse_calls if evt.event == "case.escalated_for_approval")
    assert escalation_event.data["case_id"] == case.id
    assert escalation_event.data["outcome"] == "escalate_to_edd"
    assert escalation_event.data["escalation_reason"] == "edd"


async def test_no_escalation_sse_event_when_outcome_does_not_qualify(
    session: AsyncSession,
    writer: LedgerWriter,
) -> None:
    case = _seed_case(risk_band="low")
    await CaseRepo.insert(session, case)
    await session.commit()
    sse_calls, publish = _capture_publish()
    _timer_calls, timer = _timer()

    await commit_decision(
        session=session,
        case_id=case.id,
        body=_make_body(outcome="approve"),
        user_id="user_analyst",
        writer=writer,
        sse_publish=publish,
        timer=timer,
    )

    event_names = [evt.event for _, evt in sse_calls]
    assert "case.escalated_for_approval" not in event_names
    timer.cancel(case.id)


# ─── AC #6 — idempotency (re-commit refused at the source) ──────────────────


async def test_double_commit_does_not_duplicate_escalation_entry(
    session: AsyncSession,
    writer: LedgerWriter,
) -> None:
    """Commit semantics from Story 7.7 reject a second commit on a case
    no longer in `decision_ready` (raises `DecisionConflictError` /
    HTTP 409). That guard is the load-bearing idempotency for the
    escalation entry too — once the first commit succeeds, the case is
    in `pending_lead_approval` and the second call hits the conflict
    error before any side effects."""
    case = _seed_case()
    await CaseRepo.insert(session, case)
    await session.commit()
    _calls, publish = _capture_publish()
    _timer_calls, timer = _timer()

    await commit_decision(
        session=session,
        case_id=case.id,
        body=_make_body(outcome="escalate_to_edd"),
        user_id="user_analyst",
        writer=writer,
        sse_publish=publish,
        timer=timer,
    )

    from cockpit_api.services.decision_service import DecisionConflictError  # noqa: PLC0415

    with pytest.raises(DecisionConflictError):
        await commit_decision(
            session=session,
            case_id=case.id,
            body=_make_body(outcome="escalate_to_edd"),
            user_id="user_analyst",
            writer=writer,
            sse_publish=publish,
            timer=timer,
        )

    reader = LedgerReader(writer._path)
    entries = await reader.read_for_case(case.id)
    escalations = [e for e in entries if e.action == "case.escalated_for_approval"]
    assert len(escalations) == 1
