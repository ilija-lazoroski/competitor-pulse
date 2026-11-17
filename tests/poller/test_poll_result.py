from datetime import UTC, datetime

import pytest

from competitor_pulse.errors import PollHttpError, PollIncomplete, PollNotFound, PollTimeout
from competitor_pulse.listing_source import (
    ListingNotFoundError,
    SourceConnectionError,
    SourceError,
    SourceHttpError,
    SourceInvalidBodyError,
    SourceTimeoutError,
)
from competitor_pulse.models import Listing
from competitor_pulse.poller.poll_result import from_error, from_listing
from competitor_pulse.types import ListingField, PollOutcome

FETCHED_AT = datetime(2026, 9, 10, 12, tzinfo=UTC)
LISTING = Listing(
    title="Acme CRM",
    tagline="Simple CRM for small teams",
    price=None,
    description="Track leads and deals in one place.",
    missing_fields=[],
)


def test_complete_listing_is_ok():
    result = from_listing(LISTING, FETCHED_AT)

    assert (result.outcome, result.error, result.listing) == (PollOutcome.OK, None, LISTING)


def test_listing_with_missing_fields_is_incomplete():
    listing = LISTING.model_copy(
        update={"missing_fields": [ListingField.TAGLINE, ListingField.PRICE]}
    )

    result = from_listing(listing, FETCHED_AT)

    assert result.outcome == PollOutcome.INCOMPLETE
    assert result.listing == listing
    assert result.error == PollIncomplete(
        message="The source left out or sent unreadable: tagline, price",
        fields=[ListingField.TAGLINE, ListingField.PRICE],
    )


def test_not_found_is_its_own_outcome():
    result = from_error(ListingNotFoundError("acme-crm"), FETCHED_AT)

    assert result.outcome == PollOutcome.NOT_FOUND
    assert isinstance(result.error, PollNotFound)
    assert result.listing is None


@pytest.mark.parametrize(
    ("error", "record"),
    [
        (SourceTimeoutError(10), PollTimeout),
        (SourceHttpError(503), PollHttpError),
        (SourceConnectionError("connection refused"), None),
        (SourceInvalidBodyError("the body is not JSON"), None),
    ],
)
def test_other_source_errors_are_failed_polls(error: SourceError, record: type | None):
    result = from_error(error, FETCHED_AT)

    assert result.outcome == PollOutcome.FAILED
    assert result.listing is None
    assert result.error is not None
    assert result.error.message == error.message
    if record is not None:
        assert isinstance(result.error, record)
