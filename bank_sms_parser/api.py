"""Public API: parse_sms() entry point and SUPPORTED_BANKS registry."""

import datetime

from bank_sms_parser.exceptions import ParseError, UnsupportedSmsTypeError
from bank_sms_parser.models import ParsedSms
from bank_sms_parser.parsers import PARSERS

SUPPORTED_BANKS: tuple[str, ...] = tuple(PARSERS)

_MAX_BODY_BYTES = 10 * 1024


def parse_sms(
    bank: str,
    body: str,
    *,
    sender: str | None = None,
    received_at: datetime.datetime | None = None,
) -> ParsedSms:
    """Parse an SMS body for a given bank."""
    if not isinstance(bank, str):
        raise UnsupportedSmsTypeError(
            f"Expected 'bank' to be a string, got {type(bank).__name__}"
        )
    if not isinstance(body, str):
        raise ParseError(f"Expected 'body' to be a string, got {type(body).__name__}")
    if not body.strip():
        raise ParseError("Empty SMS body")
    if len(body) > _MAX_BODY_BYTES:
        raise ParseError(f"SMS body too large (>{_MAX_BODY_BYTES} bytes)")
    normalized_bank = bank.strip().lower()
    if normalized_bank not in PARSERS:
        raise UnsupportedSmsTypeError(
            f"Unknown bank: {normalized_bank!r}. Supported: {tuple(PARSERS)}"
        )
    return PARSERS[normalized_bank]().parse(
        body, sender=sender, received_at=received_at
    )
