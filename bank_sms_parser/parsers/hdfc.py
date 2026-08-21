"""HDFC Bank SMS parsers.

Supported SMS types:
- hdfc_dc_transaction_alert: Debit-card POS/online spend
- hdfc_dc_reversal_alert: Debit-card transaction reversal (credit back)
- hdfc_cc_transaction_alert: Credit-card POS/online spend
- hdfc_cc_reversal_alert: Credit-card transaction reversal (credit back)
- hdfc_cc_refund_alert: Credit-card refund credit
- hdfc_cc_payment_received_alert: Credit-card bill-payment credit
- hdfc_account_transaction_alert: Savings account IMPS credit
- hdfc_account_credit_alert: Savings account inbound credit ("Update! INR ... deposited ..."); FT- and NEFT Cr- variants
- hdfc_account_imps_outward_alert: Savings account outward IMPS debit
- hdfc_account_upi_debit_alert: Savings account UPI debit ("Sent Rs.X From HDFC Bank A/C *...")
- hdfc_account_upi_credit_alert: Savings account UPI credit
- hdfc_cc_smartpay_bbps_alert: SmartPay BBPS bill auto-debit on CC
- hdfc_account_transfer_debit_alert: Savings-to-PPF/SSY transfer debit
- hdfc_account_neft_debit_alert: Savings account outward NEFT debit
- hdfc_account_rtgs_debit_alert: Savings account outward RTGS debit ("RTGS txn initiated")
- hdfc_account_online_transfer_debit_alert: Savings account net-banking payee transfer debit ("Money Transfer", no rail named)
"""

import datetime
import re
from typing import Literal

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BankSmsParser, BaseSmsParser
from bank_sms_parser.parsing import (
    normalize_whitespace,
    parse_amount,
    parse_date,
    parse_datetime,
    received_at_to_ist,
)


class HdfcDcTransactionAlertParser(BaseSmsParser):
    """HDFC debit-card spend alert.

    Sample:
        "Spent Rs.3000 From HDFC Bank Card x0000 At MERCHANT On
         2026-05-02:00:17:56 Bal Rs.142.26 Not You? Call ..."
    """

    bank = "hdfc"
    email_type = "hdfc_dc_transaction_alert"

    _PATTERN = re.compile(
        r"Spent\s+Rs\.(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"From\s+HDFC\s+Bank\s+Card\s+(?P<card>x\d+)\s+"
        r"At\s+(?P<merchant>.+?)\s+"
        r"On\s+(?P<datetime>\d{4}-\d{2}-\d{2}:\d{2}:\d{2}:\d{2})\s+"
        r"Bal\s+Rs\.(?P<balance>[\d,]+(?:\.\d+)?)"
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
            raise ParseError("HDFC DC transaction alert pattern did not match")
        dt = parse_datetime(match.group("datetime"))
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
                counterparty=match.group("merchant"),
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
                card_mask=match.group("card"),
                channel="card",
            ),
        )


class HdfcDcReversalAlertParser(BaseSmsParser):
    """HDFC debit-card transaction reversal alert.

    Sample (single line; note the missing space after "Reversed!"):
        "Transaction Reversed!On HDFC Bank DEBIT/ATM Card xx0000 Amt:
         Rs.2 By PAYZAPP0000000 On 2026-06-01:13:21:20"

    A reversal returns money to the debit-card account (e.g. a failed or
    refunded card/PayZapp transaction), so ``direction`` is ``credit``.
    The ``By <token>`` clause is the reversing merchant/acquirer
    (``counterparty``); the colon-separated datetime is the reversal
    time. The card mask uses HDFC's lowercase ``xx####`` form and is kept
    verbatim.

    The pattern tolerates the missing space between ``Reversed!`` and
    ``On`` seen in real bodies (``Reversed!On``); ``normalize_whitespace``
    does not insert one, so ``\\s*`` allows zero-or-more.
    """

    bank = "hdfc"
    email_type = "hdfc_dc_reversal_alert"

    _PATTERN = re.compile(
        r"Transaction\s+Reversed!\s*"
        r"On\s+HDFC\s+Bank\s+DEBIT/ATM\s+Card\s+(?P<card>xx\d+)\s+"
        r"Amt:\s*Rs\.(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"By\s+(?P<merchant>.+?)\s+"
        r"On\s+(?P<datetime>\d{4}-\d{2}-\d{2}:\d{2}:\d{2}:\d{2})"
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
            raise ParseError("HDFC DC reversal alert pattern did not match")
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
                counterparty=match.group("merchant").strip(),
                card_mask=match.group("card"),
                channel="card",
            ),
        )


class HdfcCcReversalAlertParser(BaseSmsParser):
    """HDFC credit-card transaction reversal alert.

    Sample (single line; note the missing space after "Reversed!"):
        "Transaction Reversed!On HDFC Bank CREDIT Card xx0000 Amt:
         Rs.2 By PAYZAPP0000000 On 2026-07-06:17:23:32"

    Same "Transaction Reversed!" template family as the debit-card
    reversal, but on the CREDIT card — a different instrument, so it gets
    its own CC-prefixed ``email_type`` (mirroring the bank's separate
    ``hdfc_dc_transaction_alert`` / ``hdfc_cc_transaction_alert`` split).
    A reversal returns money to the card, so ``direction`` is ``credit``.
    The ``By <token>`` clause is the reversing merchant/acquirer
    (``counterparty``); the colon-separated datetime is the reversal time.
    The lowercase ``xx####`` card mask is kept verbatim, and ``\\s*`` after
    ``Reversed!`` tolerates the glued ``Reversed!On`` seen in real bodies.
    """

    bank = "hdfc"
    email_type = "hdfc_cc_reversal_alert"

    _PATTERN = re.compile(
        r"Transaction\s+Reversed!\s*"
        r"On\s+HDFC\s+Bank\s+CREDIT\s+Card\s+(?P<card>xx\d+)\s+"
        r"Amt:\s*Rs\.(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"By\s+(?P<merchant>.+?)\s+"
        r"On\s+(?P<datetime>\d{4}-\d{2}-\d{2}:\d{2}:\d{2}:\d{2})"
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
            raise ParseError("HDFC CC reversal alert pattern did not match")
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
                counterparty=match.group("merchant").strip(),
                card_mask=match.group("card"),
                channel="card",
            ),
        )


class HdfcCcTransactionAlertParser(BaseSmsParser):
    """HDFC credit-card spend alert.

    Three body shapes share this event type (same CC debit, different rail
    or phrasing); all emit ``hdfc_cc_transaction_alert`` and the rails are
    distinguished by ``channel``.

    1) POS / online spend (``channel="card"``):
        "Spent Rs.10290 On HDFC Bank Card 0000 At MERCHANT On
         2026-05-02:22:26:01.Not You? To Block+Reissue Call ..."

    1b) Amount-first POS / online spend (``channel="card"``) — cosmetic
    rewording of (1): lowercase verbs, amount before the verb, x-prefixed
    card mask, and a "Not U?" trailer glued to the datetime's period
    (``normalize_whitespace`` does not insert the missing space; the
    pattern tolerates the glued text and requires the trailer's
    "SMS BLOCK CC" — the only credit-card discriminator in this shape):
        "Rs.569 spent on HDFC Bank Card x0000 at MERCHANT on
         2026-07-12:17:00:56.Not U? To Block & Reissue Call ..."

    2) Credit-card-on-UPI spend (``channel="upi"``):
        "Txn Rs.100.00
         On HDFC Bank Card 0000
         At sample.vpa@hdfcbank
         by UPI 000000000000
         On 02-05
         Not You?
         Call .../SMS BLOCK CC 0000 to ..."

    Discriminators vs the debit-card shape:
    - "On HDFC Bank Card" (CC) vs "From HDFC Bank Card" (DC).
    - Bare 4-digit card mask, no "x" prefix.

    The POS shape carries a full datetime followed by a literal period and
    no balance trailer. The UPI shape carries the payee VPA
    (``counterparty``) and the UPI reference (``reference_number``); its
    "On DD-MM" date has no year and no time, so — like the bank's other
    dateless shapes — ``transaction_date``/``transaction_time`` fall back to
    ``received_at`` (UTC->IST) when supplied, else stay ``None``.
    """

    bank = "hdfc"
    email_type = "hdfc_cc_transaction_alert"

    _PATTERN = re.compile(
        r"Spent\s+Rs\.(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"On\s+HDFC\s+Bank\s+Card\s+(?P<card>\d+)\s+"
        r"At\s+(?P<merchant>.+?)\s+"
        r"On\s+(?P<datetime>\d{4}-\d{2}-\d{2}:\d{2}:\d{2}:\d{2})\."
    )

    # Amount-first rewording of _PATTERN. Kept case-sensitive and narrow:
    # lowercase "spent on"/"at"/"on" and an x-prefixed mask are exactly what
    # the real template uses. The "SMS BLOCK CC" trailer is required — it is
    # the only marker that says credit card despite the DC-style x#### mask,
    # so an amount-first debit-card variant ("SMS BLOCK DC") cannot be
    # mislabeled with this CC email_type.
    _AMOUNT_FIRST_PATTERN = re.compile(
        r"Rs\.(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"spent\s+on\s+HDFC\s+Bank\s+Card\s+(?P<card>x\d+)\s+"
        r"at\s+(?P<merchant>.+?)\s+"
        r"on\s+(?P<datetime>\d{4}-\d{2}-\d{2}:\d{2}:\d{2}:\d{2})\."
        r".*?SMS\s+BLOCK\s+CC\b"
    )

    _UPI_PATTERN = re.compile(
        r"Txn\s+Rs\.(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"On\s+HDFC\s+Bank\s+Card\s+(?P<card>\d+)\s+"
        r"At\s+(?P<merchant>.+?)\s+"
        r"by\s+UPI\s+(?P<ref>\d+)\s+"
        r"On\s+\d{2}-\d{2}\b"
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        text = normalize_whitespace(body)
        if match := self._PATTERN.search(text) or self._AMOUNT_FIRST_PATTERN.search(
            text
        ):
            dt = parse_datetime(match.group("datetime"))
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
                    counterparty=match.group("merchant"),
                    card_mask=match.group("card"),
                    channel="card",
                ),
            )
        if match := self._UPI_PATTERN.search(text):
            txn_date: datetime.date | None = None
            txn_time: datetime.time | None = None
            if received_at is not None:
                ist = received_at_to_ist(received_at)
                txn_date = ist.date()
                txn_time = ist.time()
            return ParsedSms(
                email_type=self.email_type,
                bank=self.bank,
                transaction=SmsTransactionAlert(
                    direction="debit",
                    amount=Money(
                        amount=parse_amount(match.group("amount")), currency="INR"
                    ),
                    transaction_date=txn_date,
                    transaction_time=txn_time,
                    counterparty=match.group("merchant"),
                    reference_number=match.group("ref"),
                    card_mask=match.group("card"),
                    channel="upi",
                ),
            )
        raise ParseError("HDFC CC transaction alert pattern did not match")


class HdfcCcRefundAlertParser(BaseSmsParser):
    """HDFC credit-card refund credit.

    variant 1 — UPI CC reference:
        "Alert! Rs. 254 refunded by UPI CC-27-04-2026-000000000000 on
         01/MAY/2026 & adjusted against HDFC Bank Credit Card 0000
         View updated balance here: https://..."

    variant 2 — merchant/acquirer name, no reference:
        "Alert! Rs. 262.56 refunded by SampleMerchant BANGALORE IND on
         17/MAY/2026 & adjusted against HDFC Bank Credit Card 0000
         View updated balance here: https://..."

    In variant 1 the CC reference embeds the original spend's date and
    UTR; the parser captures the trailing UTR digits as
    ``reference_number``. ``transaction_date`` is the refund date, not
    the original spend date.
    """

    bank = "hdfc"
    email_type = "hdfc_cc_refund_alert"

    _UPI_REFUND = re.compile(
        r"Alert!\s+Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"refunded\s+by\s+UPI\s+CC-\d{2}-\d{2}-\d{4}-(?P<ref>\d+)\s+"
        r"on\s+(?P<date>\d{1,2}/[A-Za-z]+/\d{4})\s+"
        r"&\s+adjusted\s+against\s+HDFC\s+Bank\s+Credit\s+Card\s+(?P<card>\d+)"
    )
    _MERCHANT_REFUND = re.compile(
        r"Alert!\s+Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"refunded\s+by\s+(?P<merchant>.+?)\s+"
        r"on\s+(?P<date>\d{1,2}/[A-Za-z]+/\d{4})\s+"
        r"&\s+adjusted\s+against\s+HDFC\s+Bank\s+Credit\s+Card\s+(?P<card>\d+)"
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        text = normalize_whitespace(body)
        if match := self._UPI_REFUND.search(text):
            return self._build(
                match,
                counterparty=None,
                reference_number=match.group("ref"),
                channel="upi",
            )
        if match := self._MERCHANT_REFUND.search(text):
            return self._build(
                match,
                counterparty=match.group("merchant").strip(),
                reference_number=None,
                channel="card",
            )
        raise ParseError("HDFC CC refund alert pattern did not match")

    def _build(
        self,
        match: re.Match[str],
        *,
        counterparty: str | None,
        reference_number: str | None,
        channel: str,
    ) -> ParsedSms:
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=parse_date(match.group("date")),
                counterparty=counterparty,
                reference_number=reference_number,
                card_mask=match.group("card"),
                channel=channel,
            ),
        )


class HdfcCcPaymentReceivedAlertParser(BaseSmsParser):
    """HDFC credit-card bill-payment-received credit alert.

    Three cosmetic body shapes share this event type:

    variant 1 — mixed-case "Online Payment ... vide Ref# ..." template:
        "HDFC Bank Cardmember, Online Payment of Rs.100 vide
         Ref# 000XXXXXXXXXXXX was credited to your card ending 0000
         On 08/MAY/2026_value Date 08/MAY/2026"

    variant 2 — fully-uppercase "PAYMENT OF ... RECEIVED TOWARDS ..."
    template (no reference number; includes available limit instead):
        "DEAR HDFCBANK CARDMEMBER, PAYMENT OF Rs. 100.00 RECEIVED TOWARDS
         YOUR CREDIT CARD ENDING WITH 0000 ON 17-5-2026.
         YOUR AVAILABLE LIMIT IS RS. 200.00"

    variant 3 — mixed-case "Payment of ... was credited" template with no
    reference number (distinct from variant 1's "Online Payment ... vide
    Ref#"; ``DD/MON/YYYY`` date):
        "HDFC Bank Cardmember, Payment of Rs 100 was credited to your card
         ending 0000 on 28/MAY/2026."

    The user's bill payment was credited to the credit card, reducing CC
    outstanding. Direction is ``credit``. The trailing ``_value Date``
    repeats the same date and is intentionally ignored in variant 1.
    ``channel`` and ``counterparty`` are left ``None`` because neither
    template carries an explicit channel marker.
    """

    bank = "hdfc"
    email_type = "hdfc_cc_payment_received_alert"

    _MIXED_CASE = re.compile(
        r"HDFC\s+Bank\s+Cardmember,\s+"
        r"Online\s+Payment\s+of\s+Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"vide\s+Ref#\s+(?P<ref>[A-Za-z0-9]+)\s+"
        r"was\s+credited\s+to\s+your\s+card\s+ending\s+(?P<card>\d+)\s+"
        r"On\s+(?P<date>\d{1,2}/[A-Za-z]+/\d{4})"
    )

    _UPPERCASE = re.compile(
        r"DEAR\s+HDFCBANK\s+CARDMEMBER,\s+"
        r"PAYMENT\s+OF\s+Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"RECEIVED\s+TOWARDS\s+YOUR\s+CREDIT\s+CARD\s+ENDING\s+WITH\s+(?P<card>\d+)\s+"
        r"ON\s+(?P<date>\d{1,2}-\d{1,2}-\d{4})"
        r"(?:\.?\s*YOUR\s+AVAILABLE\s+LIMIT\s+IS\s+RS\.?\s*(?P<balance>[\d,]+(?:\.\d+)?))?",
        re.IGNORECASE,
    )

    _NO_REF = re.compile(
        r"HDFC\s+Bank\s+Cardmember,\s+"
        r"Payment\s+of\s+Rs\.?\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"was\s+credited\s+to\s+your\s+card\s+ending\s+(?P<card>\d+)\s+"
        r"[Oo]n\s+(?P<date>\d{1,2}/[A-Za-z]+/\d{4})"
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        text = normalize_whitespace(body)
        # The ledger role is a property of the template, decided here where the
        # template is known -- not inferred later from whether a reference
        # survived. The reference-bearing "Online Payment ... vide Ref#" is the
        # settlement (the ledger event); the two no-reference shapes are the
        # provisional "received" notice, whose settlement arrives separately.
        if match := self._MIXED_CASE.search(text):
            return self._build(match, ref=match.group("ref"), role="primary")
        if match := self._NO_REF.search(text):
            return self._build(match, ref=None, role="provisional")
        if match := self._UPPERCASE.search(text):
            return self._build(match, ref=None, role="provisional")
        raise ParseError("HDFC CC payment-received pattern did not match")

    def _build(
        self,
        match: re.Match[str],
        *,
        ref: str | None,
        role: Literal["primary", "provisional", "restatement"],
    ) -> ParsedSms:
        # Only the uppercase template carries an available limit. Keep it as
        # balance; the other templates omit it.
        limit = match.groupdict().get("balance")
        balance = Money(amount=parse_amount(limit), currency="INR") if limit else None
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            ledger_role=role,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=parse_date(match.group("date")),
                reference_number=ref,
                card_mask=match.group("card"),
                balance=balance,
            ),
        )


class HdfcAccountTransactionAlertParser(BaseSmsParser):
    """HDFC savings/current-account IMPS credit alert.

    Sample (multi-line in the wire body; whitespace is normalized first):
        "Received!
         INR 12,345.00 in HDFC Bank A/c xx0000
         On 03-05-26
         For IMPS -Customer- 000000000000
         Avl bal INR 99,999.99"

    The counterparty is the IMPS originator's name; for self-transfers
    that is the user's own name. Account-mask casing matches the body
    (lowercase ``xx``).
    """

    bank = "hdfc"
    email_type = "hdfc_account_transaction_alert"

    _PATTERN = re.compile(
        r"Received!\s+"
        r"INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"in\s+HDFC\s+Bank\s+A/c\s+(?P<account>xx\d+)\s+"
        r"On\s+(?P<date>\d{2}-\d{2}-\d{2})\s+"
        r"For\s+IMPS\s+-(?P<counterparty>[^-]+)-\s+(?P<ref>\d+)\s+"
        r"Avl\s+bal\s+INR\s+(?P<balance>[\d,]+(?:\.\d+)?)"
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
            raise ParseError("HDFC account IMPS credit pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=parse_date(match.group("date")),
                counterparty=match.group("counterparty").strip(),
                reference_number=match.group("ref"),
                channel="imps",
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
                account_mask=match.group("account"),
            ),
        )


class HdfcAccountUpiCreditAlertParser(BaseSmsParser):
    """HDFC savings/current-account UPI credit alert.

    Sample (multi-line in the wire body; whitespace is normalized first):
        "Credit Alert!
         Rs.1.00 credited to HDFC Bank A/c XX0000 on 09-05-26
         from VPA customer@bank (UPI 000000000000)"

    Discriminators vs the IMPS credit shape:
    - Leading "Credit Alert!" banner (IMPS uses "Received!").
    - Amount prefixed with ``Rs.`` rather than ``INR``.
    - Account mask is uppercase ``XX####`` (IMPS body uses lowercase
      ``xx####``); kept verbatim from the body.
    - "from VPA <handle>" + "(UPI <ref>)" trailer; no in-body balance.

    Counterparty stores the bare VPA handle (``customer@bank``) — the
    ``VPA`` literal is a template marker, not part of the identifier.
    """

    bank = "hdfc"
    email_type = "hdfc_account_upi_credit_alert"

    _PATTERN = re.compile(
        r"Credit\s+Alert!\s+"
        r"Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"credited\s+to\s+HDFC\s+Bank\s+A/c\s+(?P<account>XX\d+)\s+"
        r"on\s+(?P<date>\d{2}-\d{2}-\d{2})\s+"
        r"from\s+VPA\s+(?P<vpa>\S+)\s+"
        r"\(UPI\s+(?P<ref>\d+)\)"
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
            raise ParseError("HDFC account UPI credit pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=parse_date(match.group("date")),
                counterparty=match.group("vpa"),
                reference_number=match.group("ref"),
                channel="upi",
                account_mask=match.group("account"),
            ),
        )


class HdfcAccountImpsOutwardAlertParser(BaseSmsParser):
    """HDFC savings/current-account outward IMPS debit alert."""

    bank = "hdfc"
    email_type = "hdfc_account_imps_outward_alert"

    _PATTERN = re.compile(
        r"IMPS\s+INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"sent\s+from\s+HDFC\s+Bank\s+A/c\s+(?P<account>XX\d+)\s+"
        r"on\s+(?P<date>\d{2}-\d{2}-\d{2})\s+"
        r"To\s+A/c\s+(?P<dest>x+\d+)\s+"
        r"Ref-(?P<ref>\d+)"
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
            raise ParseError("HDFC account outward IMPS pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=parse_date(match.group("date")),
                counterparty=f"Acct {match.group('dest')}",
                reference_number=match.group("ref"),
                channel="imps",
                account_mask=match.group("account"),
            ),
        )


class HdfcAccountUpiDebitAlertParser(BaseSmsParser):
    """HDFC savings/current-account outbound transfer alert.

    Two cosmetic body shapes share this event type:

    1) ``Sent Rs.<amount>`` template — UPI/IMPS to a person/VPA payee
       (channel inferred from the trailing ``BLOCK UPI``/``BLOCK IMPS``
       hint; defaults to ``upi``):
        "Sent Rs.100.00
         From HDFC Bank A/C *0000
         To CUSTOMER NAME
         On 17/05/26
         Ref 000000000000
         Not You?
         Call 18002586161/SMS BLOCK UPI to 7308080808"

    2) ``IMPS INR <amount> sent`` template — IMPS to a masked account
       (no payee name; explicit IMPS prefix and ``Ref-`` delimiter
       distinguish this shape; ``channel="imps"`` unconditionally):
        "IMPS INR 1,23,456.78
         sent from HDFC Bank A/c XX0000 on 12-05-26
         To A/c xxxxxxxxxx0000
         Ref-000000000000
         Not you?Call 18002586161/SMS BLOCK OB to 7308080808"

    The IMPS-to-account shape carries no payee name, so ``counterparty``
    surfaces the masked destination account (``Acct xxxxxxxxxx0000``).

    The IMPS regex is intentionally narrow: source mask is ``XX####``
    (uppercase, per HDFC's IMPS-send convention), destination mask is
    ``x...####`` (lowercase, the only form seen in real bodies), and the
    reference delimiter is the exact token ``Ref-`` (no space, no colon).
    Loosen only when a real SMS in another shape is observed.
    """

    bank = "hdfc"
    email_type = "hdfc_account_upi_debit_alert"

    _PATTERN = re.compile(
        r"Sent\s+Rs\.(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"From\s+HDFC\s+Bank\s+A/C\s+\*?(?P<account>\d+)\s+"
        r"To\s+(?P<payee>.+?)\s+"
        r"On\s+(?P<date>\d{2}/\d{2}/\d{2})\s+"
        r"Ref\s+(?P<ref>\d+)"
    )

    _IMPS_SEND_PATTERN = re.compile(
        r"IMPS\s+INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"sent\s+from\s+HDFC\s+Bank\s+A/c\s+(?P<account>XX\d+)\s+"
        r"on\s+(?P<date>\d{2}-\d{2}-\d{2})\s+"
        r"To\s+A/c\s+(?P<dest>x+\d+)\s+"
        r"Ref-(?P<ref>\d+)"
    )

    _IMPS_HINT = re.compile(r"BLOCK\s+IMPS", re.IGNORECASE)

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        text = normalize_whitespace(body)
        if match := self._IMPS_SEND_PATTERN.search(text):
            return ParsedSms(
                email_type=self.email_type,
                bank=self.bank,
                transaction=SmsTransactionAlert(
                    direction="debit",
                    amount=Money(
                        amount=parse_amount(match.group("amount")), currency="INR"
                    ),
                    transaction_date=parse_date(match.group("date")),
                    counterparty=f"Acct {match.group('dest')}",
                    reference_number=match.group("ref"),
                    channel="imps",
                    account_mask=match.group("account"),
                ),
            )
        if match := self._PATTERN.search(text):
            channel = "imps" if self._IMPS_HINT.search(text) else "upi"
            return ParsedSms(
                email_type=self.email_type,
                bank=self.bank,
                transaction=SmsTransactionAlert(
                    direction="debit",
                    amount=Money(
                        amount=parse_amount(match.group("amount")), currency="INR"
                    ),
                    transaction_date=parse_date(match.group("date")),
                    counterparty=match.group("payee").strip(),
                    reference_number=match.group("ref"),
                    channel=channel,
                    account_mask=match.group("account"),
                ),
            )
        raise ParseError("HDFC account UPI debit pattern did not match")


class HdfcAccountCreditAlertParser(BaseSmsParser):
    """HDFC savings/current-account inbound credit alert ("Update!" template).

    Two cosmetic variants of the same "Update! ... deposited ..." deposit
    template share this event type, distinguished by the transfer tag:

    1) ``for FT-`` — generic fund transfer (``channel="imps"``):
        "Update! INR 100.00 deposited in HDFC Bank A/c XX0000 on
         16-MAY-26 for FT- CUSTOMER NAME-XXXXXXXXXX0000 - REMITTER
         NAME.Avl bal INR 200.00. Cheque deposits in A/C are subject
         to clearing"

       The trailing remitter name (after the second "-" and before the
       period that opens ``Avl bal``) is the counterparty. Default
       channel to ``imps`` — HDFC's "Update!" deposit template is the
       IMPS counterpart of the "Sent ..." debit template, and "FT-" is
       HDFC's tag for inbound fund transfers in this family.

    2) ``for NEFT Cr-`` — inbound NEFT credit (``channel="neft"``):
        "Update! INR 100.00 deposited in HDFC Bank A/c XX0000 on
         29-JUN-26 for NEFT Cr-SAMPLE0INBX01-Sample Remitter Inc-Customer
         Name-SAMPLEH00000000000.Avl bal INR 200.00. Cheque deposits in
         A/C are subject to clearing"

       The NEFT reference is structured ``<route>-<remitter>-<beneficiary>
       -<UTR>``. The remitter (first dash-segment after the route code) is
       the counterparty; the beneficiary is the user.
    """

    bank = "hdfc"
    email_type = "hdfc_account_credit_alert"

    _PATTERN = re.compile(
        r"Update!\s+INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"deposited\s+in\s+HDFC\s+Bank\s+A/c\s+(?P<account>XX\d+)\s+"
        r"on\s+(?P<date>\d{2}-[A-Z]+-\d{2})\s+"
        r"for\s+FT-\s*(?P<counterparty>[^.]+?)"
        r"\.\s*Avl\s+bal\s+INR\s+(?P<balance>[\d,]+(?:\.\d+)?)"
    )

    _NEFT_PATTERN = re.compile(
        r"Update!\s+INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"deposited\s+in\s+HDFC\s+Bank\s+A/c\s+(?P<account>XX\d+)\s+"
        r"on\s+(?P<date>\d{2}-[A-Z]+-\d{2})\s+"
        # Reference is "<route>-<remitter>-<beneficiary>-<UTR>". Route is a
        # hyphen-free code and the UTR is a hyphen-free token; the remitter
        # is captured greedily so a hyphenated remitter name (e.g.
        # "STATE-BANK") stays intact, leaving the single-segment beneficiary
        # (the user) and the UTR pinned to the right.
        r"for\s+NEFT\s+Cr-(?P<route>[^-]+)-(?P<counterparty>.+)-"
        r"(?P<beneficiary>[^-]+)-(?P<ref>[^-.]+?)"
        r"\.\s*Avl\s+bal\s+INR\s+(?P<balance>[\d,]+(?:\.\d+)?)"
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        text = normalize_whitespace(body)
        if match := self._NEFT_PATTERN.search(text):
            return ParsedSms(
                email_type=self.email_type,
                bank=self.bank,
                transaction=SmsTransactionAlert(
                    direction="credit",
                    amount=Money(
                        amount=parse_amount(match.group("amount")), currency="INR"
                    ),
                    transaction_date=parse_date(match.group("date")),
                    counterparty=match.group("counterparty").strip(),
                    reference_number=match.group("ref").strip(),
                    channel="neft",
                    balance=Money(
                        amount=parse_amount(match.group("balance")), currency="INR"
                    ),
                    account_mask=match.group("account"),
                ),
            )
        if not (match := self._PATTERN.search(text)):
            raise ParseError("HDFC account credit-alert pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=parse_date(match.group("date")),
                counterparty=match.group("counterparty").strip(),
                channel="imps",
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
                account_mask=match.group("account"),
            ),
        )


class HdfcCcSmartpayBbpsAlertParser(BaseSmsParser):
    """HDFC SmartPay BBPS bill-pay debit alert.

    Sample:
        "Dear Smart Pay Customer,We have successfully debited your HDFC
         Bank Credit card ending 0000 to pay your SpayBBPS 00000 bill
         for the amount Rs 100"

    HDFC SmartPay auto-debits the registered credit card to pay BBPS
    bills (electricity, utilities, etc.). The body carries:
    - amount (``for the amount Rs N``)
    - card mask (``ending NNNN``)
    - the BBPS biller's SpayBBPS reference (used as ``reference_number``)

    There is no in-body date and no merchant name, so:
    - ``transaction_date`` / ``transaction_time`` fall back to
      ``received_at`` (UTC→IST) when supplied, else stay ``None``;
    - ``counterparty`` is set to ``"SpayBBPS <ref>"`` so the downstream
      can surface the biller reference.

    Emits ``email_type="hdfc_cc_smartpay_bbps_alert"`` (distinct from
    the generic CC spend so downstream consumers can recognize this as
    an auto-debit BBPS bill).
    """

    bank = "hdfc"
    email_type = "hdfc_cc_smartpay_bbps_alert"

    _PATTERN = re.compile(
        r"Dear\s+Smart\s+Pay\s+Customer,?\s*"
        r"We\s+have\s+successfully\s+debited\s+your\s+HDFC\s+Bank\s+Credit\s+card\s+"
        r"ending\s+(?P<card>\d+)\s+"
        r"to\s+pay\s+your\s+SpayBBPS\s+(?P<ref>\S+)\s+bill\s+"
        r"for\s+the\s+amount\s+Rs\.?\s*(?P<amount>[\d,]+(?:\.\d+)?)",
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
            raise ParseError("HDFC SmartPay BBPS bill-pay pattern did not match")
        txn_date: datetime.date | None = None
        txn_time: datetime.time | None = None
        if received_at is not None:
            ist = received_at_to_ist(received_at)
            txn_date = ist.date()
            txn_time = ist.time()
        ref = match.group("ref")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=txn_date,
                transaction_time=txn_time,
                counterparty=f"SpayBBPS {ref}",
                reference_number=ref,
                card_mask=match.group("card"),
                channel="card",
            ),
        )


class HdfcAccountTransferDebitAlertParser(BaseSmsParser):
    """HDFC savings-to-PPF/SSY transfer debit alert.

    Sample:
        "Alert!
         Rs. 1,00,000.00 transferred to your PPF/SSY A/c No. XX0000 via
         HDFC Bank Online Banking.
         Not you?Call 18002586161"

    Money leaves the savings account into the user's own PPF/SSY account, so
    ``direction`` is ``debit`` and ``channel`` is ``online``. Only the
    destination account is in the body (surfaced as counterparty); there is
    no in-body date, so the date falls back to ``received_at`` (UTC→IST) when
    supplied, else stays ``None``.
    """

    bank = "hdfc"
    email_type = "hdfc_account_transfer_debit_alert"

    _PATTERN = re.compile(
        r"Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"transferred\s+to\s+your\s+PPF/SSY\s+A/c\s+No\.\s+(?P<dest>X+\d+)\s+"
        r"via\s+HDFC\s+Bank\s+Online\s+Banking"
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
            raise ParseError("HDFC account transfer debit pattern did not match")
        txn_date: datetime.date | None = None
        txn_time: datetime.time | None = None
        if received_at is not None:
            ist = received_at_to_ist(received_at)
            txn_date = ist.date()
            txn_time = ist.time()
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=txn_date,
                transaction_time=txn_time,
                counterparty=f"PPF/SSY A/c {match.group('dest')}",
                channel="online",
            ),
        )


class HdfcAccountNeftDebitAlertParser(BaseSmsParser):
    """Parse an HDFC online banking NEFT debit.

    Example:
        "Amt Deducted! Rs.12345.67 from your HDFC Bank A/c XX0000 for
         NEFT txn via HDFC Bank Online Banking Not you?Call 00000000000/
         SMS BLOCK OB to 0000000000"

    The message does not contain a beneficiary, reference number, balance,
    or transaction time. If ``received_at`` is available, convert it from UTC
    to IST. Use the result for the transaction date and time.

    The parser requires the fraud report text. This text prevents a match
    with an OTP or an incomplete message.

    HDFC sends this SMS at the moment of the transaction. In 59 real pairs,
    the SMS and the email arrive -5 to +14 seconds apart. Thus
    ``event_time_source`` is ``message_arrival``, and the consumer must trust
    the time less than a time that the bank writes.
    """

    bank = "hdfc"
    email_type = "hdfc_account_neft_debit_alert"
    event_time_source = "message_arrival"

    _PATTERN = re.compile(
        r"Amt\s+Deducted!\s+Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"from\s+your\s+HDFC\s+Bank\s+A/c\s+(?P<account>XX\d+)\s+"
        r"for\s+NEFT\s+txn\s+via\s+HDFC\s+Bank\s+Online\s+Banking\s+"
        r"Not\s+you\?\s*Call\s+\d+/SMS\s+BLOCK\s+OB\s+to\s+\d+\s*$",
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
        if not (match := self._PATTERN.fullmatch(text)):
            raise ParseError("HDFC account NEFT debit pattern did not match")
        txn_date: datetime.date | None = None
        txn_time: datetime.time | None = None
        if received_at is not None:
            ist = received_at_to_ist(received_at)
            txn_date = ist.date()
            txn_time = ist.time()
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=txn_date,
                transaction_time=txn_time,
                account_mask=match.group("account"),
                channel="neft",
            ),
        )


class HdfcAccountRtgsInitiatedDebitAlertParser(BaseSmsParser):
    """HDFC savings/current-account outward RTGS debit alert ("initiated").

    Two wordings share this shape:
        "RTGS txn initiated: Of Rs.123456 from your HDFC Bank A/c XX0000
         using Online Banking. Not you?Call 18002586161/SMS BLOCK OB to
         7308080808"
        "RTGS transaction initiated: Of Rs.123456 from your HDFC Bank A/c
         XX0000 using Online Banking. Not you?Call 18002586161/SMS BLOCK
         OB to 7308080808"

    HDFC sends two SMSes per RTGS transfer. This "initiated" alert is the
    ledger debit and names the source account, which the settlement message
    omits, so it keeps the debit attributable to the right HDFC account. The
    bank also sends a "RTGS Money Deposited~..." settlement SMS
    (``HdfcRtgsMoneyDepositedParser``) carrying the UTR and beneficiary but no
    source account. The dashboard fuses the two: it stamps the settlement
    leg's UTR onto this initiated row, so the single debit keeps both the
    account and the reference, and does not double-count the transfer.

    This shape carries amount, source account mask, and channel only. The
    "Not you?Call .../SMS BLOCK ..." anti-fraud boilerplate is not part of
    any field. There is no payee name, no reference number, and no balance
    in this template, so ``counterparty``, ``reference_number``, and
    ``balance`` stay ``None``. The body has no date, so the date falls
    back to ``received_at`` (UTC->IST) when supplied, else stays ``None``.
    """

    bank = "hdfc"
    email_type = "hdfc_account_rtgs_debit_alert"

    _PATTERN = re.compile(
        r"RTGS\s+(?:txn|transaction)\s+initiated:\s*"
        r"Of\s+Rs\.(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"from\s+your\s+HDFC\s+Bank\s+A/c\s+(?P<account>XX\d+)\s+"
        r"using\s+Online\s+Banking"
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
            raise ParseError("HDFC account RTGS initiated debit pattern did not match")
        txn_date: datetime.date | None = None
        txn_time: datetime.time | None = None
        if received_at is not None:
            ist = received_at_to_ist(received_at)
            txn_date = ist.date()
            txn_time = ist.time()
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=txn_date,
                transaction_time=txn_time,
                channel="rtgs",
                account_mask=match.group("account"),
            ),
        )


class HdfcAccountOnlineTransferDebitAlertParser(BaseSmsParser):
    """HDFC savings account net-banking payee transfer debit alert.

    Example:
        "Amt Deducted!
         Rs.12345.67 from your HDFC Bank A/c XX0000 for Money Transfer
         via HDFC Bank Online Banking.
         Not you?Call 00000000000/SMS BLOCK OB to 0000000000"

    The transfer moves money from the savings account to a payee over net
    banking. The bank names no rail (NEFT, IMPS, or RTGS), so ``channel``
    is ``online``. The SMS carries no payee, reference, balance, or
    transaction time.

    The parser requires the fraud report text. This text prevents a match
    with an OTP or an incomplete message.

    HDFC sends this SMS at the moment of the transaction. If ``received_at``
    is available, convert it from UTC to IST. Use the result for the
    transaction date and time. Thus ``event_time_source`` is
    ``message_arrival``.
    """

    bank = "hdfc"
    email_type = "hdfc_account_online_transfer_debit_alert"
    event_time_source = "message_arrival"

    _PATTERN = re.compile(
        r"Amt\s+Deducted!\s+Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"from\s+your\s+HDFC\s+Bank\s+A/c\s+(?P<account>XX\d+)\s+"
        r"for\s+Money\s+Transfer\s+via\s+HDFC\s+Bank\s+Online\s+Banking\.?\s*"
        r"Not\s+you\?\s*Call\s+\d+/SMS\s+BLOCK\s+OB\s+to\s+\d+\s*$",
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
        if not (match := self._PATTERN.fullmatch(text)):
            raise ParseError("HDFC account online transfer debit pattern did not match")
        txn_date: datetime.date | None = None
        txn_time: datetime.time | None = None
        if received_at is not None:
            ist = received_at_to_ist(received_at)
            txn_date = ist.date()
            txn_time = ist.time()
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=txn_date,
                transaction_time=txn_time,
                account_mask=match.group("account"),
                channel="online",
            ),
        )


class HdfcRtgsMoneyDepositedParser(BaseSmsParser):
    """HDFC outward RTGS settlement alert ("RTGS Money Deposited~").

    Sample:
        "RTGS Money Deposited~INR 2,00,000.00~To SAMPLE NAME~Txn No:
         HDFCR00000000000000000~On 21-08-2026 at 01:06:23~-HDFC Bank"

    Fires when an outward RTGS settles at the beneficiary bank. It is the
    settlement leg of the transfer and carries the UTR (``reference_number``),
    the beneficiary (``counterparty``), and an exact in-body date and time.
    Direction is ``debit`` (money left the user); ``channel`` is ``rtgs``.
    The template names no source account, so ``account_mask`` stays ``None``.

    The submission leg ("RTGS ... initiated", ``HdfcAccountRtgsInitiatedDebitAlertParser``)
    names the source account but carries no UTR. The two are one debit but
    arrive as two SMS. This parser only extracts the settlement fields; the
    dashboard fuses them, stamping this leg's UTR onto the unique initiated
    debit row (fail-closed) so the ledger row keeps both the account and the
    reference. This leg therefore does not open its own ledger row.

    The anchor requires the full "RTGS Money Deposited~...~Txn No: ...~On
    <date> at <time>~-HDFC Bank" frame. A body that shares only the opening
    words (for example a failed or returned RTGS with a different trailer)
    fails the anchor and surfaces as an error, not a wrong debit.
    """

    bank = "hdfc"
    email_type = "hdfc_account_rtgs_deposited_alert"

    _PATTERN = re.compile(
        r"RTGS\s+Money\s+Deposited~"
        r"INR\s+(?P<amount>[\d,]+(?:\.\d+)?)~"
        r"To\s+(?P<name>.+?)~"
        r"Txn\s+No:\s*(?P<ref>\S+?)~"
        r"On\s+(?P<date>\d{1,2}-\d{1,2}-\d{4})\s+at\s+(?P<time>\d{1,2}:\d{2}:\d{2})~"
        r"-?\s*HDFC\s+Bank",
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
            raise ParseError("HDFC RTGS money-deposited pattern did not match")
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
                counterparty=match.group("name").strip(),
                reference_number=match.group("ref"),
                channel="rtgs",
            ),
        )


_PARSERS: tuple[BaseSmsParser, ...] = (
    HdfcDcTransactionAlertParser(),
    # DC reversal has a unique "Transaction Reversed!" banner; grouped with
    # the DC spend for readability. Order vs the others is not load-bearing.
    HdfcDcReversalAlertParser(),
    # CC reversal shares the "Transaction Reversed!" banner but requires the
    # literal "CREDIT Card" (the DC parser requires "DEBIT/ATM Card"), so the
    # two are mutually exclusive and ordering between them is not
    # load-bearing.
    HdfcCcReversalAlertParser(),
    HdfcCcTransactionAlertParser(),
    HdfcCcRefundAlertParser(),
    # Payment-received sits after the refund (both are CC credits) and
    # before the account parsers; each has a unique anchor so order is
    # not load-bearing, but grouping the CC shapes keeps the file
    # readable.
    HdfcCcPaymentReceivedAlertParser(),
    # SmartPay BBPS auto-debit lands on the CC; specific enough that its
    # ordering vs the generic CC spend doesn't matter (different anchors).
    HdfcCcSmartpayBbpsAlertParser(),
    # Both account parsers have unique leading banners ("Received!" vs
    # "Credit Alert!") so they are mutually exclusive; ordering between
    # them is not load-bearing.
    HdfcAccountTransactionAlertParser(),
    HdfcAccountUpiCreditAlertParser(),
    HdfcAccountCreditAlertParser(),
    HdfcAccountImpsOutwardAlertParser(),
    HdfcAccountUpiDebitAlertParser(),
    HdfcAccountTransferDebitAlertParser(),
    HdfcAccountNeftDebitAlertParser(),
    # RTGS "initiated" outward debit: unique "RTGS ... initiated:" anchor, so
    # ordering vs the other account shapes is not load-bearing.
    HdfcAccountRtgsInitiatedDebitAlertParser(),
    # Outward RTGS settlement leg ("RTGS Money Deposited~..."): unique tilde
    # frame. The dashboard fuses its UTR onto the initiated debit; it opens no
    # ledger row of its own. Order not load-bearing (unique anchor).
    HdfcRtgsMoneyDepositedParser(),
    HdfcAccountOnlineTransferDebitAlertParser(),
)


class HdfcParser(BankSmsParser):
    bank = "hdfc"
    parsers = _PARSERS


def parse(
    body: str,
    *,
    sender: str | None = None,
    received_at: datetime.datetime | None = None,
) -> ParsedSms:
    """Module-level convenience wrapper."""
    return HdfcParser().parse(body, sender=sender, received_at=received_at)
