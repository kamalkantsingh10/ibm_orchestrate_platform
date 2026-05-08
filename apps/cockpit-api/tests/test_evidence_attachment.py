"""Tests for Story 8.6 — SHA-256 hashing + `case.evidence_attached`
ledger entry on evidence uploads."""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from contracts.cases import (
    VORA_CAPITAL_ID,
    Case,
    get_demo_case_fixtures,
)
from contracts.ledger import EvidenceAttachedPayload
from contracts.users import ANALYST_ID
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
from cockpit_api.services import document_storage, ledger_service
from cockpit_api.services.ledger_service import LedgerReader, LedgerWriter

HEADERS = {"X-Cockpit-Demo-User": ANALYST_ID}

_PDF_HEAD = b"%PDF-1.4\n"
_TINY_PDF = _PDF_HEAD + b"...minimal pdf body...\n%%EOF"


@pytest_asyncio.fixture
async def engine_with_app(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> AsyncIterator[tuple[AsyncEngine, LedgerWriter]]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(eng, expire_on_commit=False)
    monkeypatch.setattr(session_mod, "_engine", eng)
    monkeypatch.setattr(session_mod, "_sessionmaker", factory)

    monkeypatch.setattr(document_storage, "_uploads_root", lambda: tmp_path / "uploads")

    ledger_path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(ledger_path)
    reader = LedgerReader(ledger_path)
    ledger_service.get_ledger_writer.cache_clear()
    ledger_service.get_ledger_reader.cache_clear()
    monkeypatch.setattr(ledger_service, "get_ledger_writer", lambda: writer)
    monkeypatch.setattr(ledger_service, "get_ledger_reader", lambda: reader)

    try:
        yield eng, writer
    finally:
        await eng.dispose()


async def _seed_case(engine: AsyncEngine) -> Case:
    fixtures = get_demo_case_fixtures(datetime.now(UTC))
    target = next(c for c in fixtures if c.id == VORA_CAPITAL_ID)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await CaseRepo.insert(session, target)
        await session.commit()
    return target


# ─── AC #1, #5 — sha256 computed on upload ───────────────────────────────────


async def test_sha256_computed_on_upload_matches_known_fixture_hash(
    engine_with_app: tuple[AsyncEngine, LedgerWriter],
) -> None:
    engine, _writer = engine_with_app
    case = await _seed_case(engine)
    body = b"plain text body"
    expected = hashlib.sha256(body).hexdigest()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/v1/cases/{case.id}/documents",
            params={"kind": "evidence"},
            headers=HEADERS,
            files={"files": ("note.txt", body, "text/plain")},
        )
    assert resp.status_code == 200, resp.text
    uploaded = resp.json()["uploaded"][0]
    assert uploaded["sha256"] == expected


async def test_intake_pdf_upload_also_carries_sha256(
    engine_with_app: tuple[AsyncEngine, LedgerWriter],
) -> None:
    engine, _writer = engine_with_app
    case = await _seed_case(engine)
    expected = hashlib.sha256(_TINY_PDF).hexdigest()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/v1/cases/{case.id}/documents",
            headers=HEADERS,
            files={"files": ("intake.pdf", _TINY_PDF, "application/pdf")},
        )
    assert resp.status_code == 200, resp.text
    uploaded = resp.json()["uploaded"][0]
    assert uploaded["sha256"] == expected


# ─── AC #2 — case.evidence_attached ledger entry ─────────────────────────────


async def test_evidence_upload_appends_case_evidence_attached_ledger_entry(
    engine_with_app: tuple[AsyncEngine, LedgerWriter],
) -> None:
    engine, writer = engine_with_app
    case = await _seed_case(engine)
    body = b"some evidence body"
    expected = hashlib.sha256(body).hexdigest()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/v1/cases/{case.id}/documents",
            params={"kind": "evidence", "ingest_method": "drop"},
            headers=HEADERS,
            files={"files": ("evidence.txt", body, "text/plain")},
        )
    assert resp.status_code == 200, resp.text

    reader = LedgerReader(writer._path)
    entries = await reader.read_for_case(case.id)
    attachments = [e for e in entries if e.action == "case.evidence_attached"]
    assert len(attachments) == 1
    payload = attachments[0].payload
    assert isinstance(payload, EvidenceAttachedPayload)
    assert payload.filename == "evidence.txt"
    assert payload.sha256 == expected
    assert payload.size_bytes == len(body)
    assert payload.ingest_method == "drop"


async def test_intake_upload_does_not_append_evidence_ledger_entry(
    engine_with_app: tuple[AsyncEngine, LedgerWriter],
) -> None:
    engine, writer = engine_with_app
    case = await _seed_case(engine)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/v1/cases/{case.id}/documents",
            headers=HEADERS,
            files={"files": ("intake.pdf", _TINY_PDF, "application/pdf")},
        )
    assert resp.status_code == 200, resp.text

    reader = LedgerReader(writer._path)
    entries = await reader.read_all()
    assert all(e.action != "case.evidence_attached" for e in entries)


async def test_evidence_ledger_entry_carries_user_id_from_request_context(
    engine_with_app: tuple[AsyncEngine, LedgerWriter],
) -> None:
    engine, writer = engine_with_app
    case = await _seed_case(engine)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/v1/cases/{case.id}/documents",
            params={"kind": "evidence"},
            headers=HEADERS,
            files={"files": ("note.txt", b"body", "text/plain")},
        )
    assert resp.status_code == 200, resp.text

    reader = LedgerReader(writer._path)
    entries = await reader.read_for_case(case.id)
    attachments = [e for e in entries if e.action == "case.evidence_attached"]
    assert len(attachments) == 1
    assert attachments[0].actor_id == ANALYST_ID
    assert attachments[0].actor_type.value == "officer"


async def test_evidence_ingest_method_defaults_to_unspecified(
    engine_with_app: tuple[AsyncEngine, LedgerWriter],
) -> None:
    engine, writer = engine_with_app
    case = await _seed_case(engine)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/v1/cases/{case.id}/documents",
            params={"kind": "evidence"},
            headers=HEADERS,
            files={"files": ("note.txt", b"body", "text/plain")},
        )
    assert resp.status_code == 200, resp.text

    reader = LedgerReader(writer._path)
    entries = await reader.read_for_case(case.id)
    payload = next(e.payload for e in entries if e.action == "case.evidence_attached")
    assert isinstance(payload, EvidenceAttachedPayload)
    assert payload.ingest_method == "unspecified"
