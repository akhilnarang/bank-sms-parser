"""ICICI bank dispatcher and per-shape parsers."""

import datetime

from bank_sms_parser.models import ParsedSms
from bank_sms_parser.parsers.base import BankSmsParser, BaseSmsParser
from bank_sms_parser.parsers.icici.account import (
    IciciAccountCreditInfoAlertParser,
    IciciAccountDebitInfoAlertParser,
    IciciAccountImpsCreditAlertParser,
    IciciAccountMandateDebitAlertParser,
    IciciAccountTransactionAlertParser,
    IciciAccountUpiCreditAlertParser,
)
from bank_sms_parser.parsers.icici.cc import (
    IciciCcPaymentReceivedAlertParser,
    IciciCcTransactionAlertParser,
)

# Order: more specific first. Each regex is anchored on a distinct substring
# ("ICICI Bank Acct ... debited with", "INR/Rs ... spent ... ICICI Bank Card",
# "Payment of Rs ... received on your ICICI Bank Credit Card"), so order is
# mostly insurance.
_PARSERS: tuple[BaseSmsParser, ...] = (
    IciciAccountUpiCreditAlertParser(),
    IciciAccountImpsCreditAlertParser(),
    IciciAccountMandateDebitAlertParser(),
    IciciAccountCreditInfoAlertParser(),
    IciciAccountDebitInfoAlertParser(),
    IciciAccountTransactionAlertParser(),
    IciciCcTransactionAlertParser(),
    IciciCcPaymentReceivedAlertParser(),
)


class IciciParser(BankSmsParser):
    bank = "icici"
    parsers = _PARSERS


def parse(
    body: str,
    *,
    sender: str | None = None,
    received_at: datetime.datetime | None = None,
) -> ParsedSms:
    return IciciParser().parse(body, sender=sender, received_at=received_at)


__all__ = [
    "IciciAccountCreditInfoAlertParser",
    "IciciAccountDebitInfoAlertParser",
    "IciciAccountImpsCreditAlertParser",
    "IciciAccountMandateDebitAlertParser",
    "IciciAccountTransactionAlertParser",
    "IciciAccountUpiCreditAlertParser",
    "IciciCcPaymentReceivedAlertParser",
    "IciciCcTransactionAlertParser",
    "IciciParser",
    "parse",
]
