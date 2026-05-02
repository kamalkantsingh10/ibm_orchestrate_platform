"""``IntakeRepo`` — Story 3.5.

Owns reads + writes against the ``intake_results`` table. Stores the full
typed agent output as a JSON blob keyed by ``(case_id, agent_id)``.
Consumers re-validate the blob into the typed contract at the API boundary
(Story 3.6's GET endpoint).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from cockpit_api.db.models import IntakeRow


class IntakeRepo:
    """Repository for the ``intake_results`` table."""

    @staticmethod
    async def upsert(
        session: AsyncSession,
        case_id: str,
        agent_id: str,
        output: BaseModel,
    ) -> None:
        """INSERT OR REPLACE — re-running intake for a case overwrites prior rows.

        Serializes the Pydantic output via ``model_dump(mode="json")`` so
        nested datetimes/enums/ULIDs land as their wire-format strings.
        """
        payload: dict[str, Any] = output.model_dump(mode="json")
        stmt = sqlite_insert(IntakeRow).values(
            case_id=case_id,
            agent_id=agent_id,
            output_json=payload,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["case_id", "agent_id"],
            set_={"output_json": payload},
        )
        await session.execute(stmt)
        await session.flush()

    @staticmethod
    async def get_one(session: AsyncSession, case_id: str, agent_id: str) -> dict[str, Any] | None:
        """Return the stored output dict, or ``None`` if no row matches."""
        row = await session.get(IntakeRow, {"case_id": case_id, "agent_id": agent_id})
        return dict(row.output_json) if row is not None else None

    @staticmethod
    async def get_by_case(session: AsyncSession, case_id: str) -> dict[str, dict[str, Any]]:
        """Return ``{agent_id: output_json}`` for every row matching ``case_id``."""
        stmt = select(IntakeRow).where(IntakeRow.case_id == case_id)
        result = await session.execute(stmt)
        return {row.agent_id: dict(row.output_json) for row in result.scalars().all()}
