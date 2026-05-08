"""Tests for the Risk Scoring agent — Story 5.6 / AC #10."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from cockpit_api.repositories.case_repo import CaseRepo
from cockpit_api.repositories.intake_repo import IntakeRepo
from cockpit_api.services.ledger_service import LedgerReader, LedgerWriter
from contracts.agent_action import AgentActionLedgerEntry
from contracts.cases import (
    ANANYA_IYER_ID,
    SHREE_VENKAT_ID,
    VORA_CAPITAL_ID,
    Case,
    get_demo_case_fixtures,
)
from contracts.confidence import ConfidenceBand, to_band
from contracts.provenance import Provenance, ProvenancedField
from contracts.risk import RiskScoringInput
from contracts.ubo import UBOEdge, UBOEntityNode, UBOGraph, UBOPersonNode
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from agents.intake.risk_scoring import RiskCaseView, risk_scoring
from agents.supervisor.action_decorator import AgentExecutionError
from agents.supervisor.case_supervisor import CaseSupervisor
from agents.tools.mca_mock import MockMCALookup
from tests.test_case_supervisor import _session_factory_for

VORA_CIN = "U67120MH2024PTC444789"

# Pinned Vora UBO graph mirror of cockpit-api/tests/fixtures/ubo_graph_vora.py.
# Inlined here to avoid cross-package import which mypy strict rejects.
VORA_ROOT_ID = "ubo_e_u67120mh2024ptc444789"
DEVANSH_ID = "ubo_p_09876543"
ROHAN_ID = "ubo_p_09876544"
FILING_ID = "ubo_p_09876545"
COASTAL_ID = "ubo_e_coastal_equity_partners_pte_ltd"
ANCHOR_ID = "ubo_e_anchor_trust_services_bvi"


def _pf(c: float) -> ProvenancedField[float]:
    return ProvenancedField(
        value=c,
        provenance=Provenance(
            source_agent="ubo_graph",
            source_system="mca_mock",
            confidence=c,
            confidence_band=to_band(c),
            evidence_ids=[],
            captured_at=datetime.now(UTC),
        ),
    )


def make_vora_graph() -> UBOGraph:
    return UBOGraph(
        case_id=VORA_CAPITAL_ID,
        root_entity_id=VORA_ROOT_ID,
        nodes=[
            UBOEntityNode(
                id=VORA_ROOT_ID,
                name="Vora Capital Holdings Pvt Ltd",
                cin="U67120MH2024PTC444789",
                country="IN",
            ),
            UBOPersonNode(id=DEVANSH_ID, name="Devansh Vora", din="09876543"),
            UBOPersonNode(id=ROHAN_ID, name="Rohan Mehta", din="09876544"),
            UBOPersonNode(id=FILING_ID, name="A K Filing Services", din="09876545"),
            UBOEntityNode(
                id=COASTAL_ID,
                name="Coastal Equity Partners Pte Ltd",
                country="SG",
                is_corporate=True,
            ),
            UBOEntityNode(
                id=ANCHOR_ID,
                name="Anchor Trust Services (BVI)",
                country="VG",
                is_corporate=True,
            ),
        ],
        edges=[
            UBOEdge(
                kind="director",
                from_id=DEVANSH_ID,
                to_id=VORA_ROOT_ID,
                designation="managing_director",
                confidence=_pf(0.95),
            ),
            UBOEdge(
                kind="director",
                from_id=ROHAN_ID,
                to_id=VORA_ROOT_ID,
                designation="director",
                confidence=_pf(0.95),
            ),
            UBOEdge(
                kind="director",
                from_id=FILING_ID,
                to_id=VORA_ROOT_ID,
                designation="nominee_director",
                confidence=_pf(0.55),
                nominee_flag="nominee_suspected",
                rationale="MCA explicitly designates appointment as nominee_director",
            ),
            UBOEdge(
                kind="owns",
                from_id=DEVANSH_ID,
                to_id=VORA_ROOT_ID,
                ownership_pct=5.0,
                confidence=_pf(0.92),
            ),
            UBOEdge(
                kind="owns",
                from_id=COASTAL_ID,
                to_id=VORA_ROOT_ID,
                ownership_pct=70.0,
                confidence=_pf(0.55),
                nominee_flag="nominee_suspected",
                rationale="Foreign corporate holder (SG) with 70.0% ownership",
            ),
            UBOEdge(
                kind="owns",
                from_id=ANCHOR_ID,
                to_id=VORA_ROOT_ID,
                ownership_pct=25.0,
                confidence=_pf(0.55),
                nominee_flag="nominee_suspected",
                rationale="Foreign corporate holder (VG) with 25.0% ownership",
            ),
        ],
    )


def _vora_case() -> Case:
    fixtures = get_demo_case_fixtures(datetime.now(UTC))
    return next(c for c in fixtures if c.id == VORA_CAPITAL_ID)


def _shree_case() -> Case:
    fixtures = get_demo_case_fixtures(datetime.now(UTC))
    return next(c for c in fixtures if c.id == SHREE_VENKAT_ID)


def _ananya_case() -> Case:
    fixtures = get_demo_case_fixtures(datetime.now(UTC))
    return next(c for c in fixtures if c.id == ANANYA_IYER_ID)


# ───────────────────────────── happy paths ────────────────────────────────


async def test_shree_clean_sme_lands_in_low_band(tmp_writer: LedgerWriter) -> None:
    """Shree has clean UBO (no nominee_suspected); expected low band."""
    shree = _shree_case()
    # Build a clean Shree-shaped UBO graph by running the agent against MCA mock.
    from contracts.ubo import UBOGraphInput

    from agents.intake.ubo_graph import ubo_graph as ubo_graph_agent

    graph = await ubo_graph_agent(
        UBOGraphInput(case_id=SHREE_VENKAT_ID, cin="U51900MH2018PTC312456"),
        mca=MockMCALookup(),
    )
    view = RiskCaseView(
        case=shree,
        entity_verification=None,
        ubo_graph=graph,
        screening_hit_hint=None,
        adverse_media_hint=None,
    )
    score = await risk_scoring(RiskScoringInput(case_id=shree.id), case_view=view)
    assert score.band == "low"
    assert score.total <= 34
    by_name = {c.name: c for c in score.components}
    assert by_name["country"].value == 10.0
    assert by_name["entity_type"].value == 30.0
    assert by_name["ownership_clarity"].value == 40.0
    assert by_name["screening"].value == 0.0


async def test_vora_pre_correction_lands_in_medium_band(tmp_writer: LedgerWriter) -> None:
    """Vora pre-correction has 3 nominee_suspected edges → medium band."""
    vora = _vora_case()
    graph = make_vora_graph()
    view = RiskCaseView(
        case=vora,
        entity_verification=None,
        ubo_graph=graph,
        screening_hit_hint=None,
        adverse_media_hint=None,
    )
    score = await risk_scoring(RiskScoringInput(case_id=vora.id), case_view=view)
    assert score.band == "medium"
    assert 35 <= score.total <= 45
    by_name = {c.name: c for c in score.components}
    assert by_name["country"].value == 10.0
    assert by_name["entity_type"].value == 70.0  # foreign-corporate holders
    assert by_name["ownership_clarity"].value == 70.0  # 40 + 3*10


async def test_vora_post_correction_drops_to_low(tmp_writer: LedgerWriter) -> None:
    """Officer flips Coastal to officer_corrected → ownership_clarity drops."""
    vora = _vora_case()
    graph = make_vora_graph()
    new_edges: list[UBOEdge] = []
    for edge in graph.edges:
        if edge.from_id == COASTAL_ID and edge.kind == "owns":
            new_edges.append(edge.model_copy(update={"nominee_flag": "officer_corrected"}))
        else:
            new_edges.append(edge)
    corrected = graph.model_copy(update={"edges": new_edges})
    view = RiskCaseView(
        case=vora,
        entity_verification=None,
        ubo_graph=corrected,
        screening_hit_hint=None,
        adverse_media_hint=None,
    )
    score = await risk_scoring(RiskScoringInput(case_id=vora.id), case_view=view)
    by_name = {c.name: c for c in score.components}
    # ownership_clarity = 40 + 2 nominee_suspected * 10 - 1 officer_corrected * 4 = 56
    assert by_name["ownership_clarity"].value == 56.0
    assert score.band == "low"


async def test_ananya_with_screening_hit_lands_in_medium(tmp_writer: LedgerWriter) -> None:
    ananya = _ananya_case()
    view = RiskCaseView(
        case=ananya,
        entity_verification=None,
        ubo_graph=None,
        screening_hit_hint={"name_match": True},  # truthy
        adverse_media_hint=None,
    )
    score = await risk_scoring(RiskScoringInput(case_id=ananya.id), case_view=view)
    assert score.band == "medium"
    by_name = {c.name: c for c in score.components}
    assert by_name["screening"].value == 60.0
    assert by_name["country"].value == 20.0  # individual
    assert by_name["entity_type"].value == 25.0  # individual
    assert by_name["ownership_clarity"].value == 50.0  # opaque (no UBO graph)


# ───────────────────────────── opacity ────────────────────────────────────


async def test_no_ubo_graph_treats_as_opaque(tmp_writer: LedgerWriter) -> None:
    case = _ananya_case()
    view = RiskCaseView(
        case=case,
        entity_verification=None,
        ubo_graph=None,
        screening_hit_hint=None,
        adverse_media_hint=None,
    )
    score = await risk_scoring(RiskScoringInput(case_id=case.id), case_view=view)
    by_name = {c.name: c for c in score.components}
    assert by_name["ownership_clarity"].value == 50.0
    assert "opaque" in by_name["ownership_clarity"].rationale.lower()


# ───────────────────────────── provenance ─────────────────────────────────


async def test_provenance_band_is_high(tmp_writer: LedgerWriter) -> None:
    view = RiskCaseView(
        case=_shree_case(),
        entity_verification=None,
        ubo_graph=None,
        screening_hit_hint=None,
        adverse_media_hint=None,
    )
    score = await risk_scoring(RiskScoringInput(case_id=SHREE_VENKAT_ID), case_view=view)
    assert score.score_provenance.provenance.confidence_band == ConfidenceBand.HIGH
    assert score.score_provenance.provenance.confidence == 0.85


# ───────────────────────────── ledger entry ───────────────────────────────


async def test_ledger_entry_shape(tmp_writer: LedgerWriter) -> None:
    view = RiskCaseView(
        case=_shree_case(),
        entity_verification=None,
        ubo_graph=None,
        screening_hit_hint=None,
        adverse_media_hint=None,
    )
    await risk_scoring(RiskScoringInput(case_id=SHREE_VENKAT_ID), case_view=view)
    entries = await LedgerReader(tmp_writer._path).read_all()
    completed = [e for e in entries if e.action == "agent.completed" and e.actor_id == "risk_scoring"]
    assert len(completed) == 1
    payload = completed[0].payload
    assert isinstance(payload, AgentActionLedgerEntry)
    assert payload.agent_id == "risk_scoring"
    assert payload.model_id == "deterministic"
    assert payload.output is not None
    assert 0 <= payload.output["total"] <= 100


# ───────────────────────────── idempotency ────────────────────────────────


async def test_idempotent_same_inputs(tmp_writer: LedgerWriter) -> None:
    view = RiskCaseView(
        case=_vora_case(),
        entity_verification=None,
        ubo_graph=make_vora_graph(),
        screening_hit_hint=None,
        adverse_media_hint=None,
    )
    score_a = await risk_scoring(RiskScoringInput(case_id=VORA_CAPITAL_ID), case_view=view)
    score_b = await risk_scoring(RiskScoringInput(case_id=VORA_CAPITAL_ID), case_view=view)
    assert score_a.total == score_b.total
    assert score_a.band == score_b.band
    assert [c.value for c in score_a.components] == [c.value for c in score_b.components]


# ───────────────────────────── failure modes ──────────────────────────────


async def test_missing_case_view_raises(tmp_writer: LedgerWriter) -> None:
    with pytest.raises(AgentExecutionError):
        await risk_scoring(RiskScoringInput(case_id=VORA_CAPITAL_ID))


# ───────────────────────────── supervisor end-to-end ──────────────────────


async def _seed_vora(engine: AsyncEngine) -> Case:
    fixtures = get_demo_case_fixtures(datetime.now(UTC))
    target = next(c for c in fixtures if c.id == VORA_CAPITAL_ID)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await CaseRepo.insert(session, target)
        await session.commit()
    return target


async def test_supervisor_four_agent_fan_out(engine: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    case = await _seed_vora(engine)
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
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        risk_row = await IntakeRepo.get_one(session, case.id, "risk_scoring")
        assert risk_row is not None
        assert risk_row["band"] == "medium"
        assert 35 <= risk_row["total"] <= 45
        # evidence_id back-fill present
        ev_ids = risk_row["score_provenance"]["provenance"]["evidence_ids"]
        assert len(ev_ids) == 1
        assert ev_ids[0].startswith("led_")
        # cases.risk_band denormalized: medium → medium_high (3-tier → 4-tier mapping)
        case_after = await CaseRepo.get(session, case.id)
        assert case_after is not None
        assert case_after.risk_band == "medium_high"


async def test_supervisor_runs_risk_even_when_entity_skipped(engine: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    """Ananya has no CIN → entity_verification + ubo_graph skipped; risk still runs."""
    fixtures = get_demo_case_fixtures(datetime.now(UTC))
    ananya = next(c for c in fixtures if c.id == ANANYA_IYER_ID)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await CaseRepo.insert(session, ananya)
        await session.commit()
    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    outcome = await supervisor.run_intake(ananya.id)
    assert outcome.status == "completed"
    # Ananya has document_refs (ID + address proof) so doc_intel runs; entity_verification +
    # ubo_graph skipped (no CIN); risk_scoring runs.
    assert "risk_scoring" in outcome.agents_run
    assert "entity_verification" not in outcome.agents_run
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        risk_row = await IntakeRepo.get_one(session, ananya.id, "risk_scoring")
        assert risk_row is not None
        # Ananya has screening_hit_hint per fixture → contributes 60 * 0.20 = 12
        by_name = {c["name"]: c for c in risk_row["components"]}
        assert by_name["screening"]["value"] == 60.0
