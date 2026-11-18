"""Value types shared by the database, the poller and the API.

The enums are stored as native PostgreSQL enums; Changes is stored in snapshots.changes (jsonb).
"""

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Final, Self, TypeAlias

from pydantic import Field, StringConstraints, TypeAdapter, model_validator
from service_kit import ServiceKitBaseModel

# The patterns stay strings: Pydantic compiles them once into its own (Rust) regex engine,
# and tables.py puts them into the CHECK constraints.
CURRENCY_PATTERN: Final[str] = r"^[A-Z]{3}$"
# What a price is charged per, like "seat" or "1k events": lowercase words, one space apart.
PRICE_UNIT_PATTERN: Final[str] = r"^[a-z0-9]+( [a-z0-9]+)*$"
PRICE_UNIT_MAX_LENGTH: Final[int] = 20
COMPETITOR_ID_PATTERN: Final[str] = r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$"

# Lowercase slugs like "acme-crm". The id goes into the source URL (/listings/{id}), so
# slashes, dots and other path characters must never get through.
CompetitorID: TypeAlias = Annotated[str, StringConstraints(pattern=COMPETITOR_ID_PATTERN)]


class PollOutcome(StrEnum):
    """What a poll of the source returned."""

    OK = "ok"
    INCOMPLETE = "incomplete"
    NOT_FOUND = "not_found"
    FAILED = "failed"


class SummaryStatus(StrEnum):
    """Whether a snapshot has a summary and, if not, why."""

    READY = "ready"
    NO_CHANGE = "no_change"
    BASELINE = "baseline"
    POLL_FAILED = "poll_failed"
    PENDING = "pending"
    LLM_FAILED = "llm_failed"
    LLM_UNUSABLE = "llm_unusable"
    CAP_REACHED = "cap_reached"


class PricePeriod(StrEnum):
    """How often a price is paid."""

    MONTH = "month"
    YEAR = "year"
    ONE_TIME = "one_time"


class ListingField(StrEnum):
    """The fields of a listing that we keep and compare."""

    TITLE = "title"
    TAGLINE = "tagline"
    PRICE = "price"
    DESCRIPTION = "description"


class Price(ServiceKitBaseModel):
    """A price as values, so different formats of the same price compare equal.

    A free price has amount 0 and no currency, period or unit, however the source wrote it.
    """

    amount: Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
    currency: Annotated[str | None, Field(pattern=CURRENCY_PATTERN)]
    period: PricePeriod | None
    unit: Annotated[
        str | None,
        StringConstraints(pattern=PRICE_UNIT_PATTERN, max_length=PRICE_UNIT_MAX_LENGTH),
        Field(description="What the amount is charged per, like seat; None for a flat price"),
    ]

    @model_validator(mode="after")
    def _only_paid_prices_have_currency_period_and_unit(self) -> Self:
        """:raises ValueError: If a paid price lacks its currency or period, or a free one has
        a currency, period or unit
        """
        if self.amount > 0 and (self.currency is None or self.period is None):
            raise ValueError("a price above 0 needs a currency and a period")
        if self.amount == 0 and (self.currency, self.period, self.unit) != (None, None, None):
            raise ValueError("a free price has no currency, period or unit")
        return self


class FieldChange(ServiceKitBaseModel):
    """A listing field's value before and after a change."""

    old: str | Price | None
    new: str | Price | None


Changes = dict[ListingField, FieldChange]
changes_adapter: Final[TypeAdapter[Changes]] = TypeAdapter(Changes)
