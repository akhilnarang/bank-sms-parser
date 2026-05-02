"""ICICI credit-card SMS parser."""

import datetime
import re

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BaseSmsParser
from bank_sms_parser.parsing import normalize_whitespace, parse_amount, parse_date


class IciciCcTransactionAlertParser(BaseSmsParser):
    """ICICI credit-card spend alert.

    Sample:
        "INR 1,604.00 spent using ICICI Bank Card XX0000 on 01-May-26
         on ONYX BAR. Avl Limit: INR 99,99,999.99. ..."
    """

    bank = "icici"
    email_type = "icici_cc_transaction_alert"

    _PATTERN = re.compile(
        r"INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+spent\s+using\s+"
        r"ICICI\s+Bank\s+Card\s+(?P<card>XX\d+)\s+on\s+(?P<date>\d{2}-\w+-\d{2})\s+"
        r"on\s+(?P<merchant>.+?)\.\s+Avl\s+Limit:\s+INR\s+(?P<limit>[\d,]+(?:\.\d+)?)"
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
            raise ParseError("ICICI CC transaction alert pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                counterparty=match.group("merchant").strip(),
                balance=Money(
                    amount=parse_amount(match.group("limit")), currency="INR"
                ),
                card_mask=match.group("card"),
                channel="card",
            ),
        )
