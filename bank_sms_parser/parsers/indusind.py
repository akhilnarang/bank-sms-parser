"""IndusInd Bank SMS parsers."""

import datetime
import re

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BankSmsParser, BaseSmsParser
from bank_sms_parser.parsing import (
    normalize_whitespace,
    parse_amount,
    received_at_to_ist,
)


class IndusindAccountTransactionAlertParser(BaseSmsParser):
    """IndusInd savings/current-account UPI alert.

    Sample (carries no date — uses ``received_at`` fallback if provided):
        "A/C *XX0000 credited by Rs 35437.00 from VPA@bank.
         RRN:000000000000. Avl Bal:35437.00. ..."
    """

    bank = "indusind"
    email_type = "indusind_account_transaction_alert"

    _PATTERN = re.compile(
        r"A/C\s+\*(?P<account>XX\d+)\s+(?P<verb>credited|debited)\s+by\s+Rs\s+"
        r"(?P<amount>[\d,]+(?:\.\d+)?)\s+from\s+(?P<vpa>\S+)\.\s+"
        r"RRN:(?P<rrn>\d+)\.\s+Avl\s+Bal:(?P<balance>[\d,]+(?:\.\d+)?)"
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
            raise ParseError("IndusInd account UPI alert pattern did not match")
        direction = "credit" if match.group("verb") == "credited" else "debit"
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
                direction=direction,
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=txn_date,
                transaction_time=txn_time,
                counterparty=match.group("vpa"),
                reference_number=match.group("rrn"),
                channel="upi",
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
                account_mask=match.group("account"),
            ),
        )


_PARSERS: tuple[BaseSmsParser, ...] = (IndusindAccountTransactionAlertParser(),)


class IndusindParser(BankSmsParser):
    bank = "indusind"
    parsers = _PARSERS


def parse(body: str, *, sender: str | None = None, received_at: datetime.datetime | None = None) -> ParsedSms:
    return IndusindParser().parse(body, sender=sender, received_at=received_at)
