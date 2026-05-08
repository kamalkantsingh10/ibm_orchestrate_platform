"""Tests for POST /v1/cases/{id}/ubo/learning-events — Story 5.5 / AC #9."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from contracts.cases import (
    VORA_CAPITAL_ID,
    Case,
    get_demo_case_fixtures,
)
from contracts.users import ANALYST_ID, TEAM_LEAD_ID
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from cockpit_api.db import session as session_mod
from cockpit_api.db.models import Base
from cockpit_api.main import app
from cockpit_api.repositories.case_repo import CaseRepo
from cockpit_api.repositories.intake_repo import IntakeRepo
from cockpit_api.services import ledger_service
from cockpit_api.services.ledger_service import LedgerReader, LedgerWriter
from tests.fixtures.ubo_graph_vora import (
    ANCHOR_ID,
    COASTAL_ID,
    VORA_ROOT_ID,
    make_vora_graph,
)


@pytest_asyncio.fixture
async def engine_with_app(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(eng, expire_on_commit=False)
    monkeypatch.setattr(session_mod, "_engine", eng)
    monkeypatch.setattr(session_mod, "_sessionmaker", factory)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest.fixture
def tmp_writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[LedgerWriter]:
    path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path)
    ledger_service.get_ledger_writer.cache_clear()
    monkeypatch.setattr(ledger_service, "get_ledger_writer", lambda: writer)
    yield writer


HEADERS_ANALYST = {"X-Cockpit-Demo-User": ANALYST_ID, "Content-Type": "application/json"}
HEADERS_LEAD = {"X-Cockpit-Demo-User": TEAM_LEAD_ID, "Content-Type": "application/json"}


def _payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "edge_kind": "owns",
        "from_id": COASTAL_ID,
        "original_to_id": VORA_ROOT_ID,
        "new_to_id": VORA_ROOT_ID,
        "correction_tag": "real_ubo",
        "evidence_note": "RM email 2024-11 disclosed offshore family trust",
        "opt_in_for_retraining": True,
    }
    base.update(overrides)
    return base


async def _seed(engine: AsyncEngine, *, with_ubo: bool = True) -> Case:
    fixtures = get_demo_case_fixtures(datetime.now(UTC))
    target = next(c for c in fixtures if c.id == VORA_CAPITAL_ID)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await CaseRepo.insert(session, target)
        if with_ubo:
            await IntakeRepo.upsert(session, target.id, "ubo_graph", make_vora_graph())
        await session.commit()
    return target


# ───────────── happy path ─────────────


async def test_happy_path_real_ubo(engine_with_app: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    case = await _seed(engine_with_app)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/v1/cases/{case.id}/ubo/learning-events",
            json=_payload(),
            headers=HEADERS_ANALYST,
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["case_id"] == case.id
    assert body["ledger_entry_id"].startswith("led_")

    # Ledger entry written with the typed payload.
    entries = await LedgerReader(tmp_writer._path).read_all()
    matching = [e for e in entries if e.action == "ubo.edge_corrected"]
    assert len(matching) == 1
    entry = matching[0]
    assert entry.actor_type.value == "officer"
    assert entry.actor_id == ANALYST_ID
    assert entry.payload.kind == "learning_event"  # type: ignore[union-attr]
    assert entry.payload.correction_tag == "real_ubo"  # type: ignore[union-attr]
    assert entry.payload.opt_in_for_retraining is True  # type: ignore[union-attr]

    # Persisted graph reflects the correction.
    factory = async_sessionmaker(engine_with_app, expire_on_commit=False)
    async with factory() as session:
        row = await IntakeRepo.get_one(session, case.id, "ubo_graph")
        assert row is not None
        coastal = next(e for e in row["edges"] if e["from_id"] == COASTAL_ID and e["kind"] == "owns")
        assert coastal["nominee_flag"] == "officer_corrected"


async def test_removed_tag_strips_edge(engine_with_app: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    case = await _seed(engine_with_app)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/v1/cases/{case.id}/ubo/learning-events",
            json=_payload(from_id=ANCHOR_ID, correction_tag="removed"),
            headers=HEADERS_ANALYST,
        )
    assert resp.status_code == 201
    factory = async_sessionmaker(engine_with_app, expire_on_commit=False)
    async with factory() as session:
        row = await IntakeRepo.get_one(session, case.id, "ubo_graph")
        assert row is not None
        anchor_edges = [e for e in row["edges"] if e["from_id"] == ANCHOR_ID and e["kind"] == "owns"]
        assert anchor_edges == []


# ───────────── error paths ─────────────


async def test_404_when_case_missing(engine_with_app: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/v1/cases/{VORA_CAPITAL_ID}/ubo/learning-events",
            json=_payload(),
            headers=HEADERS_ANALYST,
        )
    assert resp.status_code == 404


async def test_409_when_ubo_graph_not_built(engine_with_app: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    case = await _seed(engine_with_app, with_ubo=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/v1/cases/{case.id}/ubo/learning-events",
            json=_payload(),
            headers=HEADERS_ANALYST,
        )
    assert resp.status_code == 409
    assert "UBO graph not built" in resp.json()["detail"]


async def test_422_when_edge_not_in_graph(engine_with_app: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    case = await _seed(engine_with_app)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/v1/cases/{case.id}/ubo/learning-events",
            json=_payload(from_id="ubo_p_nonexistent"),
            headers=HEADERS_ANALYST,
        )
    assert resp.status_code == 422


async def test_422_when_new_target_not_in_graph(engine_with_app: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    case = await _seed(engine_with_app)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/v1/cases/{case.id}/ubo/learning-events",
            json=_payload(new_to_id="ubo_e_nonexistent"),
            headers=HEADERS_ANALYST,
        )
    assert resp.status_code == 422


async def test_422_empty_evidence_note(engine_with_app: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    case = await _seed(engine_with_app)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/v1/cases/{case.id}/ubo/learning-events",
            json=_payload(evidence_note=""),
            headers=HEADERS_ANALYST,
        )
    assert resp.status_code == 422


async def test_422_evidence_note_too_long(engine_with_app: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    case = await _seed(engine_with_app)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/v1/cases/{case.id}/ubo/learning-events",
            json=_payload(evidence_note="x" * 501),
            headers=HEADERS_ANALYST,
        )
    assert resp.status_code == 422


# ───────────── identity ─────────────


async def test_actor_id_records_x_cockpit_demo_user(engine_with_app: AsyncEngine, tmp_writer: LedgerWriter) -> None:
    """team_lead is allowed to drag-correct (no role gate in this story)."""
    case = await _seed(engine_with_app)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/v1/cases/{case.id}/ubo/learning-events",
            json=_payload(),
            headers=HEADERS_LEAD,
        )
    assert resp.status_code == 201
    entries = await LedgerReader(tmp_writer._path).read_all()
    entry = next(e for e in entries if e.action == "ubo.edge_corrected")
    assert entry.actor_id == TEAM_LEAD_ID


async def test_400_when_x_cockpit_demo_user_header_missing(
    engine_with_app: AsyncEngine, tmp_writer: LedgerWriter
) -> None:
    """get_current_user dependency raises 400 when header is absent."""
    case = await _seed(engine_with_app)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/v1/cases/{case.id}/ubo/learning-events",
            json=_payload(),
            headers={"Content-Type": "application/json"},
        )
    assert resp.status_code == 400
