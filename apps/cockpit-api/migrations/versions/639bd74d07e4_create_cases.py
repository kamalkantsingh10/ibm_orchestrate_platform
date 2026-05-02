"""create cases

Revision ID: 639bd74d07e4
Revises:
Create Date: 2026-04-30 07:33:19.384494

Story 2.1 — first real migration in the project. Establishes the ``cases``
table and the ``ix_cases_created_at`` index used by the queue rail (Story 2-3).

Dialect-portable types are mandatory here (see ``apps/cockpit-api/migrations/README``):
``sa.JSON()`` over ``postgresql.JSONB()``, ``sa.String(N)`` over native UUID,
no ``gen_random_uuid()`` server defaults.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "639bd74d07e4"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "cases",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("customer_metadata", sa.JSON(), nullable=False),
        sa.Column("assigned_to_user_id", sa.String(length=36), nullable=True),
        sa.Column("risk_band", sa.String(length=16), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("closure_date", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cases_created_at", "cases", ["created_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_cases_created_at", table_name="cases")
    op.drop_table("cases")
