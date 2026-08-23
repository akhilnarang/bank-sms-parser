"""Revolut India (UPI prepaid wallet) SMS parsers."""

import datetime
import re

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BankSmsParser, BaseSmsParser
from bank_sms_parser.parsing import normalize_whitespace, parse_amount, parse_datetime


class RevolutUpiCreditAlertParser(BaseSmsParser):
    """Parse a Revolut wallet UPI credit alert.

    Sample (sanitized):
        "₹1,234.50 credited to your account via UPI on 15 May 2026 03:30 PM
         IST from Sample Payer. Balance: ₹5,678.90 - Revolut India"

    Money came into the wallet, so this is a credit. The body carries the
    amount, the channel, the date, the time, the payer, and the new balance.
    It has no account mask, which is expected for a payment-received alert.
    The "- Revolut India" signature and the fixed "credited to your account
    via ... Balance:" frame keep it apart from OTP and promo messages. The
    amount uses the bare ₹ symbol, so it is wrapped as INR Money. The time is
    in the body, so no received_at fallback is used.
    """

    bank = "revolut"
    email_type = "revolut_upi_credit_alert"

    _PATTERN = re.compile(
        r"₹\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+credited\s+to\s+your\s+account\s+"
        r"via\s+(?P<channel>[A-Za-z]+)\s+on\s+(?P<datetime>.+?)\s+IST\s+"
        r"from\s+(?P<counterparty>.+?)\.\s+"
        r"Balance:\s*₹\s*(?P<balance>[\d,]+(?:\.\d+)?)\s*-\s*Revolut\s+India\s*$",
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
            raise ParseError("Revolut UPI credit pattern did not match")
        dt = parse_datetime(match.group("datetime"))
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=dt.date(),
                transaction_time=dt.time(),
                counterparty=match.group("counterparty").strip(),
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
                channel=match.group("channel").lower(),
            ),
        )


_PARSERS: tuple[BaseSmsParser, ...] = (RevolutUpiCreditAlertParser(),)


class RevolutParser(BankSmsParser):
    bank = "revolut"
    parsers = _PARSERS


def parse(
    body: str,
    *,
    sender: str | None = None,
    received_at: datetime.datetime | None = None,
) -> ParsedSms:
    return RevolutParser().parse(body, sender=sender, received_at=received_at)
