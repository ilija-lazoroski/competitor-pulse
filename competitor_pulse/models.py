"""The models passed between the parts of the application and returned by the API."""

from datetime import datetime

from pydantic import Field
from pydantic.alias_generators import to_camel
from service_kit import ServiceKitBaseModel

from competitor_pulse.errors import PollError
from competitor_pulse.types import (
    Changes,
    CompetitorId,
    ListingField,
    PollOutcome,
    Price,
    SummaryStatus,
)


class ApiModel(ServiceKitBaseModel):
    """A model whose JSON uses camelCase (fetchedAt), as in the brief's contract."""

    model_config = {
        **ServiceKitBaseModel.model_config,
        "alias_generator": to_camel,
        "populate_by_name": True,
    }


class Competitor(ApiModel):
    """A tracked competitor."""

    id: CompetitorId
    created_at: datetime
    last_changed_at: datetime | None
    changed_recently: bool = Field(
        description="Had a change that matters within the last CP_API_RECENT_CHANGE_HOURS"
    )


class ChangeView(ApiModel):
    """A changed field's value before and after, formatted for people; None if not there."""

    old: str | None
    new: str | None


class Snapshot(ApiModel):
    """One poll of a competitor: the listing it found, or why it found none."""

    id: int = Field(description="Pass as `before` to get the next, older page")
    fetched_at: datetime
    outcome: PollOutcome
    error: str | None = Field(description="Why the poll returned no or an incomplete listing")
    title: str | None
    tagline: str | None
    price: str | None = Field(examples=["$29/mo"])
    description: str | None
    changed: bool = Field(description="Differs in a way that matters from the previous listing")
    changes: dict[ListingField, ChangeView] | None = Field(
        description="What changed, by field; shown when there is no summary"
    )
    summary: str | None = Field(description="Plain-English summary of the change, if available")
    summary_status: SummaryStatus = Field(description="Whether there is a summary, and if not, why")
    summary_error: str | None = Field(description="Why the LLM gave no summary, if it failed")


class ListingValues(ServiceKitBaseModel):
    """The fields of a listing that we keep and compare; None where a value is not known.

    Stored in competitors.known_listing as the last value the source sent for each field.
    """

    title: str | None
    tagline: str | None
    price: Price | None
    description: str | None


class Listing(ListingValues):
    """A competitor's listing as read from the source, cleaned up; unreadable fields are None."""

    missing_fields: list[ListingField] = Field(
        description="Fields the source left out, sent empty or sent in a form we cannot read"
    )


class PollResult(ServiceKitBaseModel):
    """What one poll of a competitor found, ready to be stored as a snapshot."""

    fetched_at: datetime
    outcome: PollOutcome
    error: PollError | None = Field(description="Why the listing is missing or incomplete")
    listing: Listing | None = Field(description="The listing, if the source sent one")


class PendingSummary(ServiceKitBaseModel):
    """A snapshot whose change waits for the LLM's summary."""

    snapshot_id: int
    competitor_id: CompetitorId
    changes: Changes
