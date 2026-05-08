"""Tests for the in-process decision undo timer — Story 7.4 / AC #6, #11."""

from __future__ import annotations

import asyncio

import pytest
from contracts.cases import ANANYA_IYER_ID, VORA_CAPITAL_ID

from cockpit_api.services.decision_timer import DecisionTimerService


def _make_seal_recorder() -> tuple[list[tuple[str, str]], asyncio.Event]:
    calls: list[tuple[str, str]] = []
    fired = asyncio.Event()

    async def on_seal(case_id: str, decision_id: str) -> None:
        calls.append((case_id, decision_id))
        fired.set()

    return calls, fired, on_seal  # type: ignore[return-value]


# ───────────── happy path ─────────────


async def test_schedule_then_window_elapses_invokes_on_seal_once() -> None:
    calls: list[tuple[str, str]] = []

    async def on_seal(case_id: str, decision_id: str) -> None:
        calls.append((case_id, decision_id))

    timer = DecisionTimerService(on_seal=on_seal, window_seconds=0.1)
    timer.schedule(VORA_CAPITAL_ID, "dec_test_1")
    await asyncio.sleep(0.25)
    assert calls == [(VORA_CAPITAL_ID, "dec_test_1")]
    # Slot cleared after seal.
    assert timer.remaining_seconds(VORA_CAPITAL_ID) is None


async def test_cancel_returns_true_when_active_and_blocks_seal() -> None:
    calls: list[tuple[str, str]] = []

    async def on_seal(case_id: str, decision_id: str) -> None:
        calls.append((case_id, decision_id))

    timer = DecisionTimerService(on_seal=on_seal, window_seconds=0.5)
    timer.schedule(VORA_CAPITAL_ID, "dec_test_1")
    assert timer.cancel(VORA_CAPITAL_ID) is True
    await asyncio.sleep(0.6)
    assert calls == []


async def test_cancel_returns_false_when_no_active_timer() -> None:
    timer = DecisionTimerService(on_seal=_noop_seal, window_seconds=0.5)
    assert timer.cancel(VORA_CAPITAL_ID) is False


async def test_remaining_seconds_lifecycle() -> None:
    timer = DecisionTimerService(on_seal=_noop_seal, window_seconds=0.5)
    assert timer.remaining_seconds(VORA_CAPITAL_ID) is None
    timer.schedule(VORA_CAPITAL_ID, "dec_test_1")
    initial = timer.remaining_seconds(VORA_CAPITAL_ID)
    assert initial is not None and 0.0 <= initial <= 0.5
    await asyncio.sleep(0.55)
    assert timer.remaining_seconds(VORA_CAPITAL_ID) is None


async def test_schedule_twice_on_same_case_replaces_prior_timer() -> None:
    calls: list[tuple[str, str]] = []

    async def on_seal(case_id: str, decision_id: str) -> None:
        calls.append((case_id, decision_id))

    timer = DecisionTimerService(on_seal=on_seal, window_seconds=0.2)
    timer.schedule(VORA_CAPITAL_ID, "dec_first")
    timer.schedule(VORA_CAPITAL_ID, "dec_second")
    await asyncio.sleep(0.4)
    assert calls == [(VORA_CAPITAL_ID, "dec_second")]


async def test_shutdown_cancels_all_pending_timers() -> None:
    calls: list[tuple[str, str]] = []

    async def on_seal(case_id: str, decision_id: str) -> None:
        calls.append((case_id, decision_id))

    timer = DecisionTimerService(on_seal=on_seal, window_seconds=0.5)
    timer.schedule(VORA_CAPITAL_ID, "dec_a")
    timer.schedule(ANANYA_IYER_ID, "dec_b")
    await timer.shutdown()
    await asyncio.sleep(0.6)
    assert calls == []
    assert timer.remaining_seconds(VORA_CAPITAL_ID) is None
    assert timer.remaining_seconds(ANANYA_IYER_ID) is None


async def test_on_seal_failure_logged_but_does_not_crash_loop(
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls: list[tuple[str, str]] = []

    async def boom(case_id: str, decision_id: str) -> None:
        raise RuntimeError("kaboom")

    async def ok(case_id: str, decision_id: str) -> None:
        calls.append((case_id, decision_id))

    boomy = DecisionTimerService(on_seal=boom, window_seconds=0.1)
    boomy.schedule(VORA_CAPITAL_ID, "dec_boom")
    await asyncio.sleep(0.25)
    assert "decision_timer.seal_callback_failed" in caplog.text

    # A subsequent service still works.
    ok_timer = DecisionTimerService(on_seal=ok, window_seconds=0.1)
    ok_timer.schedule(ANANYA_IYER_ID, "dec_ok")
    await asyncio.sleep(0.25)
    assert calls == [(ANANYA_IYER_ID, "dec_ok")]


async def test_concurrent_timers_for_different_cases_both_fire() -> None:
    calls: list[tuple[str, str]] = []

    async def on_seal(case_id: str, decision_id: str) -> None:
        calls.append((case_id, decision_id))

    timer = DecisionTimerService(on_seal=on_seal, window_seconds=0.1)
    timer.schedule(VORA_CAPITAL_ID, "dec_a")
    timer.schedule(ANANYA_IYER_ID, "dec_b")
    await asyncio.sleep(0.25)
    assert sorted(calls) == sorted([(VORA_CAPITAL_ID, "dec_a"), (ANANYA_IYER_ID, "dec_b")])


async def test_window_seconds_zero_seals_on_next_loop_tick() -> None:
    calls: list[tuple[str, str]] = []

    async def on_seal(case_id: str, decision_id: str) -> None:
        calls.append((case_id, decision_id))

    timer = DecisionTimerService(on_seal=on_seal, window_seconds=0.0)
    timer.schedule(VORA_CAPITAL_ID, "dec_immediate")
    # Yield control once so the timer task gets to run.
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert calls == [(VORA_CAPITAL_ID, "dec_immediate")]


# ───────────── synthetic integration (AC #11) ─────────────


async def test_seal_callback_records_case_decision_pair() -> None:
    """AC11 — synthetic shape that Story 7.7 will replace with the real
    ``seal_decision`` callback. Asserts the timer reaches the callback
    with the right (case_id, decision_id) pair."""
    seal_calls: list[tuple[str, str]] = []

    async def fake_on_seal(case_id: str, decision_id: str) -> None:
        seal_calls.append((case_id, decision_id))

    timer = DecisionTimerService(on_seal=fake_on_seal, window_seconds=0.1)
    timer.schedule(VORA_CAPITAL_ID, "dec_test_123")
    await asyncio.sleep(0.25)
    assert seal_calls == [(VORA_CAPITAL_ID, "dec_test_123")]


async def _noop_seal(case_id: str, decision_id: str) -> None:
    """Module-scope stub for tests that exercise non-callback code paths."""
    return None
