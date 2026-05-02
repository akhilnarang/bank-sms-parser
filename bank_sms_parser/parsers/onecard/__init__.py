"""OneCard bank dispatcher and per-shape parsers."""

import datetime

from bank_sms_parser.models import ParsedSms
from bank_sms_parser.parsers.base import BankSmsParser, BaseSmsParser
from bank_sms_parser.parsers.onecard.charge import OnecardCcTransactionAlertParser
from bank_sms_parser.parsers.onecard.payment_received import (
    OnecardCcPaymentReceivedParser,
)

# Order: payment-received (very narrow anchor "Hola! that was sweet") first;
# then the broader charge parser. Either order works because anchors are
# distinct, but specific-first is the convention.
_PARSERS: tuple[BaseSmsParser, ...] = (
    OnecardCcPaymentReceivedParser(),
    OnecardCcTransactionAlertParser(),
)


class OnecardParser(BankSmsParser):
    bank = "onecard"
    parsers = _PARSERS


def parse(
    body: str,
    *,
    sender: str | None = None,
    received_at: datetime.datetime | None = None,
) -> ParsedSms:
    return OnecardParser().parse(body, sender=sender, received_at=received_at)


__all__ = [
    "OnecardCcPaymentReceivedParser",
    "OnecardCcTransactionAlertParser",
    "OnecardParser",
    "parse",
]
