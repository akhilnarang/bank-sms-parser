"""Date and datetime parsing helpers for SMS bodies."""

import datetime
import re
from zoneinfo import ZoneInfo

from dateutil import parser as _dateutil

from bank_sms_parser.exceptions import ParseError

_IST = ZoneInfo("Asia/Kolkata")

# HDFC ships datetimes like "2026-05-02:00:17:56" (colon between date and time).
# dateutil cannot parse this directly; rewrite to a space separator first.
_COLON_DATETIME = re.compile(r"^(\d{4}-\d{2}-\d{2}):(\d{2}:\d{2}:\d{2})$")

# ISO-8601-like strings start with a 4-digit year; use yearfirst=True so that
# "2026-05-02" is unambiguously parsed as year=2026, month=05, day=02 even
# when dayfirst=True would otherwise flip month and day on ambiguous positions.
_YEAR_FIRST = re.compile(r"^\d{4}[-T]")


def _normalize_datetime_string(s: str) -> str:
    s = s.strip()
    m = _COLON_DATETIME.match(s)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return s


def _parse_kwargs(s: str) -> dict[str, bool]:
    """Return the correct dayfirst/yearfirst flags for the given string."""
    if _YEAR_FIRST.match(s):
        return {"yearfirst": True, "dayfirst": False}
    return {"dayfirst": True}


def parse_date(s: str) -> datetime.date:
    """Parse a date string from an SMS body. dayfirst=True for Indian formats."""
    if not s or not s.strip():
        raise ParseError("parse_date: empty input")
    cleaned = s.strip()
    try:
        return _dateutil.parse(cleaned, **_parse_kwargs(cleaned)).date()
    except (_dateutil.ParserError, ValueError, OverflowError) as exc:
        raise ParseError(f"parse_date: cannot parse {s!r}: {exc}") from exc


def parse_datetime(s: str) -> datetime.datetime:
    """Parse a datetime string from an SMS body. dayfirst=True for Indian formats.

    Pre-normalizes HDFC's ``YYYY-MM-DD:HH:MM:SS`` colon-separator format to a
    space-separator before delegating to ``dateutil``.
    """
    if not s or not s.strip():
        raise ParseError("parse_datetime: empty input")
    normalized = _normalize_datetime_string(s)
    try:
        return _dateutil.parse(normalized, **_parse_kwargs(normalized))
    except (_dateutil.ParserError, ValueError, OverflowError) as exc:
        raise ParseError(f"parse_datetime: cannot parse {s!r}: {exc}") from exc


def received_at_to_ist(received_at: datetime.datetime) -> datetime.datetime:
    """Convert a tz-aware ``received_at`` to Asia/Kolkata.

    SMS ``received_at`` is stored as UTC (per Part 1 §4); transactional dates
    on Indian SMSes are India-local. Callers that fall back to ``received_at``
    for ``transaction_date`` / ``transaction_time`` MUST go through this helper
    so a 02:30 IST SMS does not land on the previous UTC day.
    """
    if received_at.tzinfo is None or received_at.utcoffset() is None:
        raise ParseError("received_at_to_ist: input must be timezone-aware")
    return received_at.astimezone(_IST)
