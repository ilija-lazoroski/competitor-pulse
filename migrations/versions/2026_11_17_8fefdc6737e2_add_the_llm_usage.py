"""add the llm usage

Revision ID: 8fefdc6737e2
Revises: eb7b59d2d5e2
Create Date: 2026-11-17 19:39:22.171192

"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8fefdc6737e2"
down_revision: str | Sequence[str] | None = "eb7b59d2d5e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_usage",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("calls", sa.Integer(), nullable=False),
        sa.CheckConstraint("calls >= 0", name=op.f("ck_llm_usage_calls_not_negative")),
        sa.PrimaryKeyConstraint("day", name=op.f("pk_llm_usage")),
    )


def downgrade() -> None:
    op.drop_table("llm_usage")
