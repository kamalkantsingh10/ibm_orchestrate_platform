"""FastAPI app entrypoint for the KYC Cockpit API.

Story 1.2 wires the auto-generated Swagger UI (`/docs`) and the unauth-friendly
liveness endpoint (`/health`). Story 1.4 adds the demo user-switcher router.
Story 2.2 adds the cases router and the RFC 7807 error handler.
Story 3.4 ADK integration adds the agents router so the watsonx Orchestrate
runtime can invoke document_intelligence as a tool.
Story 7.4 wires the in-process decision undo timer service into the
FastAPI lifespan so the POST decision endpoint (Story 7.7) can schedule
a 120s seal countdown.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from cockpit_api.errors import RFC7807Problem
from cockpit_api.routers import agents as agents_router
from cockpit_api.routers import cases as cases_router
from cockpit_api.routers import documents as documents_router
from cockpit_api.routers import stream as stream_router
from cockpit_api.routers import users as users_router
from cockpit_api.services.decision_timer import DecisionTimerService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """App lifespan — owns the decision timer singleton + the cured
    ``seal_decision`` callback.

    Story 7.4 added the timer; Story 7.7 wires the real ``on_seal``
    callback that transitions the case to COMMITTED, writes the
    ``decision.sealed`` ledger entry, and publishes the SSE event.
    The callback uses ``session_factory`` (not a request-bound
    session) because it runs on the timer's background task.
    """
    from cockpit_api.db.session import get_sessionmaker
    from cockpit_api.services import decision_service
    from cockpit_api.services.ledger_service import get_ledger_writer
    from cockpit_api.services.sse_registry import publish_safe

    sessionmaker = get_sessionmaker()

    @asynccontextmanager
    async def _factory() -> AsyncIterator[Any]:
        async with sessionmaker() as s:
            yield s

    async def on_seal(case_id: str, decision_id: str) -> None:
        try:
            await decision_service.seal_decision(
                case_id=case_id,
                decision_id=decision_id,
                session_factory=_factory,
                writer=get_ledger_writer(),
                sse_publish=publish_safe,
            )
        except Exception:
            logger.exception(
                "decision_timer.seal_decision_failed case=%s decision=%s",
                case_id,
                decision_id,
            )

    timer = DecisionTimerService(on_seal=on_seal)
    _app.state.decision_timer = timer
    try:
        yield
    finally:
        await timer.shutdown()


app = FastAPI(title="Cockpit API", version="0.1.0", lifespan=lifespan)


def get_decision_timer(request: Request) -> DecisionTimerService:
    """FastAPI dependency that returns the lifespan-scoped timer.

    Story 7.7's POST decision endpoint and Story 7.5's undo endpoint
    both consume this — ``Depends(get_decision_timer)``.
    """
    timer = getattr(request.app.state, "decision_timer", None)
    if timer is None:  # pragma: no cover — would only happen pre-lifespan
        raise RuntimeError("decision_timer not initialised; lifespan did not run")
    return timer  # type: ignore[no-any-return]


# CORS for the local cockpit-ui dev server. The UI sends a custom
# `X-Cockpit-Demo-User` header which makes every request a CORS-non-simple
# request — without the preflight handler, the browser blocks it. Restrict
# origins to the Vite dev server; allow any header so TanStack Query's
# revalidation `cache-control`/`pragma` defaults don't fail preflight.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users_router.router)
app.include_router(cases_router.router)
app.include_router(agents_router.router)
app.include_router(documents_router.router)
app.include_router(stream_router.router)


_PROBLEM_CONTENT_TYPE = "application/problem+json"

_TITLE_FOR_STATUS = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    409: "Conflict",
    422: "Unprocessable Entity",
    500: "Internal Server Error",
}


def _problem_response(
    status_code: int,
    detail: str,
    instance: str | None,
    *,
    title: str | None = None,
) -> JSONResponse:
    problem = RFC7807Problem(
        title=title or _TITLE_FOR_STATUS.get(status_code, "Error"),
        status=status_code,
        detail=detail,
        instance=instance,
    )
    return JSONResponse(
        content=problem.model_dump(),
        status_code=status_code,
        media_type=_PROBLEM_CONTENT_TYPE,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return _problem_response(
        status_code=exc.status_code,
        detail=detail,
        instance=request.url.path,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    messages = "; ".join(f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors())
    return _problem_response(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=messages or "Request validation failed",
        instance=request.url.path,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
