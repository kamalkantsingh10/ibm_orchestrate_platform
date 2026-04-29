"""Demo user contracts — Story 1.4.

Three hardcoded users back the cockpit's user-switcher in the demo build
(re-scoped 2026-04-29). The records here are the single source of truth:
both ``cockpit-api`` (for ``GET /v1/users/me``) and ``cockpit-ui`` (via the
generated TS shadow in Story 2.11) consume them.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

# Stable UUIDs pinned at story authoring time. Mirror these in ``.env.example``.
ANALYST_ID = "dc2aaaa3-555b-4636-89d0-6047dc205220"
TEAM_LEAD_ID = "a725a9bb-5b8e-4984-8d23-19c682225002"
REGULATOR_ID = "a1582a20-62e1-497b-910c-45c0b0ee7030"


class Role(StrEnum):
    """Three demo roles. Wire format is snake_case per architecture.md#Naming Patterns."""

    ANALYST = "analyst"
    TEAM_LEAD = "team_lead"
    REGULATOR = "regulator"


class User(BaseModel):
    """A demo user. Identity-only — no auth, no permissions, no tenant."""

    model_config = {"frozen": True}

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    role: Role
    initials: str = Field(min_length=1, max_length=4)


# Names mirror the UX user journeys; Kamal substitutes for Priya since
# Kamal is the demo presenter (see Story 1.4 § Scope note).
DEMO_USERS: list[User] = [
    User(id=ANALYST_ID, name="Kamal Singh", role=Role.ANALYST, initials="KS"),
    User(id=TEAM_LEAD_ID, name="Rohan Mehta", role=Role.TEAM_LEAD, initials="RM"),
    User(id=REGULATOR_ID, name="Anika Iyer", role=Role.REGULATOR, initials="AI"),
]


def find_user_by_id(user_id: str) -> User | None:
    """Return the demo user with ``user_id`` or ``None`` if no match."""
    return next((u for u in DEMO_USERS if u.id == user_id), None)
