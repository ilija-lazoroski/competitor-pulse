from competitor_pulse.app.competitors import (
    CompetitorCreate,
    add_competitor,
    list_competitors,
    list_snapshots,
    remove_competitor,
)
from competitor_pulse.app.health import HealthResponse, UnavailableResponse, health_db
from competitor_pulse.configuration import (
    ApiConfiguration,
    CompetitorPulseConfiguration,
    DatabaseConfiguration,
    PollerConfiguration,
)
from competitor_pulse.database import to_sqlalchemy_url
from competitor_pulse.models import Competitor, Snapshot

# Pydantic fields, settings and validators are read by Pydantic/FastAPI, not by our code.
Competitor.id
CompetitorCreate.id
Competitor.changed_recently
Snapshot.fetched_at
Snapshot.title
Snapshot.tagline
Snapshot.price
Snapshot.description
Snapshot.changed
Snapshot.summary
Snapshot.outcome
Snapshot.summary_status
HealthResponse.status
UnavailableResponse.status
CompetitorPulseConfiguration.model_config
DatabaseConfiguration.model_config
DatabaseConfiguration._max_size_is_not_below_min_size
ApiConfiguration.model_config
ApiConfiguration._page_size_is_not_above_max_page_size
PollerConfiguration._pause_is_not_above_max_pause

# Route functions are called by FastAPI.
list_competitors
add_competitor
remove_competitor
list_snapshots
health_db

# Exception handlers are called by FastAPI.
_.competitor_not_tracked_handler  # type: ignore[name-defined]  # noqa: F821
_.competitor_already_tracked_handler  # type: ignore[name-defined]  # noqa: F821
_.invalid_page_size_handler  # type: ignore[name-defined]  # noqa: F821

# Used by migrations/env.py, which vulture does not scan.
to_sqlalchemy_url

# Step 1 (data model): used by the poller, the LLM worker and the API in the next steps.
from competitor_pulse.errors import (  # noqa: E402
    ErrorRecord,
    PollConnectionError,
    PollHttpError,
    PollIncomplete,
    PollInvalidBody,
    PollRateLimited,
    PollTimeout,
    SummaryConnectionError,
    SummaryHttpError,
    SummaryTimeout,
    SummaryUnusableAnswer,
    poll_error_adapter,
    summary_error_adapter,
)
from competitor_pulse.tables import snapshots  # noqa: E402
from competitor_pulse.types import (  # noqa: E402
    FieldChange,
    ListingField,
    PollOutcome,
    Price,
    PricePeriod,
    SummaryStatus,
    changes_adapter,
)

ListingField.TITLE
ListingField.TAGLINE
ListingField.PRICE
ListingField.DESCRIPTION
PollOutcome.OK
PollOutcome.INCOMPLETE
PollOutcome.NOT_FOUND
PollOutcome.FAILED
PricePeriod.MONTH
PricePeriod.YEAR
PricePeriod.ONE_TIME
SummaryStatus.READY
SummaryStatus.NO_CHANGE
SummaryStatus.BASELINE
SummaryStatus.POLL_FAILED
SummaryStatus.PENDING
SummaryStatus.LLM_FAILED
SummaryStatus.LLM_UNUSABLE
SummaryStatus.CAP_REACHED
FieldChange.old
FieldChange.new
Price.amount
Price.currency
Price.period
Price.unit
Price._only_paid_prices_have_currency_period_and_unit
ErrorRecord.message
SummaryConnectionError.kind
SummaryHttpError.kind
SummaryHttpError.status
SummaryTimeout.kind
SummaryTimeout.after_seconds
SummaryUnusableAnswer.kind
PollConnectionError.kind
PollHttpError.kind
PollHttpError.status
PollIncomplete.kind
PollIncomplete.fields
PollInvalidBody.kind
PollRateLimited.kind
PollRateLimited.retry_after_seconds
PollTimeout.kind
PollTimeout.after_seconds
changes_adapter
poll_error_adapter
summary_error_adapter
snapshots

from competitor_pulse.configuration import SourceConfiguration  # noqa: E402
from competitor_pulse.errors import PollNotFound  # noqa: E402
from competitor_pulse.models import Listing  # noqa: E402
from competitor_pulse.poller.listing_source import HttpListingSource  # noqa: E402

# Step 3 (listing source): the parser is called by the source client and the poller next.
from competitor_pulse.poller.listing_source.listing_parser import parse_listing  # noqa: E402

parse_listing
Listing.missing_fields
SourceConfiguration.model_config
PollNotFound.kind
HttpListingSource.from_configuration
HttpListingSource.fetch
HttpListingSource.close
