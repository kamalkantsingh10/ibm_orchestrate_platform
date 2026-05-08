"""Case service — Story 2.2 + Story 4.1.

Thin orchestration over ``CaseRepo``. ``get_case`` raises ``HTTPException(404)``
on missing rows so the router stays free of repo imports and the RFC 7807
handler in ``main.py`` produces the canonical error envelope.

Story 4.1 adds ``queue_order`` — a pure-function helper that sorts cases by
``risk × SLA × continuity × created_at`` for the Queue Rail. ``list_cases``
applies the helper before returning so the cockpit-ui consumes a pre-ordered
list with no client-side sorting.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Final

from contracts.cases import Case
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from cockpit_api.repositories.case_repo import CaseRepo

# Risk DESC: high beats medium_high beats medium_low beats low. ``None`` ranks
# last so unscored cases sink below scored ones — analyst chases scored work
# first. The integer values are private; only the relative order matters.
_RISK_RANK: Final[dict[str | None, int]] = {
    "high": 4,
    "medium_high": 3,
    "medium_low": 2,
    "low": 1,
    None: 0,
}


def _parse_sla_due_at(raw: object) -> datetime | None:
    """Best-effort ``fromisoformat`` parse. Returns ``None`` on any failure.

    Bad fixture data must not 500 the queue. ``Z`` suffix → ``+00:00`` for
    Python ≤ 3.10 compatibility (3.11+ tolerates ``Z`` natively but we still
    normalise for stability).
    """
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _sla_seconds_remaining(case: Case, now: datetime) -> float:
    """Seconds-until-due for the case. ``+inf`` if no SLA is set.

    Smaller is more urgent; ``+inf`` sinks unscoped cases to the bottom of
    the SLA tier. Negative values (overdue) sort to the very top.
    """
    raw = case.customer_metadata.extra.get("sla_due_at")
    due = _parse_sla_due_at(raw)
    if due is None:
        return math.inf
    return (due - now).total_seconds()


def queue_order(
    cases: list[Case],
    *,
    current_user_id: str | None,
    now: datetime,
) -> list[Case]:
    """Return ``cases`` sorted by (risk DESC, sla ASC, continuity DESC, created_at DESC).

    Pure function — no DB access, no side effects, deterministic for fixed
    inputs. ``now`` is injected so unit tests don't depend on the wall clock.

    Tiebreak by ``created_at DESC`` (newest first) is built into the sort key
    so equal-priority cases still order deterministically.

    Continuity for the demo is single-axis: a case scores ``+1`` if its
    ``assigned_to_user_id`` matches ``current_user_id``. Pass ``None`` to skip
    the continuity dimension entirely (e.g. when the agent runtime calls
    ``GET /v1/cases`` as a tool with no demo-user header).
    """

    def key(case: Case) -> tuple[int, float, int, float]:
        risk_rank = _RISK_RANK.get(case.risk_band, 0)
        sla_remaining = _sla_seconds_remaining(case, now)
        continuity = 1 if current_user_id is not None and case.assigned_to_user_id == current_user_id else 0
        # Negative timestamp so DESC reads naturally with default ascending sort.
        # ``-created_at.timestamp()`` keeps newer cases ahead in the ordering.
        return (
            -risk_rank,  # risk DESC
            sla_remaining,  # sla ASC
            -continuity,  # continuity DESC
            -case.created_at.timestamp(),  # created_at DESC
        )

    return sorted(cases, key=key)


async def get_case(session: AsyncSession, case_id: str) -> Case:
    case = await CaseRepo.get(session, case_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case {case_id} not found",
        )
    return case


async def list_cases(
    session: AsyncSession,
    *,
    current_user_id: str | None = None,
    now: datetime | None = None,
    limit: int = 100,
) -> list[Case]:
    """Return cases sorted for the Queue Rail.

    ``current_user_id`` is optional so the case_supervisor agent's tool path
    (no demo-user header) still works — it just doesn't get the continuity
    boost. ``now`` defaults to the current UTC instant; tests can pin it.
    """
    cases = await CaseRepo.list_all(session, limit=limit)
    return queue_order(
        cases,
        current_user_id=current_user_id,
        now=now or datetime.now(UTC),
    )
