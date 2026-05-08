"""Unit tests for ``case_service.queue_order`` — Story 4.1 AC #7."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from contracts.cases import Case, CaseState, CustomerMetadata
from ulid import ULID

from cockpit_api.services.case_service import queue_order

_NOW = datetime(2026, 5, 7, 9, 0, 0, tzinfo=UTC)
_ANALYST = "00000000-0000-4000-8000-000000000001"
_OTHER = "00000000-0000-4000-8000-000000000002"


def _case_id() -> str:
    return f"case_{ULID()!s}"


def _make(
    *,
    risk_band: str | None = None,
    sla_hours: float | None = None,
    assigned_to: str | None = None,
    created_at: datetime | None = None,
    name: str = "Acme",
) -> Case:
    extra: dict[str, Any] = {}
    if sla_hours is not None:
        extra["sla_due_at"] = (_NOW + timedelta(hours=sla_hours)).isoformat().replace("+00:00", "Z")
    return Case(
        id=_case_id(),
        state=CaseState.INTAKE_SCHEDULED,
        customer_metadata=CustomerMetadata(customer_name=name, extra=extra),
        assigned_to_user_id=assigned_to,
        risk_band=risk_band,  # type: ignore[arg-type]
        created_at=created_at or _NOW - timedelta(minutes=10),
        updated_at=created_at or _NOW - timedelta(minutes=10),
    )


# ───────────────────────── S1 — risk dominates ─────────────────────────


def test_higher_risk_band_orders_first() -> None:
    high = _make(risk_band="high", name="High")
    low = _make(risk_band="low", name="Low")
    ordered = queue_order([low, high], current_user_id=None, now=_NOW)
    assert [c.customer_metadata.customer_name for c in ordered] == ["High", "Low"]


# ───────────────────────── S2 — sla within same risk ────────────────────


def test_tighter_sla_orders_first_within_same_risk() -> None:
    same_risk = "medium_high"
    far = _make(risk_band=same_risk, sla_hours=48, name="Far")
    near = _make(risk_band=same_risk, sla_hours=2, name="Near")
    ordered = queue_order([far, near], current_user_id=None, now=_NOW)
    assert [c.customer_metadata.customer_name for c in ordered] == ["Near", "Far"]


# ───────────────────── S3 — continuity within same risk + sla ───────────


def test_assigned_to_current_user_wins_continuity_tie() -> None:
    assigned = _make(name="Mine", assigned_to=_ANALYST)
    not_assigned = _make(name="Theirs", assigned_to=_OTHER)
    ordered = queue_order([not_assigned, assigned], current_user_id=_ANALYST, now=_NOW)
    assert [c.customer_metadata.customer_name for c in ordered] == ["Mine", "Theirs"]


# ───────────────────── S4 — risk beats sla beats continuity ─────────────


def test_risk_beats_sla_beats_continuity() -> None:
    # high risk, far SLA, NOT mine — should still win
    a = _make(risk_band="high", sla_hours=72, name="A")
    # medium_high, near SLA, NOT mine
    b = _make(risk_band="medium_high", sla_hours=1, name="B")
    # medium_high, near SLA, mine
    c = _make(risk_band="medium_high", sla_hours=1, name="C", assigned_to=_ANALYST)
    ordered = queue_order([b, c, a], current_user_id=_ANALYST, now=_NOW)
    assert [x.customer_metadata.customer_name for x in ordered] == ["A", "C", "B"]


# ───────────────────── S5 — created_at tiebreak ─────────────────────────


def test_tiebreak_by_created_at_desc() -> None:
    older = _make(name="Older", created_at=_NOW - timedelta(hours=2))
    newer = _make(name="Newer", created_at=_NOW - timedelta(hours=1))
    ordered = queue_order([older, newer], current_user_id=None, now=_NOW)
    assert [c.customer_metadata.customer_name for c in ordered] == ["Newer", "Older"]


# ───────────────────── S6 — None risk_band sinks last ───────────────────


def test_unscored_cases_sink_below_scored() -> None:
    scored = _make(risk_band="low", name="Scored")
    unscored = _make(risk_band=None, name="Unscored")
    ordered = queue_order([unscored, scored], current_user_id=None, now=_NOW)
    assert [c.customer_metadata.customer_name for c in ordered] == ["Scored", "Unscored"]


# ───────────────────── extra — overdue SLA wins ─────────────────────────


def test_overdue_sla_orders_above_due_in_future() -> None:
    overdue = _make(name="Overdue", sla_hours=-1.0)
    upcoming = _make(name="Upcoming", sla_hours=24)
    ordered = queue_order([upcoming, overdue], current_user_id=None, now=_NOW)
    assert [c.customer_metadata.customer_name for c in ordered] == ["Overdue", "Upcoming"]


# ───────────────────── extra — bad sla string is no-op ──────────────────


def test_bad_sla_string_does_not_raise() -> None:
    bad = Case(
        id=_case_id(),
        state=CaseState.INTAKE_SCHEDULED,
        customer_metadata=CustomerMetadata(
            customer_name="Bad",
            extra={"sla_due_at": "not-a-date"},
        ),
        created_at=_NOW - timedelta(minutes=10),
        updated_at=_NOW - timedelta(minutes=10),
    )
    good = _make(name="Good", sla_hours=10)
    ordered = queue_order([bad, good], current_user_id=None, now=_NOW)
    # ``bad`` falls into +inf bucket; ``good`` is finite → good first
    assert [c.customer_metadata.customer_name for c in ordered] == ["Good", "Bad"]


# ───────────────────── extra — empty list ───────────────────────────────


def test_empty_input_returns_empty() -> None:
    assert queue_order([], current_user_id=None, now=_NOW) == []


# ───────────────────── extra — current_user_id None disables continuity ─


def test_continuity_disabled_when_user_id_none() -> None:
    assigned = _make(name="Mine", assigned_to=_ANALYST)
    not_assigned = _make(name="Theirs", assigned_to=_OTHER)
    # With current_user_id=None the continuity dimension is 0 for both;
    # tiebreak falls through to created_at DESC. Both have the same
    # created_at → relative order determined by Python's stable sort, which
    # preserves the input order.
    ordered = queue_order([not_assigned, assigned], current_user_id=None, now=_NOW)
    assert [c.customer_metadata.customer_name for c in ordered] == ["Theirs", "Mine"]
