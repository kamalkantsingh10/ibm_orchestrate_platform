"""Helper for writing `cockpit_chat.tool_invoked` ledger entries — Story 6.7.

Used by the cockpit-api routes that the Cockpit Chat agent calls as tools.
The async context manager wraps the route's body so every tool invocation
records exactly one ledger entry — `ok` on success, `error` (with the
captured exception class + message) on failure.

Lives in cockpit-api (not under apps/agents/) so the P4 lint rule
forbidding direct LedgerWriter.append from agents code doesn't apply.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from contracts.agent_action import ErrorInfo
from contracts.cases import CaseId
from contracts.ledger import ActorType, CockpitChatToolLedgerPayload, LedgerEntry
from ulid import ULID

from cockpit_api.services.ledger_service import LedgerWriter


@asynccontextmanager
async def ledger_chat_tool_call(
    writer: LedgerWriter,
    *,
    case_id: CaseId,
    tool_name: str,
    request_args: dict[str, Any],
) -> AsyncIterator[dict[str, Any]]:
    """Yield a `record` dict the route fills with ``result_summary``.

    On exit (success or exception), writes one `cockpit_chat.tool_invoked`
    ledger entry. On exception, the ``error`` payload field captures the
    exception class + message and the original exception is re-raised so
    the caller's HTTPException semantics still apply.
    """
    started = datetime.now(UTC)
    record: dict[str, Any] = {"result_summary": ""}
    error: ErrorInfo | None = None
    status: str = "ok"
    try:
        yield record
    except Exception as exc:
        status = "error"
        error = ErrorInfo(type=type(exc).__name__, message=str(exc)[:500])
        raise
    finally:
        ended = datetime.now(UTC)
        duration_ms = max(0, int((ended - started).total_seconds() * 1000))
        payload = CockpitChatToolLedgerPayload(
            tool_name=tool_name,  # type: ignore[arg-type]
            request_args=request_args,
            result_summary=record["result_summary"] or f"{tool_name} called",
            duration_ms=duration_ms,
            status=status,  # type: ignore[arg-type]
            error=error,
        )
        entry = LedgerEntry(
            id=f"led_{ULID()!s}",
            case_id=case_id,
            actor_type=ActorType.AGENT,
            actor_id="cockpit_chat",
            action="cockpit_chat.tool_invoked",
            payload=payload,
            recorded_at=started,
        )
        await writer.append(entry)
