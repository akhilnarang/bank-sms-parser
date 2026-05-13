"""slice (the fintech) SMS parsers.

Three SMS shapes supported:

1. ``slice_cc_bill_paid_alert`` — credit-card bill paid via autopay. The
   body carries no mask and no date; ``received_at`` (UTC→IST) fills the
   transaction date when supplied. Counterparty is set to a constant
   ``"Bill autopay"`` because the body has no other identifier.
2. ``slice_account_upi_credit_alert`` — UPI credit into the slice
   savings account. Carries amount, account mask, payer name, UPI
   reference, and an available balance.
3. ``slice_account_upi_debit_alert`` — UPI debit from the slice savings
   account. Carries amount, account mask, payee name, and a UPI
   reference. No balance.
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
    received_at_to_ist,
)


class SliceCcBillPaidAlertParser(BaseSmsParser):
    """slice UPI credit-card bill autopay paid notification.

    Sample (sanitized):
        "Your slice UPI credit card bill of Rs.2,500.00 has been paid
         successfully via autopay. Thanks for paying on time! - slice"

    Treated as a ``credit`` event because a payment toward the CC reduces
    outstanding CC debt (mirrors the IDFC / Axis / OneCard
    "payment received" parsers). The body carries no card mask — slice's
    template omits it for this shape — so ``card_mask`` stays ``None``,
    which the skill explicitly allows for payment-received alerts.
    """

    bank = "slice"
    email_type = "slice_cc_bill_paid_alert"

    _PATTERN = re.compile(
        r"slice\s+UPI\s+credit\s+card\s+bill\s+of\s+"
        r"Rs\.?\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"has\s+been\s+paid\s+successfully\s+via\s+autopay",
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
            raise ParseError("slice CC bill-paid pattern did not match")
        txn_date: datetime.date | None = None
        if received_at is not None:
            txn_date = received_at_to_ist(received_at).date()
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=txn_date,
                counterparty="Bill autopay",
                channel="card",
            ),
        )


class SliceAccountUpiCreditAlertParser(BaseSmsParser):
    """slice savings account UPI credit alert.

    Sample (sanitized):
        "Rs. 12,000 received in slice A/c xx1234 on 03-May-26 from
         JOHN SMITH via UPI (Ref ID: 234567890123). Avl. Bal.
         Rs. 50,000.00 - slice"
    """

    bank = "slice"
    email_type = "slice_account_upi_credit_alert"

    _PATTERN = re.compile(
        r"Rs\.?\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+received\s+in\s+slice\s+"
        r"A/c\s+(?P<account>xx\d+)\s+on\s+(?P<date>\d{1,2}-\w+-\d{2,4})\s+"
        r"from\s+(?P<sender_name>.+?)\s+via\s+UPI\s+"
        r"\(Ref\s*ID:\s*(?P<ref>\w+)\)\.\s*"
        r"Avl\.?\s*Bal\.?\s*Rs\.?\s*(?P<balance>[\d,]+(?:\.\d+)?)",
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
            raise ParseError("slice account UPI credit pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=parse_date(match.group("date")),
                counterparty=match.group("sender_name").strip(),
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
                reference_number=match.group("ref"),
                account_mask=match.group("account"),
                channel="upi",
            ),
        )


class SliceAccountUpiDebitAlertParser(BaseSmsParser):
    """slice savings account UPI debit alert.

    Sample (sanitized):
        "Rs. 7,500.00 sent from a/c xx1234 on 05-May-26 to JANE DOE
         (UPI Ref: 123456789012). Not you? Call 00000000000 - slice"
    """

    bank = "slice"
    email_type = "slice_account_upi_debit_alert"

    _PATTERN = re.compile(
        r"Rs\.?\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+sent\s+from\s+"
        r"a/c\s+(?P<account>xx\d+)\s+on\s+(?P<date>\d{1,2}-\w+-\d{2,4})\s+"
        r"to\s+(?P<recipient>.+?)\s+\(UPI\s+Ref:\s*(?P<ref>\w+)\)",
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
            raise ParseError("slice account UPI debit pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=parse_date(match.group("date")),
                counterparty=match.group("recipient").strip(),
                reference_number=match.group("ref"),
                account_mask=match.group("account"),
                channel="upi",
            ),
        )


class SliceCcTransactionAlertParser(BaseSmsParser):
    """slice credit-card spend alert.

    Sample (sanitized):
        "Rs. 100.00 spent on your credit card xx0000 at MERCHANT on
         12-May-26 (UPI Ref: 000000000000). Not you? Call 080-0000-0000
         - slice"

    The body carries amount, card mask, merchant, an in-body date, and a
    UPI reference number. Direction is ``debit``; channel defaults to
    ``card`` (the spend is reported as the CC spend, the UPI ref is the
    payment instrument used at the merchant).
    """

    bank = "slice"
    email_type = "slice_cc_transaction_alert"

    _PATTERN = re.compile(
        r"Rs\.?\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+spent\s+on\s+your\s+"
        r"credit\s+card\s+(?P<card>xx\d+)\s+at\s+(?P<merchant>.+?)\s+"
        r"on\s+(?P<date>\d{1,2}-\w+-\d{2,4})\s*"
        r"\(UPI\s+Ref:\s*(?P<ref>\w+)\)",
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
            raise ParseError("slice CC transaction alert pattern did not match")
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
                reference_number=match.group("ref"),
                card_mask=match.group("card"),
                channel="card",
            ),
        )


# Order: most-specific first. The CC bill-paid alert has a unique
# template ("slice UPI credit card bill ... paid successfully via
# autopay") that no other shape matches; the credit and debit account
# alerts are distinguished by their leading verbs ("received in" vs
# "sent from") so their relative order is not load-bearing. The CC
# spend alert is anchored on ``spent on your credit card``.
_PARSERS: tuple[BaseSmsParser, ...] = (
    SliceCcBillPaidAlertParser(),
    SliceCcTransactionAlertParser(),
    SliceAccountUpiCreditAlertParser(),
    SliceAccountUpiDebitAlertParser(),
)


class SliceParser(BankSmsParser):
    bank = "slice"
    parsers = _PARSERS


def parse(
    body: str,
    *,
    sender: str | None = None,
    received_at: datetime.datetime | None = None,
) -> ParsedSms:
    return SliceParser().parse(body, sender=sender, received_at=received_at)
