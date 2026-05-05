"""OneCard / BOBCARD service-info SMS stub parser.

The BOBCARD One template family ships several non-transactional service-info
SMSes that share TRAI senders with the real spend / payment-received alerts.
Examples seen in production:

    "Hi Customer, As per your request, your International Tap to Pay Txn
     limit has been updated to Rs.X. To view or update, click ... -
     Team BOBCARD One Credit Card"

These are NOT transactions: there is no debit, no credit, no canonical verb.
A naive parser that grabs the rupee amount would fabricate a fake transaction
out of a card-limit update.

Per the skill (`add-bank-sms-parser/SKILL.md`), we explicitly recognize the
shape and raise ``ParserStubError`` so the dispatcher records *intentional*
non-implementation rather than a generic regex miss. The match conditions
are intentionally narrow — both the BOBCARD-One marker AND a service-info
verb phrase ("limit has been updated", "Team BOBCARD One Credit Card",
etc.) — so we cannot accidentally swallow a real spend SMS that happens to
carry the BOBCARD branding.
"""

import datetime
import re

from bank_sms_parser.exceptions import ParseError, ParserStubError
from bank_sms_parser.models import ParsedSms
from bank_sms_parser.parsers.base import BaseSmsParser
from bank_sms_parser.parsing import normalize_whitespace

# Required brand marker — present in every real BOBCARD One service-info SMS.
_BRAND_MARKER = re.compile(r"BOBCARD\s+One\s+Credit\s+Card", re.IGNORECASE)

# Service-info phrasings observed so far. Add to this tuple when new shapes
# show up; do NOT broaden any individual pattern to match transactions.
_SERVICE_INFO_PATTERNS: tuple[re.Pattern[str], ...] = (
    # "your <something> limit has been updated to Rs.X"
    re.compile(r"limit\s+has\s+been\s+updated\s+to", re.IGNORECASE),
    # Team-signature on a non-transaction body
    re.compile(r"Team\s+BOBCARD\s+One\s+Credit\s+Card", re.IGNORECASE),
)


class OnecardCcServiceInfoStubParser(BaseSmsParser):
    """Recognize-and-skip parser for BOBCARD One service-info SMSes.

    Raises ``ParserStubError`` when the body is unambiguously a service-info
    notice (limit update, profile change, etc.). Raises ``ParseError`` for
    everything else, so the dispatcher continues to the real parsers.
    """

    bank = "onecard"
    email_type = "onecard_cc_service_info_stub"

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        text = normalize_whitespace(body)
        if not _BRAND_MARKER.search(text):
            raise ParseError("OneCard service-info: no BOBCARD One brand marker")
        for pattern in _SERVICE_INFO_PATTERNS:
            if pattern.search(text):
                raise ParserStubError(
                    "onecard_cc_service_info_stub: recognized BOBCARD One "
                    "service-info SMS (e.g. limit update); intentionally "
                    "not parsed as a transaction"
                )
        raise ParseError("OneCard service-info: no recognized service-info phrase")
