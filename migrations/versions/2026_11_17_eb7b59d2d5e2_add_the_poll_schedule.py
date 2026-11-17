"""add the poll schedule

Revision ID: eb7b59d2d5e2
Revises: 6938305deee8
Create Date: 2026-11-17 18:43:44.971379

"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "eb7b59d2d5e2"
down_revision: str | Sequence[str] | None = "6938305deee8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing competitors are due at once: the poller picks them up on its first claim.
    op.add_column(
        "competitors",
        sa.Column(
            "next_poll_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        op.f("ix_competitors_next_poll_at"),
        "competitors",
        ["next_poll_at"],
        postgresql_where=sa.text("removed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_competitors_next_poll_at"), table_name="competitors")
    op.drop_column("competitors", "next_poll_at")
