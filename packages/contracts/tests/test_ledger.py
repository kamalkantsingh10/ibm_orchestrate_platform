"""Tests for the LedgerEntry contract — Story 3.1 / AC #9; Story 3.3 / AC #10."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from ulid import ULID

from contracts.agent_action import AgentActionLedgerEntry, ErrorInfo
from contracts.cases import SHREE_VENKAT_ID
from contracts.ledger import (
    ActorType,
    LedgerEntry,
    is_valid_ledger_entry_id,
)


def _ledger_id() -> str:
    return f"led_{ULID()!s}"


def _now() -> datetime:
    return datetime.now(UTC)


def _make_entry(**overrides: object) -> LedgerEntry:
    defaults: dict[str, object] = {
        "id": _ledger_id(),
        "actor_type": ActorType.AGENT,
        "actor_id": "document_intelligence",
        "case_id": SHREE_VENKAT_ID,
        "action": "agent.invoked",
        "payload": {"foo": "bar"},
        "recorded_at": _now(),
    }
    defaults.update(overrides)
    return LedgerEntry(**defaults)  # type: ignore[arg-type]


# ───────────── round-trip ─────────────


def test_ledger_entry_round_trips_through_json() -> None:
    entry = _make_entry(payload={"agent_id": "doc_intel", "duration_ms": 42})
    payload = entry.model_dump_json()
    revived = LedgerEntry.model_validate_json(payload)
    assert revived == entry


def test_actor_type_round_trips_as_string() -> None:
    entry = _make_entry(actor_type=ActorType.SYSTEM, actor_id="seed_dev")
    assert '"actor_type":"system"' in entry.model_dump_json()


# ───────────── LedgerEntryId validation ─────────────


@pytest.mark.parametrize(
    "bad_id",
    [
        "ent_01HNZ8YV6Z4Z3Y4Q9YV3Z3Y4Q9",  # wrong prefix
        "led_01HNZ8YV6Z4Z3Y4Q9YV3Z3Y4Q",  # 25 chars body (too short)
        "led_01HNZ8YV6Z4Z3Y4Q9YV3Z3Y4Q99",  # 27 chars body (too long)
        "led_01HnZ8YV6Z4Z3Y4Q9YV3Z3Y4Q9",  # lowercase letter
        "led_01HIZ8YV6Z4Z3Y4Q9YV3Z3Y4Q9",  # contains 'I' (Crockford excludes)
        "led_01HOZ8YV6Z4Z3Y4Q9YV3Z3Y4Q9",  # contains 'O'
        "led_01HUZ8YV6Z4Z3Y4Q9YV3Z3Y4Q9",  # contains 'U'
        "led_01HLZ8YV6Z4Z3Y4Q9YV3Z3Y4Q9",  # contains 'L'
    ],
)
def test_ledger_entry_id_rejects_invalid_format(bad_id: str) -> None:
    with pytest.raises(ValidationError):
        _make_entry(id=bad_id)


def test_ledger_entry_id_accepts_valid_ulid() -> None:
    valid = f"led_{ULID()!s}"
    entry = _make_entry(id=valid)
    assert entry.id == valid


def test_is_valid_ledger_entry_id_helper() -> None:
    assert is_valid_ledger_entry_id(f"led_{ULID()!s}") is True
    assert is_valid_ledger_entry_id("not-a-led-id") is False
    assert is_valid_ledger_entry_id("led_short") is False
    assert is_valid_ledger_entry_id("case_01KQC7EWM0GYHP15CZ8JB5ZT69") is False


# ───────────── ActorType validation ─────────────


def test_actor_type_accepts_valid_values() -> None:
    for v in ("agent", "officer", "system"):
        e = _make_entry(actor_type=v)
        assert e.actor_type.value == v


def test_actor_type_rejects_invalid_values() -> None:
    with pytest.raises(ValidationError):
        _make_entry(actor_type="admin")


# ───────────── case_id validation ─────────────


def test_case_id_allows_none() -> None:
    entry = _make_entry(case_id=None, actor_type=ActorType.SYSTEM, actor_id="seed_dev", action="ledger.initialized")
    assert entry.case_id is None


def test_case_id_rejects_invalid_format() -> None:
    with pytest.raises(ValidationError):
        _make_entry(case_id="not-a-case-id")


# ───────────── recorded_at tz-awareness ─────────────


def test_recorded_at_rejects_naive_datetime() -> None:
    naive = datetime(2026, 4, 30, 12, 0, 0)  # no tzinfo
    with pytest.raises(ValidationError):
        _make_entry(recorded_at=naive)


def test_recorded_at_accepts_iso_string_with_z_suffix() -> None:
    entry = _make_entry(recorded_at="2026-04-30T12:00:00Z")
    assert entry.recorded_at.tzinfo is not None


# ───────────── discriminated union payload (Story 3.3) ─────────────


def _agent_action_payload() -> AgentActionLedgerEntry:
    started = datetime.now(UTC)
    return AgentActionLedgerEntry(
        agent_id="document_intelligence",
        model_id="stub",
        input={"case_id": SHREE_VENKAT_ID},
        output={"extracted_fields": []},
        started_at=started,
        completed_at=started + timedelta(milliseconds=10),
        duration_ms=10,
        status="ok",
    )


def test_typed_payload_round_trips_as_agent_action_ledger_entry() -> None:
    typed = _agent_action_payload()
    entry = _make_entry(payload=typed, action="agent.completed")
    revived = LedgerEntry.model_validate_json(entry.model_dump_json())
    assert isinstance(revived.payload, AgentActionLedgerEntry)
    assert revived.payload.agent_id == "document_intelligence"
    assert revived.payload.kind == "agent_action"


def test_dict_payload_round_trips_as_dict() -> None:
    entry = _make_entry(
        actor_type=ActorType.SYSTEM,
        actor_id="seed_dev",
        case_id=None,
        action="ledger.initialized",
        payload={"cases_seeded": 3},
    )
    revived = LedgerEntry.model_validate_json(entry.model_dump_json())
    assert isinstance(revived.payload, dict)
    assert revived.payload == {"cases_seeded": 3}


def test_typed_failure_payload_round_trips() -> None:
    started = datetime.now(UTC)
    failure = AgentActionLedgerEntry(
        agent_id="document_intelligence",
        model_id="stub",
        input={"case_id": SHREE_VENKAT_ID},
        output=None,
        started_at=started,
        completed_at=started + timedelta(milliseconds=5),
        duration_ms=5,
        status="error",
        error=ErrorInfo(type="ValueError", message="bad input"),
    )
    entry = _make_entry(payload=failure, action="agent.failed")
    revived = LedgerEntry.model_validate_json(entry.model_dump_json())
    assert isinstance(revived.payload, AgentActionLedgerEntry)
    assert revived.payload.status == "error"
    assert revived.payload.error is not None
    assert revived.payload.error.type == "ValueError"


# ───────────── Story 6.7 — CockpitChatToolLedgerPayload ─────────────


from contracts.ledger import CockpitChatToolLedgerPayload  # noqa: E402


def _chat_payload(**overrides: object) -> CockpitChatToolLedgerPayload:
    base: dict[str, object] = {
        "tool_name": "query_ledger",
        "request_args": {"case_id": "case_x", "limit": 50},
        "result_summary": "12 ledger entries returned",
        "duration_ms": 7,
        "status": "ok",
    }
    base.update(overrides)
    return CockpitChatToolLedgerPayload.model_validate(base)


def test_cockpit_chat_payload_round_trips() -> None:
    p = _chat_payload()
    revived = CockpitChatToolLedgerPayload.model_validate_json(p.model_dump_json())
    assert revived == p
    assert revived.kind == "cockpit_chat_tool"


def test_cockpit_chat_payload_rejects_empty_result_summary() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _chat_payload(result_summary="")


def test_cockpit_chat_payload_rejects_unknown_tool_name() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _chat_payload(tool_name="not_a_tool")


def test_cockpit_chat_payload_resolves_under_ledger_entry_union() -> None:
    """The discriminated union must resolve to the typed arm, not dict."""
    from datetime import UTC, datetime

    from ulid import ULID

    from contracts.ledger import ActorType, LedgerEntry

    entry = LedgerEntry(
        id=f"led_{ULID()!s}",
        case_id=None,
        actor_type=ActorType.AGENT,
        actor_id="cockpit_chat",
        action="cockpit_chat.tool_invoked",
        payload=_chat_payload(),
        recorded_at=datetime.now(UTC),
    )
    revived = LedgerEntry.model_validate_json(entry.model_dump_json())
    assert isinstance(revived.payload, CockpitChatToolLedgerPayload)
    assert revived.payload.tool_name == "query_ledger"


# ───────────── Story 7.5 — OfficerDecisionUndonePayload ─────────────


def test_officer_decision_undone_payload_round_trips() -> None:
    from contracts.ledger import OfficerDecisionUndonePayload

    payload = OfficerDecisionUndonePayload(
        decision_id="dec_test_123",
        reason="Officer realized the OFAC hit needed deeper review before sealing.",
    )
    parsed = OfficerDecisionUndonePayload.model_validate_json(payload.model_dump_json())
    assert parsed == payload
    assert parsed.kind == "officer_decision_undone"


def test_officer_decision_undone_payload_rejects_short_reason() -> None:
    from contracts.ledger import OfficerDecisionUndonePayload

    with pytest.raises(ValidationError):
        OfficerDecisionUndonePayload(decision_id="dec_x", reason="too short")


def test_officer_decision_committed_payload_round_trips() -> None:
    from contracts.ledger import OfficerDecisionCommittedPayload

    payload = OfficerDecisionCommittedPayload(
        decision_id="dec_test_1",
        outcome="approve",
        conditions=[],
        rationale_hash="a" * 64,
    )
    parsed = OfficerDecisionCommittedPayload.model_validate_json(payload.model_dump_json())
    assert parsed == payload
    assert parsed.kind == "officer_decision_committed"


def test_officer_decision_committed_rejects_short_hash() -> None:
    from contracts.ledger import OfficerDecisionCommittedPayload

    with pytest.raises(ValidationError):
        OfficerDecisionCommittedPayload(
            decision_id="dec_x",
            outcome="approve",
            conditions=[],
            rationale_hash="abc",
        )


def test_decision_sealed_payload_round_trips() -> None:
    from contracts.ledger import DecisionSealedPayload

    payload = DecisionSealedPayload(decision_id="dec_test_1", outcome="approve")
    parsed = DecisionSealedPayload.model_validate_json(payload.model_dump_json())
    assert parsed == payload
    assert parsed.kind == "decision_sealed"


def test_officer_decision_undone_payload_resolves_under_ledger_entry_union() -> None:
    """The discriminated union must resolve to the typed arm, not dict."""
    from datetime import UTC, datetime

    from contracts.ledger import (
        ActorType,
        LedgerEntry,
        OfficerDecisionUndonePayload,
    )

    payload = OfficerDecisionUndonePayload(
        decision_id="dec_test_123",
        reason="Officer realized the OFAC hit needed deeper review before sealing.",
    )
    entry = LedgerEntry(
        id=f"led_{ULID()!s}",
        case_id=SHREE_VENKAT_ID,
        actor_type=ActorType.OFFICER,
        actor_id="user_analyst",
        action="officer.decision_undone",
        payload=payload,
        recorded_at=datetime.now(UTC),
    )
    revived = LedgerEntry.model_validate_json(entry.model_dump_json())
    assert isinstance(revived.payload, OfficerDecisionUndonePayload)
    assert revived.payload.decision_id == "dec_test_123"
