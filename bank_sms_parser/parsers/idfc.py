"""IDFC FIRST Bank SMS parsers."""

import datetime
import re

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BankSmsParser, BaseSmsParser
from bank_sms_parser.parsing import normalize_whitespace, parse_amount, parse_date


class IdfcCcPaymentReceivedParser(BaseSmsParser):
    """IDFC FIRST Wealth CC bill-payment-received notification.

    Sample:
        "Thank you for payment of INR 3,000.00 towards your
         FIRST Wealth Credit Card XX0000 on 02 May 2026. IDFC FIRST Bank"
    """

    bank = "idfc"
    email_type = "idfc_cc_payment_received_alert"

    _PATTERN = re.compile(
        r"Thank\s+you\s+for\s+payment\s+of\s+INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"towards\s+your\s+FIRST\s+Wealth\s+Credit\s+Card\s+(?P<card>XX\d+)\s+"
        r"on\s+(?P<date>\d{1,2}\s+\w+\s+\d{4})"
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
            raise ParseError("IDFC CC payment-received pattern did not match")
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


_PARSERS: tuple[BaseSmsParser, ...] = (IdfcCcPaymentReceivedParser(),)


class IdfcParser(BankSmsParser):
    bank = "idfc"
    parsers = _PARSERS


def parse(body: str, *, sender: str | None = None, received_at: datetime.datetime | None = None) -> ParsedSms:
    return IdfcParser().parse(body, sender=sender, received_at=received_at)
