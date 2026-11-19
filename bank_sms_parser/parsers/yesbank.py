"""Yes Bank SMS parsers."""

import datetime
import re
from typing import Literal

from bank_sms_parser.exceptions import ParseError, ParserStubError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BankSmsParser, BaseSmsParser
from bank_sms_parser.parsing import (
    normalize_whitespace,
    parse_amount,
    parse_date,
    parse_datetime,
)


class YesbankAccountChequeDepositAlertParser(BaseSmsParser):
    """Parse a Yes Bank account cheque deposit credit alert.

    Sample (sanitized):
        "INR 12,345.00 credited to A/c XX0000 towards CHQ DEP SAMPLEBANK
         14-OCT-26 SAMPLE BRANCH CUSTOMER NAME Value 15-OCT-2026 10:20:30 .
         Clear Bal is INR 23,456.78 ."

    Money entered the account from a cheque deposit, so this is a credit.
    The body carries the amount, the account mask, the cheque deposit
    narration, the value date and time, and the clear balance. The narration
    is kept in counterparty so it can match bank-statement rows. The time is
    in the body, so no received_at fallback is used.
    """

    bank = "yesbank"
    email_type = "yesbank_account_cheque_deposit_alert"

    _PATTERN = re.compile(
        r"INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+credited\s+to\s+A/c\s+(?P<account>X+\d+)\s+"
        r"towards\s+(?P<narration>CHQ\s+DEP\b.+?)\s+"
        r"Value\s+(?P<date>\d{2}-[A-Za-z]{3}-\d{4})\s+(?P<time>\d{2}:\d{2}:\d{2})\s*\.\s*"
        r"Clear\s+Bal\s+is\s+INR\s+(?P<balance>[\d,]+(?:\.\d+)?)\s*\.\s*$",
        re.IGNORECASE,
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        """Parse one Yes Bank cheque deposit alert.

        Args:
            body: The SMS body text.
            sender: The optional TRAI sender ID.
            received_at: The optional UTC arrival time.

        Returns:
            The parsed message with a credit transaction.

        Raises:
            ParseError: If the body does not match the cheque deposit shape.
        """
        text = normalize_whitespace(body)
        if not (match := self._PATTERN.search(text)):
            raise ParseError("Yes Bank cheque deposit pattern did not match")
        dt = parse_datetime(f"{match.group('date')} {match.group('time')}")
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
                counterparty=match.group("narration").strip(),
                account_mask=match.group("account"),
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
                channel="cheque",
            ),
        )


class YesbankAccountRtgsDebitAlertParser(BaseSmsParser):
    """Parse a Yes Bank outgoing RTGS debit SMS.

    Sample (synthetic):
        "Your RTGS from YES BANK Ac with Ref No YESBR9999010100000000 of INR
         12,345.00 has been credited to beneficiary Ac XXXXXXX9999 on
         21-08-2026 at 10:20:30"

    Yes Bank sends only this SMS for an outgoing RTGS transfer. It sends no
    separate debit alert. Thus this message is the primary debit. The body
    omits the source account mask. The body holds the beneficiary mask only.
    The parser does not map it to account_mask. The body has no beneficiary
    name, so counterparty stays empty. The body carries the reference number,
    the amount, and the event date and time.
    """

    bank = "yesbank"
    email_type = "yesbank_account_rtgs_debit_alert"

    _PATTERN = re.compile(
        r"Your\s+RTGS\s+from\s+YES\s+BANK\s+Ac\s+with\s+Ref\s+No\s+(?P<ref>[A-Z0-9]+)\s+"
        r"of\s+INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+has\s+been\s+credited\s+to\s+"
        r"beneficiary\s+Ac\s+X+\d+\s+"
        r"on\s+(?P<date>\d{1,2}-\d{1,2}-\d{4})\s+at\s+(?P<time>\d{1,2}:\d{2}:\d{2})\s*\.?\s*$",
        re.IGNORECASE,
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        """Parse one Yes Bank RTGS debit SMS.

        Args:
            body: The SMS body text.
            sender: The optional TRAI sender ID.
            received_at: The optional UTC arrival time.

        Returns:
            The parsed message with a primary debit transaction.

        Raises:
            ParseError: If the body does not match the RTGS debit shape.
        """
        text = normalize_whitespace(body)
        if not (match := self._PATTERN.search(text)):
            raise ParseError("Yes Bank RTGS debit pattern did not match")
        dt = parse_datetime(f"{match.group('date')} {match.group('time')}")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=dt.date(),
                transaction_time=dt.time(),
                reference_number=match.group("ref"),
                channel="rtgs",
                raw_description=body,
            ),
        )


class YesbankAccountNeftCreditAlertParser(BaseSmsParser):
    """Parse a Yes Bank account NEFT credit alert.

    Sample (synthetic):
        "INR 12,345.00 credited to YES BANK Ac X0000 on 01JAN26 10:20.
         NEFT:SAMP0000000000/From:Mr. SAMPLE NAME. Bal INR 23,456.78."

    The body carries the amount, the account mask, the event date and time,
    the NEFT reference, the payer name and the balance. The bank can cut the
    payer name short. The parser keeps the name as sent, with any title.
    """

    bank = "yesbank"
    email_type = "yesbank_account_neft_credit_alert"

    _PATTERN = re.compile(
        r"INR\s+(?P<amount>[\d,]+\.\d{2})\s+credited\s+to\s+YES\s+BANK\s+Ac\s+"
        r"(?P<account>X+\d+)\s+on\s+(?P<date>\d{2}[A-Za-z]{3}\d{2})\s+"
        r"(?P<time>\d{2}:\d{2})\.\s+"
        r"NEFT:(?P<ref>[A-Z0-9]{8,})/From:(?P<name>.+?)\.\s+"
        r"Bal\s+INR\s+(?P<balance>[\d,]+\.\d{2})\.\s*$",
        re.IGNORECASE,
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        """Parse one Yes Bank NEFT credit alert.

        Args:
            body: The SMS body text.
            sender: The optional TRAI sender ID.
            received_at: The optional UTC arrival time.

        Returns:
            The parsed message with a credit transaction.

        Raises:
            ParseError: If the body does not match the NEFT credit shape.
        """
        text = normalize_whitespace(body)
        if not (match := self._PATTERN.search(text)):
            raise ParseError("Yes Bank NEFT credit pattern did not match")
        try:
            dt = datetime.datetime.strptime(
                f"{match.group('date')} {match.group('time')}", "%d%b%y %H:%M"
            )
        except ValueError as exc:
            raise ParseError(f"Yes Bank NEFT credit date: {exc}") from exc
        name = match.group("name").strip()
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
                counterparty=name or None,
                account_mask=match.group("account"),
                reference_number=match.group("ref"),
                channel="neft",
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
            ),
        )


class YesbankAccountImpsAlertParser(BaseSmsParser):
    """Parse a Yes Bank account IMPS alert that carries the balance.

    Samples (synthetic):
        "INR 12,345.00 credited to YES BANK Ac X0000 on 01JAN26 10:20.
         IMPS:600000000000/Mr SAMPLE NAME. Bal INR 23,456.78."
        "YES BANK Ac X0000 debited for INR 12,345.00 on 01JAN26 10:20.
         IMPS:600000000000/Mr SAMPLE NAME. Bal INR 23,456.78. Not U? ..."

    The body carries the amount, the account mask, the event date and time,
    the IMPS reference, the other party's name and the balance. The bank can
    cut the name short. The parser keeps the name as sent, with any title.
    """

    bank = "yesbank"
    email_type = "yesbank_account_imps_alert"

    _TAIL = (
        r"on\s+(?P<date>\d{2}[A-Za-z]{3}\d{2})\s+(?P<time>\d{2}:\d{2})\.\s+"
        r"IMPS:(?P<ref>\d{12})/(?P<name>.+?)\.\s+"
        r"Bal\s+INR\s+(?P<balance>[\d,]+\.\d{2})\."
    )
    _PATTERNS: tuple[tuple[Literal["credit", "debit"], re.Pattern[str]], ...] = (
        (
            "credit",
            re.compile(
                r"^INR\s+(?P<amount>[\d,]+\.\d{2})\s+credited\s+to\s+YES\s+BANK\s+Ac\s+"
                r"(?P<account>X+\d+)\s+" + _TAIL,
                re.IGNORECASE,
            ),
        ),
        (
            "debit",
            re.compile(
                r"^YES\s+BANK\s+Ac\s+(?P<account>X+\d+)\s+debited\s+for\s+INR\s+"
                r"(?P<amount>[\d,]+\.\d{2})\s+" + _TAIL,
                re.IGNORECASE,
            ),
        ),
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        """Parse one Yes Bank IMPS alert with a balance.

        Args:
            body: The SMS body text.
            sender: The optional TRAI sender ID.
            received_at: The optional UTC arrival time.

        Returns:
            The parsed message with a credit or debit transaction.

        Raises:
            ParseError: If the body does not match the IMPS alert shape.
        """
        text = normalize_whitespace(body)
        found = next(
            (
                (direction, match)
                for direction, pattern in self._PATTERNS
                if (match := pattern.search(text))
            ),
            None,
        )
        if found is None:
            raise ParseError("Yes Bank IMPS alert pattern did not match")
        direction, match = found
        try:
            dt = datetime.datetime.strptime(
                f"{match.group('date')} {match.group('time')}", "%d%b%y %H:%M"
            )
        except ValueError as exc:
            raise ParseError(f"Yes Bank IMPS alert date: {exc}") from exc
        name = match.group("name").strip()
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction=direction,
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=dt.date(),
                transaction_time=dt.time(),
                counterparty=name or None,
                account_mask=match.group("account"),
                reference_number=match.group("ref"),
                channel="imps",
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
            ),
        )


class YesbankAccountImpsRefAlertParser(BaseSmsParser):
    """Parse a Yes Bank account IMPS alert that names only the reference.

    Samples (synthetic):
        "Your a/c no. XXXXXXXX0000 is credited by Rs.12345.00 on 01-01-26
         (IMPS Ref no 600000000000). Warm Regards, YES Bank"
        "Your a/c no. XXXXXXXX0000 is debited for Rs.12345.00 on 01-01-26 and
         a/c XXXXXXXX credited (IMPS Ref no 600000000000). Warm Regards, YES Bank"

    Yes Bank sends this message beside the IMPS alert with the balance. Both
    report one event, and they share the reference. The body has no time, no
    balance and no name. The message arrives within seconds of the transfer,
    so its arrival time gives the time of the event.
    """

    bank = "yesbank"
    email_type = "yesbank_account_imps_ref_alert"
    event_time_source = "message_arrival"

    _PATTERN = re.compile(
        r"^Your\s+a/c\s+no\.\s+(?P<account>X+\d+)\s+is\s+"
        r"(?P<verb>credited\s+by|debited\s+for)\s+Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"on\s+(?P<date>\d{2}-\d{2}-\d{2})\s+(?:and\s+a/c\s+X*\d*\s+credited\s+)?"
        r"\(IMPS\s+Ref\s+no\s+(?P<ref>\d{12})\)",
        re.IGNORECASE,
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        """Parse one Yes Bank IMPS alert with only the reference.

        Args:
            body: The SMS body text.
            sender: The optional TRAI sender ID.
            received_at: The optional UTC arrival time.

        Returns:
            The parsed message with a credit or debit transaction.

        Raises:
            ParseError: If the body does not match the IMPS reference shape.
        """
        text = normalize_whitespace(body)
        if not (match := self._PATTERN.search(text)):
            raise ParseError("Yes Bank IMPS reference pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit"
                if match.group("verb").lower().startswith("credited")
                else "debit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=parse_date(match.group("date")),
                account_mask=match.group("account"),
                reference_number=match.group("ref"),
                channel="imps",
            ),
        )


class YesbankServiceInfoStubParser(BaseSmsParser):
    """Recognize and skip a Yes Bank service SMS.

    Samples (synthetic):
        "Your attempt to login in YES ONLINE has failed on 01-Jan-2026
         10:20:30 AM IST. ..."
        "Recipient SAMPLE with A/c no ending 0000 is added on 01-Jan-2026
         10:20:30 AM IST. ..."

    These messages report a login, a payee, a card or an account setting.
    They move no money. Each pattern names a whole service phrase, so it
    cannot match a transaction alert.
    """

    bank = "yesbank"
    email_type = "yesbank_service_info_stub"

    _PATTERNS: tuple[re.Pattern[str], ...] = tuple(
        re.compile(pattern, re.IGNORECASE)
        for pattern in (
            r"^Limited\s+fund\s+transfer\s+can\s+be\s+made\s+to\s+recipient\b",
            r"^Transfer\s+funds\s+up\s+to\s+daily\s+permissible\s+limit\s+to\s+"
            r"recipient\s+.+?\s+successfully\s+added\s+on\b",
            r"^Recipient\s+.+?\s+with\s+A/c\s+no\s+ending\s+\d+\s+is\s+added\s+on\b",
            r"^Your\s+attempt\s+to\s+login\s+in\s+YES\s+ONLINE\s+has\s+failed\b",
            r"^Your\s+registration\s+for\s+YES\s+Online\s+is\s+successful\b",
            r"^Your\s+security\s+Q\s*&\s*A\s+are\s+set\s+successfully\b",
            r"\bYES\s+BANK\s+Debit\s+Card\s+token\s+ending\s+with\s+\d+\s+"
            r"has\s+been\s+activated\b",
            r"\bactivate\s+your\s+YES\s+BANK\s+Credit\s+Card\s+within\s+\d+\s+days\b",
            r"\brequest\s+for\s+E-statements\s+for\s+your\s+YES\s+BANK\s+Customer\s+ID\b",
            r"\bYES\s+BANK\s+Saving\s+Account\s+number\s+\d+\s+is\s+now\s+operational\b",
            r"^Thank\s+You\s+for\s+opening\s+an\s+account\s+with\s+YES\s+BANK\b",
            r"\bnominee\s+details\s+have\s+been\s+updated\s+successfully\b",
        )
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        """Recognize one Yes Bank service SMS.

        Args:
            body: The SMS body text.
            sender: The optional TRAI sender ID.
            received_at: The optional UTC arrival time.

        Returns:
            Never returns.

        Raises:
            ParserStubError: If the body is a known service SMS.
            ParseError: If the body is not a known service SMS.
        """
        text = normalize_whitespace(body)
        if any(pattern.search(text) for pattern in self._PATTERNS):
            raise ParserStubError(
                "yesbank_service_info_stub: recognized Yes Bank service SMS; "
                "it moves no money, so it is intentionally not parsed"
            )
        raise ParseError("Yes Bank service info: no known service phrase")


_PARSERS: tuple[BaseSmsParser, ...] = (
    YesbankAccountChequeDepositAlertParser(),
    YesbankAccountRtgsDebitAlertParser(),
    YesbankAccountNeftCreditAlertParser(),
    YesbankAccountImpsAlertParser(),
    YesbankAccountImpsRefAlertParser(),
    # The stub goes last, so it never hides a transaction parser.
    YesbankServiceInfoStubParser(),
)


class YesbankParser(BankSmsParser):
    bank = "yesbank"
    parsers = _PARSERS


def parse(
    body: str,
    *,
    sender: str | None = None,
    received_at: datetime.datetime | None = None,
) -> ParsedSms:
    """Parse a Yes Bank SMS body.

    Args:
        body: The SMS body text.
        sender: The optional TRAI sender ID.
        received_at: The optional UTC arrival time.

    Returns:
        The parsed message.

    Raises:
        ParseError: If no Yes Bank parser matches the body.
    """
    return YesbankParser().parse(body, sender=sender, received_at=received_at)
