"""Tests for BaseSmsParser, BankSmsParser, and parse_with_parsers."""

import datetime
import warnings
from decimal import Decimal

import pytest
from bank_sms_parser.exceptions import ParseError, ParserStubError
from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert
from bank_sms_parser.parsers.base import (
    BankSmsParser,
    BaseSmsParser,
    parse_with_parsers,
)

# Test parser doubles ---------------------------------------------------------


class _AlwaysSucceedsParser(BaseSmsParser):
    bank = "test"
    email_type = "test_alert"

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        return ParsedSms(
            email_type=self.email_type,
            bank=self.bank,
            transaction=SmsTransactionAlert(
                direction="debit",
                amount=Money(amount=Decimal("1")),
                raw_description=f"sender={sender!r} received_at={received_at!r}",
            ),
        )


class _AlwaysParseErrorParser(BaseSmsParser):
    bank = "test"
    email_type = "test_parse_error"

    def parse(self, body, *, sender=None, received_at=None):
        raise ParseError("nope")


class _AlwaysStubParser(BaseSmsParser):
    bank = "test"
    email_type = "test_stub"

    def parse(self, body, *, sender=None, received_at=None):
        raise ParserStubError("not implemented")


class _AlwaysUnexpectedParser(BaseSmsParser):
    bank = "test"
    email_type = "test_boom"

    def parse(self, body, *, sender=None, received_at=None):
        raise KeyError("boom")


# Tests ----------------------------------------------------------------------


class TestBaseSmsParserSubclassValidation:
    def test_subclass_must_declare_bank(self) -> None:
        with pytest.raises(TypeError):
            class _Bad(BaseSmsParser):  # noqa: F841
                email_type = "x"

                def parse(self, body, *, sender=None, received_at=None):
                    raise NotImplementedError

    def test_subclass_must_declare_email_type(self) -> None:
        with pytest.raises(TypeError):
            class _Bad(BaseSmsParser):  # noqa: F841
                bank = "x"

                def parse(self, body, *, sender=None, received_at=None):
                    raise NotImplementedError


class TestParseWithParsers:
    def test_first_match_wins(self) -> None:
        parsers = [_AlwaysParseErrorParser(), _AlwaysSucceedsParser()]
        result = parse_with_parsers("test", "body", parsers)
        assert result.email_type == "test_alert"

    def test_all_parse_error_raises_final_parse_error(self) -> None:
        parsers = [_AlwaysParseErrorParser(), _AlwaysStubParser()]
        with pytest.raises(ParseError) as excinfo:
            parse_with_parsers("test", "body", parsers)
        assert "test_parse_error" in str(excinfo.value)
        assert "test_stub" in str(excinfo.value)

    def test_unexpected_exception_does_not_short_circuit(self) -> None:
        parsers = [_AlwaysUnexpectedParser(), _AlwaysSucceedsParser()]
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = parse_with_parsers("test", "body", parsers)
        assert result.email_type == "test_alert"
        assert any("KeyError" in str(w.message) for w in caught)

    def test_all_unexpected_attaches_cause(self) -> None:
        parsers = [_AlwaysUnexpectedParser()]
        with pytest.raises(ParseError) as excinfo:
            parse_with_parsers("test", "body", parsers)
        assert excinfo.value.__cause__ is not None

    def test_all_unexpected_multiple_attaches_exception_group(self) -> None:
        parsers = [_AlwaysUnexpectedParser(), _AlwaysUnexpectedParser()]
        with pytest.raises(ParseError) as excinfo:
            parse_with_parsers("test", "body", parsers)
        assert isinstance(excinfo.value.__cause__, ExceptionGroup)

    def test_sender_and_received_at_forwarded(self) -> None:
        parsers = [_AlwaysSucceedsParser()]
        ts = datetime.datetime(2026, 5, 2, 14, 23, 11, tzinfo=datetime.UTC)
        result = parse_with_parsers(
            "test", "body", parsers, sender="VK-TEST", received_at=ts
        )
        # _AlwaysSucceedsParser stuffs both into raw_description
        assert result.transaction is not None
        assert result.transaction.raw_description is not None
        assert "sender='VK-TEST'" in result.transaction.raw_description
        assert "received_at=" in result.transaction.raw_description


class TestBankSmsParser:
    def test_dispatch_runs_chain(self) -> None:
        class _TestBank(BankSmsParser):
            bank = "test"
            parsers = (_AlwaysSucceedsParser(),)

        result = _TestBank().parse("body")
        assert result.email_type == "test_alert"

    def test_dispatch_forwards_kwargs(self) -> None:
        class _TestBank(BankSmsParser):
            bank = "test"
            parsers = (_AlwaysSucceedsParser(),)

        ts = datetime.datetime(2026, 5, 2, 14, 23, 11, tzinfo=datetime.UTC)
        result = _TestBank().parse("body", sender="VK-TEST", received_at=ts)
        assert result.transaction is not None
        assert result.transaction.raw_description is not None
        assert "sender='VK-TEST'" in result.transaction.raw_description

    def test_subclass_must_declare_bank(self) -> None:
        with pytest.raises(TypeError):
            class _Bad(BankSmsParser):  # noqa: F841
                parsers = ()

    def test_subclass_must_declare_parsers(self) -> None:
        with pytest.raises(TypeError):
            class _Bad(BankSmsParser):  # noqa: F841
                bank = "test"
