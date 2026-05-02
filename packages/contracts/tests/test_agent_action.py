"""Tests for AgentActionLedgerEntry — Story 3.3 / AC #9."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from contracts.agent_action import AgentActionLedgerEntry, ErrorInfo


def _ts() -> tuple[datetime, datetime]:
    started = datetime.now(UTC)
    completed = started + timedelta(milliseconds=50)
    return started, completed


def _make(**overrides: Any) -> AgentActionLedgerEntry:
    started, completed = _ts()
    defaults: dict[str, Any] = {
        "agent_id": "document_intelligence",
        "model_id": "stub",
        "input": {"case_id": "case_01KQC7EWM0GYHP15CZ8JB5ZT69"},
        "output": {"extracted_fields": []},
        "started_at": started,
        "completed_at": completed,
        "duration_ms": 50,
        "status": "ok",
    }
    defaults.update(overrides)
    return AgentActionLedgerEntry(**defaults)


# ───────────── round-trip ─────────────


def test_success_round_trips_through_json() -> None:
    e = _make(prompt_template_id="document_intelligence/extract_v1")
    revived = AgentActionLedgerEntry.model_validate_json(e.model_dump_json())
    assert revived == e


def test_error_round_trips_through_json() -> None:
    e = _make(
        status="error",
        output=None,
        error=ErrorInfo(type="ValueError", message="bad input"),
    )
    revived = AgentActionLedgerEntry.model_validate_json(e.model_dump_json())
    assert revived.error is not None
    assert revived.error.type == "ValueError"
    assert revived.error.message == "bad input"
    assert revived.output is None


# ───────────── prompt_hash ─────────────


def test_prompt_hash_accepts_valid_sha256() -> None:
    digest = hashlib.sha256(b"hello").hexdigest()
    e = _make(prompt_hash=digest)
    assert e.prompt_hash == digest


@pytest.mark.parametrize(
    "bad",
    [
        "abc",  # too short
        "X" * 64,  # non-hex
        hashlib.sha256(b"hi").hexdigest()[:-1],  # 63 chars
        hashlib.sha256(b"hi").hexdigest().upper(),  # uppercase
    ],
)
def test_prompt_hash_rejects_invalid(bad: str) -> None:
    with pytest.raises(ValidationError):
        _make(prompt_hash=bad)


def test_prompt_hash_allows_none() -> None:
    e = _make(prompt_hash=None)
    assert e.prompt_hash is None


# ───────────── duration_ms ─────────────


def test_duration_ms_negative_raises() -> None:
    with pytest.raises(ValidationError):
        _make(duration_ms=-1)


# ───────────── kind discriminator ─────────────


def test_kind_defaults_to_agent_action() -> None:
    e = _make()
    assert e.kind == "agent_action"
    assert '"kind":"agent_action"' in e.model_dump_json()


# ───────────── tool_calls ─────────────


def test_tool_calls_default_empty() -> None:
    e = _make()
    assert e.tool_calls == []


def test_tool_calls_accept_arbitrary_dicts() -> None:
    e = _make(tool_calls=[{"name": "lookup", "args": {"x": 1}}])
    assert len(e.tool_calls) == 1


# ───────────── tz-aware timestamps ─────────────


def test_naive_started_at_raises() -> None:
    with pytest.raises(ValidationError):
        _make(started_at=datetime(2026, 4, 30, 12, 0, 0))


# ───────────── output may be None on success ─────────────


def test_output_may_be_none_on_ok_status() -> None:
    e = _make(output=None, status="ok")
    assert e.output is None
