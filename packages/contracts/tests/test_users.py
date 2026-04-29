"""Tests for the User contract — Story 1.4 / AC #3, #12."""

from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from contracts.users import (
    ANALYST_ID,
    DEMO_USERS,
    REGULATOR_ID,
    TEAM_LEAD_ID,
    Role,
    User,
)


def test_three_demo_users_exist() -> None:
    assert len(DEMO_USERS) == 3


def test_demo_user_roles_are_unique() -> None:
    roles = [u.role for u in DEMO_USERS]
    assert len(set(roles)) == 3
    assert set(roles) == {Role.ANALYST, Role.TEAM_LEAD, Role.REGULATOR}


def test_demo_user_ids_are_valid_uuids() -> None:
    for user in DEMO_USERS:
        # Raises ValueError if not a valid UUID.
        UUID(user.id)


def test_demo_user_ids_match_module_constants() -> None:
    by_role = {u.role: u for u in DEMO_USERS}
    assert by_role[Role.ANALYST].id == ANALYST_ID
    assert by_role[Role.TEAM_LEAD].id == TEAM_LEAD_ID
    assert by_role[Role.REGULATOR].id == REGULATOR_ID


def test_demo_user_names_match_ux_personas() -> None:
    by_role = {u.role: u for u in DEMO_USERS}
    # Kamal substitutes for Priya — see Story 1.4 § Scope note.
    assert by_role[Role.ANALYST].name == "Kamal Singh"
    assert by_role[Role.TEAM_LEAD].name == "Rohan Mehta"
    assert by_role[Role.REGULATOR].name == "Anika Iyer"


def test_demo_user_initials_present() -> None:
    for user in DEMO_USERS:
        assert len(user.initials) >= 1


def test_role_enum_string_values() -> None:
    # Wire format is snake_case per architecture.md#Naming Patterns.
    assert Role.ANALYST.value == "analyst"
    assert Role.TEAM_LEAD.value == "team_lead"
    assert Role.REGULATOR.value == "regulator"


def test_user_round_trips_through_json() -> None:
    user = DEMO_USERS[0]
    payload = user.model_dump_json()
    revived = User.model_validate_json(payload)
    assert revived == user


def test_user_rejects_unknown_role() -> None:
    with pytest.raises(ValidationError):
        User(id=ANALYST_ID, name="x", role="superadmin", initials="X")  # type: ignore[arg-type]


def test_user_rejects_empty_id() -> None:
    with pytest.raises(ValidationError):
        User(id="", name="x", role=Role.ANALYST, initials="X")
