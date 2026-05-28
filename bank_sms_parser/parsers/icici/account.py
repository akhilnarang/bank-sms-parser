"""ICICI account-level SMS parser (savings/checking IMPS/NEFT/UPI debit/credit)."""

import datetime
import re

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BaseSmsParser
from bank_sms_parser.parsing import normalize_whitespace, parse_amount, parse_date


class IciciAccountTransactionAlertParser(BaseSmsParser):
    """ICICI account-level transaction alert (debit via IMPS or UPI)."""

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


class IciciAccountUpiCreditAlertParser(BaseSmsParser):
    """ICICI account UPI credit alert without an available-balance field."""

    bank = "icici"
    email_type = "icici_account_upi_credit_alert"

    _PATTERN = re.compile(
        r"Dear\s+Customer,\s+Acct\s+(?P<account>XX\d+)\s+"
        r"is\s+credited\s+with\s+Rs\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"on\s+(?P<date>\d{1,2}-\w+-\d{2})\s+"
        r"from\s+(?P<payer>.+?)\.\s+UPI:(?P<ref>\d+)-ICICI\s+Bank\."
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
            raise ParseError("ICICI account UPI credit pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                counterparty=match.group("payer").strip(),
                reference_number=match.group("ref"),
                channel="upi",
                account_mask=match.group("account"),
            ),
        )
