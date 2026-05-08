"""``DecisionRepo`` — Story 7.7.

Owns reads + writes against the ``decisions`` table. The wire format is
the ``Decision`` Pydantic contract; the repo translates between
SQLAlchemy rows and the typed contract.

Undo (Story 7.5) deletes the row outright — the audit anchor is the
``officer.decision_committed`` + ``officer.decision_undone`` ledger
entries, not a row-level status field. ``delete_by_id`` is the path.
"""

from __future__ import annotations

from datetime import datetime

from contracts.decision import Decision
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from cockpit_api.db.models import DecisionRow


def _row_to_contract(row: DecisionRow) -> Decision:
    return Decision.model_validate(
        {
            "decision_id": row.decision_id,
            "case_id": row.case_id,
            "outcome": row.outcome,
            "conditions": list(row.conditions_json or []),
            "rationale_html": row.rationale_html,
            "committed_by_user_id": row.committed_by_user_id,
            "committed_at": row.committed_at,
            "sealed_at": row.sealed_at,
            "sealed_ledger_entry_id": row.sealed_ledger_entry_id,
            "committed_ledger_entry_id": row.committed_ledger_entry_id,
        }
    )


class DecisionRepo:
    """Repository for the ``decisions`` table."""

    @staticmethod
    async def insert(session: AsyncSession, decision: Decision) -> None:
        row = DecisionRow(
            decision_id=decision.decision_id,
            case_id=decision.case_id,
            outcome=decision.outcome,
            conditions_json=list(decision.conditions),
            rationale_html=decision.rationale_html,
            committed_by_user_id=decision.committed_by_user_id,
            committed_at=decision.committed_at,
            sealed_at=decision.sealed_at,
            sealed_ledger_entry_id=decision.sealed_ledger_entry_id,
            committed_ledger_entry_id=decision.committed_ledger_entry_id,
        )
        session.add(row)
        await session.flush()

    @staticmethod
    async def fetch_by_id(session: AsyncSession, decision_id: str) -> Decision | None:
        row = await session.get(DecisionRow, decision_id)
        return _row_to_contract(row) if row is not None else None

    @staticmethod
    async def fetch_latest_by_case(
        session: AsyncSession,
        case_id: str,
    ) -> Decision | None:
        stmt = (
            select(DecisionRow).where(DecisionRow.case_id == case_id).order_by(DecisionRow.committed_at.desc()).limit(1)
        )
        result = await session.execute(stmt)
        row = result.scalars().first()
        return _row_to_contract(row) if row is not None else None

    @staticmethod
    async def update_sealed(
        session: AsyncSession,
        decision_id: str,
        sealed_at: datetime,
        sealed_ledger_entry_id: str,
    ) -> None:
        row = await session.get(DecisionRow, decision_id)
        if row is None:
            return
        row.sealed_at = sealed_at
        row.sealed_ledger_entry_id = sealed_ledger_entry_id
        await session.flush()

    @staticmethod
    async def delete_by_id(session: AsyncSession, decision_id: str) -> None:
        await session.execute(delete(DecisionRow).where(DecisionRow.decision_id == decision_id))
        await session.flush()
