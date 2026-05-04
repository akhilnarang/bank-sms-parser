"""HDFC Bank SMS parsers.

Supported SMS types:
- hdfc_dc_transaction_alert: Debit-card POS/online spend
- hdfc_cc_transaction_alert: Credit-card POS/online spend
- hdfc_cc_refund_alert: Credit-card UPI refund credit
"""

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


class HdfcDcTransactionAlertParser(BaseSmsParser):
    """HDFC debit-card spend alert.

    Sample:
        "Spent Rs.3000 From HDFC Bank Card x0000 At MERCHANT On
         2026-05-02:00:17:56 Bal Rs.142.26 Not You? Call ..."
    """

    bank = "hdfc"
    email_type = "hdfc_dc_transaction_alert"

    _PATTERN = re.compile(
        r"Spent\s+Rs\.(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"From\s+HDFC\s+Bank\s+Card\s+(?P<card>x\d+)\s+"
        r"At\s+(?P<merchant>\S+)\s+"
        r"On\s+(?P<datetime>\d{4}-\d{2}-\d{2}:\d{2}:\d{2}:\d{2})\s+"
        r"Bal\s+Rs\.(?P<balance>[\d,]+(?:\.\d+)?)"
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
            raise ParseError("HDFC DC transaction alert pattern did not match")
        dt = parse_datetime(match.group("datetime"))
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=dt.date(),
                transaction_time=dt.time(),
                counterparty=match.group("merchant"),
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
                card_mask=match.group("card"),
                channel="card",
            ),
        )


class HdfcCcTransactionAlertParser(BaseSmsParser):
    """HDFC credit-card spend alert.

    Sample:
        "Spent Rs.10290 On HDFC Bank Card 0000 At MERCHANT On
         2026-05-02:22:26:01.Not You? To Block+Reissue Call ..."

    Discriminators vs the debit-card shape:
    - "On HDFC Bank Card" (CC) vs "From HDFC Bank Card" (DC).
    - Bare 4-digit card mask, no "x" prefix.
    - No "Bal Rs." trailer; the datetime is followed by a literal period.
    """

    bank = "hdfc"
    email_type = "hdfc_cc_transaction_alert"

    _PATTERN = re.compile(
        r"Spent\s+Rs\.(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"On\s+HDFC\s+Bank\s+Card\s+(?P<card>\d+)\s+"
        r"At\s+(?P<merchant>\S+)\s+"
        r"On\s+(?P<datetime>\d{4}-\d{2}-\d{2}:\d{2}:\d{2}:\d{2})\."
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
            raise ParseError("HDFC CC transaction alert pattern did not match")
        dt = parse_datetime(match.group("datetime"))
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=dt.date(),
                transaction_time=dt.time(),
                counterparty=match.group("merchant"),
                card_mask=match.group("card"),
                channel="card",
            ),
        )


class HdfcCcRefundAlertParser(BaseSmsParser):
    """HDFC credit-card UPI refund credit.

    Sample:
        "Alert! Rs. 254 refunded by UPI CC-27-04-2026-000000000000 on
         01/MAY/2026 & adjusted against HDFC Bank Credit Card 0000
         View updated balance here: https://..."

    The CC reference embeds the original spend's date and UTR; the
    parser captures the trailing UTR digits as ``reference_number``.
    ``transaction_date`` is the refund date, not the original spend date.
    """

    bank = "hdfc"
    email_type = "hdfc_cc_refund_alert"

    _PATTERN = re.compile(
        r"Alert!\s+Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"refunded\s+by\s+UPI\s+CC-\d{2}-\d{2}-\d{4}-(?P<ref>\d+)\s+"
        r"on\s+(?P<date>\d{1,2}/[A-Za-z]+/\d{4})\s+"
        r"&\s+adjusted\s+against\s+HDFC\s+Bank\s+Credit\s+Card\s+(?P<card>\d+)"
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
            raise ParseError("HDFC CC refund alert pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                reference_number=match.group("ref"),
                card_mask=match.group("card"),
                channel="upi",
            ),
        )


_PARSERS: tuple[BaseSmsParser, ...] = (
    HdfcDcTransactionAlertParser(),
    HdfcCcTransactionAlertParser(),
    HdfcCcRefundAlertParser(),
)


class HdfcParser(BankSmsParser):
    bank = "hdfc"
    parsers = _PARSERS


def parse(
    body: str,
    *,
    sender: str | None = None,
    received_at: datetime.datetime | None = None,
) -> ParsedSms:
    """Module-level convenience wrapper."""
    return HdfcParser().parse(body, sender=sender, received_at=received_at)
