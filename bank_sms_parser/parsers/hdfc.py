"""HDFC Bank SMS parsers.

Supported SMS types:
- hdfc_dc_transaction_alert: Debit-card POS/online spend
- hdfc_cc_transaction_alert: Credit-card POS/online spend
- hdfc_cc_refund_alert: Credit-card UPI refund credit
- hdfc_cc_payment_received_alert: Credit-card bill-payment credit
- hdfc_account_transaction_alert: Savings account IMPS credit
- hdfc_account_credit_alert: Savings account inbound credit ("Update! INR ... deposited ...")
- hdfc_account_upi_debit_alert: Savings account UPI/IMPS debit ("Sent Rs.X From HDFC Bank A/C *...")
- hdfc_account_upi_credit_alert: Savings account UPI credit
- hdfc_cc_smartpay_bbps_alert: SmartPay BBPS bill auto-debit on CC
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
    received_at_to_ist,
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
        r"At\s+(?P<merchant>.+?)\s+"
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
        r"At\s+(?P<merchant>.+?)\s+"
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

    Two cosmetic body shapes share this event type (mirrors the OneCard
    charge precedent of multiple compiled regexes in a single class):

    variant 1 — mixed-case "Online Payment ... vide Ref# ..." template:
        "HDFC Bank Cardmember, Online Payment of Rs.100 vide
         Ref# 000XXXXXXXXXXXX was credited to your card ending 0000
         On 08/MAY/2026_value Date 08/MAY/2026"

    variant 2 — fully-uppercase "PAYMENT OF ... RECEIVED TOWARDS ..."
    template (no reference number; includes available limit instead):
        "DEAR HDFCBANK CARDMEMBER, PAYMENT OF Rs. 100.00 RECEIVED TOWARDS
         YOUR CREDIT CARD ENDING WITH 0000 ON 17-5-2026.
         YOUR AVAILABLE LIMIT IS RS. 200.00"

    Semantic peer of ``axis_cc_payment_received_alert`` and
    ``idfc_cc_payment_received_alert`` — the user's bill payment was
    credited to the credit card (reduces CC outstanding). Direction is
    ``credit``. The trailing ``_value Date`` repeats the same date and is
    intentionally ignored in variant 1. ``channel`` and ``counterparty``
    are left ``None`` because neither template carries an explicit
    channel marker (unlike the UPI-refund shape).
    """

    bank = "hdfc"
    email_type = "hdfc_cc_payment_received_alert"

    _MIXED_CASE = re.compile(
        r"HDFC\s+Bank\s+Cardmember,\s+"
        r"Online\s+Payment\s+of\s+Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"vide\s+Ref#\s+(?P<ref>[A-Za-z0-9]+)\s+"
        r"was\s+credited\s+to\s+your\s+card\s+ending\s+(?P<card>\d+)\s+"
        r"On\s+(?P<date>\d{1,2}/[A-Za-z]+/\d{4})"
    )

    _UPPERCASE = re.compile(
        r"DEAR\s+HDFCBANK\s+CARDMEMBER,\s+"
        r"PAYMENT\s+OF\s+Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"RECEIVED\s+TOWARDS\s+YOUR\s+CREDIT\s+CARD\s+ENDING\s+WITH\s+(?P<card>\d+)\s+"
        r"ON\s+(?P<date>\d{1,2}-\d{1,2}-\d{4})",
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
        if match := self._MIXED_CASE.search(text):
            return self._build(match, ref=match.group("ref"))
        if match := self._UPPERCASE.search(text):
            return self._build(match, ref=None)
        raise ParseError("HDFC CC payment-received pattern did not match")

    def _build(self, match: re.Match[str], *, ref: str | None) -> ParsedSms:
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                reference_number=ref,
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


class HdfcAccountUpiCreditAlertParser(BaseSmsParser):
    """HDFC savings/current-account UPI credit alert.

    Sample (multi-line in the wire body; whitespace is normalized first):
        "Credit Alert!
         Rs.1.00 credited to HDFC Bank A/c XX0000 on 09-05-26
         from VPA customer@bank (UPI 000000000000)"

    Discriminators vs the IMPS credit shape:
    - Leading "Credit Alert!" banner (IMPS uses "Received!").
    - Amount prefixed with ``Rs.`` rather than ``INR``.
    - Account mask is uppercase ``XX####`` (IMPS body uses lowercase
      ``xx####``); kept verbatim from the body.
    - "from VPA <handle>" + "(UPI <ref>)" trailer; no in-body balance.

    Counterparty stores the bare VPA handle (``customer@bank``) — the
    ``VPA`` literal is a template marker, not part of the identifier.
    """

    bank = "hdfc"
    email_type = "hdfc_account_upi_credit_alert"

    _PATTERN = re.compile(
        r"Credit\s+Alert!\s+"
        r"Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"credited\s+to\s+HDFC\s+Bank\s+A/c\s+(?P<account>XX\d+)\s+"
        r"on\s+(?P<date>\d{2}-\d{2}-\d{2})\s+"
        r"from\s+VPA\s+(?P<vpa>\S+)\s+"
        r"\(UPI\s+(?P<ref>\d+)\)"
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
            raise ParseError("HDFC account UPI credit pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                counterparty=match.group("vpa"),
                reference_number=match.group("ref"),
                channel="upi",
                account_mask=match.group("account"),
            ),
        )


class HdfcAccountUpiDebitAlertParser(BaseSmsParser):
    """HDFC savings/current-account outbound transfer alert.

    Sample (multi-line in the wire body; whitespace is normalized first):
        "Sent Rs.100.00
         From HDFC Bank A/C *0000
         To CUSTOMER NAME
         On 17/05/26
         Ref 000000000000
         Not You?
         Call 18002586161/SMS BLOCK UPI to 7308080808"

    HDFC routes both UPI and IMPS outbound transfers through this template.
    The trailing block-channel hint says ``BLOCK UPI`` for UPI sends and
    ``BLOCK IMPS`` for IMPS; default to ``channel="upi"`` when neither
    appears (the dominant case) and switch only when an explicit IMPS
    block-marker is present.
    """

    bank = "hdfc"
    email_type = "hdfc_account_upi_debit_alert"

    _PATTERN = re.compile(
        r"Sent\s+Rs\.(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"From\s+HDFC\s+Bank\s+A/C\s+\*?(?P<account>\d+)\s+"
        r"To\s+(?P<payee>.+?)\s+"
        r"On\s+(?P<date>\d{2}/\d{2}/\d{2})\s+"
        r"Ref\s+(?P<ref>\d+)"
    )

    _IMPS_HINT = re.compile(r"BLOCK\s+IMPS", re.IGNORECASE)

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        text = normalize_whitespace(body)
        if not (match := self._PATTERN.search(text)):
            raise ParseError("HDFC account UPI debit pattern did not match")
        channel = "imps" if self._IMPS_HINT.search(text) else "upi"
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                counterparty=match.group("payee").strip(),
                reference_number=match.group("ref"),
                channel=channel,
                account_mask=match.group("account"),
            ),
        )


class HdfcAccountCreditAlertParser(BaseSmsParser):
    """HDFC savings/current-account inbound credit alert ("Update!" template).

    Sample (multi-line in the wire body; whitespace is normalized first):
        "Update! INR 100.00 deposited in HDFC Bank A/c XX0000 on
         16-MAY-26 for FT- CUSTOMER NAME-XXXXXXXXXX0000 - REMITTER
         NAME.Avl bal INR 200.00. Cheque deposits in A/C are subject
         to clearing"

    The "FT-" prefix indicates a fund transfer; the trailing remitter
    name (after the second "-" and before the period that opens
    ``Avl bal``) is the counterparty. Default channel to ``imps`` —
    HDFC's "Update!" deposit template is the IMPS counterpart of the
    "Sent ..." debit template, and "FT-" is HDFC's tag for inbound
    fund transfers in this family.
    """

    bank = "hdfc"
    email_type = "hdfc_account_credit_alert"

    _PATTERN = re.compile(
        r"Update!\s+INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"deposited\s+in\s+HDFC\s+Bank\s+A/c\s+(?P<account>XX\d+)\s+"
        r"on\s+(?P<date>\d{2}-[A-Z]+-\d{2})\s+"
        r"for\s+FT-\s*(?P<counterparty>[^.]+?)"
        r"\.\s*Avl\s+bal\s+INR\s+(?P<balance>[\d,]+(?:\.\d+)?)"
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
            raise ParseError("HDFC account credit-alert pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                counterparty=match.group("counterparty").strip(),
                channel="imps",
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
                account_mask=match.group("account"),
            ),
        )


class HdfcCcSmartpayBbpsAlertParser(BaseSmsParser):
    """HDFC SmartPay BBPS bill-pay debit alert.

    Sample:
        "Dear Smart Pay Customer,We have successfully debited your HDFC
         Bank Credit card ending 0000 to pay your SpayBBPS 00000 bill
         for the amount Rs 100"

    HDFC SmartPay auto-debits the registered credit card to pay BBPS
    bills (electricity, utilities, etc.). The body carries:
    - amount (``for the amount Rs N``)
    - card mask (``ending NNNN``)
    - the BBPS biller's SpayBBPS reference (used as ``reference_number``)

    There is no in-body date and no merchant name, so:
    - ``transaction_date`` / ``transaction_time`` fall back to
      ``received_at`` (UTC→IST) when supplied, else stay ``None``;
    - ``counterparty`` is set to ``"SpayBBPS <ref>"`` so the downstream
      can surface the biller reference.

    Emits ``email_type="hdfc_cc_smartpay_bbps_alert"`` (distinct from
    the generic CC spend so downstream consumers can recognize this as
    an auto-debit BBPS bill).
    """

    bank = "hdfc"
    email_type = "hdfc_cc_smartpay_bbps_alert"

    _PATTERN = re.compile(
        r"Dear\s+Smart\s+Pay\s+Customer,?\s*"
        r"We\s+have\s+successfully\s+debited\s+your\s+HDFC\s+Bank\s+Credit\s+card\s+"
        r"ending\s+(?P<card>\d+)\s+"
        r"to\s+pay\s+your\s+SpayBBPS\s+(?P<ref>\S+)\s+bill\s+"
        r"for\s+the\s+amount\s+Rs\.?\s*(?P<amount>[\d,]+(?:\.\d+)?)",
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
            raise ParseError("HDFC SmartPay BBPS bill-pay pattern did not match")
        txn_date: datetime.date | None = None
        txn_time: datetime.time | None = None
        if received_at is not None:
            ist = received_at_to_ist(received_at)
            txn_date = ist.date()
            txn_time = ist.time()
        ref = match.group("ref")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=txn_date,
                transaction_time=txn_time,
                counterparty=f"SpayBBPS {ref}",
                reference_number=ref,
                card_mask=match.group("card"),
                channel="card",
            ),
        )


_PARSERS: tuple[BaseSmsParser, ...] = (
    HdfcDcTransactionAlertParser(),
    HdfcCcTransactionAlertParser(),
    HdfcCcRefundAlertParser(),
    # Payment-received sits after the refund (both are CC credits) and
    # before the account parsers; each has a unique anchor so order is
    # not load-bearing, but grouping the CC shapes keeps the file
    # readable.
    HdfcCcPaymentReceivedAlertParser(),
    # SmartPay BBPS auto-debit lands on the CC; specific enough that its
    # ordering vs the generic CC spend doesn't matter (different anchors).
    HdfcCcSmartpayBbpsAlertParser(),
    # Both account parsers have unique leading banners ("Received!" vs
    # "Credit Alert!") so they are mutually exclusive; ordering between
    # them is not load-bearing.
    HdfcAccountTransactionAlertParser(),
    HdfcAccountUpiCreditAlertParser(),
    HdfcAccountCreditAlertParser(),
    HdfcAccountUpiDebitAlertParser(),
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
