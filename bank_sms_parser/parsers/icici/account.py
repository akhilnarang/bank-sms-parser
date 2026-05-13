"""ICICI account-level SMS parser (savings/checking IMPS/NEFT/UPI debit/credit)."""

import datetime
import re

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BaseSmsParser
from bank_sms_parser.parsing import normalize_whitespace, parse_amount, parse_date


class IciciAccountTransactionAlertParser(BaseSmsParser):
    """ICICI account-level transaction alert (debit via IMPS or UPI).

    Two cosmetic body shapes share this event type — same downstream
    meaning, different bank phrasings (mirrors the OneCard charge
    precedent of multiple compiled regexes in a single class):

    1) IMPS debit (uses "debited with" and "& Acct XX### credited.IMPS:"):
        "ICICI Bank Acct XX000 debited with Rs 10,000.00 on 02-May-26
         & Acct XX001 credited.IMPS:000000000000. ..."

    2) UPI debit (uses "debited for" and "; <Name> credited. UPI:"):
        "ICICI Bank Acct XX000 debited for Rs 14.00 on 09-May-26;
         Pune Metro credited. UPI:000000000000. ..."

    The paired credit mention in the same body refers to the
    destination account/payee; per spec §6 we emit ONE debit alert (the
    sending bank's primary event) and store the destination mask or
    merchant name in ``counterparty``.

    Each regex is anchored on the discriminating clause (``debited
    with`` + ``&`` for IMPS; ``debited for`` + ``;`` for UPI) so neither
    shape can accidentally match the other.
    """

    bank = "icici"
    email_type = "icici_account_transaction_alert"

    _DEBIT_IMPS_PATTERN = re.compile(
        r"ICICI\s+Bank\s+Acct\s+(?P<account>XX\d+)\s+debited\s+with\s+"
        r"Rs\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+on\s+(?P<date>\d{2}-\w+-\d{2})\s+"
        r"&\s+Acct\s+(?P<dest>XX\d+)\s+credited\.IMPS:(?P<ref>\d+)"
    )

    _DEBIT_UPI_PATTERN = re.compile(
        r"ICICI\s+Bank\s+Acct\s+(?P<account>XX\d+)\s+debited\s+for\s+"
        r"Rs\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+on\s+(?P<date>\d{2}-\w+-\d{2})\s*;\s*"
        r"(?P<payee>.+?)\s+credited\.\s*UPI:(?P<ref>\d+)"
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        text = normalize_whitespace(body)

        if match := self._DEBIT_IMPS_PATTERN.search(text):
            return self._build(
                match,
                counterparty=f"Acct {match.group('dest')}",
                channel="imps",
            )

        if match := self._DEBIT_UPI_PATTERN.search(text):
            return self._build(
                match,
                counterparty=match.group("payee").strip(),
                channel="upi",
            )

        raise ParseError(
            "ICICI account transaction alert: no known pattern matched "
            "(tried IMPS debit, UPI debit)"
        )

    def _build(
        self,
        match: re.Match[str],
        *,
        counterparty: str,
        channel: str,
    ) -> ParsedSms:
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                counterparty=counterparty,
                reference_number=match.group("ref"),
                channel=channel,
                account_mask=match.group("account"),
            ),
        )
