"""Tests for pydantic models."""

from decimal import Decimal

import pytest
from bank_sms_parser.models import Money
from pydantic import ValidationError


class TestMoney:
    def test_default_currency_is_inr(self) -> None:
        m = Money(amount=Decimal("100"))
        assert m.currency == "INR"

    def test_explicit_currency(self) -> None:
        m = Money(amount=Decimal("106.20"), currency="USD")
        assert m.currency == "USD"

    def test_amount_must_be_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            Money(amount=Decimal("-1"))

    def test_amount_zero_is_allowed(self) -> None:
        m = Money(amount=Decimal("0"))
        assert m.amount == Decimal("0")

    def test_decimal_exact(self) -> None:
        m = Money(amount=Decimal("1.05"))
        assert m.amount == Decimal("1.05")
