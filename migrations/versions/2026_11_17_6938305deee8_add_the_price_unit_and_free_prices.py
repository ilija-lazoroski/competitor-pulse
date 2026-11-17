"""add the price unit and free prices

Revision ID: 6938305deee8
Revises: 6b0ffe8918a1
Create Date: 2026-11-17 18:03:52.940216

"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6938305deee8"
down_revision: str | Sequence[str] | None = "6b0ffe8918a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("snapshots", sa.Column("price_unit", sa.Text(), nullable=True))
    op.drop_constraint(op.f("ck_snapshots_price_all_or_nothing"), "snapshots", type_="check")
    op.create_check_constraint(
        op.f("ck_snapshots_price_currency_and_period_iff_paid"),
        "snapshots",
        "(coalesce(price_amount, 0) > 0) = (price_currency IS NOT NULL)"
        " AND (coalesce(price_amount, 0) > 0) = (price_period IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f("ck_snapshots_price_unit_only_when_paid"),
        "snapshots",
        "price_unit IS NULL OR price_amount > 0",
    )
    op.create_check_constraint(
        op.f("ck_snapshots_price_unit_format"),
        "snapshots",
        "price_unit ~ '^[a-z0-9]+( [a-z0-9]+)*$' AND char_length(price_unit) <= 20",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_snapshots_price_unit_format"), "snapshots", type_="check")
    op.drop_constraint(op.f("ck_snapshots_price_unit_only_when_paid"), "snapshots", type_="check")
    op.drop_constraint(
        op.f("ck_snapshots_price_currency_and_period_iff_paid"), "snapshots", type_="check"
    )
    # The old schema has no free prices and no units: those snapshots lose their price rather
    # than keep a wrong one.
    op.execute(
        "UPDATE snapshots SET price_amount = NULL, price_currency = NULL, price_period = NULL"
        " WHERE price_amount = 0 OR price_unit IS NOT NULL"
    )
    op.drop_column("snapshots", "price_unit")
    op.create_check_constraint(
        op.f("ck_snapshots_price_all_or_nothing"),
        "snapshots",
        "(price_amount IS NULL) = (price_currency IS NULL)"
        " AND (price_amount IS NULL) = (price_period IS NULL)",
    )
