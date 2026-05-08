"""Tests for CaseSupervisor — Story 3.5 / AC #10."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import pytest
from cockpit_api.repositories.case_repo import CaseRepo
from cockpit_api.repositories.intake_repo import IntakeRepo
from cockpit_api.services.ledger_service import LedgerReader, LedgerWriter
from contracts.cases import (
    SHREE_VENKAT_ID,
    VORA_CAPITAL_ID,
    Case,
    CaseState,
    CustomerMetadata,
    get_demo_case_fixtures,
)
from contracts.document_intelligence import DocumentIntelligenceOutput
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

import agents.supervisor.case_supervisor as supervisor_mod
from agents.supervisor.action_decorator import AgentExecutionError
from agents.supervisor.case_supervisor import (
    CaseNotFoundError,
    CaseNotIntakeReadyError,
    CaseSupervisor,
    _fill_evidence_ids,
)


def _session_factory_for(
    engine: AsyncEngine,
) -> Any:
    factory = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def _f() -> AsyncIterator[AsyncSession]:
        async with factory() as s:
            yield s

    return _f


async def _seed_case(engine: AsyncEngine, *, state: CaseState = CaseState.INTAKE_SCHEDULED) -> Case:
    """Insert one demo case into the DB and return its contract."""
    cases = get_demo_case_fixtures(datetime.now(UTC))
    target = next(c for c in cases if c.id == VORA_CAPITAL_ID)
    if state is not CaseState.INTAKE_SCHEDULED:
        target = target.model_copy(update={"state": state})
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await CaseRepo.insert(session, target)
        await session.commit()
    return target


# ───────────── happy path ─────────────


async def test_happy_path_completes_and_persists(engine: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    case = await _seed_case(engine)
    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    outcome = await supervisor.run_intake(case.id)

    assert outcome.status == "completed"
    # Story 6.2: Vora has a CIN — five-agent fan-out incl. screening + risk_scoring.
    assert outcome.agents_run == [
        "document_intelligence",
        "entity_verification",
        "ubo_graph",
        "screening",
        "risk_scoring",
    ]
    assert outcome.fields_extracted > 0
    assert outcome.failed_agent is None

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        refreshed = await CaseRepo.get(session, case.id)
        assert refreshed is not None
        assert refreshed.state is CaseState.DECISION_READY
        row = await IntakeRepo.get_one(session, case.id, "document_intelligence")
        assert row is not None
        revived = DocumentIntelligenceOutput.model_validate(row)
        assert len(revived.extracted_fields) == outcome.fields_extracted
        for f in revived.extracted_fields:
            assert len(f.value.provenance.evidence_ids) == 1
            assert f.value.provenance.evidence_ids[0].startswith("led_")


# ───────────── agent failure ─────────────


async def test_agent_failure_via_agent_execution_error(
    engine: AsyncEngine, tmp_writer: LedgerWriter, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = await _seed_case(engine)

    async def boom(_: Any) -> Any:
        raise AgentExecutionError(
            agent_id="document_intelligence",
            case_id=case.id,
            original=ValueError("doc-ai down"),
        )

    monkeypatch.setattr(supervisor_mod, "document_intelligence", boom)

    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    outcome = await supervisor.run_intake(case.id)

    assert outcome.status == "blocked"
    assert outcome.failed_agent == "document_intelligence"
    assert "doc-ai down" in (outcome.error_message or "")
    assert outcome.fields_extracted == 0

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        refreshed = await CaseRepo.get(session, case.id)
        assert refreshed is not None
        assert refreshed.state is CaseState.ESCALATED
        assert refreshed.customer_metadata.extra.get("blocked_agent") == "document_intelligence"
        assert "doc-ai down" in refreshed.customer_metadata.extra.get("block_reason", "")


# ───────────── empty document_refs ─────────────


async def test_empty_document_refs_completes_with_zero_fields(engine: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    # Build a case with no document_refs
    now = datetime.now(UTC)
    case = Case(
        id=SHREE_VENKAT_ID,
        state=CaseState.INTAKE_SCHEDULED,
        customer_metadata=CustomerMetadata(customer_name="Empty Co", extra={}),
        created_at=now,
        updated_at=now,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await CaseRepo.insert(session, case)
        await session.commit()

    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    outcome = await supervisor.run_intake(case.id)

    assert outcome.status == "completed"
    # Story 6.2: screening + risk_scoring run always; doc_intel/entity_verification/ubo_graph skipped.
    assert outcome.agents_run == ["screening", "risk_scoring"]
    assert outcome.fields_extracted == 0


# ───────────── missing case ─────────────


async def test_missing_case_raises(engine: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    with pytest.raises(CaseNotFoundError):
        await supervisor.run_intake(VORA_CAPITAL_ID)


# ───────────── wrong state ─────────────


async def test_wrong_state_raises(engine: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    case = await _seed_case(engine, state=CaseState.DECISION_READY)
    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    with pytest.raises(CaseNotIntakeReadyError):
        await supervisor.run_intake(case.id)


# ───────────── idempotency ─────────────


async def test_second_run_raises_not_intake_ready(engine: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    case = await _seed_case(engine)
    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    first = await supervisor.run_intake(case.id)
    assert first.status == "completed"
    with pytest.raises(CaseNotIntakeReadyError):
        await supervisor.run_intake(case.id)


# ───────────── _fill_evidence_ids helper ─────────────


def test_fill_evidence_ids_helper(tmp_writer: LedgerWriter) -> None:
    from contracts.confidence import to_band
    from contracts.document_intelligence import ExtractedField
    from contracts.provenance import Provenance, ProvenancedField
    from ulid import ULID

    led_id = f"led_{ULID()!s}"
    pf: ProvenancedField[str | int | float | bool | None] = ProvenancedField(
        value="X",
        provenance=Provenance(
            source_agent="document_intelligence",
            source_system="fixture_doc_ai",
            confidence=0.9,
            confidence_band=to_band(0.9),
            evidence_ids=[],
            captured_at=datetime.now(UTC),
        ),
    )
    out = DocumentIntelligenceOutput(
        case_id=VORA_CAPITAL_ID,
        extracted_fields=[
            ExtractedField(field_name="x", document_ref="a.pdf", value=pf),
            ExtractedField(field_name="y", document_ref="b.pdf", value=pf),
        ],
    )
    filled = _fill_evidence_ids(out, led_id)
    assert all(f.value.provenance.evidence_ids == [led_id] for f in filled.extracted_fields)
    # Original unchanged (frozen)
    assert all(f.value.provenance.evidence_ids == [] for f in out.extracted_fields)


# ───────────── ledger entries ─────────────


async def test_completed_writes_intake_completed_entry(engine: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    case = await _seed_case(engine)
    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    await supervisor.run_intake(case.id)

    reader = LedgerReader(tmp_writer._path)
    entries = await reader.read_for_case(case.id)
    actions = [e.action for e in entries]
    assert "case.intake_completed" in actions
    completed_entry = next(e for e in entries if e.action == "case.intake_completed")
    assert completed_entry.actor_id == "case_supervisor"
    assert isinstance(completed_entry.payload, dict)
    assert completed_entry.payload.get("agents") == [
        "document_intelligence",
        "entity_verification",
        "ubo_graph",
        "screening",
        "risk_scoring",
    ]


async def test_blocked_writes_intake_blocked_entry(
    engine: AsyncEngine, tmp_writer: LedgerWriter, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = await _seed_case(engine)

    async def boom(_: Any) -> Any:
        raise AgentExecutionError(
            agent_id="document_intelligence",
            case_id=case.id,
            original=RuntimeError("nope"),
        )

    monkeypatch.setattr(supervisor_mod, "document_intelligence", boom)

    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    await supervisor.run_intake(case.id)

    reader = LedgerReader(tmp_writer._path)
    entries = await reader.read_for_case(case.id)
    actions = [e.action for e in entries]
    assert "case.intake_blocked" in actions


# ───────────── notify hook ─────────────


async def test_notify_hook_called_on_completion(engine: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    case = await _seed_case(engine)
    calls: list[tuple[str, str, dict[str, Any]]] = []

    async def notify(case_id: str, event: str, payload: dict[str, Any]) -> None:
        calls.append((case_id, event, payload))

    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine), notify=notify)
    await supervisor.run_intake(case.id)

    assert len(calls) == 1
    assert calls[0][0] == case.id
    assert calls[0][1] == "case.intake_completed"


# ───────────── Story 5.1: two-agent fan-out ─────────────


async def test_two_agent_fan_out_records_doc_intel_then_entity(engine: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    """Vora has both document_refs and a CIN — five agents run (Story 6.2)."""
    case = await _seed_case(engine)
    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    outcome = await supervisor.run_intake(case.id)

    assert outcome.status == "completed"
    assert outcome.agents_run == [
        "document_intelligence",
        "entity_verification",
        "ubo_graph",
        "screening",
        "risk_scoring",
    ]

    reader = LedgerReader(tmp_writer._path)
    entries = await reader.read_for_case(case.id)
    actions = [e.action for e in entries]
    actors = [e.actor_id for e in entries]
    # Five intake-fan-out agent.completed entries + 1 writing post-hook +
    # case.intake_completed. Story 7.3 added the writing post-hook.
    assert actions.count("agent.completed") == 6
    assert actors.count("entity_verification") == 1
    assert actors.count("document_intelligence") == 1
    assert actors.count("ubo_graph") == 1
    assert actors.count("screening") == 1
    assert actors.count("risk_scoring") == 1
    assert actors.count("writing") == 1
    assert "case.intake_completed" in actions

    # All five intake_results rows persist.
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        di_row = await IntakeRepo.get_one(session, case.id, "document_intelligence")
        ev_row = await IntakeRepo.get_one(session, case.id, "entity_verification")
        ubo_row = await IntakeRepo.get_one(session, case.id, "ubo_graph")
        scr_row = await IntakeRepo.get_one(session, case.id, "screening")
        risk_row = await IntakeRepo.get_one(session, case.id, "risk_scoring")
        assert di_row is not None
        assert ev_row is not None
        assert ubo_row is not None
        assert scr_row is not None
        assert risk_row is not None
        assert ev_row["mca_status"]["value"] == "active"
        assert ubo_row["root_entity_id"].startswith("ubo_e_")
        # Vora's screening hit (Rohan Mehta → OFAC SDN) is present and back-filled.
        assert scr_row["subjects_screened"] >= 1
        assert any(
            "sanctions" in hit["categories"] and hit["name_match_score"]["provenance"]["evidence_ids"]
            for hit in scr_row["hits"]
        )
        assert 0 <= risk_row["total"] <= 100


async def test_doc_intel_ok_then_entity_verification_temporary_error_escalates(
    engine: AsyncEngine, tmp_writer: LedgerWriter, monkeypatch: pytest.MonkeyPatch
) -> None:
    """document_intelligence succeeds; entity_verification's MCA call raises MCATemporaryError."""
    from agents.tools.mca_lookup import MCATemporaryError

    case = await _seed_case(engine)

    class _BoomMCA:
        async def lookup(self, *, cin: str) -> Any:  # noqa: ARG002
            raise MCATemporaryError("MCA down")

    import agents.intake.entity_verification as ev_mod

    monkeypatch.setattr(ev_mod, "get_default_mca_lookup", lambda: _BoomMCA())

    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    outcome = await supervisor.run_intake(case.id)

    assert outcome.status == "blocked"
    assert outcome.agents_run == ["document_intelligence", "entity_verification"]
    assert outcome.failed_agent == "entity_verification"
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        refreshed = await CaseRepo.get(session, case.id)
        assert refreshed is not None
        assert refreshed.state is CaseState.ESCALATED
        assert refreshed.customer_metadata.extra.get("blocked_agent") == "entity_verification"


async def test_case_without_cin_skips_entity_verification(engine: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    """Build a case with documents but no registration_number — entity_verification is skipped."""
    now = datetime.now(UTC)
    case = Case(
        id=SHREE_VENKAT_ID,
        state=CaseState.INTAKE_SCHEDULED,
        customer_metadata=CustomerMetadata(
            customer_name="No CIN Co",
            extra={
                "document_refs": ["incorporation_certificate.pdf"],
                # no registration_number
            },
        ),
        created_at=now,
        updated_at=now,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await CaseRepo.insert(session, case)
        await session.commit()

    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    outcome = await supervisor.run_intake(case.id)

    assert outcome.status == "completed"
    assert "entity_verification" not in outcome.agents_run
    # Story 6.2: screening + risk_scoring run always; ubo_graph skipped (no CIN).
    assert outcome.agents_run == ["document_intelligence", "screening", "risk_scoring"]
    # Verify no entity_verification ledger entry written.
    reader = LedgerReader(tmp_writer._path)
    entries = await reader.read_for_case(case.id)
    actors = [e.actor_id for e in entries]
    assert "entity_verification" not in actors


# ───────────── Story 6.2 — screening fan-out ─────────────


async def test_vora_intake_screening_hits_ofac(engine: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    """Vora's Rohan Mehta director should hit OFAC SDN at 0.73 sanctions."""
    from contracts.screening import ScreeningAgentOutput

    case = await _seed_case(engine)
    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    outcome = await supervisor.run_intake(case.id)

    assert outcome.status == "completed"
    assert "screening" in outcome.agents_run

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        scr_row = await IntakeRepo.get_one(session, case.id, "screening")
    assert scr_row is not None
    out = ScreeningAgentOutput.model_validate(scr_row)
    sanctions_hits = [h for h in out.hits if "sanctions" in h.categories]
    assert len(sanctions_hits) >= 1
    rohan_hit = next(h for h in sanctions_hits if h.subject_id == "ubo_p_09876544")
    assert rohan_hit.disposition == "open"
    # Evidence_ids back-filled with the screening agent's ledger entry id.
    assert len(rohan_hit.name_match_score.provenance.evidence_ids) == 1
    assert rohan_hit.name_match_score.provenance.evidence_ids[0].startswith("led_")


async def test_shree_intake_screening_no_hits(engine: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    """Shree's clean entity → no hits, but the agent.completed entry is still written."""
    from contracts.screening import ScreeningAgentOutput

    cases = get_demo_case_fixtures(datetime.now(UTC))
    shree = next(c for c in cases if c.id == SHREE_VENKAT_ID)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await CaseRepo.insert(session, shree)
        await session.commit()

    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    outcome = await supervisor.run_intake(shree.id)

    assert outcome.status == "completed"
    assert "screening" in outcome.agents_run

    async with factory() as session:
        scr_row = await IntakeRepo.get_one(session, shree.id, "screening")
    assert scr_row is not None
    out = ScreeningAgentOutput.model_validate(scr_row)
    assert out.hits == []

    reader = LedgerReader(tmp_writer._path)
    entries = await reader.read_for_case(shree.id)
    assert any(e.actor_id == "screening" and e.action == "agent.completed" for e in entries)


async def test_ananya_intake_screening_pep_hit(engine: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    """Ananya's individual case → PEP hit at 0.88, disposition open (high enough)."""
    from contracts.cases import ANANYA_IYER_ID
    from contracts.screening import ScreeningAgentOutput

    cases = get_demo_case_fixtures(datetime.now(UTC))
    ananya = next(c for c in cases if c.id == ANANYA_IYER_ID)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await CaseRepo.insert(session, ananya)
        await session.commit()

    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    outcome = await supervisor.run_intake(ananya.id)
    assert outcome.status == "completed"

    async with factory() as session:
        scr_row = await IntakeRepo.get_one(session, ananya.id, "screening")
    assert scr_row is not None
    out = ScreeningAgentOutput.model_validate(scr_row)
    pep_hits = [h for h in out.hits if "pep" in h.categories]
    assert len(pep_hits) == 1
    assert pep_hits[0].disposition == "open"
    assert pep_hits[0].name_match_score.value == pytest.approx(0.88)


async def test_build_screening_subjects_covers_entity_director_and_ubo(
    engine: AsyncEngine, tmp_writer: LedgerWriter
) -> None:
    """Direct unit test of the supervisor's subject-builder helper."""
    from contracts.ubo import UBOGraphInput

    from agents.intake.ubo_graph import ubo_graph
    from agents.supervisor.case_supervisor import IntakeContext, _build_screening_subjects

    case = await _seed_case(engine)
    ctx = IntakeContext(case=case)
    # Run UBO graph so the builder has something to enumerate.
    graph = await ubo_graph(UBOGraphInput(case_id=case.id, cin="U67120MH2024PTC444789"))
    ctx.outputs["ubo_graph"] = graph

    subjects = await _build_screening_subjects(ctx)
    kinds = {s.subject_kind for s in subjects}
    assert "entity" in kinds
    assert "director" in kinds
    # Rohan Mehta (UBO) is also a director — director subject_id covers him.
    director_ids = {s.subject_id for s in subjects if s.subject_kind == "director"}
    assert "ubo_p_09876544" in director_ids


# ───────────── Story 7.3 — run_writing ─────────────


async def test_run_intake_kicks_writing_post_hook(
    engine: AsyncEngine,
    tmp_writer: LedgerWriter,
) -> None:
    """Vora intake → writing runs automatically; intake row carries `writing` output."""
    case = await _seed_case(engine)
    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    outcome = await supervisor.run_intake(case.id)
    assert outcome.status == "completed"

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        row = await IntakeRepo.get_one(session, case.id, "writing")
    assert row is not None
    assert row["case_id"] == case.id
    assert row["html"].startswith("<p>")
    assert 2 <= len(row["paragraphs"]) <= 4

    reader = LedgerReader(tmp_writer._path)
    entries = await reader.read_for_case(case.id)
    assert any(e.actor_id == "writing" and e.action == "agent.completed" for e in entries)


async def test_writing_failure_does_not_roll_back_intake(
    engine: AsyncEngine,
    tmp_writer: LedgerWriter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agents.adapters.writing.base import RawRationaleDraft, WritingLLMError

    class _BoomLLM:
        model_id = "boom"

        async def draft_rationale(self, *, rendered_prompt: str) -> RawRationaleDraft:
            raise WritingLLMError("kaboom")

    case = await _seed_case(engine)
    supervisor = CaseSupervisor(
        session_factory=_session_factory_for(engine),
        writing_llm=_BoomLLM(),
    )
    outcome = await supervisor.run_intake(case.id)
    # Intake still completes; writing failure is swallowed.
    assert outcome.status == "completed"

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        row = await IntakeRepo.get_one(session, case.id, "writing")
        refreshed = await CaseRepo.get(session, case.id)
    assert row is None  # writing never persisted
    assert refreshed is not None
    assert refreshed.state is CaseState.DECISION_READY  # intake transitioned

    # An agent.failed entry was written for writing, but intake completed.
    reader = LedgerReader(tmp_writer._path)
    entries = await reader.read_for_case(case.id)
    failed = [e for e in entries if e.actor_id == "writing" and e.action == "agent.failed"]
    assert len(failed) == 1


async def test_run_writing_rejects_when_state_is_intake_scheduled(
    engine: AsyncEngine,
    tmp_writer: LedgerWriter,
) -> None:
    from agents.supervisor.case_supervisor import CaseNotInDecisionReadyError

    case = await _seed_case(engine)  # state = INTAKE_SCHEDULED
    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    with pytest.raises(CaseNotInDecisionReadyError):
        await supervisor.run_writing(case.id)


async def test_run_writing_rejects_when_document_intelligence_missing(
    engine: AsyncEngine,
    tmp_writer: LedgerWriter,
) -> None:
    from agents.supervisor.case_supervisor import WritingPrerequisitesMissingError

    # Seed a case directly in DECISION_READY state, but never run intake —
    # so no doc_intel row exists in the intake_results table.
    case = await _seed_case(engine, state=CaseState.DECISION_READY)
    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    with pytest.raises(WritingPrerequisitesMissingError):
        await supervisor.run_writing(case.id)


async def test_run_writing_succeeds_on_a_committed_case(
    engine: AsyncEngine,
    tmp_writer: LedgerWriter,
) -> None:
    """Re-draft path — chat agent triggers re_run_agent('writing') on a
    committed case; the new draft replaces the old in the intake row,
    while the ledger preserves history (a fresh agent.completed entry
    lands)."""
    case = await _seed_case(engine)
    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    await supervisor.run_intake(case.id)

    # Flip case state to committed via PENDING_SEAL — direct
    # decision_ready → committed transition was removed by Story 7.4.
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await CaseRepo.transition(session, case.id, CaseState.PENDING_SEAL)
        await CaseRepo.transition(session, case.id, CaseState.COMMITTED)
        await session.commit()

    output = await supervisor.run_writing(case.id)
    assert output.case_id == case.id

    reader = LedgerReader(tmp_writer._path)
    entries = await reader.read_for_case(case.id)
    completed = [e for e in entries if e.actor_id == "writing" and e.action == "agent.completed"]
    # First from the post-intake hook + second from this manual re-run.
    assert len(completed) == 2
