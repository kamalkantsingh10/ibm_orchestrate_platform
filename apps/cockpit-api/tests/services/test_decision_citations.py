"""Tests for the Story 8.4 citation gate in ``decision_service``."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from contracts.cases import VORA_CAPITAL_ID, Case, CaseState, CustomerMetadata
from contracts.decision import CommitDecisionRequest
from contracts.ledger import ActorType, LedgerEntry
from contracts.sse import SseEvent
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from ulid import ULID

from cockpit_api.db.models import Base
from cockpit_api.repositories.case_repo import CaseRepo
from cockpit_api.services import ledger_service
from cockpit_api.services.decision_service import (
    BrokenCitationsError,
    commit_decision,
    validate_decision_citations,
)
from cockpit_api.services.decision_timer import DecisionTimerService
from cockpit_api.services.ledger_service import LedgerReader, LedgerWriter

OTHER_CASE_ID = "case_01ZZZ0000000000000000000ZZ"


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s


@pytest.fixture
def writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LedgerWriter:
    p = tmp_path / "ledger.jsonl"
    w = LedgerWriter(p)
    ledger_service.get_ledger_writer.cache_clear()
    monkeypatch.setattr(ledger_service, "get_ledger_writer", lambda: w)
    return w


@pytest.fixture
def reader(writer: LedgerWriter) -> LedgerReader:
    r = LedgerReader(writer._path)
    return r


def _seed_decision_ready_case() -> Case:
    now = datetime.now(UTC)
    return Case(
        id=VORA_CAPITAL_ID,
        state=CaseState.DECISION_READY,
        customer_metadata=CustomerMetadata(
            customer_name="Vora Capital Holdings Pvt Ltd",
            customer_type="company",
            country="IN",
        ),
        created_at=now,
        updated_at=now,
    )


def _make_body(**overrides: Any) -> CommitDecisionRequest:
    base: dict[str, Any] = {
        "outcome": "approve",
        "conditions": [],
        "rationale_html": "<p>Approve based on screening hits.</p>",
    }
    base.update(overrides)
    return CommitDecisionRequest(**base)


def _publish() -> Any:
    async def _p(case_id: str | None, event: SseEvent) -> None:
        return None

    return _p


def _timer() -> DecisionTimerService:
    async def _on_seal(case_id: str, decision_id: str) -> None:
        return None

    return DecisionTimerService(on_seal=_on_seal, window_seconds=60)


async def _append_entry(writer: LedgerWriter, *, case_id: str) -> str:
    """Append a ledger entry and return the **canonical** id assigned by
    the writer (LedgerWriter regenerates `id` and `recorded_at` server-
    side; the caller-supplied values are ignored)."""
    entry = LedgerEntry(
        id=f"led_{ULID()!s}",
        case_id=case_id,
        actor_type=ActorType.SYSTEM,
        actor_id="case_supervisor",
        action="case.intake_completed",
        payload={"agents": [], "fields_extracted": 0},
        recorded_at=datetime.now(UTC),
    )
    canonical = await writer.append(entry)
    return canonical.id


# ─── validate_decision_citations ─────────────────────────────────────────────


async def test_validate_passes_when_all_citations_resolve_to_case_ledger(
    writer: LedgerWriter,
    reader: LedgerReader,
) -> None:
    led_a = await _append_entry(writer, case_id=VORA_CAPITAL_ID)
    led_b = await _append_entry(writer, case_id=VORA_CAPITAL_ID)
    rationale = (
        f'<p>Cites <span data-ledger-id="{led_a}" class="citation-token">A</span></p>'
        f"<p>Inline {{{{{led_b}}}}} as well.</p>"
    )
    broken = await validate_decision_citations(
        rationale=rationale,
        case_id=VORA_CAPITAL_ID,
        reader=reader,
    )
    assert broken == []


async def test_validate_fails_when_token_references_nonexistent_ulid(
    writer: LedgerWriter,
    reader: LedgerReader,
) -> None:
    fabricated = "led_01ZZZZGHJKMNPQRSTVWXYZ7HX9"
    rationale = f'<p><span data-ledger-id="{fabricated}" class="citation-token">x</span></p>'
    broken = await validate_decision_citations(
        rationale=rationale,
        case_id=VORA_CAPITAL_ID,
        reader=reader,
    )
    assert len(broken) == 1
    assert broken[0].token == fabricated
    assert broken[0].reason == "not_found"


async def test_validate_fails_when_token_references_other_case_ulid(
    writer: LedgerWriter,
    reader: LedgerReader,
) -> None:
    other_led = await _append_entry(writer, case_id=OTHER_CASE_ID)
    rationale = f'<p><span data-ledger-id="{other_led}" class="citation-token">x</span></p>'
    broken = await validate_decision_citations(
        rationale=rationale,
        case_id=VORA_CAPITAL_ID,
        reader=reader,
    )
    assert len(broken) == 1
    assert broken[0].token == other_led
    assert broken[0].reason == "wrong_case"


async def test_validate_collects_distinct_ulids_only(
    writer: LedgerWriter,
    reader: LedgerReader,
) -> None:
    fabricated = "led_01YYYYGHJKMNPQRSTVWXYZ7HX9"
    rationale = (
        f"<p>{{{{{fabricated}}}}}</p>"
        f'<p><span data-ledger-id="{fabricated}" class="citation-token">x</span></p>'
        f"<p>{{{{{fabricated}}}}}</p>"
    )
    broken = await validate_decision_citations(
        rationale=rationale,
        case_id=VORA_CAPITAL_ID,
        reader=reader,
    )
    assert [b.token for b in broken] == [fabricated]


async def test_validate_with_no_citations_returns_empty_list(
    writer: LedgerWriter,
    reader: LedgerReader,
) -> None:
    rationale = "<p>Rationale with no citations whatsoever.</p>"
    broken = await validate_decision_citations(
        rationale=rationale,
        case_id=VORA_CAPITAL_ID,
        reader=reader,
    )
    assert broken == []


async def test_validate_recognizes_inline_brace_token_format(
    writer: LedgerWriter,
    reader: LedgerReader,
) -> None:
    fabricated = "led_01XXXXGHJKMNPQRSTVWXYZ7HX9"
    # Story 8.3 EDD memo format — inline `{{led_<ULID>}}` tokens, not
    # yet rewritten to spans.
    rationale = f"<p>Inline {{{{{fabricated}}}}} citation.</p>"
    broken = await validate_decision_citations(
        rationale=rationale,
        case_id=VORA_CAPITAL_ID,
        reader=reader,
    )
    assert len(broken) == 1
    assert broken[0].reason == "not_found"


# ─── commit_decision wired with the validator ────────────────────────────────


async def test_commit_endpoint_returns_422_via_broken_citations_error(
    session: AsyncSession,
    writer: LedgerWriter,
    reader: LedgerReader,
) -> None:
    case = _seed_decision_ready_case()
    await CaseRepo.insert(session, case)
    await session.commit()
    fabricated = "led_01WWWWGHJKMNPQRSTVWXYZ7HX9"
    body = _make_body(
        rationale_html=(f'<p>Cites <span data-ledger-id="{fabricated}" class="citation-token">x</span>.</p>'),
    )
    with pytest.raises(BrokenCitationsError) as ei:
        await commit_decision(
            session=session,
            case_id=case.id,
            body=body,
            user_id="user_analyst",
            writer=writer,
            sse_publish=_publish(),
            timer=_timer(),
            citation_reader=reader,
        )
    assert ei.value.case_id == case.id
    assert len(ei.value.broken) == 1
    assert ei.value.broken[0].reason == "not_found"
    # Case must remain in decision_ready — no transition on refused commit.
    refreshed = await CaseRepo.get(session, case.id)
    assert refreshed is not None and refreshed.state is CaseState.DECISION_READY


async def test_commit_passes_when_all_citations_resolve(
    session: AsyncSession,
    writer: LedgerWriter,
    reader: LedgerReader,
) -> None:
    case = _seed_decision_ready_case()
    await CaseRepo.insert(session, case)
    await session.commit()
    led = await _append_entry(writer, case_id=case.id)
    body = _make_body(
        rationale_html=(f'<p>Cites <span data-ledger-id="{led}" class="citation-token">x</span>.</p>'),
    )
    response = await commit_decision(
        session=session,
        case_id=case.id,
        body=body,
        user_id="user_analyst",
        writer=writer,
        sse_publish=_publish(),
        timer=_timer(),
        citation_reader=reader,
    )
    assert response.case_state == CaseState.PENDING_SEAL


async def test_commit_skips_validator_when_no_reader_supplied(
    session: AsyncSession,
    writer: LedgerWriter,
) -> None:
    """Backwards-compatibility — legacy test paths that don't supply a
    `citation_reader` keep working (the validator is opt-in)."""
    case = _seed_decision_ready_case()
    await CaseRepo.insert(session, case)
    await session.commit()
    fabricated = "led_01VVVVGHJKMNPQRSTVWXYZ7HX9"
    body = _make_body(
        rationale_html=(f'<p>Cites <span data-ledger-id="{fabricated}" class="citation-token">x</span>.</p>'),
    )
    response = await commit_decision(
        session=session,
        case_id=case.id,
        body=body,
        user_id="user_analyst",
        writer=writer,
        sse_publish=_publish(),
        timer=_timer(),
        # citation_reader omitted — validator is skipped.
    )
    assert response.case_state == CaseState.PENDING_SEAL
