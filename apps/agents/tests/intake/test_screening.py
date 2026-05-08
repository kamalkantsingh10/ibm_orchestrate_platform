"""Tests for the Screening agent — Story 6.2 / AC #10."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from cockpit_api.services.ledger_service import LedgerReader, LedgerWriter
from contracts.agent_action import AgentActionLedgerEntry
from contracts.cases import VORA_CAPITAL_ID
from contracts.confidence import to_band
from contracts.provenance import Provenance, ProvenancedField
from contracts.screening import (
    ScreeningAdapter,
    ScreeningAgentInput,
    ScreeningHit,
    ScreeningRequest,
    ScreeningSubject,
    ScreeningTemporaryError,
)

from agents.adapters.screening import MockScreeningAdapter
from agents.intake.screening import screening
from agents.supervisor.action_decorator import AgentExecutionError


def _hit(
    *,
    score: float,
    subject_id: str,
    matched_name: str = "Match Name",
    dob: date | None = None,
) -> ScreeningHit:
    pf: ProvenancedField[float] = ProvenancedField(
        value=score,
        provenance=Provenance(
            source_agent="screening",
            source_system="screening_mock",
            confidence=score,
            confidence_band=to_band(score),
            evidence_ids=[],
            captured_at=datetime.now(UTC),
        ),
    )
    return ScreeningHit(
        hit_id=f"hit_mock_{subject_id[-12:]}",
        subject_id=subject_id,
        matched_name=matched_name,
        name_match_score=pf,
        date_of_birth=dob,
        categories=["sanctions"],
        source_lists=["OFAC SDN"],
    )


class _StubAdapter(ScreeningAdapter):
    def __init__(self, hits: list[ScreeningHit] | Exception) -> None:
        self._hits = hits

    async def screen(self, req: ScreeningRequest) -> list[ScreeningHit]:  # noqa: ARG002
        if isinstance(self._hits, Exception):
            raise self._hits
        return list(self._hits)


def _vora_subject(dob: date | None = date(1978, 1, 1)) -> ScreeningSubject:
    return ScreeningSubject(
        subject_kind="director",
        subject_id="ubo_p_09876544",
        full_name="Rohan Mehta",
        date_of_birth=dob,
    )


# ───────────── happy path ─────────────


async def test_high_score_hit_passes_through_as_open(tmp_writer: LedgerWriter) -> None:
    stub = _StubAdapter([_hit(score=0.85, subject_id="ubo_p_09876544")])
    out = await screening(
        ScreeningAgentInput(case_id=VORA_CAPITAL_ID, subjects=[_vora_subject()]),
        adapter=stub,
    )
    assert out.subjects_screened == 1
    assert len(out.hits) == 1
    assert out.hits[0].disposition == "open"
    assert out.hits[0].dismissal_rationale is None


# ───────────── auto-dismiss: low score ─────────────


async def test_low_score_hit_is_auto_dismissed(tmp_writer: LedgerWriter) -> None:
    stub = _StubAdapter([_hit(score=0.40, subject_id="ubo_p_09876544")])
    out = await screening(
        ScreeningAgentInput(case_id=VORA_CAPITAL_ID, subjects=[_vora_subject()]),
        adapter=stub,
    )
    assert out.hits[0].disposition == "dismissed_by_agent"
    assert "low name match (0.40)" in (out.hits[0].dismissal_rationale or "")


# ───────────── auto-dismiss: medium-low score with DOB mismatch ─────────────


async def test_medium_low_score_dob_differs_dismisses(tmp_writer: LedgerWriter) -> None:
    stub = _StubAdapter([_hit(score=0.55, subject_id="ubo_p_09876544", dob=date(1961, 5, 12))])
    out = await screening(
        ScreeningAgentInput(case_id=VORA_CAPITAL_ID, subjects=[_vora_subject(dob=date(1978, 1, 1))]),
        adapter=stub,
    )
    assert out.hits[0].disposition == "dismissed_by_agent"
    rationale = out.hits[0].dismissal_rationale or ""
    assert "DOB" in rationale or "dob" in rationale


# ───────────── NOT auto-dismissed: medium-low + DOB matches ─────────────


async def test_medium_low_score_dob_matches_stays_open(tmp_writer: LedgerWriter) -> None:
    stub = _StubAdapter([_hit(score=0.55, subject_id="ubo_p_09876544", dob=date(1978, 1, 1))])
    out = await screening(
        ScreeningAgentInput(case_id=VORA_CAPITAL_ID, subjects=[_vora_subject(dob=date(1978, 1, 1))]),
        adapter=stub,
    )
    assert out.hits[0].disposition == "open"


# ───────────── adapter raises temporary error → AgentExecutionError ─────────────


async def test_adapter_temporary_error_bubbles_via_decorator(tmp_writer: LedgerWriter) -> None:
    stub = _StubAdapter(ScreeningTemporaryError("vendor down"))
    with pytest.raises(AgentExecutionError) as exc_info:
        await screening(
            ScreeningAgentInput(case_id=VORA_CAPITAL_ID, subjects=[_vora_subject()]),
            adapter=stub,
        )
    assert exc_info.value.agent_id == "screening"
    assert isinstance(exc_info.value.original, ScreeningTemporaryError)


# ───────────── adapter=None resolves to default mock ─────────────


async def test_adapter_none_resolves_via_factory(tmp_writer: LedgerWriter, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCREENING_PROVIDER", "mock")
    out = await screening(
        ScreeningAgentInput(case_id=VORA_CAPITAL_ID, subjects=[_vora_subject()]),
    )
    # Mock returns OFAC SDN hit at 0.73 for Rohan Mehta — survives auto-dismissal.
    assert any("sanctions" in h.categories and h.disposition == "open" for h in out.hits)


# ───────────── ledger entry written on success ─────────────


async def test_writes_one_agent_completed_entry(tmp_writer: LedgerWriter) -> None:
    stub = _StubAdapter([_hit(score=0.85, subject_id="ubo_p_09876544")])
    await screening(
        ScreeningAgentInput(case_id=VORA_CAPITAL_ID, subjects=[_vora_subject()]),
        adapter=stub,
    )
    reader = LedgerReader(tmp_writer._path)
    entries = await reader.read_for_case(VORA_CAPITAL_ID)
    completed = [
        e
        for e in entries
        if e.actor_id == "screening" and isinstance(e.payload, AgentActionLedgerEntry) and e.payload.status == "ok"
    ]
    assert len(completed) == 1
    assert completed[0].action == "agent.completed"
    payload = completed[0].payload
    assert isinstance(payload, AgentActionLedgerEntry)
    output = payload.output
    assert output is not None
    assert output["case_id"] == VORA_CAPITAL_ID
    assert len(output["hits"]) == 1


# ───────────── adapter resolution uses mock when env unset ─────────────


async def test_default_factory_returns_mock_adapter(tmp_writer: LedgerWriter, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sanity check the factory wiring used inside screening()."""
    monkeypatch.delenv("SCREENING_PROVIDER", raising=False)
    from agents.adapters.screening import get_default_screening_adapter

    assert isinstance(get_default_screening_adapter(), MockScreeningAdapter)


# ───────────── Story 6.4 — reasoning trace integration ─────────────


async def test_screening_emits_reasoning_trace_on_open_hit(tmp_writer: LedgerWriter) -> None:
    stub = _StubAdapter([_hit(score=0.85, subject_id="ubo_p_09876544")])
    await screening(
        ScreeningAgentInput(case_id=VORA_CAPITAL_ID, subjects=[_vora_subject()]),
        adapter=stub,
    )
    reader = LedgerReader(tmp_writer._path)
    entries = await reader.read_for_case(VORA_CAPITAL_ID)
    payload = entries[-1].payload
    assert isinstance(payload, AgentActionLedgerEntry)
    rt = payload.reasoning_trace
    assert rt is not None
    assert "screening provider" in rt.what_searched
    assert "1 open" in rt.what_hit
    assert "officer-supplied evidence" in rt.counterfactual


async def test_screening_emits_reasoning_trace_on_no_hits(tmp_writer: LedgerWriter) -> None:
    stub = _StubAdapter([])
    await screening(
        ScreeningAgentInput(case_id=VORA_CAPITAL_ID, subjects=[_vora_subject()]),
        adapter=stub,
    )
    reader = LedgerReader(tmp_writer._path)
    entries = await reader.read_for_case(VORA_CAPITAL_ID)
    payload = entries[-1].payload
    assert isinstance(payload, AgentActionLedgerEntry)
    rt = payload.reasoning_trace
    assert rt is not None
    assert "No officer-actionable hits" in rt.what_hit
    assert "Result would change" in rt.counterfactual


async def test_screening_trace_confidence_is_mean_of_hit_scores(tmp_writer: LedgerWriter) -> None:
    hits = [
        _hit(score=0.7, subject_id="ubo_p_a"),
        _hit(score=0.9, subject_id="ubo_p_b"),
    ]
    stub = _StubAdapter(hits)
    await screening(
        ScreeningAgentInput(case_id=VORA_CAPITAL_ID, subjects=[_vora_subject()]),
        adapter=stub,
    )
    reader = LedgerReader(tmp_writer._path)
    entries = await reader.read_for_case(VORA_CAPITAL_ID)
    payload = entries[-1].payload
    assert isinstance(payload, AgentActionLedgerEntry)
    rt = payload.reasoning_trace
    assert rt is not None
    assert rt.confidence_self_rating.value == pytest.approx((0.7 + 0.9) / 2)


async def test_screening_trace_confidence_one_when_no_hits(tmp_writer: LedgerWriter) -> None:
    stub = _StubAdapter([])
    await screening(
        ScreeningAgentInput(case_id=VORA_CAPITAL_ID, subjects=[_vora_subject()]),
        adapter=stub,
    )
    reader = LedgerReader(tmp_writer._path)
    entries = await reader.read_for_case(VORA_CAPITAL_ID)
    payload = entries[-1].payload
    assert isinstance(payload, AgentActionLedgerEntry)
    rt = payload.reasoning_trace
    assert rt is not None
    assert rt.confidence_self_rating.value == pytest.approx(1.0)
