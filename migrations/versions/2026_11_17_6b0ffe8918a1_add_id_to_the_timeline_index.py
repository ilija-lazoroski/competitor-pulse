"""add id to the timeline index

Revision ID: 6b0ffe8918a1
Revises: b787d8f839be
Create Date: 2026-11-17 17:17:07.638737

"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6b0ffe8918a1"
down_revision: str | Sequence[str] | None = "b787d8f839be"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The timeline pages by (fetched_at, id), so id joins the index as the tie-breaker.
    op.create_index(
        op.f("ix_snapshots_competitor_id_fetched_at_id"),
        "snapshots",
        ["competitor_id", sa.text("fetched_at DESC"), sa.text("id DESC")],
    )
    op.drop_index(op.f("ix_snapshots_competitor_id_fetched_at"), table_name="snapshots")


def downgrade() -> None:
    op.create_index(
        op.f("ix_snapshots_competitor_id_fetched_at"),
        "snapshots",
        ["competitor_id", sa.text("fetched_at DESC")],
    )
    op.drop_index(op.f("ix_snapshots_competitor_id_fetched_at_id"), table_name="snapshots")
