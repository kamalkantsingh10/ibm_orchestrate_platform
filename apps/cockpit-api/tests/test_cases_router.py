"""End-to-end tests for ``GET /v1/cases`` and ``GET /v1/cases/{case_id}`` — Story 2.2 AC #9."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from contracts.cases import (
    Case,
    CaseState,
    CustomerMetadata,
)
from contracts.users import ANALYST_ID, REGULATOR_ID, TEAM_LEAD_ID
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from ulid import ULID

from cockpit_api.db.models import Base
from cockpit_api.db.session import get_session
from cockpit_api.main import app
from cockpit_api.repositories.case_repo import CaseRepo


def _case_id() -> str:
    return f"case_{ULID()!s}"


def _make_case(
    *,
    state: CaseState = CaseState.INTAKE_SCHEDULED,
    created_at: datetime | None = None,
    **overrides: Any,
) -> Case:
    now = created_at or datetime.now(UTC)
    defaults: dict[str, Any] = {
        "id": _case_id(),
        "state": state,
        "customer_metadata": CustomerMetadata(customer_name="Acme Pte Ltd"),
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return Case(**defaults)


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as s:
            yield s
            await s.commit()

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _seed(
    session_factory: async_sessionmaker[AsyncSession],
    case: Case,
) -> None:
    async with session_factory() as s:
        await CaseRepo.insert(s, case)
        await s.commit()


# ───────────── single case ─────────────


async def test_get_case_returns_200_and_envelope(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    case = _make_case()
    await _seed(session_factory, case)

    resp = await client.get(
        f"/v1/cases/{case.id}",
        headers={"X-Cockpit-Demo-User": ANALYST_ID},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == case.id
    assert body["state"] == "intake_scheduled"
    assert body["_links"] == {"documents": None, "reasoning_traces": None}
    assert body["customer_metadata"]["customer_name"] == "Acme Pte Ltd"


async def test_get_case_returns_404_rfc7807_when_missing(client: AsyncClient) -> None:
    missing_id = _case_id()
    resp = await client.get(
        f"/v1/cases/{missing_id}",
        headers={"X-Cockpit-Demo-User": ANALYST_ID},
    )
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body == {
        "type": "about:blank",
        "title": "Not Found",
        "status": 404,
        "detail": f"Case {missing_id} not found",
        "instance": f"/v1/cases/{missing_id}",
    }


async def test_get_case_returns_422_when_path_malformed(client: AsyncClient) -> None:
    resp = await client.get(
        "/v1/cases/bogus",
        headers={"X-Cockpit-Demo-User": ANALYST_ID},
    )
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["status"] == 422
    assert body["title"] == "Unprocessable Entity"
    assert "case_id" in body["detail"]


async def test_get_case_returns_400_when_header_missing(client: AsyncClient) -> None:
    resp = await client.get(f"/v1/cases/{_case_id()}")
    assert resp.status_code == 400
    body = resp.json()
    assert body["status"] == 400
    assert "X-Cockpit-Demo-User" in body["detail"]


async def test_get_case_returns_400_when_header_unknown(client: AsyncClient) -> None:
    resp = await client.get(
        f"/v1/cases/{_case_id()}",
        headers={"X-Cockpit-Demo-User": "00000000-0000-4000-8000-000000999999"},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert "Unknown" in body["detail"]


@pytest.mark.parametrize("user_id", [ANALYST_ID, TEAM_LEAD_ID, REGULATOR_ID])
async def test_get_case_succeeds_for_each_demo_user(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: str,
) -> None:
    case = _make_case()
    await _seed(session_factory, case)

    resp = await client.get(
        f"/v1/cases/{case.id}",
        headers={"X-Cockpit-Demo-User": user_id},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == case.id


# ───────────── list ─────────────


async def test_list_cases_empty(client: AsyncClient) -> None:
    resp = await client.get(
        "/v1/cases",
        headers={"X-Cockpit-Demo-User": ANALYST_ID},
    )
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "next_cursor": None, "has_more": False}


async def test_list_cases_returns_newest_first(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    base = datetime(2026, 4, 30, 12, 0, 0, tzinfo=UTC)
    older = _make_case(created_at=base - timedelta(hours=2))
    middle = _make_case(created_at=base - timedelta(hours=1))
    newest = _make_case(created_at=base)
    for c in (older, middle, newest):
        await _seed(session_factory, c)

    resp = await client.get(
        "/v1/cases",
        headers={"X-Cockpit-Demo-User": ANALYST_ID},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert [item["id"] for item in body["items"]] == [newest.id, middle.id, older.id]
    assert body["next_cursor"] is None
    assert body["has_more"] is False
    # Every envelope still carries the _links placeholder.
    for item in body["items"]:
        assert item["_links"] == {"documents": None, "reasoning_traces": None}


async def test_list_cases_succeeds_without_header() -> None:
    """Story 4.1 — ``GET /v1/cases`` is exposed as a tool to the cloud
    Orchestrate runtime, which does NOT send the demo-user header. The
    endpoint must respond 200 with an empty list (or seeded list) instead
    of 400. Continuity ordering simply doesn't apply for that path.
    """

    # Build a fresh client with no header for this assertion. We re-use the
    # session-factory fixture pattern via app.dependency_overrides — but the
    # simplest path is a direct ASGI client; the existing ``client`` fixture
    # works fine because we just don't pass the header.
    async def _go() -> None:
        from cockpit_api.db.session import get_session  # noqa: PLC0415

        eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        sf = async_sessionmaker(eng, expire_on_commit=False, class_=AsyncSession)

        async def override_get_session() -> AsyncIterator[AsyncSession]:
            async with sf() as s:
                yield s
                await s.commit()

        app.dependency_overrides[get_session] = override_get_session
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.get("/v1/cases")
                assert resp.status_code == 200
                assert resp.json() == {"items": [], "next_cursor": None, "has_more": False}
        finally:
            app.dependency_overrides.clear()
            await eng.dispose()

    await _go()


async def test_list_cases_rejects_unknown_header(client: AsyncClient) -> None:
    """Header *present but unknown* is still 400 (fail-closed for spoofing)."""
    resp = await client.get(
        "/v1/cases",
        headers={"X-Cockpit-Demo-User": "00000000-0000-4000-8000-999999999999"},
    )
    assert resp.status_code == 400
    assert "Unknown" in resp.json()["detail"]


async def test_list_cases_orders_by_risk_sla_continuity(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Story 4.1 AC #8 — three crafted cases verify the full sort precedence."""
    base = datetime(2026, 5, 7, 12, 0, 0, tzinfo=UTC)

    def _sla(hours: float) -> str:
        return (base + timedelta(hours=hours)).isoformat().replace("+00:00", "Z")

    # high risk, far SLA, NOT mine — should still be first (risk dominates)
    high_risk = _make_case(
        created_at=base - timedelta(minutes=30),
        risk_band="high",
        customer_metadata=CustomerMetadata(
            customer_name="High Risk Co",
            extra={"sla_due_at": _sla(72)},
        ),
        assigned_to_user_id=TEAM_LEAD_ID,
    )
    # medium_high, near SLA, mine — second (continuity bonus over `not mine`)
    mine_near = _make_case(
        created_at=base - timedelta(minutes=20),
        risk_band="medium_high",
        customer_metadata=CustomerMetadata(
            customer_name="Mine Near",
            extra={"sla_due_at": _sla(2)},
        ),
        assigned_to_user_id=ANALYST_ID,
    )
    # medium_high, near SLA, NOT mine — third
    theirs_near = _make_case(
        created_at=base - timedelta(minutes=10),
        risk_band="medium_high",
        customer_metadata=CustomerMetadata(
            customer_name="Theirs Near",
            extra={"sla_due_at": _sla(2)},
        ),
        assigned_to_user_id=TEAM_LEAD_ID,
    )

    for c in (theirs_near, mine_near, high_risk):  # shuffled insert order
        await _seed(session_factory, c)

    resp = await client.get(
        "/v1/cases",
        headers={"X-Cockpit-Demo-User": ANALYST_ID},
    )
    assert resp.status_code == 200
    body = resp.json()
    names = [item["customer_metadata"]["customer_name"] for item in body["items"]]
    assert names == ["High Risk Co", "Mine Near", "Theirs Near"]


# ───────────── Story 6.5 — GET reasoning trace endpoint ─────────────


import pathlib  # noqa: E402

from contracts.agent_action import AgentActionLedgerEntry  # noqa: E402
from contracts.confidence import to_band  # noqa: E402
from contracts.ledger import (  # noqa: E402
    ActorType,
    LearningEventLedgerPayload,  # noqa: E402
    LedgerEntry,
)
from contracts.reasoning_trace import (  # noqa: E402
    ConfidenceWithRationale,
    ReasoningTrace,
)

from cockpit_api.services import ledger_service  # noqa: E402
from cockpit_api.services.ledger_service import LedgerWriter  # noqa: E402

ANALYST_HEADERS = {"X-Cockpit-Demo-User": ANALYST_ID}


def _valid_trace() -> ReasoningTrace:
    return ReasoningTrace(
        what_searched="screened 1 director against the configured screening provider",
        what_hit="returned 1 sanctions match at score 0.73 against OFAC SDN",
        confidence_self_rating=ConfidenceWithRationale(
            value=0.73,
            rationale="confidence is the mean name-match score of the returned hit",
            band=to_band(0.73),
        ),
        counterfactual="disposition would change with officer DOB confirmation",
    )


@pytest_asyncio.fixture
async def writer(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> LedgerWriter:
    p = tmp_path / "ledger.jsonl"
    w = LedgerWriter(p)
    r = ledger_service.LedgerReader(p)
    ledger_service.get_ledger_writer.cache_clear()
    ledger_service.get_ledger_reader.cache_clear()
    monkeypatch.setattr(ledger_service, "get_ledger_writer", lambda: w)
    monkeypatch.setattr(ledger_service, "get_ledger_reader", lambda: r)
    # Story 6.7 — agents-side ledger references must also be patched so the
    # screening agent's @agent_action writes to the same tmp file the
    # cockpit-api endpoint reads from.
    import agents.supervisor.action_decorator as _deco

    monkeypatch.setattr(_deco, "get_ledger_writer", lambda: w)
    return w


def _agent_payload(*, trace: ReasoningTrace | None) -> AgentActionLedgerEntry:
    return AgentActionLedgerEntry(
        agent_id="screening",
        input={"k": 1},
        output={"y": 2},
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        duration_ms=12,
        status="ok",
        reasoning_trace=trace,
    )


def _entry(
    *,
    case_id: str,
    actor_id: str = "screening",
    actor_type: ActorType = ActorType.AGENT,
    action: str = "agent.completed",
    payload: AgentActionLedgerEntry | LearningEventLedgerPayload | dict[str, Any],
) -> LedgerEntry:
    return LedgerEntry(
        id=f"led_{ULID()!s}",
        actor_type=actor_type,
        actor_id=actor_id,
        case_id=case_id,
        action=action,
        payload=payload,
        recorded_at=datetime.now(UTC),
    )


async def test_reasoning_trace_returns_200_with_typed_body(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
) -> None:
    case = _make_case()
    await _seed(session_factory, case)
    appended = await writer.append(_entry(case_id=case.id, payload=_agent_payload(trace=_valid_trace())))
    resp = await client.get(
        f"/v1/cases/{case.id}/agent-actions/{appended.id}/reasoning-trace",
        headers=ANALYST_HEADERS,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "what_searched" in body
    assert "what_hit" in body
    assert "counterfactual" in body
    assert body["confidence_self_rating"]["band"] == to_band(0.73).value


async def test_reasoning_trace_returns_204_when_trace_none(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
) -> None:
    case = _make_case()
    await _seed(session_factory, case)
    appended = await writer.append(
        _entry(
            case_id=case.id,
            actor_id="document_intelligence",
            payload=_agent_payload(trace=None),
        )
    )
    resp = await client.get(
        f"/v1/cases/{case.id}/agent-actions/{appended.id}/reasoning-trace",
        headers=ANALYST_HEADERS,
    )
    assert resp.status_code == 204
    assert resp.content == b""


async def test_reasoning_trace_404_when_case_missing(client: AsyncClient, writer: LedgerWriter) -> None:
    fake_action = f"led_{ULID()!s}"
    resp = await client.get(
        f"/v1/cases/{_case_id()}/agent-actions/{fake_action}/reasoning-trace",
        headers=ANALYST_HEADERS,
    )
    assert resp.status_code == 404


async def test_reasoning_trace_404_when_action_missing(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
) -> None:
    case = _make_case()
    await _seed(session_factory, case)
    fake_action = f"led_{ULID()!s}"
    resp = await client.get(
        f"/v1/cases/{case.id}/agent-actions/{fake_action}/reasoning-trace",
        headers=ANALYST_HEADERS,
    )
    assert resp.status_code == 404


async def test_reasoning_trace_404_when_action_belongs_to_other_case(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
) -> None:
    case_a = _make_case()
    case_b = _make_case()
    await _seed(session_factory, case_a)
    await _seed(session_factory, case_b)
    appended = await writer.append(_entry(case_id=case_b.id, payload=_agent_payload(trace=_valid_trace())))
    resp = await client.get(
        f"/v1/cases/{case_a.id}/agent-actions/{appended.id}/reasoning-trace",
        headers=ANALYST_HEADERS,
    )
    assert resp.status_code == 404


async def test_reasoning_trace_404_when_entry_is_system(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
) -> None:
    case = _make_case()
    await _seed(session_factory, case)
    appended = await writer.append(
        _entry(
            case_id=case.id,
            actor_id="case_supervisor",
            actor_type=ActorType.SYSTEM,
            action="case.intake_completed",
            payload={"agents": ["screening"], "fields_extracted": 0},
        )
    )
    resp = await client.get(
        f"/v1/cases/{case.id}/agent-actions/{appended.id}/reasoning-trace",
        headers=ANALYST_HEADERS,
    )
    assert resp.status_code == 404


async def test_reasoning_trace_404_when_entry_is_learning_event(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
) -> None:
    case = _make_case()
    await _seed(session_factory, case)
    le_payload = LearningEventLedgerPayload(
        edge_kind="director",
        from_id="ubo_p_x",
        original_to_id="ubo_e_y",
        new_to_id="ubo_e_z",
        correction_tag="real_ubo",
        evidence_note="officer correction",
        opt_in_for_retraining=False,
    )
    appended = await writer.append(
        _entry(
            case_id=case.id,
            actor_id=ANALYST_ID,
            actor_type=ActorType.OFFICER,
            action="ubo.learning_event",
            payload=le_payload,
        )
    )
    resp = await client.get(
        f"/v1/cases/{case.id}/agent-actions/{appended.id}/reasoning-trace",
        headers=ANALYST_HEADERS,
    )
    assert resp.status_code == 404


async def test_reasoning_trace_422_on_bad_action_id(client: AsyncClient) -> None:
    case_id = _case_id()
    resp = await client.get(
        f"/v1/cases/{case_id}/agent-actions/not-an-id/reasoning-trace",
        headers=ANALYST_HEADERS,
    )
    assert resp.status_code == 422


async def test_reasoning_trace_400_when_header_missing(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
) -> None:
    case = _make_case()
    await _seed(session_factory, case)
    appended = await writer.append(_entry(case_id=case.id, payload=_agent_payload(trace=_valid_trace())))
    resp = await client.get(f"/v1/cases/{case.id}/agent-actions/{appended.id}/reasoning-trace")
    # No demo-user header → 400 (matches existing case-router auth pattern).
    assert resp.status_code == 400


# ───────────── Story 6.7 — re_run_agent + query_ledger endpoints ─────────────


from contracts.ledger import CockpitChatToolLedgerPayload  # noqa: E402


async def test_re_run_agent_screening_returns_action_id(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
) -> None:
    """Demo's screening-only path returns 200 + the new agent_action_id."""
    from contracts.cases import VORA_CAPITAL_ID, get_demo_case_fixtures

    fixtures = get_demo_case_fixtures(datetime.now(UTC))
    vora = next(c for c in fixtures if c.id == VORA_CAPITAL_ID)
    await _seed(session_factory, vora)

    resp = await client.post(
        f"/v1/cases/{vora.id}/agents/screening/run",
        headers=ANALYST_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["agent_slug"] == "screening"
    assert body["agent_action_id"].startswith("led_")
    assert body["status"] == "ok"

    # Two ledger entries written: the screening agent.completed (via
    # @agent_action) and the cockpit_chat.tool_invoked wrap.
    entries = await ledger_service.LedgerReader(writer._path).read_for_case(vora.id)
    actor_ids = [e.actor_id for e in entries]
    assert "screening" in actor_ids
    assert "cockpit_chat" in actor_ids


async def test_re_run_agent_other_slug_returns_501(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
) -> None:
    case = _make_case()
    await _seed(session_factory, case)
    resp = await client.post(
        f"/v1/cases/{case.id}/agents/risk_scoring/run",
        headers=ANALYST_HEADERS,
    )
    assert resp.status_code == 501


async def test_re_run_agent_404_when_case_missing(client: AsyncClient, writer: LedgerWriter) -> None:
    resp = await client.post(
        f"/v1/cases/{_case_id()}/agents/screening/run",
        headers=ANALYST_HEADERS,
    )
    assert resp.status_code == 404


async def test_get_case_ledger_returns_entries(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
) -> None:
    case = _make_case()
    await _seed(session_factory, case)
    # Seed 3 entries.
    for i in range(3):
        await writer.append(
            _entry(
                case_id=case.id,
                actor_id=f"agent_{i}",
                payload=_agent_payload(trace=None),
            )
        )
    resp = await client.get(
        f"/v1/cases/{case.id}/ledger",
        headers=ANALYST_HEADERS,
    )
    assert resp.status_code == 200
    body = resp.json()
    # The response is the snapshot taken BEFORE the chat-tool entry is
    # appended (the helper writes on context-exit). The 3 seeded entries
    # are returned; the chat-tool wrap is verified separately via the
    # ledger reader (test_query_ledger_writes_cockpit_chat_tool_entry).
    assert len(body) == 3


async def test_get_case_ledger_filters_by_actor_id(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
) -> None:
    case = _make_case()
    await _seed(session_factory, case)
    await writer.append(_entry(case_id=case.id, actor_id="screening", payload=_agent_payload(trace=None)))
    await writer.append(_entry(case_id=case.id, actor_id="ubo_graph", payload=_agent_payload(trace=None)))
    resp = await client.get(
        f"/v1/cases/{case.id}/ledger",
        headers=ANALYST_HEADERS,
        params={"actor_id": "screening"},
    )
    assert resp.status_code == 200
    body = resp.json()
    actor_ids = {e["actor_id"] for e in body}
    assert actor_ids == {"screening"}


async def test_get_case_ledger_honours_limit(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
) -> None:
    case = _make_case()
    await _seed(session_factory, case)
    for i in range(5):
        await writer.append(
            _entry(
                case_id=case.id,
                actor_id=f"agent_{i}",
                payload=_agent_payload(trace=None),
            )
        )
    resp = await client.get(
        f"/v1/cases/{case.id}/ledger?limit=2",
        headers=ANALYST_HEADERS,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2


async def test_get_case_ledger_404_when_case_missing(client: AsyncClient, writer: LedgerWriter) -> None:
    resp = await client.get(
        f"/v1/cases/{_case_id()}/ledger",
        headers=ANALYST_HEADERS,
    )
    assert resp.status_code == 404


async def test_query_ledger_writes_cockpit_chat_tool_entry(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
) -> None:
    case = _make_case()
    await _seed(session_factory, case)
    resp = await client.get(
        f"/v1/cases/{case.id}/ledger?limit=10",
        headers=ANALYST_HEADERS,
    )
    assert resp.status_code == 200
    entries = await ledger_service.LedgerReader(writer._path).read_for_case(case.id)
    chat_entries = [
        e for e in entries if e.actor_id == "cockpit_chat" and isinstance(e.payload, CockpitChatToolLedgerPayload)
    ]
    assert len(chat_entries) == 1
    payload = chat_entries[0].payload
    assert isinstance(payload, CockpitChatToolLedgerPayload)
    assert payload.tool_name == "query_ledger"


# ───────────── Story 7.5 — undo timer view + undo endpoint ─────────────


async def test_get_active_timer_returns_204_when_no_pending_seal(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
) -> None:
    case = _make_case(state=CaseState.DECISION_READY)
    await _seed(session_factory, case)
    resp = await client.get(
        f"/v1/cases/{case.id}/decisions/active/timer",
        headers=ANALYST_HEADERS,
    )
    assert resp.status_code == 204


async def test_get_active_timer_returns_200_with_view_when_active(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
) -> None:
    """Inject the timer service singleton with an active pending decision."""
    from cockpit_api.main import app as _app
    from cockpit_api.services.decision_timer import DecisionTimerService

    async def _noop(case_id: str, decision_id: str) -> None:
        return None

    case = _make_case(state=CaseState.PENDING_SEAL)
    await _seed(session_factory, case)
    timer = DecisionTimerService(on_seal=_noop, window_seconds=60)
    timer.schedule(case.id, "dec_test_777")
    saved = getattr(_app.state, "decision_timer", None)
    _app.state.decision_timer = timer
    try:
        resp = await client.get(
            f"/v1/cases/{case.id}/decisions/active/timer",
            headers=ANALYST_HEADERS,
        )
    finally:
        _app.state.decision_timer = saved
        timer.cancel(case.id)
    assert resp.status_code == 200
    body = resp.json()
    assert body["case_id"] == case.id
    assert body["decision_id"] == "dec_test_777"
    assert 0 < body["remaining_seconds"] <= 60.0


async def test_post_undo_with_valid_reason_reverts_case_and_writes_ledger(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
) -> None:
    from cockpit_api.main import app as _app
    from cockpit_api.services.decision_timer import DecisionTimerService

    async def _noop(case_id: str, decision_id: str) -> None:
        return None

    case = _make_case(state=CaseState.PENDING_SEAL)
    await _seed(session_factory, case)
    timer = DecisionTimerService(on_seal=_noop, window_seconds=60)
    timer.schedule(case.id, "dec_test_undo")
    saved = getattr(_app.state, "decision_timer", None)
    _app.state.decision_timer = timer
    try:
        resp = await client.post(
            f"/v1/cases/{case.id}/decisions/dec_test_undo/undo",
            headers=ANALYST_HEADERS,
            json={
                "reason": ("Officer realized the OFAC hit needs deeper review before sealing."),
            },
        )
    finally:
        _app.state.decision_timer = saved
    assert resp.status_code == 200, resp.json()
    body = resp.json()
    assert body["case_state"] == "decision_ready"
    assert body["decision_id"] == "dec_test_undo"
    assert body["ledger_entry_id"].startswith("led_")
    # Timer cancelled.
    assert timer.remaining_seconds(case.id) is None
    # Ledger entry exists with the typed payload.
    entries = await ledger_service.LedgerReader(writer._path).read_for_case(case.id)
    undone = [e for e in entries if e.action == "officer.decision_undone"]
    assert len(undone) == 1
    payload = undone[0].payload
    from contracts.ledger import OfficerDecisionUndonePayload

    assert isinstance(payload, OfficerDecisionUndonePayload)
    assert payload.decision_id == "dec_test_undo"
    assert "OFAC" in payload.reason


async def test_post_undo_with_short_reason_returns_422(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
) -> None:
    case = _make_case(state=CaseState.PENDING_SEAL)
    await _seed(session_factory, case)
    resp = await client.post(
        f"/v1/cases/{case.id}/decisions/dec_short/undo",
        headers=ANALYST_HEADERS,
        json={"reason": "too short"},
    )
    assert resp.status_code == 422


async def test_post_undo_when_state_is_decision_ready_returns_409(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
) -> None:
    case = _make_case(state=CaseState.DECISION_READY)
    await _seed(session_factory, case)
    resp = await client.post(
        f"/v1/cases/{case.id}/decisions/dec_x/undo",
        headers=ANALYST_HEADERS,
        json={
            "reason": "long enough reason text to pass the forty-character minimum.",
        },
    )
    assert resp.status_code == 409
    assert "no longer pending seal" in resp.json()["detail"].lower()


async def test_post_undo_when_state_is_committed_returns_409_already_sealed(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
) -> None:
    case = _make_case(state=CaseState.COMMITTED)
    await _seed(session_factory, case)
    resp = await client.post(
        f"/v1/cases/{case.id}/decisions/dec_x/undo",
        headers=ANALYST_HEADERS,
        json={
            "reason": "long enough reason text to pass the forty-character minimum.",
        },
    )
    assert resp.status_code == 409
    assert "already sealed" in resp.json()["detail"].lower()


async def test_post_undo_with_mismatched_decision_id_returns_409(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
) -> None:
    from cockpit_api.main import app as _app
    from cockpit_api.services.decision_timer import DecisionTimerService

    async def _noop(case_id: str, decision_id: str) -> None:
        return None

    case = _make_case(state=CaseState.PENDING_SEAL)
    await _seed(session_factory, case)
    timer = DecisionTimerService(on_seal=_noop, window_seconds=60)
    timer.schedule(case.id, "dec_active")
    saved = getattr(_app.state, "decision_timer", None)
    _app.state.decision_timer = timer
    try:
        resp = await client.post(
            f"/v1/cases/{case.id}/decisions/dec_stale/undo",
            headers=ANALYST_HEADERS,
            json={
                "reason": "long enough reason text to pass the forty-character minimum.",
            },
        )
    finally:
        _app.state.decision_timer = saved
        timer.cancel(case.id)
    assert resp.status_code == 409
    assert "does not match the active timer" in resp.json()["detail"].lower()


async def test_post_undo_returns_404_when_case_missing(
    client: AsyncClient,
    writer: LedgerWriter,
) -> None:
    resp = await client.post(
        # Crockford-Base32 ULID — no I/L/O/U; case never inserted.
        "/v1/cases/case_01ZZZZZZZZZZZZZZZZZZZZZ7HX/decisions/dec_x/undo",
        headers=ANALYST_HEADERS,
        json={
            "reason": "long enough reason text to pass the forty-character minimum.",
        },
    )
    assert resp.status_code == 404


# ───────────── Story 7.7 — POST /v1/cases/{id}/decisions ─────────────


@pytest_asyncio.fixture
async def decision_timer_singleton() -> AsyncIterator[None]:
    """Inject a real DecisionTimerService onto ``app.state`` for the
    duration of the test. Tests using this fixture exercise the POST
    decision route which reads the singleton off the app state.
    """
    from cockpit_api.main import app as _app
    from cockpit_api.services.decision_timer import DecisionTimerService

    async def _noop(case_id: str, decision_id: str) -> None:
        return None

    timer = DecisionTimerService(on_seal=_noop, window_seconds=300)
    saved = getattr(_app.state, "decision_timer", None)
    _app.state.decision_timer = timer
    try:
        yield
    finally:
        await timer.shutdown()
        _app.state.decision_timer = saved


def _decision_body(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "outcome": "approve",
        "conditions": [],
        "rationale_html": "<p>Approve based on screening hits.</p>",
    }
    base.update(overrides)
    return base


async def test_post_decision_201_returns_response(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
    decision_timer_singleton: None,
) -> None:
    case = _make_case(state=CaseState.DECISION_READY)
    await _seed(session_factory, case)
    resp = await client.post(
        f"/v1/cases/{case.id}/decisions",
        headers=ANALYST_HEADERS,
        json=_decision_body(),
    )
    assert resp.status_code == 201, resp.json()
    body = resp.json()
    assert body["case_id"] == case.id
    assert body["decision_id"].startswith("dec_")
    assert body["case_state"] == "pending_seal"
    assert body["ledger_entry_id"].startswith("led_")


async def test_post_decision_writes_ledger_entry(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
    decision_timer_singleton: None,
) -> None:
    case = _make_case(state=CaseState.DECISION_READY)
    await _seed(session_factory, case)
    resp = await client.post(
        f"/v1/cases/{case.id}/decisions",
        headers=ANALYST_HEADERS,
        json=_decision_body(),
    )
    assert resp.status_code == 201
    entries = await ledger_service.LedgerReader(writer._path).read_for_case(case.id)
    from contracts.ledger import OfficerDecisionCommittedPayload

    committed = [e for e in entries if isinstance(e.payload, OfficerDecisionCommittedPayload)]
    assert len(committed) == 1


async def test_post_decision_rejects_short_rationale(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
    decision_timer_singleton: None,
) -> None:
    case = _make_case(state=CaseState.DECISION_READY)
    await _seed(session_factory, case)
    resp = await client.post(
        f"/v1/cases/{case.id}/decisions",
        headers=ANALYST_HEADERS,
        json=_decision_body(rationale_html="<p>x</p>"),
    )
    assert resp.status_code == 422


async def test_post_decision_rejects_approve_with_conditions_empty(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
    decision_timer_singleton: None,
) -> None:
    case = _make_case(state=CaseState.DECISION_READY)
    await _seed(session_factory, case)
    resp = await client.post(
        f"/v1/cases/{case.id}/decisions",
        headers=ANALYST_HEADERS,
        json=_decision_body(outcome="approve_with_conditions", conditions=[]),
    )
    assert resp.status_code == 422


async def test_post_decision_409_when_intake_scheduled(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
    decision_timer_singleton: None,
) -> None:
    case = _make_case(state=CaseState.INTAKE_SCHEDULED)
    await _seed(session_factory, case)
    resp = await client.post(
        f"/v1/cases/{case.id}/decisions",
        headers=ANALYST_HEADERS,
        json=_decision_body(),
    )
    assert resp.status_code == 409


async def test_post_decision_409_when_pending_seal(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
    decision_timer_singleton: None,
) -> None:
    case = _make_case(state=CaseState.PENDING_SEAL)
    await _seed(session_factory, case)
    resp = await client.post(
        f"/v1/cases/{case.id}/decisions",
        headers=ANALYST_HEADERS,
        json=_decision_body(),
    )
    assert resp.status_code == 409


async def test_post_decision_409_when_committed(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
    decision_timer_singleton: None,
) -> None:
    case = _make_case(state=CaseState.COMMITTED)
    await _seed(session_factory, case)
    resp = await client.post(
        f"/v1/cases/{case.id}/decisions",
        headers=ANALYST_HEADERS,
        json=_decision_body(),
    )
    assert resp.status_code == 409


async def test_post_decision_404_when_case_missing(
    client: AsyncClient,
    writer: LedgerWriter,
    decision_timer_singleton: None,
) -> None:
    resp = await client.post(
        "/v1/cases/case_01ZZZZZZZZZZZZZZZZZZZZZ7HX/decisions",
        headers=ANALYST_HEADERS,
        json=_decision_body(),
    )
    assert resp.status_code == 404


async def test_post_decision_schedules_timer_and_persists_row(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    writer: LedgerWriter,
    decision_timer_singleton: None,
) -> None:
    from cockpit_api.main import app as _app
    from cockpit_api.repositories.decision_repo import DecisionRepo

    case = _make_case(state=CaseState.DECISION_READY)
    await _seed(session_factory, case)
    resp = await client.post(
        f"/v1/cases/{case.id}/decisions",
        headers=ANALYST_HEADERS,
        json=_decision_body(),
    )
    assert resp.status_code == 201
    decision_id = resp.json()["decision_id"]
    timer = getattr(_app.state, "decision_timer", None)
    assert timer is not None
    assert timer.remaining_seconds(case.id) is not None
    timer.cancel(case.id)
    async with session_factory() as s:
        row = await DecisionRepo.fetch_by_id(s, decision_id)
    assert row is not None
    assert row.outcome == "approve"
