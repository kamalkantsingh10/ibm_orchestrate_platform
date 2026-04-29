-- Local-dev Postgres init script (Story 1.2).
--
-- Runs once per fresh `postgres_data` volume via the Postgres init hook.
-- Keep this minimal: real schemas + tenant role wiring land in Story 1.5,
-- and the INSERT-only ledger role lands in Epic 3 (Story 3.1).

-- Public schema is owned by the cockpit role (created by POSTGRES_USER); make
-- sure the connection user can create per-tenant schemas later (Story 1.5).
ALTER ROLE cockpit CREATEDB;

-- Reserve placeholder role names so later migrations can ALTER ROLE / CREATE
-- ROLE idempotently against a known starting state. These are stubs only —
-- privileges are configured in their owning stories.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ledger_writer') THEN
    CREATE ROLE ledger_writer NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ledger_reader') THEN
    CREATE ROLE ledger_reader NOLOGIN;
  END IF;
END $$;
