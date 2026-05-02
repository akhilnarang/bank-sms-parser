"""ICICI bank dispatcher and per-shape parsers."""

import datetime

from bank_sms_parser.models import ParsedSms
from bank_sms_parser.parsers.base import BankSmsParser, BaseSmsParser
from bank_sms_parser.parsers.icici.account import IciciAccountTransactionAlertParser
from bank_sms_parser.parsers.icici.cc import IciciCcTransactionAlertParser

# Order: more specific first. Both regexes are anchored on distinct
# substrings ("ICICI Bank Acct ... debited with" vs "INR ... spent using
# ICICI Bank Card"), so order is mostly insurance.
_PARSERS: tuple[BaseSmsParser, ...] = (
    IciciAccountTransactionAlertParser(),
    IciciCcTransactionAlertParser(),
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
    "IciciAccountTransactionAlertParser",
    "IciciCcTransactionAlertParser",
    "IciciParser",
    "parse",
]
