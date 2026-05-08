"""SSE stream router — Story 4.6.

``GET /v1/cases/{case_id}/stream`` — text/event-stream per-case channel.

Auth: browsers cannot send custom headers via ``EventSource``; instead we
accept ``?as=<demo-user-id>`` as a query string. ``X-Cockpit-Demo-User``
is also honored when the caller is a non-browser (curl, integration test)
that can set headers. One of the two must validate against the fixture
user list — fail-closed on missing or unknown.

Heartbeat: a 15-second ``: keepalive`` comment preserves the connection
through proxies that idle-close.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from contracts.users import find_user_by_id
from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from cockpit_api.db.session import get_session
from cockpit_api.services import case_service
from cockpit_api.services.sse_registry import get_sse_registry

logger = logging.getLogger(__name__)

_HEADER_NAME = "X-Cockpit-Demo-User"
_HEARTBEAT_SECONDS = 15.0

router = APIRouter(prefix="/v1/cases", tags=["cases"])

_CASE_ID_PATH = Path(pattern=r"^case_[0-9A-HJKMNP-TV-Z]{26}$")


def _resolve_demo_user(
    *,
    header_value: str | None,
    query_value: str | None,
) -> str:
    """Return the validated user id, raising 400 on miss."""
    candidate = (header_value or query_value or "").strip()
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing {_HEADER_NAME} header or ?as= query parameter",
        )
    if find_user_by_id(candidate) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown user id: {candidate}",
        )
    return candidate


def _format_sse_message(event: str, data: object) -> bytes:
    """Encode one ``event``/``data`` pair into an SSE frame."""
    payload = json.dumps(data, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n".encode()


@router.get(
    "/{case_id}/stream",
    summary="Per-case Server-Sent Events stream",
    description=(
        "Story 4.6 — yields agent.state_changed / case.state_changed / "
        "case.documents_changed events for the given case. Single-worker "
        "in-process fan-out (no Redis pub/sub in demo). Auth via ``?as=`` "
        "query param (EventSource cannot send custom headers) or the "
        "``X-Cockpit-Demo-User`` header."
    ),
)
async def stream_case_events(
    case_id: Annotated[str, _CASE_ID_PATH],
    session: Annotated[AsyncSession, Depends(get_session)],
    x_cockpit_demo_user: Annotated[str | None, Header(alias=_HEADER_NAME)] = None,
    as_query: Annotated[str | None, Query(alias="as")] = None,
) -> StreamingResponse:
    # Validate auth + case existence before opening the stream.
    _resolve_demo_user(header_value=x_cockpit_demo_user, query_value=as_query)
    await case_service.get_case(session, case_id)

    registry = get_sse_registry()

    async def _stream() -> AsyncIterator[bytes]:
        # Initial frame so the client's open handler fires immediately.
        yield b": connected\n\n"
        queue, unsubscribe = registry.subscribe(case_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), _HEARTBEAT_SECONDS)
                except TimeoutError:
                    # Heartbeat — keep the connection alive through proxies.
                    yield b": keepalive\n\n"
                    continue
                yield _format_sse_message(event.event, event.data)
        finally:
            unsubscribe()

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
