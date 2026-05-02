"""Tests for pydantic models."""

import datetime
from decimal import Decimal

import pytest
from bank_sms_parser.models import Money, SmsTransactionAlert
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


class TestSmsTransactionAlert:
    def _minimal(self) -> SmsTransactionAlert:
        return SmsTransactionAlert(
            direction="debit",
            amount=Money(amount=Decimal("100"), currency="INR"),
        )

    def test_minimal_construction(self) -> None:
        t = self._minimal()
        assert t.direction == "debit"
        assert t.amount.amount == Decimal("100")
        # Defaults
        assert t.transaction_date is None
        assert t.transaction_time is None
        assert t.counterparty is None
        assert t.balance is None
        assert t.reference_number is None
        assert t.account_mask is None
        assert t.card_mask is None
        assert t.channel is None
        assert t.raw_description is None

    def test_direction_must_be_in_literal(self) -> None:
        with pytest.raises(ValidationError):
            SmsTransactionAlert(
                direction="invalid",  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
                amount=Money(amount=Decimal("1")),
            )

    def test_direction_credit_and_declined_allowed(self) -> None:
        for d in ("debit", "credit", "declined"):
            t = SmsTransactionAlert(
                direction=d,  # type: ignore[arg-type]
                amount=Money(amount=Decimal("1")),
            )
            assert t.direction == d

    def test_raw_description_excluded_from_dump(self) -> None:
        t = SmsTransactionAlert(
            direction="debit",
            amount=Money(amount=Decimal("1")),
            raw_description="debug only",
        )
        dumped = t.model_dump()
        assert "raw_description" not in dumped

    def test_raw_description_excluded_from_repr(self) -> None:
        t = SmsTransactionAlert(
            direction="debit",
            amount=Money(amount=Decimal("1")),
            raw_description="debug only",
        )
        assert "debug only" not in repr(t)

    def test_full_construction(self) -> None:
        t = SmsTransactionAlert(
            direction="debit",
            amount=Money(amount=Decimal("3000")),
            transaction_date=datetime.date(2026, 5, 2),
            transaction_time=datetime.time(0, 17, 56),
            counterparty="MERCHANT",
            balance=Money(amount=Decimal("142.26")),
            reference_number="000000000000",
            account_mask="XX0000",
            card_mask="x0000",
            channel="card",
        )
        assert t.transaction_date == datetime.date(2026, 5, 2)
        assert t.channel == "card"
