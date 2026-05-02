"""Case Supervisor — Story 3.5.

Deterministic orchestrator for case intake fan-out. Triggered manually (by
``make seed`` and by ``POST /v1/cases/{id}/intake``); fans out across the
``INTAKE_AGENTS`` registry; catches typed agent failures; transitions the
case state atomically; appends system-level ledger entries naming the
outcome.

This module is allowed to call ``LedgerWriter.append`` directly (the P4
lint rule excludes it via Makefile). The supervisor's ``case.intake_*``
entries are SYSTEM events, not agent invocations — see the lint rule's
comment block in the Makefile.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final

from cockpit_api.repositories.case_repo import CaseRepo
from cockpit_api.repositories.intake_repo import IntakeRepo
from cockpit_api.services.ledger_service import (
    LedgerReader,
    LedgerWriter,
    get_ledger_reader,
    get_ledger_writer,
)
from contracts.agent_action import AgentActionLedgerEntry
from contracts.case_supervisor import CaseIntakeOutcome
from contracts.cases import Case, CaseId, CaseState
from contracts.document_intelligence import (
    DocumentIntelligenceInput,
    DocumentIntelligenceOutput,
    ExtractedField,
)
from contracts.ledger import ActorType, LedgerEntry, LedgerEntryId
from contracts.provenance import ProvenancedField
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from agents.intake.document_intelligence import document_intelligence
from agents.supervisor.action_decorator import AgentExecutionError

logger = logging.getLogger(__name__)


# ───────────────────────────── exceptions ─────────────────────────────────


class CaseNotFoundError(RuntimeError):
    """Raised by the supervisor when the case_id does not resolve."""

    def __init__(self, case_id: CaseId) -> None:
        self.case_id = case_id
        super().__init__(f"Case {case_id!r} not found")


class CaseNotIntakeReadyError(RuntimeError):
    """Raised when the supervisor is asked to run intake on a case past intake_scheduled."""

    def __init__(self, case_id: CaseId, current_state: CaseState) -> None:
        self.case_id = case_id
        self.current_state = current_state
        super().__init__(f"Case {case_id!r} is in {current_state.value!r}; intake only runs from intake_scheduled")


# ───────────────────────────── intake registry ────────────────────────────


@dataclass(frozen=True)
class IntakeAgentSpec:
    """One entry in the supervisor's fan-out list.

    ``invoke`` returns the agent's typed output. ``requires`` is a pure
    predicate over the case (not the session) that decides whether to invoke.
    """

    name: str
    invoke: Callable[[Case], Awaitable[Any]]
    requires: Callable[[Case], bool]


async def _invoke_document_intelligence(case: Case) -> DocumentIntelligenceOutput:
    document_refs = list(case.customer_metadata.extra.get("document_refs", []))
    output = await document_intelligence(DocumentIntelligenceInput(case_id=case.id, document_refs=document_refs))
    return output


def _has_document_refs(case: Case) -> bool:
    return bool(case.customer_metadata.extra.get("document_refs"))


INTAKE_AGENTS: Final[tuple[IntakeAgentSpec, ...]] = (
    IntakeAgentSpec(
        name="document_intelligence",
        invoke=_invoke_document_intelligence,
        requires=_has_document_refs,
    ),
    # Epics 5–6 will append: entity_verification, ubo_graph, screening, risk_scoring
)


# ───────────────────────────── helpers ────────────────────────────────────


def _placeholder_ledger_id() -> str:
    """Pattern-valid ID. The writer regenerates it on append."""
    return f"led_{ULID()!s}"


def _fill_evidence_ids(
    output: DocumentIntelligenceOutput, ledger_entry_id: LedgerEntryId
) -> DocumentIntelligenceOutput:
    """Pure helper — return a new output with each field's evidence_ids set.

    Frozen Pydantic models require copy-on-write via ``model_copy``. We
    rebuild each ``Provenance`` with the supervisor-resolved ledger entry
    ID; ``confidence`` and ``confidence_band`` are unchanged so the
    band-vs-confidence consistency validator still passes.
    """
    new_fields: list[ExtractedField] = []
    for field in output.extracted_fields:
        new_provenance = field.value.provenance.model_copy(update={"evidence_ids": [ledger_entry_id]})
        new_value: ProvenancedField[Any] = field.value.model_copy(update={"provenance": new_provenance})
        new_fields.append(field.model_copy(update={"value": new_value}))
    return output.model_copy(update={"extracted_fields": new_fields})


async def _find_agent_ledger_entry(reader: LedgerReader, case_id: CaseId, actor_id: str) -> LedgerEntry | None:
    """Return the most recent successful agent.completed entry for (case, actor).

    Linear file scan. For the demo's small ledger this is fine; the recently
    written entry sits at the tail.
    """
    entries = await reader.read_for_case(case_id)
    for entry in reversed(entries):
        if (
            entry.actor_id == actor_id
            and isinstance(entry.payload, AgentActionLedgerEntry)
            and entry.payload.status == "ok"
        ):
            return entry
    return None


# ───────────────────────────── notify hook type ───────────────────────────

NotifyHook = Callable[[CaseId, str, dict[str, Any]], Awaitable[None]]
SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


# ───────────────────────────── supervisor ─────────────────────────────────


class CaseSupervisor:
    """Orchestrates case intake — the only path that invokes intake agents.

    Constructed per-request (not as a singleton). Cheap constructor; DI
    plumbing varies across callers (seed script vs HTTP route).
    """

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        notify: NotifyHook | None = None,
        writer: LedgerWriter | None = None,
        reader: LedgerReader | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._notify = notify
        self._writer = writer if writer is not None else get_ledger_writer()
        self._reader = reader if reader is not None else get_ledger_reader()

    async def run_intake(self, case_id: CaseId) -> CaseIntakeOutcome:
        """Run case intake. Returns a typed outcome on completed OR blocked.

        Caller-visible exceptions only on infrastructure failures (DB,
        ledger writer). Domain failures (case missing, wrong state, agent
        execution) raise typed errors or land in the ``blocked`` outcome.
        """
        async with self._session_factory() as session:
            case = await CaseRepo.get(session, case_id)
            if case is None:
                raise CaseNotFoundError(case_id)
            if case.state is not CaseState.INTAKE_SCHEDULED:
                raise CaseNotIntakeReadyError(case_id, case.state)

            agents_run: list[str] = []
            failed_agent: str | None = None
            error_message: str | None = None
            fields_extracted = 0
            doc_intel_output: DocumentIntelligenceOutput | None = None

            for spec in INTAKE_AGENTS:
                if not spec.requires(case):
                    logger.info(
                        "supervisor.skipped agent=%s case=%s reason=requires_false",
                        spec.name,
                        case_id,
                    )
                    continue
                agents_run.append(spec.name)
                try:
                    output = await spec.invoke(case)
                except AgentExecutionError as exc:
                    failed_agent = exc.agent_id
                    error_message = str(exc.original)[:500]
                    break
                else:
                    if spec.name == "document_intelligence":
                        assert isinstance(output, DocumentIntelligenceOutput)
                        doc_intel_output = output

            if failed_agent is not None:
                # Blocked path
                await CaseRepo.transition(session, case_id, CaseState.ESCALATED)
                await CaseRepo.add_block_marker(
                    session,
                    case_id,
                    blocked_agent=failed_agent,
                    block_reason=error_message or "agent execution error",
                )
                await session.commit()
                await self._append_block_ledger(case_id, failed_agent, error_message or "")
                if self._notify is not None:
                    await self._notify(
                        case_id,
                        "case.intake_blocked",
                        {
                            "failed_agent": failed_agent,
                            "error_message": error_message,
                        },
                    )
                return CaseIntakeOutcome(
                    case_id=case_id,
                    status="blocked",
                    agents_run=agents_run,
                    failed_agent=failed_agent,
                    error_message=error_message,
                    fields_extracted=0,
                    completed_at=datetime.now(UTC),
                )

            # Completed path — fill evidence_ids, persist, transition.
            if doc_intel_output is not None:
                agent_entry = await _find_agent_ledger_entry(self._reader, case_id, "document_intelligence")
                if agent_entry is not None:
                    filled = _fill_evidence_ids(doc_intel_output, agent_entry.id)
                else:
                    logger.error(
                        "supervisor.agent_entry_missing case=%s actor=%s",
                        case_id,
                        "document_intelligence",
                    )
                    filled = doc_intel_output
                await IntakeRepo.upsert(session, case_id, "document_intelligence", filled)
                fields_extracted = len(filled.extracted_fields)

            await CaseRepo.transition(session, case_id, CaseState.DECISION_READY)
            await session.commit()

            await self._append_completed_ledger(
                case_id,
                agents_run=agents_run,
                fields_extracted=fields_extracted,
            )
            if self._notify is not None:
                await self._notify(
                    case_id,
                    "case.intake_completed",
                    {
                        "agents": agents_run,
                        "fields_extracted": fields_extracted,
                    },
                )
            return CaseIntakeOutcome(
                case_id=case_id,
                status="completed",
                agents_run=agents_run,
                fields_extracted=fields_extracted,
                completed_at=datetime.now(UTC),
            )

    # ─── ledger helpers ───
    #
    # The ledger writes happen AFTER the DB commit (AC7). If they fail, the
    # audit trail has a gap but user-visible state is correct — log loud
    # and move on. Story 9.1 (Audit Trail Timeline) will surface gaps.

    async def _append_completed_ledger(
        self,
        case_id: CaseId,
        *,
        agents_run: list[str],
        fields_extracted: int,
    ) -> None:
        try:
            await self._writer.append(
                LedgerEntry(
                    id=_placeholder_ledger_id(),
                    actor_type=ActorType.SYSTEM,
                    actor_id="case_supervisor",
                    case_id=case_id,
                    action="case.intake_completed",
                    payload={
                        "agents": agents_run,
                        "fields_extracted": fields_extracted,
                    },
                    recorded_at=datetime.now(UTC),
                )
            )
        except Exception as exc:
            logger.error(
                "supervisor.ledger_write_failed case=%s action=case.intake_completed error=%r",
                case_id,
                exc,
            )

    async def _append_block_ledger(self, case_id: CaseId, failed_agent: str, error_message: str) -> None:
        try:
            await self._writer.append(
                LedgerEntry(
                    id=_placeholder_ledger_id(),
                    actor_type=ActorType.SYSTEM,
                    actor_id="case_supervisor",
                    case_id=case_id,
                    action="case.intake_blocked",
                    payload={
                        "failed_agent": failed_agent,
                        "error_message": error_message,
                    },
                    recorded_at=datetime.now(UTC),
                )
            )
        except Exception as exc:
            logger.error(
                "supervisor.ledger_write_failed case=%s action=case.intake_blocked error=%r",
                case_id,
                exc,
            )
