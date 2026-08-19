"""SBI Card SMS parsers."""

import datetime
import re

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BankSmsParser, BaseSmsParser
from bank_sms_parser.parsing import (
    normalize_whitespace,
    parse_amount,
    parse_date,
    parse_datetime,
    received_at_to_ist,
)


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


class SbiCcPaymentReceivedAlertParser(BaseSmsParser):
    """SBI Card bill-payment processed notification.

    Sample::

        "Dear SBI Cardholder, payment of Rs. 12345.00 for your SBI
         Credit Card has been successfully processed.
         ref no : ABC00DE0FG0HIJ."

    Direction is ``credit``: the payment reduces outstanding CC debt.
    The body carries no card mask (the user may hold more than one SBI
    card) and no merchant, so ``identifies_by`` is ``none``; the
    alphanumeric ``ref no`` is the reference. It also carries no date:
    ``received_at`` (UTC→IST) fills the transaction date when supplied,
    and SBI sends the SMS at the moment the payment is processed, so
    ``event_time_source`` is ``message_arrival``. The full
    ``has been successfully processed`` clause plus the ``ref no``
    trailer are both required so a payment reminder or promo quoting an
    amount cannot fabricate a credit.
    """

    bank = "sbi"
    email_type = "sbi_cc_payment_received_alert"
    event_time_source = "message_arrival"
    identifies_by = "none"

    _PATTERN = re.compile(
        r"Dear\s+SBI\s+Cardholder,\s+payment\s+of\s+"
        r"Rs\.?\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"for\s+your\s+SBI\s+Credit\s+Card\s+has\s+been\s+"
        r"successfully\s+processed\.\s*"
        r"ref\s+no\s*:\s*(?P<ref>[A-Za-z0-9]+)",
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
            raise ParseError("SBI CC payment-received pattern did not match")
        txn_date: datetime.date | None = None
        if received_at is not None:
            txn_date = received_at_to_ist(received_at).date()
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=txn_date,
                counterparty="Payment received",
                reference_number=match.group("ref"),
                channel="card",
            ),
        )


class SbiDcTransactionAlertParser(BaseSmsParser):
    """SBI debit-card spend alert.

    Sample::

        "Dear Customer, transaction number 000000000000 for Rs.100.00 by
         SBI Debit Card X0000 done at SampleMerchant on 01Jan26 at
         10:00:00. Your updated available balance is Rs.200.00. If not
         done by you, forward this SMS to 0000000000/ call 0000000000 to
         block card. GOI helpline for cyber fraud 1930."

    The body carries the reference number, the card mask, the merchant,
    the date and time, and the updated available balance. The fraud report
    trailer is required. It stops a truncated or unrelated SBI message from
    matching on an amount and a card number alone.
    """

    bank = "sbi"
    email_type = "sbi_dc_transaction_alert"

    _PATTERN = re.compile(
        r"Dear\s+Customer,\s+transaction\s+number\s+(?P<ref>\d+)\s+"
        r"for\s+Rs\.?\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"by\s+SBI\s+Debit\s+Card\s+(?P<card>X\d+)\s+"
        r"done\s+at\s+(?P<merchant>.+?)\s+"
        r"on\s+(?P<date>\d{1,2}[A-Za-z]{3}\d{2,4})\s+at\s+"
        r"(?P<time>\d{1,2}:\d{2}:\d{2})\.\s+"
        r"Your\s+updated\s+available\s+balance\s+is\s+"
        r"Rs\.?\s*(?P<balance>[\d,]+(?:\.\d+)?)\.\s+"
        r"If\s+not\s+done\s+by\s+you,\s+forward\s+this\s+SMS\s+to\s+"
        r".*?block\s+card",
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
            raise ParseError("SBI DC transaction alert pattern did not match")
        txn_dt = parse_datetime(f"{match.group('date')} {match.group('time')}")
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
                counterparty=match.group("merchant").strip(),
                card_mask=match.group("card"),
                reference_number=match.group("ref"),
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
                channel="card",
            ),
        )


_PARSERS: tuple[BaseSmsParser, ...] = (
    SbiCcTransactionAlertParser(),
    SbiDcTransactionAlertParser(),
    # CC payment-received: unique "payment ... for your SBI Credit Card has
    # been successfully processed" anchor; cannot collide with the spend or
    # account-credit shapes.
    SbiCcPaymentReceivedAlertParser(),
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
