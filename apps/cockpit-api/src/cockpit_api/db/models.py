"""ORM model rows — Story 2.1.

The repository layer (``cockpit_api.repositories``) is the only path that
touches these classes; ORM rows never leave the repo. Wire types are the
Pydantic contracts in ``packages/contracts``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, PrimaryKeyConstraint, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Project-wide SQLAlchemy declarative base.

    All ORM models inherit from this. Alembic's ``env.py`` exposes
    ``Base.metadata`` to autogenerate migrations.
    """


class CaseRow(Base):
    """SQL shape for the ``cases`` table.

    Mirrors the ``Case`` Pydantic contract column-for-column using
    dialect-portable types (no ``JSONB``, no native ``UUID``, no ``ENUM``).
    State validation is done in Python via ``contracts.cases.assert_transition``
    — the column is a plain ``String``.
    """

    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    # No FK: ``users`` is contract-only in the demo (see Story 1.4); the
    # column stores a UUID string but no row exists to constrain it.
    assigned_to_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    risk_band: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    closure_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_cases_created_at", "created_at"),)


class IntakeRow(Base):
    """SQL shape for the ``intake_results`` table — Story 3.5.

    Stores the full typed agent output as a JSON dict, keyed by
    ``(case_id, agent_id)``. Re-running intake for a case overwrites the
    previous row (upsert semantics; the supervisor blocks re-runs via the
    state machine, but the table itself permits replace).
    """

    __tablename__ = "intake_results"

    case_id: Mapped[str] = mapped_column(String(32), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    output_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        PrimaryKeyConstraint("case_id", "agent_id", name="pk_intake_results"),
        Index("ix_intake_results_case_id", "case_id"),
    )
