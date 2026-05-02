"""Pydantic Settings — environment-driven config.

Story 2.1 introduces the first ``Settings`` consumer (``db.session`` reads
``DATABASE_URL`` here). Future stories may add more fields; keep them strictly
env-sourced and avoid leaking defaults that mask misconfiguration.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the cockpit-api service."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./data/cockpit.db"
    # Story 3.1 — append-only JSONL ledger path (cwd-relative by default).
    ledger_path: Path = Path("./data/ledger.jsonl")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached ``Settings`` instance."""
    return Settings()
