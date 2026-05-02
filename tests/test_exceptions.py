"""Sanity tests for exception class hierarchy."""

import pytest
from bank_sms_parser.exceptions import (
    ParseError,
    ParserStubError,
    UnsupportedSmsTypeError,
)


def test_parse_error_is_exception() -> None:
    assert issubclass(ParseError, Exception)


def test_parser_stub_error_is_not_implemented_error() -> None:
    # Mirrors bank-email-parser exactly — see spec §9.
    assert issubclass(ParserStubError, NotImplementedError)


def test_parser_stub_error_is_not_subclass_of_parse_error() -> None:
    # If this changes, the dispatcher must catch both explicitly.
    assert not issubclass(ParserStubError, ParseError)


def test_unsupported_sms_type_error_is_exception() -> None:
    assert issubclass(UnsupportedSmsTypeError, Exception)


def test_exceptions_can_be_raised_and_caught() -> None:
    with pytest.raises(ParseError):
        raise ParseError("test")
    with pytest.raises(ParserStubError):
        raise ParserStubError("test")
    with pytest.raises(UnsupportedSmsTypeError):
        raise UnsupportedSmsTypeError("test")
