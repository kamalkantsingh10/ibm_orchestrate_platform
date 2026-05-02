"""Case retrieval router — Story 2.2.

* ``GET /v1/cases`` — list (newest first), demo cap 100, no real cursor yet.
* ``GET /v1/cases/{case_id}`` — single case envelope.

The ``_links`` field is a forward-compat placeholder — Epic 3 (documents)
and Epic 6 (reasoning traces) populate it. Both keys are present and ``null``
in the demo so consumers can pattern-match without conditionals.
"""

from __future__ import annotations

from typing import Annotated

from contracts.case_supervisor import CaseIntakeOutcome
from contracts.cases import Case
from contracts.document_intelligence import DocumentIntelligenceOutput
from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from cockpit_api.db.session import get_session
from cockpit_api.deps.current_user import get_current_user
from cockpit_api.services import case_service

router = APIRouter(prefix="/v1/cases", tags=["cases"])

# Path-param shape mirrors ``contracts.cases._CASE_ID_PATTERN``; FastAPI
# returns 422 automatically on mismatch (no manual validation needed).
_CASE_ID_PATH = Path(pattern=r"^case_[0-9A-HJKMNP-TV-Z]{26}$", description="Case ID (`case_<ULID>`)")

CaseIdPath = Annotated[str, _CASE_ID_PATH]


def _empty_links() -> dict[str, str | None]:
    return {"documents": None, "reasoning_traces": None}


class CaseEnvelope(Case):
    """``Case`` plus the API-shape-only ``_links`` placeholder."""

    links: dict[str, str | None] = Field(default_factory=_empty_links, alias="_links")

    model_config = {"frozen": True, "use_enum_values": False, "populate_by_name": True}


class CaseListResponse(BaseModel):
    """Pagination envelope per ``architecture.md#Format Patterns``."""

    items: list[CaseEnvelope]
    next_cursor: str | None = None
    has_more: bool = False


def _wrap(case: Case) -> CaseEnvelope:
    return CaseEnvelope.model_validate({**case.model_dump(), "_links": _empty_links()})


@router.get(
    "",
    response_model=CaseListResponse,
    dependencies=[Depends(get_current_user)],
    summary="List cases (newest first)",
)
async def list_cases(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CaseListResponse:
    cases = await case_service.list_cases(session)
    return CaseListResponse(items=[_wrap(c) for c in cases])


@router.get(
    "/{case_id}",
    response_model=CaseEnvelope,
    dependencies=[Depends(get_current_user)],
    summary="Get a single case by ID",
)
async def get_case(
    case_id: CaseIdPath,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CaseEnvelope:
    case = await case_service.get_case(session, case_id)
    return _wrap(case)


@router.post(
    "/{case_id}/intake",
    response_model=CaseIntakeOutcome,
    dependencies=[Depends(get_current_user)],
    summary="Run the Case Supervisor intake fan-out for a case",
    description=(
        "Triggers Story 3.5's CaseSupervisor for the given case. Fans out "
        "across the intake-agent registry (currently: Document Intelligence), "
        "persists results, transitions the case to decision_ready on success "
        "or escalated on agent failure. Returns a typed CaseIntakeOutcome."
    ),
)
async def run_case_intake(case_id: CaseIdPath) -> CaseIntakeOutcome:
    # Local imports — apps/agents has a path-dep on cockpit-api; the
    # supervisor imports back into us. Importing at module top creates a
    # circular import on alembic invocation. Deferring to call time is safe.
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager

    from agents.supervisor.case_supervisor import (  # noqa: PLC0415
        CaseNotFoundError,
        CaseNotIntakeReadyError,
        CaseSupervisor,
    )

    from cockpit_api.db.session import get_sessionmaker  # noqa: PLC0415

    factory = get_sessionmaker()

    @asynccontextmanager
    async def _session_factory() -> AsyncIterator[AsyncSession]:
        async with factory() as s:
            yield s

    supervisor = CaseSupervisor(session_factory=_session_factory)
    try:
        return await supervisor.run_intake(case_id)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CaseNotIntakeReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get(
    "/{case_id}/intake/document_intelligence",
    response_model=DocumentIntelligenceOutput,
    dependencies=[Depends(get_current_user)],
    summary="Get the Document Intelligence agent's intake output for a case",
    description=(
        "Returns the typed extraction output produced by Story 3.4's "
        "Document Intelligence agent for the given case. 404 if the case "
        "doesn't exist OR if intake hasn't run yet — distinguished by the "
        "`detail` field of the RFC 7807 problem body."
    ),
)
async def get_document_intelligence_intake(
    case_id: CaseIdPath,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DocumentIntelligenceOutput:
    from pydantic import ValidationError  # noqa: PLC0415

    from cockpit_api.repositories.intake_repo import IntakeRepo  # noqa: PLC0415

    # case_service.get_case raises 404 itself if missing.
    await case_service.get_case(session, case_id)
    row = await IntakeRepo.get_one(session, case_id, "document_intelligence")
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(f"Document Intelligence intake not yet run for case {case_id!r}"),
        )
    try:
        return DocumentIntelligenceOutput.model_validate(row)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Intake data corrupt: {exc}",
        ) from exc
