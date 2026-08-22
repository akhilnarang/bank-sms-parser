"""ICICI account-level SMS parser (savings/checking IMPS/NEFT/UPI debit/credit)."""

import datetime
import re
from typing import NamedTuple

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BaseSmsParser
from bank_sms_parser.parsing import (
    normalize_whitespace,
    parse_amount,
    parse_date,
    parse_datetime,
)


class _InfoFields(NamedTuple):
    """Fields extracted from an ICICI ``Info`` descriptor."""

    channel: str | None
    reference_number: str | None
    counterparty: str | None


# Maps a rail token found in an ``Info`` descriptor to a channel slug. The
# descriptor is the narration ICICI puts after ``Info``; its prefix names the
# rail (``RTGS*ICICR120``, ``RTGS-HDFCR5...-``, ``BIL*INFT*<ref>*``).
# ``INFT`` is ICICI's internal-funds-transfer marker, surfaced as imps.
_INFO_CHANNELS = {
    "RTGS": "rtgs",
    "NEFT": "neft",
    "IMPS": "imps",
    "INFT": "imps",
    "UPI": "upi",
}

# A clear reference token: an alphanumeric run with at least one letter and one
# digit (e.g. ICICR000, HDFCR0000000000, FFF0000000), 6+ chars. This avoids
# scraping plain words ("TRF", "TO", "FD") or the boilerplate
# dispute/BLOCK numbers as a reference.
_REF_TOKEN = re.compile(r"\b(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*\d)[A-Z0-9]{6,}\b")

# An NEFT descriptor contains the rail, reference, and sender name.
_NEFT_INFO = re.compile(
    r"^NEFT-(?P<ref>(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*\d)[A-Z0-9]{6,})-"
    r"(?P<counterparty>.+)$",
    re.IGNORECASE,
)

# A transfer into a fixed deposit ("TRF TO FD no."). The counterparty is the
# deposit itself, so label it "ICICI FD"; the downstream categorizer reads it as
# an investment. Anchored to the leading boilerplate so a rail descriptor whose
# name segment merely contains "to fd" (e.g. an NEFT sender) is not caught.
_FD_INFO = re.compile(r"^\s*TRF\s+TO\s+FD\b", re.IGNORECASE)
_FD_LABEL = "ICICI FD"


def _classify_info(descriptor: str) -> _InfoFields:
    """Extract the channel, reference, and counterparty from ``Info`` text.

    The channel comes from a known rail token. The reference is the first
    clear alphanumeric reference token. A transfer to a fixed deposit becomes
    "ICICI FD". For ``NEFT-<reference>-<sender>`` text, the sender is the
    counterparty. For other formats, the full descriptor is the counterparty.
    """
    segments = re.split(r"[\s*\-]", descriptor.strip())
    channel: str | None = None
    for segment in segments:
        if segment.upper() in _INFO_CHANNELS:
            channel = _INFO_CHANNELS[segment.upper()]
            break
    ref_match = _REF_TOKEN.search(descriptor)
    reference_number = ref_match.group(0) if ref_match else None
    counterparty = descriptor.strip() or None
    if _FD_INFO.search(descriptor):
        counterparty = _FD_LABEL
    elif neft_match := _NEFT_INFO.fullmatch(descriptor.strip()):
        reference_number = neft_match.group("ref")
        counterparty = neft_match.group("counterparty").strip()
    return _InfoFields(
        channel=channel,
        reference_number=reference_number,
        counterparty=counterparty,
    )


class IciciAccountTransactionAlertParser(BaseSmsParser):
    """ICICI account-level transaction alert (debit via IMPS or UPI)."""

    bank = "icici"
    email_type = "icici_account_transaction_alert"

    _DEBIT_IMPS_PATTERN = re.compile(
        r"ICICI\s+Bank\s+Acct\s+(?P<account>XX\d+)\s+debited\s+with\s+"
        r"Rs\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+on\s+(?P<date>\d{2}-\w+-\d{2})\s+"
        r"&\s+Acct\s+(?P<dest>XX\d+)\s+credited\.IMPS:(?P<ref>\d+)"
    )

    _DEBIT_UPI_PATTERN = re.compile(
        r"ICICI\s+Bank\s+Acct\s+(?P<account>XX\d+)\s+debited\s+for\s+"
        r"Rs\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+on\s+(?P<date>\d{2}-\w+-\d{2})\s*;\s*"
        r"(?P<payee>.+?)\s+credited\.\s*UPI:(?P<ref>\d+)"
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        text = normalize_whitespace(body)

        if match := self._DEBIT_IMPS_PATTERN.search(text):
            return self._build(
                match,
                counterparty=f"Acct {match.group('dest')}",
                channel="imps",
            )

        if match := self._DEBIT_UPI_PATTERN.search(text):
            return self._build(
                match,
                counterparty=match.group("payee").strip(),
                channel="upi",
            )

        raise ParseError(
            "ICICI account transaction alert: no known pattern matched "
            "(tried IMPS debit, UPI debit)"
        )

    def _build(
        self,
        match: re.Match[str],
        *,
        counterparty: str,
        channel: str,
    ) -> ParsedSms:
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                counterparty=counterparty,
                reference_number=match.group("ref"),
                channel=channel,
                account_mask=match.group("account"),
            ),
        )


class IciciAccountUpiCreditAlertParser(BaseSmsParser):
    """ICICI account UPI credit alert without an available-balance field."""

    bank = "icici"
    email_type = "icici_account_upi_credit_alert"

    _PATTERN = re.compile(
        r"Dear\s+Customer,\s+Acct\s+(?P<account>XX\d+)\s+"
        r"is\s+credited\s+with\s+Rs\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"on\s+(?P<date>\d{1,2}-\w+-\d{2})\s+"
        r"from\s+(?P<payer>.+?)\.\s+UPI:(?P<ref>\d+)-ICICI\s+Bank\."
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
            raise ParseError("ICICI account UPI credit pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                counterparty=match.group("payer").strip(),
                reference_number=match.group("ref"),
                channel="upi",
                account_mask=match.group("account"),
            ),
        )


class IciciAccountImpsCreditAlertParser(BaseSmsParser):
    """ICICI account IMPS credit from a mobile-linked account.

    Sample:
        "ICICI Bank Account XX000 is credited with Rs 15,000.00 on
         01-Jun-26 by Account linked to mobile number XXXXX00000.
         IMPS Ref. no. 000000000000."

    Discriminators vs ``IciciAccountUpiCreditAlertParser``:
    - leading ``ICICI Bank Account`` (UPI shape opens with
      ``Dear Customer, Acct``);
    - remitter is ``Account linked to mobile number <masked>`` rather
      than a named payer;
    - trailing ``IMPS Ref. no. <digits>.`` (the UPI shape uses
      ``UPI:<digits>-ICICI Bank.``).

    ``channel`` is ``imps``; the masked mobile is surfaced as the
    counterparty (``Mobile XXXXX####``), mirroring the IDFC IMPS-credit
    parser's convention.
    """

    bank = "icici"
    email_type = "icici_account_imps_credit_alert"

    _PATTERN = re.compile(
        r"ICICI\s+Bank\s+Account\s+(?P<account>XX\d+)\s+is\s+credited\s+with\s+"
        r"Rs\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"on\s+(?P<date>\d{1,2}-\w+-\d{2,4})\s+"
        r"by\s+Account\s+linked\s+to\s+mobile\s+number\s+(?P<mobile>X+\d+)\.\s*"
        r"IMPS\s+Ref\.?\s+no\.?\s+(?P<ref>\d+)"
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
            raise ParseError("ICICI account IMPS credit pattern did not match")
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


class IciciAccountDebitInfoAlertParser(BaseSmsParser):
    """ICICI account outward debit carrying an ``Info`` narration + ``Avl Bal``.

    Sample:
        "ICICI Bank Acc XX000 debited Rs. 12,345.00 on 11-Jun-26
         InfoRTGS*ICICR000.Avl Bal Rs. 0.00.To dispute call 18002662 or
         SMS BLOCK 000 to 9215676766"

    Discriminators vs ``IciciAccountTransactionAlertParser`` ("ICICI Bank
    Acct ... debited with/for ..."):
    - opens with ``ICICI Bank Acc`` (no ``t``) then ``debited Rs.``;
    - the narration sits in an ``Info<descriptor>`` clause terminated by
      ``.Avl Bal Rs. <balance>``.

    ``_classify_info`` extracts the counterparty, channel, and reference. The
    pattern stops before the dispute text. Thus, the dispute text cannot be
    part of these fields.
    """

    bank = "icici"
    email_type = "icici_account_debit_info_alert"

    _PATTERN = re.compile(
        r"ICICI\s+Bank\s+Acc\s+(?P<account>XX\d+)\s+debited\s+"
        r"Rs\.?\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+on\s+(?P<date>\d{1,2}-\w+-\d{2,4})\s+"
        r"Info(?P<info>.*?)\.\s*Avl\s+Bal\s+"
        r"Rs\.?\s*(?P<balance>[\d,]+(?:\.\d+)?)"
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
            raise ParseError("ICICI account debit Info pattern did not match")
        descriptor = match.group("info").strip()
        info = _classify_info(descriptor)
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                counterparty=info.counterparty,
                reference_number=info.reference_number,
                channel=info.channel,
                account_mask=match.group("account"),
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
            ),
        )


class IciciAccountCreditInfoAlertParser(BaseSmsParser):
    """ICICI account inward credit carrying an ``Info`` narration + balance.

    Sample:
        "ICICI Bank Account XX000 credited:Rs. 70,000.00 on 11-Jun-26.
         Info BIL*INFT*FFF0000000*. Available Balance is Rs. 70,000.00."

    Discriminators vs the UPI/IMPS credit shapes ("... is credited with
    Rs ..."):
    - ``credited:Rs.`` colon form;
    - the narration sits in an ``Info <descriptor>`` clause followed by
      ``Available Balance is Rs. <balance>``.

    ``_classify_info`` extracts the counterparty, channel, and reference. For
    an NEFT descriptor, the counterparty is the sender name after the
    reference.
    """

    bank = "icici"
    email_type = "icici_account_credit_info_alert"

    _PATTERN = re.compile(
        r"ICICI\s+Bank\s+Account\s+(?P<account>XX\d+)\s+credited:\s*"
        r"Rs\.?\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+on\s+"
        r"(?P<date>\d{1,2}-\w+-\d{2,4})\.\s*"
        r"Info\s+(?P<info>.*?)\.\s*Available\s+Balance\s+is\s+"
        r"Rs\.?\s*(?P<balance>[\d,]+(?:\.\d+)?)"
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
            raise ParseError("ICICI account credit Info pattern did not match")
        descriptor = match.group("info").strip()
        info = _classify_info(descriptor)
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                counterparty=info.counterparty,
                reference_number=info.reference_number,
                channel=info.channel,
                account_mask=match.group("account"),
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
            ),
        )


class IciciAccountMandateDebitAlertParser(BaseSmsParser):
    """ICICI recurring-mandate execution debit.

    A successfully redeemed mandate is the completed money movement, not a
    mandate-registration or reminder message. The template carries the debit
    amount, merchant, execution date, and RRN, but omits the account mask.
    Requiring the complete ``raised by ... successfully redeemed through RRN``
    frame prevents generic mandate notices from being treated as transactions.
    """

    bank = "icici"
    email_type = "icici_account_mandate_debit_alert"

    _PATTERN = re.compile(
        r"Dear\s+Customer,\s+the\s+mandate\s+of\s+INR\s+"
        r"(?P<amount>[\d,]+(?:\.\d+)?)\s+raised\s+by\s+(?P<merchant>.+?)\s+"
        r"on\s+(?P<date>\d{1,2}-\w+-\d{2,4})\s+and\s+is\s+successfully\s+"
        r"redeemed\s+through\s+RRN\s+(?P<ref>\d+)\s+-ICICI\s+Bank\.?$",
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
            raise ParseError("ICICI account mandate-debit pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                counterparty=match.group("merchant").strip(),
                reference_number=match.group("ref"),
                channel="emandate",
            ),
        )


class IciciAccountNeftCompletionAlertParser(BaseSmsParser):
    """ICICI outward-NEFT settlement confirmation carrying the full UTR.

    Sample:
        "ICICI BANK NEFT Transaction with reference number IN00000000000000
         for Rs. 2,500.00 has been credited to the beneficiary account on
         21-08-2026 at 15:02:16"

    ICICI's account-debit alert for an outward NEFT
    (``IciciAccountDebitInfoAlertParser``) truncates the UTR in its ``Info
    BIL*NEFT*...`` narration, so that row records the account but no usable
    reference. This later confirmation carries the **full** UTR and the exact
    time. It is the settlement of the same debit — direction ``debit`` (money
    left the user), ``channel="neft"`` — and names no source account.

    Declares ``ledger_role="completion"``: it opens no ledger row of its own.
    The consumer stamps this UTR onto the unique prior ICICI NEFT debit (which
    still lacks a reference) so the transfer can pair with its credit leg.
    """

    bank = "icici"
    email_type = "icici_account_neft_completion_alert"

    _PATTERN = re.compile(
        r"ICICI\s+BANK\s+NEFT\s+Transaction\s+with\s+reference\s+number\s+"
        r"(?P<ref>[A-Z0-9]+)\s+for\s+Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"has\s+been\s+credited\s+to\s+the\s+beneficiary\s+account\s+"
        r"on\s+(?P<date>\d{1,2}-\d{1,2}-\d{4})\s+at\s+(?P<time>\d{1,2}:\d{2}:\d{2})\s*$",
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
            raise ParseError("ICICI NEFT completion pattern did not match")
        dt = parse_datetime(f"{match.group('date')} {match.group('time')}")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            # Supplies the UTR the account-debit alert truncated; opens no row
            # of its own. See bank_sms_parser ParsedSms.ledger_role.
            ledger_role="completion",
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=dt.date(),
                transaction_time=dt.time(),
                reference_number=match.group("ref"),
                channel="neft",
            ),
        )
