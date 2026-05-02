"""Tests for the document upload router — Story 3.8 / AC #10."""

from __future__ import annotations

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
from cockpit_api.services import document_storage

HEADERS = {"X-Cockpit-Demo-User": ANALYST_ID}

_PDF_HEAD = b"%PDF-1.4\n"
_TINY_PDF = _PDF_HEAD + b"...minimal pdf body...\n%%EOF"


@pytest_asyncio.fixture
async def engine_with_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(eng, expire_on_commit=False)
    monkeypatch.setattr(session_mod, "_engine", eng)
    monkeypatch.setattr(session_mod, "_sessionmaker", factory)

    # Redirect uploads to a tmp dir so tests don't pollute ./fixtures/uploads.
    monkeypatch.setattr(document_storage, "_uploads_root", lambda: tmp_path / "uploads")

    try:
        yield eng
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


# ───────────── upload happy path ─────────────


async def test_upload_persists_file_and_updates_document_refs(
    engine_with_app: AsyncEngine,
) -> None:
    case = await _seed_case(engine_with_app)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/v1/cases/{case.id}/documents",
            headers=HEADERS,
            files={
                "files": ("custom_doc.pdf", _TINY_PDF, "application/pdf"),
            },
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["case_id"] == case.id
    assert len(body["uploaded"]) == 1
    assert body["uploaded"][0]["filename"] == "custom_doc.pdf"
    assert body["uploaded"][0]["size_bytes"] == len(_TINY_PDF)
    assert "custom_doc.pdf" in body["document_refs"]


async def test_upload_rejects_oversized_file(
    engine_with_app: AsyncEngine,
) -> None:
    case = await _seed_case(engine_with_app)
    big = _PDF_HEAD + (b"\0" * (11 * 1024 * 1024))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/v1/cases/{case.id}/documents",
            headers=HEADERS,
            files={"files": ("big.pdf", big, "application/pdf")},
        )
    assert resp.status_code == 413


async def test_upload_rejects_non_pdf(engine_with_app: AsyncEngine) -> None:
    case = await _seed_case(engine_with_app)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/v1/cases/{case.id}/documents",
            headers=HEADERS,
            files={"files": ("not_a_pdf.pdf", b"PNG\x89...", "application/pdf")},
        )
    assert resp.status_code == 415


async def test_upload_rejects_path_traversal_filename(
    engine_with_app: AsyncEngine,
) -> None:
    case = await _seed_case(engine_with_app)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/v1/cases/{case.id}/documents",
            headers=HEADERS,
            files={
                "files": ("../etc/passwd.pdf", _TINY_PDF, "application/pdf"),
            },
        )
    assert resp.status_code == 400


async def test_upload_multi_file_round_trip(engine_with_app: AsyncEngine) -> None:
    case = await _seed_case(engine_with_app)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/v1/cases/{case.id}/documents",
            headers=HEADERS,
            files=[
                ("files", ("a.pdf", _TINY_PDF, "application/pdf")),
                ("files", ("b.pdf", _TINY_PDF, "application/pdf")),
            ],
        )
    assert resp.status_code == 200
    body = resp.json()
    assert {u["filename"] for u in body["uploaded"]} == {"a.pdf", "b.pdf"}
    assert "a.pdf" in body["document_refs"]
    assert "b.pdf" in body["document_refs"]


# ───────────── list ─────────────


async def test_list_returns_uploaded_files(
    engine_with_app: AsyncEngine,
) -> None:
    case = await _seed_case(engine_with_app)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            f"/v1/cases/{case.id}/documents",
            headers=HEADERS,
            files={"files": ("alpha.pdf", _TINY_PDF, "application/pdf")},
        )
        resp = await client.get(f"/v1/cases/{case.id}/documents", headers=HEADERS)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(item["filename"] == "alpha.pdf" for item in items)


# ───────────── delete ─────────────


async def test_delete_removes_file_and_document_ref(
    engine_with_app: AsyncEngine,
) -> None:
    case = await _seed_case(engine_with_app)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            f"/v1/cases/{case.id}/documents",
            headers=HEADERS,
            files={"files": ("delete_me.pdf", _TINY_PDF, "application/pdf")},
        )
        resp_del = await client.delete(f"/v1/cases/{case.id}/documents/delete_me.pdf", headers=HEADERS)
    assert resp_del.status_code == 204

    factory = async_sessionmaker(engine_with_app, expire_on_commit=False)
    async with factory() as session:
        refreshed = await CaseRepo.get(session, case.id)
        assert refreshed is not None
        assert "delete_me.pdf" not in (refreshed.customer_metadata.extra.get("document_refs") or [])


async def test_delete_404_when_missing(engine_with_app: AsyncEngine) -> None:
    case = await _seed_case(engine_with_app)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete(
            f"/v1/cases/{case.id}/documents/never_uploaded.pdf",
            headers=HEADERS,
        )
    assert resp.status_code == 404
