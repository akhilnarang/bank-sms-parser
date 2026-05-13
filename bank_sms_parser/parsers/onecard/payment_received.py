"""OneCard CC bill-payment-received SMS parser."""

import datetime
import re

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BaseSmsParser
from bank_sms_parser.parsing import normalize_whitespace, parse_amount, parse_date


class OnecardCcPaymentReceivedParser(BaseSmsParser):
    """OneCard CC bill-payment-received notification.

    Sample:
        "Hola! that was sweet. We have received payment against your
         OneCard for Rs. 10,000.00 on 29 Apr 2026."

    Note: this template carries no card mask — per spec §10, payment-received
    alerts may omit the mask if the bank's template lacks one.
    """

    bank = "onecard"
    email_type = "onecard_cc_payment_received_alert"

    _PATTERN = re.compile(
        r"Hola!\s+that\s+was\s+sweet\.\s+"
        r"We\s+have\s+received\s+payment\s+against\s+your\s+OneCard\s+for\s+"
        r"Rs\.?\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+on\s+(?P<date>\d{1,2}\s+\w+\s+\d{4})"
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
            raise ParseError("OneCard CC payment-received pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
            ),
        )
