"""Axis Bank SMS parsers."""

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


class AxisCcPaymentReceivedParser(BaseSmsParser):
    """Axis CC bill-payment-received notification.

    Sample:
        "Payment of INR 15000 has been received towards your
         Axis Bank Credit Card XX0000 on 02-05-26 - Axis Bank"
    """

    bank = "axis"
    email_type = "axis_cc_payment_received_alert"

    _PATTERN = re.compile(
        r"Payment\s+of\s+INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"has\s+been\s+received\s+towards\s+your\s+"
        r"Axis\s+Bank\s+Credit\s+Card\s+(?P<card>XX\d+)\s+"
        r"on\s+(?P<date>\d{2}-\d{2}-\d{2})"
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
            raise ParseError("Axis CC payment-received pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                card_mask=match.group("card"),
            ),
        )


class AxisCcTransactionAlertParser(BaseSmsParser):
    """Axis credit-card spend alert.

    Sample (multi-line in the wire body; whitespace is normalized first):
        "Spent INR 123.45
         Axis Bank Card no. XX0000
         02-05-26 19:53:18 IST
         SampleMerchant Store
         Avl Limit: INR 99,999.99
         Not you? SMS BLOCK 0000 to 9999999999"

    Discriminators vs the payment-received shape: the "Spent INR" verb,
    the "Axis Bank Card no. XX####" mask, the "DD-MM-YY HH:MM:SS IST"
    stamp, and the trailing "Avl Limit: INR" available-credit line. The
    available credit limit is stored in ``balance`` (a credit card has no
    account balance). ``channel`` is ``card`` — a POS/online swipe.
    """

    bank = "axis"
    email_type = "axis_cc_transaction_alert"

    _PATTERN = re.compile(
        r"Spent\s+INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"Axis\s+Bank\s+Card\s+no\.\s+(?P<card>XX\d+)\s+"
        r"(?P<datetime>\d{2}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+IST\s+"
        r"(?P<merchant>.+?)\s+"
        r"Avl\s+Limit:\s+INR\s+(?P<limit>[\d,]+(?:\.\d+)?)"
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
            raise ParseError("Axis CC transaction alert pattern did not match")
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


class AxisCcReversalAlertParser(BaseSmsParser):
    """Axis credit-card transaction reversal alert.

    Sample (multi-line in the wire body; whitespace is normalized first):
        "Txn reversal of INR 2499 at SAMPLESHOP IN was successful.
         Card no. XX0000
         02-05-26 19:53:18 IST
         Avl Limit: INR 99,999.99
         Axis Bank"

    A reversal credits the amount back to the card, so ``direction`` is
    ``credit`` and the merchant is the ``counterparty``. Discriminator is
    the leading "Txn reversal of INR ... was successful." clause; unlike
    the spend shape, the mask line is a bare "Card no. XX####" (no
    "Axis Bank" prefix). The "Avl Limit" available credit is stored in
    ``balance``; ``channel`` is ``card``.
    """

    bank = "axis"
    email_type = "axis_cc_reversal_alert"

    _PATTERN = re.compile(
        r"Txn\s+reversal\s+of\s+INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"at\s+(?P<merchant>.+?)\s+was\s+successful\.\s+"
        r"Card\s+no\.\s+(?P<card>XX\d+)\s+"
        r"(?P<datetime>\d{2}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+IST\s+"
        r"Avl\s+Limit:\s+INR\s+(?P<limit>[\d,]+(?:\.\d+)?)"
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
            raise ParseError("Axis CC reversal alert pattern did not match")
        dt = parse_datetime(match.group("datetime"))
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
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
    AxisCcPaymentReceivedParser(),
    AxisCcTransactionAlertParser(),
    AxisCcReversalAlertParser(),
)


class AxisParser(BankSmsParser):
    bank = "axis"
    parsers = _PARSERS


def parse(body: str, *, sender: str | None = None, received_at: datetime.datetime | None = None) -> ParsedSms:
    return AxisParser().parse(body, sender=sender, received_at=received_at)
