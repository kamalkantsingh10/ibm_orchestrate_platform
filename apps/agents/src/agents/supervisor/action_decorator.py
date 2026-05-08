"""@agent_action decorator and AgentExecutionError — Story 3.2 / Story 3.4 § AC9.

This module is the only sanctioned path from agent code to the ledger.
Direct ``LedgerWriter.append`` calls inside ``apps/agents/`` outside this
file violate P4 (Agent Action Pattern). See architecture.md § P4 and the
demo-scope simplification in Story 3-2.

The decorator wraps async agent functions and:

* records ``agent.completed`` ledger entries on success with a typed
  ``AgentActionLedgerEntry`` payload (input, output, model_id, duration_ms,
  …);
* records ``agent.failed`` entries on exception and re-raises a typed
  ``AgentExecutionError`` so Story 3-5's supervisor can detect and surface
  blocked-intake state per FR55;
* allows agents to override ``model_id`` and ``prompt_hash`` at call time
  via the module-level ``ContextVar`` setters (Story 3.4 AC9). This lets a
  doc-AI adapter that doesn't know its model ID until the request is built
  surface the right value into the ledger entry.
"""

from __future__ import annotations

import functools
import inspect
import logging
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import ParamSpec, TypeVar

from cockpit_api.services.ledger_service import get_ledger_writer
from cockpit_api.services.sse_registry import publish_safe
from contracts.agent_action import AgentActionLedgerEntry, ErrorInfo
from contracts.cases import CaseId
from contracts.ledger import ActorType, LedgerEntry
from contracts.reasoning_trace import (
    IncompleteReasoningTraceError,
    ReasoningTrace,
)
from contracts.sse import SseEvent
from pydantic import BaseModel, ValidationError
from ulid import ULID

logger = logging.getLogger(__name__)

P = ParamSpec("P")
OutputT = TypeVar("OutputT", bound=BaseModel)


# ───────────────────────────── runtime overrides ──────────────────────────
#
# Story 3.4 AC9 — agents that resolve their LLM client at call time can set
# the runtime model_id and prompt_hash here. The decorator reads them after
# the wrapped function returns and substitutes them into the ledger entry.
# ContextVars are per-task in Python 3.11+ — concurrent agent calls do not
# cross-pollute.

_runtime_model_id: ContextVar[str | None] = ContextVar("agent_action_model_id", default=None)
_runtime_prompt_hash: ContextVar[str | None] = ContextVar("agent_action_prompt_hash", default=None)
# Story 6.4 — task-local 4-section reasoning trace. ContextVars are
# per-task in Python 3.11+ so concurrent agent invocations don't
# cross-pollute. Wrapper resets to None before/after each call.
_runtime_reasoning_trace: ContextVar[ReasoningTrace | None] = ContextVar("agent_action_reasoning_trace", default=None)


def set_runtime_model_id(model_id: str) -> None:
    """Override the static ``model_id`` for the current task's ledger entry."""
    _runtime_model_id.set(model_id)


def set_runtime_prompt_hash(prompt_hash: str) -> None:
    """Set the SHA-256 prompt hash for the current task's ledger entry."""
    _runtime_prompt_hash.set(prompt_hash)


def set_runtime_reasoning_trace(trace: ReasoningTrace) -> None:
    """Attach a ReasoningTrace to the current task's ledger entry.

    Called by agent function bodies before they return. The decorator
    reads this ContextVar after the wrapped function returns and
    substitutes it into the AgentActionLedgerEntry on the success path.

    Eagerly re-validates the trace and raises IncompleteReasoningTraceError
    on contract failure. Eager validation surfaces the typed error
    immediately (vs. a silent invalid trace at ledger-write time).
    """
    try:
        ReasoningTrace.model_validate(trace.model_dump())
    except ValidationError as exc:
        raise IncompleteReasoningTraceError(
            agent_id="(set via set_runtime_reasoning_trace)",
            errors=[dict(e) for e in exc.errors()],
        ) from exc
    _runtime_reasoning_trace.set(trace)


# ───────────────────────────── error type ─────────────────────────────────


class AgentExecutionError(RuntimeError):
    """Raised by ``@agent_action`` when the wrapped function or the writer fails.

    Wraps the original exception via ``raise from``. The supervisor (Story
    3-5) catches this typed exception and surfaces a blocked-intake state.
    """

    def __init__(
        self,
        *,
        agent_id: str,
        case_id: CaseId | None,
        original: BaseException,
    ) -> None:
        self.agent_id = agent_id
        self.case_id = case_id
        self.original = original
        super().__init__(str(self))

    def __str__(self) -> str:
        case_label = self.case_id or "N/A"
        return f"agent {self.agent_id} failed on case {case_label}: {self.original.__class__.__name__}: {self.original}"


# ───────────────────────────── decorator ──────────────────────────────────


def agent_action(
    *,
    agent_id: str,
    model_id: str = "stub",
    prompt_template_id: str | None = None,
) -> Callable[[Callable[P, Awaitable[OutputT]]], Callable[P, Awaitable[OutputT]]]:
    """Decorate an async agent function so every invocation hits the ledger.

    See module docstring. The wrapped function MUST be async and MUST take a
    Pydantic ``BaseModel`` as the first positional argument (the agent input).
    """

    def decorator(
        fn: Callable[P, Awaitable[OutputT]],
    ) -> Callable[P, Awaitable[OutputT]]:
        if not inspect.iscoroutinefunction(fn):
            raise TypeError("@agent_action must wrap an async function")

        @functools.wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> OutputT:
            if not args:
                raise TypeError("agent must be called with at least one input model as the first arg")
            input_model = args[0]
            resolved_case_id = _resolve_case_id(input_model, kwargs)

            # Reset overrides so a previous task's stale value never leaks
            # into this entry.
            _runtime_model_id.set(None)
            _runtime_prompt_hash.set(None)
            _runtime_reasoning_trace.set(None)

            started_at = datetime.now(UTC)
            try:
                output = await fn(*args, **kwargs)
            except Exception as exc:
                completed_at = datetime.now(UTC)
                await _record_failure(
                    agent_id=agent_id,
                    static_model_id=model_id,
                    prompt_template_id=prompt_template_id,
                    input_model=input_model,
                    case_id=resolved_case_id,
                    started_at=started_at,
                    completed_at=completed_at,
                    exc=exc,
                )
                raise AgentExecutionError(agent_id=agent_id, case_id=resolved_case_id, original=exc) from exc

            completed_at = datetime.now(UTC)
            try:
                await _record_success(
                    agent_id=agent_id,
                    static_model_id=model_id,
                    prompt_template_id=prompt_template_id,
                    input_model=input_model,
                    output=output,
                    case_id=resolved_case_id,
                    started_at=started_at,
                    completed_at=completed_at,
                )
            except Exception as writer_exc:
                # The agent succeeded but the ledger write failed. Per Story
                # 3.2 § Pitfalls #3, this is loud-fail territory: the agent
                # didn't "return" per P4 because no audit trail was written.
                logger.error(
                    "ledger.append_failed_after_success agent_id=%s case_id=%s error=%r",
                    agent_id,
                    resolved_case_id,
                    writer_exc,
                )
                raise AgentExecutionError(
                    agent_id=agent_id,
                    case_id=resolved_case_id,
                    original=writer_exc,
                ) from writer_exc
            return output

        return wrapper

    return decorator


# ───────────────────────────── internals ──────────────────────────────────


def _resolve_case_id(input_model: object, kwargs: dict[str, object]) -> CaseId | None:
    """Find the ``case_id`` attached to this invocation, or ``None``."""
    if isinstance(input_model, BaseModel):
        candidate = getattr(input_model, "case_id", None)
        if isinstance(candidate, str):
            return candidate
    kw_candidate = kwargs.get("case_id")
    if isinstance(kw_candidate, str):
        return kw_candidate
    return None


def _placeholder_ledger_id() -> str:
    """Pattern-valid stand-in. The writer regenerates this on append."""
    return f"led_{ULID()!s}"


def _duration_ms(started: datetime, completed: datetime) -> int:
    delta = completed - started
    return max(0, int(delta.total_seconds() * 1000))


def _resolve_overrides(static_model_id: str) -> tuple[str, str | None]:
    runtime_model_id = _runtime_model_id.get()
    runtime_prompt_hash = _runtime_prompt_hash.get()
    return runtime_model_id or static_model_id, runtime_prompt_hash


def _dump_input(input_model: object) -> dict[str, object]:
    if isinstance(input_model, BaseModel):
        return input_model.model_dump(mode="json")
    return {"value": str(input_model)}


def _dump_output(output: object) -> dict[str, object]:
    if isinstance(output, BaseModel):
        return output.model_dump(mode="json")
    return {"value": str(output)}


async def _record_success(
    *,
    agent_id: str,
    static_model_id: str,
    prompt_template_id: str | None,
    input_model: object,
    output: object,
    case_id: CaseId | None,
    started_at: datetime,
    completed_at: datetime,
) -> None:
    resolved_model_id, resolved_prompt_hash = _resolve_overrides(static_model_id)
    payload = AgentActionLedgerEntry(
        agent_id=agent_id,
        model_id=resolved_model_id,
        prompt_template_id=prompt_template_id,
        prompt_hash=resolved_prompt_hash,
        input=_dump_input(input_model),
        output=_dump_output(output),
        started_at=started_at,
        completed_at=completed_at,
        duration_ms=_duration_ms(started_at, completed_at),
        status="ok",
        reasoning_trace=_runtime_reasoning_trace.get(),
    )
    entry = LedgerEntry(
        id=_placeholder_ledger_id(),
        actor_type=ActorType.AGENT,
        actor_id=agent_id,
        case_id=case_id,
        action="agent.completed",
        payload=payload,
        recorded_at=datetime.now(UTC),
    )
    await get_ledger_writer().append(entry)
    # Story 4.6 — fan-out an SSE event so the cockpit-ui invalidates
    # `['cases', caseId, 'agent-mesh-state']`. Best-effort; registry
    # failures are logged but do not abort the agent path.
    await publish_safe(
        case_id,
        SseEvent(
            event="agent.state_changed",
            data={"case_id": case_id, "agent_slug": agent_id, "state": "complete"},
        ),
    )


async def _record_failure(
    *,
    agent_id: str,
    static_model_id: str,
    prompt_template_id: str | None,
    input_model: object,
    case_id: CaseId | None,
    started_at: datetime,
    completed_at: datetime,
    exc: BaseException,
) -> None:
    resolved_model_id, resolved_prompt_hash = _resolve_overrides(static_model_id)
    payload = AgentActionLedgerEntry(
        agent_id=agent_id,
        model_id=resolved_model_id,
        prompt_template_id=prompt_template_id,
        prompt_hash=resolved_prompt_hash,
        input=_dump_input(input_model),
        output=None,
        started_at=started_at,
        completed_at=completed_at,
        duration_ms=_duration_ms(started_at, completed_at),
        status="error",
        error=ErrorInfo(
            type=exc.__class__.__name__,
            message=str(exc)[:500],
        ),
    )
    entry = LedgerEntry(
        id=_placeholder_ledger_id(),
        actor_type=ActorType.AGENT,
        actor_id=agent_id,
        case_id=case_id,
        action="agent.failed",
        payload=payload,
        recorded_at=datetime.now(UTC),
    )
    try:
        await get_ledger_writer().append(entry)
    except Exception as writer_exc:
        # Both the agent AND the writer failed. Surface the agent error
        # (the original) — but note the writer failure in logs so it isn't
        # silent.
        logger.error(
            "ledger.failure_record_failed agent_id=%s case_id=%s error=%r",
            agent_id,
            case_id,
            writer_exc,
        )
        return
    # Story 4.6 — best-effort SSE fan-out for the failure case.
    await publish_safe(
        case_id,
        SseEvent(
            event="agent.state_changed",
            data={"case_id": case_id, "agent_slug": agent_id, "state": "blocked"},
        ),
    )
