"""Case service — Story 2.2.

Thin orchestration over ``CaseRepo``. ``get_case`` raises ``HTTPException(404)``
on missing rows so the router stays free of repo imports and the RFC 7807
handler in ``main.py`` produces the canonical error envelope.
"""

from __future__ import annotations

from contracts.cases import Case
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from cockpit_api.repositories.case_repo import CaseRepo


async def get_case(session: AsyncSession, case_id: str) -> Case:
    case = await CaseRepo.get(session, case_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case {case_id} not found",
        )
    return case


async def list_cases(session: AsyncSession, limit: int = 100) -> list[Case]:
    return await CaseRepo.list_ordered_by_created_at_desc(session, limit=limit)
