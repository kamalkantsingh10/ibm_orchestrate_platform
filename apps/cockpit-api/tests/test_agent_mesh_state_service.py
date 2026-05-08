"""Unit tests for ``services.agent_mesh_state.aggregate`` — Story 4.5 AC #9."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from contracts.agent_action import AgentActionLedgerEntry
from contracts.agent_mesh import AgentMeshAgentState, AgentSlug
from contracts.cases import VORA_CAPITAL_ID
from contracts.ledger import ActorType, LedgerEntry
from ulid import ULID

from cockpit_api.services.agent_mesh_state import aggregate

_NOW = datetime(2026, 5, 7, 12, 0, 0, tzinfo=UTC)


def _entry(
    *,
    actor_id: str,
    status: str,
    minutes_ago: int = 0,
) -> LedgerEntry:
    started = _NOW - timedelta(minutes=minutes_ago + 1)
    completed = _NOW - timedelta(minutes=minutes_ago)
    payload = AgentActionLedgerEntry(
        agent_id=actor_id,
        input={},
        output={"ok": True} if status == "ok" else None,
        started_at=started,
        completed_at=completed,
        duration_ms=60_000,
        status=status,  # type: ignore[arg-type]
    )
    return LedgerEntry(
        id=f"led_{ULID()!s}",
        actor_type=ActorType.AGENT,
        actor_id=actor_id,
        case_id=VORA_CAPITAL_ID,
        action="agent.completed",
        payload=payload,
        recorded_at=completed,
    )


def test_empty_ledger_returns_eight_idle_agents() -> None:
    snap = aggregate([], case_id=VORA_CAPITAL_ID)
    assert snap.case_id == VORA_CAPITAL_ID
    assert len(snap.agents) == 8
    for row in snap.agents:
        assert row.state == AgentMeshAgentState.IDLE
        assert row.last_activity_at is None
        assert row.last_action_id is None


def test_canonical_render_order_preserved() -> None:
    snap = aggregate([], case_id=VORA_CAPITAL_ID)
    slugs = [row.agent_slug for row in snap.agents]
    assert slugs == [
        AgentSlug.CASE_SUPERVISOR,
        AgentSlug.DOCUMENT_INTELLIGENCE,
        AgentSlug.ENTITY_VERIFICATION,
        AgentSlug.UBO_GRAPH,
        AgentSlug.SCREENING,
        AgentSlug.RISK_SCORING,
        AgentSlug.WRITING,
        AgentSlug.COCKPIT_CHAT,
    ]


def test_status_ok_maps_to_complete() -> None:
    e = _entry(actor_id="document_intelligence", status="ok")
    snap = aggregate([e], case_id=VORA_CAPITAL_ID)
    by_slug = {row.agent_slug: row for row in snap.agents}
    assert by_slug[AgentSlug.DOCUMENT_INTELLIGENCE].state == AgentMeshAgentState.COMPLETE
    assert by_slug[AgentSlug.DOCUMENT_INTELLIGENCE].last_action_id == e.id
    # Other agents remain idle.
    assert by_slug[AgentSlug.SCREENING].state == AgentMeshAgentState.IDLE


def test_status_error_maps_to_blocked() -> None:
    e = _entry(actor_id="screening", status="error")
    snap = aggregate([e], case_id=VORA_CAPITAL_ID)
    by_slug = {row.agent_slug: row for row in snap.agents}
    assert by_slug[AgentSlug.SCREENING].state == AgentMeshAgentState.BLOCKED


def test_underscored_actor_id_normalises_to_dashed_slug() -> None:
    """The action decorator may pass ``document_intelligence``; the slug is
    ``document-intelligence``. The aggregator normalises on the read path."""
    e = _entry(actor_id="document_intelligence", status="ok")
    snap = aggregate([e], case_id=VORA_CAPITAL_ID)
    by_slug = {row.agent_slug: row for row in snap.agents}
    assert by_slug[AgentSlug.DOCUMENT_INTELLIGENCE].state == AgentMeshAgentState.COMPLETE


def test_latest_entry_per_slug_wins() -> None:
    earlier_failed = _entry(actor_id="ubo_graph", status="error", minutes_ago=10)
    later_ok = _entry(actor_id="ubo_graph", status="ok", minutes_ago=2)
    snap = aggregate([earlier_failed, later_ok], case_id=VORA_CAPITAL_ID)
    by_slug = {row.agent_slug: row for row in snap.agents}
    assert by_slug[AgentSlug.UBO_GRAPH].state == AgentMeshAgentState.COMPLETE
    assert by_slug[AgentSlug.UBO_GRAPH].last_action_id == later_ok.id


def test_officer_entries_are_ignored() -> None:
    officer_entry = LedgerEntry(
        id=f"led_{ULID()!s}",
        actor_type=ActorType.OFFICER,
        actor_id="officer-x",
        case_id=VORA_CAPITAL_ID,
        action="case.committed",
        payload={"note": "approve"},
        recorded_at=_NOW,
    )
    snap = aggregate([officer_entry], case_id=VORA_CAPITAL_ID)
    for row in snap.agents:
        assert row.state == AgentMeshAgentState.IDLE


def test_entity_verification_actor_id_normalises_to_dashed_slug() -> None:
    """Story 5.1 / AC14: actor_id `entity_verification` → AgentSlug.ENTITY_VERIFICATION (kebab)."""
    e = _entry(actor_id="entity_verification", status="ok")
    snap = aggregate([e], case_id=VORA_CAPITAL_ID)
    by_slug = {row.agent_slug: row for row in snap.agents}
    assert by_slug[AgentSlug.ENTITY_VERIFICATION].state == AgentMeshAgentState.COMPLETE
    assert by_slug[AgentSlug.ENTITY_VERIFICATION].last_action_id == e.id


def test_ubo_graph_actor_id_normalises_to_dashed_slug() -> None:
    """Story 5.3 / AC13: actor_id `ubo_graph` → AgentSlug.UBO_GRAPH (kebab)."""
    e = _entry(actor_id="ubo_graph", status="ok")
    snap = aggregate([e], case_id=VORA_CAPITAL_ID)
    by_slug = {row.agent_slug: row for row in snap.agents}
    assert by_slug[AgentSlug.UBO_GRAPH].state == AgentMeshAgentState.COMPLETE
    assert by_slug[AgentSlug.UBO_GRAPH].last_action_id == e.id


def test_risk_scoring_actor_id_normalises_to_dashed_slug() -> None:
    """Story 5.6 / AC14: actor_id `risk_scoring` → AgentSlug.RISK_SCORING (kebab)."""
    e = _entry(actor_id="risk_scoring", status="ok")
    snap = aggregate([e], case_id=VORA_CAPITAL_ID)
    by_slug = {row.agent_slug: row for row in snap.agents}
    assert by_slug[AgentSlug.RISK_SCORING].state == AgentMeshAgentState.COMPLETE


def test_dict_payload_status_is_honored() -> None:
    """Some seeded entries carry ``payload`` as a plain dict (Story 3.3 union)."""
    e = LedgerEntry(
        id=f"led_{ULID()!s}",
        actor_type=ActorType.AGENT,
        actor_id="case-supervisor",
        case_id=VORA_CAPITAL_ID,
        action="agent.invoked",
        payload={"kind": "system_event", "status": "ok"},
        recorded_at=_NOW,
    )
    snap = aggregate([e], case_id=VORA_CAPITAL_ID)
    by_slug = {row.agent_slug: row for row in snap.agents}
    assert by_slug[AgentSlug.CASE_SUPERVISOR].state == AgentMeshAgentState.COMPLETE
