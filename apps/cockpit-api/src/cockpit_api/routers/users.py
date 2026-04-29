"""Demo user-switcher router (Story 1.4 AC #11)."""

from __future__ import annotations

from typing import Annotated

from contracts.users import User
from fastapi import APIRouter, Depends

from cockpit_api.deps.current_user import get_current_user

router = APIRouter(prefix="/v1/users", tags=["users"])

CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/me", response_model=User)
def me(current_user: CurrentUser) -> User:
    """Return the user identified by ``X-Cockpit-Demo-User``."""
    return current_user
