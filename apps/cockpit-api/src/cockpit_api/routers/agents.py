"""Agent invocation router — Story 3.4 ADK integration.

Exposes the Document Intelligence agent as an HTTP endpoint so the IBM
watsonx Orchestrate ADK runtime can call it as a tool. The endpoint is the
thin HTTP boundary; the heavy lifting still happens in
``apps/agents/src/agents/intake/document_intelligence.py`` via
``@agent_action``, so every ADK-driven invocation lands in the JSONL
ledger exactly the same way a direct Python call would.

Demo flow:
    Chat UI  →  ADK runtime (Docker)  →  HTTP POST  →  this endpoint  →
    document_intelligence(input)  →  ledger entry  →  response back to ADK.

The endpoint is wide-open (no auth) on purpose — the demo runs entirely on
localhost. When the bank-buyer scope revives, this is where OIDC + the
audience-restricted JWT check land.
"""

from __future__ import annotations

from typing import Annotated

from agents.intake.document_intelligence import document_intelligence
from agents.intake.entity_verification import entity_verification
from agents.intake.risk_scoring import RiskCaseView, risk_scoring
from agents.intake.screening import screening
from agents.intake.ubo_graph import ubo_graph
from agents.supervisor.action_decorator import AgentExecutionError
from contracts.document_intelligence import (
    DocumentIntelligenceInput,
    DocumentIntelligenceOutput,
)
from contracts.entity_verification import (
    EntityVerificationInput,
    EntityVerificationResult,
)
from contracts.risk import RiskScore, RiskScoringInput
from contracts.screening import ScreeningAgentInput, ScreeningAgentOutput
from contracts.ubo import UBOGraph, UBOGraphInput
from contracts.writing import DraftedRationale, WritingAgentInput
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from cockpit_api.db.session import get_session

router = APIRouter(prefix="/v1/agents", tags=["agents"])


@router.post(
    "/document_intelligence/extract",
    response_model=DocumentIntelligenceOutput,
    summary="Run the Document Intelligence agent against a case's documents",
    description=(
        "Calls the Document Intelligence agent with the supplied case id and "
        "document refs. Returns the extracted fields with provenance + "
        "confidence band. Every invocation writes one ledger entry."
    ),
)
async def extract_document_fields(
    payload: DocumentIntelligenceInput,
) -> DocumentIntelligenceOutput:
    try:
        return await document_intelligence(payload)
    except AgentExecutionError as exc:
        # The decorator already wrote an `agent.failed` ledger entry. Surface
        # the failure as a 502 so the ADK runtime sees a typed error rather
        # than a 500 + traceback.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post(
    "/entity_verification/verify",
    response_model=EntityVerificationResult,
    summary="Run the Entity Verification agent against a CIN",
    description=(
        "Calls the Entity Verification agent. Looks the CIN up against "
        "the mock MCA lookup tool, diffs case-side fields, returns "
        "typed mismatches. Every invocation writes one ledger entry."
    ),
)
async def verify_entity(
    payload: EntityVerificationInput,
) -> EntityVerificationResult:
    try:
        return await entity_verification(payload)
    except AgentExecutionError as exc:
        # Same 502 mapping as Document Intelligence — the decorator already
        # wrote an `agent.failed` ledger entry; surface a typed error.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post(
    "/ubo_graph/build",
    response_model=UBOGraph,
    summary="Build the UBO graph for a case",
    description=(
        "Calls the UBO Graph agent. Looks the CIN up via the mca_lookup "
        "tool, builds typed nodes + edges with the nominee heuristic, "
        "returns the graph. Every invocation writes one ledger entry."
    ),
)
async def build_ubo_graph(payload: UBOGraphInput) -> UBOGraph:
    try:
        return await ubo_graph(payload)
    except AgentExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post(
    "/risk_scoring/score",
    response_model=RiskScore,
    summary="Run the Risk Scoring agent against a case",
    description=(
        "Calls the Risk Scoring agent. Reads prior intake outputs "
        "(entity_verification, ubo_graph) and customer_metadata to "
        "compute a 5-component decomposed risk score. Read-only — does "
        "NOT persist or update Case.risk_band; the supervisor's intake "
        "fan-out owns that. Every invocation writes one ledger entry."
    ),
)
async def score_risk(
    payload: RiskScoringInput,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RiskScore:
    from cockpit_api.repositories.case_repo import CaseRepo  # noqa: PLC0415
    from cockpit_api.repositories.intake_repo import IntakeRepo  # noqa: PLC0415

    case = await CaseRepo.get(session, payload.case_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case {payload.case_id!r} not found",
        )
    ev_row = await IntakeRepo.get_one(session, payload.case_id, "entity_verification")
    ub_row = await IntakeRepo.get_one(session, payload.case_id, "ubo_graph")
    extra = case.customer_metadata.extra
    screening_hint = extra.get("screening_hit_hint")
    media_hint = extra.get("adverse_media_hint")
    view = RiskCaseView(
        case=case,
        entity_verification=(EntityVerificationResult.model_validate(ev_row) if ev_row is not None else None),
        ubo_graph=UBOGraph.model_validate(ub_row) if ub_row is not None else None,
        screening_hit_hint=screening_hint if isinstance(screening_hint, dict) else None,
        adverse_media_hint=media_hint if isinstance(media_hint, dict) else None,
    )
    try:
        return await risk_scoring(payload, case_view=view)
    except AgentExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post(
    "/screening/run",
    response_model=ScreeningAgentOutput,
    summary="Run the Screening agent against a case's subjects",
    description=(
        "Calls the Screening agent (Story 6.2) with the supplied case_id "
        "and pre-built subject list (entity / directors / UBOs). Returns "
        "the typed output including auto-dismissed hits. Every "
        "invocation writes one ledger entry."
    ),
)
async def run_screening(payload: ScreeningAgentInput) -> ScreeningAgentOutput:
    try:
        return await screening(payload)
    except AgentExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post(
    "/writing/draft",
    response_model=DraftedRationale,
    summary="Draft the KYC decision rationale for a case",
    description=(
        "Story 7.3 — invokes the Writing agent for a case in "
        "decision_ready (or pending_seal / committed for re-draft). "
        "Reads upstream agent outputs from the case's intake row, "
        "runs the LLM, and returns a typed DraftedRationale with "
        "Tiptap-renderable HTML and structured citations. Every "
        "invocation writes one ledger entry."
    ),
)
async def draft_rationale(payload: WritingAgentInput) -> DraftedRationale:
    # Local imports — agents has a path-dep on cockpit-api; deferring
    # avoids circular load.
    from collections.abc import AsyncIterator  # noqa: PLC0415
    from contextlib import asynccontextmanager  # noqa: PLC0415

    from agents.supervisor.case_supervisor import (  # noqa: PLC0415
        CaseNotFoundError,
        CaseNotInDecisionReadyError,
        CaseSupervisor,
        WritingPrerequisitesMissingError,
    )

    from cockpit_api.db.session import get_sessionmaker  # noqa: PLC0415

    factory = get_sessionmaker()

    @asynccontextmanager
    async def _factory() -> AsyncIterator[AsyncSession]:
        async with factory() as s:
            yield s

    supervisor = CaseSupervisor(session_factory=_factory)
    try:
        return await supervisor.run_writing(payload.case_id)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CaseNotInDecisionReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WritingPrerequisitesMissingError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except AgentExecutionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
