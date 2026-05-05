"""OneCard bank dispatcher and per-shape parsers."""

import datetime

from bank_sms_parser.models import ParsedSms
from bank_sms_parser.parsers.base import BankSmsParser, BaseSmsParser
from bank_sms_parser.parsers.onecard.charge import OnecardCcTransactionAlertParser
from bank_sms_parser.parsers.onecard.payment_received import (
    OnecardCcPaymentReceivedParser,
)
from bank_sms_parser.parsers.onecard.service_info import (
    OnecardCcServiceInfoStubParser,
)
from bank_sms_parser.parsers.onecard.statement_notice import (
    OnecardCcStatementNoticeStubParser,
)

# Order: real transaction parsers first (most-specific anchors win), then the
# BOBCARD-One service-info / statement-notice stubs at the very end so they
# can never shadow a real spend or payment-received SMS.
#
# - OnecardCcPaymentReceivedParser anchors on the unique "Hola! that was
#   sweet" phrase (AX-OneCrd-S sender family); cannot collide with BOBCARD.
# - OnecardCcTransactionAlertParser handles the three BOBCARD spend phrasings
#   (bill cleared / spent / paid <CCY>) under a single email_type.
# - OnecardCcServiceInfoStubParser raises ParserStubError on the BOBCARD
#   limit-update / service-info shape so we don't fabricate a transaction.
# - OnecardCcStatementNoticeStubParser raises ParserStubError on the BOBCARD
#   monthly bill-ready notice (model has no slot for statement notices).
_PARSERS: tuple[BaseSmsParser, ...] = (
    OnecardCcPaymentReceivedParser(),
    OnecardCcTransactionAlertParser(),
    OnecardCcStatementNoticeStubParser(),
    OnecardCcServiceInfoStubParser(),
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
    "OnecardCcServiceInfoStubParser",
    "OnecardCcStatementNoticeStubParser",
    "OnecardCcTransactionAlertParser",
    "OnecardParser",
    "parse",
]
