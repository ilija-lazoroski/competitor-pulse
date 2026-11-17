"""add the known listing

Revision ID: 15207b826840
Revises: 8fefdc6737e2
Create Date: 2026-11-17 23:16:45.386464

"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "15207b826840"
down_revision: str | Sequence[str] | None = "8fefdc6737e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "competitors",
        sa.Column("known_listing", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    # Fill it from the history: the newest value the source sent for each field. Competitors
    # whose polls never read a field stay NULL, like ones that were never polled.
    op.execute(
        """
        UPDATE competitors
        SET known_listing = known.listing
        FROM (
            SELECT
                competitor_id,
                jsonb_build_object(
                    'title', (array_agg(title ORDER BY id DESC)
                        FILTER (WHERE title IS NOT NULL))[1],
                    'tagline', (array_agg(tagline ORDER BY id DESC)
                        FILTER (WHERE tagline IS NOT NULL))[1],
                    'price', (array_agg(
                        jsonb_build_object(
                            'amount', price_amount::text,
                            'currency', price_currency,
                            'period', price_period,
                            'unit', price_unit
                        ) ORDER BY id DESC) FILTER (WHERE price_amount IS NOT NULL))[1],
                    'description', (array_agg(description ORDER BY id DESC)
                        FILTER (WHERE description IS NOT NULL))[1]
                ) AS listing
            FROM snapshots
            WHERE outcome IN ('ok', 'incomplete')
            GROUP BY competitor_id
            HAVING bool_or(
                title IS NOT NULL OR tagline IS NOT NULL
                OR price_amount IS NOT NULL OR description IS NOT NULL
            )
        ) AS known
        WHERE competitors.id = known.competitor_id
        """
    )


def downgrade() -> None:
    op.drop_column("competitors", "known_listing")
