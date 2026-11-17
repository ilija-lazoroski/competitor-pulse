"""Value types shared by the database, the poller and the API.

The enums are stored as native PostgreSQL enums; Changes is stored in snapshots.changes (jsonb).
"""

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Final, TypeAlias

from pydantic import Field, StringConstraints, TypeAdapter
from service_kit import ServiceKitBaseModel

CURRENCY_PATTERN: Final = r"^[A-Z]{3}$"
COMPETITOR_ID_PATTERN: Final = r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$"

# Lowercase slugs like "acme-crm". The id goes into the source URL (/listings/{id}), so
# slashes, dots and other path characters must never get through.
CompetitorId: TypeAlias = Annotated[str, StringConstraints(pattern=COMPETITOR_ID_PATTERN)]


class PollOutcome(StrEnum):
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
    MONTH = "month"
    YEAR = "year"
    ONE_TIME = "one_time"


class ListingField(StrEnum):
    TITLE = "title"
    TAGLINE = "tagline"
    PRICE = "price"
    DESCRIPTION = "description"


class Price(ServiceKitBaseModel):
    amount: Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
    currency: Annotated[str, Field(pattern=CURRENCY_PATTERN)]
    period: PricePeriod


class FieldChange(ServiceKitBaseModel):
    old: str | Price | None
    new: str | Price | None


# snapshots.changes: what changed, per field.
Changes = dict[ListingField, FieldChange]
changes_adapter: Final = TypeAdapter(Changes)
