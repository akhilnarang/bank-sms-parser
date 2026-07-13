"""Equitas CC payment-received SMS parser tests.

Kept in its own module to avoid merge conflicts with the broader
``test_new_parsers.py`` file that several parallel agents are editing.
"""

import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from bank_sms_parser import parse_sms
from bank_sms_parser.exceptions import ParseError

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sms"


def _read(rel: str) -> str:
    return (FIXTURES_DIR / rel).read_text()


def test_parses_equitas_cc_payment_received() -> None:
    body = _read("equitas/cc_payment_received.txt")
    result = parse_sms("equitas", body)
    assert result.email_type == "equitas_cc_payment_alert"
    assert result.bank == "equitas"
    txn = result.transaction
    assert txn is not None
    assert txn.direction == "credit"
    assert txn.amount.amount == Decimal("12345.00")
    assert txn.amount.currency == "INR"
    assert txn.card_mask == "XX9999"
    assert txn.counterparty == "Payment received"
    assert txn.channel == "card"
    assert txn.transaction_date == datetime.date(2026, 5, 5)
    # Payment-received notifications carry no time component.
    assert txn.transaction_time is None
    assert txn.account_mask is None
    assert txn.balance is None


def test_parses_equitas_cc_payment_received_thank_you_variant() -> None:
    """The "Thank you for the payment of Rs.X towards Equitas Credit
    Card ####" variant (DD/MM/YY date, bare 4-digit card, no reference)
    parses to the same equitas_cc_payment_alert credit event."""
    body = _read("equitas/cc_payment_received_thank_you.txt")
    result = parse_sms("equitas", body)
    assert result.email_type == "equitas_cc_payment_alert"
    assert result.bank == "equitas"
    txn = result.transaction
    assert txn is not None
    assert txn.direction == "credit"
    assert txn.amount.amount == Decimal("12345.00")
    assert txn.amount.currency == "INR"
    assert txn.card_mask == "0000"
    assert txn.counterparty == "Payment received"
    assert txn.channel == "card"
    assert txn.transaction_date == datetime.date(2026, 6, 7)
    assert txn.transaction_time is None
    assert txn.account_mask is None
    assert txn.balance is None
    assert txn.reference_number is None


def test_existing_spend_alert_does_not_match_payment_received() -> None:
    """The pre-existing 'spent' shape must still parse as the spend alert,
    not as the new payment-received parser — the two patterns are mutually
    exclusive and the spend body has no 'was received' / 'was credited'
    markers."""
    body = _read("equitas/cc_spend.txt")
    result = parse_sms("equitas", body)
    assert result.email_type == "equitas_cc_transaction_alert"
    assert result.transaction is not None
    assert result.transaction.direction == "debit"


def test_payment_received_synthetic_negative_raises_parse_error() -> None:
    """A spend-alert-shaped body without the payment-received markers
    must not be (mis)parsed by the payment-received parser. We assert the
    dispatcher's overall behaviour: this body must parse as a spend alert,
    proving the payment-received pattern correctly rejected it."""
    body = (
        "INR 30.00 spent on Equitas CC XX0000 at SOME MERCHANT on "
        "01-05-2026 07:53:18 PM. Available limit is INR. 99,999.99."
    )
    result = parse_sms("equitas", body)
    assert result.email_type == "equitas_cc_transaction_alert"


def test_payment_received_truncated_body_raises_parse_error() -> None:
    """A truncated payment-received body that lacks the card mask must
    raise ParseError rather than silently dropping the field."""
    body = "INR 12,345.00 was received on 05/05/2026 and was credited to your"
    with pytest.raises(ParseError):
        parse_sms("equitas", body)


class TestEquitasStubs:
    """Non-transaction Equitas shapes are recognized-and-skipped via stubs.

    Each stub raises ``ParserStubError`` internally; the dispatcher catches
    it and continues, so callers see the aggregate ``ParseError`` from
    ``parse_sms``. The stub's ``email_type`` (ending in ``_stub``) appears
    in that error message — the downstream sms_pipeline marks such SMSes
    "skipped" instead of "error" based on the ``_stub`` substring.
    """

    def test_payment_due_recognized_as_stub(self) -> None:
        body = _read("equitas/negative/payment_due.txt")
        with pytest.raises(ParseError) as excinfo:
            parse_sms("equitas", body)
        assert "equitas_cc_payment_due_stub" in str(excinfo.value)
        assert "ParserStubError" in str(excinfo.value)

    def test_statement_generated_recognized_as_stub(self) -> None:
        body = _read("equitas/negative/statement_generated.txt")
        with pytest.raises(ParseError) as excinfo:
            parse_sms("equitas", body)
        assert "equitas_cc_statement_notice_stub" in str(excinfo.value)
        assert "ParserStubError" in str(excinfo.value)

    def test_mobile_login_failed_recognized_as_stub(self) -> None:
        body = _read("equitas/negative/mobile_login_failed.txt")
        with pytest.raises(ParseError) as excinfo:
            parse_sms("equitas", body)
        assert "equitas_service_info_stub" in str(excinfo.value)
        assert "ParserStubError" in str(excinfo.value)

    def test_unrelated_failure_does_not_leak_stub_marker(self) -> None:
        """An Equitas body no parser (stub or real) recognizes must produce
        an aggregate error WITHOUT the ``_stub`` substring — otherwise the
        downstream pipeline would disposition every unparseable Equitas SMS
        as skipped instead of surfacing it as an error."""
        with pytest.raises(ParseError) as excinfo:
            parse_sms(
                "equitas",
                "Your Equitas OTP is 123456. Do not share it with anyone.",
            )
        assert "_stub" not in str(excinfo.value)

    def test_stubs_do_not_swallow_real_transaction_bodies(self) -> None:
        """Every stub must raise plain ParseError (never ParserStubError)
        for the bank's real spend / payment-received bodies, so the
        dispatcher continues on to the transaction parsers."""
        from bank_sms_parser.exceptions import ParserStubError
        from bank_sms_parser.parsers.equitas import _PARSERS

        stubs = [p for p in _PARSERS if p.email_type.endswith("_stub")]
        assert stubs, "expected Equitas stub parsers in _PARSERS"
        for fixture in (
            "equitas/cc_spend.txt",
            "equitas/cc_payment_received.txt",
            "equitas/cc_payment_received_thank_you.txt",
        ):
            body = _read(fixture)
            for stub in stubs:
                try:
                    stub.parse(body)
                except ParserStubError as exc:
                    pytest.fail(
                        f"{stub.email_type} must not classify {fixture} "
                        f"as a stub shape: {exc}"
                    )
                except ParseError:
                    pass

    def test_real_parsers_appear_before_stubs(self) -> None:
        """First match wins: stubs must sit at the very end of _PARSERS."""
        from bank_sms_parser.parsers.equitas import _PARSERS

        types = [p.email_type for p in _PARSERS]
        stubs = [t for t in types if t.endswith("_stub")]
        real = [t for t in types if not t.endswith("_stub")]
        assert stubs and real
        last_real = max(types.index(t) for t in real)
        first_stub = min(types.index(t) for t in stubs)
        assert last_real < first_stub, (
            f"stub parsers must come after real parsers: {types}"
        )

    def test_real_fixtures_still_parse_with_stubs_registered(self) -> None:
        """End-to-end: adding stubs must not change what the real
        fixtures parse to."""
        for fixture, email_type in (
            ("equitas/cc_spend.txt", "equitas_cc_transaction_alert"),
            ("equitas/cc_payment_received.txt", "equitas_cc_payment_alert"),
            (
                "equitas/cc_payment_received_thank_you.txt",
                "equitas_cc_payment_alert",
            ),
        ):
            result = parse_sms("equitas", _read(fixture))
            assert result.email_type == email_type
