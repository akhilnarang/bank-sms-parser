"""Public-API invariants on parse_sms."""

import pytest
from bank_sms_parser import parse_sms
from bank_sms_parser.api import SUPPORTED_BANKS
from bank_sms_parser.exceptions import ParseError, UnsupportedSmsTypeError


class TestParseSmsTypeChecks:
    def test_non_string_bank_raises_unsupported(self) -> None:
        with pytest.raises(UnsupportedSmsTypeError):
            parse_sms(123, "body")  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]

    def test_non_string_body_raises_parse_error(self) -> None:
        with pytest.raises(ParseError):
            parse_sms("hdfc", 123)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]

    def test_empty_body_raises_parse_error(self) -> None:
        with pytest.raises(ParseError):
            parse_sms("hdfc", "")

    def test_whitespace_only_body_raises_parse_error(self) -> None:
        with pytest.raises(ParseError):
            parse_sms("hdfc", "   \t\n  ")

    def test_oversized_body_raises_parse_error(self) -> None:
        with pytest.raises(ParseError):
            parse_sms("hdfc", "x" * (10 * 1024 + 1))

    def test_unknown_bank_raises_unsupported(self) -> None:
        with pytest.raises(UnsupportedSmsTypeError):
            parse_sms("notabank", "Spent Rs.100 ...")


class TestSupportedBanks:
    def test_supported_banks_is_tuple_of_strings(self) -> None:
        assert isinstance(SUPPORTED_BANKS, tuple)
        for b in SUPPORTED_BANKS:
            assert isinstance(b, str)
            assert b == b.lower()
