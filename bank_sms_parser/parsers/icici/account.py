"""ICICI account-level SMS parser (savings/checking IMPS/NEFT debit/credit)."""

import datetime
import re

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BaseSmsParser
from bank_sms_parser.parsing import normalize_whitespace, parse_amount, parse_date


class IciciAccountTransactionAlertParser(BaseSmsParser):
    """ICICI account-level transaction alert (currently: debit via IMPS).

    Sample (debit + paired-credit-mention):
        "ICICI Bank Acct XX000 debited with Rs 10,000.00 on 02-May-26
         & Acct XX001 credited.IMPS:000000000000. ..."

    The paired credit mention in the same body refers to the destination
    account; per spec §6 we emit ONE debit alert (the sending bank's
    primary event) and store the destination mask in `counterparty`.
    """

    bank = "icici"
    email_type = "icici_account_transaction_alert"

    _DEBIT_IMPS_PATTERN = re.compile(
        r"ICICI\s+Bank\s+Acct\s+(?P<account>XX\d+)\s+debited\s+with\s+"
        r"Rs\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+on\s+(?P<date>\d{2}-\w+-\d{2})\s+"
        r"&\s+Acct\s+(?P<dest>XX\d+)\s+credited\.IMPS:(?P<ref>\d+)"
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        text = normalize_whitespace(body)
        match = self._DEBIT_IMPS_PATTERN.search(text)
        if not match:
            raise ParseError("ICICI account IMPS debit pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                counterparty=f"Acct {match.group('dest')}",
                reference_number=match.group("ref"),
                channel="imps",
                account_mask=match.group("account"),
            ),
        )
