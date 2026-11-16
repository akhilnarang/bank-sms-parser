"""AU Small Finance Bank SMS parsers."""

import datetime
import re

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BankSmsParser, BaseSmsParser
from bank_sms_parser.parsing import normalize_whitespace, parse_amount, parse_date

_AMOUNT = r"[\d,]+(?:\.\d+)?"
_RAIL_REF = re.compile(r"^(?P<channel>IMPS|NEFT|RTGS|UPI)[-/:](?P<ref>\w+)$", re.I)
_NARRATION_REF = re.compile(r"^[A-Z0-9]{8,}-(?P<rest>.+)$")


class AuAccountDebitAlertParser(BaseSmsParser):
    """Parse an AU savings account debit alert.

    Sample (sanitized):
        "Alert! Your AU Bank A/c No. X0000 has been Dr with INR 1,234.00 on
         16-NOV-2026 for ABCD000000000000-International Transfe. Avl Bal:
         INR 5,678.90. - AU Bank"

    The body has the amount, the date, a narration and the new balance. It has
    no time. AU sends the SMS at the moment of the debit, so the arrival time
    is the event time.

    The narration starts with an order ID, then a description. AU cuts the
    description short. One order can cause more than one debit, for example a
    transfer and its currency conversion fee. These debits have the same order
    ID, so the order ID is not a reference: it would merge them. The parser
    keeps the description as the counterparty and sets no reference.
    """

    bank = "au"
    email_type = "au_account_debit_alert"
    event_time_source = "message_arrival"

    _PATTERN = re.compile(
        r"Your\s+AU\s+Bank\s+A/c\s+No\.?\s*(?P<mask>X+\d+)\s+has\s+been\s+Dr\s+"
        rf"with\s+INR\s*(?P<amount>{_AMOUNT})\s+on\s+(?P<date>\d{{2}}-[A-Z]{{3}}-\d{{4}})\s+"
        rf"for\s+(?P<narration>.+?)\.\s+Avl\s+Bal:\s*INR\s*(?P<balance>{_AMOUNT})",
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
            raise ParseError("AU account debit pattern did not match")
        narration = match.group("narration").strip()
        if split := _NARRATION_REF.match(narration):
            narration = split.group("rest").strip()
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=parse_date(match.group("date")),
                counterparty=narration,
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
                account_mask=match.group("mask"),
            ),
        )


class AuAccountCreditAlertParser(BaseSmsParser):
    """Parse an AU savings account credit alert.

    Samples (sanitized):
        "Credited INR 1,234.00 to A/c X0000 on 16-NOV-2026 Ref
         IMPS-000000000000 -CUSTOMER. Bal INR 5,678.90. -AU Bank"
        "Credited INR 1,234.00 to A/c X0000 on 12-NOV-2026 Ref
         ABCDE_0000_00000000000000 | samplepayer-S. Bal INR 1,234.00. -AU Bank"

    The body has the amount, the date, a reference, the payer and the new
    balance. It has no time. AU sends the SMS at the moment of the credit, so
    the arrival time is the event time.

    A reference such as "IMPS-000000000000" names the rail. The parser sets the
    channel from the rail and keeps only the number as the reference, so the
    reference agrees with the alert of the sending bank. Other references stay
    whole and set no channel.
    """

    bank = "au"
    email_type = "au_account_credit_alert"
    event_time_source = "message_arrival"

    _PATTERN = re.compile(
        rf"Credited\s+INR\s*(?P<amount>{_AMOUNT})\s+to\s+A/c\s+(?P<mask>X+\d+)\s+"
        r"on\s+(?P<date>\d{2}-[A-Z]{3}-\d{4})\s+Ref\s+(?P<ref>\S+)\s+[-|]\s*"
        rf"(?P<counterparty>.+?)\.\s+Bal\s+INR\s*(?P<balance>{_AMOUNT})",
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
            raise ParseError("AU account credit pattern did not match")
        reference = match.group("ref")
        channel = None
        if rail := _RAIL_REF.match(reference):
            reference = rail.group("ref")
            channel = rail.group("channel").lower()
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=parse_date(match.group("date")),
                counterparty=match.group("counterparty").strip(),
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
                reference_number=reference,
                account_mask=match.group("mask"),
                channel=channel,
            ),
        )


_PARSERS: tuple[BaseSmsParser, ...] = (
    AuAccountDebitAlertParser(),
    AuAccountCreditAlertParser(),
)


class AuParser(BankSmsParser):
    bank = "au"
    parsers = _PARSERS


def parse(
    body: str,
    *,
    sender: str | None = None,
    received_at: datetime.datetime | None = None,
) -> ParsedSms:
    return AuParser().parse(body, sender=sender, received_at=received_at)
