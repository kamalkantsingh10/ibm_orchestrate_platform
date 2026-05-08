"""Tests for the UBO Graph agent — Story 5.3 / AC #10."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from cockpit_api.repositories.case_repo import CaseRepo
from cockpit_api.repositories.intake_repo import IntakeRepo
from cockpit_api.services.ledger_service import LedgerReader, LedgerWriter
from contracts.agent_action import AgentActionLedgerEntry
from contracts.cases import (
    SHREE_VENKAT_ID,
    VORA_CAPITAL_ID,
    Case,
    get_demo_case_fixtures,
)
from contracts.confidence import ConfidenceBand
from contracts.mca import MCACompanyMaster, MCADirector, MCAShareholder
from contracts.ubo import UBOEntityNode, UBOGraphInput, UBOPersonNode
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from agents.intake.ubo_graph import (
    _apply_nominee_heuristics,
    _construct_graph_components,
    _slugify,
    ubo_graph,
)
from agents.supervisor.action_decorator import AgentExecutionError
from agents.supervisor.case_supervisor import CaseSupervisor
from agents.tools.mca_lookup import MCALookup, MCANotFoundError, MCATemporaryError
from agents.tools.mca_mock import MockMCALookup
from tests.test_case_supervisor import _session_factory_for

VORA_CIN = "U67120MH2024PTC444789"
SHREE_CIN = "U51900MH2018PTC312456"


# ───────────────────────────── helpers ────────────────────────────────────


class _StubMCALookup(MCALookup):
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


def _minimal_master(
    *,
    cin: str = VORA_CIN,
    directors: list[MCADirector] | None = None,
    shareholders: list[MCAShareholder] | None = None,
) -> MCACompanyMaster:
    return MCACompanyMaster(
        cin=cin,
        company_name="Test Co",
        status="active",
        registered_office="Somewhere",
        incorporation_date="2024-01-01",
        directors=directors or [],
        shareholders=shareholders or [],
    )


# ───────────────────────────── slugify ────────────────────────────────────


def test_slugify_basic() -> None:
    assert _slugify("Devansh Vora") == "devansh_vora"


def test_slugify_multispaces_and_caps() -> None:
    assert _slugify("A K Filing Services") == "a_k_filing_services"


def test_slugify_strips_punctuation_and_parens() -> None:
    assert _slugify("Anchor Trust Services (BVI)") == "anchor_trust_services_bvi"


# ───────────────────────────── happy path: Vora ───────────────────────────


async def test_vora_happy_path_node_and_edge_counts(tmp_writer: LedgerWriter) -> None:
    graph = await ubo_graph(
        UBOGraphInput(case_id=VORA_CAPITAL_ID, cin=VORA_CIN),
        mca=MockMCALookup(),
    )
    # 6 nodes: 1 root + 3 directors + 2 corporate shareholders.
    # Devansh appears as both director and shareholder → one node, two edges.
    assert len(graph.nodes) == 6
    # 6 edges: 3 director + 3 owns.
    assert len(graph.edges) == 6
    # 3 nominee_suspected: Coastal R1, Anchor R1, A K Filing R2.
    flagged = [e for e in graph.edges if e.nominee_flag == "nominee_suspected"]
    assert len(flagged) == 3
    # Root entity has the expected CIN-derived id.
    assert graph.root_entity_id == "ubo_e_u67120mh2024ptc444789"
    # Devansh appears once as a UBOPersonNode.
    devansh = [n for n in graph.nodes if isinstance(n, UBOPersonNode) and n.din == "09876543"]
    assert len(devansh) == 1


async def test_vora_nominee_rationales_pinned(tmp_writer: LedgerWriter) -> None:
    graph = await ubo_graph(
        UBOGraphInput(case_id=VORA_CAPITAL_ID, cin=VORA_CIN),
        mca=MockMCALookup(),
    )
    by_from = {e.from_id: e for e in graph.edges if e.nominee_flag == "nominee_suspected"}

    coastal_id = "ubo_e_coastal_equity_partners_pte_ltd"
    anchor_id = "ubo_e_anchor_trust_services_bvi"
    filing_id = "ubo_p_09876545"

    assert "SG" in (by_from[coastal_id].rationale or "")
    anchor_rationale = by_from[anchor_id].rationale or ""
    assert "VG" in anchor_rationale
    # R1 fires before R3 → rationale mentions foreign corporate, not "trust signal".
    assert "trust signal" not in anchor_rationale.lower()
    assert "Foreign corporate holder" in anchor_rationale
    assert by_from[filing_id].designation == "nominee_director"


async def test_vora_flagged_edges_drop_to_medium_low(tmp_writer: LedgerWriter) -> None:
    graph = await ubo_graph(
        UBOGraphInput(case_id=VORA_CAPITAL_ID, cin=VORA_CIN),
        mca=MockMCALookup(),
    )
    flagged = [e for e in graph.edges if e.nominee_flag == "nominee_suspected"]
    for edge in flagged:
        assert edge.confidence.value == 0.55
        assert edge.confidence.provenance.confidence_band == ConfidenceBand.MEDIUM_LOW


# ───────────────────────────── happy path: Shree ──────────────────────────


async def test_shree_happy_path_no_nominee_flags(tmp_writer: LedgerWriter) -> None:
    graph = await ubo_graph(
        UBOGraphInput(case_id=SHREE_VENKAT_ID, cin=SHREE_CIN),
        mca=MockMCALookup(),
    )
    # Both directors are also individual shareholders. The dedup rule
    # (Story 5.3 AC10) reuses each director's DIN-based id when the same
    # name appears as a shareholder → 1 person node per individual.
    # 3 nodes: 1 root + 2 persons (Venkat Reddy din=08123456, Lakshmi din=08123457).
    assert len(graph.nodes) == 3
    # 4 edges: 2 director + 2 owns.
    assert len(graph.edges) == 4
    # No nominee suspected — no foreign corporates, no nominee_director, no trust.
    assert all(e.nominee_flag == "clear" for e in graph.edges)


# ───────────────────────────── failure paths ──────────────────────────────


async def test_cin_not_found_raises_agent_execution_error(tmp_writer: LedgerWriter) -> None:
    stub = _StubMCALookup(raises=MCANotFoundError(VORA_CIN))
    with pytest.raises(AgentExecutionError):
        await ubo_graph(
            UBOGraphInput(case_id=VORA_CAPITAL_ID, cin=VORA_CIN),
            mca=stub,
        )


async def test_temporary_error_raises_agent_execution_error(tmp_writer: LedgerWriter) -> None:
    stub = _StubMCALookup(raises=MCATemporaryError("transient"))
    with pytest.raises(AgentExecutionError):
        await ubo_graph(
            UBOGraphInput(case_id=VORA_CAPITAL_ID, cin=VORA_CIN),
            mca=stub,
        )


# ───────────────────────────── heuristic isolation ────────────────────────


async def test_rule_1_isolated_foreign_corporate_majority(tmp_writer: LedgerWriter) -> None:
    """R1 alone — foreign SG corporate at 30%."""
    master = _minimal_master(
        shareholders=[
            MCAShareholder(name="ForeignCo Holdings", ownership_pct=30.0, country="SG", is_corporate=True),
        ],
    )
    stub = _StubMCALookup(master=master)
    graph = await ubo_graph(
        UBOGraphInput(case_id=VORA_CAPITAL_ID, cin=VORA_CIN),
        mca=stub,
    )
    flagged = [e for e in graph.edges if e.nominee_flag == "nominee_suspected"]
    assert len(flagged) == 1
    assert "Foreign corporate holder (SG)" in (flagged[0].rationale or "")


async def test_rule_2_isolated_nominee_director(tmp_writer: LedgerWriter) -> None:
    master = _minimal_master(
        directors=[
            MCADirector(din="11111111", name="Plain Director", designation="director"),
            MCADirector(din="22222222", name="The Nominee", designation="nominee_director"),
        ],
    )
    stub = _StubMCALookup(master=master)
    graph = await ubo_graph(
        UBOGraphInput(case_id=VORA_CAPITAL_ID, cin=VORA_CIN),
        mca=stub,
    )
    flagged = [e for e in graph.edges if e.nominee_flag == "nominee_suspected"]
    assert len(flagged) == 1
    assert "nominee_director" in (flagged[0].rationale or "")


async def test_rule_3_isolated_trust_name(tmp_writer: LedgerWriter) -> None:
    """R3 alone — IN-country trust services (R1 doesn't fire because country=IN)."""
    master = _minimal_master(
        shareholders=[
            MCAShareholder(name="Mumbai Trust Services", ownership_pct=10.0, country="IN", is_corporate=True),
        ],
    )
    stub = _StubMCALookup(master=master)
    graph = await ubo_graph(
        UBOGraphInput(case_id=VORA_CAPITAL_ID, cin=VORA_CIN),
        mca=stub,
    )
    flagged = [e for e in graph.edges if e.nominee_flag == "nominee_suspected"]
    assert len(flagged) == 1
    assert "trust signal" in (flagged[0].rationale or "")


async def test_rule_precedence_r1_over_r3(tmp_writer: LedgerWriter) -> None:
    """Both R1 and R3 apply — R1's rationale wins (mentions foreign country)."""
    master = _minimal_master(
        shareholders=[
            MCAShareholder(name="VG Trust Services", ownership_pct=40.0, country="VG", is_corporate=True),
        ],
    )
    stub = _StubMCALookup(master=master)
    graph = await ubo_graph(
        UBOGraphInput(case_id=VORA_CAPITAL_ID, cin=VORA_CIN),
        mca=stub,
    )
    flagged = [e for e in graph.edges if e.nominee_flag == "nominee_suspected"]
    assert len(flagged) == 1
    # R1's rationale wins.
    assert "Foreign corporate holder (VG)" in (flagged[0].rationale or "")
    assert "trust signal" not in (flagged[0].rationale or "")


# ───────────────────────────── ledger entry shape ─────────────────────────


async def test_ledger_entry_shape(tmp_writer: LedgerWriter) -> None:
    await ubo_graph(
        UBOGraphInput(case_id=VORA_CAPITAL_ID, cin=VORA_CIN),
        mca=MockMCALookup(),
    )
    entries = await LedgerReader(tmp_writer._path).read_all()
    completed = [e for e in entries if e.action == "agent.completed" and e.actor_id == "ubo_graph"]
    assert len(completed) == 1
    payload = completed[0].payload
    assert isinstance(payload, AgentActionLedgerEntry)
    assert payload.agent_id == "ubo_graph"
    assert payload.model_id == "deterministic"
    assert payload.output is not None
    assert payload.output["root_entity_id"] == "ubo_e_u67120mh2024ptc444789"


# ───────────────────────────── supervisor end-to-end ──────────────────────


async def _seed_vora(engine: AsyncEngine) -> Case:
    cases = get_demo_case_fixtures(datetime.now(UTC))
    target = next(c for c in cases if c.id == VORA_CAPITAL_ID)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await CaseRepo.insert(session, target)
        await session.commit()
    return target


async def test_supervisor_three_agent_fan_out_persists_ubo_graph(engine: AsyncEngine, tmp_writer: LedgerWriter) -> None:
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
        ubo_row = await IntakeRepo.get_one(session, case.id, "ubo_graph")
        assert ubo_row is not None
        # All edges have evidence_ids back-filled with the agent's ledger ID.
        ev_ids = {tuple(e["confidence"]["provenance"]["evidence_ids"]) for e in ubo_row["edges"]}
        # Single shared ledger entry across edges → one tuple.
        assert len(ev_ids) == 1
        only = next(iter(ev_ids))
        assert len(only) == 1
        assert only[0].startswith("led_")


async def test_supervisor_ubo_graph_failure_escalates(
    engine: AsyncEngine, tmp_writer: LedgerWriter, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If ubo_graph fails after entity_verification succeeded → case escalated."""
    case = await _seed_vora(engine)

    real_lookup = MockMCALookup()
    call_count = 0

    class _FailingMCA:
        async def lookup(self, *, cin: str) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Entity Verification's call succeeds.
                return await real_lookup.lookup(cin=cin)
            # UBO Graph's call fails.
            raise MCATemporaryError("UBO downstream blew up")

    import agents.intake.entity_verification as ev_mod
    import agents.intake.ubo_graph as ubo_mod

    failing = _FailingMCA()
    monkeypatch.setattr(ev_mod, "get_default_mca_lookup", lambda: failing)
    monkeypatch.setattr(ubo_mod, "get_default_mca_lookup", lambda: failing)

    supervisor = CaseSupervisor(session_factory=_session_factory_for(engine))
    outcome = await supervisor.run_intake(case.id)

    assert outcome.status == "blocked"
    assert outcome.failed_agent == "ubo_graph"
    # ubo_graph fails before risk_scoring runs.
    assert outcome.agents_run == ["document_intelligence", "entity_verification", "ubo_graph"]


# ───────────────────────────── _construct_graph_components ────────────────


def test_construct_components_dedupes_director_shareholder_overlap() -> None:
    master = _minimal_master(
        directors=[
            MCADirector(din="08123456", name="Devansh", designation="director"),
        ],
        shareholders=[
            MCAShareholder(name="Devansh", ownership_pct=100.0, country="IN", is_corporate=False),
        ],
    )
    nodes, edges = _construct_graph_components(master)
    # Dedup-by-name (Story 5.3 AC10): one person node + two edges.
    person_nodes = [n for n in nodes if isinstance(n, UBOPersonNode)]
    assert len(person_nodes) == 1
    assert person_nodes[0].id == "ubo_p_08123456"
    # 2 edges: 1 director + 1 owns, both pointing to the same from_id.
    assert len(edges) == 2
    assert edges[0].from_id == edges[1].from_id == "ubo_p_08123456"


def test_construct_components_root_node_uses_cin_slug() -> None:
    master = _minimal_master(cin="U99999XX9999XXX111111")
    nodes, _edges = _construct_graph_components(master)
    root_entities = [n for n in nodes if isinstance(n, UBOEntityNode)]
    assert root_entities[0].id == "ubo_e_u99999xx9999xxx111111"


# ───────────────────────────── _apply_nominee_heuristics ──────────────────


def test_apply_heuristics_no_change_on_clean_master() -> None:
    master = _minimal_master(
        directors=[MCADirector(din="11111111", name="Clean", designation="director")],
        shareholders=[MCAShareholder(name="Plain Person", ownership_pct=100.0, country="IN")],
    )
    nodes, edges = _construct_graph_components(master)
    new_edges = _apply_nominee_heuristics(edges, nodes)
    assert all(e.nominee_flag == "clear" for e in new_edges)
