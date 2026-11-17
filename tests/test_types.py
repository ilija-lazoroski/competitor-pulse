import pytest
from pydantic import ValidationError

from competitor_pulse.types import Price


@pytest.mark.parametrize(
    "price",
    [
        {"amount": "29", "currency": None, "period": "month", "unit": None},
        {"amount": "29", "currency": "USD", "period": None, "unit": None},
        {"amount": "0", "currency": "USD", "period": None, "unit": None},
        {"amount": "0", "currency": None, "period": "month", "unit": None},
        {"amount": "0", "currency": None, "period": None, "unit": "seat"},
    ],
)
def test_price_is_either_paid_or_free(price: dict):
    with pytest.raises(ValidationError, match="paid|free|above 0"):
        Price.model_validate(price)
