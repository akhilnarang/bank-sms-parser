"""SBI Card SMS parsers."""

import datetime
import re

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BankSmsParser, BaseSmsParser
from bank_sms_parser.parsing import normalize_whitespace, parse_amount, parse_date


class SbiCcTransactionAlertParser(BaseSmsParser):
    """SBI credit-card spend alert.

    Sample shape::

        "Rs.123.45 spent on your SBI Credit Card ending 0000 at
         SampleMerchant on 19/07/26. Trxn. not done by you? Report at
         https://sbicard.com/Dispute"

    The template supplies no transaction time or available limit. The fraud
    reporting trailer is required so that a truncated or unrelated SBI Card
    message cannot be accepted based only on an amount and card number.
    """

    bank = "sbi"
    email_type = "sbi_cc_transaction_alert"

    _PATTERN = re.compile(
        r"Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"spent\s+on\s+your\s+SBI\s+Credit\s+Card\s+"
        r"ending\s+(?P<card>\d{4})\s+at\s+"
        r"(?P<merchant>.+?)\s+on\s+"
        r"(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\.\s+"
        r"Trxn\.\s+not\s+done\s+by\s+you\?\s+Report\s+at\s+"
        r"https://sbicard\.com/Dispute\s*$",
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
        if not (match := self._PATTERN.fullmatch(text)):
            raise ParseError("SBI CC transaction alert pattern did not match")
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
                card_mask=match.group("card"),
                channel="card",
            ),
        )


class SbiAccountCreditAlertParser(BaseSmsParser):
    """SBI savings/current account inbound credit (NEFT/IMPS/UPI).

    Sample::

        "Dear SBI User, your A/c X0000-credited by Rs.12345 on
         28Jul26 transfer from Sample Name Ref No 123456789012 -SBI"
    """

    bank = "sbi"
    email_type = "sbi_account_credit_alert"

    _PATTERN = re.compile(
        r"Dear\s+SBI\s+User,\s+your\s+A/c\s+"
        r"(?P<account>X\d+)-credited\s+by\s+"
        r"Rs\.?\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+on\s+"
        r"(?P<date>\S+)\s+transfer\s+from\s+"
        r"(?P<sender>.+?)\s+Ref\s+No\s+"
        r"(?P<ref>\d+)\s+-\s*SBI",
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
            raise ParseError("SBI account credit pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=parse_date(match.group("date")),
                counterparty=match.group("sender").strip(),
                reference_number=match.group("ref"),
                account_mask=match.group("account"),
            ),
        )


_PARSERS: tuple[BaseSmsParser, ...] = (
    SbiCcTransactionAlertParser(),
    SbiAccountCreditAlertParser(),
)


class SbiParser(BankSmsParser):
    bank = "sbi"
    parsers = _PARSERS


def parse(
    body: str,
    *,
    sender: str | None = None,
    received_at: datetime.datetime | None = None,
) -> ParsedSms:
    return SbiParser().parse(body, sender=sender, received_at=received_at)
