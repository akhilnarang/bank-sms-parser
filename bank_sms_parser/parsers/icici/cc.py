"""ICICI credit-card SMS parser."""

import datetime
import re

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BaseSmsParser
from bank_sms_parser.parsing import normalize_whitespace, parse_amount, parse_date


class IciciCcTransactionAlertParser(BaseSmsParser):
    """ICICI credit-card spend alert.

    Two cosmetic body shapes share this event type:

    variant 1 — ``INR ... spent using ICICI Bank Card`` (uses ``on`` for
    merchant and ``Avl Limit: INR`` for the limit):
        "INR X spent using ICICI Bank Card XX0000 on 01-May-26
         on MERCHANT. Avl Limit: INR Y. ..."

    variant 2 — ``Rs ... spent on ICICI Bank Card`` (uses ``at`` for
    merchant and ``Avl Lmt: Rs`` for the limit):
        "Rs X spent on ICICI Bank Card XX0000 on 16-May-26 at
         MERCHANT. Avl Lmt: Rs Y. To dispute, call ..."

    Both emit ``email_type="icici_cc_transaction_alert"`` so downstream
    consumers do not need to distinguish wire-templates.
    """

    bank = "icici"
    email_type = "icici_cc_transaction_alert"

    _PATTERN_USING = re.compile(
        r"INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+spent\s+using\s+"
        r"ICICI\s+Bank\s+Card\s+(?P<card>XX\d+)\s+on\s+(?P<date>\d{2}-\w+-\d{2})\s+"
        r"on\s+(?P<merchant>.+?)\.\s+Avl\s+Limit:\s+INR\s+(?P<limit>[\d,]+(?:\.\d+)?)"
    )

    _PATTERN_ON = re.compile(
        r"Rs\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+spent\s+on\s+"
        r"ICICI\s+Bank\s+Card\s+(?P<card>XX\d+)\s+on\s+(?P<date>\d{1,2}-\w+-\d{2})\s+"
        r"at\s+(?P<merchant>.+?)\.\s+Avl\s+Lmt:\s+Rs\s+(?P<limit>[\d,]+(?:\.\d+)?)"
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        text = normalize_whitespace(body)
        for pattern in (self._PATTERN_USING, self._PATTERN_ON):
            if match := pattern.search(text):
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
        raise ParseError("ICICI CC transaction alert pattern did not match")


class IciciCcPaymentReceivedAlertParser(BaseSmsParser):
    """ICICI credit-card bill-payment-received notification.

    Sample:
        "Payment of Rs 50,000.00 has been received on your ICICI Bank
         Credit Card XX0000 through Bharat Bill Payment System on 21-MAY-26."

    Money is credited to the card (it reduces the outstanding balance), so
    this is emitted as a ``credit``. Mirrors the axis/idfc
    ``cc_payment_received`` convention: card_mask + date only, no
    counterparty/balance. The payment rail ("through ...") is optional so a
    rail-less variant still matches.
    """

    bank = "icici"
    email_type = "icici_cc_payment_received_alert"

    _PATTERN = re.compile(
        r"Payment\s+of\s+Rs\.?\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"has\s+been\s+received\s+on\s+your\s+"
        r"ICICI\s+Bank\s+Credit\s+Card\s+(?P<card>XX\d+)\s+"
        r"(?:through\s+.+?\s+)?on\s+(?P<date>\d{1,2}-\w+-\d{2})"
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
            raise ParseError("ICICI CC payment-received pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=parse_date(match.group("date")),
                card_mask=match.group("card"),
            ),
        )
