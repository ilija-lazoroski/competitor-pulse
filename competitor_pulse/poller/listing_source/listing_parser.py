"""Turns the listing source's noisy JSON into a Listing.

The source sends the same values in different forms from one request to the next: whitespace,
HTML entities and many ways to write a price. Anything we cannot read becomes a missing field
rather than a guess.
"""

import html
import re
from collections.abc import Mapping
from decimal import Decimal
from typing import Any, Final

from pydantic import ValidationError

from competitor_pulse.models import Listing
from competitor_pulse.types import ListingField, Price, PricePeriod

# Amounts always have two decimals, so 29 and 29.00 are written, stored and compared alike.
CENTS: Final[Decimal] = Decimal("0.01")
FREE_PRICE: Final[Price] = Price(
    amount=Decimal(0).quantize(CENTS), currency=None, period=None, unit=None
)

CURRENCY_BY_SYMBOL: Final[dict[str, str]] = {"$": "USD", "€": "EUR", "£": "GBP"}
PERIOD_BY_WORD: Final[dict[str, PricePeriod]] = {
    "mo": PricePeriod.MONTH,
    "month": PricePeriod.MONTH,
    "yr": PricePeriod.YEAR,
    "year": PricePeriod.YEAR,
}

_FREE: Final[re.Pattern[str]] = re.compile(r"free(?: forever)?", re.IGNORECASE)
# A currency symbol or ISO code, the amount, then what is left: "/seat/mo", "per month", ...
_PAID: Final[re.Pattern[str]] = re.compile(
    r"(?:(?P<symbol>[$€£])\s*|(?P<code>[A-Z]{3})\s+)"
    r"(?P<amount>\d{1,10}(?:\.\d{1,2})?)\s*"
    r"(?P<rest>.*)"
)
_SEPARATOR: Final[re.Pattern[str]] = re.compile(r"\s*(?:/|\bper\b)\s*", re.IGNORECASE)


def clean_text(value: Any) -> str | None:
    """Cleans a text field: decodes HTML entities and collapses whitespace.

    :param value: The field's value as the source sent it
    :returns: The cleaned text, or None if the value is not a string or is empty once cleaned
    """
    if not isinstance(value, str):
        return None
    text = html.unescape(value).replace("\xa0", " ")
    return " ".join(text.split()) or None


def parse_price(value: Any) -> Price | None:
    """Reads a price written in any of the source's forms, like $29/mo or EUR 8 per seat per month.

    Free, Free forever and an amount of 0 are all the same free price.

    :param value: The price field as the source sent it
    :returns: The price, or None if it is missing or in a form we cannot read
    """
    text = clean_text(value)
    if text is None:
        return None
    if _FREE.fullmatch(text):
        return FREE_PRICE

    paid = _PAID.fullmatch(text)
    if paid is None:
        return None
    amount = Decimal(paid["amount"]).quantize(CENTS)
    if amount == 0:
        return FREE_PRICE

    # "/seat/mo" splits into ["", "seat", "mo"]: a separator first, then the unit and the period.
    leading, *segments = _SEPARATOR.split(paid["rest"])
    if leading or not 1 <= len(segments) <= 2:
        return None
    period = PERIOD_BY_WORD.get(segments[-1].lower())
    if period is None:
        return None
    unit = _normalize_unit(segments[0]) if len(segments) == 2 else None

    currency = CURRENCY_BY_SYMBOL[paid["symbol"]] if paid["symbol"] else paid["code"]
    try:
        return Price(amount=amount, currency=currency, period=period, unit=unit)
    except ValidationError:
        return None


def parse_listing(body: Mapping[str, Any]) -> Listing:
    """Reads the fields we keep from the source's JSON body and ignores everything else.

    :param body: The JSON object the source answered with
    :returns: The listing; fields that are missing, empty or unreadable are None and listed in
              missing_fields
    """
    title = clean_text(body.get(ListingField.TITLE))
    tagline = clean_text(body.get(ListingField.TAGLINE))
    price = parse_price(body.get(ListingField.PRICE))
    description = clean_text(body.get(ListingField.DESCRIPTION))

    values = {
        ListingField.TITLE: title,
        ListingField.TAGLINE: tagline,
        ListingField.PRICE: price,
        ListingField.DESCRIPTION: description,
    }
    return Listing(
        title=title,
        tagline=tagline,
        price=price,
        description=description,
        missing_fields=[field for field, value in values.items() if value is None],
    )


def _normalize_unit(text: str) -> str:
    """Writes a unit one way, so that "Seats" and "seat" are the same unit.

    :param text: The unit as written in the price, like "seat" or "Seats"
    :returns: The unit in lowercase, single-spaced, with a plural "s" on the last word dropped
    """
    words = text.lower().split()
    if words and len(words[-1]) > 3 and words[-1].endswith("s") and not words[-1].endswith("ss"):
        words[-1] = words[-1][:-1]
    return " ".join(words)
