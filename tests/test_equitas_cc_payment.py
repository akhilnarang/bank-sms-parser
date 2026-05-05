"""Equitas CC payment-received SMS parser tests.

Kept in its own module to avoid merge conflicts with the broader
``test_new_parsers.py`` file that several parallel agents are editing.
"""

import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from bank_sms_parser import parse_sms
from bank_sms_parser.exceptions import ParseError

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sms"


def _read(rel: str) -> str:
    return (FIXTURES_DIR / rel).read_text()


def test_parses_equitas_cc_payment_received() -> None:
    body = _read("equitas/cc_payment_received.txt")
    result = parse_sms("equitas", body)
    assert result.email_type == "equitas_cc_payment_alert"
    assert result.bank == "equitas"
    txn = result.transaction
    assert txn is not None
    assert txn.direction == "credit"
    assert txn.amount.amount == Decimal("12345.00")
    assert txn.amount.currency == "INR"
    assert txn.card_mask == "XX9999"
    assert txn.counterparty == "Payment received"
    assert txn.channel == "card"
    assert txn.transaction_date == datetime.date(2026, 5, 5)
    # Payment-received notifications carry no time component.
    assert txn.transaction_time is None
    assert txn.account_mask is None
    assert txn.balance is None


def test_existing_spend_alert_does_not_match_payment_received() -> None:
    """The pre-existing 'spent' shape must still parse as the spend alert,
    not as the new payment-received parser — the two patterns are mutually
    exclusive and the spend body has no 'was received' / 'was credited'
    markers."""
    body = _read("equitas/cc_spend.txt")
    result = parse_sms("equitas", body)
    assert result.email_type == "equitas_cc_transaction_alert"
    assert result.transaction is not None
    assert result.transaction.direction == "debit"


def test_payment_received_synthetic_negative_raises_parse_error() -> None:
    """A spend-alert-shaped body without the payment-received markers
    must not be (mis)parsed by the payment-received parser. We assert the
    dispatcher's overall behaviour: this body must parse as a spend alert,
    proving the payment-received pattern correctly rejected it."""
    body = (
        "INR 30.00 spent on Equitas CC XX0000 at SOME MERCHANT on "
        "01-05-2026 07:53:18 PM. Available limit is INR. 99,999.99."
    )
    result = parse_sms("equitas", body)
    assert result.email_type == "equitas_cc_transaction_alert"


def test_payment_received_truncated_body_raises_parse_error() -> None:
    """A truncated payment-received body that lacks the card mask must
    raise ParseError rather than silently dropping the field."""
    body = "INR 12,345.00 was received on 05/05/2026 and was credited to your"
    with pytest.raises(ParseError):
        parse_sms("equitas", body)
