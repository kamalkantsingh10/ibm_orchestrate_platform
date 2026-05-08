"""Decision commit + seal orchestration — Stories 7.7 and 8.4.

Owns the request-side ``commit_decision`` and the background-side
``seal_decision``. The commit path:

1. Validate case state (must be ``decision_ready``).
2. **Validate citations** (Story 8.4) — every ``led_<ULID>`` referenced
   in the rationale must resolve to a ledger entry on this case.
3. Append the ``officer.decision_committed`` ledger entry.
4. Persist the ``Decision`` row.
5. Transition the case to ``pending_seal``.
6. Commit the SQL session.
7. Schedule Story 7.4's ``DecisionTimerService`` (post-commit so a
   rollback never leaves a phantom timer).
8. Publish the ``decision.committed`` SSE event.

The seal path is symmetric but invoked from the timer's background
task (no FastAPI request scope) — it accepts a ``session_factory``
plus the singleton repos / writer / publisher curried by the
lifespan context manager (see ``main.py``'s ``lifespan``).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from contracts.cases import CaseId, CaseState
from contracts.decision import (
    BrokenCitation,
    CommitDecisionRequest,
    CommitDecisionResponse,
    Decision,
)
from contracts.ledger import (
    ActorType,
    DecisionSealedPayload,
    EscalatedForApprovalPayload,
    LedgerEntry,
    OfficerDecisionCommittedPayload,
)
from contracts.sse import SseEvent
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from cockpit_api.repositories.case_repo import CaseRepo
from cockpit_api.repositories.decision_repo import DecisionRepo
from cockpit_api.services.decision_timer import DecisionTimerService
from cockpit_api.services.ledger_service import LedgerReader, LedgerWriter

UNDO_WINDOW = timedelta(seconds=120)


# Story 8.4 — broken-citation validator. Matches both the inline
# ``{{led_<ULID>}}`` token format (Story 8.3 EDD memo) and the
# ``data-ledger-id="led_<ULID>"`` HTML attribute format (Story 7.1
# rationale draft). The regex captures the ULID payload in either
# case.
_CITATION_RE = re.compile(
    r"data-ledger-id=\"(led_[0-9A-HJKMNP-TV-Z]{26})\""
    r"|\{\{(led_[0-9A-HJKMNP-TV-Z]{26})\}\}"
)


def _extract_cited_ledger_ids(rationale: str) -> list[str]:
    """Return the list of distinct ledger ULIDs cited in the rationale,
    preserving first-occurrence order. Story 8.4."""
    seen: list[str] = []
    seen_set: set[str] = set()
    for match in _CITATION_RE.finditer(rationale):
        ulid = match.group(1) or match.group(2)
        if ulid and ulid not in seen_set:
            seen_set.add(ulid)
            seen.append(ulid)
    return seen


async def validate_decision_citations(
    *,
    rationale: str,
    case_id: CaseId,
    reader: LedgerReader,
) -> list[BrokenCitation]:
    """Story 8.4 / AC #1 — return the list of broken citations in
    ``rationale``. Empty list ⇒ everything resolved.

    For each ULID extracted from the rationale, the helper looks up the
    ledger entry. A missing entry is ``not_found``; an entry whose
    ``case_id`` differs from the supplied case is ``wrong_case``.
    """
    cited_ids = _extract_cited_ledger_ids(rationale)
    if not cited_ids:
        return []

    broken: list[BrokenCitation] = []
    for ulid in cited_ids:
        entry = await reader.read_by_id(ulid)
        if entry is None:
            broken.append(BrokenCitation(token=ulid, reason="not_found"))
        elif entry.case_id != case_id:
            broken.append(BrokenCitation(token=ulid, reason="wrong_case"))
    return broken


class BrokenCitationsError(RuntimeError):
    """Raised by ``commit_decision`` when one or more citations in the
    decision's rationale do not resolve to a ledger entry on this case.
    The router translates this to HTTP 422 — Story 8.4 / AC #2.
    """

    def __init__(self, case_id: CaseId, broken: list[BrokenCitation]) -> None:
        self.case_id = case_id
        self.broken = broken
        labels = ", ".join(f"{b.token}({b.reason})" for b in broken)
        super().__init__(f"Case {case_id!r} commit refused: {len(broken)} broken citation(s): {labels}")


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
# Story 8.3 — optional post-commit hook fired when outcome is
# `escalate_to_edd`. The router/lifespan wires this to
# CaseSupervisor.run_writing_edd_memo. Async, takes the case_id,
# returns nothing (the supervisor persists its own output).
EddMemoTrigger = Callable[[CaseId], Awaitable[None]]


async def commit_decision(
    *,
    session: AsyncSession,
    case_id: CaseId,
    body: CommitDecisionRequest,
    user_id: str,
    writer: LedgerWriter,
    sse_publish: SsePublish,
    timer: DecisionTimerService,
    edd_memo_trigger: EddMemoTrigger | None = None,
    citation_reader: LedgerReader | None = None,
) -> CommitDecisionResponse:
    """Run the commit pipeline. Order of operations matters — see
    Story 7.7 pitfall #1: ledger → row → state → DB commit → timer →
    SSE.

    Story 8.3 — when ``body.outcome == 'escalate_to_edd'`` and
    ``edd_memo_trigger`` is supplied, the trigger is invoked AFTER the
    DB commit and SSE publish so the EDD memo write doesn't block the
    HTTP response. Failures in the trigger are logged but do NOT
    rollback the commit (the decision and its undo timer are already
    durable)."""
    case = await CaseRepo.get(session, case_id)
    if case is None:
        raise CaseNotFoundError(case_id)
    if case.state != CaseState.DECISION_READY:
        raise DecisionConflictError(case_id, case.state)

    # Story 8.4 — broken-citation gate. The rationale must cite only
    # ledger entries that exist on this case. Skipped only when no
    # reader is supplied (legacy callers / tests that don't exercise
    # citation validation explicitly).
    if citation_reader is not None:
        broken = await validate_decision_citations(
            rationale=body.rationale_html,
            case_id=case_id,
            reader=citation_reader,
        )
        if broken:
            raise BrokenCitationsError(case_id, broken)

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

    # Story 8.7 — qualifying outcomes route to the Team Lead approval
    # queue instead of the 120s undo / seal flow. The escalation is
    # atomic with the commit (same SQL session, same DB commit).
    escalation_reason = _resolve_escalation_reason(body.outcome.value, case.risk_band)
    is_escalation = escalation_reason is not None
    target_state = CaseState.PENDING_LEAD_APPROVAL if is_escalation else CaseState.PENDING_SEAL
    await CaseRepo.transition(session, case_id, target_state)

    if is_escalation:
        # Inside this branch is_escalation is True, which by definition
        # of _resolve_escalation_reason means escalation_reason is non-None.
        # body.outcome.value is constrained by DecisionOutcome's enum members
        # to one of the EscalatedForApprovalPayload.outcome literals when
        # escalation_reason is non-None.
        assert escalation_reason is not None  # noqa: S101 — type narrowing, not validation
        escalation_outcome = cast(
            Literal["approve_with_conditions", "escalate_to_edd"],
            body.outcome.value,
        )
        await writer.append(
            LedgerEntry(
                id=f"led_{ULID()!s}",
                case_id=case_id,
                actor_type=ActorType.OFFICER,
                actor_id=user_id,
                action="case.escalated_for_approval",
                payload=EscalatedForApprovalPayload(
                    decision_id=decision_id,
                    outcome=escalation_outcome,
                    prior_state="decision_ready",
                    new_state="pending_lead_approval",
                    escalation_reason=escalation_reason,
                ),
                recorded_at=now,
            )
        )

    await session.commit()

    if not is_escalation:
        timer.schedule(case_id, decision_id)

    await sse_publish(
        case_id,
        SseEvent(
            event="decision.committed",
            data={"case_id": case_id, "decision_id": decision_id},
        ),
    )

    if is_escalation:
        await sse_publish(
            case_id,
            SseEvent(
                event="case.escalated_for_approval",
                data={
                    "case_id": case_id,
                    "decision_id": decision_id,
                    "outcome": body.outcome.value,
                    "escalation_reason": escalation_reason,
                    "timestamp": now.isoformat(),
                },
            ),
        )

    # Story 8.3 — fire the EDD memo writer post-commit on
    # escalate_to_edd. We never block the response on this; any
    # failure is logged but the commit stands.
    if edd_memo_trigger is not None and body.outcome.value == "escalate_to_edd":
        try:
            await edd_memo_trigger(case_id)
        except Exception:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).exception(
                "decision_service.edd_memo_trigger_failed case=%s decision=%s",
                case_id,
                decision_id,
            )

    return CommitDecisionResponse(
        case_id=case_id,
        decision_id=decision_id,
        case_state=target_state,
        # Stories 7.7 + 8.7 — `seal_at` reflects the 120s undo window
        # for non-escalating commits. Escalating commits skip the undo
        # window (Lead approval is the gate), so we surface `now` here;
        # cockpit-ui treats the field as "decision frozen at" rather
        # than "seal-at" when state is PENDING_LEAD_APPROVAL.
        seal_at=(now if is_escalation else now + UNDO_WINDOW),
        ledger_entry_id=committed_entry.id,
    )


def _resolve_escalation_reason(
    outcome: str,
    risk_band: str | None,
) -> Literal["edd", "high_risk_conditions"] | None:
    """Story 8.7 / AC #2 — return the escalation reason if the outcome
    qualifies for Team Lead approval; ``None`` otherwise.

    * `escalate_to_edd` always qualifies (`reason='edd'`).
    * `approve_with_conditions` qualifies only when the case's risk
      band is `high` or `medium_high` (`reason='high_risk_conditions'`).
      Low / medium-low cases approve-with-conditions without an
      additional gate.
    """
    if outcome == "escalate_to_edd":
        return "edd"
    if outcome == "approve_with_conditions" and risk_band in {"high", "medium_high"}:
        return "high_risk_conditions"
    return None


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
