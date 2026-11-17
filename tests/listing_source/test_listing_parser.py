from decimal import Decimal
from typing import Any

import pytest

from competitor_pulse.listing_source.listing_parser import (
    FREE_PRICE,
    clean_text,
    parse_listing,
    parse_price,
)
from competitor_pulse.types import ListingField, Price, PricePeriod

MONTH = PricePeriod.MONTH
YEAR = PricePeriod.YEAR


def paid(amount: str, currency: str, period: PricePeriod, unit: str | None = None) -> Price:
    return Price(amount=Decimal(amount), currency=currency, period=period, unit=unit)


# Every price string the running source sent while we probed it, and what each one means.
OBSERVED_PRICES = [
    ("$29/mo", paid("29", "USD", MONTH)),
    ("$29.00/mo", paid("29", "USD", MONTH)),
    ("$29 / month", paid("29", "USD", MONTH)),
    ("USD 29 per month", paid("29", "USD", MONTH)),
    ("$39/mo", paid("39", "USD", MONTH)),
    ("$39.00/mo", paid("39", "USD", MONTH)),
    ("$39 / month", paid("39", "USD", MONTH)),
    ("USD 39 per month", paid("39", "USD", MONTH)),
    ("$49/mo", paid("49", "USD", MONTH)),
    ("$49.00/mo", paid("49", "USD", MONTH)),
    ("$49 / month", paid("49", "USD", MONTH)),
    ("USD 49 per month", paid("49", "USD", MONTH)),
    ("$59/mo", paid("59", "USD", MONTH)),
    ("$59.00/mo", paid("59", "USD", MONTH)),
    ("$59 / month", paid("59", "USD", MONTH)),
    ("USD 59 per month", paid("59", "USD", MONTH)),
    ("$199/mo", paid("199", "USD", MONTH)),
    ("$199.00/mo", paid("199", "USD", MONTH)),
    ("$199 / month", paid("199", "USD", MONTH)),
    ("USD 199 per month", paid("199", "USD", MONTH)),
    ("$12/seat/mo", paid("12", "USD", MONTH, "seat")),
    ("$12.00/seat/mo", paid("12", "USD", MONTH, "seat")),
    ("$12 / seat / month", paid("12", "USD", MONTH, "seat")),
    ("USD 12 per seat per month", paid("12", "USD", MONTH, "seat")),
    ("€8/seat/mo", paid("8", "EUR", MONTH, "seat")),
    ("€8.00/seat/mo", paid("8", "EUR", MONTH, "seat")),
    ("€8 / seat / month", paid("8", "EUR", MONTH, "seat")),
    ("EUR 8 per seat per month", paid("8", "EUR", MONTH, "seat")),
    ("€10/seat/mo", paid("10", "EUR", MONTH, "seat")),
    ("€10.00/seat/mo", paid("10", "EUR", MONTH, "seat")),
    ("€10 / seat / month", paid("10", "EUR", MONTH, "seat")),
    ("EUR 10 per seat per month", paid("10", "EUR", MONTH, "seat")),
    ("€96/yr", paid("96", "EUR", YEAR)),
    ("€96.00/yr", paid("96", "EUR", YEAR)),
    ("€96 / year", paid("96", "EUR", YEAR)),
    ("EUR 96 per year", paid("96", "EUR", YEAR)),
    ("Free", FREE_PRICE),
    ("Free forever", FREE_PRICE),
    ("$0/mo", FREE_PRICE),
]


@pytest.mark.parametrize(("raw", "expected"), OBSERVED_PRICES)
def test_observed_prices_are_read(raw: str, expected: Price):
    assert parse_price(raw) == expected


@pytest.mark.parametrize("raw", ["$29/mo", "$29.00/mo", "USD 29 per month", "Free", "$0/mo"])
def test_amounts_always_have_two_decimals(raw: str):
    price = parse_price(raw)

    assert price is not None
    assert price.amount.as_tuple().exponent == -2


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Forms we did not see but read the same way.
        ("USD 29/mo", paid("29", "USD", MONTH)),
        ("£5 per month", paid("5", "GBP", MONTH)),
        ("$5 / user / month", paid("5", "USD", MONTH, "user")),
        ("$5 / Seats / Month", paid("5", "USD", MONTH, "seat")),
        ("USD 2 per 1k events per month", paid("2", "USD", MONTH, "1k event")),
        ("CHF 120 per year", paid("120", "CHF", YEAR)),
        ("  $29&nbsp;/&nbsp;mo\n", paid("29", "USD", MONTH)),
        ("FREE", FREE_PRICE),
    ],
)
def test_other_forms_of_the_same_grammar_are_read(raw: str, expected: Price):
    assert parse_price(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "   ",
        29,
        {"amount": 29, "currency": "USD", "period": "month"},
        "29",
        "$29",
        "29 USD per month",
        "$29 per week",
        "$29/mo/seat/extra",
        "$29.999/mo",
        "Contact sales",
        "Free trial",
        "$5 / per-seat / month",
        "$5 / a very long unit name here / month",
    ],
)
def test_unreadable_prices_are_none(raw: Any):
    assert parse_price(raw) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Acme CRM ", "Acme CRM"),
        ("Acme CRM\n", "Acme CRM"),
        ("Acme  CRM", "Acme CRM"),
        ("Acme&nbsp;CRM", "Acme CRM"),
        ("Track leads &amp; deals in one place.", "Track leads & deals in one place."),
        ("Track  leads  &  deals in  one place.", "Track leads & deals in one place."),
    ],
)
def test_text_noise_is_cleaned(raw: str, expected: str):
    assert clean_text(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "  \n ", "&nbsp;", 42])
def test_empty_or_non_text_is_none(raw: Any):
    assert clean_text(raw) is None


def test_listing_keeps_our_fields_and_ignores_the_rest():
    body = {
        "id": "acme-crm",
        "title": "  Acme CRM ",
        "tagline": "Simple&nbsp;CRM for small teams",
        "price": "USD 29 per month",
        "description": "Track leads &amp; deals in one place.\n",
        "viewerCount": 77,
        "promoBanner": "Spring sale: 20% off annual plans",
        "cache": {"hit": True, "ageSeconds": 120},
    }

    listing = parse_listing(body)

    assert listing.title == "Acme CRM"
    assert listing.tagline == "Simple CRM for small teams"
    assert listing.price == paid("29", "USD", MONTH)
    assert listing.description == "Track leads & deals in one place."
    assert listing.missing_fields == []


def test_listing_reports_missing_empty_and_unreadable_fields():
    body = {"tagline": None, "price": "Contact sales", "description": ""}

    listing = parse_listing(body)

    assert listing.missing_fields == [
        ListingField.TITLE,
        ListingField.TAGLINE,
        ListingField.PRICE,
        ListingField.DESCRIPTION,
    ]
