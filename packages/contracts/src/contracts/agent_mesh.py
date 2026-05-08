"""Agent mesh state — Story 4.5.

Snapshot view over the per-agent state of the cockpit's mesh as observed
from the JSON ledger. Consumed by the cockpit-ui's Agent Copilot Pane via
``GET /v1/cases/{case_id}/agent-mesh-state``.

Demo state derivation rules (see ``cockpit_api.services.agent_mesh_state``):
* ``complete`` — most-recent agent action for the slug has ``status == "ok"``.
* ``blocked`` — most-recent has ``status == "error"``.
* ``idle`` — no agent action recorded for this slug yet.

The bank-buyer scope adds ``working`` and ``needs_input`` derivations from
in-flight action decorators; for the demo those states surface only through
SSE events (Story 4.6) and live ephemerally on the client.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from contracts.cases import CaseId


class AgentSlug(StrEnum):
    """The eight MVP agents. Slug values mirror the registry directory names."""

    CASE_SUPERVISOR = "case-supervisor"
    DOCUMENT_INTELLIGENCE = "document-intelligence"
    ENTITY_VERIFICATION = "entity-verification"
    UBO_GRAPH = "ubo-graph"
    SCREENING = "screening"
    RISK_SCORING = "risk-scoring"
    WRITING = "writing"
    COCKPIT_CHAT = "cockpit-chat"


class AgentMeshAgentState(StrEnum):
    """Coarse-grained state surfaced to the cockpit pane."""

    IDLE = "idle"
    WORKING = "working"
    COMPLETE = "complete"
    BLOCKED = "blocked"
    NEEDS_INPUT = "needs_input"


# Canonical render order for the pane (matches AGENT_ORDER in cockpit-ui).
AGENT_RENDER_ORDER: tuple[AgentSlug, ...] = (
    AgentSlug.CASE_SUPERVISOR,
    AgentSlug.DOCUMENT_INTELLIGENCE,
    AgentSlug.ENTITY_VERIFICATION,
    AgentSlug.UBO_GRAPH,
    AgentSlug.SCREENING,
    AgentSlug.RISK_SCORING,
    AgentSlug.WRITING,
    AgentSlug.COCKPIT_CHAT,
)


class AgentMeshAgentEntry(BaseModel):
    """Per-agent snapshot row."""

    model_config = {"frozen": True, "use_enum_values": False}

    agent_slug: AgentSlug
    state: AgentMeshAgentState
    last_activity_at: datetime | None = None
    last_action_id: str | None = Field(default=None)


class AgentMeshSnapshot(BaseModel):
    """Response model for ``GET /v1/cases/{case_id}/agent-mesh-state``."""

    model_config = {"frozen": True, "use_enum_values": False}

    case_id: CaseId
    agents: list[AgentMeshAgentEntry]
