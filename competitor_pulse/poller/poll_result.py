from datetime import datetime

from competitor_pulse.errors import PollIncomplete, PollNotFound, poll_error_adapter
from competitor_pulse.listing_source import SourceError
from competitor_pulse.models import Listing, PollResult
from competitor_pulse.types import PollOutcome


def from_listing(listing: Listing, fetched_at: datetime) -> PollResult:
    """Describes a poll that got a listing: ok if complete, incomplete otherwise.

    :param listing: The listing the source sent
    :param fetched_at: When the source answered
    :returns: The poll result, with the missing fields as its error if there are any
    """
    if not listing.missing_fields:
        return PollResult(
            fetched_at=fetched_at, outcome=PollOutcome.OK, error=None, listing=listing
        )

    missing = ", ".join(listing.missing_fields)
    error = PollIncomplete(
        message=f"The source left out or sent unreadable: {missing}",
        fields=listing.missing_fields,
    )
    return PollResult(
        fetched_at=fetched_at, outcome=PollOutcome.INCOMPLETE, error=error, listing=listing
    )


def from_error(error: SourceError, fetched_at: datetime) -> PollResult:
    """Describes a poll that got no listing: not found, or failed.

    :param error: Why the source gave no listing
    :param fetched_at: When the poll gave up
    :returns: The poll result, with the error stored as its record
    :raises ValidationError: If the error's fields do not match a stored error record
    """
    record = poll_error_adapter.validate_python(error.structured_error)
    outcome = PollOutcome.NOT_FOUND if isinstance(record, PollNotFound) else PollOutcome.FAILED
    return PollResult(fetched_at=fetched_at, outcome=outcome, error=record, listing=None)
