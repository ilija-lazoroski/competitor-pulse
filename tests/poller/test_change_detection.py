from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from competitor_pulse.errors import PollNotFound, PollTimeout
from competitor_pulse.models import Listing, PollResult
from competitor_pulse.poller.change_detection import (
    DELISTED_SUMMARY,
    RELISTED_UNCHANGED_SUMMARY,
    compare,
    decide,
)
from competitor_pulse.types import FieldChange, ListingField, PollOutcome, Price, PricePeriod

FETCHED_AT = datetime(2026, 9, 10, 12, tzinfo=UTC)
PRICE = Price(amount=Decimal("39.00"), currency="USD", period=PricePeriod.MONTH, unit=None)
CHEAPER = Price(amount=Decimal("29.00"), currency="USD", period=PricePeriod.MONTH, unit=None)
LISTING = Listing(
    title="Acme CRM",
    tagline="Simple CRM for small teams",
    price=PRICE,
    description="Track leads & deals in one place.",
    missing_fields=[],
)


def listing(**fields: Any) -> Listing:
    return LISTING.model_copy(update=fields)


def found(current: Listing, outcome: PollOutcome = PollOutcome.OK) -> PollResult:
    return PollResult(fetched_at=FETCHED_AT, outcome=outcome, error=None, listing=current)


NOT_FOUND = PollResult(
    fetched_at=FETCHED_AT,
    outcome=PollOutcome.NOT_FOUND,
    error=PollNotFound(message="The source does not list 'acme-crm'"),
    listing=None,
)
FAILED = PollResult(
    fetched_at=FETCHED_AT,
    outcome=PollOutcome.FAILED,
    error=PollTimeout(message="The source did not answer within 10s", after_seconds=10),
    listing=None,
)


@pytest.mark.parametrize(
    ("current", "expected"),
    [
        (listing(), {}),
        (listing(title="Acme CRM Pro"), {"title": ("Acme CRM", "Acme CRM Pro")}),
        (listing(title="ACME CRM"), {"title": ("Acme CRM", "ACME CRM")}),
        (
            listing(tagline="The CRM small teams love"),
            {"tagline": (LISTING.tagline, "The CRM small teams love")},
        ),
        (listing(price=CHEAPER), {"price": (PRICE, CHEAPER)}),
        (
            listing(price=PRICE.model_copy(update={"unit": "seat"})),
            {"price": (PRICE, PRICE.model_copy(update={"unit": "seat"}))},
        ),
        (
            listing(description="Track leads & deals."),
            {"description": (LISTING.description, "Track leads & deals.")},
        ),
        # Unreadable in this poll: unknown, not removed.
        (listing(price=None, tagline=None), {}),
        (listing(price=None, title="Acme CRM Pro"), {"title": ("Acme CRM", "Acme CRM Pro")}),
    ],
)
def test_compare_lists_changed_fields(current: Listing, expected: dict):
    changes = compare(LISTING, current)

    assert {field: (c.old, c.new) for field, c in changes.items()} == expected


def test_the_same_price_written_differently_is_no_change():
    # 39 and 39.00 parse to equal values, so they compare equal.
    same = PRICE.model_copy(update={"amount": Decimal("39")})

    assert compare(LISTING, listing(price=same)) == {}


def test_compare_against_no_listing_removes_every_known_field():
    previous = listing(tagline=None)

    changes = compare(previous, None)

    assert changes == {
        ListingField.TITLE: FieldChange(old="Acme CRM", new=None),
        ListingField.PRICE: FieldChange(old=PRICE, new=None),
        ListingField.DESCRIPTION: FieldChange(old=LISTING.description, new=None),
    }


@pytest.mark.parametrize(
    ("result", "previous", "previously_delisted", "changed", "status", "summary"),
    [
        # The first listing is the baseline.
        (found(LISTING), None, False, False, "baseline", None),
        (found(LISTING), LISTING, False, False, "no_change", None),
        (found(listing(price=CHEAPER)), LISTING, False, True, "pending", None),
        (
            found(listing(price=None), PollOutcome.INCOMPLETE),
            LISTING,
            False,
            False,
            "no_change",
            None,
        ),
        # A failed poll changes nothing.
        (FAILED, LISTING, False, False, "poll_failed", None),
        (FAILED, None, False, False, "poll_failed", None),
        # Not found: the first time after a listing is a change with a fixed summary.
        (NOT_FOUND, LISTING, False, True, "ready", DELISTED_SUMMARY),
        (NOT_FOUND, LISTING, True, False, "poll_failed", None),
        (NOT_FOUND, None, False, False, "poll_failed", None),
        # Back after not found: unchanged gets a fixed summary, changed waits for the LLM.
        (found(LISTING), LISTING, True, True, "ready", RELISTED_UNCHANGED_SUMMARY),
        (found(listing(price=CHEAPER)), LISTING, True, True, "pending", None),
    ],
)
def test_decide(
    result: PollResult,
    previous: Listing | None,
    previously_delisted: bool,
    changed: bool,
    status: str,
    summary: str | None,
):
    decision = decide(result, previous, previously_delisted)

    assert (decision.changed, decision.summary_status, decision.summary) == (
        changed,
        status,
        summary,
    )
    assert (decision.changes is not None) == changed
