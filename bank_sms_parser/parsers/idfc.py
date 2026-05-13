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


class IdfcAccountTransactionAlertParser(BaseSmsParser):
    """IDFC FIRST savings/current-account debit alert.

    Two cosmetic body shapes share this event type — same downstream
    meaning, different bank phrasings (mirrors the ICICI account precedent
    and OneCard charge pattern of multiple compiled regexes in one class):

    1) Debit-card POS/online spend (anchored on ``Spent Rs.X from A/C``):
        "Spent Rs.2,448.00 from A/C XX0000 at INSTAMART on 04/05/26.
         Not you? Call 180010888/SMS BLOCK ... IDFC FIRST Bank"
        ``channel="card"``; counterparty=merchant; no RRN; no balance.

    2) UPI debit (anchored on ``Your A/c ... debited by Rs.``):
        "Your A/c XX0000 debited by Rs. 20,000.00 on 09/05/26;
         <Name> credited. RRN 000000000000. Available balance
         Rs. 16,442.65. Team IDFC FIRST Bank"
        ``channel="upi"`` (RRN sequence is UPI per IDFC convention,
        same as IndusInd); counterparty=recipient name; reference=RRN;
        balance=Available balance.

    Each regex is anchored on its discriminating clause so neither shape
    can accidentally match the other.
    """

    bank = "idfc"
    email_type = "idfc_account_transaction_alert"

    _SPEND_CARD_PATTERN = re.compile(
        r"Spent\s+Rs\.(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"from\s+A/C\s+(?P<account>XX\d+)\s+"
        r"at\s+(?P<merchant>.+?)\s+"
        r"on\s+(?P<date>\d{2}/\d{2}/\d{2})"
    )

    _UPI_DEBIT_PATTERN = re.compile(
        r"Your\s+A/c\s+(?P<account>XX\d+)\s+debited\s+by\s+"
        r"Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"on\s+(?P<date>\d{2}/\d{2}/\d{2})\s*;\s*"
        r"(?P<payee>.+?)\s+credited\.\s*"
        r"RRN\s+(?P<ref>\d+)\.\s*"
        r"Available\s+balance\s+Rs\.\s*(?P<balance>[\d,]+(?:\.\d+)?)"
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        text = normalize_whitespace(body)

        if match := self._SPEND_CARD_PATTERN.search(text):
            return self._build(
                match,
                counterparty=match.group("merchant").strip(),
                channel="card",
            )

        if match := self._UPI_DEBIT_PATTERN.search(text):
            return self._build(
                match,
                counterparty=match.group("payee").strip(),
                channel="upi",
                reference_number=match.group("ref"),
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
            )

        raise ParseError(
            "IDFC account transaction alert: no known pattern matched "
            "(tried card spend, UPI debit)"
        )

    def _build(
        self,
        match: re.Match[str],
        *,
        counterparty: str,
        channel: str,
        reference_number: str | None = None,
        balance: Money | None = None,
    ) -> ParsedSms:
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                counterparty=counterparty,
                reference_number=reference_number,
                channel=channel,
                account_mask=match.group("account"),
                balance=balance,
            ),
        )


_PARSERS: tuple[BaseSmsParser, ...] = (
    IdfcCcPaymentReceivedParser(),
    IdfcAccountTransactionAlertParser(),
)


class IdfcParser(BankSmsParser):
    bank = "idfc"
    parsers = _PARSERS


def parse(body: str, *, sender: str | None = None, received_at: datetime.datetime | None = None) -> ParsedSms:
    return IdfcParser().parse(body, sender=sender, received_at=received_at)
