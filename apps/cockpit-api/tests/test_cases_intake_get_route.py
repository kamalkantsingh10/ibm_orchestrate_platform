"""Tests for GET /v1/cases/{id}/intake/document_intelligence — Story 3.6 / AC #10."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
import pytest_asyncio
from contracts.cases import (
    VORA_CAPITAL_ID,
    Case,
    get_demo_case_fixtures,
)
from contracts.confidence import to_band
from contracts.document_intelligence import (
    DocumentIntelligenceOutput,
    ExtractedField,
)
from contracts.provenance import Provenance, ProvenancedField
from contracts.users import ANALYST_ID
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from ulid import ULID

from cockpit_api.db import session as session_mod
from cockpit_api.db.models import Base
from cockpit_api.main import app
from cockpit_api.repositories.case_repo import CaseRepo
from cockpit_api.repositories.intake_repo import IntakeRepo


@pytest_asyncio.fixture
async def engine_with_app(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[AsyncEngine]:
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


HEADERS = {"X-Cockpit-Demo-User": ANALYST_ID}


async def _seed_case_and_intake(engine: AsyncEngine) -> Case:
    fixtures = get_demo_case_fixtures(datetime.now(UTC))
    target = next(c for c in fixtures if c.id == VORA_CAPITAL_ID)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    pf: ProvenancedField[str | int | float | bool | None] = ProvenancedField(
        value="Vora Capital Holdings Pvt Ltd",
        provenance=Provenance(
            source_agent="document_intelligence",
            source_system="fixture_doc_ai",
            confidence=0.92,
            confidence_band=to_band(0.92),
            evidence_ids=[f"led_{ULID()!s}"],
            captured_at=datetime.now(UTC),
        ),
    )
    output = DocumentIntelligenceOutput(
        case_id=target.id,
        extracted_fields=[
            ExtractedField(
                field_name="company_name",
                document_ref="incorporation_certificate.pdf",
                value=pf,
            )
        ],
    )
    async with factory() as session:
        await CaseRepo.insert(session, target)
        await IntakeRepo.upsert(session, target.id, "document_intelligence", output)
        await session.commit()
    return target


async def test_get_returns_typed_output(
    engine_with_app: AsyncEngine,
) -> None:
    case = await _seed_case_and_intake(engine_with_app)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/v1/cases/{case.id}/intake/document_intelligence", headers=HEADERS)
    assert resp.status_code == 200
    body: dict[str, Any] = resp.json()
    assert body["case_id"] == case.id
    assert len(body["extracted_fields"]) == 1
    f = body["extracted_fields"][0]
    assert f["field_name"] == "company_name"
    assert f["value"]["provenance"]["confidence_band"] == "high"


async def test_get_404_when_case_missing(
    engine_with_app: AsyncEngine,
) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/v1/cases/{VORA_CAPITAL_ID}/intake/document_intelligence",
            headers=HEADERS,
        )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


async def test_get_404_with_distinct_detail_when_intake_not_run(
    engine_with_app: AsyncEngine,
) -> None:
    fixtures = get_demo_case_fixtures(datetime.now(UTC))
    target = next(c for c in fixtures if c.id == VORA_CAPITAL_ID)
    factory = async_sessionmaker(engine_with_app, expire_on_commit=False)
    async with factory() as session:
        await CaseRepo.insert(session, target)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/v1/cases/{target.id}/intake/document_intelligence", headers=HEADERS)
    assert resp.status_code == 404
    assert "intake not yet run" in resp.json()["detail"].lower()


async def test_get_400_without_demo_user_header(
    engine_with_app: AsyncEngine,
) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/v1/cases/{VORA_CAPITAL_ID}/intake/document_intelligence")
    assert resp.status_code == 400


# ───────────── Story 6.2 — GET /intake/screening ─────────────


async def _seed_case_and_screening_intake(engine: AsyncEngine) -> Case:
    """Seed Vora + a hand-rolled ScreeningAgentOutput for endpoint tests."""
    from datetime import date

    from contracts.screening import ScreeningAgentOutput, ScreeningHit

    fixtures = get_demo_case_fixtures(datetime.now(UTC))
    target = next(c for c in fixtures if c.id == VORA_CAPITAL_ID)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    score_pf: ProvenancedField[float] = ProvenancedField(
        value=0.73,
        provenance=Provenance(
            source_agent="screening",
            source_system="screening_mock",
            confidence=0.73,
            confidence_band=to_band(0.73),
            evidence_ids=[f"led_{ULID()!s}"],
            captured_at=datetime.now(UTC),
        ),
    )
    output = ScreeningAgentOutput(
        case_id=target.id,
        subjects_screened=1,
        hits=[
            ScreeningHit(
                hit_id="hit_mock_abc123",
                subject_id="ubo_p_09876544",
                matched_name="Patel R.",
                name_match_score=score_pf,
                date_of_birth=date(1961, 5, 12),
                categories=["sanctions"],
                source_lists=["OFAC SDN"],
            )
        ],
    )
    async with factory() as session:
        await CaseRepo.insert(session, target)
        await IntakeRepo.upsert(session, target.id, "screening", output)
        await session.commit()
    return target


async def test_get_screening_returns_typed_output(
    engine_with_app: AsyncEngine,
) -> None:
    case = await _seed_case_and_screening_intake(engine_with_app)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/v1/cases/{case.id}/intake/screening", headers=HEADERS)
    assert resp.status_code == 200
    body: dict[str, Any] = resp.json()
    assert body["case_id"] == case.id
    assert body["subjects_screened"] == 1
    assert len(body["hits"]) == 1
    hit = body["hits"][0]
    assert hit["matched_name"] == "Patel R."
    assert hit["name_match_score"]["value"] == 0.73
    assert "sanctions" in hit["categories"]


async def test_get_screening_404_when_intake_not_run(
    engine_with_app: AsyncEngine,
) -> None:
    fixtures = get_demo_case_fixtures(datetime.now(UTC))
    target = next(c for c in fixtures if c.id == VORA_CAPITAL_ID)
    factory = async_sessionmaker(engine_with_app, expire_on_commit=False)
    async with factory() as session:
        await CaseRepo.insert(session, target)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/v1/cases/{target.id}/intake/screening", headers=HEADERS)
    assert resp.status_code == 404
    assert "screening intake not yet run" in resp.json()["detail"].lower()


# ───────────── Story 7.3 — GET /intake/writing ─────────────


async def _seed_case_and_writing_intake(engine: AsyncEngine) -> Case:
    """Seed Vora + a hand-rolled DraftedRationale for endpoint tests."""
    from contracts.writing import CitedClaim, DraftedRationale

    fixtures = get_demo_case_fixtures(datetime.now(UTC))
    target = next(c for c in fixtures if c.id == VORA_CAPITAL_ID)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    led_id = f"led_{ULID()!s}"
    output = DraftedRationale(
        case_id=target.id,
        html=(f'<p>Approve based on <span data-ledger-id="{led_id}" class="citation-token">screening</span>.</p>'),
        paragraphs=["Approve based on screening.", "No open hits."],
        cited_claims=[CitedClaim(text="screening", evidence_ledger_id=led_id)],
        model_id="fixture-writing-v1",
    )
    async with factory() as session:
        await CaseRepo.insert(session, target)
        await IntakeRepo.upsert(session, target.id, "writing", output)
        await session.commit()
    return target


async def test_get_writing_returns_drafted_rationale(
    engine_with_app: AsyncEngine,
) -> None:
    case = await _seed_case_and_writing_intake(engine_with_app)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/v1/cases/{case.id}/intake/writing", headers=HEADERS)
    assert resp.status_code == 200
    body: dict[str, Any] = resp.json()
    assert body["case_id"] == case.id
    assert body["html"].startswith("<p>")
    assert "data-ledger-id=" in body["html"]
    assert 2 <= len(body["paragraphs"]) <= 4
    assert body["model_id"] == "fixture-writing-v1"


async def test_get_writing_404_when_writing_not_run(
    engine_with_app: AsyncEngine,
) -> None:
    fixtures = get_demo_case_fixtures(datetime.now(UTC))
    target = next(c for c in fixtures if c.id == VORA_CAPITAL_ID)
    factory = async_sessionmaker(engine_with_app, expire_on_commit=False)
    async with factory() as session:
        await CaseRepo.insert(session, target)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/v1/cases/{target.id}/intake/writing", headers=HEADERS)
    assert resp.status_code == 404
    assert "writing agent has not yet run" in resp.json()["detail"].lower()
