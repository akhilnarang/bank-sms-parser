"""Union Bank of India SMS parsers."""

import datetime
import re
from typing import Literal

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BankSmsParser, BaseSmsParser
from bank_sms_parser.parsing import normalize_whitespace, parse_amount, parse_datetime


class UnionAccountMobBkDebitAlertParser(BaseSmsParser):
    """Union Bank account mobile-banking outbound debit alert.

    Sample::

        "Union Bank of India A/c *0000 Debited Rs:151.00 on 25-08-2026 09:50:01
         by Mob Bk ref no 000000000000, Fvg: RAHUL SHARMA Avl Bal Rs:7138.46.
         Not you?Call 18002333/SMS BLOCK 0000 to 9900000000"
    """

    bank = "union"
    email_type = "union_account_mob_bk_debit_alert"

    _PATTERN = re.compile(
        r"(?:Union\s+Bank\s+of\s+India\s+)?A/c\s+(?P<account>\*?\d+)\s+"
        r"Debited\s+Rs:(?P<amount>[\d,]+(?:\.\d+)?)\s+on\s+"
        r"(?P<date>\d{1,2}-\d{1,2}-\d{4})\s+(?P<time>\d{1,2}:\d{2}:\d{2})\s+"
        r"by\s+Mob\s+Bk\s+ref\s+no\s+(?P<ref>[A-Za-z0-9]+),\s*"
        r"Fvg:\s*(?P<payee>.*?)\s*"
        r"Avl\s+Bal\s+Rs:(?P<balance>[\d,]+(?:\.\d+)?)\.\s*"
        r"Not\s+you\?Call\s+[\d\s]+/SMS\s+BLOCK\s+\d+\s+to\s+\d+",
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
            raise ParseError("Union Bank account Mob Bk debit pattern did not match")
        txn_dt = parse_datetime(f"{match.group('date')} {match.group('time')}")
        payee = match.group("payee").strip() or None
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=txn_dt.date(),
                transaction_time=txn_dt.time(),
                counterparty=payee,
                reference_number=match.group("ref"),
                account_mask=match.group("account"),
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
            ),
        )

    def identifies_by_for(
        self, result: ParsedSms
    ) -> Literal["counterparty", "card_mask", "none"]:
        transaction = result.transaction
        if transaction is None or transaction.counterparty is None:
            return "none"
        return "counterparty"


class UnionAccountMobBkCreditAlertParser(BaseSmsParser):
    """Union Bank account mobile-banking inbound credit alert.

    Sample::

        "A/c *0000 Credited for Rs:60.00 on 28-08-2026 11:09:48 by Mob Bk ref no
         000000000000 Avl Bal Rs:4364.46.Never Share OTP/PIN/CVV-Union Bank of India"
    """

    bank = "union"
    email_type = "union_account_mob_bk_credit_alert"
    identifies_by = "none"

    _PATTERN = re.compile(
        r"(?:Your\s+SB\s+)?A/c\s+(?P<account>\*?\d+)\s+"
        r"Credited\s+for\s+Rs:(?P<amount>[\d,]+(?:\.\d+)?)\s+on\s+"
        r"(?P<date>\d{1,2}-\d{1,2}-\d{4})\s+(?P<time>\d{1,2}:\d{2}:\d{2})\s+"
        r"by\s+Mob\s+Bk\s+ref\s+no\s+(?P<ref>[A-Za-z0-9]+)\s+"
        r"Avl\s+Bal\s+Rs:(?P<balance>-?[\d,]+(?:\.\d+)?)\.\s*"
        r"Never\s+Share\s+OTP/PIN/CVV(?:-Union\s+Bank\s+of\s+India)?",
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
            raise ParseError("Union Bank account Mob Bk credit pattern did not match")
        txn_dt = parse_datetime(f"{match.group('date')} {match.group('time')}")
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
                transaction_date=txn_dt.date(),
                transaction_time=txn_dt.time(),
                reference_number=match.group("ref"),
                account_mask=match.group("account"),
                balance=balance,
            ),
        )


class UnionAccountImpsCreditAlertParser(BaseSmsParser):
    """Union Bank account IMPS inbound credit alert.

    Sample::

        "Your SB A/c *0000 Credited for Rs:1500.00 on 11-09-2026 12:04:11
         by IMPS ref no 000000000000 Avl Bal Rs:2198.72.Never Share PIN/OTP-Union Bank of India"
    """

    bank = "union"
    email_type = "union_account_imps_credit_alert"
    identifies_by = "none"

    _PATTERN = re.compile(
        r"(?:Your\s+SB\s+)?A/c\s+(?P<account>\*?\d+)\s+"
        r"Credited\s+for\s+Rs:(?P<amount>[\d,]+(?:\.\d+)?)\s+on\s+"
        r"(?P<date>\d{1,2}-\d{1,2}-\d{4})\s+(?P<time>\d{1,2}:\d{2}:\d{2})\s+"
        r"by\s+IMPS\s+ref\s+no\s+(?P<ref>[A-Za-z0-9]+)\s+"
        r"Avl\s+Bal\s+Rs:(?P<balance>[\d,]+(?:\.\d+)?)\.\s*"
        r"Never\s+Share\s+PIN/OTP(?:-Union\s+Bank\s+of\s+India)?",
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
            raise ParseError("Union Bank account IMPS credit pattern did not match")
        txn_dt = parse_datetime(f"{match.group('date')} {match.group('time')}")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=txn_dt.date(),
                transaction_time=txn_dt.time(),
                reference_number=match.group("ref"),
                account_mask=match.group("account"),
                channel="imps",
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
            ),
        )


class UnionAccountBranchCreditAlertParser(BaseSmsParser):
    """Union Bank account branch cash/deposit credit alert.

    Sample::

        "Your SB A/c *0000 Credited for Rs:1500.00 on 08-09-2026 12:51:28
         by BRANCH Avl Bal Rs:3523.40.Don't share Card PIN/CVV -Union Bank of India"
    """

    bank = "union"
    email_type = "union_account_branch_credit_alert"
    identifies_by = "none"

    _PATTERN = re.compile(
        r"(?:Your\s+SB\s+)?A/c\s+(?P<account>\*?\d+)\s+"
        r"Credited\s+for\s+Rs:(?P<amount>[\d,]+(?:\.\d+)?)\s+on\s+"
        r"(?P<date>\d{1,2}-\d{1,2}-\d{4})\s+(?P<time>\d{1,2}:\d{2}:\d{2})\s+"
        r"by\s+BRANCH\s+"
        r"Avl\s+Bal\s+Rs:(?P<balance>[\d,]+(?:\.\d+)?)\.\s*"
        r"Don't\s+share\s+Card\s+PIN/CVV\s*-Union\s+Bank\s+of\s+India",
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
            raise ParseError("Union Bank account branch credit pattern did not match")
        txn_dt = parse_datetime(f"{match.group('date')} {match.group('time')}")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=txn_dt.date(),
                transaction_time=txn_dt.time(),
                account_mask=match.group("account"),
                channel="branch",
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
            ),
        )


_PARSERS: tuple[BaseSmsParser, ...] = (
    UnionAccountMobBkDebitAlertParser(),
    UnionAccountMobBkCreditAlertParser(),
    UnionAccountImpsCreditAlertParser(),
    UnionAccountBranchCreditAlertParser(),
)


class UnionParser(BankSmsParser):
    bank = "union"
    parsers = _PARSERS


def parse(
    body: str,
    *,
    sender: str | None = None,
    received_at: datetime.datetime | None = None,
) -> ParsedSms:
    return UnionParser().parse(body, sender=sender, received_at=received_at)
