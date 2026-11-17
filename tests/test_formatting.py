from decimal import Decimal

import pytest

from competitor_pulse.formatting import format_price
from competitor_pulse.types import Price, PricePeriod


@pytest.mark.parametrize(
    ("amount", "currency", "period", "expected"),
    [
        ("29.00", "USD", PricePeriod.MONTH, "$29/mo"),
        ("29.99", "EUR", PricePeriod.YEAR, "€29.99/yr"),
        ("0.50", "GBP", PricePeriod.MONTH, "£0.50/mo"),
        ("49", "CHF", PricePeriod.ONE_TIME, "49 CHF one-time"),
        ("1200.00", "USD", PricePeriod.YEAR, "$1200/yr"),
    ],
)
def test_format_price(amount: str, currency: str, period: PricePeriod, expected: str):
    price = Price(amount=Decimal(amount), currency=currency, period=period)

    assert format_price(price) == expected
