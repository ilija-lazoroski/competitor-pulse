"""What the competitor repository returns: the API's response shapes."""

from datetime import datetime

from pydantic import Field
from pydantic.alias_generators import to_camel
from service_kit import ServiceKitBaseModel

from competitor_pulse.types import CompetitorId, PollOutcome, SummaryStatus


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
    summary: str | None = Field(description="Plain-English summary of the change, if available")
    summary_status: SummaryStatus = Field(description="Whether there is a summary, and if not, why")
    summary_error: str | None = Field(description="Why the LLM gave no summary, if it failed")
