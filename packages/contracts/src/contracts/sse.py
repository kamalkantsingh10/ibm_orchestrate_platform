"""SSE event contract — Story 4.6.

Server-Sent Events flow ID-only payloads to the cockpit-ui; clients
re-fetch detail via TanStack Query invalidation. Per ``architecture.md``
P6 the payload is capped at 256 bytes when serialised — these payloads
are tiny by design (case_id + agent_slug + state).

Event names follow ``<domain>.<past_tense_verb>``, dot-delimited
snake_case past-tense.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class SseEvent(BaseModel):
    """One SSE message; ``event`` is the named type, ``data`` is JSON."""

    model_config = {"frozen": True}

    event: Literal[
        "agent.state_changed",
        "case.state_changed",
        "case.documents_changed",
        "case.ubo_corrected",
        "case.risk_recalculated",
        # Story 6.8 — Cockpit Chat streaming. token = mid-stream chunk;
        # message_complete = final body + parsed citations; error = failure.
        "cockpit_chat.token",
        "cockpit_chat.message_complete",
        "cockpit_chat.error",
        # Story 7.4 — decision lifecycle.
        # decision.committed fires when Story 7.7's POST lands the
        # pending_seal entry; decision.sealed fires when the 120s timer
        # elapses; decision.undone fires on Story 7.5's officer undo.
        "decision.committed",
        "decision.sealed",
        "decision.undone",
        # Story 8.7 — fires when a commit's outcome routes the case to
        # the Team Lead approval queue (escalate_to_edd, or
        # approve_with_conditions on a high-risk case).
        "case.escalated_for_approval",
    ]
    data: dict[str, Any]
