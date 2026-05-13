"""HDFC Bank SMS parsers.

Supported SMS types:
- hdfc_dc_transaction_alert: Debit-card POS/online spend
- hdfc_cc_transaction_alert: Credit-card POS/online spend
- hdfc_cc_refund_alert: Credit-card UPI refund credit
- hdfc_cc_payment_received_alert: Credit-card bill-payment credit
- hdfc_account_transaction_alert: Savings account IMPS credit
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


class HdfcCcPaymentReceivedAlertParser(BaseSmsParser):
    """HDFC credit-card bill-payment-received credit alert.

    Sample:
        "HDFC Bank Cardmember, Online Payment of Rs.1000 vide
         Ref# 000XXXXXXXXXXXX was credited to your card ending 0000
         On 08/MAY/2026_value Date 08/MAY/2026"

    Semantic peer of ``axis_cc_payment_received_alert`` and
    ``idfc_cc_payment_received_alert`` — the user's bill payment was
    credited to the credit card (reduces CC outstanding). Direction is
    ``credit``. The trailing ``_value Date`` repeats the same date and is
    intentionally ignored. ``channel`` and ``counterparty`` are left
    ``None`` because the body has no explicit channel marker (unlike the
    UPI-refund shape).
    """

    bank = "hdfc"
    email_type = "hdfc_cc_payment_received_alert"

    _PATTERN = re.compile(
        r"HDFC\s+Bank\s+Cardmember,\s+"
        r"Online\s+Payment\s+of\s+Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"vide\s+Ref#\s+(?P<ref>[A-Za-z0-9]+)\s+"
        r"was\s+credited\s+to\s+your\s+card\s+ending\s+(?P<card>\d+)\s+"
        r"On\s+(?P<date>\d{1,2}/[A-Za-z]+/\d{4})"
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
            raise ParseError("HDFC CC payment-received pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                reference_number=match.group("ref"),
                card_mask=match.group("card"),
            ),
        )


class HdfcAccountTransactionAlertParser(BaseSmsParser):
    """HDFC savings/current-account IMPS credit alert.

    Sample (multi-line in the wire body; whitespace is normalized first):
        "Received!
         INR 12,345.00 in HDFC Bank A/c xx0000
         On 03-05-26
         For IMPS -Customer- 000000000000
         Avl bal INR 99,999.99"

    The counterparty is the IMPS originator's name; for self-transfers
    that is the user's own name. Account-mask casing matches the body
    (lowercase ``xx``).
    """

    bank = "hdfc"
    email_type = "hdfc_account_transaction_alert"

    _PATTERN = re.compile(
        r"Received!\s+"
        r"INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"in\s+HDFC\s+Bank\s+A/c\s+(?P<account>xx\d+)\s+"
        r"On\s+(?P<date>\d{2}-\d{2}-\d{2})\s+"
        r"For\s+IMPS\s+-(?P<counterparty>[^-]+)-\s+(?P<ref>\d+)\s+"
        r"Avl\s+bal\s+INR\s+(?P<balance>[\d,]+(?:\.\d+)?)"
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
            raise ParseError("HDFC account IMPS credit pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                counterparty=match.group("counterparty").strip(),
                reference_number=match.group("ref"),
                channel="imps",
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
                account_mask=match.group("account"),
            ),
        )


_PARSERS: tuple[BaseSmsParser, ...] = (
    HdfcDcTransactionAlertParser(),
    HdfcCcTransactionAlertParser(),
    HdfcCcRefundAlertParser(),
    # Payment-received sits after the refund (both are CC credits) and
    # before the account parser; each has a unique anchor so order is not
    # load-bearing, but grouping the CC shapes keeps the file readable.
    HdfcCcPaymentReceivedAlertParser(),
    HdfcAccountTransactionAlertParser(),
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
