"""Tests for @agent_action — Story 3.2 / AC #9; Story 3.4 § AC9."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from cockpit_api.services import ledger_service
from cockpit_api.services.ledger_service import LedgerReader, LedgerWriter
from contracts.agent_action import AgentActionLedgerEntry
from contracts.cases import SHREE_VENKAT_ID, CaseId
from contracts.ledger import ActorType, LedgerEntry
from pydantic import BaseModel

from agents.supervisor.action_decorator import (
    AgentExecutionError,
    _runtime_model_id,
    _runtime_prompt_hash,
    agent_action,
    set_runtime_model_id,
    set_runtime_prompt_hash,
)


class StubIn(BaseModel):
    case_id: CaseId
    foo: str = "bar"


class StubInNoCase(BaseModel):
    foo: str = "no-case"


class StubOut(BaseModel):
    bar: int


# ───────────── fixture: tmp ledger writer ─────────────


@pytest.fixture
def tmp_writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[LedgerWriter]:
    """Bind the global writer/reader singletons to a tmp_path-scoped file.

    Clears the ``lru_cache`` on both getters so this test gets its own
    writer; restores cleanup on teardown for hygiene.
    """
    path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path)
    reader = LedgerReader(path)

    ledger_service.get_ledger_writer.cache_clear()
    ledger_service.get_ledger_reader.cache_clear()

    monkeypatch.setattr(ledger_service, "get_ledger_writer", lambda: writer)
    monkeypatch.setattr(ledger_service, "get_ledger_reader", lambda: reader)
    # The decorator imports ``get_ledger_writer`` by name; patch the binding
    # in the decorator's module too.
    import agents.supervisor.action_decorator as deco

    monkeypatch.setattr(deco, "get_ledger_writer", lambda: writer)

    # Reset context vars so a prior test's set value doesn't leak.
    _runtime_model_id.set(None)
    _runtime_prompt_hash.set(None)

    yield writer


async def _read(writer: LedgerWriter) -> list[LedgerEntry]:
    reader = LedgerReader(writer._path)
    return await reader.read_all()


# ───────────── happy path ─────────────


async def test_happy_path_writes_completed_entry(tmp_writer: LedgerWriter) -> None:
    @agent_action(
        agent_id="document_intelligence",
        model_id="stub",
        prompt_template_id="document_intelligence/extract_v1",
    )
    async def stub(_: StubIn) -> StubOut:
        return StubOut(bar=42)

    out = await stub(StubIn(case_id=SHREE_VENKAT_ID, foo="hello"))
    assert out.bar == 42

    entries = await _read(tmp_writer)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.actor_type == ActorType.AGENT
    assert entry.actor_id == "document_intelligence"
    assert entry.case_id == SHREE_VENKAT_ID
    assert entry.action == "agent.completed"

    assert isinstance(entry.payload, AgentActionLedgerEntry)
    assert entry.payload.agent_id == "document_intelligence"
    assert entry.payload.model_id == "stub"
    assert entry.payload.prompt_template_id == "document_intelligence/extract_v1"
    assert entry.payload.status == "ok"
    assert entry.payload.duration_ms >= 0
    assert entry.payload.input == {"case_id": SHREE_VENKAT_ID, "foo": "hello"}
    assert entry.payload.output == {"bar": 42}


# ───────────── failure path ─────────────


async def test_failure_path_writes_failed_entry_and_raises_typed_error(
    tmp_writer: LedgerWriter,
) -> None:
    @agent_action(agent_id="broken")
    async def boom(_: StubIn) -> StubOut:
        raise ValueError("bad input")

    with pytest.raises(AgentExecutionError) as excinfo:
        await boom(StubIn(case_id=SHREE_VENKAT_ID))
    assert isinstance(excinfo.value.original, ValueError)
    assert excinfo.value.agent_id == "broken"
    assert excinfo.value.case_id == SHREE_VENKAT_ID

    entries = await _read(tmp_writer)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.action == "agent.failed"
    assert isinstance(entry.payload, AgentActionLedgerEntry)
    assert entry.payload.status == "error"
    assert entry.payload.error is not None
    assert entry.payload.error.type == "ValueError"
    assert entry.payload.error.message == "bad input"
    assert entry.payload.output is None


# ───────────── ordering: writer failure on success path ─────────────


async def test_writer_failure_on_success_raises_agent_execution_error(
    tmp_writer: LedgerWriter,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the agent succeeds but the writer fails, we surface the writer error."""

    async def boom_append(_: LedgerEntry) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr(tmp_writer, "append", boom_append)

    @agent_action(agent_id="a")
    async def stub(_: StubIn) -> StubOut:
        return StubOut(bar=1)

    with caplog.at_level(logging.ERROR), pytest.raises(AgentExecutionError) as excinfo:
        await stub(StubIn(case_id=SHREE_VENKAT_ID))

    assert isinstance(excinfo.value.original, RuntimeError)
    assert "ledger.append_failed_after_success" in caplog.text


# ───────────── case_id resolution ─────────────


async def test_case_id_from_input_model(tmp_writer: LedgerWriter) -> None:
    @agent_action(agent_id="a")
    async def stub(_: StubIn) -> StubOut:
        return StubOut(bar=1)

    await stub(StubIn(case_id=SHREE_VENKAT_ID))
    entries = await _read(tmp_writer)
    assert entries[0].case_id == SHREE_VENKAT_ID


async def test_case_id_from_kwargs_when_input_lacks_field(
    tmp_writer: LedgerWriter,
) -> None:
    @agent_action(agent_id="a")
    async def stub(_: StubInNoCase, *, case_id: str | None = None) -> StubOut:
        return StubOut(bar=1)

    await stub(StubInNoCase(), case_id=SHREE_VENKAT_ID)
    entries = await _read(tmp_writer)
    assert entries[0].case_id == SHREE_VENKAT_ID


async def test_case_id_resolves_to_none_for_system_agent(
    tmp_writer: LedgerWriter,
) -> None:
    @agent_action(agent_id="a")
    async def stub(_: StubInNoCase) -> StubOut:
        return StubOut(bar=1)

    await stub(StubInNoCase())
    entries = await _read(tmp_writer)
    assert entries[0].case_id is None


# ───────────── sync function rejection ─────────────


def test_sync_function_rejected_at_decoration_time() -> None:
    def sync_stub(_: StubIn) -> StubOut:
        return StubOut(bar=1)

    with pytest.raises(TypeError, match="async function"):
        agent_action(agent_id="a")(sync_stub)  # type: ignore[arg-type]


# ───────────── metadata preservation ─────────────


async def test_functools_wraps_preserves_metadata(tmp_writer: LedgerWriter) -> None:
    @agent_action(agent_id="a")
    async def stub_named(_: StubIn) -> StubOut:
        """Stub agent docstring."""
        return StubOut(bar=1)

    assert stub_named.__name__ == "stub_named"
    assert stub_named.__doc__ == "Stub agent docstring."


# ───────────── concurrent invocations ─────────────


async def test_concurrent_invocations_produce_distinct_entries(
    tmp_writer: LedgerWriter,
) -> None:
    @agent_action(agent_id="a")
    async def stub(_: StubIn) -> StubOut:
        await asyncio.sleep(0)
        return StubOut(bar=1)

    await asyncio.gather(*[stub(StubIn(case_id=SHREE_VENKAT_ID, foo=f"i{i}")) for i in range(10)])
    entries = await _read(tmp_writer)
    assert len(entries) == 10
    ids = {e.id for e in entries}
    assert len(ids) == 10  # all distinct


# ───────────── runtime overrides (Story 3.4 AC9) ─────────────


async def test_runtime_model_id_override(tmp_writer: LedgerWriter) -> None:
    @agent_action(agent_id="doc_intel", model_id="stub")
    async def stub(_: StubIn) -> StubOut:
        set_runtime_model_id("watsonx/granite-3-2-8b-instruct")
        return StubOut(bar=1)

    await stub(StubIn(case_id=SHREE_VENKAT_ID))
    entries = await _read(tmp_writer)
    assert isinstance(entries[0].payload, AgentActionLedgerEntry)
    assert entries[0].payload.model_id == "watsonx/granite-3-2-8b-instruct"


async def test_runtime_prompt_hash_override(tmp_writer: LedgerWriter) -> None:
    digest = "a" * 64

    @agent_action(agent_id="doc_intel")
    async def stub(_: StubIn) -> StubOut:
        set_runtime_prompt_hash(digest)
        return StubOut(bar=1)

    await stub(StubIn(case_id=SHREE_VENKAT_ID))
    entries = await _read(tmp_writer)
    assert isinstance(entries[0].payload, AgentActionLedgerEntry)
    assert entries[0].payload.prompt_hash == digest


async def test_runtime_overrides_do_not_leak_across_calls(
    tmp_writer: LedgerWriter,
) -> None:
    """Each call resets the context vars before invoking the agent."""

    @agent_action(agent_id="a", model_id="static")
    async def setter(_: StubIn) -> StubOut:
        set_runtime_model_id("override-1")
        return StubOut(bar=1)

    @agent_action(agent_id="b", model_id="static")
    async def no_set(_: StubIn) -> StubOut:
        return StubOut(bar=2)

    await setter(StubIn(case_id=SHREE_VENKAT_ID))
    await no_set(StubIn(case_id=SHREE_VENKAT_ID))

    entries = await _read(tmp_writer)
    assert isinstance(entries[0].payload, AgentActionLedgerEntry)
    assert isinstance(entries[1].payload, AgentActionLedgerEntry)
    assert entries[0].payload.model_id == "override-1"
    assert entries[1].payload.model_id == "static"


# ───────────── Story 6.4 — reasoning trace integration ─────────────

from contracts.reasoning_trace import ReasoningTrace  # noqa: E402


def _valid_trace() -> ReasoningTrace:
    from contracts.confidence import to_band
    from contracts.reasoning_trace import ConfidenceWithRationale

    return ReasoningTrace(
        what_searched="searched the screening provider against 3 subjects",
        what_hit="returned 1 sanctions match at score 0.73",
        confidence_self_rating=ConfidenceWithRationale(
            value=0.73,
            rationale="mean of returned hit scores; sample of 1",
            band=to_band(0.73),
        ),
        counterfactual="disposition would change with officer DOB confirmation",
    )


async def test_reasoning_trace_attached_to_ledger_entry(tmp_writer: LedgerWriter) -> None:
    from agents.supervisor.action_decorator import set_runtime_reasoning_trace

    @agent_action(agent_id="screening")
    async def stub(_: StubIn) -> StubOut:
        set_runtime_reasoning_trace(_valid_trace())
        return StubOut(bar=1)

    await stub(StubIn(case_id=SHREE_VENKAT_ID))
    entries = await _read(tmp_writer)
    payload = entries[0].payload
    assert isinstance(payload, AgentActionLedgerEntry)
    assert payload.reasoning_trace is not None
    assert "screening provider" in payload.reasoning_trace.what_searched


async def test_no_trace_attached_yields_none(tmp_writer: LedgerWriter) -> None:
    @agent_action(agent_id="document_intelligence")
    async def stub(_: StubIn) -> StubOut:
        return StubOut(bar=1)

    await stub(StubIn(case_id=SHREE_VENKAT_ID))
    entries = await _read(tmp_writer)
    payload = entries[0].payload
    assert isinstance(payload, AgentActionLedgerEntry)
    assert payload.reasoning_trace is None


async def test_invalid_trace_raises_incomplete_error() -> None:
    from contracts.confidence import to_band
    from contracts.reasoning_trace import (
        ConfidenceWithRationale,
        IncompleteReasoningTraceError,
        ReasoningTrace,
    )

    from agents.supervisor.action_decorator import set_runtime_reasoning_trace

    # Build a "valid" object first, then mutate via model_copy with an
    # invalid (too-short) field so we hit the validator.
    bad = ReasoningTrace.model_construct(
        what_searched="x",  # too short
        what_hit="okay length string here",
        confidence_self_rating=ConfidenceWithRationale(value=0.5, rationale="this is a rationale", band=to_band(0.5)),
        counterfactual="okay length string here",
    )
    with pytest.raises(IncompleteReasoningTraceError) as exc_info:
        set_runtime_reasoning_trace(bad)
    assert "what_searched" in str(exc_info.value)


async def test_failed_agent_run_has_no_reasoning_trace(tmp_writer: LedgerWriter) -> None:
    @agent_action(agent_id="entity_verification")
    async def boom(_: StubIn) -> StubOut:
        raise RuntimeError("kaboom")

    with pytest.raises(AgentExecutionError):
        await boom(StubIn(case_id=SHREE_VENKAT_ID))
    entries = await _read(tmp_writer)
    payload = entries[0].payload
    assert isinstance(payload, AgentActionLedgerEntry)
    assert payload.status == "error"
    assert payload.reasoning_trace is None


async def test_concurrent_traces_do_not_cross_pollute(tmp_writer: LedgerWriter) -> None:
    """ContextVars are task-local — two concurrent agents see only their own trace."""
    import asyncio

    from contracts.confidence import to_band
    from contracts.reasoning_trace import ConfidenceWithRationale, ReasoningTrace

    from agents.supervisor.action_decorator import set_runtime_reasoning_trace

    def _trace(label: str) -> ReasoningTrace:
        return ReasoningTrace(
            what_searched=f"search by {label} agent for testing",
            what_hit=f"hit by {label} agent for testing",
            confidence_self_rating=ConfidenceWithRationale(
                value=0.5, rationale=f"rationale for {label}", band=to_band(0.5)
            ),
            counterfactual=f"counterfactual for {label}",
        )

    @agent_action(agent_id="agent_a")
    async def a(_: StubIn) -> StubOut:
        await asyncio.sleep(0.01)
        set_runtime_reasoning_trace(_trace("a"))
        return StubOut(bar=1)

    @agent_action(agent_id="agent_b")
    async def b(_: StubIn) -> StubOut:
        await asyncio.sleep(0.005)
        set_runtime_reasoning_trace(_trace("b"))
        return StubOut(bar=2)

    await asyncio.gather(a(StubIn(case_id=SHREE_VENKAT_ID)), b(StubIn(case_id=SHREE_VENKAT_ID)))
    entries = await _read(tmp_writer)
    by_agent: dict[str, AgentActionLedgerEntry] = {}
    for e in entries:
        if isinstance(e.payload, AgentActionLedgerEntry):
            by_agent[e.payload.agent_id] = e.payload
    assert by_agent["agent_a"].reasoning_trace is not None
    assert "search by a" in by_agent["agent_a"].reasoning_trace.what_searched
    assert by_agent["agent_b"].reasoning_trace is not None
    assert "search by b" in by_agent["agent_b"].reasoning_trace.what_searched
