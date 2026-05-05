"""OneCard / BOBCARD statement-ready SMS stub parser.

BOBCARD One sends a monthly bill-ready notice (no card mask, no payment
event):

    "Hi, Hope you love using your BOBCARD One Credit Card! Your <Month-Year>
     bill of Rs.X is ready. Please pay by <date> through the OneCard app.
     View statement: 1crd.in/OneCrd/bill"

This is a reminder, not a transaction. ``SmsTransactionAlert`` has no slot
for "statement notice" data (no ``password_hint`` equivalent on the SMS
side; the model only models real money movement). Per the skill we reject
reminder messages, but to distinguish "intentionally unsupported known
shape" from "generic regex miss" we raise ``ParserStubError`` rather than
``ParseError``. The match is gated on the BOBCARD brand marker plus the
canonical reminder phrase ("bill of Rs.X is ready") so we cannot swallow a
real spend or payment-received body.
"""

import datetime
import re

from bank_sms_parser.exceptions import ParseError, ParserStubError
from bank_sms_parser.models import ParsedSms
from bank_sms_parser.parsers.base import BaseSmsParser
from bank_sms_parser.parsing import normalize_whitespace

_BRAND_MARKER = re.compile(r"BOBCARD\s+One\s+Credit\s+Card", re.IGNORECASE)

# "Your <Month>-<Year> bill of Rs.X is ready" — anchor is the literal phrase
# "bill of Rs" + ... + "is ready". This must NOT match the bill-cleared
# spend SMS ("Your bill of Rs. X at MERCHANT has been cleared ...").
_STATEMENT_READY = re.compile(
    r"bill\s+of\s+Rs\.?\s*[\d,]+(?:\.\d+)?\s+is\s+ready",
    re.IGNORECASE,
)


class OnecardCcStatementNoticeStubParser(BaseSmsParser):
    """Recognize-and-skip parser for the BOBCARD One statement-ready notice."""

    bank = "onecard"
    email_type = "onecard_cc_statement_notice_stub"

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        text = normalize_whitespace(body)
        if not _BRAND_MARKER.search(text):
            raise ParseError("OneCard statement notice: no BOBCARD One brand marker")
        if not _STATEMENT_READY.search(text):
            raise ParseError("OneCard statement notice: not a 'bill is ready' shape")
        raise ParserStubError(
            "onecard_cc_statement_notice_stub: recognized BOBCARD One "
            "statement-ready reminder; the SmsTransactionAlert model has no "
            "field for statement notices, so this shape is intentionally "
            "unimplemented"
        )
