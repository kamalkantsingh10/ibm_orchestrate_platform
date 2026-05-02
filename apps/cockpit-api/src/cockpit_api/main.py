"""FastAPI app entrypoint for the KYC Cockpit API.

Story 1.2 wires the auto-generated Swagger UI (`/docs`) and the unauth-friendly
liveness endpoint (`/health`). Story 1.4 adds the demo user-switcher router.
Story 2.2 adds the cases router and the RFC 7807 error handler.
Story 3.4 ADK integration adds the agents router so the watsonx Orchestrate
runtime can invoke document_intelligence as a tool.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from cockpit_api.errors import RFC7807Problem
from cockpit_api.routers import agents as agents_router
from cockpit_api.routers import cases as cases_router
from cockpit_api.routers import documents as documents_router
from cockpit_api.routers import users as users_router

app = FastAPI(title="Cockpit API", version="0.1.0")

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
