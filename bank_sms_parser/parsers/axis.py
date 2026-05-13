"""Axis Bank SMS parsers."""

import datetime
import re

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BankSmsParser, BaseSmsParser
from bank_sms_parser.parsing import normalize_whitespace, parse_amount, parse_date


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


_PARSERS: tuple[BaseSmsParser, ...] = (AxisCcPaymentReceivedParser(),)


class AxisParser(BankSmsParser):
    bank = "axis"
    parsers = _PARSERS


def parse(body: str, *, sender: str | None = None, received_at: datetime.datetime | None = None) -> ParsedSms:
    return AxisParser().parse(body, sender=sender, received_at=received_at)
