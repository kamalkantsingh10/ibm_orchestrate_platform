"""In-process SSE registry — Story 4.6.

Single-worker fan-out: each subscriber gets its own ``asyncio.Queue``;
``publish`` enqueues onto every subscriber for a case. Demo-scope
simplification of architecture.md A2/P6 — the bank-buyer scope's Redis
pub/sub coordinator (cut from demo per ``sprint-change-proposal-2026-04-29``)
is replaced by this in-process broker.

No replay buffer; if a client disconnects, missed events are accepted.
TanStack Query's `staleTime` on the next user interaction backfills.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable
from contextlib import suppress
from functools import lru_cache

from contracts.sse import SseEvent

logger = logging.getLogger(__name__)

# Per-subscriber queue cap — beyond this we drop old events to avoid pinning
# memory if a client stops draining.
_QUEUE_MAXSIZE = 64


class SseRegistry:
    """Per-case fan-out registry.

    Public surface:
    * ``subscribe(case_id) -> (queue, unsubscribe)`` — register a fresh queue
      that receives every published event for ``case_id``. Caller drains the
      queue with ``await queue.get()`` and MUST call ``unsubscribe()`` when
      done so the queue stops accumulating.
    * ``publish(case_id, event)`` — fan-out to all current subscribers.
    """

    def __init__(self) -> None:
        self._queues: dict[str, list[asyncio.Queue[SseEvent]]] = defaultdict(list)

    def subscribe(
        self,
        case_id: str,
    ) -> tuple[asyncio.Queue[SseEvent], Callable[[], None]]:
        """Register a fresh queue for ``case_id``; return the queue + unsubscribe.

        Synchronous because we only need to mutate a local dict; no async I/O.
        """
        queue: asyncio.Queue[SseEvent] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self._queues[case_id].append(queue)

        def _unsubscribe() -> None:
            bucket = self._queues.get(case_id)
            if bucket is None:
                return
            with suppress(ValueError):
                bucket.remove(queue)
            if not bucket:
                self._queues.pop(case_id, None)

        return queue, _unsubscribe

    async def publish(self, case_id: str, event: SseEvent) -> None:
        """Fan-out ``event`` to every subscriber for ``case_id``.

        Best-effort. Drops old events on per-queue overflow rather than
        blocking the publisher — a slow client must not stall an agent run.
        """
        # Snapshot to a local list so concurrent unsubscribe doesn't mutate
        # underneath us. No lock needed — list copy is cheap and dict reads
        # are atomic in CPython.
        queues = list(self._queues.get(case_id, ()))
        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Drop the oldest event to keep the queue draining.
                with suppress(asyncio.QueueEmpty):
                    q.get_nowait()
                with suppress(asyncio.QueueFull):
                    q.put_nowait(event)
                logger.warning(
                    "sse.queue_overflow case_id=%s subscriber dropped an event",
                    case_id,
                )

    def subscriber_count(self, case_id: str) -> int:
        """Snapshot count, mainly for tests."""
        return len(self._queues.get(case_id, ()))


@lru_cache(maxsize=1)
def get_sse_registry() -> SseRegistry:
    """Process-wide singleton."""
    return SseRegistry()


async def publish_safe(case_id: str | None, event: SseEvent) -> None:
    """Best-effort publish — used by producers (decorator, services).

    Swallows registry errors so a failed publish doesn't abort an agent run
    or a state transition. Logs at WARN.
    """
    if not case_id:
        return
    try:
        await get_sse_registry().publish(case_id, event)
    except Exception as exc:  # noqa: BLE001 — best-effort by design
        logger.warning(
            "sse.publish_failed case_id=%s event=%s error=%r",
            case_id,
            event.event,
            exc,
        )
