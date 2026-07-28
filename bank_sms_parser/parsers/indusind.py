"""IndusInd Bank SMS parsers."""

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
    received_at_to_ist,
)


class IndusindAccountTransactionAlertParser(BaseSmsParser):
    """IndusInd savings/current-account transaction alert.

    Three body shapes share this event type:

    1) UPI alert (carries no in-body date — uses ``received_at`` fallback):
        "A/C *XX0000 credited by Rs 12345.00 from VPA@bank.
         RRN:000000000000. Avl Bal:12345.00. ..."

    2) IMPS transfer (carries an in-body DD-MM-YY date and the
       destination account/name):
        "Your account XXXXXXX0000 debited with Rs. 12345 on 03-05-26
         and account XXXXXXX0001/Customer will be credited.
         (IMPS Ref no. 000000000000). ..."

    3) Debit-card purchase debit (no in-body date — uses ``received_at``
       fallback; no merchant in the body, so ``counterparty`` stays
       ``None``; ``channel="card"``):
        "INR 1,100.00 debited from your A/C 000***000000 towards
         Debit Card Purchase. Avl BAL INR 0.00 - Not you? ..."
       The account-mask format here uses a 3-digit prefix + ``***`` +
       a 6-digit suffix (distinct from the ``*XX####`` UPI form and the
       all-X IMPS form), and is preserved verbatim.
    """

    bank = "indusind"
    email_type = "indusind_account_transaction_alert"

    _UPI_PATTERN = re.compile(
        r"A/C\s+\*(?P<account>XX\d+)\s+(?P<verb>credited|debited)\s+by\s+Rs\s+"
        r"(?P<amount>[\d,]+(?:\.\d+)?)\s+from\s+(?P<vpa>\S+)\.\s+"
        r"RRN:(?P<rrn>\d+)\.\s+Avl\s+Bal:(?P<balance>[\d,]+(?:\.\d+)?)"
    )

    _IMPS_PATTERN = re.compile(
        r"Your\s+account\s+(?P<account>X+\d+)\s+(?P<verb>debited|credited)\s+with\s+"
        r"Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"on\s+(?P<date>\d{2}-\d{2}-\d{2})\s+"
        r"and\s+account\s+(?P<dest>X+\d+)/(?P<dest_name>[^.]+?)\s+will\s+be\s+credited\.\s*"
        r"\(IMPS\s+Ref\s+no\.\s*(?P<ref>\d+)\)"
    )

    _DC_PURCHASE_PATTERN = re.compile(
        r"INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"debited\s+from\s+your\s+A/C\s+(?P<account>\d{3}\*{3}\d{6})\s+"
        r"towards\s+Debit\s+Card\s+Purchase\.\s+"
        r"Avl\s+BAL\s+INR\s+(?P<balance>[\d,]+(?:\.\d+)?)"
    )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        text = normalize_whitespace(body)

        if match := self._UPI_PATTERN.search(text):
            return self._build_upi(match, received_at)

        if match := self._IMPS_PATTERN.search(text):
            return self._build_imps(match)

        if match := self._DC_PURCHASE_PATTERN.search(text):
            return self._build_dc_purchase(match, received_at)

        raise ParseError(
            "IndusInd account transaction alert: no known pattern matched"
        )

    def _build_upi(
        self,
        match: re.Match[str],
        received_at: datetime.datetime | None,
    ) -> ParsedSms:
        direction = "credit" if match.group("verb") == "credited" else "debit"
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
                direction=direction,
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=txn_date,
                transaction_time=txn_time,
                counterparty=match.group("vpa"),
                reference_number=match.group("rrn"),
                channel="upi",
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
                account_mask=match.group("account"),
            ),
        )

    def _build_imps(self, match: re.Match[str]) -> ParsedSms:
        direction = "debit" if match.group("verb") == "debited" else "credit"
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction=direction,
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                counterparty=f"Acct {match.group('dest')}/{match.group('dest_name').strip()}",
                reference_number=match.group("ref"),
                channel="imps",
                account_mask=match.group("account"),
            ),
        )

    def _build_dc_purchase(
        self,
        match: re.Match[str],
        received_at: datetime.datetime | None,
    ) -> ParsedSms:
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
                channel="card",
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
                account_mask=match.group("account"),
            ),
        )


class IndusindAccountUpiCreditAlertParser(BaseSmsParser):
    """IndusInd savings/current-account UPI credit alert.

    Body shape (carries no in-body date — uses ``received_at`` fallback):
        "A/C *XX0000 credited by Rs 12345.00 from 9999999999@samplevpa.
         RRN:999999999999. Avl Bal:12345.00. Not you? Call 18602677777
         - IndusInd bank"

    Specific to the UPI inbound shape: account mask, ``credited by``
    verb, source VPA, RRN, and Avl Bal are all required. The verb is
    intentionally restricted to ``credited`` so the IMPS debit shape
    (``debited with`` plus an in-body date) cannot accidentally match.
    """

    bank = "indusind"
    email_type = "indusind_account_upi_credit_alert"

    _PATTERN = re.compile(
        r"A/C\s+\*(?P<account>XX\d+)\s+credited\s+by\s+Rs\s+"
        r"(?P<amount>[\d,]+(?:\.\d+)?)\s+from\s+(?P<vpa>\S+?)\.\s+"
        r"RRN:(?P<rrn>\d+)\.\s+Avl\s+Bal:(?P<balance>[\d,]+(?:\.\d+)?)"
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
            raise ParseError(
                "IndusInd account UPI credit alert: pattern did not match"
            )

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
                direction="credit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=txn_date,
                transaction_time=txn_time,
                counterparty=match.group("vpa"),
                reference_number=match.group("rrn"),
                channel="upi",
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
                account_mask=match.group("account"),
            ),
        )


class IndusindAccountUpiDebitAlertParser(BaseSmsParser):
    """IndusInd savings/current-account UPI debit alert.

    Body shape (carries no in-body date — uses ``received_at`` fallback):
        "A/C *XX0000 debited by Rs 12345.00 towards 9999999999@samplevpa.
         RRN:999999999999. Avl Bal:12345.00. Not you? Call 18602677777
         - IndusInd bank"

    Symmetric counterpart of ``IndusindAccountUpiCreditAlertParser``:
    same body grammar with ``debited``/``towards`` instead of
    ``credited``/``from``. The verb is intentionally restricted to
    ``debited`` and the preposition to ``towards`` so the legacy UPI
    pattern (which uses ``from``) and the IMPS debit shape cannot
    accidentally match.
    """

    bank = "indusind"
    email_type = "indusind_account_upi_debit_alert"

    _PATTERN = re.compile(
        r"A/C\s+\*(?P<account>XX\d+)\s+debited\s+by\s+Rs\s+"
        r"(?P<amount>[\d,]+(?:\.\d+)?)\s+towards\s+(?P<vpa>\S+?)\.\s+"
        r"RRN:(?P<rrn>\d+)\.\s+Avl\s+Bal:(?P<balance>[\d,]+(?:\.\d+)?)"
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
            raise ParseError(
                "IndusInd account UPI debit alert: pattern did not match"
            )

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
                counterparty=match.group("vpa"),
                reference_number=match.group("rrn"),
                channel="upi",
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
                account_mask=match.group("account"),
            ),
        )


class IndusindAccountDcPurchaseAlertParser(BaseSmsParser):
    """IndusInd account debit from debit-card purchase."""

    bank = "indusind"
    email_type = "indusind_account_dc_purchase_alert"

    _PATTERN = re.compile(
        r"INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"debited\s+from\s+your\s+A/C\s+(?P<account>\d{3}\*{3}\d{6})\s+"
        r"towards\s+Debit\s+Card\s+Purchase\.\s+"
        r"Avl\s+BAL\s+INR\s+(?P<balance>[\d,]+(?:\.\d+)?)"
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
            raise ParseError("IndusInd account debit-card purchase pattern did not match")
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
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=txn_date,
                transaction_time=txn_time,
                channel="card",
                balance=Money(amount=parse_amount(match.group("balance")), currency="INR"),
                account_mask=match.group("account"),
            ),
        )


class IndusindAccountCreditAlertParser(BaseSmsParser):
    """IndusInd savings/current-account generic inbound credit alert.

    Sample:
        "IndusInd A/C **0000 Credited; INR 1,234.56 Ref-Refund Frm
         SampleSource Payments.Bal INR 2,345.67.Dispute-Call
         18602677777-IndusInd Bank"

    Distinct from the UPI/IMPS credit shapes: this template uses the
    ``A/C **####`` two-asterisk mask, a ``Credited;`` verb, an ``INR``
    amount, a ``Ref-<text>`` narration, and a ``Bal INR`` balance. The
    ``Ref-`` clause here is **descriptive narration** (e.g. a refund
    source), not a numeric/alnum reference token. It is stored as the
    ``counterparty`` (cleaned of the trailing ``Bal``/``Dispute-Call``
    boilerplate); ``reference_number`` stays ``None`` so a descriptive
    string cannot collide downstream as a fake reference.

    The body carries no date — ``received_at`` (UTC→IST) fills the
    transaction date/time when supplied.
    """

    bank = "indusind"
    email_type = "indusind_account_credit_alert"

    _PATTERN = re.compile(
        r"IndusInd\s+A/C\s+(?P<account>\*\*\d+)\s+Credited;\s+INR\s+"
        r"(?P<amount>[\d,]+(?:\.\d+)?)\s+Ref-(?P<ref>.+?)\.\s*"
        r"Bal\s+INR\s+(?P<balance>[\d,]+(?:\.\d+)?)",
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
            raise ParseError("IndusInd account credit pattern did not match")

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
                direction="credit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=txn_date,
                transaction_time=txn_time,
                counterparty=match.group("ref").strip(),
                reference_number=None,
                balance=Money(
                    amount=parse_amount(match.group("balance")), currency="INR"
                ),
                account_mask=match.group("account"),
            ),
        )


class IndusindCcPaymentReceivedAlertParser(BaseSmsParser):
    """IndusInd credit-card payment-received notification.

    Sample:
        "Dear Customer, thank you for your Payment of INR 1,234.56
         towards your IndusInd Bank Credit Card on 18/07/2026
         - IndusInd Bank"

    This is IndusInd's completed payment receipt and is therefore a primary
    credit that reduces card debt. The template omits the card mask, so account
    resolution is left to the consumer. ``counterparty="Payment received"``
    matches the sibling email parser and lets cross-channel deduplication pair
    the two alerts. Requiring the full thank-you, payment,
    card-product, date, and bank-signature frame rejects statement reminders.
    """

    bank = "indusind"
    email_type = "indusind_cc_payment_received_alert"
    # This alert names no merchant and gives no card mask. Thus no field
    # shows which card the payment belongs to.
    identifies_by = "none"

    _PATTERN = re.compile(
        r"Dear\s+Customer,\s+thank\s+you\s+for\s+your\s+Payment\s+of\s+INR\s+"
        r"(?P<amount>[\d,]+(?:\.\d+)?)\s+towards\s+your\s+IndusInd\s+Bank\s+"
        r"Credit\s+Card\s+on\s+(?P<date>\d{1,2}/\d{1,2}/\d{4})\s+"
        r"-\s*IndusInd\s+Bank\.?$",
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
            raise ParseError("IndusInd CC payment-received pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=parse_date(match.group("date")),
                counterparty="Payment received",
                channel="card",
            ),
        )


class IndusindCcRefundAlertParser(BaseSmsParser):
    """IndusInd credit-card merchant refund.

    Sample::

        "Dear Customer, refund of INR 1,234.00 from SampleMerchant
         BENGALURU IND has been credited to your IndusInd Bank Credit
         Card XX0000 on 27-Jul-26 and the refund amount has been
         adjusted against the outstanding on your card account
         - IndusInd Bank"
    """

    bank = "indusind"
    email_type = "indusind_cc_refund_alert"

    _PATTERN = re.compile(
        r"Dear\s+Customer,\s+refund\s+of\s+INR\s+"
        r"(?P<amount>[\d,]+(?:\.\d+)?)\s+from\s+"
        r"(?P<merchant>.+?)\s+has\s+been\s+credited\s+to\s+your\s+"
        r"IndusInd\s+Bank\s+Credit\s+Card\s+(?P<card>XX\d+)\s+on\s+"
        r"(?P<date>\S+)\s+and\s+the\s+refund\s+amount\s+has\s+been\s+"
        r"adjusted\s+against\s+the\s+outstanding\s+on\s+your\s+card\s+"
        r"account\s+-\s*IndusInd\s+Bank",
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
            raise ParseError("IndusInd CC refund pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(
                    amount=parse_amount(match.group("amount")), currency="INR"
                ),
                transaction_date=parse_date(match.group("date")),
                counterparty=match.group("merchant").strip(),
                card_mask=match.group("card"),
                channel="card",
            ),
        )


class IndusindCcSpendAlertParser(BaseSmsParser):
    """IndusInd credit-card spend alert.

    Distinct from the savings/current-account UPI/IMPS shapes: this is a
    card POS/online spend that carries an in-body date + 12-hour clock time
    and an ``Avl Lmt`` (available credit limit) rather than ``Avl Bal``.

    Sample:
        "INR 1,234.00 spent on IndusInd Card XX0000 on 22-05-2026
         07:58:13 pm at PYU*SWIGGY FOOD. Avl Lmt: INR 99,999.99.
         To dispute, call 18602677777/SMS BLOCK 0000 to 5676757"
    """

    bank = "indusind"
    email_type = "indusind_cc_transaction_alert"

    _PATTERN = re.compile(
        r"INR\s+(?P<amount>[\d,]+(?:\.\d+)?)\s+spent\s+on\s+"
        r"IndusInd\s+Card\s+(?P<card>XX\d+)\s+on\s+"
        r"(?P<date>\d{2}-\d{2}-\d{4})\s+"
        r"(?P<time>\d{1,2}:\d{2}:\d{2}\s*(?i:[ap]m))\s+"
        r"at\s+(?P<merchant>.+?)\.\s+Avl\s+Lmt:\s+INR\s+"
        r"(?P<limit>[\d,]+(?:\.\d+)?)"
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
            raise ParseError("IndusInd CC spend pattern did not match")

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
                counterparty=match.group("merchant").strip(),
                balance=Money(
                    amount=parse_amount(match.group("limit")), currency="INR"
                ),
                card_mask=match.group("card"),
                channel="card",
            ),
        )


# Order: the shape-specific UPI parsers run first. The UPI-credit parser
# is verb-restricted to ``credited`` + ``from``; the UPI-debit parser is
# verb-restricted to ``debited`` + ``towards``. Both claim their UPI
# traffic before falling through to the legacy alert parser, which still
# handles the IMPS debit shape (and remains a safety net for the historic
# UPI ``from``-only regex).
_PARSERS: tuple[BaseSmsParser, ...] = (
    IndusindCcPaymentReceivedAlertParser(),
    IndusindCcRefundAlertParser(),
    IndusindCcSpendAlertParser(),
    IndusindAccountUpiCreditAlertParser(),
    IndusindAccountUpiDebitAlertParser(),
    IndusindAccountCreditAlertParser(),
    IndusindAccountDcPurchaseAlertParser(),
    IndusindAccountTransactionAlertParser(),
)


class IndusindParser(BankSmsParser):
    bank = "indusind"
    parsers = _PARSERS


def parse(body: str, *, sender: str | None = None, received_at: datetime.datetime | None = None) -> ParsedSms:
    return IndusindParser().parse(body, sender=sender, received_at=received_at)
