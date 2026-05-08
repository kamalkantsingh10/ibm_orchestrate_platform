"""Tests for the Entity Verification agent — Story 5.1 / AC #11."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from cockpit_api.repositories.case_repo import CaseRepo
from cockpit_api.repositories.intake_repo import IntakeRepo
from cockpit_api.services.ledger_service import LedgerReader, LedgerWriter
from contracts.agent_action import AgentActionLedgerEntry
from contracts.cases import (
    VORA_CAPITAL_ID,
    Case,
    CaseState,
    get_demo_case_fixtures,
)
from contracts.confidence import ConfidenceBand, to_band
from contracts.entity_verification import EntityVerificationInput
from contracts.mca import MCACompanyMaster, MCADirector, MCAShareholder
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from agents.intake.entity_verification import (
    EntityCaseView,
    _compute_mismatches,
    entity_verification,
)
from agents.supervisor.action_decorator import AgentExecutionError
from agents.supervisor.case_supervisor import CaseSupervisor
from agents.tools.mca_lookup import MCALookup, MCANotFoundError, MCATemporaryError
from agents.tools.mca_mock import MockMCALookup
from tests.test_case_supervisor import _session_factory_for

VORA_CIN = "U67120MH2024PTC444789"


# ───────────────────────────── helpers ────────────────────────────────────


class _StubMCALookup(MCALookup):
    """Test double — returns a fixed master OR raises a fixed exception."""

    def __init__(
        self,
        *,
        master: MCACompanyMaster | None = None,
        raises: Exception | None = None,
    ) -> None:
        self._master = master
        self._raises = raises

    async def lookup(self, *, cin: str) -> MCACompanyMaster:  # noqa: ARG002
        if self._raises is not None:
            raise self._raises
        assert self._master is not None
        return self._master


def _vora_master_with(**overrides: Any) -> MCACompanyMaster:
    """Build a Vora master matching the case-side fields, overriding any field for test isolation."""
    base = MCACompanyMaster(
        cin=VORA_CIN,
        company_name="Vora Capital Holdings Pvt Ltd",
        status="active",
        registered_office="Suite 402, Sea Breeze Heights, Bandra West, Mumbai 400050",
        incorporation_date="2024-08-22",
        directors=[
            MCADirector(din="09876543", name="Devansh Vora", designation="managing_director"),
        ],
        shareholders=[
            MCAShareholder(name="Devansh Vora", ownership_pct=100.0, country="IN"),
        ],
    )
    return base.model_copy(update=overrides) if overrides else base


def _vora_case_view() -> EntityCaseView:
    return EntityCaseView(
        company_name="Vora Capital Holdings Pvt Ltd",
        registered_address="Suite 402, Sea Breeze Heights, Bandra West, Mumbai 400050",
        incorporation_date="2024-08-22",
        cin=VORA_CIN,
    )


# ───────────────────────────── happy path ─────────────────────────────────


async def test_happy_path_with_mock_returns_active_high(tmp_writer: LedgerWriter) -> None:
    result = await entity_verification(
        EntityVerificationInput(case_id=VORA_CAPITAL_ID, cin=VORA_CIN),
        mca=MockMCALookup(),
        case_view=_vora_case_view(),
    )
    assert result.case_id == VORA_CAPITAL_ID
    assert result.cin == VORA_CIN
    assert result.mca_status.value == "active"
    assert result.mca_status.provenance.confidence == 0.95
    assert result.mca_status.provenance.confidence_band == ConfidenceBand.HIGH
    assert result.mca_status.provenance.evidence_ids == []  # supervisor back-fills
    # Vora's case-side fields exactly match the mock fixture → no mismatches.
    assert result.mismatches == []


# ───────────────────────────── mismatch detection ─────────────────────────


async def test_mismatch_detection_company_name(tmp_writer: LedgerWriter) -> None:
    stub = _StubMCALookup(master=_vora_master_with(company_name="Vora Holdings Ltd"))
    result = await entity_verification(
        EntityVerificationInput(case_id=VORA_CAPITAL_ID, cin=VORA_CIN),
        mca=stub,
        case_view=_vora_case_view(),
    )
    names = [m.field_name for m in result.mismatches]
    assert names == ["company_name"]
    assert result.mismatches[0].severity == "warning"
    assert result.mismatches[0].case_value == "Vora Capital Holdings Pvt Ltd"
    assert result.mismatches[0].mca_value == "Vora Holdings Ltd"


async def test_critical_date_drift(tmp_writer: LedgerWriter) -> None:
    stub = _StubMCALookup(master=_vora_master_with(incorporation_date="2024-09-01"))
    result = await entity_verification(
        EntityVerificationInput(case_id=VORA_CAPITAL_ID, cin=VORA_CIN),
        mca=stub,
        case_view=_vora_case_view(),
    )
    by_field = {m.field_name: m for m in result.mismatches}
    assert "incorporation_date" in by_field
    assert by_field["incorporation_date"].severity == "critical"


async def test_missing_case_side_field_yields_info_severity(tmp_writer: LedgerWriter) -> None:
    """When ctx.outputs is empty, no doc-intel context is available."""
    stub = _StubMCALookup(master=_vora_master_with())
    empty_view = EntityCaseView(
        company_name=None,
        registered_address=None,
        incorporation_date=None,
        cin=VORA_CIN,
    )
    result = await entity_verification(
        EntityVerificationInput(case_id=VORA_CAPITAL_ID, cin=VORA_CIN),
        mca=stub,
        case_view=empty_view,
    )
    # Three fields (company_name, registered_address, incorporation_date) — all info severity.
    assert {m.field_name for m in result.mismatches} == {
        "company_name",
        "registered_address",
        "incorporation_date",
    }
    for m in result.mismatches:
        assert m.severity == "info"
        assert m.notes == "MCA has field; case does not"


# ───────────────────────────── failure paths ──────────────────────────────


async def test_mca_not_found_raises_agent_execution_error(tmp_writer: LedgerWriter) -> None:
    stub = _StubMCALookup(raises=MCANotFoundError(VORA_CIN))
    with pytest.raises(AgentExecutionError):
        await entity_verification(
            EntityVerificationInput(case_id=VORA_CAPITAL_ID, cin=VORA_CIN),
            mca=stub,
            case_view=_vora_case_view(),
        )
    # The decorator wrote agent.failed.
    entries = await LedgerReader(tmp_writer._path).read_all()
    failures = [e for e in entries if e.action == "agent.failed" and e.actor_id == "entity_verification"]
    assert len(failures) == 1


async def test_mca_temporary_error_raises_agent_execution_error(tmp_writer: LedgerWriter) -> None:
    stub = _StubMCALookup(raises=MCATemporaryError("transient"))
    with pytest.raises(AgentExecutionError):
        await entity_verification(
            EntityVerificationInput(case_id=VORA_CAPITAL_ID, cin=VORA_CIN),
            mca=stub,
            case_view=_vora_case_view(),
        )


async def test_supervisor_routes_not_found_to_escalated(
    engine: AsyncEngine, tmp_writer: LedgerWriter, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end: doc_intel ok + entity_verification raises MCANotFound → escalated."""
    case = await _seed_vora(engine)

    # Inject a stub MCA that always raises not-found.
    import agents.intake.entity_verification as ev_mod

    monkeypatch.setattr(ev_mod, "get_default_mca_lookup", lambda: _StubMCALookup(raises=MCANotFoundError(VORA_CIN)))

    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    outcome = await supervisor.run_intake(case.id)

    assert outcome.status == "blocked"
    assert outcome.failed_agent == "entity_verification"
    assert "no company master" in (outcome.error_message or "")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        refreshed = await CaseRepo.get(session, case.id)
        assert refreshed is not None
        assert refreshed.state is CaseState.ESCALATED
        assert refreshed.customer_metadata.extra.get("blocked_agent") == "entity_verification"


async def test_supervisor_routes_temporary_to_escalated(
    engine: AsyncEngine, tmp_writer: LedgerWriter, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = await _seed_vora(engine)
    import agents.intake.entity_verification as ev_mod

    monkeypatch.setattr(ev_mod, "get_default_mca_lookup", lambda: _StubMCALookup(raises=MCATemporaryError("MCA temp")))
    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    outcome = await supervisor.run_intake(case.id)
    assert outcome.status == "blocked"
    assert outcome.failed_agent == "entity_verification"


# ───────────────────────────── ledger entry shape ─────────────────────────


async def test_ledger_entry_shape(tmp_writer: LedgerWriter) -> None:
    """The decorator records the right input/output/model_id."""
    await entity_verification(
        EntityVerificationInput(case_id=VORA_CAPITAL_ID, cin=VORA_CIN),
        mca=MockMCALookup(),
        case_view=_vora_case_view(),
    )
    entries = await LedgerReader(tmp_writer._path).read_all()
    completed = [e for e in entries if e.action == "agent.completed" and e.actor_id == "entity_verification"]
    assert len(completed) == 1
    payload = completed[0].payload
    assert isinstance(payload, AgentActionLedgerEntry)
    assert payload.agent_id == "entity_verification"
    assert payload.model_id == "deterministic"
    assert payload.input["cin"] == VORA_CIN
    assert payload.output is not None
    assert payload.output["mca_status"]["value"] == "active"
    # Per Story 5.1 dev notes pitfall #8: tool_calls is intentionally [] in the
    # interim. Story 6.x's reasoning trace work will revisit.
    assert payload.tool_calls == []


# ───────────────────────────── evidence_ids back-fill ─────────────────────


async def test_evidence_ids_back_filled_by_supervisor(engine: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    case = await _seed_vora(engine)
    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    outcome = await supervisor.run_intake(case.id)
    assert outcome.status == "completed"
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        ev_row = await IntakeRepo.get_one(session, case.id, "entity_verification")
        assert ev_row is not None
        evidence_ids = ev_row["mca_status"]["provenance"]["evidence_ids"]
        assert len(evidence_ids) == 1
        assert evidence_ids[0].startswith("led_")

        # Cross-check: that ledger_id matches the entity_verification agent.completed entry.
        reader = LedgerReader(tmp_writer._path)
        entries = await reader.read_for_case(case.id)
        ev_entries = [e for e in entries if e.actor_id == "entity_verification" and e.action == "agent.completed"]
        assert len(ev_entries) == 1
        assert evidence_ids[0] == ev_entries[0].id


# ───────────────────────────── provenance band consistency ────────────────


def test_provenance_band_matches_confidence() -> None:
    assert to_band(0.95) == ConfidenceBand.HIGH


# ───────────────────────────── _compute_mismatches unit ───────────────────


def test_compute_mismatches_normalization_collapses_whitespace_and_case() -> None:
    master = _vora_master_with(company_name="VORA  CAPITAL  HOLDINGS pvt ltd.")
    view = EntityCaseView(
        company_name="vora capital holdings pvt ltd",
        registered_address=master.registered_office,
        incorporation_date=master.incorporation_date,
        cin=VORA_CIN,
    )
    assert _compute_mismatches(view, master) == []


def test_compute_mismatches_case_only_field_yields_info() -> None:
    master = _vora_master_with(company_name="Vora Co")  # MCA has it
    view = EntityCaseView(
        company_name=None,
        registered_address=master.registered_office,
        incorporation_date=master.incorporation_date,
        cin=VORA_CIN,
    )
    mismatches = _compute_mismatches(view, master)
    assert len(mismatches) == 1
    assert mismatches[0].field_name == "company_name"
    assert mismatches[0].severity == "info"
    assert mismatches[0].notes == "MCA has field; case does not"


# ───────────────────────────── seed helpers ───────────────────────────────


async def _seed_vora(engine: AsyncEngine) -> Case:
    cases = get_demo_case_fixtures(datetime.now(UTC))
    target = next(c for c in cases if c.id == VORA_CAPITAL_ID)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await CaseRepo.insert(session, target)
        await session.commit()
    return target


# ───────────── Story 6.4 — reasoning trace ─────────────


async def test_entity_verification_emits_reasoning_trace(tmp_writer: LedgerWriter) -> None:
    master = _vora_master_with()
    await entity_verification(
        EntityVerificationInput(case_id=VORA_CAPITAL_ID, cin=VORA_CIN),
        mca=_StubMCALookup(master=master),
        case_view=EntityCaseView(
            company_name="Vora Capital Holdings Pvt Ltd",
            registered_address=None,
            incorporation_date=None,
            cin=VORA_CIN,
        ),
    )
    entries = await LedgerReader(tmp_writer._path).read_for_case(VORA_CAPITAL_ID)
    payload = entries[-1].payload
    assert isinstance(payload, AgentActionLedgerEntry)
    rt = payload.reasoning_trace
    assert rt is not None
    assert VORA_CIN in rt.what_searched
    assert "MCA status" in rt.what_hit
    # confidence_self_rating.band matches mca_status.provenance.confidence_band
    assert rt.confidence_self_rating.band == ConfidenceBand.HIGH  # mock returns 0.95
