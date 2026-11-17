"""The database tables (SQLAlchemy Core). Alembic compares migrations with this metadata."""

from enum import StrEnum
from typing import Final

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    MetaData,
    Numeric,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import CHAR, ENUM, JSONB

from competitor_pulse.types import (
    CURRENCY_PATTERN,
    PRICE_UNIT_MAX_LENGTH,
    PRICE_UNIT_PATTERN,
    PollOutcome,
    PricePeriod,
    SummaryStatus,
)

# Constraint and index names are derived from these, so migrations name them the same way.
NAMING_CONVENTION: Final = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)

# Python None must be SQL NULL, not the JSON value null: the check constraints test IS NULL.
JsonbOrNull: Final = JSONB(none_as_null=True)


def _pg_enum(enum: type[StrEnum], name: str) -> ENUM:
    """Makes a PostgreSQL enum type that stores the values ("not_found"), not the names.

    :param enum: The Python enum
    :param name: The name of the PostgreSQL type
    :returns: The column type
    """
    return ENUM(enum, name=name, values_callable=lambda members: [m.value for m in members])


poll_outcome_type: Final = _pg_enum(PollOutcome, "poll_outcome")
summary_status_type: Final = _pg_enum(SummaryStatus, "summary_status")
price_period_type: Final = _pg_enum(PricePeriod, "price_period")


competitors = Table(
    "competitors",
    metadata,
    Column("id", Text, primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    Column("removed_at", DateTime(timezone=True)),
    # Copied from the newest changed snapshot, so the list shows recent changes cheaply.
    Column("last_changed_at", DateTime(timezone=True)),
    Column("next_poll_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    # Partial: the poller only looks for tracked competitors that are due.
    Index(
        "ix_competitors_next_poll_at",
        "next_poll_at",
        postgresql_where=text("removed_at IS NULL"),
    ),
)


# A competitor is tracked until the user removes it.
is_tracked: Final = competitors.c.removed_at.is_(None)

snapshots = Table(
    "snapshots",
    metadata,
    Column("id", BigInteger, Identity(always=True), primary_key=True),
    Column(
        "competitor_id",
        Text,
        ForeignKey("competitors.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("fetched_at", DateTime(timezone=True), nullable=False),
    Column("outcome", poll_outcome_type, nullable=False),
    Column("error", JsonbOrNull),
    Column("title", Text),
    Column("tagline", Text),
    Column("price_amount", Numeric(12, 2)),
    Column("price_currency", CHAR(3)),
    Column("price_period", price_period_type),
    Column("price_unit", Text),
    Column("description", Text),
    Column("changed", Boolean, nullable=False),
    Column("changes", JsonbOrNull),
    Column("summary", Text),
    Column("summary_status", summary_status_type, nullable=False),
    Column("summary_error", JsonbOrNull),
    CheckConstraint("(outcome = 'ok') = (error IS NULL)", name="error_iff_not_ok"),
    # A free price (amount 0) has no currency, period or unit; a paid one has the first two.
    CheckConstraint(
        "(coalesce(price_amount, 0) > 0) = (price_currency IS NOT NULL)"
        " AND (coalesce(price_amount, 0) > 0) = (price_period IS NOT NULL)",
        name="price_currency_and_period_iff_paid",
    ),
    CheckConstraint("price_unit IS NULL OR price_amount > 0", name="price_unit_only_when_paid"),
    CheckConstraint("price_amount >= 0", name="price_amount_not_negative"),
    CheckConstraint(f"price_currency ~ '{CURRENCY_PATTERN}'", name="price_currency_iso_4217"),
    CheckConstraint(
        f"price_unit ~ '{PRICE_UNIT_PATTERN}'"
        f" AND char_length(price_unit) <= {PRICE_UNIT_MAX_LENGTH}",
        name="price_unit_format",
    ),
    CheckConstraint("changed = (changes IS NOT NULL)", name="changes_iff_changed"),
    CheckConstraint("(summary_status = 'ready') = (summary IS NOT NULL)", name="summary_iff_ready"),
    CheckConstraint(
        "(summary_status IN ('llm_failed', 'llm_unusable')) = (summary_error IS NOT NULL)",
        name="summary_error_iff_llm_error",
    ),
    Index(
        "ix_snapshots_competitor_id_fetched_at_id",
        "competitor_id",
        text("fetched_at DESC"),
        text("id DESC"),
    ),
    # Partial: only the few rows that wait for a summary.
    Index(
        "ix_snapshots_pending_summary",
        "fetched_at",
        postgresql_where=text("summary_status = 'pending'"),
    ),
    # Rows arrive in time order, so a BRIN index on the age stays tiny.
    Index("ix_snapshots_fetched_at_brin", "fetched_at", postgresql_using="brin"),
)
