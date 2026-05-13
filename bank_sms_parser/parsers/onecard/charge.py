"""OneCard credit-card charge SMS parser.

OneCard ships three cosmetic phrasings of the same CC-charge event:
    1. "Your bill of Rs. X at Y has been cleared with your BOBCARD One Credit Card ending in XX..."
    2. "Fresh picks! You've spent Rs. X at Y with your BOBCARD One Credit Card ending in XX..."
    3. "You've paid <CCY> X at Y with your BOBCARD One Credit Card ending in XX..."

All three emit ``email_type="onecard_cc_transaction_alert"`` (per spec §6).
They live in one parser class with three SEPARATELY COMPILED regexes,
tried in order — a single regex with 3-way alternation would re-use
named groups and trigger ``re.error: redefinition of group name`` in
Python's stdlib ``re`` module (see spec §6 OneCard notes).

Variant 3 carries a 3-letter ISO currency code (real example: USD); the
other two are INR by convention.
"""

import datetime
import re

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BaseSmsParser
from bank_sms_parser.parsing import (
    normalize_whitespace,
    parse_amount,
    received_at_to_ist,
)


class OnecardCcTransactionAlertParser(BaseSmsParser):
    bank = "onecard"
    email_type = "onecard_cc_transaction_alert"

    _BILL_CLEARED = re.compile(
        r"Your\s+bill\s+of\s+Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"at\s+(?P<merchant>.+?)\s+has\s+been\s+cleared\s+with\s+your\s+"
        r"BOBCARD\s+One\s+Credit\s+Card\s+ending\s+in\s+(?P<card>XX\d+)"
    )
    _SPENT = re.compile(
        r"You've\s+spent\s+Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"at\s+(?P<merchant>.+?)\s+with\s+your\s+"
        r"BOBCARD\s+One\s+Credit\s+Card\s+ending\s+in\s+(?P<card>XX\d+)"
    )
    _PAID_FOREIGN = re.compile(
        r"You've\s+paid\s+(?P<currency>[A-Z]{3})\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"at\s+(?P<merchant>.+?)\s+with\s+your\s+"
        r"BOBCARD\s+One\s+Credit\s+Card\s+ending\s+in\s+(?P<card>XX\d+)"
    )

    _PATTERNS_INR = (_BILL_CLEARED, _SPENT)
    _PATTERN_FOREIGN = _PAID_FOREIGN

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        text = normalize_whitespace(body)
        for pattern in self._PATTERNS_INR:
            if match := pattern.search(text):
                return self._build(match, currency="INR", received_at=received_at)
        if match := self._PATTERN_FOREIGN.search(text):
            return self._build(
                match, currency=match.group("currency"), received_at=received_at
            )
        raise ParseError(
            "OneCard CC charge: no known shape matched (tried bill_cleared, spent, paid_foreign)"
        )

    def _build(
        self,
        match: re.Match,
        *,
        currency: str,
        received_at: datetime.datetime | None,
    ) -> ParsedSms:
        # OneCard charge bodies carry no date; per spec §10, fall back to
        # received_at (UTC→IST) when supplied, else leave date/time None.
        txn_date: datetime.date | None = None
        txn_time: datetime.time | None = None
        if received_at is not None:
            ist = received_at_to_ist(received_at)
            txn_date = ist.date()
            txn_time = ist.time()
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(amount=parse_amount(match.group("amount")), currency=currency),
                transaction_date=txn_date,
                transaction_time=txn_time,
                counterparty=match.group("merchant").strip(),
                card_mask=match.group("card"),
                channel="card",
            ),
        )
