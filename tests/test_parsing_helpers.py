"""Tests for parsing helpers (dates, amounts, text)."""

import datetime
from decimal import Decimal

import pytest
from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money
from bank_sms_parser.parsing.amounts import parse_amount, parse_money
from bank_sms_parser.parsing.dates import (
    parse_date,
    parse_datetime,
    received_at_to_ist,
)


class TestParseDate:
    def test_dd_mon_yy(self) -> None:
        # ICICI: "02-May-26"
        assert parse_date("02-May-26") == datetime.date(2026, 5, 2)

    def test_dd_mm_yy(self) -> None:
        # Axis: "02-05-26"  (dayfirst=True)
        assert parse_date("02-05-26") == datetime.date(2026, 5, 2)

    def test_dd_mm_yyyy_dayfirst(self) -> None:
        # Equitas: "01-05-2026" must be 1 May 2026, not 5 January.
        assert parse_date("01-05-2026") == datetime.date(2026, 5, 1)

    def test_dd_month_yyyy(self) -> None:
        # IDFC: "02 May 2026"
        assert parse_date("02 May 2026") == datetime.date(2026, 5, 2)

    def test_dd_month_yyyy_short(self) -> None:
        # OneCard payment-received: "29 Apr 2026"
        assert parse_date("29 Apr 2026") == datetime.date(2026, 4, 29)

    def test_garbage_raises_parse_error(self) -> None:
        with pytest.raises(ParseError):
            parse_date("not-a-date")

    def test_empty_raises_parse_error(self) -> None:
        with pytest.raises(ParseError):
            parse_date("")


class TestParseDatetime:
    def test_iso_with_colon_separator(self) -> None:
        # HDFC: "2026-05-02:00:17:56" — must be pre-normalized to space-separator.
        assert parse_datetime("2026-05-02:00:17:56") == datetime.datetime(
            2026, 5, 2, 0, 17, 56
        )

    def test_dd_mm_yyyy_with_am_pm(self) -> None:
        # Equitas: "01-05-2026 07:53:18 PM"
        assert parse_datetime("01-05-2026 07:53:18 PM") == datetime.datetime(
            2026, 5, 1, 19, 53, 18
        )

    def test_iso_t_separator(self) -> None:
        assert parse_datetime("2026-05-02T14:23:11") == datetime.datetime(
            2026, 5, 2, 14, 23, 11
        )

    def test_garbage_raises_parse_error(self) -> None:
        with pytest.raises(ParseError):
            parse_datetime("not-a-date")


class TestReceivedAtToIst:
    def test_utc_to_ist(self) -> None:
        # 21:00 UTC == 02:30 IST next day
        utc = datetime.datetime(2026, 5, 1, 21, 0, 0, tzinfo=datetime.UTC)
        ist = received_at_to_ist(utc)
        assert ist.date() == datetime.date(2026, 5, 2)
        assert ist.time() == datetime.time(2, 30)

    def test_ist_input_returns_ist(self) -> None:
        from zoneinfo import ZoneInfo

        already_ist = datetime.datetime(2026, 5, 2, 2, 30, tzinfo=ZoneInfo("Asia/Kolkata"))
        ist = received_at_to_ist(already_ist)
        assert ist.date() == datetime.date(2026, 5, 2)
        assert ist.time() == datetime.time(2, 30)

    def test_naive_input_raises(self) -> None:
        with pytest.raises(ParseError):
            received_at_to_ist(datetime.datetime(2026, 5, 1, 21, 0, 0))


class TestParseAmount:
    @pytest.mark.parametrize("s, expected", [
        ("1,604.00", Decimal("1604.00")),
        ("99,99,999.99", Decimal("9999999.99")),  # Indian grouping
        ("35437.00", Decimal("35437.00")),
        ("3000", Decimal("3000")),
        ("99,999.99", Decimal("99999.99")),
    ])
    def test_bare_numeric(self, s: str, expected: Decimal) -> None:
        assert parse_amount(s) == expected

    def test_empty_raises(self) -> None:
        with pytest.raises(ParseError):
            parse_amount("")

    def test_non_numeric_raises(self) -> None:
        with pytest.raises(ParseError):
            parse_amount("abc")


class TestParseMoney:
    @pytest.mark.parametrize("s, amount, currency", [
        ("Rs.3000", Decimal("3000"), "INR"),
        ("Rs 3000", Decimal("3000"), "INR"),
        ("Rs. 1.00", Decimal("1.00"), "INR"),
        ("INR 15000", Decimal("15000"), "INR"),
        ("INR. 99,999.99", Decimal("99999.99"), "INR"),
        ("USD 106.20", Decimal("106.20"), "USD"),
        ("EUR 50.00", Decimal("50.00"), "EUR"),
        ("GBP 10", Decimal("10"), "GBP"),
    ])
    def test_with_prefix(self, s: str, amount: Decimal, currency: str) -> None:
        m = parse_money(s)
        assert m == Money(amount=amount, currency=currency)

    def test_bare_numeric_raises(self) -> None:
        # parse_money REQUIRES a currency prefix — bare numerics are parse_amount's job.
        with pytest.raises(ParseError):
            parse_money("3000")

    def test_empty_raises(self) -> None:
        with pytest.raises(ParseError):
            parse_money("")

    def test_unknown_three_letter_code_accepted(self) -> None:
        # Any 3-letter uppercase ASCII code is accepted as the currency.
        m = parse_money("AED 100")
        assert m.currency == "AED"
