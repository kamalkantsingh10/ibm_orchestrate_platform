"""Shared `RiskCaseView` builder — Story 5.8 / AC #3.

Used by both the supervisor's intake fan-out (Story 5.6) and the recalc
orchestrator (this story) so a single implementation drives both paths.
"""

from __future__ import annotations

from agents.intake.risk_scoring import RiskCaseView
from contracts.cases import CaseId
from contracts.entity_verification import EntityVerificationResult
from contracts.ubo import UBOGraph
from sqlalchemy.ext.asyncio import AsyncSession

from cockpit_api.repositories.case_repo import CaseRepo
from cockpit_api.repositories.intake_repo import IntakeRepo


async def build_risk_case_view(session: AsyncSession, case_id: CaseId) -> RiskCaseView | None:
    """Return None when the case is missing; otherwise a populated view."""
    case = await CaseRepo.get(session, case_id)
    if case is None:
        return None
    ev_row = await IntakeRepo.get_one(session, case_id, "entity_verification")
    ub_row = await IntakeRepo.get_one(session, case_id, "ubo_graph")
    extra = case.customer_metadata.extra
    screening_hint = extra.get("screening_hit_hint")
    media_hint = extra.get("adverse_media_hint")
    return RiskCaseView(
        case=case,
        entity_verification=(EntityVerificationResult.model_validate(ev_row) if ev_row is not None else None),
        ubo_graph=UBOGraph.model_validate(ub_row) if ub_row is not None else None,
        screening_hit_hint=screening_hint if isinstance(screening_hint, dict) else None,
        adverse_media_hint=media_hint if isinstance(media_hint, dict) else None,
    )
