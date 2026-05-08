"""Tests for ledger_chat_tool_call helper — Story 6.7 / AC #11."""

from __future__ import annotations

from pathlib import Path

import pytest
from contracts.cases import VORA_CAPITAL_ID
from contracts.ledger import CockpitChatToolLedgerPayload

from cockpit_api.services.cockpit_chat_ledger import ledger_chat_tool_call
from cockpit_api.services.ledger_service import LedgerReader, LedgerWriter


@pytest.fixture
def writer(tmp_path: Path) -> LedgerWriter:
    return LedgerWriter(tmp_path / "ledger.jsonl")


async def test_writes_one_entry_on_success_with_status_ok(writer: LedgerWriter) -> None:
    async with ledger_chat_tool_call(
        writer,
        case_id=VORA_CAPITAL_ID,
        tool_name="get_case",
        request_args={"case_id": VORA_CAPITAL_ID},
    ) as record:
        record["result_summary"] = "case fetched"

    entries = await LedgerReader(writer._path).read_for_case(VORA_CAPITAL_ID)
    assert len(entries) == 1
    payload = entries[0].payload
    assert isinstance(payload, CockpitChatToolLedgerPayload)
    assert payload.status == "ok"
    assert payload.tool_name == "get_case"
    assert payload.result_summary == "case fetched"


async def test_writes_one_entry_on_exception_with_status_error(
    writer: LedgerWriter,
) -> None:
    with pytest.raises(RuntimeError):
        async with ledger_chat_tool_call(
            writer,
            case_id=VORA_CAPITAL_ID,
            tool_name="re_run_agent",
            request_args={"case_id": VORA_CAPITAL_ID, "agent_slug": "screening"},
        ):
            raise RuntimeError("kaboom")

    entries = await LedgerReader(writer._path).read_for_case(VORA_CAPITAL_ID)
    assert len(entries) == 1
    payload = entries[0].payload
    assert isinstance(payload, CockpitChatToolLedgerPayload)
    assert payload.status == "error"
    assert payload.error is not None
    assert payload.error.type == "RuntimeError"
    assert "kaboom" in payload.error.message


async def test_request_args_pass_through_verbatim(writer: LedgerWriter) -> None:
    args = {"case_id": VORA_CAPITAL_ID, "actor_id": "screening", "limit": 25}
    async with ledger_chat_tool_call(
        writer,
        case_id=VORA_CAPITAL_ID,
        tool_name="query_ledger",
        request_args=args,
    ) as record:
        record["result_summary"] = "5 entries"

    entries = await LedgerReader(writer._path).read_for_case(VORA_CAPITAL_ID)
    payload = entries[0].payload
    assert isinstance(payload, CockpitChatToolLedgerPayload)
    assert payload.request_args == args


async def test_default_result_summary_when_record_unset(writer: LedgerWriter) -> None:
    async with ledger_chat_tool_call(
        writer,
        case_id=VORA_CAPITAL_ID,
        tool_name="get_reasoning_trace",
        request_args={},
    ):
        pass  # don't fill record

    entries = await LedgerReader(writer._path).read_for_case(VORA_CAPITAL_ID)
    payload = entries[0].payload
    assert isinstance(payload, CockpitChatToolLedgerPayload)
    assert payload.result_summary == "get_reasoning_trace called"


async def test_duration_ms_is_non_negative(writer: LedgerWriter) -> None:
    async with ledger_chat_tool_call(
        writer,
        case_id=VORA_CAPITAL_ID,
        tool_name="get_case",
        request_args={},
    ) as record:
        record["result_summary"] = "case fetched"

    entries = await LedgerReader(writer._path).read_for_case(VORA_CAPITAL_ID)
    payload = entries[0].payload
    assert isinstance(payload, CockpitChatToolLedgerPayload)
    assert payload.duration_ms >= 0
