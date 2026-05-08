"""Risk recalc orchestrator — Story 5.8.

Triggered as a `fastapi.BackgroundTasks` task after a successful officer
drag-correct (Story 5.5). Re-runs the Risk Scoring agent against the
just-mutated UBO graph, persists the new score, denormalizes the band,
and fires the `case.risk_recalculated` SSE event so the cockpit-ui
refetches the panel + queue rail.

Single-worker / fire-and-forget: races between concurrent corrections
on the same case are tolerated (last write wins). Documented limitation.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from agents.intake.risk_scoring import risk_scoring
from agents.supervisor.action_decorator import AgentExecutionError
from agents.supervisor.case_supervisor import _fill_evidence_ids_risk_scoring
from contracts.agent_action import AgentActionLedgerEntry
from contracts.cases import CaseId
from contracts.ledger import LedgerEntry
from contracts.risk import RiskScoringInput
from contracts.sse import SseEvent
from sqlalchemy.ext.asyncio import AsyncSession

from cockpit_api.repositories.case_repo import CaseRepo
from cockpit_api.repositories.intake_repo import IntakeRepo
from cockpit_api.services.ledger_service import (
    LedgerReader,
    LedgerWriter,
    get_ledger_reader,
    get_ledger_writer,
)
from cockpit_api.services.risk_view_builder import build_risk_case_view
from cockpit_api.services.sse_registry import publish_safe

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


async def _find_risk_ledger_entry(reader: LedgerReader, case_id: CaseId) -> LedgerEntry | None:
    entries = await reader.read_for_case(case_id)
    for entry in reversed(entries):
        if (
            entry.actor_id == "risk_scoring"
            and isinstance(entry.payload, AgentActionLedgerEntry)
            and entry.payload.status == "ok"
        ):
            return entry
    return None


async def run_risk_recalc(
    *,
    case_id: CaseId,
    session_factory: SessionFactory,
    writer: LedgerWriter | None = None,
    reader: LedgerReader | None = None,
) -> None:
    """Recompute risk for ``case_id`` and persist + announce.

    Errors are logged but never raised — this runs as a fire-and-forget
    background task; the original endpoint already returned 201. The next
    correction triggers another recalc. ``writer`` / ``reader`` are
    optional (test injection); defaults resolve from singletons.
    """
    _ = writer  # placeholder for future test override; @agent_action uses the singleton writer
    resolved_reader = reader if reader is not None else get_ledger_reader()
    try:
        async with session_factory() as session:
            view = await build_risk_case_view(session, case_id)
            if view is None:
                logger.warning("risk_recalc.case_missing case=%s", case_id)
                return
            if view.ubo_graph is None:
                logger.warning("risk_recalc.no_ubo_graph case=%s; skipping recalc", case_id)
                return

            try:
                score = await risk_scoring(
                    RiskScoringInput(case_id=case_id),
                    case_view=view,
                )
            except AgentExecutionError as exc:
                logger.error("risk_recalc.agent_failed case=%s error=%r", case_id, exc)
                return

            entry = await _find_risk_ledger_entry(resolved_reader, case_id)
            if entry is not None:
                filled_score = _fill_evidence_ids_risk_scoring(score, entry.id)
            else:
                logger.warning("risk_recalc.ledger_entry_missing case=%s actor=risk_scoring", case_id)
                filled_score = score

            await IntakeRepo.upsert(session, case_id, "risk_scoring", filled_score)
            await CaseRepo.update_risk_band(session, case_id, filled_score.band)
            await session.commit()

            await publish_safe(
                case_id,
                SseEvent(
                    event="case.risk_recalculated",
                    data={
                        "case_id": case_id,
                        "band": filled_score.band,
                        "total": filled_score.total,
                    },
                ),
            )
    except Exception as exc:  # noqa: BLE001
        logger.error("risk_recalc.unexpected_error case=%s error=%r", case_id, exc)


# Re-export the writer accessor so tests can replicate the get_ledger_writer
# patching pattern (mirrors action_decorator.get_ledger_writer indirection).
_ = get_ledger_writer
