from decimal import Decimal

import pytest

from competitor_pulse.formatting import format_price
from competitor_pulse.types import Price, PricePeriod


@pytest.mark.parametrize(
    ("amount", "currency", "period", "unit", "expected"),
    [
        ("29.00", "USD", PricePeriod.MONTH, None, "$29/mo"),
        ("29.99", "EUR", PricePeriod.YEAR, None, "€29.99/yr"),
        ("0.50", "GBP", PricePeriod.MONTH, None, "£0.50/mo"),
        ("49", "CHF", PricePeriod.ONE_TIME, None, "49 CHF one-time"),
        ("1200.00", "USD", PricePeriod.YEAR, None, "$1200/yr"),
        ("12.00", "USD", PricePeriod.MONTH, "seat", "$12/seat/mo"),
        ("2", "EUR", PricePeriod.MONTH, "1k events", "€2/1k events/mo"),
        ("0", None, None, None, "Free"),
    ],
)
def test_format_price(
    amount: str,
    currency: str | None,
    period: PricePeriod | None,
    unit: str | None,
    expected: str,
):
    price = Price(amount=Decimal(amount), currency=currency, period=period, unit=unit)

    assert format_price(price) == expected
