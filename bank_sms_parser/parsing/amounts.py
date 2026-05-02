"""Amount and currency parsing helpers for SMS bodies."""

import re
from decimal import Decimal, InvalidOperation

from bank_sms_parser.exceptions import ParseError
from bank_sms_parser.models import Money

# Bare-numeric token: digits with optional commas (Indian grouping) and optional
# decimal part. Anchors the entire string.
_BARE_NUMERIC = re.compile(r"^\d{1,3}(?:,\d{1,3})*(?:\.\d+)?$|^\d+(?:\.\d+)?$")

# Amount with currency prefix:
#   - INR / Rs. / Rs / INR.  → INR
#   - any 3-letter uppercase ASCII code → that code
_PREFIXED = re.compile(
    r"^\s*(?P<prefix>Rs\.?|INR\.?|[A-Z]{3})\s*(?P<num>\d{1,3}(?:,\d{1,3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s*$",
)


def parse_amount(s: str) -> Decimal:
    """Parse a bare numeric amount (no currency prefix). Returns Decimal."""
    if not s or not s.strip():
        raise ParseError("parse_amount: empty input")
    cleaned = s.strip()
    if not _BARE_NUMERIC.match(cleaned):
        raise ParseError(f"parse_amount: not a bare numeric: {s!r}")
    try:
        return Decimal(cleaned.replace(",", ""))
    except InvalidOperation as exc:
        raise ParseError(f"parse_amount: cannot parse {s!r}: {exc}") from exc


def parse_money(s: str) -> Money:
    """Parse an amount with a currency prefix into a Money.

    Accepts ``Rs.X``, ``Rs X``, ``INR X``, ``INR. X`` (all → INR), and any
    three-letter uppercase ASCII code (``USD 106.20`` → currency="USD").
    Raises ParseError if there is no recognizable prefix — bare numerics
    must use ``parse_amount`` instead.
    """
    if not s or not s.strip():
        raise ParseError("parse_money: empty input")
    m = _PREFIXED.match(s)
    if not m:
        raise ParseError(f"parse_money: missing or unrecognized currency prefix: {s!r}")
    prefix = m.group("prefix")
    num = m.group("num")
    currency = "INR" if prefix in {"Rs", "Rs.", "INR", "INR."} else prefix
    try:
        amount = Decimal(num.replace(",", ""))
    except InvalidOperation as exc:
        raise ParseError(f"parse_money: cannot parse amount {num!r}: {exc}") from exc
    return Money(amount=amount, currency=currency)
