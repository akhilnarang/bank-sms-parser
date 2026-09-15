"""Canara Bank SMS parsers."""

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


class CanaraAccountUpiDebitAlertParser(BaseSmsParser):
    """Canara Bank account UPI outbound debit alert.

    Sample::

        "Dear Customer, Acct XXXX0000 Dr. INR 7.00 on 13/09/26 to RAHUL SHARMA;
         UPI: 000000000000; Bal INR 8,018.54.Not you?SMS BLOCKUPI to 9900000000-CanaraBank"
    """

    bank = "canara"
    email_type = "canara_account_upi_debit_alert"

    _PATTERN = re.compile(
        r"Dear\s+Customer,\s+Acct\s+(?P<account>[X\d]+)\s+"
        r"Dr\.\s+INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+on\s+"
        r"(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\s+to\s+"
        r"(?P<payee>.+?);\s*UPI:\s*(?P<ref>[A-Za-z0-9]+);\s*"
        r"Bal\s+INR\s+(?P<balance>-?[\d,]+(?:\.\d+)?)\.\s*"
        r"Not\s+you\?SMS\s+BLOCKUPI\s+to\s+\d+\s*-CanaraBank",
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
            raise ParseError("Canara Bank account UPI debit pattern did not match")
        bal_raw = match.group("balance")
        balance = None
        if not bal_raw.startswith("-"):
            balance = Money(amount=parse_amount(bal_raw), currency="INR")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=parse_date(match.group("date")),
                counterparty=match.group("payee").strip() or None,
                reference_number=match.group("ref"),
                account_mask=match.group("account"),
                channel="upi",
                balance=balance,
            ),
        )


class CanaraAccountUpiCreditAlertParser(BaseSmsParser):
    """Canara Bank account UPI inbound credit alert.

    Sample::

        "Dear Customer, Acct XXXX0000 credited with INR 1,250.00 on 13/09/26
         from Mr RAHUL SHARMA; UPI:000000000000; Bal INR 3,775.74-CanaraBank"
    """

    bank = "canara"
    email_type = "canara_account_upi_credit_alert"

    _PATTERN = re.compile(
        r"Dear\s+Customer,\s+Acct\s+(?P<account>[X\d]+)\s+"
        r"credited\s+with\s+INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+on\s+"
        r"(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\s+from\s+"
        r"(?P<sender>.+?);\s*UPI:\s*(?P<ref>[A-Za-z0-9]+);\s*"
        r"Bal\s+INR\s+(?P<balance>-?[\d,]+(?:\.\d+)?)\s*-CanaraBank",
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
            raise ParseError("Canara Bank account UPI credit pattern did not match")
        bal_raw = match.group("balance")
        balance = None
        if not bal_raw.startswith("-"):
            balance = Money(amount=parse_amount(bal_raw), currency="INR")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=parse_date(match.group("date")),
                counterparty=match.group("sender").strip() or None,
                reference_number=match.group("ref"),
                account_mask=match.group("account"),
                channel="upi",
                balance=balance,
            ),
        )


class CanaraAccountTxnDeclinedAlertParser(BaseSmsParser):
    """Canara Bank failed/declined transaction alert.

    Sample::

        "Dear Customer, txn of Rs.637.70 thru A/C XX1234 on 18-8-26 at 14:16:16
         to ACME STORE failed due to INSUFFICIENT FUNDS-Canara Bank"
    """

    bank = "canara"
    email_type = "canara_account_txn_declined_alert"

    _PATTERN = re.compile(
        r"(?:Dear\s+Customer,\s+)?(?P<upi>UPI\s+)?txn\s+of\s+Rs\.?\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"thru\s+A/C\s+(?P<account>[X\d]+)\s+on\s+"
        r"(?P<date>\d{1,2}-\d{1,2}-\d{2,4})\s+at\s+"
        r"(?P<time>\d{1,2}:\d{2}:\d{2})\s+to\s+"
        r"(?P<payee>.+?)\s+failed\s+due\s+to\s+"
        r"(?P<reason>.+?)(?:-Canara\s*Bank|\.\s*If\s+not\s+you)",
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
            raise ParseError("Canara Bank transaction declined pattern did not match")
        channel = "upi" if match.group("upi") else None
        txn_dt = parse_datetime(f"{match.group('date')} {match.group('time')}")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="declined",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=txn_dt.date(),
                transaction_time=txn_dt.time(),
                counterparty=match.group("payee").strip() or None,
                account_mask=match.group("account"),
                channel=channel,
            ),
        )


_PARSERS: tuple[BaseSmsParser, ...] = (
    CanaraAccountUpiDebitAlertParser(),
    CanaraAccountUpiCreditAlertParser(),
    CanaraAccountTxnDeclinedAlertParser(),
)


class CanaraParser(BankSmsParser):
    bank = "canara"
    parsers = _PARSERS


def parse(
    body: str,
    *,
    sender: str | None = None,
    received_at: datetime.datetime | None = None,
) -> ParsedSms:
    return CanaraParser().parse(body, sender=sender, received_at=received_at)
