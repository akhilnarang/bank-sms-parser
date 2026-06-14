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

    Two cosmetic body shapes share this event type:

    variant 1 — "INR ... was received ... credited to your Equitas Credit
    Card XX####" (``DD/MM/YYYY`` date, masked ``XX####`` card):
        "INR 12,345.00 was received on 05/05/2026 and was credited to
         your Equitas Credit Card XX9999. Equitas SFB"

    variant 2 — "Thank you for the payment of Rs.... towards Equitas
    Credit Card ####" (``DD/MM/YY`` 2-digit-year date, bare 4-digit card,
    no reference number):
        "Thank you for the payment of Rs.12,345.00 towards Equitas Credit
         Card 0000, this has been credited to your account on 07/06/26.
         Equitas SFB"

    Both reduce the credit-card outstanding, so ``direction`` is
    ``credit`` and ``email_type`` stays ``equitas_cc_payment_alert`` for
    downstream CC-payment reconciliation. Neither template carries a
    reference number.
    """

    bank = "equitas"
    email_type = "equitas_cc_payment_alert"

    _PATTERN = re.compile(
        r"INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"was\s+received\s+on\s+(?P<date>\d{2}/\d{2}/\d{4})\s+"
        r"and\s+was\s+credited\s+to\s+your\s+Equitas\s+Credit\s+Card\s+"
        r"(?P<card>XX\d+)"
    )

    _THANK_YOU = re.compile(
        r"Thank\s+you\s+for\s+the\s+payment\s+of\s+"
        r"Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"towards\s+Equitas\s+Credit\s+Card\s+(?P<card>\d+),?\s+"
        r"this\s+has\s+been\s+credited\s+to\s+your\s+account\s+on\s+"
        r"(?P<date>\d{2}/\d{2}/\d{2})"
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        text = normalize_whitespace(body)
        if match := self._PATTERN.search(text):
            return self._build(match)
        if match := self._THANK_YOU.search(text):
            return self._build(match)
        raise ParseError("Equitas CC payment-received pattern did not match")

    def _build(self, match: re.Match[str]) -> ParsedSms:
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
        if not (match := self._PATTERN.search(text)):
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
