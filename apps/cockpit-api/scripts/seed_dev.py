"""Seed the dev SQLite database with demo tenant + officer + cases.

Idempotent: re-running does not duplicate rows. UUIDs are pinned via env vars,
inserts use ``INSERT OR IGNORE`` (SQLite syntax — the demo build is SQLite-only
per Story 1.5 § Demo Scope Addendum).

The ``tenants`` and ``officers`` tables don't exist until later stories land
the schemas. Until then this script gracefully no-ops with a clear log line —
explicitly NOT a silent failure (architecture.md anti-pattern P-AP).

Story 2.4 — also seeds three pinned fixture cases via
``contracts.cases.get_demo_case_fixtures``. Same skip-when-table-missing
pattern; same idempotent ``INSERT OR IGNORE`` semantics.

Story 3.1 — appends ``ledger.initialized`` and per-case ``case.seeded`` entries
to the JSONL ledger after the SQL insert phase. The ledger is append-only by
design — every ``make seed`` run appends fresh entries; ``make demo-reset``
wipes them.

Run via ``make seed`` or directly: ``poetry run python scripts/seed_dev.py``.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from contracts.cases import Case, get_demo_case_fixtures
from contracts.ledger import ActorType, LedgerEntry
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from ulid import ULID

from cockpit_api.config import get_settings
from cockpit_api.services.ledger_service import LedgerWriter

DEMO_TENANT_ID = os.environ.get("DEMO_TENANT_ID", "00000000-0000-4000-8000-000000000001")
DEMO_OFFICER_ID = os.environ.get("DEMO_OFFICER_ID", "00000000-0000-4000-8000-000000000002")
DEMO_TENANT_NAME = "Demo Bank Pvt Ltd"
DEMO_OFFICER_EMAIL = "officer@demo.local"


def _placeholder_ledger_id() -> str:
    """Pattern-valid ledger ID. Overwritten by the writer at append time."""
    return f"led_{ULID()!s}"


def _missing_table_error(exc: OperationalError, table: str) -> bool:
    """True if ``exc`` is the SQLite ``no such table: <table>`` variant."""
    msg = str(exc).lower()
    return "no such table" in msg and table.lower() in msg


async def _seed_cases(conn: AsyncConnection, fixtures: list[Case]) -> bool:
    """Insert the three demo cases. Returns False if the table is missing.

    ``INSERT OR IGNORE`` keeps the call idempotent — re-running does not
    duplicate rows or raise on existing IDs.
    """
    insert_sql = text(
        "INSERT OR IGNORE INTO cases "
        "(id, state, customer_metadata, assigned_to_user_id, risk_band, "
        " created_at, updated_at, closure_date) "
        "VALUES (:id, :state, :customer_metadata, :assigned_to_user_id, "
        ":risk_band, :created_at, :updated_at, :closure_date)"
    )
    try:
        for case in fixtures:
            await conn.execute(
                insert_sql,
                {
                    "id": case.id,
                    "state": case.state.value,
                    "customer_metadata": case.customer_metadata.model_dump_json(),
                    "assigned_to_user_id": case.assigned_to_user_id,
                    "risk_band": case.risk_band,
                    "created_at": case.created_at,
                    "updated_at": case.updated_at,
                    "closure_date": case.closure_date,
                },
            )
    except OperationalError as e:
        if _missing_table_error(e, "cases"):
            print("  cases table not yet present — skipping demo cases.")
            return False
        raise
    return True


async def _seed(engine: AsyncEngine) -> tuple[bool, bool, bool]:
    """Insert demo rows. Returns (tenants_seeded, officers_seeded, cases_seeded).

    ``False`` means the corresponding table doesn't exist yet and the insert
    was skipped.
    """

    tenants_seeded = False
    officers_seeded = False
    cases_seeded = False

    fixtures = get_demo_case_fixtures(datetime.now(UTC))

    async with engine.begin() as conn:
        try:
            await conn.execute(
                text("INSERT OR IGNORE INTO tenants (id, name) VALUES (:id, :name)"),
                {"id": DEMO_TENANT_ID, "name": DEMO_TENANT_NAME},
            )
            tenants_seeded = True
        except OperationalError as e:
            if _missing_table_error(e, "tenants"):
                print("  tenants table not yet present — skipping demo tenant.")
            else:
                raise

        try:
            await conn.execute(
                text("INSERT OR IGNORE INTO officers (id, tenant_id, email) VALUES (:id, :tenant_id, :email)"),
                {"id": DEMO_OFFICER_ID, "tenant_id": DEMO_TENANT_ID, "email": DEMO_OFFICER_EMAIL},
            )
            officers_seeded = True
        except OperationalError as e:
            if _missing_table_error(e, "officers"):
                print("  officers table not yet present — skipping demo officer.")
            else:
                raise

        cases_seeded = await _seed_cases(conn, fixtures)

    return tenants_seeded, officers_seeded, cases_seeded


async def _seed_ledger(fixtures: list[Case], cases_seeded: bool) -> int:
    """Append bootstrap entries to the JSONL ledger. Returns count appended."""
    writer = LedgerWriter(get_settings().ledger_path)
    appended = 0

    await writer.append(
        LedgerEntry(
            id=_placeholder_ledger_id(),
            actor_type=ActorType.SYSTEM,
            actor_id="seed_dev",
            case_id=None,
            action="ledger.initialized",
            payload={"cases_seeded": len(fixtures) if cases_seeded else 0},
            recorded_at=datetime.now(UTC),
        )
    )
    appended += 1

    if cases_seeded:
        for case in fixtures:
            await writer.append(
                LedgerEntry(
                    id=_placeholder_ledger_id(),
                    actor_type=ActorType.SYSTEM,
                    actor_id="seed_dev",
                    case_id=case.id,
                    action="case.seeded",
                    payload={
                        "customer_name": case.customer_metadata.customer_name,
                        "case_id": case.id,
                    },
                    recorded_at=datetime.now(UTC),
                )
            )
            appended += 1

    return appended


async def _run_intake_for_fixtures(engine: AsyncEngine, fixtures: list[Case]) -> int:
    """Run case intake for each freshly-seeded case — Story 3.5 § AC8.

    Returns the number of cases that completed (status="completed").
    Skipped cases (already past intake_scheduled) are tolerated quietly.
    """
    # Local import: agents has a path-dep on cockpit-api; the supervisor
    # imports back into us. Importing at module top would create a circular
    # import on alembic invocation. Deferring to call time is safe.
    from contextlib import asynccontextmanager

    from agents.supervisor.case_supervisor import (
        CaseNotIntakeReadyError,
        CaseSupervisor,
    )
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    factory = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def _session_factory() -> AsyncIterator[AsyncSession]:
        async with factory() as s:
            yield s

    supervisor = CaseSupervisor(session_factory=_session_factory)
    completed = 0
    for case in fixtures:
        try:
            outcome = await supervisor.run_intake(case.id)
        except CaseNotIntakeReadyError:
            print(f"  intake {case.id} → skipped (already past intake_scheduled)")
            continue
        if outcome.status == "completed":
            completed += 1
            print(f"  intake {case.id} → completed ({outcome.fields_extracted} fields)")
        else:
            print(f"  intake {case.id} → blocked ({outcome.failed_agent}: {outcome.error_message})")
    return completed


async def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is not set — refusing to seed.", file=sys.stderr)
        return 1

    engine = create_async_engine(dsn, future=True)
    try:
        tenants_seeded, officers_seeded, cases_seeded = await _seed(engine)

        print(f"Demo tenant:  {DEMO_TENANT_ID}{'' if tenants_seeded else ' (skipped)'}")
        print(f"Demo officer: {DEMO_OFFICER_ID}{'' if officers_seeded else ' (skipped)'}")
        fixtures = get_demo_case_fixtures(datetime.now(UTC))
        if cases_seeded:
            ids = ", ".join(c.id for c in fixtures)
            print(f"Demo cases:   {ids}")
        else:
            print("Demo cases:   (skipped)")

        appended = await _seed_ledger(fixtures, cases_seeded)
        print(f"Ledger:       appended {appended} bootstrap entries.")

        # Story 4 hardening — let the demo presenter choose whether intake
        # runs at seed time. SEED_SKIP_INTAKE=1 leaves every case in
        # ``intake_scheduled`` with no agent ledger entries so the cockpit's
        # Agent Copilot Pane starts all-idle and the analyst can demo the
        # live "Process now → SSE → pane animates" flow.
        skip_intake = os.environ.get("SEED_SKIP_INTAKE", "").lower() in {"1", "true", "yes"}
        if cases_seeded and not skip_intake:
            print("Running case intake...")
            completed = await _run_intake_for_fixtures(engine, fixtures)
            print(f"Intake:       completed for {completed} case(s).")
        elif cases_seeded and skip_intake:
            print('Intake:       skipped (SEED_SKIP_INTAKE=1) — click "Process now" in the cockpit.')
    finally:
        await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
