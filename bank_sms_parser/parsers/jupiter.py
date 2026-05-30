"""Jupiter (Edge CSB Bank RuPay Credit Card) SMS parsers."""

import datetime
import re

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BankSmsParser, BaseSmsParser
from bank_sms_parser.parsing import normalize_whitespace, parse_amount, parse_datetime


class JupiterCcTransactionAlertParser(BaseSmsParser):
    """Jupiter Edge credit-card spend alert.

    Sample (sanitized):
        "₹100.00 paid from your Edge CSB Bank RuPay Credit Card to
         SampleMerchant Bengaluru kaIN on 2026-05-29T17:55:25.123456+05:30
         IST. To raise an issue, call 0000000000. Thank you for using Jupiter."

    The amount carries the ``₹`` symbol (not ``Rs.``/``INR``), so it is
    captured as a bare numeric and wrapped as INR ``Money`` directly. The
    body has no card mask — Jupiter's Edge template never includes one — so
    ``card_mask`` stays ``None``; the ``paid from your Edge CSB Bank RuPay
    Credit Card to <merchant>`` anchor plus the ``Thank you for using
    Jupiter`` signature make this unambiguous against OTP/promo bodies. The
    timestamp is ISO-8601 with an embedded ``+05:30`` (IST) offset, so the
    date/time are read straight from the body without a ``received_at``
    fallback.
    """

    bank = "jupiter"
    email_type = "jupiter_cc_transaction_alert"

    _PATTERN = re.compile(
        r"₹\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"paid\s+from\s+your\s+Edge\s+CSB\s+Bank\s+RuPay\s+Credit\s+Card\s+"
        r"to\s+(?P<merchant>.+?)\s+"
        r"on\s+(?P<datetime>\d{4}-\d{2}-\d{2}T[\d:.]+\+\d{2}:\d{2})\s+IST"
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
            raise ParseError("Jupiter CC transaction alert pattern did not match")
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
                channel="card",
            ),
        )


_PARSERS: tuple[BaseSmsParser, ...] = (JupiterCcTransactionAlertParser(),)


class JupiterParser(BankSmsParser):
    bank = "jupiter"
    parsers = _PARSERS


def parse(
    body: str,
    *,
    sender: str | None = None,
    received_at: datetime.datetime | None = None,
) -> ParsedSms:
    return JupiterParser().parse(body, sender=sender, received_at=received_at)
