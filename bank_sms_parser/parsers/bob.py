"""Bank of Baroda SMS parsers.

Supported SMS types:
- bob_account_upi_debit_alert: Outbound account UPI debit alert
- bob_account_upi_credit_alert: Inbound account UPI credit alert
"""

import datetime
import re

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BankSmsParser, BaseSmsParser
from bank_sms_parser.parsing import (
    normalize_whitespace,
    parse_amount,
    parse_date,
    parse_datetime,
)


class BobAccountUpiDebitAlertParser(BaseSmsParser):
    """Bank of Baroda account outbound UPI debit alert.

    The body clock has no AM/PM marker, so the parser leaves the transaction
    time unset rather than treating an ambiguous 12-hour value as 24-hour time.

    Sample::

        "Rs.230.00 Dr. from A/C XXXXXX1234 and Cr. to example@okbank. Ref:000000000000.
         AvlBal:Rs618.85(2026:09:06 09:56:33). Not you? Call 18005700/5000-BOB"
    """

    bank = "bob"
    email_type = "bob_account_upi_debit_alert"

    _PATTERN = re.compile(
        r"Rs\.?\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+Dr\.\s+from\s+A/C\s+(?P<account>[X\d]+)\s+"
        r"and\s+Cr\.\s+to\s+(?P<payee>.+?)\.\s+Ref:\s*(?P<ref>[A-Za-z0-9]+)\.\s+"
        r"AvlBal:Rs\s*(?P<balance>-?[\d,]+(?:\.\d+)?)\s*"
        r"\((?P<date>\d{4}[:-]\d{2}[:-]\d{2})\s+\d{1,2}:\d{2}:\d{2}\)",
        re.IGNORECASE,
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        text = normalize_whitespace(body)
        if not (match := self._PATTERN.search(text)):
            raise ParseError("BOB account UPI debit pattern did not match")
        date_str = match.group("date").replace(":", "-")
        txn_date = parse_date(date_str)

        balance = None
        bal_raw = match.group("balance")
        if bal_raw is not None and not bal_raw.startswith("-"):
            balance = Money(amount=parse_amount(bal_raw), currency="INR")

        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=txn_date,
                counterparty=match.group("payee").strip() or None,
                reference_number=match.group("ref"),
                account_mask=match.group("account"),
                channel="upi",
                balance=balance,
            ),
        )


class BobAccountUpiCreditAlertParser(BaseSmsParser):
    """Bank of Baroda account inbound UPI credit alert.

    Sample::

        "Dear BOB UPI User, your account is credited INR 15179.00 on Date
         2026-08-19 02:10:08 PM by UPI Ref No 000000000000 - BOB"

    Also matches the AvlBal variant::

        "Dear BOB UPI User: Your account is credited with INR 50000.00 on
         2026-09-03 10:47:14 AM by UPI Ref No 000000000000; AvlBal: Rs80509.13 - BOB"
    """

    bank = "bob"
    email_type = "bob_account_upi_credit_alert"
    identifies_by = "none"

    _PATTERN = re.compile(
        r"Dear\s+BOB\s+UPI\s+User[:,]\s+[Yy]our\s+account\s+is\s+credited\s+(?:with\s+)?INR\s+"
        r"(?P<amount>[\d,]+(?:\.\d+)?)\s+on\s+(?:Date\s+)?"
        r"(?P<datetime>\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}:\d{2}\s+(?:AM|PM))\s+"
        r"by\s+UPI\s+Ref\s+No\s+(?P<ref>[A-Za-z0-9]+)"
        r"(?:;\s*AvlBal:\s*Rs\s*(?P<balance>-?[\d,]+(?:\.\d+)?))?\s*-\s*BOB",
        re.IGNORECASE,
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        text = normalize_whitespace(body)
        if not (match := self._PATTERN.search(text)):
            raise ParseError("BOB account UPI credit pattern did not match")
        txn_dt = parse_datetime(match.group("datetime"))
        balance = None
        bal_raw = match.group("balance")
        if bal_raw is not None and not bal_raw.startswith("-"):
            balance = Money(amount=parse_amount(bal_raw), currency="INR")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=txn_dt.date(),
                transaction_time=txn_dt.time(),
                reference_number=match.group("ref"),
                channel="upi",
                balance=balance,
            ),
        )


_PARSERS: tuple[BaseSmsParser, ...] = (
    BobAccountUpiDebitAlertParser(),
    BobAccountUpiCreditAlertParser(),
)


class BobParser(BankSmsParser):
    bank = "bob"
    parsers = _PARSERS


def parse(
    body: str,
    *,
    sender: str | None = None,
    received_at: datetime.datetime | None = None,
) -> ParsedSms:
    return BobParser().parse(body, sender=sender, received_at=received_at)
