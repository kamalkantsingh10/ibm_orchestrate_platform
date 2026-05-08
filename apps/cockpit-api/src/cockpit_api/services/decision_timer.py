"""In-memory 120-second decision undo timer — Story 7.4 (extended in 7.5).

Demo simplification of bank-buyer Story 7.8 (Redis-backed). Process-local
``asyncio.Task`` per pending decision; seals on timer expiry; cancels on
officer undo. Cockpit-api restart loses in-flight timers — acceptable
for the demo per the 2026-04-29 re-scope.

The ``on_seal`` callback is wired by Story 7.7's POST endpoint via the
FastAPI lifespan singleton; this module is concerned only with the
scheduling primitive. Tests construct their own ``DecisionTimerService``
with a stub callback.

Story 7.5 added the ``view(case_id)`` helper so the GET active-timer
route can serialize the timer state (including ``decision_id``) without
exposing the internal ``asyncio.Task``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from contracts.cases import CaseId
from pydantic import BaseModel

logger = logging.getLogger(__name__)

UNDO_WINDOW_SECONDS: int = 120


class DecisionTimerView(BaseModel):
    """Serializable snapshot of a pending decision timer — Story 7.5."""

    model_config = {"frozen": True}

    case_id: CaseId
    decision_id: str
    remaining_seconds: float
    window_seconds: float = float(UNDO_WINDOW_SECONDS)


@dataclass
class _PendingTimer:
    """Per-case timer record. The dataclass is the retention point that
    keeps the asyncio.Task from being GC'd before completion."""

    case_id: CaseId
    decision_id: str
    scheduled_at: float
    seal_at: float
    task: asyncio.Task[None]


class DecisionTimerService:
    """Process-local timer registry. One instance per cockpit-api
    process, constructed in the FastAPI lifespan and consumed by the
    POST decision / undo decision endpoints via dependency injection.
    """

    def __init__(
        self,
        *,
        on_seal: Callable[[CaseId, str], Awaitable[None]],
        window_seconds: float = UNDO_WINDOW_SECONDS,
    ) -> None:
        self._on_seal = on_seal
        self._window = window_seconds
        self._timers: dict[CaseId, _PendingTimer] = {}

    def schedule(self, case_id: CaseId, decision_id: str) -> None:
        """Start a 120s timer. Idempotent: re-scheduling on the same
        case cancels and replaces the prior timer (handles double-click
        Commit). The asyncio.Task is retained on ``self._timers`` so
        Python's GC doesn't collect it before the timer fires.
        """
        existing = self._timers.pop(case_id, None)
        if existing is not None:
            existing.task.cancel()
            logger.info("decision_timer.replaced case=%s", case_id)

        now = time.monotonic()
        seal_at = now + self._window
        task = asyncio.create_task(self._run_timer(case_id, decision_id, seal_at))
        self._timers[case_id] = _PendingTimer(
            case_id=case_id,
            decision_id=decision_id,
            scheduled_at=now,
            seal_at=seal_at,
            task=task,
        )

    def cancel(self, case_id: CaseId) -> bool:
        """Cancel the timer for ``case_id``. Returns ``True`` iff one
        was active and cancelled."""
        existing = self._timers.pop(case_id, None)
        if existing is None:
            return False
        existing.task.cancel()
        return True

    def remaining_seconds(self, case_id: CaseId) -> float | None:
        """Seconds remaining before seal. Returns ``None`` when no
        active timer exists for the case."""
        t = self._timers.get(case_id)
        if t is None:
            return None
        return max(0.0, t.seal_at - time.monotonic())

    def view(self, case_id: CaseId) -> DecisionTimerView | None:
        """Serializable snapshot of the active timer — Story 7.5. Returns
        ``None`` when no timer is active. Mirrors ``remaining_seconds``
        but also exposes the ``decision_id`` so the cockpit-ui can
        confirm-its-decision when invoking ``/undo``."""
        t = self._timers.get(case_id)
        if t is None:
            return None
        return DecisionTimerView(
            case_id=case_id,
            decision_id=t.decision_id,
            remaining_seconds=max(0.0, t.seal_at - time.monotonic()),
            window_seconds=float(self._window),
        )

    async def shutdown(self) -> None:
        """Cancel all pending timers. Called on app shutdown.

        ``on_seal`` is NOT invoked for cancelled timers — pending_seal
        cases stay in that state across restart by design (see story
        pitfall #2).
        """
        for t in list(self._timers.values()):
            t.task.cancel()
        self._timers.clear()

    async def _run_timer(
        self,
        case_id: CaseId,
        decision_id: str,
        seal_at: float,
    ) -> None:
        try:
            wait = max(0.0, seal_at - time.monotonic())
            await asyncio.sleep(wait)
            # Race-safe self-check: ``cancel`` or ``schedule`` may have
            # replaced this slot while we were sleeping. The slot must
            # still hold our decision_id for the seal to fire.
            current = self._timers.get(case_id)
            if current is None or current.decision_id != decision_id:
                return
            self._timers.pop(case_id, None)
            try:
                await self._on_seal(case_id, decision_id)
            except Exception:
                # on_seal failure leaves the case in pending_seal. The
                # demo accepts this; production would queue a retry.
                logger.exception(
                    "decision_timer.seal_callback_failed case=%s decision=%s",
                    case_id,
                    decision_id,
                )
        except asyncio.CancelledError:
            logger.info("decision_timer.cancelled case=%s", case_id)
            raise


__all__ = [
    "UNDO_WINDOW_SECONDS",
    "DecisionTimerService",
    "DecisionTimerView",
]
