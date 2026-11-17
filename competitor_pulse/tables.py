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

from competitor_pulse.types import CURRENCY_PATTERN, PollOutcome, PricePeriod, SummaryStatus

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
    # Store the values ("not_found"), not the member names ("NOT_FOUND").
    return ENUM(enum, name=name, values_callable=lambda members: [m.value for m in members])


poll_outcome_type: Final = _pg_enum(PollOutcome, "poll_outcome")
summary_status_type: Final = _pg_enum(SummaryStatus, "summary_status")
price_period_type: Final = _pg_enum(PricePeriod, "price_period")


competitors = Table(
    "competitors",
    metadata,
    Column("id", Text, primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    # Set when the user stops tracking the competitor. Its history stays until the cleaner
    # removes it; adding the id again clears this and continues the same timeline.
    Column("removed_at", DateTime(timezone=True)),
    # The newest snapshot with changed = true, so the list can show recent changes cheaply.
    Column("last_changed_at", DateTime(timezone=True)),
)


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
    # The listing, normalized. NULL when the poll did not return the field.
    Column("title", Text),
    Column("tagline", Text),
    Column("price_amount", Numeric(12, 2)),
    Column("price_currency", CHAR(3)),
    Column("price_period", price_period_type),
    Column("description", Text),
    Column("changed", Boolean, nullable=False),
    Column("changes", JsonbOrNull),
    Column("summary", Text),
    Column("summary_status", summary_status_type, nullable=False),
    Column("summary_error", JsonbOrNull),
    CheckConstraint("(outcome = 'ok') = (error IS NULL)", name="error_iff_not_ok"),
    CheckConstraint(
        "(price_amount IS NULL) = (price_currency IS NULL)"
        " AND (price_amount IS NULL) = (price_period IS NULL)",
        name="price_all_or_nothing",
    ),
    CheckConstraint("price_amount >= 0", name="price_amount_not_negative"),
    CheckConstraint(f"price_currency ~ '{CURRENCY_PATTERN}'", name="price_currency_iso_4217"),
    CheckConstraint("changed = (changes IS NOT NULL)", name="changes_iff_changed"),
    CheckConstraint("(summary_status = 'ready') = (summary IS NOT NULL)", name="summary_iff_ready"),
    CheckConstraint(
        "(summary_status IN ('llm_failed', 'llm_unusable')) = (summary_error IS NOT NULL)",
        name="summary_error_iff_llm_error",
    ),
    # The timeline: one competitor's snapshots, newest first.
    Index("ix_snapshots_competitor_id_fetched_at", "competitor_id", text("fetched_at DESC")),
    # The LLM worker's queue: only the few rows that wait for a summary.
    Index(
        "ix_snapshots_pending_summary",
        "fetched_at",
        postgresql_where=text("summary_status = 'pending'"),
    ),
    # The cleaner deletes by age. Rows arrive in time order, so BRIN stays tiny.
    Index("ix_snapshots_fetched_at_brin", "fetched_at", postgresql_using="brin"),
)
