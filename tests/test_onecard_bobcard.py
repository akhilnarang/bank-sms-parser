"""Targeted tests for the BOBCARD One template family inside OneCard.

The OneCard subpackage carries two SMS families:
  1. ``AX-OneCrd-S`` — the "Hola! that was sweet" payment-received template.
  2. ``AX-BOBONE-S`` / ``CP-BOBONE-S`` / ``AD-BOBONE-S`` — the BOBCARD One
     spend, bill-cleared, foreign-currency, statement-ready, and limit-update
     templates.

These tests focus on the BOBCARD half: the four real spend phrasings, the two
intentional stubs (``ParserStubError`` -> dispatcher returns ``ParseError``),
and a regression assertion that the legacy "Hola!" parser still wins for its
own template after the BOBCARD parsers were added to ``_PARSERS``.

Mirror conventions from ``tests/test_new_parsers.py``: read sanitized fixtures
from ``tests/fixtures/sms/onecard/``, and never put real merchant names,
amounts, or card masks in this file.
"""

import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from bank_sms_parser import parse_sms
from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.parsers.onecard import (
    _PARSERS,
    OnecardCcPaymentReceivedParser,
    OnecardCcServiceInfoStubParser,
    OnecardCcStatementNoticeStubParser,
    OnecardCcTransactionAlertParser,
    OnecardParser,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sms" / "onecard"


def _read(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


# Happy-path BOBCARD spends ---------------------------------------------------


class TestBobcardSpendShapes:
    """All three BOBCARD spend phrasings collapse into one email_type."""

    def test_bill_cleared_inr(self) -> None:
        result = parse_sms("onecard", _read("cc_charge_bill_cleared.txt"))
        assert result.email_type == "onecard_cc_transaction_alert"
        assert result.bank == "onecard"
        txn = result.transaction
        assert txn is not None
        assert txn.direction == "debit"
        assert txn.amount.amount == Decimal("49.00")
        assert txn.amount.currency == "INR"
        assert txn.card_mask == "XX0000"
        assert txn.counterparty == "SampleSubs Monthly"
        assert txn.channel == "card"

    def test_spent_inr(self) -> None:
        result = parse_sms("onecard", _read("cc_charge_spent.txt"))
        assert result.email_type == "onecard_cc_transaction_alert"
        txn = result.transaction
        assert txn is not None
        assert txn.direction == "debit"
        assert txn.amount.amount == Decimal("1234.00")
        assert txn.amount.currency == "INR"
        assert txn.card_mask == "XX0000"
        assert txn.counterparty == "QuickGroceries Marketplace"
        assert txn.channel == "card"

    def test_paid_foreign_currency(self) -> None:
        result = parse_sms("onecard", _read("cc_charge_paid_usd.txt"))
        assert result.email_type == "onecard_cc_transaction_alert"
        txn = result.transaction
        assert txn is not None
        assert txn.direction == "debit"
        assert txn.amount.amount == Decimal("42.50")
        # Verify USD is preserved end-to-end — not silently coerced to INR.
        assert txn.amount.currency == "USD"
        assert txn.card_mask == "XX0000"
        assert txn.counterparty == "OffshoreVendor Pte. Ltd."
        assert txn.channel == "card"

    def test_spent_uses_received_at_for_date_fallback(self) -> None:
        """BOBCARD spend bodies carry no date; received_at (UTC->IST) fills it."""
        # 2026-04-13 21:30 UTC == 2026-04-14 03:00 IST
        received = datetime.datetime(2026, 4, 13, 21, 30, tzinfo=datetime.UTC)
        result = parse_sms(
            "onecard", _read("cc_charge_spent.txt"), received_at=received
        )
        txn = result.transaction
        assert txn is not None
        assert txn.transaction_date == datetime.date(2026, 4, 14)
        assert txn.transaction_time == datetime.time(3, 0)


# Intentional stubs -----------------------------------------------------------


class TestBobcardStubs:
    """#18 limit-update and #19 statement-ready raise ParserStubError internally.

    The dispatcher catches ``ParserStubError`` and continues, so callers see the
    aggregate ``ParseError`` from ``parse_sms``. The ``email_type`` of each
    stub appears in the error message, which is how downstream consumers
    distinguish "intentionally unsupported known shape" from "no parser
    matched at all".
    """

    def test_limit_update_recognized_as_service_info_stub(self) -> None:
        body = _read("negative/limit_update.txt")
        with pytest.raises(ParseError) as excinfo:
            parse_sms("onecard", body)
        # Stub identity surfaces in the dispatcher's aggregated error message.
        assert "onecard_cc_service_info_stub" in str(excinfo.value)
        assert "ParserStubError" in str(excinfo.value)

    def test_statement_ready_recognized_as_statement_notice_stub(self) -> None:
        body = _read("negative/statement_ready.txt")
        with pytest.raises(ParseError) as excinfo:
            parse_sms("onecard", body)
        assert "onecard_cc_statement_notice_stub" in str(excinfo.value)
        assert "ParserStubError" in str(excinfo.value)

    def test_service_info_stub_does_not_swallow_real_spend(self) -> None:
        """The stub must NOT match a real BOBCARD spend body."""
        # Direct call to the stub: a real spend body has the brand marker but
        # no service-info phrase. The stub must raise ParseError, not
        # ParserStubError, so the dispatcher continues to the real parser.
        from bank_sms_parser.exceptions import ParserStubError as _Stub

        stub = OnecardCcServiceInfoStubParser()
        with pytest.raises(ParseError):
            stub.parse(_read("cc_charge_spent.txt"))
        # And not the stub-flavored error either.
        try:
            stub.parse(_read("cc_charge_bill_cleared.txt"))
        except _Stub as exc:
            pytest.fail(
                "service-info stub should not classify a bill-cleared spend "
                f"as a stub: {exc}"
            )
        except ParseError:
            pass

    def test_statement_notice_stub_does_not_swallow_bill_cleared(self) -> None:
        """The "is ready" anchor must not match "has been cleared"."""
        from bank_sms_parser.exceptions import ParserStubError as _Stub

        stub = OnecardCcStatementNoticeStubParser()
        for fixture in (
            "cc_charge_bill_cleared.txt",
            "cc_charge_spent.txt",
            "cc_charge_paid_usd.txt",
            "cc_payment_received_10000.txt",
        ):
            try:
                stub.parse(_read(fixture))
            except _Stub as exc:
                pytest.fail(
                    f"statement-notice stub wrongly matched {fixture}: {exc}"
                )
            except ParseError:
                pass


# Regression: legacy "Hola!" payment-received parser still wins ---------------


class TestLegacyOneCrdRegression:
    """The AX-OneCrd-S 'Hola!' template must still parse after BOBCARD parsers.

    Adds explicit assertions for all three legacy fixtures so that any future
    reordering or refactoring of ``_PARSERS`` that breaks the payment-received
    path will fail loudly here.
    """

    @pytest.mark.parametrize(
        "fixture, amount, txn_date",
        [
            ("cc_payment_received_10000.txt", Decimal("10000.00"), datetime.date(2026, 4, 29)),
            ("cc_payment_received_1050.txt", Decimal("1050.00"), datetime.date(2026, 4, 28)),
            ("cc_payment_received_1799.txt", Decimal("1799.94"), datetime.date(2026, 4, 25)),
        ],
    )
    def test_hola_payment_received_still_wins(
        self, fixture: str, amount: Decimal, txn_date: datetime.date
    ) -> None:
        result = parse_sms("onecard", _read(fixture))
        assert result.email_type == "onecard_cc_payment_received_alert"
        txn = result.transaction
        assert txn is not None
        assert txn.direction == "credit"
        assert txn.amount.amount == amount
        assert txn.amount.currency == "INR"
        assert txn.transaction_date == txn_date


# _PARSERS ordering invariants ------------------------------------------------


class TestParsersOrdering:
    """Order matters: real parsers first, stubs last."""

    def test_real_parsers_appear_before_stubs(self) -> None:
        types = [type(p) for p in _PARSERS]
        real = (OnecardCcPaymentReceivedParser, OnecardCcTransactionAlertParser)
        stubs = (OnecardCcStatementNoticeStubParser, OnecardCcServiceInfoStubParser)
        # Every real-parser index must be strictly less than every stub index.
        last_real = max(types.index(t) for t in real)
        first_stub = min(types.index(t) for t in stubs)
        assert last_real < first_stub, (
            f"Stubs must follow real parsers in _PARSERS; got {types}"
        )

    def test_dispatcher_uses_same_tuple(self) -> None:
        assert OnecardParser.parsers is _PARSERS

    def test_all_parsers_share_the_onecard_bank(self) -> None:
        for parser in _PARSERS:
            assert parser.bank == "onecard"
