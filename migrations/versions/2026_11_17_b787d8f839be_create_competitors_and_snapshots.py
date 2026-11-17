"""create competitors and snapshots

Revision ID: b787d8f839be
Revises:
Create Date: 2026-11-17 16:43:14.718951

"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b787d8f839be"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The values are written out (not imported from the app) so this revision keeps describing
# the schema as it was, whatever the code looks like later.
poll_outcome = postgresql.ENUM(
    "ok", "incomplete", "not_found", "failed", name="poll_outcome", create_type=False
)
summary_status = postgresql.ENUM(
    "ready",
    "no_change",
    "baseline",
    "poll_failed",
    "pending",
    "llm_failed",
    "llm_unusable",
    "cap_reached",
    name="summary_status",
    create_type=False,
)
price_period = postgresql.ENUM("month", "year", "one_time", name="price_period", create_type=False)

ENUMS = (poll_outcome, summary_status, price_period)


def upgrade() -> None:
    for enum in ENUMS:
        enum.create(op.get_bind())

    op.create_table(
        "competitors",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_competitors")),
    )

    op.create_table(
        "snapshots",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("competitor_id", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", poll_outcome, nullable=False),
        sa.Column("error", postgresql.JSONB(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("tagline", sa.Text(), nullable=True),
        sa.Column("price_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("price_currency", postgresql.CHAR(3), nullable=True),
        sa.Column("price_period", price_period, nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("changed", sa.Boolean(), nullable=False),
        sa.Column("changes", postgresql.JSONB(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("summary_status", summary_status, nullable=False),
        sa.Column("summary_error", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_snapshots")),
        sa.ForeignKeyConstraint(
            ["competitor_id"],
            ["competitors.id"],
            name=op.f("fk_snapshots_competitor_id_competitors"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "(outcome = 'ok') = (error IS NULL)", name=op.f("ck_snapshots_error_iff_not_ok")
        ),
        sa.CheckConstraint(
            "(price_amount IS NULL) = (price_currency IS NULL)"
            " AND (price_amount IS NULL) = (price_period IS NULL)",
            name=op.f("ck_snapshots_price_all_or_nothing"),
        ),
        sa.CheckConstraint(
            "price_amount >= 0", name=op.f("ck_snapshots_price_amount_not_negative")
        ),
        sa.CheckConstraint(
            "price_currency ~ '^[A-Z]{3}$'", name=op.f("ck_snapshots_price_currency_iso_4217")
        ),
        sa.CheckConstraint(
            "changed = (changes IS NOT NULL)", name=op.f("ck_snapshots_changes_iff_changed")
        ),
        sa.CheckConstraint(
            "(summary_status = 'ready') = (summary IS NOT NULL)",
            name=op.f("ck_snapshots_summary_iff_ready"),
        ),
        sa.CheckConstraint(
            "(summary_status IN ('llm_failed', 'llm_unusable')) = (summary_error IS NOT NULL)",
            name=op.f("ck_snapshots_summary_error_iff_llm_error"),
        ),
    )
    op.create_index(
        op.f("ix_snapshots_competitor_id_fetched_at"),
        "snapshots",
        ["competitor_id", sa.text("fetched_at DESC")],
    )
    op.create_index(
        op.f("ix_snapshots_pending_summary"),
        "snapshots",
        ["fetched_at"],
        postgresql_where=sa.text("summary_status = 'pending'"),
    )
    op.create_index(
        op.f("ix_snapshots_fetched_at_brin"),
        "snapshots",
        ["fetched_at"],
        postgresql_using="brin",
    )


def downgrade() -> None:
    op.drop_table("snapshots")
    op.drop_table("competitors")
    for enum in reversed(ENUMS):
        enum.drop(op.get_bind())
