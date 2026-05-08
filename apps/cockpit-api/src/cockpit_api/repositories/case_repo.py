"""``CaseRepo`` — Story 2.1.

Owns every read and write against the ``cases`` table. Wire types are the
``Case`` Pydantic contract; the ``CaseRow`` ORM class never leaves this module.
"""

from __future__ import annotations

from datetime import UTC, datetime

from contracts.cases import (
    Case,
    CaseState,
    CustomerMetadata,
    assert_transition,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cockpit_api.db.models import CaseRow


def _ensure_utc(value: datetime | None) -> datetime | None:
    """Re-attach UTC tzinfo if SQLite stripped it on round-trip.

    SQLite's ``DATETIME`` is timezone-naive; Postgres' ``timestamptz`` is not.
    The contract guarantees UTC ISO-8601 on the wire, so we normalise here.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _to_contract(row: CaseRow) -> Case:
    """Translate an ORM row into the Pydantic contract."""
    created_at = _ensure_utc(row.created_at)
    updated_at = _ensure_utc(row.updated_at)
    assert created_at is not None  # NOT NULL columns
    assert updated_at is not None
    return Case(
        id=row.id,
        state=CaseState(row.state),
        customer_metadata=CustomerMetadata.model_validate(row.customer_metadata),
        assigned_to_user_id=row.assigned_to_user_id,
        risk_band=row.risk_band,  # type: ignore[arg-type]
        created_at=created_at,
        updated_at=updated_at,
        closure_date=_ensure_utc(row.closure_date),
    )


def _to_row(case: Case) -> CaseRow:
    """Translate a Pydantic ``Case`` into an ORM row for INSERT."""
    return CaseRow(
        id=case.id,
        state=case.state.value,
        customer_metadata=case.customer_metadata.model_dump(),
        assigned_to_user_id=case.assigned_to_user_id,
        risk_band=case.risk_band,
        created_at=case.created_at,
        updated_at=case.updated_at,
        closure_date=case.closure_date,
    )


class CaseRepo:
    """Repository for the ``cases`` table.

    Each method takes an explicit ``AsyncSession``; there is no global
    session. Callers (FastAPI dependencies) are responsible for the
    session lifecycle.
    """

    @staticmethod
    async def get(session: AsyncSession, case_id: str) -> Case | None:
        """Return the case with ``case_id`` or ``None`` if missing."""
        row = await session.get(CaseRow, case_id)
        return _to_contract(row) if row is not None else None

    @staticmethod
    async def list_all(session: AsyncSession, limit: int = 100) -> list[Case]:
        """Return cases (newest-first by repo convention; service layer owns final ordering).

        Story 4.1 moved Queue Rail ordering into ``case_service.queue_order``.
        This method retains a stable repo-level order (newest first) so callers
        without sort needs see deterministic output, but it is no longer the
        contract — consumers wanting risk × SLA × continuity must go through
        ``case_service.list_cases``.
        """
        stmt = select(CaseRow).order_by(CaseRow.created_at.desc()).limit(limit)
        result = await session.execute(stmt)
        return [_to_contract(row) for row in result.scalars().all()]

    @staticmethod
    async def insert(session: AsyncSession, case: Case) -> None:
        """Insert a contract-validated case row. No UPSERT."""
        session.add(_to_row(case))
        await session.flush()

    @staticmethod
    async def transition(session: AsyncSession, case_id: str, target: CaseState) -> Case:
        """Transition ``case_id`` to ``target`` if the edge is allowed.

        Raises ``CaseStateTransitionError`` if not. Sets ``closure_date`` only
        on the first transition into ``CLOSED``.
        """
        row = await session.get(CaseRow, case_id)
        if row is None:
            raise LookupError(f"Case {case_id!r} not found")

        current = CaseState(row.state)
        assert_transition(current, target)

        row.state = target.value
        if target is CaseState.CLOSED and row.closure_date is None:
            row.closure_date = datetime.now(UTC)

        await session.flush()
        await session.refresh(row)
        return _to_contract(row)

    @staticmethod
    async def update_risk_band(
        session: AsyncSession,
        case_id: str,
        band: str,
    ) -> Case:
        """Denormalize the risk band onto the case row — Story 5.6 / AC #5.

        The 3-tier RiskBand on the wire (``low | medium | high``) is widened
        to the 4-tier ``cases.risk_band`` column (``low | medium_low |
        medium_high | high``) at this boundary: ``medium`` → ``medium_high``
        (keeps Story 4.1's queue-rail risk-driven sort stable). Also bumps
        ``updated_at`` so the queue rail's ``(risk DESC, sla ASC,
        updated_at DESC)`` ordering surfaces the recalc.
        """
        row = await session.get(CaseRow, case_id)
        if row is None:
            raise LookupError(f"Case {case_id!r} not found")
        if band == "low":
            mapped = "low"
        elif band == "medium":
            mapped = "medium_high"
        elif band == "high":
            mapped = "high"
        else:
            raise ValueError(f"unknown risk band {band!r}")
        row.risk_band = mapped
        row.updated_at = datetime.now(UTC)
        await session.flush()
        await session.refresh(row)
        return _to_contract(row)

    @staticmethod
    async def add_document_ref(session: AsyncSession, case_id: str, filename: str) -> Case:
        """Append ``filename`` to ``customer_metadata.extra.document_refs``.

        Story 3.8 § AC2. Idempotent — re-adding the same filename leaves
        the list unchanged. Preserves existing entries and order.
        """
        row = await session.get(CaseRow, case_id)
        if row is None:
            raise LookupError(f"Case {case_id!r} not found")

        metadata = dict(row.customer_metadata or {})
        extra = dict(metadata.get("extra") or {})
        refs = list(extra.get("document_refs") or [])
        if filename not in refs:
            refs.append(filename)
        extra["document_refs"] = refs
        metadata["extra"] = extra
        row.customer_metadata = metadata

        await session.flush()
        await session.refresh(row)
        return _to_contract(row)

    @staticmethod
    async def remove_document_ref(session: AsyncSession, case_id: str, filename: str) -> Case:
        """Remove ``filename`` from ``customer_metadata.extra.document_refs``."""
        row = await session.get(CaseRow, case_id)
        if row is None:
            raise LookupError(f"Case {case_id!r} not found")

        metadata = dict(row.customer_metadata or {})
        extra = dict(metadata.get("extra") or {})
        refs = [f for f in (extra.get("document_refs") or []) if f != filename]
        extra["document_refs"] = refs
        metadata["extra"] = extra
        row.customer_metadata = metadata

        await session.flush()
        await session.refresh(row)
        return _to_contract(row)

    @staticmethod
    async def add_block_marker(
        session: AsyncSession,
        case_id: str,
        blocked_agent: str,
        block_reason: str,
    ) -> Case:
        """Merge ``blocked_agent`` + ``block_reason`` into ``customer_metadata.extra``.

        Story 3.5 § AC2 step 7. Used on the supervisor's blocked-intake path
        so the UI can render which agent failed and why.

        Preserves all existing keys in ``customer_metadata.extra``; only
        overwrites the two new keys.
        """
        row = await session.get(CaseRow, case_id)
        if row is None:
            raise LookupError(f"Case {case_id!r} not found")

        # SQLAlchemy's mutation tracking on ``JSON`` is shallow — assign a
        # new dict to ensure the change is detected and persisted.
        metadata = dict(row.customer_metadata or {})
        extra = dict(metadata.get("extra") or {})
        extra["blocked_agent"] = blocked_agent
        extra["block_reason"] = block_reason[:500]
        metadata["extra"] = extra
        row.customer_metadata = metadata

        await session.flush()
        await session.refresh(row)
        return _to_contract(row)
