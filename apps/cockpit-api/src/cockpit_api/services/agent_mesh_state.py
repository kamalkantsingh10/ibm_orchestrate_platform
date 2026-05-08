"""Agent mesh state aggregator — Story 4.5 AC #2.

Reads the JSON ledger via ``LedgerReader`` and emits an ``AgentMeshSnapshot``
for the cockpit pane: one row per known agent slug, with the most-recent
state derived from the agent's latest ledger entry. Pure-function-shaped
(takes a list of entries, returns a snapshot) so it's trivially testable
without I/O.

Demo derivation rules:
    * `complete`  ← latest entry's ``payload.status == "ok"``
    * `blocked`   ← latest entry's ``payload.status == "error"``
    * `idle`      ← no entries exist for the slug yet

`working` and `needs_input` are reserved for SSE-driven client updates
(Story 4.6); the ledger doesn't store in-flight markers.
"""

from __future__ import annotations

from contracts.agent_mesh import (
    AGENT_RENDER_ORDER,
    AgentMeshAgentEntry,
    AgentMeshAgentState,
    AgentMeshSnapshot,
    AgentSlug,
)
from contracts.cases import CaseId
from contracts.ledger import ActorType, LedgerEntry

from cockpit_api.services import ledger_service

# Map an arbitrary actor_id (e.g. "document_intelligence") onto a canonical
# slug (e.g. "document-intelligence"). Underscores → dashes; lowercase. The
# action decorator may pass either form depending on call site, so we
# normalise here on the read path.
_DASHIFY = str.maketrans({"_": "-"})


def _normalise(actor_id: str) -> str:
    return actor_id.lower().translate(_DASHIFY)


def derive_state(entry: LedgerEntry | None) -> AgentMeshAgentState:
    """Map the latest ledger entry to the public coarse-grained state."""
    if entry is None:
        return AgentMeshAgentState.IDLE
    payload = entry.payload
    status = getattr(payload, "status", None)
    if status is None and isinstance(payload, dict):
        status = payload.get("status")
    if status == "ok":
        return AgentMeshAgentState.COMPLETE
    if status == "error":
        return AgentMeshAgentState.BLOCKED
    return AgentMeshAgentState.IDLE


def aggregate(
    entries: list[LedgerEntry],
    *,
    case_id: CaseId,
) -> AgentMeshSnapshot:
    """Build the snapshot for ``case_id`` from raw ledger entries."""
    latest_by_slug: dict[str, LedgerEntry] = {}
    for entry in entries:
        if entry.actor_type != ActorType.AGENT:
            continue
        slug = _normalise(entry.actor_id)
        # Append-order traversal — last write wins.
        latest_by_slug[slug] = entry

    rows: list[AgentMeshAgentEntry] = []
    for slug in AGENT_RENDER_ORDER:
        latest = latest_by_slug.get(slug.value)
        rows.append(
            AgentMeshAgentEntry(
                agent_slug=AgentSlug(slug),
                state=derive_state(latest),
                last_activity_at=latest.recorded_at if latest is not None else None,
                last_action_id=latest.id if latest is not None else None,
            )
        )
    return AgentMeshSnapshot(case_id=case_id, agents=rows)


async def get_agent_mesh_state(case_id: str) -> AgentMeshSnapshot:
    """Read the ledger and return the snapshot for ``case_id``.

    Raises ``ValueError`` if ``case_id`` does not match the ``case_<ULID>``
    shape — callers should let that propagate to the FastAPI 422 handler.
    """
    reader = ledger_service.get_ledger_reader()
    entries = await reader.read_for_case(case_id)
    return aggregate(entries, case_id=case_id)
