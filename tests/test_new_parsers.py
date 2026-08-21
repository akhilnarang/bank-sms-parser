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


@pytest.mark.parametrize(
    "bank, fixture, expected",
    [
        (
            "hdfc",
            "hdfc/dc_spend.txt",
            {
                "email_type": "hdfc_dc_transaction_alert",
                "direction": "debit",
                "amount": Decimal("3000"),
                "currency": "INR",
                "card_mask": "x0000",
                "counterparty": "PZCREDIT0000000",
                "balance": Decimal("142.26"),
                "transaction_date": datetime.date(2026, 5, 2),
                "transaction_time": datetime.time(0, 17, 56),
            },
        ),
        (
            "hdfc",
            "hdfc/cc_spend.txt",
            {
                "email_type": "hdfc_cc_transaction_alert",
                "direction": "debit",
                "amount": Decimal("10290"),
                "currency": "INR",
                "card_mask": "0000",
                "counterparty": "EAZYDINE0000000",
                "transaction_date": datetime.date(2026, 5, 2),
                "transaction_time": datetime.time(22, 26, 1),
                "channel": "card",
            },
        ),
        # Amount-first CC spend variant: "Rs.X spent on HDFC Bank Card x0000 at
        # MERCHANT on <dt>.Not U?" — lowercase verbs, x-prefixed mask, and the
        # ".Not U?" trailer glued to the datetime (no space).
        (
            "hdfc",
            "hdfc/cc_spend_amount_first.txt",
            {
                "email_type": "hdfc_cc_transaction_alert",
                "direction": "debit",
                "amount": Decimal("569"),
                "currency": "INR",
                "card_mask": "x0000",
                "counterparty": "RAZ*SampleFood",
                "transaction_date": datetime.date(2026, 7, 12),
                "transaction_time": datetime.time(17, 0, 56),
                "channel": "card",
            },
        ),
        (
            "hdfc",
            "hdfc/cc_refund.txt",
            {
                "email_type": "hdfc_cc_refund_alert",
                "direction": "credit",
                "amount": Decimal("254"),
                "currency": "INR",
                "card_mask": "0000",
                "channel": "upi",
                "reference_number": "000000000000",
                "transaction_date": datetime.date(2026, 5, 1),
            },
        ),
        (
            "hdfc",
            "hdfc/cc_merchant_refund.txt",
            {
                "email_type": "hdfc_cc_refund_alert",
                "direction": "credit",
                "amount": Decimal("262.56"),
                "currency": "INR",
                "card_mask": "0000",
                "counterparty": "SampleMerchant Payments BANGALORE IND",
                "channel": "card",
                "transaction_date": datetime.date(2026, 5, 17),
            },
        ),
        (
            "hdfc",
            "hdfc/cc_payment_received.txt",
            {
                "email_type": "hdfc_cc_payment_received_alert",
                "direction": "credit",
                "amount": Decimal("1000"),
                "currency": "INR",
                "card_mask": "0000",
                "reference_number": "000XXXXXXXXXXXX",
                "transaction_date": datetime.date(2026, 5, 8),
            },
        ),
        # Spaced "Rs. 1,000" variant — guards the optional `\s*` after `Rs.`
        # and the grouped-digit amount.
        (
            "hdfc",
            "hdfc/cc_payment_received_spaced.txt",
            {
                "email_type": "hdfc_cc_payment_received_alert",
                "direction": "credit",
                "amount": Decimal("1000"),
                "currency": "INR",
                "card_mask": "0000",
                "reference_number": "000XXXXXXXXXXXX",
                "transaction_date": datetime.date(2026, 5, 8),
            },
        ),
        (
            "hdfc",
            "hdfc/account_imps_credit.txt",
            {
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
            },
        ),
        (
            "hdfc",
            "hdfc/account_upi_credit.txt",
            {
                "email_type": "hdfc_account_upi_credit_alert",
                "direction": "credit",
                "amount": Decimal("1.00"),
                "currency": "INR",
                "account_mask": "XX0000",
                "counterparty": "customer@bank",
                "reference_number": "000000000000",
                "channel": "upi",
                "transaction_date": datetime.date(2026, 5, 9),
            },
        ),
        (
            "equitas",
            "equitas/cc_spend.txt",
            {
                "email_type": "equitas_cc_transaction_alert",
                "direction": "debit",
                "amount": Decimal("30.00"),
                "currency": "INR",
                "card_mask": "XX0000",
                "counterparty": "CITY REALTY AND DEVELO",
                "balance": Decimal("99999.99"),
                "transaction_date": datetime.date(2026, 5, 1),
                "transaction_time": datetime.time(19, 53, 18),
            },
        ),
        (
            "axis",
            "axis/cc_payment_received.txt",
            {
                "email_type": "axis_cc_payment_received_alert",
                "direction": "credit",
                "amount": Decimal("15000"),
                "currency": "INR",
                "card_mask": "XX0000",
                "transaction_date": datetime.date(2026, 5, 2),
            },
        ),
        (
            "idfc",
            "idfc/cc_payment_received.txt",
            {
                "email_type": "idfc_cc_payment_received_alert",
                "direction": "credit",
                "amount": Decimal("3000.00"),
                "currency": "INR",
                "card_mask": "XX0000",
                "transaction_date": datetime.date(2026, 5, 2),
            },
        ),
        (
            "idfc",
            "idfc/cc_spend.txt",
            {
                "email_type": "idfc_cc_transaction_alert",
                "direction": "debit",
                "amount": Decimal("370.80"),
                "currency": "INR",
                "card_mask": "XX0000",
                "counterparty": "SAMPLE MERCHANT LTD",
                "channel": "card",
                "balance": Decimal("99999.9"),
                "transaction_date": datetime.date(2026, 7, 5),
                "transaction_time": datetime.time(11, 54),
            },
        ),
        (
            "idfc",
            "idfc/account_spend.txt",
            {
                "email_type": "idfc_account_transaction_alert",
                "direction": "debit",
                "amount": Decimal("2448.00"),
                "currency": "INR",
                "account_mask": "XX0000",
                "counterparty": "INSTAMART",
                "channel": "card",
                "transaction_date": datetime.date(2026, 5, 4),
            },
        ),
        (
            "idfc",
            "idfc/account_upi_debit.txt",
            {
                "email_type": "idfc_account_transaction_alert",
                "direction": "debit",
                "amount": Decimal("20000.00"),
                "currency": "INR",
                "account_mask": "XX0000",
                "counterparty": "CUSTOMER NAME",
                "reference_number": "000000000000",
                "channel": "upi",
                "balance": Decimal("16442.65"),
                "transaction_date": datetime.date(2026, 5, 9),
            },
        ),
        # Dotted-payee variant — guards against a `[^.]+?` payee class that
        # would silently reject merchants like "M/S A.B. MART".
        (
            "idfc",
            "idfc/account_upi_debit_dotted_payee.txt",
            {
                "email_type": "idfc_account_transaction_alert",
                "direction": "debit",
                "amount": Decimal("750.00"),
                "currency": "INR",
                "account_mask": "XX0000",
                "counterparty": "M/S A.B. MART",
                "reference_number": "000000000001",
                "channel": "upi",
                "balance": Decimal("10000.00"),
                "transaction_date": datetime.date(2026, 5, 9),
            },
        ),
        (
            "idfc",
            "idfc/account_balance_credit_165.txt",
            {
                "email_type": "idfc_account_balance_credit_alert",
                "direction": "credit",
                "amount": Decimal("50000.00"),
                "currency": "INR",
                "account_mask": "XXXXX000001",
                "balance": Decimal("99999.00"),
                "transaction_date": datetime.date(2026, 5, 25),
                "transaction_time": datetime.time(12, 53),
            },
        ),
        (
            "idfc",
            "idfc/account_balance_debit_166.txt",
            {
                "email_type": "idfc_account_balance_debit_alert",
                "direction": "debit",
                "amount": Decimal("50000.00"),
                "currency": "INR",
                "account_mask": "XXXXX000002",
                "balance": Decimal("0.00"),
                "transaction_date": datetime.date(2026, 5, 25),
                "transaction_time": datetime.time(12, 53),
            },
        ),
        (
            "indusind",
            "indusind/account_upi_credit.txt",
            {
                "email_type": "indusind_account_upi_credit_alert",
                "direction": "credit",
                "amount": Decimal("12345.00"),
                "currency": "INR",
                "account_mask": "XX0000",
                "counterparty": "9999999999@bank",
                "reference_number": "000000000000",
                "channel": "upi",
                "balance": Decimal("12345.00"),
            },
        ),
        (
            "indusind",
            "indusind/account_upi_debit.txt",
            {
                "email_type": "indusind_account_upi_debit_alert",
                "direction": "debit",
                "amount": Decimal("46500.00"),
                "currency": "INR",
                "account_mask": "XX0000",
                "counterparty": "9999999999@bank",
                "reference_number": "000000000000",
                "channel": "upi",
                "balance": Decimal("0.00"),
            },
        ),
        (
            "indusind",
            "indusind/account_imps_debit.txt",
            {
                "email_type": "indusind_account_transaction_alert",
                "direction": "debit",
                "amount": Decimal("12345"),
                "currency": "INR",
                "account_mask": "XXXXXXX0000",
                "counterparty": "Acct XXXXXXX0001/Customer",
                "reference_number": "000000000000",
                "channel": "imps",
                "transaction_date": datetime.date(2026, 5, 3),
            },
        ),
        # IndusInd credit-card spend (distinct from the account UPI/IMPS shapes):
        # carries an in-body date + 12-hour time and an "Avl Lmt" credit limit.
        (
            "indusind",
            "indusind/cc_spend.txt",
            {
                "email_type": "indusind_cc_transaction_alert",
                "direction": "debit",
                "amount": Decimal("1234.00"),
                "currency": "INR",
                "card_mask": "XX0000",
                "counterparty": "PYU*SWIGGY FOOD",
                "balance": Decimal("99999.99"),
                "transaction_date": datetime.date(2026, 5, 22),
                "transaction_time": datetime.time(19, 58, 13),
                "channel": "card",
            },
        ),
        (
            "indusind",
            "indusind/cc_payment_received.txt",
            {
                "email_type": "indusind_cc_payment_received_alert",
                "direction": "credit",
                "amount": Decimal("1234.56"),
                "currency": "INR",
                "card_mask": None,
                "counterparty": "Payment received",
                "channel": "card",
                "transaction_date": datetime.date(2026, 7, 18),
            },
        ),
        (
            "indusind",
            "indusind/cc_refund.txt",
            {
                "email_type": "indusind_cc_refund_alert",
                "direction": "credit",
                "amount": Decimal("1234"),
                "currency": "INR",
                "card_mask": "XX0000",
                "counterparty": "SampleMerchant BENGALURU IND",
                "channel": "card",
                "transaction_date": datetime.date(2026, 7, 27),
            },
        ),
        # IndusInd generic account inbound credit (a refund). The "Ref-"
        # clause is descriptive narration (the refund source), stored as
        # counterparty; reference_number stays None so a descriptive string
        # cannot collide downstream as a fake reference.
        (
            "indusind",
            "indusind/account_credit.txt",
            {
                "email_type": "indusind_account_credit_alert",
                "direction": "credit",
                "amount": Decimal("1234.56"),
                "currency": "INR",
                "account_mask": "**0000",
                "counterparty": "Refund Frm SampleSource Payments",
                "reference_number": None,
                "balance": Decimal("2345.67"),
                "transaction_date": None,
            },
        ),
        (
            "icici",
            "icici/account_imps_debit.txt",
            {
                "email_type": "icici_account_transaction_alert",
                "direction": "debit",
                "amount": Decimal("10000.00"),
                "currency": "INR",
                "account_mask": "XX000",
                "counterparty": "Acct XX001",
                "reference_number": "000000000000",
                "channel": "imps",
                "transaction_date": datetime.date(2026, 5, 2),
            },
        ),
        (
            "icici",
            "icici/account_upi_debit.txt",
            {
                "email_type": "icici_account_transaction_alert",
                "direction": "debit",
                "amount": Decimal("14.00"),
                "currency": "INR",
                "account_mask": "XX000",
                "counterparty": "Pune Metro",
                "reference_number": "000000000000",
                "channel": "upi",
                "transaction_date": datetime.date(2026, 5, 9),
            },
        ),
        # Dotted-payee variant — guards against a `[^.]+?` payee class that
        # would silently reject merchants like "A.B. Traders".
        (
            "icici",
            "icici/account_upi_debit_dotted_payee.txt",
            {
                "email_type": "icici_account_transaction_alert",
                "direction": "debit",
                "amount": Decimal("250.00"),
                "currency": "INR",
                "account_mask": "XX000",
                "counterparty": "A.B. Traders",
                "reference_number": "000000000001",
                "channel": "upi",
                "transaction_date": datetime.date(2026, 5, 9),
            },
        ),
        (
            "icici",
            "icici/account_upi_credit_201.txt",
            {
                "email_type": "icici_account_upi_credit_alert",
                "direction": "credit",
                "amount": Decimal("1000.00"),
                "currency": "INR",
                "account_mask": "XX000",
                "counterparty": "SAMPLE CUSTOMER",
                "reference_number": "000000000000",
                "channel": "upi",
                "transaction_date": datetime.date(2026, 5, 28),
            },
        ),
        (
            "icici",
            "icici/account_mandate_debit.txt",
            {
                "email_type": "icici_account_mandate_debit_alert",
                "direction": "debit",
                "amount": Decimal("1234.56"),
                "currency": "INR",
                "account_mask": None,
                "counterparty": "SAMPLE FUND MANAGER",
                "reference_number": "000000000000",
                "channel": "emandate",
                "transaction_date": datetime.date(2026, 7, 18),
            },
        ),
        (
            "icici",
            "icici/cc_spend.txt",
            {
                "email_type": "icici_cc_transaction_alert",
                "direction": "debit",
                "amount": Decimal("1604.00"),
                "currency": "INR",
                "card_mask": "XX0000",
                "counterparty": "ONYX BAR",
                "balance": Decimal("9999999.99"),
                "transaction_date": datetime.date(2026, 5, 1),
            },
        ),
        (
            "onecard",
            "onecard/cc_charge_bill_cleared.txt",
            {
                "email_type": "onecard_cc_transaction_alert",
                "direction": "debit",
                "amount": Decimal("49.00"),
                "currency": "INR",
                "card_mask": "XX0000",
                "counterparty": "SampleSubs Monthly",
            },
        ),
        (
            "onecard",
            "onecard/cc_charge_spent.txt",
            {
                "email_type": "onecard_cc_transaction_alert",
                "direction": "debit",
                "amount": Decimal("1234.00"),
                "currency": "INR",
                "card_mask": "XX0000",
                "counterparty": "QuickGroceries Marketplace",
            },
        ),
        (
            "onecard",
            "onecard/cc_charge_paid_usd.txt",
            {
                "email_type": "onecard_cc_transaction_alert",
                "direction": "debit",
                "amount": Decimal("42.50"),
                "currency": "USD",
                "card_mask": "XX0000",
                "counterparty": "OffshoreVendor Pte. Ltd.",
            },
        ),
        (
            "onecard",
            "onecard/cc_payment_received_10000.txt",
            {
                "email_type": "onecard_cc_payment_received_alert",
                "direction": "credit",
                "amount": Decimal("10000.00"),
                "currency": "INR",
                "transaction_date": datetime.date(2026, 4, 29),
            },
        ),
        (
            "onecard",
            "onecard/cc_payment_received_1050.txt",
            {
                "email_type": "onecard_cc_payment_received_alert",
                "direction": "credit",
                "amount": Decimal("1050.00"),
                "currency": "INR",
                "transaction_date": datetime.date(2026, 4, 28),
            },
        ),
        (
            "onecard",
            "onecard/cc_payment_received_1799.txt",
            {
                "email_type": "onecard_cc_payment_received_alert",
                "direction": "credit",
                "amount": Decimal("1799.94"),
                "currency": "INR",
                "transaction_date": datetime.date(2026, 4, 25),
            },
        ),
        # HDFC CC spend with a multi-word merchant — guards against an
        # `\S+` merchant class that would silently reject names like
        # "URBAN BISTRO" by capturing only the first word.
        (
            "hdfc",
            "hdfc/cc_spend_multiword_merchant.txt",
            {
                "email_type": "hdfc_cc_transaction_alert",
                "direction": "debit",
                "amount": Decimal("100"),
                "currency": "INR",
                "card_mask": "0000",
                "counterparty": "URBAN BISTRO",
                "transaction_date": datetime.date(2026, 5, 16),
                "transaction_time": datetime.time(15, 55, 55),
                "channel": "card",
            },
        ),
        (
            "hdfc",
            "hdfc/cc_payment_received_uppercase.txt",
            {
                "email_type": "hdfc_cc_payment_received_alert",
                "direction": "credit",
                "amount": Decimal("100.00"),
                "currency": "INR",
                "card_mask": "0000",
                "transaction_date": datetime.date(2026, 5, 17),
            },
        ),
        # Mixed-case "Payment of ... was credited" variant with no reference
        # number (distinct from the "Online Payment ... vide Ref#" shape).
        (
            "hdfc",
            "hdfc/cc_payment_received_220.txt",
            {
                "email_type": "hdfc_cc_payment_received_alert",
                "direction": "credit",
                "amount": Decimal("100"),
                "currency": "INR",
                "card_mask": "0000",
                "reference_number": None,
                "transaction_date": datetime.date(2026, 5, 28),
            },
        ),
        (
            "hdfc",
            "hdfc/account_credit_alert.txt",
            {
                "email_type": "hdfc_account_credit_alert",
                "direction": "credit",
                "amount": Decimal("100.00"),
                "currency": "INR",
                "account_mask": "XX0000",
                "counterparty": "CUSTOMER NAME-XXXXXXXXXX0000 - REMITTER NAME",
                "channel": "imps",
                "balance": Decimal("200.00"),
                "transaction_date": datetime.date(2026, 5, 16),
            },
        ),
        # NEFT inbound credit: same "Update! ... deposited ..." template as the
        # FT- variant above, but the transfer tag is "for NEFT Cr-<route>-
        # <remitter>-<beneficiary>-<UTR>". Counterparty is the remitter.
        (
            "hdfc",
            "hdfc/account_neft_credit.txt",
            {
                "email_type": "hdfc_account_credit_alert",
                "direction": "credit",
                "amount": Decimal("100.00"),
                "currency": "INR",
                "account_mask": "XX0000",
                "counterparty": "Sample Remitter Inc",
                "channel": "neft",
                "balance": Decimal("200.00"),
                "transaction_date": datetime.date(2026, 6, 29),
            },
        ),
        # Hyphenated remitter name must stay intact in the counterparty (the
        # greedy remitter capture leaves the single-segment beneficiary and UTR
        # pinned to the right).
        (
            "hdfc",
            "hdfc/account_neft_credit_hyphenated.txt",
            {
                "email_type": "hdfc_account_credit_alert",
                "direction": "credit",
                "amount": Decimal("100.00"),
                "currency": "INR",
                "account_mask": "XX0000",
                "counterparty": "State-Bank Remitter",
                "channel": "neft",
                "reference_number": "SAMPLEH00000000000",
                "balance": Decimal("200.00"),
                "transaction_date": datetime.date(2026, 6, 29),
            },
        ),
        (
            "hdfc",
            "hdfc/account_upi_debit.txt",
            {
                "email_type": "hdfc_account_upi_debit_alert",
                "direction": "debit",
                "amount": Decimal("100.00"),
                "currency": "INR",
                "account_mask": "0000",
                "counterparty": "CUSTOMER NAME",
                "reference_number": "000000000000",
                "channel": "upi",
                "transaction_date": datetime.date(2026, 5, 17),
            },
        ),
        (
            "hdfc",
            "hdfc/cc_smartpay_bbps.txt",
            {
                "email_type": "hdfc_cc_smartpay_bbps_alert",
                "direction": "debit",
                "amount": Decimal("100"),
                "currency": "INR",
                "card_mask": "0000",
                "reference_number": "00000",
                "counterparty": "SpayBBPS 00000",
                "channel": "card",
            },
        ),
        (
            "icici",
            "icici/cc_spend_variant2.txt",
            {
                "email_type": "icici_cc_transaction_alert",
                "direction": "debit",
                "amount": Decimal("100.00"),
                "currency": "INR",
                "card_mask": "XX0000",
                "counterparty": "SAMPLE MERCHANT",
                "balance": Decimal("200.00"),
                "transaction_date": datetime.date(2026, 5, 16),
            },
        ),
        # ICICI CC bill-payment received (money credited to the card via BBPS).
        # Mirrors the axis/idfc cc_payment_received convention: direction=credit,
        # card_mask + date, no counterparty/balance.
        (
            "icici",
            "icici/cc_payment_received.txt",
            {
                "email_type": "icici_cc_payment_received_alert",
                "direction": "credit",
                "amount": Decimal("12345.00"),
                "currency": "INR",
                "card_mask": "XX0000",
                "transaction_date": datetime.date(2026, 5, 21),
            },
        ),
        # HSBC credit-card spend: lowercase "xxxxx####" card mask, "used at"
        # merchant, "for INR", DD/MM/YY date, and "Limit Rs" available credit
        # limit stored in balance (the trailing "Due Rs" outstanding is dropped).
        (
            "hsbc",
            "hsbc/cc_spend.txt",
            {
                "email_type": "hsbc_cc_transaction_alert",
                "direction": "debit",
                "amount": Decimal("100.00"),
                "currency": "INR",
                "card_mask": "xxxxx0000",
                "counterparty": "SampleMerchant Store",
                "balance": Decimal("99999.99"),
                "channel": "card",
                "transaction_date": datetime.date(2026, 7, 1),
            },
        ),
        # HSBC credit-card payment received: "we have received a payment of
        # INR ... for credit card ending ####" with a bare-digit card mask and
        # a DD-MON-YY date. Mirrors the equitas cc_payment convention:
        # direction=credit, counterparty="Payment received", channel="card".
        (
            "hsbc",
            "hsbc/cc_payment_received.txt",
            {
                "email_type": "hsbc_cc_payment_received_alert",
                "direction": "credit",
                "amount": Decimal("15000.00"),
                "currency": "INR",
                "card_mask": "0000",
                "counterparty": "Payment received",
                "channel": "card",
                "transaction_date": datetime.date(2026, 7, 2),
            },
        ),
        # SBI Card spend alerts from SMS 889/890 share one shape: amount first,
        # a bare last-four mask, merchant, and DD/MM/YY date.
        (
            "sbi",
            "sbi/cc_spend_889.txt",
            {
                "email_type": "sbi_cc_transaction_alert",
                "direction": "debit",
                "amount": Decimal("123.45"),
                "currency": "INR",
                "card_mask": "0000",
                "counterparty": "SAMPLE MART",
                "channel": "card",
                "transaction_date": datetime.date(2026, 7, 19),
            },
        ),
        (
            "sbi",
            "sbi/cc_spend_890.txt",
            {
                "email_type": "sbi_cc_transaction_alert",
                "direction": "debit",
                "amount": Decimal("678.90"),
                "currency": "INR",
                "card_mask": "0001",
                "counterparty": "SAMPLE STORE",
                "channel": "card",
                "transaction_date": datetime.date(2026, 7, 20),
            },
        ),
        # SBI debit-card spend. The body carries a reference number, card mask,
        # merchant, in-body date and time, and the updated available balance.
        (
            "sbi",
            "sbi/dc_transaction.txt",
            {
                "email_type": "sbi_dc_transaction_alert",
                "direction": "debit",
                "amount": Decimal("100.00"),
                "currency": "INR",
                "card_mask": "X0000",
                "counterparty": "SAMPLE MART",
                "reference_number": "000000000000",
                "balance": Decimal("200.00"),
                "channel": "card",
                "transaction_date": datetime.date(2026, 8, 19),
                "transaction_time": datetime.time(13, 35, 48),
            },
        ),
        # SBI Card bill-payment processed: no card mask, no date (received_at
        # fallback asserted separately), alphanumeric ref, constant counterparty.
        (
            "sbi",
            "sbi/cc_payment_received.txt",
            {
                "email_type": "sbi_cc_payment_received_alert",
                "direction": "credit",
                "amount": Decimal("12345.00"),
                "currency": "INR",
                "counterparty": "Payment received",
                "reference_number": "ABC00DE0FG0HIJ",
                "channel": "card",
            },
        ),
        # IDFC merchant debit: "for <merchant> transaction." with a DD-Mon-YYYY
        # date + 24-hour time and no balance trailer.
        (
            "idfc",
            "idfc/account_merchant_debit.txt",
            {
                "email_type": "idfc_account_transaction_alert",
                "direction": "debit",
                "amount": Decimal("12345.00"),
                "currency": "INR",
                "account_mask": "XXXXXXX0000",
                "counterparty": "SamplePay Private Limited",
                "transaction_date": datetime.date(2026, 8, 5),
                "transaction_time": datetime.time(13, 34),
            },
        ),
        (
            "sbi",
            "sbi/account_credit.txt",
            {
                "email_type": "sbi_account_credit_alert",
                "direction": "credit",
                "amount": Decimal("12345"),
                "currency": "INR",
                "account_mask": "X0000",
                "counterparty": "Sample Name",
                "reference_number": "123456789012",
                "transaction_date": datetime.date(2026, 7, 28),
            },
        ),
        (
            "slice",
            "slice/cc_spend.txt",
            {
                "email_type": "slice_cc_transaction_alert",
                "direction": "debit",
                "amount": Decimal("100"),
                "currency": "INR",
                "card_mask": "xx0000",
                "counterparty": "SampleMerchant",
                "reference_number": "000000000000",
                "channel": "card",
                "transaction_date": datetime.date(2026, 5, 12),
            },
        ),
        # slice CC manual repayment received (autopay paused/off). No mask,
        # no date, no ref; counterparty is the constant "Bill repayment".
        (
            "slice",
            "slice/cc_repayment_received.txt",
            {
                "email_type": "slice_cc_repayment_received_alert",
                "direction": "credit",
                "amount": Decimal("3750"),
                "currency": "INR",
                "counterparty": "Bill repayment",
                "channel": "card",
            },
        ),
        # slice CC refund (credit back to the card). Merchant in "from ...",
        # a four-x card mask (xxxx0000, distinct from the spend shape's
        # xx0000), no in-body date, no reference.
        (
            "slice",
            "slice/cc_refund.txt",
            {
                "email_type": "slice_cc_refund_alert",
                "direction": "credit",
                "amount": Decimal("500"),
                "currency": "INR",
                "card_mask": "xxxx0000",
                "counterparty": "SampleMerchant",
                "channel": "card",
            },
        ),
        # slice account IMPS credit (distinct from the UPI credit shape:
        # "via IMPS" not "via UPI"). Amount arrives without decimals; the
        # balance uses Indian digit grouping.
        (
            "slice",
            "slice/account_imps_credit.txt",
            {
                "email_type": "slice_account_imps_credit_alert",
                "direction": "credit",
                "amount": Decimal("45000"),
                "currency": "INR",
                "account_mask": "xx0000",
                "counterparty": "SENDER NAME",
                "reference_number": "000000000000",
                "channel": "imps",
                "balance": Decimal("123456.78"),
                "transaction_date": datetime.date(2026, 6, 11),
            },
        ),
        (
            "slice",
            "slice/account_rtgs_credit.txt",
            {
                "email_type": "slice_account_rtgs_credit_alert",
                "direction": "credit",
                "amount": Decimal("12345"),
                "currency": "INR",
                "account_mask": "xx0000",
                "counterparty": "CUSTOMER NAME",
                "reference_number": "SAMPLE00000000000000000",
                "channel": "rtgs",
                "balance": Decimal("23456.78"),
                "transaction_date": datetime.date(2026, 7, 18),
            },
        ),
        # Axis CC POS/online spend (distinct from the payment-received credit):
        # in-body "DD-MM-YY HH:MM:SS IST" stamp; the "Avl Limit" credit limit
        # is stored in `balance`.
        (
            "axis",
            "axis/cc_spend.txt",
            {
                "email_type": "axis_cc_transaction_alert",
                "direction": "debit",
                "amount": Decimal("123.45"),
                "currency": "INR",
                "card_mask": "XX0000",
                "counterparty": "SampleMerchant Store",
                "balance": Decimal("99999.99"),
                "transaction_date": datetime.date(2026, 5, 2),
                "transaction_time": datetime.time(19, 53, 18),
                "channel": "card",
            },
        ),
        # Axis CC transaction reversal — "Txn reversal of INR ... at MERCHANT
        # was successful." credits the card back; shares the spend shape's
        # in-body IST stamp and "Avl Limit" line (stored in `balance`).
        (
            "axis",
            "axis/cc_reversal.txt",
            {
                "email_type": "axis_cc_reversal_alert",
                "direction": "credit",
                "amount": Decimal("2499"),
                "currency": "INR",
                "card_mask": "XX0000",
                "counterparty": "SAMPLESHOP IN",
                "balance": Decimal("99999.99"),
                "transaction_date": datetime.date(2026, 5, 2),
                "transaction_time": datetime.time(19, 53, 18),
                "channel": "card",
            },
        ),
        # HDFC credit-card-on-UPI spend — same `hdfc_cc_transaction_alert`
        # event as the POS spend, distinguished by channel="upi"; carries the
        # payee VPA + UPI ref. The "On DD-MM" date has no year/time, so date
        # falls back to received_at (asserted separately; None without it).
        (
            "hdfc",
            "hdfc/cc_upi_spend.txt",
            {
                "email_type": "hdfc_cc_transaction_alert",
                "direction": "debit",
                "amount": Decimal("100.00"),
                "currency": "INR",
                "card_mask": "0000",
                "counterparty": "sample.vpa@hdfcbank",
                "reference_number": "000000000000",
                "channel": "upi",
            },
        ),
        (
            "hdfc",
            "hdfc/account_imps_sent.txt",
            {
                "email_type": "hdfc_account_imps_outward_alert",
                "direction": "debit",
                "amount": Decimal("123456.78"),
                "currency": "INR",
                "account_mask": "XX0000",
                "counterparty": "Acct xxxxxxxxxx0000",
                "reference_number": "000000000000",
                "channel": "imps",
                "transaction_date": datetime.date(2026, 5, 12),
            },
        ),
        (
            "hdfc",
            "hdfc/account_imps_outward_174.txt",
            {
                "email_type": "hdfc_account_imps_outward_alert",
                "direction": "debit",
                "amount": Decimal("100000.00"),
                "currency": "INR",
                "account_mask": "XX0000",
                "counterparty": "Acct xxxxxxxxxx0000",
                "reference_number": "000000000001",
                "channel": "imps",
                "transaction_date": datetime.date(2026, 5, 26),
            },
        ),
        (
            "hdfc",
            "hdfc/account_imps_outward_199.txt",
            {
                "email_type": "hdfc_account_imps_outward_alert",
                "direction": "debit",
                "amount": Decimal("123456.00"),
                "currency": "INR",
                "account_mask": "XX0000",
                "counterparty": "Acct xxxxxxxxxx0000",
                "reference_number": "000000000002",
                "channel": "imps",
                "transaction_date": datetime.date(2026, 5, 28),
            },
        ),
        (
            "idfc",
            "idfc/account_imps_credit.txt",
            {
                "email_type": "idfc_account_imps_credit_alert",
                "direction": "credit",
                "amount": Decimal("50000.00"),
                "currency": "INR",
                "account_mask": "XXXXXXXX000",
                "counterparty": "Mobile XXXXXXXXX000",
                "reference_number": "000000000000",
                "channel": "imps",
                "transaction_date": datetime.date(2026, 5, 2),
            },
        ),
        (
            "idfc",
            "idfc/account_imps_credit_175.txt",
            {
                "email_type": "idfc_account_imps_credit_alert",
                "direction": "credit",
                "amount": Decimal("100000.00"),
                "currency": "INR",
                "account_mask": "XXXXXXXX000",
                "counterparty": "Mobile XXXXXXXXX000",
                "reference_number": "000000000001",
                "channel": "imps",
                "transaction_date": datetime.date(2026, 5, 26),
            },
        ),
        (
            "idfc",
            "idfc/account_imps_credit_200.txt",
            {
                "email_type": "idfc_account_imps_credit_alert",
                "direction": "credit",
                "amount": Decimal("123456.00"),
                "currency": "INR",
                "account_mask": "XXXXXXXX000",
                "counterparty": "Mobile XXXXXXXXX000",
                "reference_number": "000000000002",
                "channel": "imps",
                "transaction_date": datetime.date(2026, 5, 28),
            },
        ),
        (
            "idfc",
            "idfc/account_debit_with_balance.txt",
            {
                "email_type": "idfc_account_balance_debit_alert",
                "direction": "debit",
                "amount": Decimal("1234.00"),
                "currency": "INR",
                "account_mask": "XXXXX000",
                "balance": Decimal("0.00"),
                "transaction_date": datetime.date(2026, 5, 16),
                "transaction_time": datetime.time(9, 30),
            },
        ),
        (
            "idfc",
            "idfc/account_credit_with_balance.txt",
            {
                "email_type": "idfc_account_balance_credit_alert",
                "direction": "credit",
                "amount": Decimal("1234.00"),
                "currency": "INR",
                "account_mask": "XXXXX000",
                "balance": Decimal("999999.99"),
                "transaction_date": datetime.date(2026, 5, 16),
                "transaction_time": datetime.time(9, 30),
            },
        ),
        (
            "idfc",
            "idfc/account_balance_credit_182.txt",
            {
                "email_type": "idfc_account_balance_credit_alert",
                "direction": "credit",
                "amount": Decimal("20000.00"),
                "currency": "INR",
                "account_mask": "XXXXX000001",
                "balance": Decimal("123456.00"),
                "transaction_date": datetime.date(2026, 5, 26),
                "transaction_time": datetime.time(15, 35),
            },
        ),
        (
            "indusind",
            "indusind/account_dc_purchase.txt",
            {
                "email_type": "indusind_account_dc_purchase_alert",
                "direction": "debit",
                "amount": Decimal("2345.00"),
                "currency": "INR",
                "account_mask": "000***000000",
                "balance": Decimal("12345.67"),
                "channel": "card",
            },
        ),
        (
            "indusind",
            "indusind/account_dc_purchase_170.txt",
            {
                "email_type": "indusind_account_dc_purchase_alert",
                "direction": "debit",
                "amount": Decimal("1000.00"),
                "currency": "INR",
                "account_mask": "000***000000",
                "balance": Decimal("0.00"),
                "channel": "card",
            },
        ),
        # Jupiter Edge CC spend: ₹-prefixed amount, ISO-8601 timestamp with an
        # embedded +05:30 (IST) offset, and no card mask in the template.
        (
            "jupiter",
            "jupiter/cc_spend_227.txt",
            {
                "email_type": "jupiter_cc_transaction_alert",
                "direction": "debit",
                "amount": Decimal("100.00"),
                "currency": "INR",
                "card_mask": None,
                "counterparty": "SampleMerchant Bengaluru kaIN",
                "channel": "card",
                "transaction_date": datetime.date(2026, 5, 29),
                "transaction_time": datetime.time(17, 55, 25, 123456),
            },
        ),
        # Kotak debit card spend. The body gives a date and a balance but no
        # time, so the parser takes the time from received_at.
        (
            "kotak",
            "kotak/dc_spend_990.txt",
            {
                "email_type": "kotak_dc_transaction_alert",
                "direction": "debit",
                "amount": Decimal("1234.56"),
                "currency": "INR",
                "card_mask": "XX0000",
                "counterparty": "SAMPLE MERCHANT",
                "channel": "card",
                "transaction_date": datetime.date(2026, 7, 16),
                "transaction_time": None,
            },
        ),
        (
            "kotak",
            "kotak/dc_spend_991.txt",
            {
                "email_type": "kotak_dc_transaction_alert",
                "direction": "debit",
                "amount": Decimal("2500.00"),
                "currency": "INR",
                "card_mask": "XX0000",
                "counterparty": "TESTCO",
                "channel": "card",
                "transaction_date": datetime.date(2026, 7, 27),
                "transaction_time": None,
            },
        ),
        # Jupiter Edge CC payment messages do not contain a date or card mask.
        # A separate test checks the received_at value.
        (
            "jupiter",
            "jupiter/cc_payment_received_963.txt",
            {
                "email_type": "jupiter_cc_payment_received_alert",
                "direction": "credit",
                "amount": Decimal("123.45"),
                "currency": "INR",
                "card_mask": None,
                "counterparty": "Payment received",
                "channel": "card",
                "transaction_date": None,
                "transaction_time": None,
            },
        ),
        (
            "jupiter",
            "jupiter/cc_payment_received_964.txt",
            {
                "email_type": "jupiter_cc_payment_received_alert",
                "direction": "credit",
                "amount": Decimal("678.90"),
                "currency": "INR",
                "card_mask": None,
                "counterparty": "Payment received",
                "channel": "card",
                "transaction_date": None,
                "transaction_time": None,
            },
        ),
        # HDFC debit-card transaction reversal: money returned to the DC, so
        # direction is credit. "By PAYZAPP0000000" is the reversing
        # merchant/acquirer; the colon-separated datetime is the reversal time.
        (
            "hdfc",
            "hdfc/dc_reversal.txt",
            {
                "email_type": "hdfc_dc_reversal_alert",
                "direction": "credit",
                "amount": Decimal("2"),
                "currency": "INR",
                "card_mask": "xx0000",
                "counterparty": "PAYZAPP0000000",
                "channel": "card",
                "transaction_date": datetime.date(2026, 6, 1),
                "transaction_time": datetime.time(13, 21, 20),
            },
        ),
        # HDFC credit-card transaction reversal: same "Transaction Reversed!On"
        # template as the DC reversal but on the CREDIT card, so it emits the
        # CC-specific email_type. Money returns to the CC → direction credit.
        (
            "hdfc",
            "hdfc/cc_reversal.txt",
            {
                "email_type": "hdfc_cc_reversal_alert",
                "direction": "credit",
                "amount": Decimal("2"),
                "currency": "INR",
                "card_mask": "xx0000",
                "counterparty": "PAYZAPP0000000",
                "channel": "card",
                "transaction_date": datetime.date(2026, 7, 6),
                "transaction_time": datetime.time(17, 23, 32),
            },
        ),
        # IDFC outward IMPS debit phrased as "a/c ending <digits> ... debited
        # ... and a/c ending <digits> credited (IMPS Ref no ...)". The source
        # masks use "ending <digits>" (no XX prefix); destination account is the
        # counterparty.
        (
            "idfc",
            "idfc/account_imps_outward.txt",
            {
                "email_type": "idfc_account_imps_outward_alert",
                "direction": "debit",
                "amount": Decimal("15000.00"),
                "currency": "INR",
                "account_mask": "XXXXXXXX000",
                "counterparty": "Acct XXXXXXXXX000",
                "reference_number": "000000000000",
                "channel": "imps",
                "transaction_date": datetime.date(2026, 6, 1),
            },
        ),
        # ICICI account IMPS credit: "ICICI Bank Account XX### is credited with
        # Rs ... by Account linked to mobile number XXXXX####. IMPS Ref. no. ...".
        # Distinct from the UPI credit shape ("Dear Customer, Acct ... UPI:...").
        (
            "icici",
            "icici/account_imps_credit.txt",
            {
                "email_type": "icici_account_imps_credit_alert",
                "direction": "credit",
                "amount": Decimal("15000.00"),
                "currency": "INR",
                "account_mask": "XX000",
                "counterparty": "Mobile XXXXX00000",
                "reference_number": "000000000000",
                "channel": "imps",
                "transaction_date": datetime.date(2026, 6, 1),
            },
        ),
        # ICICI account "debited Rs. ... Info<X>.Avl Bal" outward debit. The
        # Info descriptor is the channel/narration; "RTGS*<ref>" yields channel
        # rtgs + a reference. The trailing "To dispute call..." boilerplate must
        # never leak into counterparty/reference.
        (
            "icici",
            "icici/account_debit_info_rtgs.txt",
            {
                "email_type": "icici_account_debit_info_alert",
                "direction": "debit",
                "amount": Decimal("12345.00"),
                "currency": "INR",
                "account_mask": "XX000",
                "counterparty": "RTGS*ICICR000",
                "reference_number": "ICICR000",
                "channel": "rtgs",
                "balance": Decimal("0.00"),
                "transaction_date": datetime.date(2026, 6, 11),
            },
        ),
        # "TRF TO FD no." is a transfer into a fixed deposit — counterparty is
        # labeled "ICICI FD" so the categorizer reads it as an investment. It
        # carries no ref token, so reference_number stays None (must not scrape
        # boilerplate as a ref).
        (
            "icici",
            "icici/account_debit_info_trf_fd.txt",
            {
                "email_type": "icici_account_debit_info_alert",
                "direction": "debit",
                "amount": Decimal("23456.00"),
                "currency": "INR",
                "account_mask": "XX000",
                "counterparty": "ICICI FD",
                "reference_number": None,
                "channel": None,
                "balance": Decimal("32109.00"),
                "transaction_date": datetime.date(2026, 6, 11),
            },
        ),
        # ICICI account "credited:Rs. ... Info <Y>. Available Balance is Rs. Z"
        # inward credit. "BIL*INFT*<ref>*" → channel imps (INFT) + ref.
        (
            "icici",
            "icici/account_credit_info_bil_inft.txt",
            {
                "email_type": "icici_account_credit_info_alert",
                "direction": "credit",
                "amount": Decimal("54321.00"),
                "currency": "INR",
                "account_mask": "XX000",
                "counterparty": "BIL*INFT*FFF0000000*",
                "reference_number": "FFF0000000",
                "channel": "imps",
                "balance": Decimal("54321.00"),
                "transaction_date": datetime.date(2026, 6, 11),
            },
        ),
        # For NEFT text, use the sender name after the reference as counterparty.
        (
            "icici",
            "icici/account_credit_info_neft.txt",
            {
                "email_type": "icici_account_credit_info_alert",
                "direction": "credit",
                "amount": Decimal("12345.67"),
                "currency": "INR",
                "account_mask": "XX000",
                "counterparty": "CUSTOMER NAME",
                "reference_number": "HDFCH00000000000",
                "channel": "neft",
                "balance": Decimal("23456.78"),
                "transaction_date": datetime.date(2026, 7, 27),
            },
        ),
        # Same credit shape with "RTGS-<ref>-" → channel rtgs + ref.
        (
            "icici",
            "icici/account_credit_info_rtgs.txt",
            {
                "email_type": "icici_account_credit_info_alert",
                "direction": "credit",
                "amount": Decimal("23456.00"),
                "currency": "INR",
                "account_mask": "XX000",
                "counterparty": "RTGS-HDFCR00000000000000000-",
                "reference_number": "HDFCR00000000000000000",
                "channel": "rtgs",
                "balance": Decimal("34000.00"),
                "transaction_date": datetime.date(2026, 6, 11),
            },
        ),
        # HDFC savings-to-PPF/SSY transfer debit; no in-body date, so
        # transaction_date is None without received_at.
        (
            "hdfc",
            "hdfc/account_transfer_ppf.txt",
            {
                "email_type": "hdfc_account_transfer_debit_alert",
                "direction": "debit",
                "amount": Decimal("100000.00"),
                "currency": "INR",
                "counterparty": "PPF/SSY A/c XX0000",
                "channel": "online",
                "transaction_date": None,
            },
        ),
        # IDFC RTGS outward debit.
        (
            "idfc",
            "idfc/account_rtgs_debit.txt",
            {
                "email_type": "idfc_account_rtgs_debit_alert",
                "direction": "debit",
                "amount": Decimal("200000.00"),
                "currency": "INR",
                "account_mask": "XXXXXXX0000",
                "counterparty": "SAMPLE NAME",
                "reference_number": "IDFBR60000000000000000",
                "balance": Decimal("99999.99"),
                "channel": "rtgs",
                "transaction_date": datetime.date(2026, 6, 5),
            },
        ),
        # IDFC NEFT outward debit: same "has been debited by Rs. ... New bal:"
        # frame as RTGS, discriminated by the "Info: NEFT/ <utr>/<name>" clause.
        (
            "idfc",
            "idfc/account_neft_debit.txt",
            {
                "email_type": "idfc_account_neft_debit_alert",
                "direction": "debit",
                "amount": Decimal("12345.00"),
                "currency": "INR",
                "account_mask": "XXXXXXX0000",
                "counterparty": "BENEFICIARY NAME",
                "reference_number": "IDFB0000X0000000",
                "balance": Decimal("1234.56"),
                "channel": "neft",
                "transaction_date": datetime.date(2026, 6, 5),
            },
        ),
        # IDFC NEFT beneficiary-received confirmation: a confirmation that a NEFT
        # the user *initiated* reached the beneficiary. Direction=debit (money
        # left the user); no account mask and no balance in this template.
        (
            "idfc",
            "idfc/account_neft_beneficiary_credit.txt",
            {
                "email_type": "idfc_account_neft_beneficiary_credit_alert",
                "direction": "debit",
                "amount": Decimal("12345.00"),
                "currency": "INR",
                "account_mask": None,
                "counterparty": "BENEFICIARY NAME",
                "reference_number": "IDFB0000X0000000",
                "channel": "neft",
                "transaction_date": None,
            },
        ),
        # The HDFC NEFT debit message does not contain a beneficiary, reference,
        # balance, or date.
        (
            "hdfc",
            "hdfc/account_neft_debit.txt",
            {
                "email_type": "hdfc_account_neft_debit_alert",
                "direction": "debit",
                "amount": Decimal("12345.67"),
                "currency": "INR",
                "account_mask": "XX0000",
                "counterparty": None,
                "reference_number": None,
                "channel": "neft",
                "transaction_date": None,
                "transaction_time": None,
            },
        ),
        # HDFC net-banking payee transfer debit. The bank names no rail, so the
        # channel is "online". The SMS carries no payee, reference, balance, or
        # in-body date.
        (
            "hdfc",
            "hdfc/account_online_transfer_debit.txt",
            {
                "email_type": "hdfc_account_online_transfer_debit_alert",
                "direction": "debit",
                "amount": Decimal("12345.67"),
                "currency": "INR",
                "account_mask": "XX0000",
                "counterparty": None,
                "reference_number": None,
                "channel": "online",
                "transaction_date": None,
                "transaction_time": None,
            },
        ),
        # HDFC RTGS "initiated" outward debit. This "initiated" leg is the only
        # one parsed; the "RTGS Money Deposited~..." confirmation twin is
        # recognized and skipped. It names the source account (kept for
        # attribution) but no payee, reference, balance, or in-body date.
        (
            "hdfc",
            "hdfc/account_rtgs_debit.txt",
            {
                "email_type": "hdfc_account_rtgs_debit_alert",
                "direction": "debit",
                "amount": Decimal("123456"),
                "currency": "INR",
                "account_mask": "XX0000",
                "counterparty": None,
                "reference_number": None,
                "channel": "rtgs",
                "transaction_date": None,
            },
        ),
        # Same outward RTGS debit worded "RTGS transaction initiated:" (the full
        # word) rather than "txn". Both wordings share one shape and email_type.
        # HDFC changed the wording between real transfers (June "txn", August
        # "transaction"), so both must parse.
        (
            "hdfc",
            "hdfc/account_rtgs_debit_transaction.txt",
            {
                "email_type": "hdfc_account_rtgs_debit_alert",
                "direction": "debit",
                "amount": Decimal("123456.78"),
                "currency": "INR",
                "account_mask": "XX0000",
                "counterparty": None,
                "reference_number": None,
                "channel": "rtgs",
                "transaction_date": None,
            },
        ),
        # HDFC outward RTGS settlement leg ("RTGS Money Deposited~..."). Carries
        # the UTR, beneficiary, and exact in-body date+time; no source account
        # mask (the dashboard fuses this UTR onto the initiated debit row).
        (
            "hdfc",
            "hdfc/account_rtgs_deposited.txt",
            {
                "email_type": "hdfc_account_rtgs_deposited_alert",
                "direction": "debit",
                "amount": Decimal("200000.00"),
                "currency": "INR",
                "account_mask": None,
                "counterparty": "SAMPLE NAME",
                "reference_number": "HDFCR00000000000000000",
                "channel": "rtgs",
                "transaction_date": datetime.date(2026, 8, 21),
                "transaction_time": datetime.time(1, 6, 23),
            },
        ),
        # IDFC inbound NEFT credit: the credit counterpart of the outward NEFT
        # debit, using the same "credited with Rs. ... Info: NEFT/<utr>/<name>.
        # New bal:" frame as the RTGS credit but with the NEFT rail token.
        (
            "idfc",
            "idfc/account_neft_credit.txt",
            {
                "email_type": "idfc_account_neft_credit_alert",
                "direction": "credit",
                "amount": Decimal("2500.00"),
                "currency": "INR",
                "account_mask": "XXXXXXX0000",
                "counterparty": "SAMPLE NAME",
                "reference_number": "IN00000000000000",
                "balance": Decimal("99999.99"),
                "channel": "neft",
                "transaction_date": datetime.date(2026, 8, 21),
            },
        ),
        # IDFC inbound RTGS credit: the "credited with Rs. ... Info: RTGS/
        # <ref>/<name>" frame is the credit counterpart of the outward RTGS
        # debit. Remitter name is the counterparty; the RTGS reference and the
        # new balance are carried.
        (
            "idfc",
            "idfc/account_rtgs_credit.txt",
            {
                "email_type": "idfc_account_rtgs_credit_alert",
                "direction": "credit",
                "amount": Decimal("200000.00"),
                "currency": "INR",
                "account_mask": "XXXXXXX0000",
                "counterparty": "SAMPLE NAME",
                "reference_number": "HDFCR00000000000000000",
                "balance": Decimal("99999.99"),
                "channel": "rtgs",
                "transaction_date": datetime.date(2026, 8, 21),
            },
        ),
    ],
)
def test_parses_real_sms(bank, fixture, expected) -> None:
    body = _read(fixture)
    result = parse_sms(bank, body)
    _assert_matches(result, expected)


def test_jupiter_cc_payment_uses_received_at_for_datetime_fallback() -> None:
    body = _read("jupiter/cc_payment_received_963.txt")
    # 21:45 UTC on 2026-07-26 is 03:15 IST on 2026-07-27.
    received = datetime.datetime(2026, 7, 26, 21, 45, tzinfo=datetime.UTC)
    result = parse_sms("jupiter", body, received_at=received)
    assert result.transaction is not None
    assert result.transaction.transaction_date == datetime.date(2026, 7, 27)
    assert result.transaction.transaction_time == datetime.time(3, 15)


def test_sbi_cc_payment_uses_received_at_for_date_fallback() -> None:
    body = _read("sbi/cc_payment_received.txt")
    # 21:45 UTC on 2026-08-13 is 03:15 IST on 2026-08-14.
    received = datetime.datetime(2026, 8, 13, 21, 45, tzinfo=datetime.UTC)
    result = parse_sms("sbi", body, received_at=received)
    assert result.event_time_source == "message_arrival"
    assert result.identifies_by == "none"
    assert result.transaction is not None
    assert result.transaction.transaction_date == datetime.date(2026, 8, 14)
    assert result.transaction.card_mask is None


def test_sbi_dc_and_cc_spends_stay_distinct() -> None:
    """The debit-card and credit-card spend shapes must not shadow each
    other. Each parser claims only its own wording."""
    dc = parse_sms("sbi", _read("sbi/dc_transaction.txt"))
    assert dc.email_type == "sbi_dc_transaction_alert"
    cc = parse_sms("sbi", _read("sbi/cc_spend_889.txt"))
    assert cc.email_type == "sbi_cc_transaction_alert"


def test_indusind_cc_payment_is_primary_and_accepts_optional_period() -> None:
    body = _read("indusind/cc_payment_received.txt").rstrip() + "."
    result = parse_sms("indusind", body)
    assert result.email_type == "indusind_cc_payment_received_alert"
    assert result.ledger_role == "primary"
    assert result.transaction is not None
    assert result.transaction.direction == "credit"


@pytest.mark.parametrize(
    "bank, fixture",
    [
        ("onecard", "onecard/negative/limit_update.txt"),
        ("onecard", "onecard/negative/statement_ready.txt"),
        ("equitas", "equitas/negative/payment_due.txt"),
        ("equitas", "equitas/negative/statement_generated.txt"),
        ("equitas", "equitas/negative/mobile_login_failed.txt"),
        ("idfc", "idfc/negative/asba_blocked.txt"),
        ("idfc", "idfc/negative/asba_unblocked.txt"),
    ],
)
def test_real_negative_fixtures_raise_parse_error(bank, fixture) -> None:
    body = _read(fixture)
    with pytest.raises(ParseError):
        parse_sms(bank, body)


@pytest.mark.parametrize(
    "fixture",
    [
        "idfc/negative/asba_blocked.txt",
        "idfc/negative/asba_unblocked.txt",
    ],
)
def test_idfc_asba_notices_are_recognized_stubs(fixture) -> None:
    """Both ASBA lifecycle shapes must carry the recognized-stub marker so
    the downstream pipeline dispositions them as skipped, not failed."""
    body = _read(fixture)
    with pytest.raises(ParseError) as excinfo:
        parse_sms("idfc", body)
    assert "idfc_asba_notice_stub: ParserStubError" in str(excinfo.value)


def test_hdfc_neft_debit_uses_received_at_for_datetime() -> None:
    body = _read("hdfc/account_neft_debit.txt")
    # 19:33 UTC on 2026-07-26 is 01:03 IST on 2026-07-27.
    received = datetime.datetime(2026, 7, 26, 19, 33, tzinfo=datetime.UTC)
    result = parse_sms("hdfc", body, received_at=received)
    assert result.transaction is not None
    assert result.transaction.transaction_date == datetime.date(2026, 7, 27)
    assert result.transaction.transaction_time == datetime.time(1, 3)


def test_hdfc_online_transfer_debit_uses_received_at_for_datetime() -> None:
    body = _read("hdfc/account_online_transfer_debit.txt")
    # 19:33 UTC on 2026-07-26 is 01:03 IST on 2026-07-27.
    received = datetime.datetime(2026, 7, 26, 19, 33, tzinfo=datetime.UTC)
    result = parse_sms("hdfc", body, received_at=received)
    assert result.event_time_source == "message_arrival"
    assert result.transaction is not None
    assert result.transaction.transaction_date == datetime.date(2026, 7, 27)
    assert result.transaction.transaction_time == datetime.time(1, 3)


def test_hdfc_online_transfer_debit_does_not_shadow_neft() -> None:
    """The "Money Transfer" shape and the "NEFT txn" shape stay distinct.

    Each parser must claim only its own wording."""
    online = parse_sms("hdfc", _read("hdfc/account_online_transfer_debit.txt"))
    assert online.email_type == "hdfc_account_online_transfer_debit_alert"
    assert online.transaction is not None
    assert online.transaction.channel == "online"
    neft = parse_sms("hdfc", _read("hdfc/account_neft_debit.txt"))
    assert neft.email_type == "hdfc_account_neft_debit_alert"


def test_hdfc_rtgs_initiated_omits_balance_and_reference() -> None:
    """The RTGS "initiated" alert carries neither a balance nor a reference
    number, and no payee; all must stay None rather than be fabricated. It
    does name the source account, which the confirmation twin omits."""
    body = _read("hdfc/account_rtgs_debit.txt")
    result = parse_sms("hdfc", body)
    assert result.transaction is not None
    assert result.transaction.balance is None
    assert result.transaction.reference_number is None
    assert result.transaction.counterparty is None
    assert result.transaction.account_mask == "XX0000"


def test_hdfc_rtgs_initiated_uses_received_at_for_date_fallback() -> None:
    """The RTGS "initiated" body carries no date; received_at (UTC→IST)
    fills transaction_date/time, like the bank's other dateless shapes."""
    body = _read("hdfc/account_rtgs_debit.txt")
    # 2026-06-13 21:30 UTC == 2026-06-14 03:00 IST
    received = datetime.datetime(2026, 6, 13, 21, 30, tzinfo=datetime.UTC)
    result = parse_sms("hdfc", body, received_at=received)
    assert result.transaction is not None
    assert result.transaction.transaction_date == datetime.date(2026, 6, 14)
    assert result.transaction.transaction_time == datetime.time(3, 0)


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


def test_hdfc_account_transfer_uses_received_at_for_date_fallback() -> None:
    """HDFC PPF/SSY transfer SMS carries no date; received_at (UTC→IST) fills it."""
    body = _read("hdfc/account_transfer_ppf.txt")
    # 2026-06-05 21:30 UTC == 2026-06-06 03:00 IST
    received = datetime.datetime(2026, 6, 5, 21, 30, tzinfo=datetime.UTC)
    result = parse_sms("hdfc", body, received_at=received)
    assert result.transaction is not None
    assert result.transaction.transaction_date == datetime.date(2026, 6, 6)
    assert result.transaction.transaction_time == datetime.time(3, 0)


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


def test_hdfc_cc_upi_uses_received_at_for_date_fallback() -> None:
    """The CC-on-UPI body's "On DD-MM" has no year/time; received_at
    (UTC->IST) fills transaction_date/time, like the bank's dateless shapes."""
    body = _read("hdfc/cc_upi_spend.txt")
    # 2026-05-23 12:01:32 UTC == 2026-05-23 17:31:32 IST
    received = datetime.datetime(2026, 5, 23, 12, 1, 32, tzinfo=datetime.UTC)
    result = parse_sms("hdfc", body, received_at=received)
    assert result.transaction is not None
    assert result.transaction.transaction_date == datetime.date(2026, 5, 23)
    assert result.transaction.transaction_time == datetime.time(17, 31, 32)


def test_hdfc_cc_upi_no_received_at_leaves_date_none() -> None:
    """Without received_at there is no date to anchor to; never fabricate."""
    body = _read("hdfc/cc_upi_spend.txt")
    result = parse_sms("hdfc", body)
    assert result.transaction is not None
    assert result.transaction.transaction_date is None
    assert result.transaction.transaction_time is None


def test_hdfc_refund_not_shadowed_by_cc_upi_pattern() -> None:
    """The CC-spend parser (which now also matches a UPI shape) runs before
    the refund parser; the existing refund fixture must still parse as a
    credit refund, not get mis-claimed as a UPI debit."""
    result = parse_sms("hdfc", _read("hdfc/cc_refund.txt"))
    assert result.email_type == "hdfc_cc_refund_alert"
    assert result.transaction is not None
    assert result.transaction.direction == "credit"


@pytest.mark.parametrize(
    "bank, body",
    [
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
        # Amount-first spend with a debit-card trailer ("SMS BLOCK DC"): the
        # amount-first CC pattern requires the "SMS BLOCK CC" trailer as its
        # credit-card discriminator, so this must not parse as a CC alert (no
        # amount-first DC template is known yet either).
        (
            "hdfc",
            "Rs.569 spent on HDFC Bank Card x0000 at RAZ*SampleFood on "
            "2026-07-12:17:00:56.Not U? To Block & Reissue Call "
            "18002586161/SMS BLOCK DC 0000 to 7308080808",
        ),
        # The parser requires the fraud report text in an HDFC NEFT debit.
        # This incomplete message must not match.
        (
            "hdfc",
            "Amt Deducted! Rs.100.00 from your HDFC Bank A/c XX0000 for NEFT "
            "txn via HDFC Bank Online Banking",
        ),
        # Equitas service-info SMS that is not a transaction.
        (
            "equitas",
            "Dear Customer, your Equitas CC XX0000 statement is now available. "
            "Login to view.",
        ),
        # HSBC spend truncated before the "Limit Rs" clause — the available-limit
        # clause is a mandatory truncation guard, so this must not parse.
        (
            "hsbc",
            "HSBC creditcard xxxxx0000 used at SampleMerchant Store for INR "
            "100.00 on 01/07/26.",
        ),
        # HSBC OTP surface form: card mask + amount present but no "used at" verb.
        (
            "hsbc",
            "HSBC creditcard xxxxx0000 OTP for INR 100.00 is 123456. Do not share.",
        ),
        # The parser must reject Jupiter payment OTP and pending notices.
        (
            "jupiter",
            "OTP 123456 is for your payment of Rs 100.00 for your Edge CSB Bank "
            "RuPay Credit Card. Do not share it.",
        ),
        # The parser requires the success text and the Jupiter app text.
        # These text items reject an incomplete payment message.
        (
            "jupiter",
            "Your payment of Rs 100.00 for your Edge CSB Bank RuPay Credit Card",
        ),
        # SBI OTP has the same amount and bare card mask but no canonical
        # "spent on your SBI Credit Card" transaction clause.
        (
            "sbi",
            "OTP 123456 is for Rs.100.00 on your SBI Credit Card ending 0000. "
            "Do not share it with anyone.",
        ),
        # The fraud-reporting trailer is the SBI shape's truncation guard.
        (
            "sbi",
            "Rs.100.00 spent on your SBI Credit Card ending 0000 at SAMPLE MART "
            "on 19/07/26.",
        ),
        # A generic ICICI mandate notice is not an executed debit; only the full
        # "successfully redeemed through RRN" template is transactional.
        (
            "icici",
            "Dear Customer, your account has been unblocked by INR 1,234.56 "
            "against a UPI one-time mandate - ICICI Bank.",
        ),
        # IndusInd statement reminders mention payments and amounts but are not
        # payment-received events.
        (
            "indusind",
            "Statement Alert: Amount Due on your IndusInd Bank Credit Card is "
            "INR 1,234.56. Payment to be made by 18/08/26.",
        ),
        # A truncated slice RTGS credit without its mandatory balance must fail.
        (
            "slice",
            "Rs. 12,345 has been credited to your A/c xx0000 from CUSTOMER NAME "
            "on 18-Jul-26 via RTGS (Ref ID: SAMPLE00000000000000000)",
        ),
    ],
)
def test_synthetic_adversarial_bodies_raise_parse_error(bank, body) -> None:
    with pytest.raises(ParseError):
        parse_sms(bank, body)


def test_hdfc_cc_payment_ledger_roles_by_template() -> None:
    """The ref-bearing settlement carries the ledger event; both no-ref
    "received" shapes are provisional pre-announcements of it. The role is
    assigned per template, not inferred from ref-presence at the consumer."""
    settlement = (
        "HDFC Bank Cardmember, Online Payment of Rs.100 vide Ref# 000ABCDE "
        "was credited to your card ending 0000 On 08/MAY/2026"
    )
    provisional_upper = (
        "DEAR HDFCBANK CARDMEMBER, PAYMENT OF Rs. 100.00 RECEIVED TOWARDS "
        "YOUR CREDIT CARD ENDING WITH 0000 ON 17-5-2026. YOUR AVAILABLE "
        "LIMIT IS RS. 200.00"
    )
    provisional_noref = (
        "HDFC Bank Cardmember, Payment of Rs.100 was credited to your card "
        "ending 0000 On 08/MAY/2026"
    )
    parsed_settlement = parse_sms("hdfc", settlement)
    parsed_upper = parse_sms("hdfc", provisional_upper)
    parsed_noref = parse_sms("hdfc", provisional_noref)
    assert parsed_settlement.ledger_role == "primary"
    assert parsed_upper.ledger_role == "provisional"
    assert parsed_noref.ledger_role == "provisional"
    # All three share one email_type; the ref rides on the settlement only.
    assert parsed_settlement.transaction is not None
    assert parsed_noref.transaction is not None
    assert parsed_settlement.transaction.reference_number == "000ABCDE"
    assert parsed_noref.transaction.reference_number is None
    # The uppercase provisional carries the available limit; capture it as
    # balance. The other two templates omit it.
    assert parsed_upper.transaction is not None
    assert parsed_upper.transaction.balance is not None
    assert parsed_upper.transaction.balance.amount == Decimal("200.00")
    assert parsed_settlement.transaction.balance is None
    assert parsed_noref.transaction.balance is None


def test_kotak_dc_spend_takes_the_time_from_received_at() -> None:
    """The body gives a date but no time. The bank sends this SMS at the
    moment of the transaction, so the time of receipt stands for the time of
    the event. The body date stays, because the bank states it."""
    body = (FIXTURES_DIR / "kotak" / "dc_spend_990.txt").read_text()
    result = parse_sms(
        "kotak",
        body,
        received_at=datetime.datetime(2026, 7, 16, 10, 24, 4, tzinfo=datetime.UTC),
    )
    txn = result.transaction
    assert txn is not None
    # 10:24:04 UTC is 15:54:04 IST.
    assert txn.transaction_time == datetime.time(15, 54, 4)
    assert txn.transaction_date == datetime.date(2026, 7, 16)


def test_kotak_dc_spend_keeps_the_balance() -> None:
    """Two spends of the same amount on one day differ only in the balance.
    The consumer needs it to tell them apart."""
    body = (FIXTURES_DIR / "kotak" / "dc_spend_990.txt").read_text()
    txn = parse_sms("kotak", body).transaction
    assert txn is not None
    assert txn.balance is not None
    assert txn.balance.amount == Decimal("9999.99")


def test_kotak_dc_spend_reads_a_merchant_of_several_words() -> None:
    """A merchant name can contain spaces. The capture must stop at ' on
    <date>' and not at the first space."""
    body = (
        "Rs.100.00 spent via Kotak Debit Card XX0000 at SAMPLE STORE CITY on "
        "16/07/2026. Avl bal Rs.1.00 Not you?Tap https://kotak.com/KBANKT/Fraud"
    )
    txn = parse_sms("kotak", body).transaction
    assert txn is not None
    assert txn.counterparty == "SAMPLE STORE CITY"


def test_kotak_rejects_a_body_without_the_fraud_text() -> None:
    """The fraud report text ends the message. Without it the body can be an
    OTP or a part of a message."""
    with pytest.raises(ParseError):
        parse_sms(
            "kotak",
            "Rs.100.00 spent via Kotak Debit Card XX0000 at SHOP on 16/07/2026.",
        )


def test_kotak_dc_spend_declares_that_the_time_comes_from_arrival() -> None:
    """The body gives no time, and the bank sends this SMS at the moment of
    the transaction. The consumer must know that, so it can give the row a
    smaller window when it looks for the matching message."""
    from bank_sms_parser.parsers.kotak import KotakDcTransactionAlertParser

    assert KotakDcTransactionAlertParser.event_time_source == "message_arrival"
    body = (FIXTURES_DIR / "kotak" / "dc_spend_990.txt").read_text()
    result = parse_sms(
        "kotak",
        body,
        received_at=datetime.datetime(2026, 7, 16, 10, 24, 4, tzinfo=datetime.UTC),
    )
    assert result.event_time_source == "message_arrival"
