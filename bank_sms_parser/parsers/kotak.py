"""Kotak Mahindra Bank SMS parsers.

Supported SMS types:
- kotak_dc_transaction_alert: Debit card spend at a merchant
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
    received_at_to_ist,
)


class KotakDcTransactionAlertParser(BaseSmsParser):
    """Parse a Kotak debit card spend.

    Example:
        "Rs.1234.56 spent via Kotak Debit Card XX0000 at SAMPLE MERCHANT on
         16/07/2026. Avl bal Rs.9999.99 Not you?Tap
         https://kotak.com/KBANKT/Fraud"

    Money leaves the account at a merchant, so ``direction`` is ``debit`` and
    ``channel`` is ``card``. The card mask gives ``card_mask`` and the
    merchant gives ``counterparty``.

    The body gives a date but no time. The bank sends this SMS at the moment
    of the transaction, so the parser takes the time from ``received_at``.
    The body date stays, because the bank states it.

    The body gives the balance after the transaction. Two spends of the same
    amount on one day differ only in that balance, so the consumer needs it
    to tell them apart.

    The parser requires the fraud report text. This text prevents a match
    with an OTP or an incomplete message.
    """

    bank = "kotak"
    email_type = "kotak_dc_transaction_alert"
    event_time_source = "message_arrival"

    _PATTERN = re.compile(
        r"Rs\.?\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+spent\s+via\s+"
        r"Kotak\s+Debit\s+Card\s+(?P<card>[X\d]+)\s+"
        r"at\s+(?P<merchant>.+?)\s+on\s+(?P<date>\d{1,2}/\d{1,2}/\d{4})\.\s*"
        r"Avl\s+bal\s+Rs\.?\s*(?P<balance>[\d,]+(?:\.\d+)?)\s+"
        r"Not\s+you\?\s*Tap\s+\S+\s*$",
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
        if not (match := self._PATTERN.fullmatch(text)):
            raise ParseError("Kotak debit card spend pattern did not match")
        txn_time: datetime.time | None = None
        if received_at is not None:
            txn_time = received_at_to_ist(received_at).time()
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=parse_date(match.group("date")),
                transaction_time=txn_time,
                counterparty=match.group("merchant").strip(),
                card_mask=match.group("card"),
                channel="card",
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
            ),
        )


_PARSERS = (KotakDcTransactionAlertParser(),)


class KotakParser(BankSmsParser):
    bank = "kotak"
    parsers = _PARSERS


def parse(
    body: str,
    *,
    sender: str | None = None,
    received_at: datetime.datetime | None = None,
) -> ParsedSms:
    return KotakParser().parse(body, sender=sender, received_at=received_at)
