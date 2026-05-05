"""Equitas Small Finance Bank SMS parsers."""

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


class EquitasCcPaymentReceivedParser(BaseSmsParser):
    """Equitas credit-card bill-payment-received notification.

    Sample (sanitized):
        "INR 12,345.00 was received on 05/05/2026 and was credited to
         your Equitas Credit Card XX9999. Equitas SFB"
    """

    bank = "equitas"
    email_type = "equitas_cc_payment_alert"

    _PATTERN = re.compile(
        r"INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"was\s+received\s+on\s+(?P<date>\d{2}/\d{2}/\d{4})\s+"
        r"and\s+was\s+credited\s+to\s+your\s+Equitas\s+Credit\s+Card\s+"
        r"(?P<card>XX\d+)"
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        text = normalize_whitespace(body)
        match = self._PATTERN.search(text)
        if not match:
            raise ParseError("Equitas CC payment-received pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                counterparty="Payment received",
                card_mask=match.group("card"),
                channel="card",
            ),
        )


class EquitasCcTransactionAlertParser(BaseSmsParser):
    """Equitas credit-card spend alert.

    Sample:
        "INR 30.00 spent on Equitas CC XX0000 at MERCHANT on
         01-05-2026 07:53:18 PM. Available limit is INR. 99,999.99."
    """

    bank = "equitas"
    email_type = "equitas_cc_transaction_alert"

    _PATTERN = re.compile(
        r"INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"spent\s+on\s+Equitas\s+CC\s+(?P<card>XX\d+)\s+"
        r"at\s+(?P<merchant>.+?)\s+"
        r"on\s+(?P<datetime>\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}:\d{2}\s+(?:AM|PM))\.\s+"
        r"Available\s+limit\s+is\s+INR\.\s+(?P<limit>[\d,]+(?:\.\d+)?)"
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        text = normalize_whitespace(body)
        match = self._PATTERN.search(text)
        if not match:
            raise ParseError("Equitas CC transaction alert pattern did not match")
        dt = parse_datetime(match.group("datetime"))
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=dt.date(),
                transaction_time=dt.time(),
                counterparty=match.group("merchant").strip(),
                balance=Money(
                    amount=parse_amount(match.group("limit")), currency="INR"
                ),
                card_mask=match.group("card"),
                channel="card",
            ),
        )


_PARSERS: tuple[BaseSmsParser, ...] = (
    EquitasCcPaymentReceivedParser(),
    EquitasCcTransactionAlertParser(),
)


class EquitasParser(BankSmsParser):
    bank = "equitas"
    parsers = _PARSERS


def parse(body: str, *, sender: str | None = None, received_at: datetime.datetime | None = None) -> ParsedSms:
    return EquitasParser().parse(body, sender=sender, received_at=received_at)
