"""Indian Bank SMS parsers."""

import datetime
import re

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BankSmsParser, BaseSmsParser
from bank_sms_parser.parsing import normalize_whitespace, parse_amount, parse_date


class IndianBankAccountDebitAlertParser(BaseSmsParser):
    """Indian Bank account outbound debit alert.

    Sample::

        "Sent Rs.1000.00 from A/c *0000 on 14-09-26 to RAHUL SHARMA.RRN
         000000000000.Avl Bal Rs.415919.25.Not you?SMS BLOCK to 9900000000-Indian Bank"
    """

    bank = "indian_bank"
    email_type = "indian_bank_account_debit_alert"

    _PATTERN = re.compile(
        r"Sent\s+Rs\.?\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"from\s+A/c\s+(?P<account>\*?\d+)\s+on\s+"
        r"(?P<date>\d{1,2}-\d{1,2}-\d{2,4})\s+to\s+"
        r"(?P<payee>.+?)\.\s*RRN\s*(?P<ref>[A-Za-z0-9]+)\.?\s*"
        r"Avl\s+Bal\s+Rs\.?\s*(?P<balance>-?[\d,]+(?:\.\d+)?)\.\s*"
        r"Not\s+you\?SMS\s+BLOCK\s+to\s+\d+\s*-Indian\s*Bank",
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
            raise ParseError("Indian Bank account debit pattern did not match")
        bal_raw = match.group("balance")
        balance = None
        if not bal_raw.startswith("-"):
            balance = Money(amount=parse_amount(bal_raw), currency="INR")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=parse_date(match.group("date")),
                counterparty=match.group("payee").strip() or None,
                reference_number=match.group("ref"),
                account_mask=match.group("account"),
                balance=balance,
            ),
        )


class IndianBankAccountImpsCreditAlertParser(BaseSmsParser):
    """Indian Bank account inbound IMPS credit alert.

    Sample::

        "Your a/c. XXXX0000 is credited by Rs. 200.00 on 06-09-26 by a/c linked
         to mobile 9XXXXXX00000 (IMPS Ref no. 000000000000). -IndianBank"
    """

    bank = "indian_bank"
    email_type = "indian_bank_account_imps_credit_alert"

    _PATTERN = re.compile(
        r"Your\s+a/c\.\s+(?P<account>[X\d]+)\s+is\s+credited\s+by\s+"
        r"Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+on\s+"
        r"(?P<date>\d{1,2}-\d{1,2}-\d{2,4})\s+by\s+a/c\s+linked\s+to\s+mobile\s+"
        r"(?P<mobile>[\dX]+)\s*"
        r"\(IMPS\s+Ref\s+no\.?\s+(?P<ref>[A-Za-z0-9]+)\)\.\s*-Indian\s*Bank",
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
            raise ParseError("Indian Bank account IMPS credit pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=parse_date(match.group("date")),
                counterparty=f"Mobile {match.group('mobile')}",
                reference_number=match.group("ref"),
                account_mask=match.group("account"),
                channel="imps",
            ),
        )


class IndianBankAccountCreditAlertParser(BaseSmsParser):
    """Indian Bank account inbound credit alert.

    Sample (standard with balance)::

        "Your A/c *1234 is credited with Rs.2000.00 on 13-09-26 by RAHUL SHARMA.
         RRN 000000000000. Available balance is Rs. 2154.17 - Indian Bank"

    Sample (UPI VPA transfer)::

        "Rs.109.00 credited to a/c *1234 on 14/09/2026 by a/c linked to
         VPA example@okbank (UPI Ref no 000000000000).Indian Bank"
    """

    bank = "indian_bank"
    email_type = "indian_bank_account_credit_alert"

    _PATTERN_A = re.compile(
        r"Your\s+A/c\s+(?P<account>\*?\d+)\s+is\s+credited\s+with\s+Rs\.?\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"on\s+(?P<date>\d{1,2}-\d{1,2}-\d{2,4})\s+by\s+(?P<payer>.+?)\.\s*RRN\s+(?P<ref>[A-Za-z0-9]+)\.\s*"
        r"Available\s+balance\s+is\s+Rs\.?\s*(?P<balance>-?[\d,]+(?:\.\d+)?)",
        re.IGNORECASE,
    )

    _PATTERN_B = re.compile(
        r"Rs\.?\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+credited\s+to\s+a/c\s+(?P<account>\*?\d+)\s+"
        r"on\s+(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\s+by\s+a/c\s+linked\s+to\s+VPA\s+(?P<vpa>\S+)\s+"
        r"\(UPI\s+Ref\s+no\s+(?P<ref>[A-Za-z0-9]+)\)\s*\.?\s*Indian\s*Bank",
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
        if match := self._PATTERN_A.search(text):
            bal_raw = match.group("balance")
            balance = None
            if not bal_raw.startswith("-"):
                balance = Money(amount=parse_amount(bal_raw), currency="INR")
            return ParsedSms(
                email_type=self.email_type,
                bank=self.bank,
                transaction=SmsTransactionAlert(
                    direction="credit",
                    amount=Money(
                        amount=parse_amount(match.group("amount")), currency="INR"
                    ),
                    transaction_date=parse_date(match.group("date")),
                    counterparty=match.group("payer").strip() or None,
                    reference_number=match.group("ref"),
                    account_mask=match.group("account"),
                    balance=balance,
                ),
            )

        if match := self._PATTERN_B.search(text):
            return ParsedSms(
                email_type=self.email_type,
                bank=self.bank,
                transaction=SmsTransactionAlert(
                    direction="credit",
                    amount=Money(
                        amount=parse_amount(match.group("amount")), currency="INR"
                    ),
                    transaction_date=parse_date(match.group("date")),
                    counterparty=match.group("vpa").strip(),
                    reference_number=match.group("ref"),
                    account_mask=match.group("account"),
                    channel="upi",
                ),
            )

        raise ParseError("Indian Bank account credit pattern did not match")


_PARSERS: tuple[BaseSmsParser, ...] = (
    IndianBankAccountDebitAlertParser(),
    IndianBankAccountImpsCreditAlertParser(),
    IndianBankAccountCreditAlertParser(),
)


class IndianBankParser(BankSmsParser):
    bank = "indian_bank"
    parsers = _PARSERS


def parse(
    body: str,
    *,
    sender: str | None = None,
    received_at: datetime.datetime | None = None,
) -> ParsedSms:
    return IndianBankParser().parse(body, sender=sender, received_at=received_at)
