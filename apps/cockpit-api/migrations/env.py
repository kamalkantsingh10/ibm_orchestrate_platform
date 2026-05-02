import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Story 2.1 — Alembic invocation cwd is `apps/cockpit-api/`; the package lives
# under `src/cockpit_api/`. Editable installs handle imports inside the venv,
# but autogenerate sometimes runs in a context where the src layout isn't on
# sys.path. Add it explicitly to keep the import bullet-proof.
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from cockpit_api.db.models import Base  # noqa: E402  (sys.path tweak above)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Story 1.5 — read DATABASE_URL from env; alembic.ini's `sqlalchemy.url` is
# only a placeholder. Strip the +aiosqlite driver for sync Alembic execution.
_database_url = os.environ.get("DATABASE_URL")
if _database_url:
    sync_url = _database_url.replace("+aiosqlite", "").replace("+asyncpg", "")
    config.set_main_option("sqlalchemy.url", sync_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Story 2.1 — first real migration: point Alembic at the project's metadata.
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
