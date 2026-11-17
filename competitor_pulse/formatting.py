from typing import Final

from competitor_pulse.types import Price, PricePeriod

CURRENCY_SYMBOLS: Final = {"USD": "$", "EUR": "€", "GBP": "£"}
PERIOD_SUFFIXES: Final = {
    PricePeriod.MONTH: "/mo",
    PricePeriod.YEAR: "/yr",
    PricePeriod.ONE_TIME: " one-time",
}


def format_price(price: Price) -> str:
    """Formats a price for people, like $29/mo, $12/seat/mo, €29.99/yr or Free.

    :param price: The price to format
    :returns: The price with a currency symbol where one is known; whole amounts lose their
              decimals
    """
    if price.currency is None or price.period is None:
        return "Free"
    amount = price.amount
    number = f"{amount:.0f}" if amount == amount.to_integral_value() else f"{amount:.2f}"
    symbol = CURRENCY_SYMBOLS.get(price.currency)
    money = f"{symbol}{number}" if symbol else f"{number} {price.currency}"
    unit = f"/{price.unit}" if price.unit else ""
    return money + unit + PERIOD_SUFFIXES[price.period]


def format_value(value: str | Price | None) -> str | None:
    """Formats a listing field's value for people.

    :param value: A text field, a price, or None for a value that is not there
    :returns: The text as it is, the price formatted, or None
    """
    return format_price(value) if isinstance(value, Price) else value
