"""Current-user dependency for the demo build (Story 1.4 AC #11).

The demo has no real auth — identity is carried in the ``X-Cockpit-Demo-User``
header set by the cockpit-ui's openapi-fetch wrapper. We look the value up
against the contract-defined ``DEMO_USERS`` list and raise 400 on miss.
No anonymous fallback (architecture.md#Anti-Patterns to Refuse — silent failures).
"""

from __future__ import annotations

from contracts.users import User, find_user_by_id
from fastapi import Header, HTTPException, status

_HEADER_NAME = "X-Cockpit-Demo-User"


def get_current_user(
    x_cockpit_demo_user: str | None = Header(default=None, alias=_HEADER_NAME),
) -> User:
    if not x_cockpit_demo_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing {_HEADER_NAME} header",
        )
    user = find_user_by_id(x_cockpit_demo_user)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown {_HEADER_NAME}: {x_cockpit_demo_user}",
        )
    return user
