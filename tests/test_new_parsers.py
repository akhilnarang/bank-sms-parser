"""Fixture-driven tests: one parametrized case per real SMS shape."""

import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from bank_sms_parser import parse_sms
from bank_sms_parser.exceptions import ParseError

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
    ("hdfc", "hdfc/cc_spend.txt", {
        "email_type": "hdfc_cc_transaction_alert",
        "direction": "debit",
        "amount": Decimal("10290"),
        "currency": "INR",
        "card_mask": "0000",
        "counterparty": "EAZYDINE0000000",
        "transaction_date": datetime.date(2026, 5, 2),
        "transaction_time": datetime.time(22, 26, 1),
        "channel": "card",
    }),
    ("hdfc", "hdfc/cc_refund.txt", {
        "email_type": "hdfc_cc_refund_alert",
        "direction": "credit",
        "amount": Decimal("254"),
        "currency": "INR",
        "card_mask": "0000",
        "channel": "upi",
        "reference_number": "000000000000",
        "transaction_date": datetime.date(2026, 5, 1),
    }),
    ("hdfc", "hdfc/cc_payment_received.txt", {
        "email_type": "hdfc_cc_payment_received_alert",
        "direction": "credit",
        "amount": Decimal("1000"),
        "currency": "INR",
        "card_mask": "0000",
        "reference_number": "000XXXXXXXXXXXX",
        "transaction_date": datetime.date(2026, 5, 8),
    }),
    # Spaced "Rs. 1,000" variant — guards the optional `\s*` after `Rs.`
    # and the grouped-digit amount.
    ("hdfc", "hdfc/cc_payment_received_spaced.txt", {
        "email_type": "hdfc_cc_payment_received_alert",
        "direction": "credit",
        "amount": Decimal("1000"),
        "currency": "INR",
        "card_mask": "0000",
        "reference_number": "000XXXXXXXXXXXX",
        "transaction_date": datetime.date(2026, 5, 8),
    }),
    ("hdfc", "hdfc/account_imps_credit.txt", {
        "email_type": "hdfc_account_transaction_alert",
        "direction": "credit",
        "amount": Decimal("12345.00"),
        "currency": "INR",
        "account_mask": "xx0000",
        "counterparty": "Customer",
        "reference_number": "000000000000",
        "channel": "imps",
        "balance": Decimal("99999.99"),
        "transaction_date": datetime.date(2026, 5, 3),
    }),
    ("hdfc", "hdfc/account_upi_credit.txt", {
        "email_type": "hdfc_account_upi_credit_alert",
        "direction": "credit",
        "amount": Decimal("1.00"),
        "currency": "INR",
        "account_mask": "XX0000",
        "counterparty": "customer@bank",
        "reference_number": "000000000000",
        "channel": "upi",
        "transaction_date": datetime.date(2026, 5, 9),
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
    ("idfc", "idfc/cc_payment_received.txt", {
        "email_type": "idfc_cc_payment_received_alert",
        "direction": "credit",
        "amount": Decimal("3000.00"),
        "currency": "INR",
        "card_mask": "XX0000",
        "transaction_date": datetime.date(2026, 5, 2),
    }),
    ("idfc", "idfc/account_spend.txt", {
        "email_type": "idfc_account_transaction_alert",
        "direction": "debit",
        "amount": Decimal("2448.00"),
        "currency": "INR",
        "account_mask": "XX0000",
        "counterparty": "INSTAMART",
        "channel": "card",
        "transaction_date": datetime.date(2026, 5, 4),
    }),
    ("indusind", "indusind/account_upi_credit.txt", {
        "email_type": "indusind_account_upi_credit_alert",
        "direction": "credit",
        "amount": Decimal("12345.00"),
        "currency": "INR",
        "account_mask": "XX0000",
        "counterparty": "9999999999@bank",
        "reference_number": "000000000000",
        "channel": "upi",
        "balance": Decimal("12345.00"),
    }),
    ("indusind", "indusind/account_imps_debit.txt", {
        "email_type": "indusind_account_transaction_alert",
        "direction": "debit",
        "amount": Decimal("12345"),
        "currency": "INR",
        "account_mask": "XXXXXXX0000",
        "counterparty": "Acct XXXXXXX0001/Customer",
        "reference_number": "000000000000",
        "channel": "imps",
        "transaction_date": datetime.date(2026, 5, 3),
    }),
    ("icici", "icici/account_imps_debit.txt", {
        "email_type": "icici_account_transaction_alert",
        "direction": "debit",
        "amount": Decimal("10000.00"),
        "currency": "INR",
        "account_mask": "XX000",
        "counterparty": "Acct XX001",
        "reference_number": "000000000000",
        "channel": "imps",
        "transaction_date": datetime.date(2026, 5, 2),
    }),
    ("icici", "icici/cc_spend.txt", {
        "email_type": "icici_cc_transaction_alert",
        "direction": "debit",
        "amount": Decimal("1604.00"),
        "currency": "INR",
        "card_mask": "XX0000",
        "counterparty": "ONYX BAR",
        "balance": Decimal("9999999.99"),
        "transaction_date": datetime.date(2026, 5, 1),
    }),
    ("onecard", "onecard/cc_charge_bill_cleared.txt", {
        "email_type": "onecard_cc_transaction_alert",
        "direction": "debit",
        "amount": Decimal("49.00"),
        "currency": "INR",
        "card_mask": "XX0000",
        "counterparty": "SampleSubs Monthly",
    }),
    ("onecard", "onecard/cc_charge_spent.txt", {
        "email_type": "onecard_cc_transaction_alert",
        "direction": "debit",
        "amount": Decimal("1234.00"),
        "currency": "INR",
        "card_mask": "XX0000",
        "counterparty": "QuickGroceries Marketplace",
    }),
    ("onecard", "onecard/cc_charge_paid_usd.txt", {
        "email_type": "onecard_cc_transaction_alert",
        "direction": "debit",
        "amount": Decimal("42.50"),
        "currency": "USD",
        "card_mask": "XX0000",
        "counterparty": "OffshoreVendor Pte. Ltd.",
    }),
    ("onecard", "onecard/cc_payment_received_10000.txt", {
        "email_type": "onecard_cc_payment_received_alert",
        "direction": "credit",
        "amount": Decimal("10000.00"),
        "currency": "INR",
        "transaction_date": datetime.date(2026, 4, 29),
    }),
    ("onecard", "onecard/cc_payment_received_1050.txt", {
        "email_type": "onecard_cc_payment_received_alert",
        "direction": "credit",
        "amount": Decimal("1050.00"),
        "currency": "INR",
        "transaction_date": datetime.date(2026, 4, 28),
    }),
    ("onecard", "onecard/cc_payment_received_1799.txt", {
        "email_type": "onecard_cc_payment_received_alert",
        "direction": "credit",
        "amount": Decimal("1799.94"),
        "currency": "INR",
        "transaction_date": datetime.date(2026, 4, 25),
    }),
])
def test_parses_real_sms(bank, fixture, expected) -> None:
    body = _read(fixture)
    result = parse_sms(bank, body)
    _assert_matches(result, expected)


@pytest.mark.parametrize("bank, fixture", [
    ("onecard", "onecard/negative/limit_update.txt"),
    ("onecard", "onecard/negative/statement_ready.txt"),
])
def test_real_negative_fixtures_raise_parse_error(bank, fixture) -> None:
    body = _read(fixture)
    with pytest.raises(ParseError):
        parse_sms(bank, body)


def test_indusind_uses_received_at_for_date_fallback() -> None:
    """IndusInd body has no date; received_at (UTC→IST) fills transaction_date/time."""
    body = _read("indusind/account_upi_credit.txt")
    # 2026-04-30 21:30 UTC == 2026-05-01 03:00 IST
    received = datetime.datetime(2026, 4, 30, 21, 30, tzinfo=datetime.UTC)
    result = parse_sms("indusind", body, received_at=received)
    assert result.transaction is not None
    assert result.transaction.transaction_date == datetime.date(2026, 5, 1)
    assert result.transaction.transaction_time == datetime.time(3, 0)


def test_indusind_no_received_at_leaves_date_none() -> None:
    """Without received_at, transaction_date/time stay None — never fabricated."""
    body = _read("indusind/account_upi_credit.txt")
    result = parse_sms("indusind", body)
    assert result.transaction is not None
    assert result.transaction.transaction_date is None
    assert result.transaction.transaction_time is None


def test_onecard_charge_uses_received_at_for_date_fallback() -> None:
    """OneCard charge bodies carry no date; received_at (UTC→IST) fills it."""
    body = _read("onecard/cc_charge_spent.txt")
    # 2026-04-13 21:30 UTC == 2026-04-14 03:00 IST
    received = datetime.datetime(2026, 4, 13, 21, 30, tzinfo=datetime.UTC)
    result = parse_sms("onecard", body, received_at=received)
    assert result.transaction is not None
    assert result.transaction.transaction_date == datetime.date(2026, 4, 14)
    assert result.transaction.transaction_time == datetime.time(3, 0)


def test_onecard_charge_no_received_at_leaves_date_none() -> None:
    body = _read("onecard/cc_charge_spent.txt")
    result = parse_sms("onecard", body)
    assert result.transaction is not None
    assert result.transaction.transaction_date is None
    assert result.transaction.transaction_time is None


@pytest.mark.parametrize("bank, body", [
    # HDFC OTP that mimics the spend body's surface form (amount, merchant,
    # card mask all present) but lacks the discriminating verb "Spent".
    (
        "hdfc",
        "OTP for your Rs.3000 transaction at PZCREDIT0000000 using HDFC "
        "Bank Card x0000 is 123456. Valid 5 mins. Do not share.",
    ),
    # HDFC promotional fluff with the bank name + card mask.
    (
        "hdfc",
        "Get 5% cashback on your next HDFC Card x0000 spend at any partner "
        "merchant. T&C apply.",
    ),
    # Truncated HDFC transaction missing date and balance.
    (
        "hdfc",
        "Spent Rs.3000 From HDFC Bank Card x0000",
    ),
    # Equitas service-info SMS that is not a transaction.
    (
        "equitas",
        "Dear Customer, your Equitas CC XX0000 statement is now available. "
        "Login to view.",
    ),
])
def test_synthetic_adversarial_bodies_raise_parse_error(bank, body) -> None:
    with pytest.raises(ParseError):
        parse_sms(bank, body)
