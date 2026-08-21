"""IDFC FIRST Bank SMS parsers."""

import datetime
import re

from bank_sms_parser.exceptions import ParseError, ParserStubError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import BankSmsParser, BaseSmsParser
from bank_sms_parser.parsing import (
    normalize_whitespace,
    parse_amount,
    parse_date,
    parse_datetime,
    parse_money,
)


class IdfcCcPaymentReceivedParser(BaseSmsParser):
    """IDFC FIRST Wealth CC bill-payment-received notification.

    Sample:
        "Thank you for payment of INR 3,000.00 towards your
         FIRST Wealth Credit Card XX0000 on 02 May 2026. IDFC FIRST Bank"
    """

    bank = "idfc"
    email_type = "idfc_cc_payment_received_alert"
    # You pay your own card bill, so this alert names no merchant. The
    # card mask shows which payment it reports.
    identifies_by = "card_mask"

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


class IdfcCcTransactionAlertParser(BaseSmsParser):
    """IDFC FIRST Bank credit-card spend alert.

    Sample:
        "Transaction Successful! INR 370.80 spent on your IDFC FIRST Bank
         Credit Card ending XX0000 at SAMPLE MERCHANT LTD on 05 JUL 2026 at
         11:54 AM Avbl Limit: INR 99999.9 If not done by you, call 180010888
         for dispute or to block your card SMS CCBLOCK 0000 to 5676732"

    Anchored on ``spent on your IDFC FIRST Bank Credit Card ending`` so it
    cannot collide with the bank's account-level shapes (which all anchor on
    ``A/C``/``A/c`` clauses) or the CC payment-received shape. The merchant
    is the counterparty, the in-body ``DD MON YYYY at HH:MM AM/PM`` stamp
    supplies date + time, and the ``Avbl Limit: INR ...`` trailer is surfaced
    as ``balance``. Amounts carry an ``INR`` prefix, so ``parse_money`` is
    used. ``channel="card"``; ``direction="debit"``.
    """

    bank = "idfc"
    email_type = "idfc_cc_transaction_alert"

    _PATTERN = re.compile(
        r"(?P<amount>INR\s+[\d,]+(?:\.\d+)?)\s+spent\s+on\s+your\s+"
        r"IDFC\s+FIRST\s+Bank\s+Credit\s+Card\s+ending\s+(?P<card>X+\d+)\s+"
        r"at\s+(?P<merchant>.+?)\s+"
        r"on\s+(?P<datetime>\d{1,2}\s+[A-Za-z]{3,}\s+\d{4}\s+at\s+"
        r"\d{1,2}:\d{2}\s+[AP]M)\s+"
        r"Avbl\s+Limit\s*:\s*(?P<balance>INR\s+[\d,]+(?:\.\d+)?)"
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
            raise ParseError("IDFC CC spend pattern did not match")
        txn_dt = parse_datetime(match.group("datetime"))
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=parse_money(match.group("amount")),
                transaction_date=txn_dt.date(),
                transaction_time=txn_dt.time(),
                counterparty=match.group("merchant").strip(),
                channel="card",
                card_mask=match.group("card"),
                balance=parse_money(match.group("balance")),
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

    4) Merchant debit anchored on ``for <merchant> transaction.``,
       carrying a DD-Mon-YYYY date + 24-hour time and no balance
       trailer (a payment-gateway pull, e.g. a netbanking checkout);
       ``channel`` stays ``None`` because the body carries no rail
       marker; the merchant is the counterparty:
        "Your A/c XXXXXXX0000 is debited by INR 12,345.00 on
         05-Aug-2026 13:34 for SamplePay Private Limited transaction.
         Call us on 180010888 for dispute. Team IDFC FIRST Bank."

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

    _MERCHANT_DEBIT_PATTERN = re.compile(
        r"Your\s+A/[Cc]\s+(?P<account>X+\d+)\s+is\s+debited\s+by\s+INR\s+"
        r"(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"on\s+(?P<date>\d{1,2}-[A-Za-z]{3}-\d{4})\s+(?P<time>\d{1,2}:\d{2})\s+"
        r"for\s+(?P<merchant>.+?)\s+transaction\.\s*"
        r"Call\s+us\s+on\s+\d+\s+for\s+dispute"
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

        if match := self._MERCHANT_DEBIT_PATTERN.search(text):
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
                    account_mask=match.group("account"),
                ),
            )

        raise ParseError(
            "IDFC account transaction alert: no known pattern matched "
            "(tried card spend, UPI debit, generic debit, merchant debit)"
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


class IdfcAccountRtgsCreditAlertParser(BaseSmsParser):
    """IDFC FIRST account inbound RTGS credit alert.

    Sample:
        "Your A/c XXXXXXX0000 has been credited with Rs. 200,000.00 on
         21-08-2026. Info: RTGS/HDFCR00000000000000000/SAMPLE NAME.
         New bal: Rs. 99,999.99. Team IDFC FIRST Bank"

    The completed ``has been credited with Rs.`` frame is the inbound
    counterpart of the outward RTGS debit. The ``Info: RTGS/ <ref>/<name>``
    clause carries the RTGS reference and the remitter name (surfaced as
    counterparty). ``channel="rtgs"``. For a self-transfer the remitter is
    the user; the body is parsed as it reads, one credit event.
    """

    bank = "idfc"
    email_type = "idfc_account_rtgs_credit_alert"

    _PATTERN = re.compile(
        r"Your\s+A/c\s+(?P<account>X+\d+)\s+has\s+been\s+credited\s+with\s+"
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
            raise ParseError("IDFC account RTGS credit pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                counterparty=match.group("name").strip(),
                reference_number=match.group("ref"),
                channel="rtgs",
                balance=Money(amount=parse_amount(match.group("balance")), currency="INR"),
                account_mask=match.group("account"),
            ),
        )


class IdfcAccountNeftCreditAlertParser(BaseSmsParser):
    """IDFC FIRST account inbound NEFT credit alert.

    Sample:
        "Your A/c XXXXXXX0000 has been credited with Rs. 2,500.00 on
         21-08-2026. Info: NEFT/IN00000000000000/SAMPLE NAME.
         New bal: Rs. 99,999.99. Team IDFC FIRST Bank"

    The completed ``has been credited with Rs.`` frame is the inbound
    counterpart of the outward NEFT debit, discriminated from the RTGS
    credit by the ``Info: NEFT/`` rail token. The clause carries the NEFT
    UTR and the remitter name (surfaced as counterparty). ``channel="neft"``.
    """

    bank = "idfc"
    email_type = "idfc_account_neft_credit_alert"

    _PATTERN = re.compile(
        r"Your\s+A/c\s+(?P<account>X+\d+)\s+has\s+been\s+credited\s+with\s+"
        r"Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"on\s+(?P<date>\d{2}-\d{2}-\d{4})\.\s*"
        r"Info:\s*NEFT/\s*(?P<ref>\S+?)/(?P<name>.+?)\.\s*"
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
            raise ParseError("IDFC account NEFT credit pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="credit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                counterparty=match.group("name").strip(),
                reference_number=match.group("ref"),
                channel="neft",
                balance=Money(amount=parse_amount(match.group("balance")), currency="INR"),
                account_mask=match.group("account"),
            ),
        )


class IdfcAccountNeftDebitAlertParser(BaseSmsParser):
    """IDFC FIRST account outward NEFT debit alert.

    Sample:
        "Your A/c XXXXXXX0000 has been debited by Rs. 12,345.00 on
         05-06-2026. Info: NEFT/ IDFB0000X0000000/BENEFICIARY NAME.
         New bal: Rs. 980.89. Team IDFC FIRST Bank"

    Structurally identical to the RTGS debit shape but anchored on the
    ``Info: NEFT/ <utr>/<name>`` clause. The clause carries the NEFT UTR
    (surfaced as ``reference_number``) and the beneficiary name (surfaced
    as ``counterparty``). ``channel="neft"``.
    """

    bank = "idfc"
    email_type = "idfc_account_neft_debit_alert"

    _PATTERN = re.compile(
        r"Your\s+A/c\s+(?P<account>X+\d+)\s+has\s+been\s+debited\s+by\s+"
        r"Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"on\s+(?P<date>\d{2}-\d{2}-\d{4})\.\s*"
        r"Info:\s*NEFT/\s*(?P<ref>\S+?)/(?P<name>.+?)\.\s*"
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
            raise ParseError("IDFC account NEFT debit pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                transaction_date=parse_date(match.group("date")),
                counterparty=match.group("name").strip(),
                reference_number=match.group("ref"),
                channel="neft",
                balance=Money(amount=parse_amount(match.group("balance")), currency="INR"),
                account_mask=match.group("account"),
            ),
        )


class IdfcAccountNeftBeneficiaryCreditAlertParser(BaseSmsParser):
    """IDFC FIRST NEFT beneficiary-received confirmation.

    Sample:
        "Your beneficiary BENEFICIARY NAME has received Rs. 12,345.00
         transferred via NEFT UTR IDFB0000X0000000.
         Team IDFC First Bank."

    This is a low-signal *confirmation* that a NEFT the user **initiated**
    was received by the beneficiary — it is NOT a credit to the user's own
    account. Per the single-event contract we parse what the body literally
    says. ``direction="debit"`` because this event describes money leaving
    the user (the same outflow as the NEFT debit alert, here confirmed from
    the beneficiary's side); modelling it as a credit would falsely imply
    the user received funds. It carries no account/card mask and no balance,
    so those fields stay ``None``; the beneficiary name is the counterparty
    and the UTR is the reference. Parsing it to a structured result (rather
    than raising) stops it erroring in prod, while the distinct
    ``idfc_account_neft_beneficiary_credit_alert`` email_type lets the
    fetcher treat it as a confirmation and dedupe against the matching
    NEFT debit by UTR.
    """

    bank = "idfc"
    email_type = "idfc_account_neft_beneficiary_credit_alert"

    _PATTERN = re.compile(
        r"Your\s+beneficiary\s+(?P<name>.+?)\s+has\s+received\s+"
        r"Rs\.\s*(?P<amount>[\d,]+(?:\.\d+)?)\s+"
        r"transferred\s+via\s+NEFT\s+UTR\s+(?P<ref>\S+?)\.?\s*"
        r"Team\s+IDFC\s+First\s+Bank"
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
            raise ParseError("IDFC NEFT beneficiary-received pattern did not match")
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(amount=parse_amount(match.group("amount")), currency="INR"),
                counterparty=match.group("name").strip(),
                reference_number=match.group("ref"),
                channel="neft",
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


class IdfcAsbaNoticeStubParser(BaseSmsParser):
    """Recognize-and-skip parser for IDFC IPO ASBA lifecycle notices.

    Two shapes of the same lifecycle:

    1) Application received / amount blocked:
        "Your ASBA application for SAMPLEIPO is received and Application
         value of Rs 14999 is blocked in your registered Bank account on
         14/08/2026. Team IDFC FIRST Bank"

    2) Amount unblocked (no/partial allotment, per the registrar):
        "An amount of Rs 14999 is unblocked on 14/08/2026 on account of
         No Allotment of shares for SAMPLEIPO as per the RTA.
         Team IDFC FIRST Bank"

    An ASBA block is a lien, not a debit — the money never leaves the
    account, and the unblock merely releases the lien. Neither shape is a
    money-movement event ``SmsTransactionAlert`` can model, so per the
    skill we recognize the shape and raise ``ParserStubError`` (rather
    than ``ParseError``) to distinguish "intentionally unsupported known
    shape" from "generic regex miss". Both anchors require the full ASBA
    clause (``blocked in your registered Bank account`` /
    ``unblocked ... as per the RTA``) so a real debit or credit body
    cannot be swallowed.
    """

    bank = "idfc"
    email_type = "idfc_asba_notice_stub"

    _BLOCKED_PATTERN = re.compile(
        r"Your\s+ASBA\s+application\s+for\s+\S+\s+is\s+received\s+and\s+"
        r"Application\s+value\s+of\s+Rs\.?\s*[\d,]+(?:\.\d+)?\s+"
        r"is\s+blocked\s+in\s+your\s+registered\s+Bank\s+account",
        re.IGNORECASE,
    )

    _UNBLOCKED_PATTERN = re.compile(
        r"An\s+amount\s+of\s+Rs\.?\s*[\d,]+(?:\.\d+)?\s+is\s+unblocked\s+"
        r"on\s+\d{2}/\d{2}/\d{4}\s+on\s+account\s+of\s+.+?\s+"
        r"as\s+per\s+the\s+RTA",
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
        if not (
            self._BLOCKED_PATTERN.search(text)
            or self._UNBLOCKED_PATTERN.search(text)
        ):
            raise ParseError("IDFC ASBA notice: not an ASBA block/unblock shape")
        raise ParserStubError(
            "idfc_asba_notice_stub: recognized IPO ASBA lifecycle notice; an "
            "ASBA block/unblock is a lien on the account, not a debit or "
            "credit, so this shape is intentionally unimplemented"
        )


_PARSERS: tuple[BaseSmsParser, ...] = (
    IdfcCcPaymentReceivedParser(),
    # CC spend: unique "spent on your IDFC FIRST Bank Credit Card ending"
    # anchor; cannot collide with the A/C-anchored account shapes.
    IdfcCcTransactionAlertParser(),
    IdfcAccountBalanceDebitAlertParser(),
    IdfcAccountTransactionAlertParser(),
    IdfcAccountRtgsDebitAlertParser(),
    # Inbound RTGS credit: the "credited with Rs. ... Info: RTGS/..." frame is
    # the credit counterpart of the outward RTGS debit. Distinct verb
    # ("credited with" vs "debited by"), so order vs the debit is not
    # load-bearing.
    IdfcAccountRtgsCreditAlertParser(),
    # Outward NEFT debit: same "has been debited by Rs. ... New bal: Rs. ..."
    # frame as RTGS, discriminated by the "Info: NEFT/ <utr>/<name>" clause;
    # order vs RTGS is not load-bearing (mutually exclusive rail markers).
    IdfcAccountNeftDebitAlertParser(),
    # Inbound NEFT credit: the credit counterpart of the outward NEFT debit,
    # discriminated from the RTGS credit by the "Info: NEFT/..." rail token.
    IdfcAccountNeftCreditAlertParser(),
    # NEFT beneficiary-received confirmation: unique "Your beneficiary ... has
    # received ... via NEFT UTR ..." anchor; cannot collide with other shapes.
    IdfcAccountNeftBeneficiaryCreditAlertParser(),
    # Outward IMPS debit: anchored on "a/c ending <digits> ... debited ...
    # (IMPS Ref no ...)". Its "a/c ending <bare digits>" mask form is
    # distinct from the transaction parser's "A/c XX####", so order is not
    # load-bearing.
    IdfcAccountImpsOutwardAlertParser(),
    IdfcAccountImpsCreditAlertParser(),
    IdfcAccountBalanceCreditAlertParser(),
    IdfcAccountCreditAlertParser(),
    # ASBA lifecycle stub last, so it can never shadow a real parser.
    IdfcAsbaNoticeStubParser(),
)


class IdfcParser(BankSmsParser):
    bank = "idfc"
    parsers = _PARSERS


def parse(body: str, *, sender: str | None = None, received_at: datetime.datetime | None = None) -> ParsedSms:
    return IdfcParser().parse(body, sender=sender, received_at=received_at)
