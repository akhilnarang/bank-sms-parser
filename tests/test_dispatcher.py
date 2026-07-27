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


class _StubNamedMissParser(BaseSmsParser):
    """Stub-named parser that does NOT recognize the body (plain ParseError)."""

    bank = "test"
    email_type = "test_notice_stub"

    def parse(self, body, *, sender=None, received_at=None):
        raise ParseError("did not recognize")


class _MixedCaseStubMissParser(BaseSmsParser):
    """Stub with a mixed-case suffix; downstream greps msg.lower()."""

    bank = "test"
    email_type = "test_notice_Stub"

    def parse(self, body, *, sender=None, received_at=None):
        raise ParseError("did not recognize")


class _CrashesWithStubTextParser(BaseSmsParser):
    """Buggy parser whose unexpected exception text names a stub email_type."""

    bank = "test"
    email_type = "test_buggy"

    def parse(self, body, *, sender=None, received_at=None):
        raise RuntimeError("test_notice_stub misconfigured")


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

    def test_recognized_stub_keeps_stub_marker_in_message(self) -> None:
        # A ParserStubError means the stub positively recognized the shape;
        # downstream greps "_stub" in the message to disposition the row as
        # skipped, so the full email_type must appear verbatim.
        parsers = [_AlwaysParseErrorParser(), _AlwaysStubParser()]
        with pytest.raises(ParseError) as excinfo:
            parse_with_parsers("test", "body", parsers)
        assert "test_stub: ParserStubError" in str(excinfo.value)

    def test_unrecognized_stub_never_leaks_stub_marker(self) -> None:
        # A stub-named parser that raised plain ParseError did NOT recognize
        # the body. Its "_stub" suffix must be elided from the aggregate
        # message ("Tried:" list included), otherwise every unparseable SMS
        # for the bank would be dispositioned as skipped downstream.
        parsers = [_AlwaysParseErrorParser(), _StubNamedMissParser()]
        with pytest.raises(ParseError) as excinfo:
            parse_with_parsers("test", "body", parsers)
        msg = str(excinfo.value)
        assert "_stub" not in msg
        assert "test_notice (stub; did not recognize)" in msg

    def test_mixed_case_stub_suffix_is_still_elided(self) -> None:
        # Downstream greps msg.lower(), so the elision predicate must be
        # case-insensitive too.
        parsers = [_MixedCaseStubMissParser()]
        with pytest.raises(ParseError) as excinfo:
            parse_with_parsers("test", "body", parsers)
        assert "_stub" not in str(excinfo.value).lower()

    def test_unexpected_exception_text_cannot_smuggle_stub_marker(self) -> None:
        # A buggy parser crashing with a stub email_type in its exception
        # message must not trip the downstream "_stub" skip-grep; the raw
        # exception is still preserved on __cause__.
        parsers = [_CrashesWithStubTextParser()]
        with pytest.raises(ParseError) as excinfo:
            parse_with_parsers("test", "body", parsers)
        assert "_stub" not in str(excinfo.value).lower()
        assert "misconfigured" in str(excinfo.value)
        assert isinstance(excinfo.value.__cause__, RuntimeError)

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


def test_a_parser_declares_the_default_time_source() -> None:
    """A parser that says nothing declares that the body states the time."""

    class _QuietParser(BaseSmsParser):
        bank = "samplebank"
        email_type = "samplebank_debit_alert"

        def parse(self, body, *, sender=None, received_at=None) -> ParsedSms:
            return ParsedSms(
                email_type=self.email_type,
                bank=self.bank,
                transaction=SmsTransactionAlert(
                    direction="debit", amount=Money(amount=Decimal("1.00"))
                ),
            )

    assert _QuietParser.event_time_source == "body"
    result = parse_with_parsers("samplebank", "x", (_QuietParser(),))
    assert result.event_time_source == "body"


def test_the_dispatcher_copies_the_time_source_to_the_result() -> None:
    """The caller receives a model and not the class. Thus the dispatcher must
    copy the declaration to each result."""

    class _ArrivalParser(BaseSmsParser):
        bank = "samplebank"
        email_type = "samplebank_transfer_debit_alert"
        event_time_source = "message_arrival"

        def parse(self, body, *, sender=None, received_at=None) -> ParsedSms:
            return ParsedSms(
                email_type=self.email_type,
                bank=self.bank,
                transaction=SmsTransactionAlert(
                    direction="debit", amount=Money(amount=Decimal("1.00"))
                ),
            )

    result = parse_with_parsers("samplebank", "x", (_ArrivalParser(),))
    assert result.event_time_source == "message_arrival"


def test_a_parser_cannot_declare_an_unknown_time_source() -> None:
    """The base class checks the value when you define the class. A wrong
    value thus fails at import and not at run time."""
    with pytest.raises(TypeError, match="event_time_source"):

        class _BadParser(BaseSmsParser):
            bank = "samplebank"
            email_type = "samplebank_typo_alert"
            event_time_source = "arrival"

            def parse(self, body, *, sender=None, received_at=None):
                raise NotImplementedError  # pragma: no cover


def test_the_hdfc_neft_debit_parser_declares_message_arrival() -> None:
    """This SMS has no time in the body, and HDFC sends it at the moment of
    the transaction. The consumer needs this fact to trust the time less."""
    from bank_sms_parser.parsers.hdfc import HdfcAccountNeftDebitAlertParser

    assert HdfcAccountNeftDebitAlertParser.event_time_source == "message_arrival"


def test_a_subclass_cannot_escape_the_time_source_check() -> None:
    """A subclass can inherit bank and email_type and declare only
    event_time_source. The base class must still check that value. If it does
    not, a wrong value reaches the consumer, which reads it as "body" and
    gives the row the wide window."""

    class _Parent(BaseSmsParser):
        bank = "samplebank"
        email_type = "samplebank_parent_alert"

        def parse(self, body, *, sender=None, received_at=None) -> ParsedSms:
            raise NotImplementedError  # pragma: no cover

    with pytest.raises(TypeError, match="event_time_source"):

        class _Child(_Parent):
            event_time_source = "arrival"
