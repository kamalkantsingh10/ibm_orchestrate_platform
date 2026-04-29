"""FastAPI app entrypoint for the KYC Cockpit API.

Story 1.2 wires the auto-generated Swagger UI (`/docs`) and the unauth-friendly
liveness endpoint (`/health`). Story 1.4 adds the demo user-switcher router.
Routers, services, repos, middleware, adapters, db, and observability
subpackages are introduced in their own stories — do not pre-create them here.
"""

from fastapi import FastAPI

from cockpit_api.routers import users as users_router

app = FastAPI(title="Cockpit API", version="0.1.0")
app.include_router(users_router.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
