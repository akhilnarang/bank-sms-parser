"""IDFC FIRST Bank SMS parsers."""

import datetime
import re

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BankSmsParser, BaseSmsParser
from bank_sms_parser.parsing import (
    normalize_whitespace,
    parse_amount,
    parse_date,
    parse_datetime,
)


class IdfcCcPaymentReceivedParser(BaseSmsParser):
    """IDFC FIRST Wealth CC bill-payment-received notification.

    Sample:
        "Thank you for payment of INR 3,000.00 towards your
         FIRST Wealth Credit Card XX0000 on 02 May 2026. IDFC FIRST Bank"
    """

    bank = "idfc"
    email_type = "idfc_cc_payment_received_alert"

    _PATTERN = re.compile(
        r"Thank\s+you\s+for\s+payment\s+of\s+INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"towards\s+your\s+FIRST\s+Wealth\s+Credit\s+Card\s+(?P<card>XX\d+)\s+"
        r"on\s+(?P<date>\d{1,2}\s+\w+\s+\d{4})"
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
            raise ParseError("IDFC CC payment-received pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                card_mask=match.group("card"),
            ),
        )


class IdfcAccountBalanceDebitAlertParser(BaseSmsParser):
    """IDFC FIRST account debit alert with balance and in-body timestamp."""

    bank = "idfc"
    email_type = "idfc_account_balance_debit_alert"

    _PATTERN = re.compile(
        r"Your\s+A/C\s+(?P<account>X+\d+)\s+is\s+debited\s+by\s+INR\s+"
        r"(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"on\s+(?P<date>\d{2}/\d{2}/\d{2})\s+(?P<time>\d{1,2}:\d{2})\.\s*"
        r"New\s+Bal\s*:\s*INR\s+(?P<balance>[\d,]+(?:\.\d+)?)"
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
            raise ParseError("IDFC account balance debit pattern did not match")
        txn_dt = parse_datetime(f"{match.group('date')} {match.group('time')}")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=txn_dt.date(),
                transaction_time=txn_dt.time(),
                balance=Money(amount=parse_amount(match.group("balance")), currency="INR"),
                account_mask=match.group("account"),
            ),
        )


class IdfcAccountTransactionAlertParser(BaseSmsParser):
    """IDFC FIRST savings/current-account debit alert.

    Three cosmetic body shapes share this event type:

    1) Debit-card POS/online spend (anchored on ``Spent Rs.X from A/C``):
        "Spent Rs.2,448.00 from A/C XX0000 at INSTAMART on 04/05/26.
         Not you? Call 180010888/SMS BLOCK ... IDFC FIRST Bank"
        ``channel="card"``; counterparty=merchant; no RRN; no balance.

    2) UPI debit (anchored on ``Your A/c ... debited by Rs.``):
        "Your A/c XX0000 debited by Rs. 20,000.00 on 09/05/26;
         <Name> credited. RRN 000000000000. Available balance
         Rs. 16,442.65. Team IDFC FIRST Bank"
        ``channel="upi"`` (RRN sequence is UPI per IDFC convention);
        counterparty=recipient name; reference=RRN;
        balance=Available balance.

    3) Generic debit anchored on ``Your A/C ... is debited by INR``
       carrying an in-body DD/MM/YY date + 24-hour time and a
       ``New Bal :INR ...`` trailer; no merchant, no reference;
       ``channel`` stays ``None`` because the body carries no rail
       marker. The debit-direction counterpart of
       ``IdfcAccountCreditAlertParser._GENERIC_CREDIT_PATTERN``:
        "Your A/C XXXXX000 is debited by INR 1,234.00 on 16/05/26
         09:30. New Bal :INR 0.00. Call us on 180010888 for dispute.
         Team IDFC FIRST Bank"

    Each regex is anchored on its discriminating clause so the shapes
    cannot accidentally match each other.
    """

    bank = "idfc"
    email_type = "idfc_account_transaction_alert"

    _SPEND_CARD_PATTERN = re.compile(
        r"Spent\s+Rs\.(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"from\s+A/C\s+(?P<account>XX\d+)\s+"
        r"at\s+(?P<merchant>.+?)\s+"
        r"on\s+(?P<date>\d{2}/\d{2}/\d{2})"
    )

    _UPI_DEBIT_PATTERN = re.compile(
        r"Your\s+A/c\s+(?P<account>XX\d+)\s+debited\s+by\s+"
        r"Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"on\s+(?P<date>\d{2}/\d{2}/\d{2})\s*;\s*"
        r"(?P<payee>.+?)\s+credited\.\s*"
        r"RRN\s+(?P<ref>\d+)\.\s*"
        r"Available\s+balance\s+Rs\.\s*(?P<balance>[\d,]+(?:\.\d+)?)"
    )

    _GENERIC_DEBIT_PATTERN = re.compile(
        r"Your\s+A/C\s+(?P<account>X+\d+)\s+is\s+debited\s+by\s+INR\s+"
        r"(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"on\s+(?P<date>\d{2}/\d{2}/\d{2})\s+(?P<time>\d{1,2}:\d{2})\.\s*"
        r"New\s+Bal\s*:\s*INR\s+(?P<balance>[\d,]+(?:\.\d+)?)"
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        text = normalize_whitespace(body)

        if match := self._SPEND_CARD_PATTERN.search(text):
            return self._build(
                match,
                counterparty=match.group("merchant").strip(),
                channel="card",
            )

        if match := self._UPI_DEBIT_PATTERN.search(text):
            return self._build(
                match,
                counterparty=match.group("payee").strip(),
                channel="upi",
                reference_number=match.group("ref"),
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
            )

        if match := self._GENERIC_DEBIT_PATTERN.search(text):
            txn_dt = parse_datetime(f"{match.group('date')} {match.group('time')}")
            return ParsedSms(
                email_type=self.email_type,
                bank=self.bank,
                transaction=SmsTransactionAlert(
                    direction="debit",
                    amount=Money(
                        amount=parse_amount(match.group("amount")), currency="INR"
                    ),
                    transaction_date=txn_dt.date(),
                    transaction_time=txn_dt.time(),
                    balance=Money(
                        amount=parse_amount(match.group("balance")), currency="INR"
                    ),
                    account_mask=match.group("account"),
                ),
            )

        raise ParseError(
            "IDFC account transaction alert: no known pattern matched "
            "(tried card spend, UPI debit, generic debit)"
        )

    def _build(
        self,
        match: re.Match[str],
        *,
        counterparty: str,
        channel: str,
        reference_number: str | None = None,
        balance: Money | None = None,
    ) -> ParsedSms:
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                counterparty=counterparty,
                reference_number=reference_number,
                channel=channel,
                account_mask=match.group("account"),
                balance=balance,
            ),
        )


class IdfcAccountRtgsDebitAlertParser(BaseSmsParser):
    """IDFC FIRST account outward RTGS debit alert.

    Sample:
        "Your A/c XXXXXXX0000 has been debited by Rs. 200,000.00 on
         05-06-2026. Info: RTGS/ IDFBR60000000000000000/SAMPLE NAME.
         New bal: Rs. 99,999.99. Team IDFC FIRST Bank"

    The ``Info: RTGS/ <ref>/<name>`` clause carries the RTGS reference and
    the beneficiary name (surfaced as counterparty). ``channel="rtgs"``.
    """

    bank = "idfc"
    email_type = "idfc_account_rtgs_debit_alert"

    _PATTERN = re.compile(
        r"Your\s+A/c\s+(?P<account>X+\d+)\s+has\s+been\s+debited\s+by\s+"
        r"Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"on\s+(?P<date>\d{2}-\d{2}-\d{4})\.\s*"
        r"Info:\s*RTGS/\s*(?P<ref>\S+?)/(?P<name>.+?)\.\s*"
        r"New\s+bal:\s*Rs\.\s*(?P<balance>[\d,]+(?:\.\d+)?)"
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
            raise ParseError("IDFC account RTGS debit pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                counterparty=match.group("name").strip(),
                reference_number=match.group("ref"),
                channel="rtgs",
                balance=Money(amount=parse_amount(match.group("balance")), currency="INR"),
                account_mask=match.group("account"),
            ),
        )


class IdfcAccountImpsOutwardAlertParser(BaseSmsParser):
    """IDFC FIRST account outward IMPS debit alert.

    Sample:
        "Your a/c ending XXXXXXXX000 is debited by Rs. 15000.00 on
         01-Jun-26 and a/c ending XXXXXXXXX000 credited (IMPS Ref no
         000000000000 ). Team IDFC FIRST Bank"

    The user's account is debited and a destination account is credited
    via IMPS, so ``direction`` is ``debit`` and ``channel`` is ``imps``.
    Discriminators vs the bank's other debit shapes:

    - source mask is introduced by ``a/c ending <digits>`` (bare digits,
      no ``XX`` prefix) — unlike ``IdfcAccountTransactionAlertParser``'s
      ``A/C XX####`` / ``A/c XX####`` forms;
    - the ``and a/c ending <digits> credited`` clause names the
      destination account (no payee name), surfaced as the counterparty;
    - the ``(IMPS Ref no <digits>)`` trailer (note: no period, unlike the
      credit shape's ``IMPS Ref no. ...``) carries the reference.

    The account masks are kept verbatim (the leading ``X``s are part of
    the bank's masking, the trailing digits are the visible tail).
    """

    bank = "idfc"
    email_type = "idfc_account_imps_outward_alert"

    _PATTERN = re.compile(
        r"Your\s+a/c\s+ending\s+(?P<account>[X\d]+)\s+is\s+debited\s+by\s+"
        r"Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"on\s+(?P<date>\d{1,2}-[A-Za-z]+-\d{2,4})\s+"
        r"and\s+a/c\s+ending\s+(?P<dest>[X\d]+)\s+credited\s*"
        r"\(IMPS\s+Ref\s+no\.?\s+(?P<ref>\d+)\s*\)"
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
            raise ParseError("IDFC account outward IMPS pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                counterparty=f"Acct {match.group('dest')}",
                reference_number=match.group("ref"),
                channel="imps",
                account_mask=match.group("account"),
            ),
        )


class IdfcAccountImpsCreditAlertParser(BaseSmsParser):
    """IDFC FIRST account IMPS credit from a mobile-linked account."""

    bank = "idfc"
    email_type = "idfc_account_imps_credit_alert"

    _PATTERN = re.compile(
        r"Your\s+a/c\s+no\.\s+(?P<account>X+\d+)\s+is\s+credited\s+by\s+"
        r"Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"on\s+(?P<date>\d{1,2}-[A-Za-z]+-\d{2,4})\s+"
        r"by\s+a/c\s+linked\s+to\s+mobile\s+(?P<mobile>X+\d+)\s*"
        r"\(IMPS\s+Ref\s+no\.?\s+(?P<ref>\d+)\s*\)"
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
            raise ParseError("IDFC account IMPS credit pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                counterparty=f"Mobile {match.group('mobile')}",
                reference_number=match.group("ref"),
                channel="imps",
                account_mask=match.group("account"),
            ),
        )


class IdfcAccountBalanceCreditAlertParser(BaseSmsParser):
    """IDFC FIRST account credit alert with balance and in-body timestamp."""

    bank = "idfc"
    email_type = "idfc_account_balance_credit_alert"

    _PATTERN = re.compile(
        r"Your\s+A/C\s+(?P<account>X+\d+)\s+is\s+credited\s+with\s+INR\s+"
        r"(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"on\s+(?P<date>\d{2}/\d{2}/\d{2})\s+(?P<time>\d{1,2}:\d{2})\.\s*"
        r"Your\s+new\s+balance\s+is\s+INR\s+(?P<balance>[\d,]+(?:\.\d+)?)"
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
            raise ParseError("IDFC account balance credit pattern did not match")
        txn_dt = parse_datetime(f"{match.group('date')} {match.group('time')}")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=txn_dt.date(),
                transaction_time=txn_dt.time(),
                balance=Money(amount=parse_amount(match.group("balance")), currency="INR"),
                account_mask=match.group("account"),
            ),
        )


class IdfcAccountCreditAlertParser(BaseSmsParser):
    """IDFC FIRST savings/current-account inbound credit alert.

    Two cosmetic body shapes share this event type:

    1) IMPS credit anchored on ``credited by Rs.`` with a mobile-linked
       remitter and an ``(IMPS Ref no ...)`` trailer; ``channel="imps"``,
       counterparty=originator's masked mobile, reference=IMPS ref:
        "Your a/c no. XXXXXXXX669 is credited by Rs. 50000.00 on
         02-May-26 by a/c linked to mobile XXXXXXXXX000
         (IMPS Ref no 000000000000 ). Team IDFC FIRST Bank"

    2) Generic credit anchored on ``credited with INR`` carrying an
       in-body DD/MM/YY date + 24-hour time and a ``Your new balance is
       INR ...`` trailer; no remitter or reference; ``channel`` stays
       ``None`` because the body carries no rail marker:
        "Your A/C XXXXX000 is credited with INR 1,234.00 on
         16/05/26 09:30. Your new balance is INR 9,99,999.99.
         Team IDFC FIRST Bank"
    """

    bank = "idfc"
    email_type = "idfc_account_credit_alert"

    _IMPS_CREDIT_PATTERN = re.compile(
        r"Your\s+a/c\s+no\.\s+(?P<account>X+\d+)\s+is\s+credited\s+by\s+"
        r"Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"on\s+(?P<date>\d{1,2}-[A-Za-z]+-\d{2,4})\s+"
        r"by\s+a/c\s+linked\s+to\s+mobile\s+(?P<mobile>X+\d+)\s*"
        r"\(IMPS\s+Ref\s+no\.?\s+(?P<ref>\d+)\s*\)"
    )

    _GENERIC_CREDIT_PATTERN = re.compile(
        r"Your\s+A/C\s+(?P<account>X+\d+)\s+is\s+credited\s+with\s+INR\s+"
        r"(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"on\s+(?P<date>\d{2}/\d{2}/\d{2})\s+(?P<time>\d{1,2}:\d{2})\.\s*"
        r"Your\s+new\s+balance\s+is\s+INR\s+(?P<balance>[\d,]+(?:\.\d+)?)"
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        text = normalize_whitespace(body)

        if match := self._IMPS_CREDIT_PATTERN.search(text):
            return ParsedSms(
                email_type=self.email_type,
                bank=self.bank,
                transaction=SmsTransactionAlert(
                    direction="credit",
                    amount=Money(
                        amount=parse_amount(match.group("amount")), currency="INR"
                    ),
                    transaction_date=parse_date(match.group("date")),
                    counterparty=f"Mobile {match.group('mobile')}",
                    reference_number=match.group("ref"),
                    channel="imps",
                    account_mask=match.group("account"),
                ),
            )

        if match := self._GENERIC_CREDIT_PATTERN.search(text):
            txn_dt = parse_datetime(f"{match.group('date')} {match.group('time')}")
            return ParsedSms(
                email_type=self.email_type,
                bank=self.bank,
                transaction=SmsTransactionAlert(
                    direction="credit",
                    amount=Money(
                        amount=parse_amount(match.group("amount")), currency="INR"
                    ),
                    transaction_date=txn_dt.date(),
                    transaction_time=txn_dt.time(),
                    balance=Money(
                        amount=parse_amount(match.group("balance")), currency="INR"
                    ),
                    account_mask=match.group("account"),
                ),
            )

        raise ParseError(
            "IDFC account credit alert: no known pattern matched "
            "(tried IMPS credit, generic credit)"
        )


_PARSERS: tuple[BaseSmsParser, ...] = (
    IdfcCcPaymentReceivedParser(),
    IdfcAccountBalanceDebitAlertParser(),
    IdfcAccountTransactionAlertParser(),
    IdfcAccountRtgsDebitAlertParser(),
    # Outward IMPS debit: anchored on "a/c ending <digits> ... debited ...
    # (IMPS Ref no ...)". Its "a/c ending <bare digits>" mask form is
    # distinct from the transaction parser's "A/c XX####", so order is not
    # load-bearing.
    IdfcAccountImpsOutwardAlertParser(),
    IdfcAccountImpsCreditAlertParser(),
    IdfcAccountBalanceCreditAlertParser(),
    IdfcAccountCreditAlertParser(),
)


class IdfcParser(BankSmsParser):
    bank = "idfc"
    parsers = _PARSERS


def parse(body: str, *, sender: str | None = None, received_at: datetime.datetime | None = None) -> ParsedSms:
    return IdfcParser().parse(body, sender=sender, received_at=received_at)
