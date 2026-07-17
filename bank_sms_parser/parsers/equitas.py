"""Equitas Small Finance Bank SMS parsers."""

import datetime
import re

from bank_sms_parser.exceptions import ParseError, ParserStubError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BankSmsParser, BaseSmsParser
from bank_sms_parser.parsing import (
    normalize_whitespace,
    parse_amount,
    parse_date,
    parse_datetime,
)


class EquitasCcPaymentReceivedParser(BaseSmsParser):
    """Equitas credit-card bill-payment-received notification.

    Sample (``DD/MM/YYYY`` date, masked ``XX####`` card):
        "INR 12,345.00 was received on 05/05/2026 and was credited to
         your Equitas Credit Card XX9999. Equitas SFB"

    This is the first of the two SMSes Equitas sends per bill payment and
    the one that carries the event into the ledger: ``direction`` is
    ``credit`` and ``email_type`` stays ``equitas_cc_payment_alert`` for
    downstream CC-payment reconciliation. The template carries no
    reference number.
    """

    bank = "equitas"
    email_type = "equitas_cc_payment_alert"

    _PATTERN = re.compile(
        r"INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"was\s+received\s+on\s+(?P<date>\d{2}/\d{2}/\d{4})\s+"
        r"and\s+was\s+credited\s+to\s+your\s+Equitas\s+Credit\s+Card\s+"
        r"(?P<card>XX\d+)"
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
            raise ParseError("Equitas CC payment-received pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                counterparty="Payment received",
                card_mask=match.group("card"),
                channel="card",
            ),
        )


class EquitasCcPaymentConfirmationParser(BaseSmsParser):
    """Equitas credit-card bill-payment confirmation notification.

    Sample (``DD/MM/YY`` 2-digit-year date, bare 4-digit card, no
    reference number):
        "Thank you for the payment of Rs.12,345.00 towards Equitas Credit
         Card 0000, this has been credited to your account on 07/06/26.
         Equitas SFB"

    Equitas sends this a few hours to a day after the
    ``equitas_cc_payment_alert`` SMS for the *same* payment; it restates a
    credit that has already been recorded rather than describing a second
    movement of money. It is given its own ``email_type`` so downstream
    consumers can recognize the restatement and decline to open a ledger
    row for it. Sender ID cannot be used to tell the two templates apart —
    the same sender IDs carry spend alerts and statement notices too — so
    the body wording is the only reliable discriminator.

    ``direction`` is still ``credit`` and the parsed fields are still
    populated: the event is real, only the second telling of it is
    redundant.
    """

    bank = "equitas"
    email_type = "equitas_cc_payment_confirmation_alert"

    _PATTERN = re.compile(
        r"Thank\s+you\s+for\s+the\s+payment\s+of\s+"
        r"Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"towards\s+Equitas\s+Credit\s+Card\s+(?P<card>\d+),?\s+"
        r"this\s+has\s+been\s+credited\s+to\s+your\s+account\s+on\s+"
        r"(?P<date>\d{2}/\d{2}/\d{2})"
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
            raise ParseError("Equitas CC payment-confirmation pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            ledger_role="restatement",
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                counterparty="Payment received",
                card_mask=match.group("card"),
                channel="card",
            ),
        )


class EquitasCcTransactionAlertParser(BaseSmsParser):
    """Equitas credit-card spend alert.

    Sample:
        "INR 30.00 spent on Equitas CC XX0000 at MERCHANT on
         01-05-2026 07:53:18 PM. Available limit is INR. 99,999.99."
    """

    bank = "equitas"
    email_type = "equitas_cc_transaction_alert"

    _PATTERN = re.compile(
        r"INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"spent\s+on\s+Equitas\s+CC\s+(?P<card>XX\d+)\s+"
        r"at\s+(?P<merchant>.+?)\s+"
        r"on\s+(?P<datetime>\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}:\d{2}\s+(?:AM|PM))\.\s+"
        r"Available\s+limit\s+is\s+INR\.\s+(?P<limit>[\d,]+(?:\.\d+)?)"
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
            raise ParseError("Equitas CC transaction alert pattern did not match")
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
                balance=Money(
                    amount=parse_amount(match.group("limit")), currency="INR"
                ),
                card_mask=match.group("card"),
                channel="card",
            ),
        )


class EquitasCcPaymentDueStubParser(BaseSmsParser):
    """Recognize-and-skip stub for the Equitas CC payment-due reminder.

    Sample (sender AD-EQUTAS-S):

        "Payment of Equitas Credit Card 0000 is due on 10/07/26. Min due
         Rs 1234.56 Total due Rs 12345.67. Non payment is reported to
         Credit Bureau. Pls ignore if paid"

    This is a reminder, not a transaction: no money moved and there is no
    canonical debit/credit verb. ``SmsTransactionAlert`` only models real
    money movement, so per the skill we recognize the shape and raise
    ``ParserStubError`` (intentionally unimplemented) rather than let it
    surface as a generic regex miss. The anchor phrase "Payment of Equitas
    Credit Card <digits> is due on" cannot appear in the bank's spend
    ("spent on Equitas CC") or payment-received ("was received" / "Thank
    you for the payment of") templates.
    """

    bank = "equitas"
    email_type = "equitas_cc_payment_due_stub"

    _PATTERN = re.compile(
        r"Payment\s+of\s+Equitas\s+Credit\s+Card\s+\S+\s+is\s+due\s+on",
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
        if not self._PATTERN.search(text):
            raise ParseError("Equitas payment-due reminder pattern did not match")
        raise ParserStubError(
            "equitas_cc_payment_due_stub: recognized Equitas CC payment-due "
            "reminder; not a transaction, intentionally unimplemented"
        )


class EquitasCcStatementNoticeStubParser(BaseSmsParser):
    """Recognize-and-skip stub for the Equitas CC statement-generated notice.

    Sample (sender AD-EQUTAS-S):

        "Statement for your Equitas Credit Card 0000 is generated. Total
         Due: 12345.67 Min Due: 1234.56 Due by: 09/06/26. Pls pay by due
         date."

    A statement notice carries amounts but records no money movement; a
    naive parser would fabricate a fake transaction out of "Total Due".
    The anchor "Statement for your Equitas Credit Card ... is generated"
    is unique to this template.
    """

    bank = "equitas"
    email_type = "equitas_cc_statement_notice_stub"

    _PATTERN = re.compile(
        r"Statement\s+for\s+your\s+Equitas\s+Credit\s+Card\s+\S+\s+is\s+generated",
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
        if not self._PATTERN.search(text):
            raise ParseError("Equitas statement-generated pattern did not match")
        raise ParserStubError(
            "equitas_cc_statement_notice_stub: recognized Equitas CC "
            "statement-generated notice; not a transaction, intentionally "
            "unimplemented"
        )


class EquitasServiceInfoStubParser(BaseSmsParser):
    """Recognize-and-skip stub for Equitas service-info SMSes.

    Sample (sender AD-EQUTAS-S) — mobile-app login failure:

        "Dear customer, your attempt to login to Equitas Mobile App failed
         due to incorrect MPIN. If not you, call us at 18001031222 -
         Equitas SFB"

    Pure service information: no amount, no account, no money movement.
    Phrasings are collected in ``_SERVICE_INFO_PATTERNS``; add new ones
    there, and never broaden a pattern to something that could appear in a
    transaction alert.
    """

    bank = "equitas"
    email_type = "equitas_service_info_stub"

    _SERVICE_INFO_PATTERNS: tuple[re.Pattern[str], ...] = (
        # Mobile-app login failure (incorrect MPIN etc.)
        re.compile(
            r"attempt\s+to\s+login\s+to\s+Equitas\s+Mobile\s+App\s+failed",
            re.IGNORECASE,
        ),
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        text = normalize_whitespace(body)
        for pattern in self._SERVICE_INFO_PATTERNS:
            if pattern.search(text):
                raise ParserStubError(
                    "equitas_service_info_stub: recognized Equitas "
                    "service-info SMS (e.g. mobile-app login failure); "
                    "intentionally not parsed as a transaction"
                )
        raise ParseError("Equitas service-info: no recognized service-info phrase")


_PARSERS: tuple[BaseSmsParser, ...] = (
    EquitasCcPaymentReceivedParser(),
    EquitasCcPaymentConfirmationParser(),
    EquitasCcTransactionAlertParser(),
    # ParserStubError stubs LAST so they can never shadow real parsers.
    EquitasCcPaymentDueStubParser(),
    EquitasCcStatementNoticeStubParser(),
    EquitasServiceInfoStubParser(),
)


class EquitasParser(BankSmsParser):
    bank = "equitas"
    parsers = _PARSERS


def parse(body: str, *, sender: str | None = None, received_at: datetime.datetime | None = None) -> ParsedSms:
    return EquitasParser().parse(body, sender=sender, received_at=received_at)
