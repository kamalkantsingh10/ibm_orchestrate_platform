"""Case Supervisor — Story 3.5 / Story 5.1.

Deterministic orchestrator for case intake fan-out. Triggered manually (by
``make seed`` and by ``POST /v1/cases/{id}/intake``); fans out across the
``INTAKE_AGENTS`` registry; catches typed agent failures; transitions the
case state atomically; appends system-level ledger entries naming the
outcome.

This module is allowed to call ``LedgerWriter.append`` directly (the P4
lint rule excludes it via Makefile). The supervisor's ``case.intake_*``
entries are SYSTEM events, not agent invocations — see the lint rule's
comment block in the Makefile.

Story 5.1 refactor: the per-run ``IntakeContext`` carries typed outputs
across agents so each spec's ``invoke`` can read prior agents' results
without resorting to globals.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Final, TypeVar

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
from contracts.entity_verification import EntityVerificationInput, EntityVerificationResult
from contracts.ledger import ActorType, LedgerEntry, LedgerEntryId
from contracts.provenance import ProvenancedField
from contracts.risk import RiskScore, RiskScoringInput
from contracts.screening import (
    ScreeningAgentInput,
    ScreeningAgentOutput,
    ScreeningHit,
    ScreeningSubject,
)
from contracts.ubo import UBOEdge, UBOGraph, UBOGraphInput, UBOPersonNode
from contracts.writing import DraftedRationale, WritingAgentInput
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from agents.adapters.writing import WritingLLM
from agents.decision.writing import writing
from agents.intake.document_intelligence import document_intelligence
from agents.intake.entity_verification import EntityCaseView, entity_verification
from agents.intake.risk_scoring import RiskCaseView, risk_scoring
from agents.intake.screening import screening
from agents.intake.ubo_graph import ubo_graph
from agents.supervisor.action_decorator import AgentExecutionError
from agents.tools.mca_lookup import (
    MCANotFoundError,
    MCATemporaryError,
    get_default_mca_lookup,
)

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


class CaseNotInDecisionReadyError(RuntimeError):
    """Raised when the supervisor is asked to run the Writing agent on
    a case that hasn't completed intake or is in a terminal state.
    """

    def __init__(self, case_id: CaseId, current_state: CaseState) -> None:
        self.case_id = case_id
        self.current_state = current_state
        super().__init__(
            f"Case {case_id!r} is in {current_state.value!r}; "
            f"writing requires decision_ready, pending_seal, committed, or escalated"
        )


class WritingPrerequisitesMissingError(RuntimeError):
    """Raised when ``run_writing`` cannot proceed because an upstream
    intake output is missing (e.g., document_intelligence never ran).
    """

    def __init__(self, case_id: CaseId, missing: str) -> None:
        self.case_id = case_id
        self.missing = missing
        super().__init__(f"Cannot run writing for case {case_id!r}: missing upstream {missing!r}")


# ───────────────────────────── intake context ─────────────────────────────


_CIN_RE = re.compile(r"^[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}$")


@dataclass
class IntakeContext:
    """Per-run state. Mutated inside ``run_intake``; never escapes.

    ``outputs`` is keyed by ``IntakeAgentSpec.name``; values are the typed
    Pydantic outputs each agent returned (immutable). The dict is the
    carrier that lets later agents read earlier agents' results without
    repacking the canonical ``INTAKE_AGENTS`` tuple mid-loop.
    """

    case: Case
    outputs: dict[str, BaseModel] = field(default_factory=dict)


# ───────────────────────────── intake registry ────────────────────────────


@dataclass(frozen=True)
class IntakeAgentSpec:
    """One entry in the supervisor's fan-out list.

    ``invoke`` returns the agent's typed output; takes the per-run
    ``IntakeContext`` so it can read upstream agents' typed outputs (e.g.,
    Entity Verification reads Document Intelligence). ``requires`` is a
    pure predicate over the case (not the session) that decides whether to
    invoke the agent at all.
    """

    name: str
    invoke: Callable[[IntakeContext], Awaitable[BaseModel]]
    requires: Callable[[Case], bool]


async def _invoke_document_intelligence(ctx: IntakeContext) -> DocumentIntelligenceOutput:
    document_refs = list(ctx.case.customer_metadata.extra.get("document_refs", []))
    output = await document_intelligence(
        DocumentIntelligenceInput(case_id=ctx.case.id, document_refs=document_refs),
    )
    return output


def _has_document_refs(case: Case) -> bool:
    return bool(case.customer_metadata.extra.get("document_refs"))


def _has_cin(case: Case) -> bool:
    """Cheap pre-fan-out predicate.

    The supervisor doesn't have the doc-intel output at requires-evaluation
    time (``requires`` runs before fan-out), so this only checks
    ``customer_metadata.extra.registration_number``. The diff path inside
    the agent re-tries via doc-intel output when present.
    """
    reg = case.customer_metadata.extra.get("registration_number")
    return isinstance(reg, str) and bool(_CIN_RE.match(reg))


def _build_entity_case_view(
    case: Case,
    doc_intel_output: DocumentIntelligenceOutput | None,
) -> EntityCaseView:
    """Project the four fields Entity Verification diffs out of the case + doc-intel intake row."""

    def _extracted(name: str) -> str | None:
        if doc_intel_output is None:
            return None
        for f in doc_intel_output.extracted_fields:
            if f.field_name == name:
                inner = f.value.value
                if inner is not None and isinstance(inner, str) and inner != "":
                    return inner
        return None

    extra = case.customer_metadata.extra

    def _extra_str(key: str) -> str | None:
        value = extra.get(key)
        return value if isinstance(value, str) else None

    cin = _extracted("cin") or _extra_str("registration_number")
    company_name = _extracted("company_name") or case.customer_metadata.customer_name
    registered_address = _extracted("registered_address") or _extra_str("registered_address")
    incorporation_date = _extracted("incorporation_date") or _extra_str("incorporation_date")

    return EntityCaseView(
        company_name=company_name,
        registered_address=registered_address,
        incorporation_date=incorporation_date,
        cin=cin,
    )


def _resolve_cin(ctx: IntakeContext) -> str | None:
    """Prefer customer_metadata.extra.registration_number; fall back to extracted CIN field."""
    reg = ctx.case.customer_metadata.extra.get("registration_number")
    if isinstance(reg, str) and _CIN_RE.match(reg):
        return reg
    doc_intel_output = ctx.outputs.get("document_intelligence")
    if isinstance(doc_intel_output, DocumentIntelligenceOutput):
        for f in doc_intel_output.extracted_fields:
            if f.field_name == "cin":
                inner = f.value.value
                if isinstance(inner, str) and _CIN_RE.match(inner):
                    return inner
    return None


async def _invoke_entity_verification(ctx: IntakeContext) -> EntityVerificationResult:
    cin = _resolve_cin(ctx)
    if cin is None:
        # _has_cin would have returned False to begin with; this is a defensive
        # branch — surface as a typed agent error so the supervisor records the
        # block marker.
        raise ValueError("entity_verification: case has no CIN")
    doc_intel = ctx.outputs.get("document_intelligence")
    doc_intel_output = doc_intel if isinstance(doc_intel, DocumentIntelligenceOutput) else None
    case_view = _build_entity_case_view(ctx.case, doc_intel_output)
    return await entity_verification(
        EntityVerificationInput(case_id=ctx.case.id, cin=cin),
        case_view=case_view,
    )


async def _invoke_ubo_graph(ctx: IntakeContext) -> UBOGraph:
    cin = _resolve_cin(ctx)
    if cin is None:
        raise ValueError("ubo_graph: case has no CIN")
    return await ubo_graph(UBOGraphInput(case_id=ctx.case.id, cin=cin))


def _build_risk_case_view(ctx: IntakeContext) -> RiskCaseView:
    """Per-intake builder — uses the in-memory ``ctx.outputs`` rather than DB.

    The recalc orchestrator (Story 5.8) uses a separate DB-backed builder at
    ``cockpit_api.services.risk_view_builder.build_risk_case_view`` for the
    case where intake outputs only live in the DB, not in an ``IntakeContext``.
    Both builders produce the same ``RiskCaseView`` shape.
    """
    ev = ctx.outputs.get("entity_verification")
    ub = ctx.outputs.get("ubo_graph")
    extra = ctx.case.customer_metadata.extra
    screening_hint_value = extra.get("screening_hit_hint")
    media_hint_value = extra.get("adverse_media_hint")
    return RiskCaseView(
        case=ctx.case,
        entity_verification=ev if isinstance(ev, EntityVerificationResult) else None,
        ubo_graph=ub if isinstance(ub, UBOGraph) else None,
        screening_hit_hint=screening_hint_value if isinstance(screening_hint_value, dict) else None,
        adverse_media_hint=media_hint_value if isinstance(media_hint_value, dict) else None,
    )


async def _invoke_risk_scoring(ctx: IntakeContext) -> RiskScore:
    view = _build_risk_case_view(ctx)
    return await risk_scoring(RiskScoringInput(case_id=ctx.case.id), case_view=view)


def _always(case: Case) -> bool:  # noqa: ARG001
    return True


async def _build_screening_subjects(ctx: IntakeContext) -> list[ScreeningSubject]:
    """Assemble the entity + director + UBO subject list for the screening agent.

    Construction rules (Story 6.2 / AC #4):

    * Entity subject — always emitted. ``subject_id`` is the case's
      ``customer_metadata.extra.customer_id`` if present, else the case_id.
      For the demo, individual cases (Ananya) use the case_id directly.
    * Director subjects — only when the case has a CIN. The supervisor calls
      MCA lookup again rather than reshaping ``EntityVerificationResult`` to
      carry the full director list (cheaper than contract churn — see Story
      6.2 § Pitfall #4). DOB is unknown for MCA-derived directors (the mock
      doesn't carry it); identifiers carry the DIN.
    * UBO subjects — only when ``ubo_graph`` ran. For each ``UBOPersonNode``
      whose at-least-one outgoing edge has ``ownership_pct >= 0.10``, emit
      one subject. Skip ``UBOEntityNode``s — already covered by the entity
      subject.

    Subject IDs are deduped: a person who is both a director and a UBO
    person node uses the UBO node's id (matches Story 5.3's dedup output).
    """
    subjects: list[ScreeningSubject] = []
    seen_ids: set[str] = set()
    case = ctx.case

    # Entity subject (always).
    entity_id = _entity_subject_id(case)
    extra = case.customer_metadata.extra
    identifiers: dict[str, str] = {}
    reg = extra.get("registration_number")
    if isinstance(reg, str) and reg:
        identifiers["cin"] = reg
    entity_dob = _individual_case_dob(case)
    subjects.append(
        ScreeningSubject(
            subject_kind="entity",
            subject_id=entity_id,
            full_name=case.customer_metadata.customer_name,
            date_of_birth=entity_dob,
            identifiers=identifiers,
        )
    )
    seen_ids.add(entity_id)

    # Director subjects — MCA-sourced. Skip if no CIN.
    cin = _resolve_cin(ctx)
    if cin is not None:
        try:
            mca = get_default_mca_lookup()
            master = await mca.lookup(cin=cin)
        except (MCATemporaryError, MCANotFoundError):
            logger.info("supervisor.screening.mca_lookup_skipped case=%s cin=%s", case.id, cin)
            master = None
        if master is not None:
            for director in master.directors:
                subj_id = (
                    f"ubo_p_{director.din}" if director.din is not None else f"ubo_p_{_director_slug(director.name)}"
                )
                if subj_id in seen_ids:
                    continue
                seen_ids.add(subj_id)
                director_ids: dict[str, str] = {}
                if director.din is not None:
                    director_ids["din"] = director.din
                subjects.append(
                    ScreeningSubject(
                        subject_kind="director",
                        subject_id=subj_id,
                        full_name=director.name,
                        date_of_birth=None,
                        identifiers=director_ids,
                    )
                )

    # UBO person subjects — graph-sourced.
    ubo_out = ctx.outputs.get("ubo_graph")
    if isinstance(ubo_out, UBOGraph):
        material_owners = _ubo_person_ids_with_min_ownership(ubo_out, threshold=0.10)
        person_nodes = {n.id: n for n in ubo_out.nodes if isinstance(n, UBOPersonNode)}
        for node_id in material_owners:
            if node_id in seen_ids:
                continue
            node = person_nodes.get(node_id)
            if node is None:
                continue
            seen_ids.add(node_id)
            subjects.append(
                ScreeningSubject(
                    subject_kind="ubo",
                    subject_id=node.id,
                    full_name=node.name,
                    date_of_birth=None,
                    identifiers={"din": node.din} if node.din else {},
                )
            )

    return subjects


def _entity_subject_id(case: Case) -> str:
    """Return the subject_id used for the case's entity subject.

    ``customer_metadata.extra.customer_id`` if present, else the ``case.id``.
    Mirrors Story 6.1's fixture key for Ananya (no customer_id → case_id).
    """
    extra_id = case.customer_metadata.extra.get("customer_id")
    if isinstance(extra_id, str) and extra_id:
        return extra_id
    return case.id


def _individual_case_dob(case: Case) -> date | None:
    """Return the DOB from ``customer_metadata.extra.date_of_birth`` if parseable."""
    raw = case.customer_metadata.extra.get("date_of_birth")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _director_slug(name: str) -> str:
    """Lowercase + non-alnum → underscore. Mirrors `agents/intake/ubo_graph.py:_slugify`."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _ubo_person_ids_with_min_ownership(graph: UBOGraph, *, threshold: float) -> list[str]:
    """Return UBO person node IDs that have ≥ threshold ownership on any outgoing edge."""
    out: set[str] = set()
    for edge in graph.edges:
        if edge.ownership_pct is None:
            continue
        # ownership_pct is a percentage (0..100), not a fraction. The 0.10
        # threshold from the story is a *fraction* convention — convert to %.
        if edge.ownership_pct >= threshold * 100.0:
            out.add(edge.from_id)
    return sorted(out)


def _has_screenable_subjects(case: Case) -> bool:  # noqa: ARG001
    """Demo always has a screenable entity (every case has a customer_name).

    A real platform would predicate on intake completeness. Pro forma here.
    """
    return True


async def _invoke_screening(ctx: IntakeContext) -> ScreeningAgentOutput:
    subjects = await _build_screening_subjects(ctx)
    return await screening(ScreeningAgentInput(case_id=ctx.case.id, subjects=subjects))


INTAKE_AGENTS: Final[tuple[IntakeAgentSpec, ...]] = (
    IntakeAgentSpec(
        name="document_intelligence",
        invoke=_invoke_document_intelligence,
        requires=_has_document_refs,
    ),
    IntakeAgentSpec(
        name="entity_verification",
        invoke=_invoke_entity_verification,
        requires=_has_cin,
    ),
    IntakeAgentSpec(
        name="ubo_graph",
        invoke=_invoke_ubo_graph,
        requires=_has_cin,
    ),
    IntakeAgentSpec(
        name="screening",
        invoke=_invoke_screening,
        requires=_has_screenable_subjects,
    ),
    IntakeAgentSpec(
        name="risk_scoring",
        invoke=_invoke_risk_scoring,
        requires=_always,
    ),
)


# ───────────────────────────── helpers ────────────────────────────────────


def _placeholder_ledger_id() -> str:
    """Pattern-valid ID. The writer regenerates it on append."""
    return f"led_{ULID()!s}"


T = TypeVar("T")


def _rebuild_provenanced_field(pf: ProvenancedField[T], evidence_ids: list[LedgerEntryId]) -> ProvenancedField[T]:
    """Copy-on-write helper — rebuild ``pf`` with new ``evidence_ids``.

    Frozen Pydantic models require ``model_copy``. ``confidence`` and
    ``confidence_band`` are unchanged so the band-vs-confidence
    consistency validator still passes.
    """
    new_prov = pf.provenance.model_copy(update={"evidence_ids": evidence_ids})
    return pf.model_copy(update={"provenance": new_prov})


def _fill_evidence_ids(
    output: DocumentIntelligenceOutput, ledger_entry_id: LedgerEntryId
) -> DocumentIntelligenceOutput:
    """Pure helper — return a new output with each field's evidence_ids set."""
    new_fields: list[ExtractedField] = []
    for f in output.extracted_fields:
        new_value = _rebuild_provenanced_field(f.value, [ledger_entry_id])
        new_fields.append(f.model_copy(update={"value": new_value}))
    return output.model_copy(update={"extracted_fields": new_fields})


def _fill_evidence_ids_entity_verification(
    output: EntityVerificationResult, ledger_entry_id: LedgerEntryId
) -> EntityVerificationResult:
    """Back-fill the single ``mca_status`` ProvenancedField with the agent's ledger ID."""
    new_status = _rebuild_provenanced_field(output.mca_status, [ledger_entry_id])
    return output.model_copy(update={"mca_status": new_status})


def _fill_evidence_ids_ubo_graph(graph: UBOGraph, ledger_entry_id: LedgerEntryId) -> UBOGraph:
    """Back-fill every edge's confidence ProvenancedField with the agent's ledger ID."""
    new_edges: list[UBOEdge] = []
    for edge in graph.edges:
        new_conf = _rebuild_provenanced_field(edge.confidence, [ledger_entry_id])
        new_edges.append(edge.model_copy(update={"confidence": new_conf}))
    return graph.model_copy(update={"edges": new_edges})


def _fill_evidence_ids_risk_scoring(score: RiskScore, ledger_entry_id: LedgerEntryId) -> RiskScore:
    """Back-fill ``score_provenance.evidence_ids`` with the agent's ledger ID."""
    new_prov = _rebuild_provenanced_field(score.score_provenance, [ledger_entry_id])
    return score.model_copy(update={"score_provenance": new_prov})


def _fill_evidence_ids_screening(output: ScreeningAgentOutput, ledger_entry_id: LedgerEntryId) -> ScreeningAgentOutput:
    """Back-fill every hit's name_match_score evidence_ids with the agent's ledger ID."""
    new_hits: list[ScreeningHit] = []
    for hit in output.hits:
        new_score = _rebuild_provenanced_field(hit.name_match_score, [ledger_entry_id])
        new_hits.append(hit.model_copy(update={"name_match_score": new_score}))
    return output.model_copy(update={"hits": new_hits})


async def _find_agent_ledger_entry(reader: LedgerReader, case_id: CaseId, actor_id: str) -> LedgerEntry | None:
    """Return the most recent successful agent.completed entry for (case, actor)."""
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
    """Orchestrates case intake — the only path that invokes intake agents."""

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        notify: NotifyHook | None = None,
        writer: LedgerWriter | None = None,
        reader: LedgerReader | None = None,
        writing_llm: WritingLLM | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._notify = notify
        self._writer = writer if writer is not None else get_ledger_writer()
        self._reader = reader if reader is not None else get_ledger_reader()
        # Story 7.3 — optional override; production resolves via the
        # WRITING_LLM_PROVIDER env. Tests inject a stub.
        self._writing_llm = writing_llm

    async def run_intake(self, case_id: CaseId) -> CaseIntakeOutcome:
        async with self._session_factory() as session:
            case = await CaseRepo.get(session, case_id)
            if case is None:
                raise CaseNotFoundError(case_id)
            if case.state is not CaseState.INTAKE_SCHEDULED:
                raise CaseNotIntakeReadyError(case_id, case.state)

            ctx = IntakeContext(case=case)
            agents_run: list[str] = []
            failed_agent: str | None = None
            error_message: str | None = None
            fields_extracted = 0

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
                    output = await spec.invoke(ctx)
                except AgentExecutionError as exc:
                    failed_agent = exc.agent_id
                    error_message = str(exc.original)[:500]
                    break
                else:
                    ctx.outputs[spec.name] = output

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

            # Completed path — fill evidence_ids, persist each typed output, transition.
            doc_intel_output = ctx.outputs.get("document_intelligence")
            if isinstance(doc_intel_output, DocumentIntelligenceOutput):
                agent_entry = await _find_agent_ledger_entry(self._reader, case_id, "document_intelligence")
                if agent_entry is not None:
                    filled_di = _fill_evidence_ids(doc_intel_output, agent_entry.id)
                else:
                    logger.error(
                        "supervisor.agent_entry_missing case=%s actor=%s",
                        case_id,
                        "document_intelligence",
                    )
                    filled_di = doc_intel_output
                await IntakeRepo.upsert(session, case_id, "document_intelligence", filled_di)
                fields_extracted = len(filled_di.extracted_fields)

            ev_output = ctx.outputs.get("entity_verification")
            if isinstance(ev_output, EntityVerificationResult):
                ev_entry = await _find_agent_ledger_entry(self._reader, case_id, "entity_verification")
                if ev_entry is not None:
                    filled_ev = _fill_evidence_ids_entity_verification(ev_output, ev_entry.id)
                else:
                    logger.error(
                        "supervisor.agent_entry_missing case=%s actor=%s",
                        case_id,
                        "entity_verification",
                    )
                    filled_ev = ev_output
                await IntakeRepo.upsert(session, case_id, "entity_verification", filled_ev)

            ubo_output = ctx.outputs.get("ubo_graph")
            if isinstance(ubo_output, UBOGraph):
                ubo_entry = await _find_agent_ledger_entry(self._reader, case_id, "ubo_graph")
                if ubo_entry is not None:
                    filled_ubo = _fill_evidence_ids_ubo_graph(ubo_output, ubo_entry.id)
                else:
                    logger.error(
                        "supervisor.agent_entry_missing case=%s actor=%s",
                        case_id,
                        "ubo_graph",
                    )
                    filled_ubo = ubo_output
                await IntakeRepo.upsert(session, case_id, "ubo_graph", filled_ubo)

            screening_output = ctx.outputs.get("screening")
            if isinstance(screening_output, ScreeningAgentOutput):
                scr_entry = await _find_agent_ledger_entry(self._reader, case_id, "screening")
                if scr_entry is not None:
                    filled_scr = _fill_evidence_ids_screening(screening_output, scr_entry.id)
                else:
                    logger.error(
                        "supervisor.agent_entry_missing case=%s actor=%s",
                        case_id,
                        "screening",
                    )
                    filled_scr = screening_output
                await IntakeRepo.upsert(session, case_id, "screening", filled_scr)

            risk_output = ctx.outputs.get("risk_scoring")
            if isinstance(risk_output, RiskScore):
                risk_entry = await _find_agent_ledger_entry(self._reader, case_id, "risk_scoring")
                if risk_entry is not None:
                    filled_risk = _fill_evidence_ids_risk_scoring(risk_output, risk_entry.id)
                else:
                    logger.error(
                        "supervisor.agent_entry_missing case=%s actor=%s",
                        case_id,
                        "risk_scoring",
                    )
                    filled_risk = risk_output
                await IntakeRepo.upsert(session, case_id, "risk_scoring", filled_risk)
                # Story 5.6 / AC5 — denormalize the band onto cases.risk_band.
                await CaseRepo.update_risk_band(session, case_id, filled_risk.band)

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

            # Story 7.3 — kick the Writing agent now that all intake
            # outputs landed. Writing is a separate phase, not part of
            # the intake fan-out (pitfall #1: don't pollute
            # ``agents_run`` with writing). Failure here MUST NOT roll
            # back intake — the analyst can still author the rationale
            # from scratch.
            try:
                await self.run_writing(case_id)
            except Exception as exc:  # noqa: BLE001 — explicit "swallow + log"
                logger.warning(
                    "supervisor.writing_failed case=%s error=%r",
                    case_id,
                    exc,
                )

            return CaseIntakeOutcome(
                case_id=case_id,
                status="completed",
                agents_run=agents_run,
                fields_extracted=fields_extracted,
                completed_at=datetime.now(UTC),
            )

    async def run_writing(self, case_id: CaseId) -> DraftedRationale:
        """Run the Writing agent for a case that has completed intake.

        Loads upstream typed outputs from the intake row, resolves the
        latest ``agent.completed`` ledger entry per upstream agent slug,
        and invokes the agent function. Persists the resulting
        ``DraftedRationale`` under ``IntakeRepo`` keyed by
        ``agent_id="writing"``. Callable on already-committed cases
        (re-draft path); the new draft replaces the old in the intake
        row, while the ledger preserves history via a fresh
        ``agent.completed`` entry.
        """
        async with self._session_factory() as session:
            case = await CaseRepo.get(session, case_id)
            if case is None:
                raise CaseNotFoundError(case_id)
            if case.state not in (
                CaseState.DECISION_READY,
                CaseState.PENDING_SEAL,
                CaseState.COMMITTED,
                CaseState.ESCALATED,
            ):
                raise CaseNotInDecisionReadyError(case_id, case.state)

            outputs = await IntakeRepo.get_by_case(session, case_id)

            doc_intel_raw = outputs.get("document_intelligence")
            if doc_intel_raw is None:
                raise WritingPrerequisitesMissingError(case_id, "document_intelligence")
            doc_intel_output = DocumentIntelligenceOutput.model_validate(doc_intel_raw)

            ev_raw = outputs.get("entity_verification")
            ev_output = EntityVerificationResult.model_validate(ev_raw) if ev_raw is not None else None

            ubo_raw = outputs.get("ubo_graph")
            ubo_output = UBOGraph.model_validate(ubo_raw) if ubo_raw is not None else None

            screening_raw = outputs.get("screening")
            screening_output = ScreeningAgentOutput.model_validate(screening_raw) if screening_raw is not None else None

            risk_raw = outputs.get("risk_scoring")
            risk_output = RiskScore.model_validate(risk_raw) if risk_raw is not None else None

            ledger_ids: dict[str, str] = {}
            for slug in (
                "document_intelligence",
                "entity_verification",
                "ubo_graph",
                "screening",
                "risk_scoring",
            ):
                entry = await _find_agent_ledger_entry(self._reader, case_id, slug)
                if entry is not None:
                    ledger_ids[slug] = entry.id

            output = await writing(
                WritingAgentInput(case_id=case_id),
                case=case,
                doc_intel=doc_intel_output,
                entity_verification=ev_output,
                ubo=ubo_output,
                screening=screening_output,
                risk=risk_output,
                ledger_ids=ledger_ids,
                llm=self._writing_llm,
            )

            await IntakeRepo.upsert(session, case_id, "writing", output)
            await session.commit()
            return output

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
