"""Decision commit + seal orchestration — Story 7.7.

Owns the request-side ``commit_decision`` and the background-side
``seal_decision``. The commit path:

1. Validate case state (must be ``decision_ready``).
2. Append the ``officer.decision_committed`` ledger entry.
3. Persist the ``Decision`` row.
4. Transition the case to ``pending_seal``.
5. Commit the SQL session.
6. Schedule Story 7.4's ``DecisionTimerService`` (post-commit so a
   rollback never leaves a phantom timer).
7. Publish the ``decision.committed`` SSE event.

The seal path is symmetric but invoked from the timer's background
task (no FastAPI request scope) — it accepts a ``session_factory``
plus the singleton repos / writer / publisher curried by the
lifespan context manager (see ``main.py``'s ``lifespan``).
"""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta

from contracts.cases import CaseId, CaseState
from contracts.decision import (
    CommitDecisionRequest,
    CommitDecisionResponse,
    Decision,
)
from contracts.ledger import (
    ActorType,
    DecisionSealedPayload,
    LedgerEntry,
    OfficerDecisionCommittedPayload,
)
from contracts.sse import SseEvent
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from cockpit_api.repositories.case_repo import CaseRepo
from cockpit_api.repositories.decision_repo import DecisionRepo
from cockpit_api.services.decision_timer import DecisionTimerService
from cockpit_api.services.ledger_service import LedgerWriter

UNDO_WINDOW = timedelta(seconds=120)


class CaseNotFoundError(RuntimeError):
    """Raised when the case_id does not resolve."""

    def __init__(self, case_id: CaseId) -> None:
        self.case_id = case_id
        super().__init__(f"Case {case_id!r} not found")


class DecisionConflictError(RuntimeError):
    """Raised when commit is attempted on a case not in decision_ready."""

    def __init__(self, case_id: CaseId, current_state: CaseState) -> None:
        self.case_id = case_id
        self.current_state = current_state
        super().__init__(f"Case {case_id!r} is in {current_state.value!r}; commit allowed only from decision_ready")


SsePublish = Callable[[str | None, SseEvent], Awaitable[None]]
SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


async def commit_decision(
    *,
    session: AsyncSession,
    case_id: CaseId,
    body: CommitDecisionRequest,
    user_id: str,
    writer: LedgerWriter,
    sse_publish: SsePublish,
    timer: DecisionTimerService,
) -> CommitDecisionResponse:
    """Run the commit pipeline. Order of operations matters — see
    Story 7.7 pitfall #1: ledger → row → state → DB commit → timer →
    SSE."""
    case = await CaseRepo.get(session, case_id)
    if case is None:
        raise CaseNotFoundError(case_id)
    if case.state != CaseState.DECISION_READY:
        raise DecisionConflictError(case_id, case.state)

    now = datetime.now(UTC)
    decision_id = f"dec_{ULID()!s}"
    rationale_hash = hashlib.sha256(body.rationale_html.encode("utf-8")).hexdigest()

    committed_payload = OfficerDecisionCommittedPayload(
        decision_id=decision_id,
        outcome=body.outcome.value,
        conditions=list(body.conditions),
        rationale_hash=rationale_hash,
    )
    committed_entry = await writer.append(
        LedgerEntry(
            id=f"led_{ULID()!s}",
            case_id=case_id,
            actor_type=ActorType.OFFICER,
            actor_id=user_id,
            action="officer.decision_committed",
            payload=committed_payload,
            recorded_at=now,
        )
    )

    decision = Decision(
        decision_id=decision_id,
        case_id=case_id,
        outcome=body.outcome,
        conditions=list(body.conditions),
        rationale_html=body.rationale_html,
        committed_by_user_id=user_id,
        committed_at=now,
        committed_ledger_entry_id=committed_entry.id,
    )
    await DecisionRepo.insert(session, decision)
    await CaseRepo.transition(session, case_id, CaseState.PENDING_SEAL)
    await session.commit()

    timer.schedule(case_id, decision_id)

    await sse_publish(
        case_id,
        SseEvent(
            event="decision.committed",
            data={"case_id": case_id, "decision_id": decision_id},
        ),
    )

    return CommitDecisionResponse(
        case_id=case_id,
        decision_id=decision_id,
        case_state=CaseState.PENDING_SEAL,
        seal_at=now + UNDO_WINDOW,
        ledger_entry_id=committed_entry.id,
    )


async def seal_decision(
    *,
    case_id: CaseId,
    decision_id: str,
    session_factory: SessionFactory,
    writer: LedgerWriter,
    sse_publish: SsePublish,
) -> None:
    """Background-task callback bound by the lifespan context manager.

    Idempotent: if the decision row is already sealed (a re-fired
    timer; should not happen under correct cancel semantics) or no
    longer exists (Story 7.5 undo deleted it), the function returns
    without writing a duplicate ledger entry.
    """
    async with session_factory() as session:
        decision = await DecisionRepo.fetch_by_id(session, decision_id)
        if decision is None or decision.sealed_at is not None:
            return

        now = datetime.now(UTC)
        sealed_payload = DecisionSealedPayload(
            decision_id=decision_id,
            outcome=decision.outcome.value,
        )
        seal_entry = await writer.append(
            LedgerEntry(
                id=f"led_{ULID()!s}",
                case_id=case_id,
                actor_type=ActorType.SYSTEM,
                actor_id="platform",
                action="decision.sealed",
                payload=sealed_payload,
                recorded_at=now,
            )
        )
        await DecisionRepo.update_sealed(session, decision_id, now, seal_entry.id)
        await CaseRepo.transition(session, case_id, CaseState.COMMITTED)
        await session.commit()

    await sse_publish(
        case_id,
        SseEvent(
            event="decision.sealed",
            data={
                "case_id": case_id,
                "decision_id": decision_id,
                "ledger_entry_id": seal_entry.id,
            },
        ),
    )
