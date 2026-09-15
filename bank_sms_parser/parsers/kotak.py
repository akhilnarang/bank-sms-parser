"""Kotak Mahindra Bank SMS parsers.

Supported SMS types:
- kotak_dc_transaction_alert: Debit card spend at a merchant
- kotak_account_upi_debit_alert: UPI payment sent from the account
- kotak_account_transaction_processed_alert: Bare "processed successfully"
  confirmation. It states no direction, so it carries no transaction.
"""

import datetime
import re

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BankSmsParser, BaseSmsParser
from bank_sms_parser.parsing import (
    normalize_whitespace,
    parse_amount,
    parse_date,
    received_at_to_ist,
)


class KotakDcTransactionAlertParser(BaseSmsParser):
    """Parse a Kotak debit card spend.

    Example:
        "Rs.1234.56 spent via Kotak Debit Card XX0000 at SAMPLE MERCHANT on
         16/07/2026. Avl bal Rs.9999.99 Not you?Tap
         https://kotak.com/KBANKT/Fraud"

    Money leaves the account at a merchant, so ``direction`` is ``debit`` and
    ``channel`` is ``card``. The card mask gives ``card_mask`` and the
    merchant gives ``counterparty``.

    The body gives a date but no time. The bank sends this SMS at the moment
    of the transaction, so the parser takes the time from ``received_at``.
    The body date stays, because the bank states it.

    The body gives the balance after the transaction. Two spends of the same
    amount on one day differ only in that balance, so the consumer needs it
    to tell them apart.

    The parser requires the fraud report text. This text prevents a match
    with an OTP or an incomplete message.
    """

    bank = "kotak"
    email_type = "kotak_dc_transaction_alert"
    event_time_source = "message_arrival"

    _PATTERN = re.compile(
        r"Rs\.?\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+spent\s+via\s+"
        r"Kotak\s+Debit\s+Card\s+(?P<card>[X\d]+)\s+"
        r"at\s+(?P<merchant>.+?)\s+on\s+(?P<date>\d{1,2}/\d{1,2}/\d{4})\.\s*"
        r"Avl\s+bal\s+Rs\.?\s*(?P<balance>[\d,]+(?:\.\d+)?)\s+"
        r"Not\s+you\?\s*Tap\s+\S+\s*$",
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
            raise ParseError("Kotak debit card spend pattern did not match")
        txn_time: datetime.time | None = None
        if received_at is not None:
            txn_time = received_at_to_ist(received_at).time()
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=parse_date(match.group("date")),
                transaction_time=txn_time,
                counterparty=match.group("merchant").strip(),
                card_mask=match.group("card"),
                channel="card",
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
            ),
        )


class KotakAccountUpiDebitAlertParser(BaseSmsParser):
    """Parse a Kotak UPI payment sent from the account.

    Two wordings share this shape:
        "Sent Rs.500.00 from Kotak Bank A/c X0000 to SampleCo on 10-09-26.
         UPI Ref 000000000000. Not done by you? Tap
         https://kotak.bank.in/KBANKT/Fraud"
        "Sent Rs.9.00 from XX0000 to SampleCo on 08-Sep-26. UPI ref no.
         000000000000. Not you? Tap https://kotk.in/KOTAKD/XXXXXX to
         report -Kotak"

    The second wording drops "Kotak Bank A/c", writes the date with a
    month name, and says "UPI ref no." instead of "UPI Ref".

    The date accepts a number or a name for the month, one digit or two
    for the day, and a hyphen or a slash. The bank writes the two known
    wordings differently, so a third style is likely.

    Money leaves the account to a payee, so ``direction`` is ``debit`` and
    ``channel`` is ``upi``. The UPI reference gives ``reference_number``,
    which makes the event identifiable across channels.

    The body gives a date but no time and no balance. The bank sends this
    SMS at the moment of the transaction, so the parser takes the time from
    ``received_at``.

    The parser requires the fraud report text. This text prevents a match
    with an OTP or an incomplete message.
    """

    bank = "kotak"
    email_type = "kotak_account_upi_debit_alert"
    event_time_source = "message_arrival"

    _PATTERN = re.compile(
        r"Sent\s+Rs\.?\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+from\s+"
        r"(?:Kotak\s+Bank\s+A/c\s+)?(?P<account>[Xx]+\d+)\s+"
        r"to\s+(?P<payee>.+?)\s+on\s+(?P<date>\d{1,2}[-/]\w{1,9}[-/]\d{2,4})\.\s*"
        r"UPI\s+[Rr]ef(?:\s+no\.?)?\s*(?P<ref>\w+)\.\s*"
        r"Not\s+(?:done\s+by\s+)?you\?",
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
            raise ParseError("Kotak UPI debit pattern did not match")
        txn_time: datetime.time | None = None
        if received_at is not None:
            txn_time = received_at_to_ist(received_at).time()
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=parse_date(match.group("date")),
                transaction_time=txn_time,
                counterparty=match.group("payee").strip(),
                account_mask=match.group("account"),
                reference_number=match.group("ref"),
                channel="upi",
            ),
        )


class KotakAccountTransactionProcessedAlertParser(BaseSmsParser):
    """Parse a Kotak bare "transaction processed" confirmation.

    Example:
        "Your transaction for INR 10000.00 against txn ID 000000000000 has
         been processed successfully. -Kotak"

    The body gives an amount and a transaction ID. It does not give a
    direction, an account, or a counterparty. The bank sends it after a
    transfer that another message already reports, on one side or both.

    The parser returns no ``transaction``. A ``SmsTransactionAlert``
    requires a direction, and the body states none. A made-up direction
    would be a false statement about the event, and a consumer that reads
    it would put a phantom row in the ledger.

    ``ledger_role`` stays ``primary``, because the role describes a
    transaction and there is none here. See ``ParsedSms.ledger_role``:
    "not a transaction" is ``transaction is None``, which is an axis of
    its own.

    TODO(transaction-linkage): the reference number joins this message to
    the row that another message already opened. The model has nowhere to
    put a reference without a transaction, so the link is lost. Give the
    consumer the reference, then let it stamp the arrival on that row.
    """

    bank = "kotak"
    email_type = "kotak_account_transaction_processed_alert"
    event_time_source = "message_arrival"

    _PATTERN = re.compile(
        r"Your\s+transaction\s+for\s+(?:INR|Rs\.?)\s*"
        r"(?P<amount>[\d,]+(?:\.\d+)?)\s+against\s+txn\s+ID\s+"
        r"(?P<ref>\w+)\s+has\s+been\s+processed\s+successfully",
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
        if not self._PATTERN.search(text):
            raise ParseError("Kotak transaction-processed pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
        )


_PARSERS = (
    KotakDcTransactionAlertParser(),
    KotakAccountUpiDebitAlertParser(),
    KotakAccountTransactionProcessedAlertParser(),
)


class KotakParser(BankSmsParser):
    bank = "kotak"
    parsers = _PARSERS


def parse(
    body: str,
    *,
    sender: str | None = None,
    received_at: datetime.datetime | None = None,
) -> ParsedSms:
    return KotakParser().parse(body, sender=sender, received_at=received_at)
