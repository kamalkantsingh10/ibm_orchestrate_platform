"""Tests for the Case contract — Story 2.1 / AC #8."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from ulid import ULID

from contracts.cases import (
    ALLOWED_TRANSITIONS,
    Case,
    CaseState,
    CaseStateTransitionError,
    CustomerMetadata,
    assert_transition,
    is_valid_case_id,
)


def _case_id() -> str:
    return f"case_{ULID()!s}"


def _make_case(**overrides: object) -> Case:
    now = datetime.now(UTC)
    defaults: dict[str, object] = {
        "id": _case_id(),
        "state": CaseState.INTAKE_SCHEDULED,
        "customer_metadata": CustomerMetadata(customer_name="Acme Pte Ltd"),
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return Case(**defaults)  # type: ignore[arg-type]


# ───────────── Case round-trip ─────────────


def test_case_round_trips_through_json() -> None:
    case = _make_case(
        customer_metadata=CustomerMetadata(
            customer_name="Acme Pte Ltd",
            customer_type="company",
            country="SG",
            extra={"demo_tag": "fixture-1"},
        ),
        assigned_to_user_id="dc2aaaa3-555b-4636-89d0-6047dc205220",
        risk_band="medium_low",
    )
    payload = case.model_dump_json()
    revived = Case.model_validate_json(payload)
    assert revived == case


def test_case_state_round_trips_as_string() -> None:
    case = _make_case(state=CaseState.DECISION_READY)
    assert '"state":"decision_ready"' in case.model_dump_json()


def test_case_is_frozen() -> None:
    case = _make_case()
    with pytest.raises(ValidationError):
        case.state = CaseState.CLOSED


# ───────────── CaseId validation ─────────────


def test_case_id_accepts_valid_ulid() -> None:
    cid = _case_id()
    case = _make_case(id=cid)
    assert case.id == cid


def test_case_id_rejects_missing_prefix() -> None:
    with pytest.raises(ValidationError):
        _make_case(id=str(ULID()))


def test_case_id_rejects_wrong_prefix() -> None:
    with pytest.raises(ValidationError):
        _make_case(id=f"user_{ULID()!s}")


def test_case_id_rejects_short_body() -> None:
    with pytest.raises(ValidationError):
        _make_case(id="case_TOOSHORT")


def test_case_id_rejects_excluded_crockford_letters() -> None:
    # Valid ULID would never contain I, L, O, U.
    with pytest.raises(ValidationError):
        _make_case(id="case_IIIIIIIIIIIIIIIIIIIIIIIIII")


def test_is_valid_case_id_helper() -> None:
    assert is_valid_case_id(_case_id())
    assert not is_valid_case_id("not-a-case-id")
    assert not is_valid_case_id(f"case_{ULID()!s}x")


# ───────────── CustomerMetadata validation ─────────────


def test_customer_metadata_rejects_empty_name() -> None:
    with pytest.raises(ValidationError):
        CustomerMetadata(customer_name="")


def test_customer_metadata_extra_defaults_empty() -> None:
    md = CustomerMetadata(customer_name="X")
    assert md.extra == {}


def test_customer_metadata_rejects_unknown_customer_type() -> None:
    with pytest.raises(ValidationError):
        CustomerMetadata(customer_name="X", customer_type="other")  # type: ignore[arg-type]


# ───────────── State machine ─────────────


_ALL_PAIRS: list[tuple[CaseState, CaseState]] = [(src, tgt) for src in CaseState for tgt in CaseState]
_ALLOWED_PAIRS: list[tuple[CaseState, CaseState]] = [
    (src, tgt) for src, targets in ALLOWED_TRANSITIONS.items() for tgt in targets
]
_DISALLOWED_PAIRS: list[tuple[CaseState, CaseState]] = [pair for pair in _ALL_PAIRS if pair not in _ALLOWED_PAIRS]


@pytest.mark.parametrize(("src", "tgt"), _ALLOWED_PAIRS)
def test_assert_transition_accepts_every_allowed_edge(src: CaseState, tgt: CaseState) -> None:
    assert_transition(src, tgt)  # must not raise


@pytest.mark.parametrize(("src", "tgt"), _DISALLOWED_PAIRS)
def test_assert_transition_rejects_every_disallowed_edge(src: CaseState, tgt: CaseState) -> None:
    with pytest.raises(CaseStateTransitionError) as excinfo:
        assert_transition(src, tgt)
    msg = str(excinfo.value)
    assert src.value in msg
    assert tgt.value in msg


def test_canonical_rejection_closed_to_intake_scheduled() -> None:
    with pytest.raises(CaseStateTransitionError):
        assert_transition(CaseState.CLOSED, CaseState.INTAKE_SCHEDULED)


def test_closed_is_terminal() -> None:
    assert ALLOWED_TRANSITIONS[CaseState.CLOSED] == set()


def test_every_state_appears_in_allowed_transitions_keys() -> None:
    # Sanity: no orphaned states. Every CaseState has an entry as a source
    # (even if its outbound set is empty, like CLOSED).
    assert set(ALLOWED_TRANSITIONS.keys()) == set(CaseState)


def test_every_state_except_intake_scheduled_is_a_target() -> None:
    # INTAKE_SCHEDULED is the entry state; no transition leads to it.
    targets = {tgt for targets in ALLOWED_TRANSITIONS.values() for tgt in targets}
    assert targets == set(CaseState) - {CaseState.INTAKE_SCHEDULED}


# ───────────── Story 2.4 — demo fixtures ─────────────


from datetime import timedelta  # noqa: E402

from contracts.cases import (  # noqa: E402
    ANANYA_IYER_ID,
    SHREE_VENKAT_ID,
    VORA_CAPITAL_ID,
    get_demo_case_fixtures,
)
from contracts.users import ANALYST_ID  # noqa: E402

_FROZEN_NOW = datetime(2026, 4, 29, 9, 0, 0, tzinfo=UTC)


def test_demo_case_fixtures_are_three() -> None:
    assert len(get_demo_case_fixtures(_FROZEN_NOW)) == 3


def test_demo_case_fixtures_have_pinned_ids() -> None:
    ids = {c.id for c in get_demo_case_fixtures(_FROZEN_NOW)}
    assert ids == {SHREE_VENKAT_ID, VORA_CAPITAL_ID, ANANYA_IYER_ID}


def test_demo_case_fixtures_use_pinned_analyst_owner() -> None:
    for c in get_demo_case_fixtures(_FROZEN_NOW):
        assert c.assigned_to_user_id == ANALYST_ID


def test_demo_case_fixtures_are_intake_scheduled() -> None:
    for c in get_demo_case_fixtures(_FROZEN_NOW):
        assert c.state == CaseState.INTAKE_SCHEDULED


def test_demo_case_fixtures_have_distinct_descending_created_ats() -> None:
    by_id = {c.id: c for c in get_demo_case_fixtures(_FROZEN_NOW)}
    # Ananya (newest, -2min) > Vora (-7min) > Shree (-12min) per AC1.
    assert by_id[ANANYA_IYER_ID].created_at > by_id[VORA_CAPITAL_ID].created_at
    assert by_id[VORA_CAPITAL_ID].created_at > by_id[SHREE_VENKAT_ID].created_at
    # Spaced ~5 minutes apart.
    assert (by_id[ANANYA_IYER_ID].created_at - by_id[VORA_CAPITAL_ID].created_at) == timedelta(minutes=5)
    assert (by_id[VORA_CAPITAL_ID].created_at - by_id[SHREE_VENKAT_ID].created_at) == timedelta(minutes=5)


def test_demo_case_fixtures_round_trip_json() -> None:
    for c in get_demo_case_fixtures(_FROZEN_NOW):
        revived = Case.model_validate_json(c.model_dump_json())
        assert revived == c


def test_demo_case_fixtures_carry_forward_compat_extras() -> None:
    by_id = {c.id: c for c in get_demo_case_fixtures(_FROZEN_NOW)}
    # Vora carries the multi-layered UBO chain hint for Epic 5.
    assert "ubo_chain_hint" in by_id[VORA_CAPITAL_ID].customer_metadata.extra
    # Ananya carries the synthetic screening hit for Epic 6.
    assert "screening_hit_hint" in by_id[ANANYA_IYER_ID].customer_metadata.extra
    # All three carry document refs for Epic 3's Document Intelligence.
    for c in by_id.values():
        assert "document_refs" in c.customer_metadata.extra
