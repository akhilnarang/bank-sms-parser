"""Fixture-driven tests for slice (the fintech) SMS parsers."""

import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from bank_sms_parser import parse_sms
from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.parsers.slice import (
    SliceAccountImpsDebitAlertParser,
    SliceAccountUpiCreditAlertParser,
    SliceAccountUpiDebitAlertParser,
    SliceCcBillPaidAlertParser,
    SliceCcRefundAlertParser,
    SliceCcRepaymentReceivedAlertParser,
    SliceCcTransactionAlertParser,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sms"


def _read(rel: str) -> str:
    return (FIXTURES_DIR / rel).read_text()


# Happy path -----------------------------------------------------------------


def test_slice_account_upi_debit_alert() -> None:
    body = _read("slice/account_upi_debit.txt")
    result = parse_sms("slice", body)
    assert result.email_type == "slice_account_upi_debit_alert"
    assert result.bank == "slice"
    txn = result.transaction
    assert txn is not None
    assert txn.direction == "debit"
    assert txn.amount.amount == Decimal("7500.00")
    assert txn.amount.currency == "INR"
    assert txn.account_mask == "xx1234"
    assert txn.counterparty == "JANE DOE"
    assert txn.reference_number == "123456789012"
    assert txn.channel == "upi"
    assert txn.transaction_date == datetime.date(2026, 5, 5)
    assert txn.balance is None
    assert txn.card_mask is None


def test_slice_account_imps_debit_alert() -> None:
    body = _read("slice/account_imps_debit.txt")
    result = parse_sms("slice", body)
    assert result.email_type == "slice_account_imps_debit_alert"
    assert result.bank == "slice"
    txn = result.transaction
    assert txn is not None
    assert txn.direction == "debit"
    assert txn.amount.amount == Decimal("40000")
    assert txn.amount.currency == "INR"
    assert txn.account_mask == "xx1234"
    assert txn.counterparty == "JANE DOE"
    assert txn.reference_number == "234567890123"
    assert txn.channel == "imps"
    assert txn.transaction_date == datetime.date(2026, 5, 30)
    assert txn.balance is None
    assert txn.card_mask is None


def test_slice_account_upi_credit_alert() -> None:
    body = _read("slice/account_upi_credit.txt")
    result = parse_sms("slice", body)
    assert result.email_type == "slice_account_upi_credit_alert"
    assert result.bank == "slice"
    txn = result.transaction
    assert txn is not None
    assert txn.direction == "credit"
    assert txn.amount.amount == Decimal("12000")
    assert txn.amount.currency == "INR"
    assert txn.account_mask == "xx1234"
    assert txn.counterparty == "JOHN SMITH"
    assert txn.reference_number == "234567890123"
    assert txn.channel == "upi"
    assert txn.transaction_date == datetime.date(2026, 5, 3)
    assert txn.balance is not None
    assert txn.balance.amount == Decimal("50000.00")
    assert txn.balance.currency == "INR"
    assert txn.card_mask is None


def test_slice_cc_bill_paid_alert_with_received_at() -> None:
    body = _read("slice/cc_bill_paid.txt")
    # 2026-05-04 21:30 UTC == 2026-05-05 03:00 IST
    received = datetime.datetime(2026, 5, 4, 21, 30, tzinfo=datetime.UTC)
    result = parse_sms("slice", body, received_at=received)
    assert result.email_type == "slice_cc_bill_paid_alert"
    assert result.bank == "slice"
    txn = result.transaction
    assert txn is not None
    assert txn.direction == "credit"
    assert txn.amount.amount == Decimal("2500.00")
    assert txn.amount.currency == "INR"
    assert txn.counterparty == "Bill autopay"
    assert txn.channel == "card"
    assert txn.card_mask is None
    assert txn.account_mask is None
    assert txn.reference_number is None
    assert txn.transaction_date == datetime.date(2026, 5, 5)


def test_slice_cc_bill_paid_alert_without_received_at_leaves_date_none() -> None:
    """Body has no date; without received_at, transaction_date stays None."""
    body = _read("slice/cc_bill_paid.txt")
    result = parse_sms("slice", body)
    assert result.email_type == "slice_cc_bill_paid_alert"
    txn = result.transaction
    assert txn is not None
    assert txn.transaction_date is None
    assert txn.transaction_time is None


def test_slice_cc_repayment_received_alert_with_received_at() -> None:
    body = _read("slice/cc_repayment_received.txt")
    # 2026-05-04 21:30 UTC == 2026-05-05 03:00 IST
    received = datetime.datetime(2026, 5, 4, 21, 30, tzinfo=datetime.UTC)
    result = parse_sms("slice", body, received_at=received)
    assert result.email_type == "slice_cc_repayment_received_alert"
    assert result.bank == "slice"
    txn = result.transaction
    assert txn is not None
    assert txn.direction == "credit"
    assert txn.amount.amount == Decimal("3750")
    assert txn.amount.currency == "INR"
    assert txn.counterparty == "Bill repayment"
    assert txn.channel == "card"
    assert txn.card_mask is None
    assert txn.account_mask is None
    assert txn.reference_number is None
    assert txn.transaction_date == datetime.date(2026, 5, 5)


def test_slice_cc_repayment_received_alert_without_received_at_leaves_date_none() -> (
    None
):
    """Body has no date; without received_at, transaction_date stays None."""
    body = _read("slice/cc_repayment_received.txt")
    result = parse_sms("slice", body)
    assert result.email_type == "slice_cc_repayment_received_alert"
    txn = result.transaction
    assert txn is not None
    assert txn.transaction_date is None
    assert txn.transaction_time is None


def test_slice_cc_refund_alert_with_received_at() -> None:
    body = _read("slice/cc_refund.txt")
    # 2026-05-04 21:30 UTC == 2026-05-05 03:00 IST
    received = datetime.datetime(2026, 5, 4, 21, 30, tzinfo=datetime.UTC)
    result = parse_sms("slice", body, received_at=received)
    assert result.email_type == "slice_cc_refund_alert"
    assert result.bank == "slice"
    txn = result.transaction
    assert txn is not None
    assert txn.direction == "credit"
    assert txn.amount.amount == Decimal("500")
    assert txn.amount.currency == "INR"
    assert txn.counterparty == "SampleMerchant"
    assert txn.card_mask == "xxxx0000"
    assert txn.channel == "card"
    assert txn.account_mask is None
    assert txn.reference_number is None
    assert txn.transaction_date == datetime.date(2026, 5, 5)


def test_slice_cc_refund_alert_without_received_at_leaves_date_none() -> None:
    """Body has no date; without received_at, transaction_date stays None."""
    body = _read("slice/cc_refund.txt")
    result = parse_sms("slice", body)
    assert result.email_type == "slice_cc_refund_alert"
    txn = result.transaction
    assert txn is not None
    assert txn.transaction_date is None
    assert txn.transaction_time is None


# Negative cases -------------------------------------------------------------


def test_credit_parser_rejects_debit_body() -> None:
    body = _read("slice/account_upi_debit.txt")
    parser = SliceAccountUpiCreditAlertParser()
    with pytest.raises(ParseError):
        parser.parse(body)


def test_debit_parser_rejects_credit_body() -> None:
    body = _read("slice/account_upi_credit.txt")
    parser = SliceAccountUpiDebitAlertParser()
    with pytest.raises(ParseError):
        parser.parse(body)


def test_cc_bill_parser_rejects_account_alert() -> None:
    body = _read("slice/account_upi_credit.txt")
    parser = SliceCcBillPaidAlertParser()
    with pytest.raises(ParseError):
        parser.parse(body)


def test_account_parsers_reject_cc_bill_body() -> None:
    body = _read("slice/cc_bill_paid.txt")
    for parser in (
        SliceAccountUpiCreditAlertParser(),
        SliceAccountUpiDebitAlertParser(),
        SliceAccountImpsDebitAlertParser(),
    ):
        with pytest.raises(ParseError):
            parser.parse(body)


def test_repayment_parser_rejects_bill_paid_body() -> None:
    """The autopay bill-paid shape must not be parsed as a repayment."""
    body = _read("slice/cc_bill_paid.txt")
    with pytest.raises(ParseError):
        SliceCcRepaymentReceivedAlertParser().parse(body)


def test_bill_paid_parser_rejects_repayment_body() -> None:
    """The manual-repayment shape must not be parsed as an autopay bill payment."""
    body = _read("slice/cc_repayment_received.txt")
    with pytest.raises(ParseError):
        SliceCcBillPaidAlertParser().parse(body)


def test_cc_spend_parser_rejects_repayment_body() -> None:
    """The CC spend (debit) parser must not claim the repayment credit."""
    body = _read("slice/cc_repayment_received.txt")
    with pytest.raises(ParseError):
        SliceCcTransactionAlertParser().parse(body)


def test_account_parsers_reject_repayment_body() -> None:
    body = _read("slice/cc_repayment_received.txt")
    for parser in (
        SliceAccountUpiCreditAlertParser(),
        SliceAccountUpiDebitAlertParser(),
        SliceAccountImpsDebitAlertParser(),
    ):
        with pytest.raises(ParseError):
            parser.parse(body)


def test_refund_parser_rejects_cc_spend_body() -> None:
    """The CC spend (debit) shape must not be parsed as a refund."""
    body = _read("slice/cc_spend.txt")
    with pytest.raises(ParseError):
        SliceCcRefundAlertParser().parse(body)


def test_cc_spend_parser_rejects_refund_body() -> None:
    body = _read("slice/cc_refund.txt")
    with pytest.raises(ParseError):
        SliceCcTransactionAlertParser().parse(body)


def test_imps_debit_parser_rejects_upi_debit_body() -> None:
    """The IMPS debit shape must not be parsed by the UPI debit verb."""
    body = _read("slice/account_imps_debit.txt")
    with pytest.raises(ParseError):
        SliceAccountUpiDebitAlertParser().parse(body)


def test_upi_debit_parser_rejects_imps_debit_body() -> None:
    body = _read("slice/account_upi_debit.txt")
    with pytest.raises(ParseError):
        SliceAccountImpsDebitAlertParser().parse(body)


@pytest.mark.parametrize(
    "body",
    [
        # OTP that mentions slice + a Rs amount but no transaction verb.
        "Your slice OTP is 123456 for a Rs.500 transaction. Do not share.",
        # Promotional SMS with the bank name and an amount.
        "Get up to Rs.5,000 cashback on your next slice card spend. T&C apply.",
        # Service-info: statement-ready notice, not a transaction.
        "Your slice credit card statement for Apr-26 is ready. Login to view.",
        # Truncated debit body missing the UPI Ref clause.
        "Rs. 500 sent from a/c xx1234 on 05-May-26 to JANE DOE.",
        # OTP that quotes the repayment prefix but lacks the "credited to
        # your card account" confirmation clause — must not parse.
        "Your OTP for repayment of Rs.5,000 received for the slice "
        "credit card is 123456. Do not share.",
        # Promo that reuses "Repayment of Rs. ..." wording without the
        # confirmation sentence.
        "Repayment of Rs.5,000 or more on the slice credit card earns "
        "you bonus rewards this month. T&C apply.",
        # Refund near-miss: pending, not "has been successfully processed".
        "Refund of Rs. 500 from SampleMerchant is being processed to "
        "your credit card xxxx0000 - slice",
        # Empty body would never reach the parser (api rejects), but a
        # whitespace-padded non-matching body must still raise.
        "Hi from slice — nothing transactional here.",
    ],
)
def test_synthetic_adversarial_bodies_raise_parse_error(body: str) -> None:
    with pytest.raises(ParseError):
        parse_sms("slice", body)
