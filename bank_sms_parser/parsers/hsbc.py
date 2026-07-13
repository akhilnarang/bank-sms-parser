"""HSBC credit-card SMS parser."""

import datetime
import re

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BankSmsParser, BaseSmsParser
from bank_sms_parser.parsing import normalize_whitespace, parse_amount, parse_date


class HsbcCcTransactionAlertParser(BaseSmsParser):
    """HSBC credit-card spend alert.

    Sample shape::

        "HSBC creditcard xxxxx0000 used at SampleMerchant for INR 100.00 on
         01/07/26.Limit Rs 200.00 Due Rs 50.00.Report fraud on +910000000000"

    The card mask is a run of lowercase ``x`` followed by the last digits
    (``xxxxx0000``). ``used at`` marks the debit and introduces the merchant.
    ``Limit Rs`` is the available credit limit, stored in ``balance`` (mirrors
    the ICICI/Axis ``Avl Limit`` convention); the trailing ``Due Rs`` is the
    running statement outstanding and has no model field, so it is dropped.
    The date is ``DD/MM/YY`` (``dayfirst`` handles it).

    ``Limit Rs`` is required, not optional: every real HSBC spend alert carries
    it, so its absence signals a truncated/foreign body that must not parse.
    """

    bank = "hsbc"
    email_type = "hsbc_cc_transaction_alert"

    _PATTERN = re.compile(
        r"HSBC\s+credit\s*card\s+(?P<card>x+\d{4})\s+used\s+at\s+"
        r"(?P<merchant>.+?)\s+for\s+INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"on\s+(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\b"
        r".*?\bLimit\s+Rs\.?\s*(?P<limit>[\d,]+(?:\.\d+)?)",
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
            raise ParseError("HSBC CC transaction alert pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=parse_date(match.group("date")),
                counterparty=match.group("merchant").strip(),
                balance=Money(
                    amount=parse_amount(match.group("limit")), currency="INR"
                ),
                card_mask=match.group("card"),
                channel="card",
            ),
        )


class HsbcCcPaymentReceivedAlertParser(BaseSmsParser):
    """HSBC credit-card bill-payment-received credit alert.

    Sample shape::

        "Dear Customer, we have received a payment of INR 15000.00 for
         credit card ending 0000 on 02-JUL-26. Thank you for using HSBC
         credit card."

    A payment toward the card reduces the CC outstanding, so ``direction``
    is ``credit`` and ``channel`` is ``card``. The card mask is the bare
    last digits after ``credit card ending`` (kept verbatim, matching the
    HDFC ``card ending ####`` convention); the date is ``DD-MON-YY``
    (``dayfirst`` handles it). The template names no payer, so the constant
    ``"Payment received"`` counterparty mirrors the Equitas CC payment
    precedent. The trailing "Thank you for using HSBC credit card" sentence
    is boilerplate and intentionally unanchored.
    """

    bank = "hsbc"
    email_type = "hsbc_cc_payment_received_alert"

    _PATTERN = re.compile(
        r"we\s+have\s+received\s+a\s+payment\s+of\s+INR\s+"
        r"(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"for\s+credit\s+card\s+ending\s+(?P<card>\d+)\s+"
        r"on\s+(?P<date>\d{1,2}-[A-Za-z]{3}-\d{2,4})\b",
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
            raise ParseError("HSBC CC payment-received pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=parse_date(match.group("date")),
                counterparty="Payment received",
                card_mask=match.group("card"),
                channel="card",
            ),
        )


_PARSERS: tuple[BaseSmsParser, ...] = (
    HsbcCcTransactionAlertParser(),
    # Payment-received alert: anchored on "we have received a payment of
    # INR ... for credit card ending"; cannot collide with the spend
    # shape's "used at" anchor, so order is not load-bearing.
    HsbcCcPaymentReceivedAlertParser(),
)


class HsbcParser(BankSmsParser):
    bank = "hsbc"
    parsers = _PARSERS


def parse(
    body: str,
    *,
    sender: str | None = None,
    received_at: datetime.datetime | None = None,
) -> ParsedSms:
    return HsbcParser().parse(body, sender=sender, received_at=received_at)
