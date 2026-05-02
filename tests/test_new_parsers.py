"""Fixture-driven tests: one parametrized case per real SMS shape."""

import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from bank_sms_parser import parse_sms

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sms"


def _read(rel: str) -> str:
    return (FIXTURES_DIR / rel).read_text()


def _assert_matches(parsed, expected: dict) -> None:
    """Assert the per-field expected dict matches the parsed.transaction.

    Field 'email_type' is on parsed, not parsed.transaction.
    'amount' and 'currency' compare against parsed.transaction.amount.
    'balance' compares against parsed.transaction.balance.amount (if set).
    Other fields compare directly.
    """
    assert parsed.email_type == expected["email_type"]
    txn = parsed.transaction
    assert txn is not None, "parsed.transaction was None"
    if "direction" in expected:
        assert txn.direction == expected["direction"]
    if "amount" in expected:
        assert txn.amount.amount == expected["amount"]
    if "currency" in expected:
        assert txn.amount.currency == expected["currency"]
    if "card_mask" in expected:
        assert txn.card_mask == expected["card_mask"]
    if "account_mask" in expected:
        assert txn.account_mask == expected["account_mask"]
    if "counterparty" in expected:
        assert txn.counterparty == expected["counterparty"]
    if "balance" in expected:
        assert txn.balance is not None
        assert txn.balance.amount == expected["balance"]
    if "transaction_date" in expected:
        assert txn.transaction_date == expected["transaction_date"]
    if "transaction_time" in expected:
        assert txn.transaction_time == expected["transaction_time"]
    if "channel" in expected:
        assert txn.channel == expected["channel"]
    if "reference_number" in expected:
        assert txn.reference_number == expected["reference_number"]


@pytest.mark.parametrize("bank, fixture, expected", [
    ("hdfc", "hdfc/dc_spend.txt", {
        "email_type": "hdfc_dc_transaction_alert",
        "direction": "debit",
        "amount": Decimal("3000"),
        "currency": "INR",
        "card_mask": "x0000",
        "counterparty": "PZCREDIT0000000",
        "balance": Decimal("142.26"),
        "transaction_date": datetime.date(2026, 5, 2),
        "transaction_time": datetime.time(0, 17, 56),
    }),
    ("equitas", "equitas/cc_spend.txt", {
        "email_type": "equitas_cc_transaction_alert",
        "direction": "debit",
        "amount": Decimal("30.00"),
        "currency": "INR",
        "card_mask": "XX0000",
        "counterparty": "CITY REALTY AND DEVELO",
        "balance": Decimal("99999.99"),
        "transaction_date": datetime.date(2026, 5, 1),
        "transaction_time": datetime.time(19, 53, 18),
    }),
    ("axis", "axis/cc_payment_received.txt", {
        "email_type": "axis_cc_payment_received_alert",
        "direction": "credit",
        "amount": Decimal("15000"),
        "currency": "INR",
        "card_mask": "XX0000",
        "transaction_date": datetime.date(2026, 5, 2),
    }),
])
def test_parses_real_sms(bank, fixture, expected) -> None:
    body = _read(fixture)
    result = parse_sms(bank, body)
    _assert_matches(result, expected)
