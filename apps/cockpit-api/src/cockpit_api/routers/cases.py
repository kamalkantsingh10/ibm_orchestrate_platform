"""Case retrieval router — Story 2.2.

* ``GET /v1/cases`` — list (newest first), demo cap 100, no real cursor yet.
* ``GET /v1/cases/{case_id}`` — single case envelope.

The ``_links`` field is a forward-compat placeholder — Epic 3 (documents)
and Epic 6 (reasoning traces) populate it. Both keys are present and ``null``
in the demo so consumers can pattern-match without conditionals.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from contracts.agent_action import AgentActionLedgerEntry
from contracts.agent_mesh import AgentMeshSnapshot
from contracts.case_supervisor import CaseIntakeOutcome
from contracts.cases import Case
from contracts.cases import CaseState as _CaseStateEnum
from contracts.decision import CommitDecisionRequest, CommitDecisionResponse
from contracts.document_intelligence import DocumentIntelligenceOutput
from contracts.learning_event import (
    LearningEventInput,
    LearningEventLedgerPayload,
    LearningEventResponse,
)
from contracts.ledger import ActorType, LedgerEntry, OfficerDecisionUndonePayload
from contracts.reasoning_trace import ReasoningTrace
from contracts.risk import RiskScore
from contracts.screening import ScreeningAgentOutput
from contracts.sse import SseEvent
from contracts.ubo import UBOGraph
from contracts.users import User
from contracts.writing import DraftedRationale
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from cockpit_api.db.session import get_session
from cockpit_api.deps.current_user import get_current_user, get_optional_current_user
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
    # No auth: exposed as a tool to the case_supervisor agent (Story 1.6+
    # ADK integration). Same rationale as the other agent-tool endpoints.
    summary="List cases (newest first)",
    description=(
        "Returns every case currently in the cockpit, newest first. Each "
        "item carries the case id, current state (intake_scheduled, "
        "decision_ready, etc.), customer metadata, and assigned officer. "
        "Used by the case_supervisor agent to answer 'what cases are there?'."
    ),
)
async def list_cases(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User | None, Depends(get_optional_current_user)] = None,
) -> CaseListResponse:
    # Story 4.1 — order by risk × SLA × continuity. ``current_user`` is
    # optional so the case_supervisor agent's tool path (no demo-user
    # header from the cloud runtime) still works; it just doesn't get the
    # continuity bonus. Analyst/UI calls do, since the header is sent.
    cases = await case_service.list_cases(
        session,
        current_user_id=current_user.id if current_user is not None else None,
    )
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
    # No auth: this is an internal flow called by the Orchestrate runtime
    # as a tool, not by the analyst directly. Same rationale as
    # /v1/agents/document_intelligence/extract. Auth re-attaches when the
    # bank-buyer scope (OIDC + JWT audience check) revives.
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
    "/{case_id}/agent-mesh-state",
    response_model=AgentMeshSnapshot,
    dependencies=[Depends(get_current_user)],
    summary="Get the per-agent mesh state for a case",
    description=(
        "Story 4.5 — returns one row per MVP agent with state derived from "
        "the latest ledger entry: complete (ok) / blocked (error) / idle "
        "(no entries). Demo today does not surface working / needs_input "
        "from the ledger; those flow through SSE (Story 4.6)."
    ),
)
async def get_agent_mesh_state(
    case_id: CaseIdPath,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentMeshSnapshot:
    # Validate the case exists; service ``get_case`` raises 404 itself.
    await case_service.get_case(session, case_id)
    from cockpit_api.services.agent_mesh_state import (  # noqa: PLC0415
        get_agent_mesh_state as _get,
    )

    return await _get(case_id)


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


@router.get(
    "/{case_id}/intake/ubo_graph",
    response_model=UBOGraph,
    dependencies=[Depends(get_current_user)],
    summary="Get the UBO Graph agent's intake output for a case",
    description=(
        "Returns the typed UBO graph produced by Story 5.3's UBO Graph "
        "agent for the given case. 404 if the case doesn't exist OR if "
        "intake hasn't run yet — distinguished by the `detail` field."
    ),
)
async def get_ubo_graph_intake(
    case_id: CaseIdPath,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UBOGraph:
    from pydantic import ValidationError  # noqa: PLC0415

    from cockpit_api.repositories.intake_repo import IntakeRepo  # noqa: PLC0415

    await case_service.get_case(session, case_id)
    row = await IntakeRepo.get_one(session, case_id, "ubo_graph")
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"UBO Graph intake not yet run for case {case_id!r}",
        )
    try:
        return UBOGraph.model_validate(row)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Intake data corrupt: {exc}",
        ) from exc


@router.get(
    "/{case_id}/intake/screening",
    response_model=ScreeningAgentOutput,
    dependencies=[Depends(get_current_user)],
    summary="Get the Screening agent's intake output for a case",
    description=(
        "Returns the typed ScreeningAgentOutput produced by Story 6.2's "
        "Screening agent for the given case. 404 if the case doesn't "
        "exist OR if intake hasn't run yet — distinguished by the "
        "`detail` field."
    ),
)
async def get_screening_intake(
    case_id: CaseIdPath,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ScreeningAgentOutput:
    from pydantic import ValidationError  # noqa: PLC0415

    from cockpit_api.repositories.intake_repo import IntakeRepo  # noqa: PLC0415

    await case_service.get_case(session, case_id)
    row = await IntakeRepo.get_one(session, case_id, "screening")
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Screening intake not yet run for case {case_id!r}",
        )
    try:
        return ScreeningAgentOutput.model_validate(row)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Intake data corrupt: {exc}",
        ) from exc


@router.get(
    "/{case_id}/intake/risk_scoring",
    response_model=RiskScore,
    dependencies=[Depends(get_current_user)],
    summary="Get the Risk Scoring agent's intake output for a case",
    description=(
        "Returns the typed RiskScore produced by Story 5.6's Risk "
        "Scoring agent for the given case. 404 if the case doesn't "
        "exist OR if intake hasn't run yet — distinguished by the "
        "`detail` field."
    ),
)
async def get_risk_scoring_intake(
    case_id: CaseIdPath,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RiskScore:
    from pydantic import ValidationError  # noqa: PLC0415

    from cockpit_api.repositories.intake_repo import IntakeRepo  # noqa: PLC0415

    await case_service.get_case(session, case_id)
    row = await IntakeRepo.get_one(session, case_id, "risk_scoring")
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Risk Scoring intake not yet run for case {case_id!r}",
        )
    try:
        return RiskScore.model_validate(row)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Intake data corrupt: {exc}",
        ) from exc


@router.get(
    "/{case_id}/intake/writing",
    response_model=DraftedRationale,
    dependencies=[Depends(get_current_user)],
    summary="Get the Writing agent's drafted rationale for a case",
    description=(
        "Story 7.3 — returns the typed `DraftedRationale` produced by "
        "the Writing agent for the given case. 404 if the case doesn't "
        "exist OR if the Writing agent hasn't run yet — distinguished by "
        "the `detail` field. Story 7.1's Decision Zone consumes this to "
        "pre-populate the Tiptap editor."
    ),
)
async def get_writing_intake(
    case_id: CaseIdPath,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DraftedRationale:
    from pydantic import ValidationError  # noqa: PLC0415

    from cockpit_api.repositories.intake_repo import IntakeRepo  # noqa: PLC0415

    await case_service.get_case(session, case_id)
    row = await IntakeRepo.get_one(session, case_id, "writing")
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Writing agent has not yet run for case {case_id!r}",
        )
    try:
        return DraftedRationale.model_validate(row)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Intake data corrupt: {exc}",
        ) from exc


# ───────────── Story 7.7 — POST /v1/cases/{case_id}/decisions ─────────────


@router.post(
    "/{case_id}/decisions",
    response_model=CommitDecisionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Commit a decision and start the 120-second undo window",
    description=(
        "Story 7.7 — accepts ``{outcome, conditions, rationale_html}``, "
        "validates the case is in ``decision_ready``, writes one "
        "``officer.decision_committed`` ledger entry, persists the "
        "``Decision`` row, transitions the case to ``pending_seal``, "
        "schedules Story 7.4's 120-second seal timer, and publishes a "
        "``decision.committed`` SSE event. Returns the new "
        "``decision_id`` plus the seal-at timestamp. 409 when the case "
        "is in any other state; 404 when the case is missing."
    ),
)
async def post_decision(
    case_id: CaseIdPath,
    body: CommitDecisionRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CommitDecisionResponse:
    from cockpit_api.main import app as _app  # noqa: PLC0415
    from cockpit_api.services.decision_service import (  # noqa: PLC0415
        CaseNotFoundError,
        DecisionConflictError,
        commit_decision,
    )
    from cockpit_api.services.ledger_service import get_ledger_writer  # noqa: PLC0415
    from cockpit_api.services.sse_registry import publish_safe  # noqa: PLC0415

    timer = getattr(_app.state, "decision_timer", None)
    if timer is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="decision timer not initialised",
        )
    try:
        return await commit_decision(
            session=session,
            case_id=case_id,
            body=body,
            user_id=user.id,
            writer=get_ledger_writer(),
            sse_publish=publish_safe,
            timer=timer,
        )
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DecisionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


# ───────────── Story 7.5 — decision undo timer view + undo endpoint ─────────────


@router.get(
    "/{case_id}/decisions/active/timer",
    dependencies=[Depends(get_current_user)],
    responses={
        200: {"description": "Active timer present."},
        204: {"description": "No active timer for the given case."},
    },
    summary="Get the active decision-undo timer for a case",
    description=(
        "Story 7.5 — returns the `DecisionTimerView` for the case's "
        "currently-pending decision. 200 with the typed body when a "
        "timer is active; 204 No Content when no timer (case not in "
        "pending_seal). Used by the cockpit-ui's UndoPill on initial "
        "mount to seed the countdown deterministically."
    ),
)
async def get_active_decision_timer(
    case_id: CaseIdPath,
) -> Response:

    # Synthesize a Request-less retrieval: the singleton is on app.state.
    # Re-import to avoid a circular load when this module is imported
    # before main.py finishes initialising.
    from cockpit_api.main import app  # noqa: PLC0415

    timer = getattr(app.state, "decision_timer", None)
    if timer is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    view = timer.view(case_id)
    if view is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return Response(
        content=view.model_dump_json(),
        media_type="application/json",
        status_code=status.HTTP_200_OK,
    )


class UndoDecisionRequest(BaseModel):
    """Request body for `POST /v1/cases/{case_id}/decisions/{decision_id}/undo`.

    Story 7.5 — `reason` is the audit-trail anchor; ≥40 chars per
    NFR-T6.
    """

    model_config = {"frozen": True}

    reason: str = Field(min_length=40, max_length=2000)


class UndoDecisionResponse(BaseModel):
    """200 response shape for the undo endpoint — Story 7.5."""

    model_config = {"frozen": True}

    case_id: str
    decision_id: str
    case_state: str
    ledger_entry_id: str


@router.post(
    "/{case_id}/decisions/{decision_id}/undo",
    response_model=UndoDecisionResponse,
    summary="Undo a pending-seal decision (within the 120s window)",
    description=(
        "Story 7.5 — cancels Story 7.4's pending timer, reverts the "
        "case to decision_ready, and writes one "
        "`officer.decision_undone` ledger entry whose payload carries "
        "the officer-supplied reason. Fires `decision.undone` over SSE. "
        "Returns 409 when the decision has already sealed or the "
        "decision_id no longer matches the active timer."
    ),
)
async def undo_decision(
    case_id: CaseIdPath,
    decision_id: Annotated[str, Path(min_length=1, max_length=64)],
    body: UndoDecisionRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UndoDecisionResponse:
    from datetime import UTC as _UTC  # noqa: PLC0415
    from datetime import datetime as _dt

    from ulid import ULID  # noqa: PLC0415

    from cockpit_api.main import app  # noqa: PLC0415
    from cockpit_api.repositories.case_repo import CaseRepo  # noqa: PLC0415
    from cockpit_api.services.ledger_service import get_ledger_writer  # noqa: PLC0415
    from cockpit_api.services.sse_registry import publish_safe  # noqa: PLC0415

    case = await case_service.get_case(session, case_id)
    if case.state.value != _CaseStateEnum.PENDING_SEAL.value:
        if case.state.value == _CaseStateEnum.COMMITTED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="decision already sealed; cannot undo",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"decision is no longer pending seal (case state: {case.state.value})",
        )

    timer = getattr(app.state, "decision_timer", None)
    if timer is not None:
        view = timer.view(case_id)
        if view is None:
            # Timer already expired between the state check and here —
            # rare but possible. Fall through to the case state revert
            # so the analyst doesn't see a stuck pending_seal.
            pass
        elif view.decision_id != decision_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(f"decision_id {decision_id!r} does not match the active timer ({view.decision_id!r})"),
            )
        timer.cancel(case_id)

    # Order matters (story pitfall #3): cancel → state transition →
    # ledger entry → SSE. The ledger write is the audit anchor.
    await CaseRepo.transition(session, case_id, _CaseStateEnum.DECISION_READY)
    await session.commit()

    writer = get_ledger_writer()
    new_id = f"led_{ULID()!s}"
    payload = OfficerDecisionUndonePayload(decision_id=decision_id, reason=body.reason)
    entry = LedgerEntry(
        id=new_id,
        actor_type=ActorType.OFFICER,
        actor_id=user.id,
        case_id=case_id,
        action="officer.decision_undone",
        payload=payload,
        recorded_at=_dt.now(_UTC),
    )
    persisted = await writer.append(entry)

    await publish_safe(
        case_id,
        SseEvent(
            event="decision.undone",
            data={
                "case_id": case_id,
                "decision_id": decision_id,
                "reason": body.reason,
            },
        ),
    )

    return UndoDecisionResponse(
        case_id=case_id,
        decision_id=decision_id,
        case_state=_CaseStateEnum.DECISION_READY.value,
        ledger_entry_id=persisted.id,
    )


_ACTION_ID_PATH = Path(
    pattern=r"^led_[0-9A-HJKMNP-TV-Z]{26}$",
    description="Agent action ID (`led_<ULID>` — same shape as the ledger entry ID)",
)
ActionIdPath = Annotated[str, _ACTION_ID_PATH]


@router.get(
    "/{case_id}/agent-actions/{action_id}/reasoning-trace",
    response_model=ReasoningTrace,
    dependencies=[Depends(get_current_user)],
    responses={
        204: {"description": "Agent action exists but emitted no reasoning trace."},
        404: {"description": "Case or agent action not found."},
    },
    summary="Get the 4-section reasoning trace for an agent action",
    description=(
        "Returns the typed `ReasoningTrace` from "
        "`AgentActionLedgerEntry.reasoning_trace` (Story 6.4). 200 with the "
        "typed body when present; 204 No Content when the agent ran but "
        "emitted no trace (e.g., Document Intelligence, UBO Graph); 404 "
        "when the case doesn't resolve, the action_id doesn't exist, the "
        "action belongs to a different case, or the entry is a SYSTEM / "
        "learning_event entry rather than an agent action."
    ),
)
async def get_reasoning_trace(
    case_id: CaseIdPath,
    action_id: ActionIdPath,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReasoningTrace | Response:
    from cockpit_api.services.ledger_service import get_ledger_reader  # noqa: PLC0415

    # Resolve the case first (raises 404 if missing).
    await case_service.get_case(session, case_id)

    reader = get_ledger_reader()
    entry = await reader.read_by_id(action_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent action {action_id!r} not found",
        )
    # Don't leak cross-case existence — same case scope as case_service.get_case.
    if entry.case_id != case_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent action {action_id!r} not found in case {case_id!r}",
        )
    if not isinstance(entry.payload, AgentActionLedgerEntry):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent action {action_id!r} not found (entry is not an agent action)",
        )
    if entry.payload.reasoning_trace is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return entry.payload.reasoning_trace


class AgentRerunResponse(BaseModel):
    """Story 6.7 / AC #4 response shape for `POST /cases/.../agents/.../run`."""

    model_config = {"frozen": True}

    case_id: str
    agent_slug: str
    agent_action_id: str
    status: str


class CockpitChatMessageRequest(BaseModel):
    """Story 6.8 / AC #1 — POST body for the cockpit-chat message route."""

    model_config = {"frozen": True}

    message: str = Field(min_length=1, max_length=2000)
    message_id: str = Field(min_length=1, max_length=64)


class CockpitChatMessageAccepted(BaseModel):
    """Story 6.8 / AC #1 — 202 response shape."""

    model_config = {"frozen": True}

    case_id: str
    message_id: str
    status: str


@router.post(
    "/{case_id}/cockpit-chat/messages",
    response_model=CockpitChatMessageAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(get_current_user)],
    summary="Send a Cockpit Chat message and stream the reply via SSE",
    description=(
        "Story 6.8. Accepts a user chat message, kicks off a background "
        "task that streams the agent's reply token-by-token onto the "
        "case's existing SSE channel (`cockpit_chat.token` events), and "
        "returns 202 immediately with the message_id echo so the UI can "
        "correlate streamed tokens.\n\n"
        "**Demo simplification**: the reply is generated by a local "
        "deterministic templater (cockpit_api.services.cockpit_chat_reply), "
        "not the cloud Orchestrate streaming chat API. This keeps the "
        "demo's typewriter + citation rendering reliably observable. The "
        "cockpit_chat agent is registered to cloud Orchestrate (Story "
        "6.7) for the Path B reviewer surface; this route is the cockpit-"
        "side fallback that powers the in-cockpit chat panel."
    ),
)
async def post_chat_message(
    case_id: CaseIdPath,
    body: CockpitChatMessageRequest,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CockpitChatMessageAccepted:
    case = await case_service.get_case(session, case_id)
    background_tasks.add_task(
        _stream_chat_reply,
        case_id=case_id,
        case=case,
        message_id=body.message_id,
        user_message=body.message,
    )
    return CockpitChatMessageAccepted(
        case_id=case_id,
        message_id=body.message_id,
        status="accepted",
    )


async def _stream_chat_reply(
    *,
    case_id: str,
    case: Case,
    message_id: str,
    user_message: str,
) -> None:
    """Background task: generate + stream the reply onto the case SSE channel."""
    import asyncio  # noqa: PLC0415

    from cockpit_api.services.citation_parser import parse_citations  # noqa: PLC0415
    from cockpit_api.services.cockpit_chat_reply import (  # noqa: PLC0415
        chunk_reply,
        generate_reply,
    )
    from cockpit_api.services.ledger_service import get_ledger_reader  # noqa: PLC0415
    from cockpit_api.services.sse_registry import publish_safe  # noqa: PLC0415

    try:
        reader = get_ledger_reader()
        entries = await reader.read_for_case(case_id)
        reply = generate_reply(case=case, ledger_entries=entries, user_message=user_message)
        chunks = chunk_reply(reply, chunk_size=8)
        for idx, chunk in enumerate(chunks):
            await publish_safe(
                case_id,
                SseEvent(
                    event="cockpit_chat.token",
                    data={"message_id": message_id, "token": chunk, "position": idx},
                ),
            )
            # Tiny delay so the typewriter renders smoothly in the UI.
            await asyncio.sleep(0.05)
        await publish_safe(
            case_id,
            SseEvent(
                event="cockpit_chat.message_complete",
                data={
                    "message_id": message_id,
                    "full_text": reply,
                    "agent_action_ids": parse_citations(reply),
                },
            ),
        )
    except Exception as exc:  # noqa: BLE001
        await publish_safe(
            case_id,
            SseEvent(
                event="cockpit_chat.error",
                data={
                    "message_id": message_id,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc)[:500],
                },
            ),
        )


@router.post(
    "/{case_id}/agents/{agent_slug}/run",
    response_model=AgentRerunResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(get_current_user)],
    summary="Re-run an intake agent for a case (Cockpit Chat tool)",
    description=(
        "Story 6.7 — `re_run_agent` tool wired for cloud Orchestrate. "
        "Demo wires `screening` only; other slugs return 501. Writes one "
        "`cockpit_chat.tool_invoked` ledger entry per call."
    ),
)
async def re_run_agent(
    case_id: CaseIdPath,
    agent_slug: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentRerunResponse:
    from cockpit_api.repositories.intake_repo import IntakeRepo  # noqa: PLC0415
    from cockpit_api.services.cockpit_chat_ledger import (  # noqa: PLC0415
        ledger_chat_tool_call,
    )
    from cockpit_api.services.ledger_service import (  # noqa: PLC0415
        get_ledger_reader,
        get_ledger_writer,
    )

    if agent_slug not in ("screening", "writing"):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(f"Demo supports re-running 'screening' or 'writing' only; requested agent_slug={agent_slug!r}."),
        )

    case = await case_service.get_case(session, case_id)
    writer = get_ledger_writer()
    reader = get_ledger_reader()

    async with ledger_chat_tool_call(
        writer,
        case_id=case_id,
        tool_name="re_run_agent",
        request_args={"case_id": case_id, "agent_slug": agent_slug},
    ) as record:
        # Local imports — agents has a path-dep on cockpit-api; deferring
        # avoids load-time circular import in some test contexts.
        from agents.intake.screening import screening  # noqa: PLC0415
        from agents.supervisor.case_supervisor import (  # noqa: PLC0415
            CaseSupervisor,
            IntakeContext,
            _build_screening_subjects,
        )
        from contracts.entity_verification import EntityVerificationResult  # noqa: PLC0415
        from contracts.screening import ScreeningAgentInput  # noqa: PLC0415
        from contracts.ubo import UBOGraph as UBOGraphContract  # noqa: PLC0415

        if agent_slug == "writing":
            # Story 7.3 — re-draft path. Defer to the supervisor, which
            # owns the upstream-output loading + ledger_ids resolution.
            from agents.supervisor.case_supervisor import (  # noqa: PLC0415
                CaseNotInDecisionReadyError,
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
                await supervisor.run_writing(case_id)
            except CaseNotInDecisionReadyError as exc:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
            except WritingPrerequisitesMissingError as exc:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
            new_entry = await reader.read_latest_by_actor(case_id, "writing")
            if new_entry is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="writing ran but no agent_action ledger entry was found",
                )
            record["result_summary"] = f"re-ran writing; new agent_action_id {new_entry.id}"
            return AgentRerunResponse(
                case_id=case_id,
                agent_slug=agent_slug,
                agent_action_id=new_entry.id,
                status="ok",
            )

        ctx = IntakeContext(case=case)
        ev_row = await IntakeRepo.get_one(session, case_id, "entity_verification")
        if ev_row is not None:
            ctx.outputs["entity_verification"] = EntityVerificationResult.model_validate(ev_row)
        ubo_row = await IntakeRepo.get_one(session, case_id, "ubo_graph")
        if ubo_row is not None:
            ctx.outputs["ubo_graph"] = UBOGraphContract.model_validate(ubo_row)

        subjects = await _build_screening_subjects(ctx)
        await screening(ScreeningAgentInput(case_id=case_id, subjects=subjects))

        new_entry = await reader.read_latest_by_actor(case_id, "screening")
        if new_entry is None:
            # @agent_action wrote one — defensive fallback.
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="screening ran but no agent_action ledger entry was found",
            )
        record["result_summary"] = f"re-ran screening; new agent_action_id {new_entry.id}"
        return AgentRerunResponse(
            case_id=case_id,
            agent_slug=agent_slug,
            agent_action_id=new_entry.id,
            status="ok",
        )


@router.get(
    "/{case_id}/ledger",
    response_model=list[LedgerEntry],
    dependencies=[Depends(get_current_user)],
    summary="Read recent ledger entries for a case (Cockpit Chat tool)",
    description=(
        "Story 6.7 — `query_ledger` tool. Returns the last `limit` entries "
        "for the case in chronological order (oldest first). Optional "
        "`actor_id` filters to a single agent (e.g., 'screening')."
    ),
)
async def get_case_ledger(
    case_id: CaseIdPath,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[LedgerEntry]:
    from cockpit_api.services.cockpit_chat_ledger import (  # noqa: PLC0415
        ledger_chat_tool_call,
    )
    from cockpit_api.services.ledger_service import (  # noqa: PLC0415
        get_ledger_reader,
        get_ledger_writer,
    )

    await case_service.get_case(session, case_id)

    writer = get_ledger_writer()
    reader = get_ledger_reader()
    args: dict[str, Any] = {"case_id": case_id, "limit": limit}
    if actor_id is not None:
        args["actor_id"] = actor_id

    async with ledger_chat_tool_call(
        writer,
        case_id=case_id,
        tool_name="query_ledger",
        request_args=args,
    ) as record:
        entries = await reader.read_for_case(case_id)
        if actor_id is not None:
            entries = [e for e in entries if e.actor_id == actor_id]
        result = entries[-limit:]
        record["result_summary"] = f"{len(result)} ledger entries returned"
        return result


@router.post(
    "/{case_id}/ubo/learning-events",
    response_model=LearningEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Officer correction to the UBO graph (drag-correct flow)",
    description=(
        "Story 5.5 — drag-correct interaction. The officer flips a flagged "
        "edge (or removes one) and supplies an evidence note. The endpoint "
        "mutates the persisted UBO graph, appends a `learning_event` "
        "ledger entry, and fires `case.ubo_corrected` over SSE so the "
        "cockpit-ui refetches."
    ),
)
async def create_ubo_learning_event(
    case_id: CaseIdPath,
    payload: LearningEventInput,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LearningEventResponse:
    # Local imports to keep router module load fast.
    from datetime import UTC, datetime  # noqa: PLC0415

    from pydantic import ValidationError  # noqa: PLC0415
    from ulid import ULID  # noqa: PLC0415

    from cockpit_api.db.session import get_sessionmaker  # noqa: PLC0415
    from cockpit_api.repositories.intake_repo import IntakeRepo  # noqa: PLC0415
    from cockpit_api.services.ledger_service import get_ledger_writer  # noqa: PLC0415
    from cockpit_api.services.risk_recalc_service import run_risk_recalc  # noqa: PLC0415
    from cockpit_api.services.sse_registry import publish_safe  # noqa: PLC0415
    from cockpit_api.services.ubo_correction_service import (  # noqa: PLC0415
        EdgeNotFoundError,
        NodeNotFoundError,
        apply_officer_correction,
    )

    await case_service.get_case(session, case_id)
    row = await IntakeRepo.get_one(session, case_id, "ubo_graph")
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="UBO graph not built; run intake first",
        )
    try:
        graph = UBOGraph.model_validate(row)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Intake data corrupt: {exc}",
        ) from exc

    try:
        new_graph = apply_officer_correction(
            graph,
            edge_kind=payload.edge_kind,
            from_id=payload.from_id,
            original_to_id=payload.original_to_id,
            new_to_id=payload.new_to_id,
            correction_tag=payload.correction_tag,
            actor_id=current_user.id,
        )
    except EdgeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except NodeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    await IntakeRepo.upsert(session, case_id, "ubo_graph", new_graph)
    await session.commit()

    # Append the typed ledger entry. The writer regenerates `id`.
    placeholder_id = f"led_{ULID()!s}"
    ledger_payload = LearningEventLedgerPayload(
        edge_kind=payload.edge_kind,
        from_id=payload.from_id,
        original_to_id=payload.original_to_id,
        new_to_id=payload.new_to_id,
        correction_tag=payload.correction_tag,
        evidence_note=payload.evidence_note,
        opt_in_for_retraining=payload.opt_in_for_retraining,
    )
    recorded_at = datetime.now(UTC)
    entry = LedgerEntry(
        id=placeholder_id,
        actor_type=ActorType.OFFICER,
        actor_id=current_user.id,
        case_id=case_id,
        action="ubo.edge_corrected",
        payload=ledger_payload,
        recorded_at=recorded_at,
    )
    appended = await get_ledger_writer().append(entry)

    # SSE fan-out — ID-only payload per architecture.md § P6.
    await publish_safe(
        case_id,
        SseEvent(
            event="case.ubo_corrected",
            data={
                "case_id": case_id,
                "edge_kind": payload.edge_kind,
                "from_id": payload.from_id,
                "new_to_id": payload.new_to_id,
            },
        ),
    )

    # Story 5.8 — schedule a fire-and-forget risk recalc. The background task
    # runs after the response is sent; result lands via the
    # `case.risk_recalculated` SSE event.
    sessionmaker = get_sessionmaker()

    @asynccontextmanager
    async def _new_session_cm() -> AsyncIterator[AsyncSession]:
        async with sessionmaker() as new_session:
            yield new_session

    background_tasks.add_task(
        run_risk_recalc,
        case_id=case_id,
        session_factory=_new_session_cm,
    )

    return LearningEventResponse(
        ledger_entry_id=appended.id,
        case_id=case_id,
        recorded_at=appended.recorded_at,
    )
