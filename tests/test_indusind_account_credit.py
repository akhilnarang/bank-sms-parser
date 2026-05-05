"""Tests for the IndusInd account UPI-credit SMS parser.

Lives in its own module so parallel agents touching ``test_new_parsers.py``
do not collide with the credit-shape coverage. Mirrors the conventions in
``test_new_parsers.py`` (fixture-driven body, per-field assertions on
``parsed.transaction``).
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


def test_upi_credit_happy_path() -> None:
    """All fields surface from the UPI-credit body, including balance/RRN/VPA."""
    body = _read("indusind/account_upi_credit.txt")
    result = parse_sms("indusind", body)

    assert result.email_type == "indusind_account_upi_credit_alert"
    assert result.bank == "indusind"
    txn = result.transaction
    assert txn is not None
    assert txn.direction == "credit"
    assert txn.amount.amount == Decimal("12345.00")
    assert txn.amount.currency == "INR"
    assert txn.account_mask == "XX0000"
    assert txn.counterparty == "9999999999@bank"
    assert txn.reference_number == "000000000000"
    assert txn.channel == "upi"
    assert txn.balance is not None
    assert txn.balance.amount == Decimal("12345.00")
    assert txn.balance.currency == "INR"


def test_upi_credit_received_at_fills_transaction_date_in_ist() -> None:
    """Body has no date — received_at (UTC) converts to IST and fills the field."""
    body = _read("indusind/account_upi_credit.txt")
    # 2026-04-30 21:30 UTC == 2026-05-01 03:00 IST (crosses the day boundary).
    received = datetime.datetime(2026, 4, 30, 21, 30, tzinfo=datetime.UTC)
    result = parse_sms("indusind", body, received_at=received)

    txn = result.transaction
    assert txn is not None
    assert result.email_type == "indusind_account_upi_credit_alert"
    assert txn.transaction_date == datetime.date(2026, 5, 1)
    assert txn.transaction_time == datetime.time(3, 0)


def test_upi_credit_no_received_at_leaves_date_none() -> None:
    """Without received_at, the parser must not fabricate a date/time."""
    body = _read("indusind/account_upi_credit.txt")
    result = parse_sms("indusind", body)

    txn = result.transaction
    assert txn is not None
    assert txn.transaction_date is None
    assert txn.transaction_time is None


def test_imps_debit_still_parses_as_legacy_alert() -> None:
    """Regression: the existing IMPS-debit shape keeps its email_type & direction.

    The new credit parser is verb-restricted to ``credited``; the IMPS body
    uses ``debited with`` and must fall through to
    ``IndusindAccountTransactionAlertParser``.
    """
    body = _read("indusind/account_imps_debit.txt")
    result = parse_sms("indusind", body)

    assert result.email_type == "indusind_account_transaction_alert"
    txn = result.transaction
    assert txn is not None
    assert txn.direction == "debit"
    assert txn.amount.amount == Decimal("12345")
    assert txn.account_mask == "XXXXXXX0000"
    assert txn.counterparty == "Acct XXXXXXX0001/Customer"
    assert txn.reference_number == "000000000000"
    assert txn.channel == "imps"
    assert txn.transaction_date == datetime.date(2026, 5, 3)


@pytest.mark.parametrize(
    "body",
    [
        # OTP shape that mentions "credited" but is not a transaction alert
        # and lacks the required A/C *XX... structure.
        "OTP 123456 to confirm Rs 1000 will be credited to your IndusInd "
        "account. Valid 5 mins. Do not share.",
        # Promotional fluff with no UPI structure.
        "Get assured cashback when your IndusInd account is credited via UPI. "
        "T&C apply.",
        # Same shape but verb is "debited" — must NOT match the credit parser
        # (and the IMPS-debit body, which would, lacks the A/C *XX prefix).
        "A/C *XX0000 debited by Rs 500.00 to 9999999999@bank. "
        "RRN:000000000000. Avl Bal:1.00.",
    ],
)
def test_upi_credit_rejects_non_credit_shapes(body: str) -> None:
    """The new parser must reject OTP/promo/debit shapes — verb-restricted."""
    # The dispatcher will try every IndusInd parser; none should claim these.
    with pytest.raises(ParseError):
        parse_sms("indusind", body)
