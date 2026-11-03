"""Yes Bank SMS parsers."""

import datetime
import re

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BankSmsParser, BaseSmsParser
from bank_sms_parser.parsing import normalize_whitespace, parse_amount, parse_datetime


class YesbankAccountChequeDepositAlertParser(BaseSmsParser):
    """Parse a Yes Bank account cheque deposit credit alert.

    Sample (sanitized):
        "INR 12,345.00 credited to A/c XX0000 towards CHQ DEP SAMPLEBANK
         14-OCT-26 SAMPLE BRANCH CUSTOMER NAME Value 15-OCT-2026 10:20:30 .
         Clear Bal is INR 23,456.78 ."

    Money entered the account from a cheque deposit, so this is a credit.
    The body carries the amount, the account mask, the cheque deposit
    narration, the value date and time, and the clear balance. The narration
    is kept in counterparty so it can match bank-statement rows. The time is
    in the body, so no received_at fallback is used.
    """

    bank = "yesbank"
    email_type = "yesbank_account_cheque_deposit_alert"

    _PATTERN = re.compile(
        r"INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+credited\s+to\s+A/c\s+(?P<account>X+\d+)\s+"
        r"towards\s+(?P<narration>CHQ\s+DEP\b.+?)\s+"
        r"Value\s+(?P<date>\d{2}-[A-Za-z]{3}-\d{4})\s+(?P<time>\d{2}:\d{2}:\d{2})\s*\.\s*"
        r"Clear\s+Bal\s+is\s+INR\s+(?P<balance>[\d,]+(?:\.\d+)?)\s*\.\s*$",
        re.IGNORECASE,
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        """Parse one Yes Bank cheque deposit alert.

        Args:
            body: The SMS body text.
            sender: The optional TRAI sender ID.
            received_at: The optional UTC arrival time.

        Returns:
            The parsed message with a credit transaction.

        Raises:
            ParseError: If the body does not match the cheque deposit shape.
        """
        text = normalize_whitespace(body)
        if not (match := self._PATTERN.search(text)):
            raise ParseError("Yes Bank cheque deposit pattern did not match")
        dt = parse_datetime(f"{match.group('date')} {match.group('time')}")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=dt.date(),
                transaction_time=dt.time(),
                counterparty=match.group("narration").strip(),
                account_mask=match.group("account"),
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
                channel="cheque",
            ),
        )


class YesbankAccountRtgsDebitAlertParser(BaseSmsParser):
    """Parse a Yes Bank outgoing RTGS debit SMS.

    Sample (synthetic):
        "Your RTGS from YES BANK Ac with Ref No YESBR9999010100000000 of INR
         12,345.00 has been credited to beneficiary Ac XXXXXXX9999 on
         21-08-2026 at 10:20:30"

    Yes Bank sends only this SMS for an outgoing RTGS transfer. It sends no
    separate debit alert. Thus this message is the primary debit. The body
    omits the source account mask. The body holds the beneficiary mask only.
    The parser does not map it to account_mask. The body has no beneficiary
    name, so counterparty stays empty. The body carries the reference number,
    the amount, and the event date and time.
    """

    bank = "yesbank"
    email_type = "yesbank_account_rtgs_debit_alert"

    _PATTERN = re.compile(
        r"Your\s+RTGS\s+from\s+YES\s+BANK\s+Ac\s+with\s+Ref\s+No\s+(?P<ref>[A-Z0-9]+)\s+"
        r"of\s+INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+has\s+been\s+credited\s+to\s+"
        r"beneficiary\s+Ac\s+X+\d+\s+"
        r"on\s+(?P<date>\d{1,2}-\d{1,2}-\d{4})\s+at\s+(?P<time>\d{1,2}:\d{2}:\d{2})\s*\.?\s*$",
        re.IGNORECASE,
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        """Parse one Yes Bank RTGS debit SMS.

        Args:
            body: The SMS body text.
            sender: The optional TRAI sender ID.
            received_at: The optional UTC arrival time.

        Returns:
            The parsed message with a primary debit transaction.

        Raises:
            ParseError: If the body does not match the RTGS debit shape.
        """
        text = normalize_whitespace(body)
        if not (match := self._PATTERN.search(text)):
            raise ParseError("Yes Bank RTGS debit pattern did not match")
        dt = parse_datetime(f"{match.group('date')} {match.group('time')}")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=dt.date(),
                transaction_time=dt.time(),
                reference_number=match.group("ref"),
                channel="rtgs",
                raw_description=body,
            ),
        )


_PARSERS: tuple[BaseSmsParser, ...] = (
    YesbankAccountChequeDepositAlertParser(),
    YesbankAccountRtgsDebitAlertParser(),
)


class YesbankParser(BankSmsParser):
    bank = "yesbank"
    parsers = _PARSERS


def parse(
    body: str,
    *,
    sender: str | None = None,
    received_at: datetime.datetime | None = None,
) -> ParsedSms:
    """Parse a Yes Bank SMS body.

    Args:
        body: The SMS body text.
        sender: The optional TRAI sender ID.
        received_at: The optional UTC arrival time.

    Returns:
        The parsed message.

    Raises:
        ParseError: If no Yes Bank parser matches the body.
    """
    return YesbankParser().parse(body, sender=sender, received_at=received_at)
