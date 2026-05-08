"""SseRegistry unit tests — Story 4.6 AC #11."""

from __future__ import annotations

import asyncio

import pytest
from contracts.sse import SseEvent

from cockpit_api.services.sse_registry import SseRegistry


@pytest.fixture
def registry() -> SseRegistry:
    return SseRegistry()


def _ev(state: str = "complete") -> SseEvent:
    return SseEvent(event="agent.state_changed", data={"state": state})


async def test_publish_with_no_subscribers_is_a_noop(registry: SseRegistry) -> None:
    await registry.publish("case_X", _ev())
    assert registry.subscriber_count("case_X") == 0


async def test_subscriber_receives_published_events(registry: SseRegistry) -> None:
    queue, unsubscribe = registry.subscribe("case_X")
    try:
        assert registry.subscriber_count("case_X") == 1
        await registry.publish("case_X", _ev("complete"))
        await registry.publish("case_X", _ev("blocked"))
        first = await asyncio.wait_for(queue.get(), 1.0)
        second = await asyncio.wait_for(queue.get(), 1.0)
        assert [first.data["state"], second.data["state"]] == ["complete", "blocked"]
    finally:
        unsubscribe()
    assert registry.subscriber_count("case_X") == 0


async def test_two_subscribers_each_receive_the_event(registry: SseRegistry) -> None:
    a_q, a_un = registry.subscribe("case_X")
    b_q, b_un = registry.subscribe("case_X")
    try:
        await registry.publish("case_X", _ev())
        await asyncio.wait_for(a_q.get(), 1.0)
        await asyncio.wait_for(b_q.get(), 1.0)
    finally:
        a_un()
        b_un()


async def test_publish_to_other_case_does_not_reach_subscriber(
    registry: SseRegistry,
) -> None:
    queue, unsubscribe = registry.subscribe("case_X")
    try:
        await registry.publish("case_OTHER", _ev())
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), 0.05)
    finally:
        unsubscribe()


async def test_unsubscribe_removes_the_queue(registry: SseRegistry) -> None:
    _, unsubscribe = registry.subscribe("case_X")
    assert registry.subscriber_count("case_X") == 1
    unsubscribe()
    assert registry.subscriber_count("case_X") == 0


async def test_unsubscribe_is_safe_to_call_twice(registry: SseRegistry) -> None:
    _, unsubscribe = registry.subscribe("case_X")
    unsubscribe()
    unsubscribe()  # should not raise
    assert registry.subscriber_count("case_X") == 0
