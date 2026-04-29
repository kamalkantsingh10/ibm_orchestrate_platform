"""Seed the dev Postgres with one demo tenant + one demo officer.

Idempotent: re-running does not duplicate rows (UUIDs are pinned via env vars
and inserts use ``ON CONFLICT DO NOTHING``).

The ``tenants`` and ``officers`` tables don't exist until Story 1.5 lands the
tenant-schema primitives. Until then, this script gracefully no-ops with a
clear log line — explicitly NOT a silent failure (anti-pattern from the
architecture is "silent failures").

Run via ``make seed`` or directly: ``poetry run python scripts/seed_dev.py``.
"""

from __future__ import annotations

import asyncio
import os
import sys
from urllib.parse import urlparse, urlunparse

import asyncpg

DEMO_TENANT_ID = os.environ.get("DEMO_TENANT_ID", "00000000-0000-4000-8000-000000000001")
DEMO_OFFICER_ID = os.environ.get("DEMO_OFFICER_ID", "00000000-0000-4000-8000-000000000002")
DEMO_TENANT_NAME = "Demo Bank Pvt Ltd"
DEMO_OFFICER_EMAIL = "officer@demo.local"


def _normalise_dsn(dsn: str) -> str:
    """asyncpg expects ``postgresql://...`` not ``postgresql+asyncpg://...``.

    The repo's ``.env`` ships the SQLAlchemy-flavoured URL by default, so we
    strip the driver prefix when handing the DSN to asyncpg.
    """

    parsed = urlparse(dsn)
    if "+" in parsed.scheme:
        scheme = parsed.scheme.split("+", 1)[0]
        parsed = parsed._replace(scheme=scheme)
    return urlunparse(parsed)


async def _seed(conn: asyncpg.Connection) -> tuple[bool, bool]:
    """Insert demo rows. Returns (tenants_seeded, officers_seeded).

    ``False`` means the table doesn't exist yet and the insert was skipped.
    """

    tenants_seeded = False
    officers_seeded = False

    try:
        await conn.execute(
            """
            INSERT INTO tenants (id, name)
            VALUES ($1::uuid, $2)
            ON CONFLICT (id) DO NOTHING
            """,
            DEMO_TENANT_ID,
            DEMO_TENANT_NAME,
        )
        tenants_seeded = True
    except asyncpg.UndefinedTableError:
        print("  tenants table not yet present (Story 1.5 owns it) — skipping demo tenant.")

    try:
        await conn.execute(
            """
            INSERT INTO officers (id, tenant_id, email)
            VALUES ($1::uuid, $2::uuid, $3)
            ON CONFLICT (id) DO NOTHING
            """,
            DEMO_OFFICER_ID,
            DEMO_TENANT_ID,
            DEMO_OFFICER_EMAIL,
        )
        officers_seeded = True
    except asyncpg.UndefinedTableError:
        print("  officers table not yet present (Story 1.6 owns it) — skipping demo officer.")

    return tenants_seeded, officers_seeded


async def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is not set — refusing to seed.", file=sys.stderr)
        return 1

    conn = await asyncpg.connect(_normalise_dsn(dsn))
    try:
        tenants_seeded, officers_seeded = await _seed(conn)
    finally:
        await conn.close()

    print(f"Demo tenant:  {DEMO_TENANT_ID}{'' if tenants_seeded else ' (skipped)'}")
    print(f"Demo officer: {DEMO_OFFICER_ID}{'' if officers_seeded else ' (skipped)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
