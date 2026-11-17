from typing import Final

from competitor_pulse.types import Price, PricePeriod

CURRENCY_SYMBOLS: Final = {"USD": "$", "EUR": "€", "GBP": "£"}
PERIOD_SUFFIXES: Final = {
    PricePeriod.MONTH: "/mo",
    PricePeriod.YEAR: "/yr",
    PricePeriod.ONE_TIME: " one-time",
}


def format_price(price: Price) -> str:
    """$29/mo, €29.99/yr, 49 CHF one-time: whole amounts lose their decimals."""
    amount = price.amount
    number = f"{amount:.0f}" if amount == amount.to_integral_value() else f"{amount:.2f}"
    symbol = CURRENCY_SYMBOLS.get(price.currency)
    money = f"{symbol}{number}" if symbol else f"{number} {price.currency}"
    return money + PERIOD_SUFFIXES[price.period]
