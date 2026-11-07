"""OneCard credit-card reversal SMS parser."""

import datetime
import re

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BaseSmsParser
from bank_sms_parser.parsing import (
    normalize_whitespace,
    parse_amount,
    parse_date,
    received_at_to_ist,
)


class OnecardCcReversalAlertParser(BaseSmsParser):
    """BOBCARD One credit-card reversal.

    Sample::

        "You've received a reversal of your transaction of Rs. 123.00 done
         at SampleShop In on 01 Jan 2026 with your BOBCARD One Credit Card."

    Direction is ``credit``: the amount goes back to the card. The merchant
    is the counterparty. The template has no card mask. The body date is
    the date of the original purchase, not of this credit, so the parser
    does not use it. The body has no time, and OneCard sends the SMS when
    it posts the reversal. Thus ``received_at`` (UTC to IST) gives the
    date, and ``event_time_source`` is ``message_arrival``.
    """

    bank = "onecard"
    email_type = "onecard_cc_reversal_alert"
    event_time_source = "message_arrival"

    _PATTERN = re.compile(
        r"You['’]ve\s+received\s+a\s+reversal\s+of\s+your\s+transaction\s+"
        r"of\s+Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+done\s+at\s+"
        r"(?P<merchant>.+?)\s+on\s+(?P<date>\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\s+"
        r"with\s+your\s+BOBCARD\s+One\s+Credit\s+Card\.?"
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
            raise ParseError("OneCard CC reversal pattern did not match")
        # A date that does not parse marks a corrupt body. The parser does not
        # use the date: it is the date of the original purchase.
        parse_date(match.group("date"))
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
                counterparty=match.group("merchant").strip(),
                channel="card",
            ),
        )
