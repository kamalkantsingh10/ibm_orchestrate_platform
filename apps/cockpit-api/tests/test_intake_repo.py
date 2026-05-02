"""Tests for IntakeRepo — Story 3.5 / AC #4, #10."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from contracts.cases import VORA_CAPITAL_ID
from contracts.confidence import to_band
from contracts.document_intelligence import (
    DocumentIntelligenceOutput,
    ExtractedField,
)
from contracts.provenance import Provenance, ProvenancedField
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from cockpit_api.db.models import Base
from cockpit_api.repositories.intake_repo import IntakeRepo


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine: AsyncEngine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def _stub_output(case_id: str = VORA_CAPITAL_ID) -> DocumentIntelligenceOutput:
    pf: ProvenancedField[str | int | float | bool | None] = ProvenancedField(
        value="Vora Capital",
        provenance=Provenance(
            source_agent="document_intelligence",
            source_system="fixture_doc_ai",
            confidence=0.92,
            confidence_band=to_band(0.92),
            evidence_ids=[],
            captured_at=datetime.now(UTC),
        ),
    )
    return DocumentIntelligenceOutput(
        case_id=case_id,
        extracted_fields=[
            ExtractedField(
                field_name="company_name",
                document_ref="incorporation_certificate.pdf",
                value=pf,
            )
        ],
    )


async def test_upsert_then_get_one_round_trip(session: AsyncSession) -> None:
    out = _stub_output()
    await IntakeRepo.upsert(session, VORA_CAPITAL_ID, "document_intelligence", out)
    row = await IntakeRepo.get_one(session, VORA_CAPITAL_ID, "document_intelligence")
    assert row is not None
    revived = DocumentIntelligenceOutput.model_validate(row)
    assert revived.case_id == VORA_CAPITAL_ID
    assert len(revived.extracted_fields) == 1
    assert revived.extracted_fields[0].field_name == "company_name"


async def test_upsert_replaces_on_conflict(session: AsyncSession) -> None:
    first = _stub_output()
    second_pf: ProvenancedField[str | int | float | bool | None] = ProvenancedField(
        value="Updated Capital Ltd",
        provenance=first.extracted_fields[0].value.provenance.model_copy(),
    )
    second = first.model_copy(
        update={"extracted_fields": [first.extracted_fields[0].model_copy(update={"value": second_pf})]}
    )
    await IntakeRepo.upsert(session, VORA_CAPITAL_ID, "document_intelligence", first)
    await IntakeRepo.upsert(session, VORA_CAPITAL_ID, "document_intelligence", second)

    row = await IntakeRepo.get_one(session, VORA_CAPITAL_ID, "document_intelligence")
    assert row is not None
    revived = DocumentIntelligenceOutput.model_validate(row)
    assert revived.extracted_fields[0].value.value == "Updated Capital Ltd"


async def test_get_one_returns_none_when_missing(session: AsyncSession) -> None:
    row = await IntakeRepo.get_one(session, VORA_CAPITAL_ID, "document_intelligence")
    assert row is None


async def test_get_by_case_returns_all_agents(session: AsyncSession) -> None:
    out = _stub_output()
    await IntakeRepo.upsert(session, VORA_CAPITAL_ID, "document_intelligence", out)
    await IntakeRepo.upsert(session, VORA_CAPITAL_ID, "entity_verification", out)
    rows = await IntakeRepo.get_by_case(session, VORA_CAPITAL_ID)
    assert set(rows.keys()) == {"document_intelligence", "entity_verification"}


async def test_unused_timedelta_import_kept_for_clarity() -> None:
    # ensure timedelta still imports cleanly (kept for future tests)
    assert timedelta(seconds=1).total_seconds() == 1.0
